import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import sqlite3
import uuid
import re
import os
import time
import asyncio
import subprocess
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# ─── Config ───
TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", "1479770170389172285"))

# ─── Database ───
db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")
db.executescript("""
    CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        created_by TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        redeemed_by TEXT DEFAULT NULL,
        redeemed_at INTEGER DEFAULT NULL,
        revoked INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS authorized_users (
        user_id TEXT PRIMARY KEY,
        key_used TEXT NOT NULL,
        authorized_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS panels (
        user_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'stopped',
        ticket_category TEXT DEFAULT 'None',
        command TEXT DEFAULT 'None',
        transfer_command TEXT DEFAULT 'None',
        custom_id TEXT DEFAULT 'None',
        updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS selfbot_sessions (
        user_id TEXT PRIMARY KEY,
        token TEXT NOT NULL,
        process_id INTEGER,
        status TEXT DEFAULT 'offline',
        started_at INTEGER,
        last_ping INTEGER,
        settings TEXT DEFAULT '{}'
    );
""")
db.commit()

def now_ms(): return int(time.time() * 1000)
def parse_duration(text):
    m = re.match(r"^(\d+)(m|h|d)$", text.strip().lower())
    if not m: return None
    val, unit = int(m.group(1)), m.group(2)
    return val * {"m": 60000, "h": 3600000, "d": 86400000}[unit]

def gen_key(): return "-".join(uuid.uuid4().hex[:12].upper()[i:i+4] for i in range(0, 12, 4))
def is_authorized(uid): 
    row = db.execute("SELECT * FROM authorized_users WHERE user_id = ? AND expires_at > ?", (str(uid), now_ms())).fetchone()
    return dict(row) if row else None
def get_panel(uid): 
    row = db.execute("SELECT * FROM panels WHERE user_id = ?", (str(uid),)).fetchone()
    return dict(row) if row else None
def upsert_panel(uid, **kwargs):
    existing = get_panel(uid)
    if existing:
        sets, vals = [], []
        for k, v in kwargs.items():
            if v is not None: sets.append(f"{k} = ?"); vals.append(v)
        if sets:
            sets.append("updated_at = ?"); vals.extend([now_ms(), str(uid)])
            db.execute(f"UPDATE panels SET {', '.join(sets)} WHERE user_id = ?", vals); db.commit()
    else:
        db.execute("INSERT INTO panels VALUES (?,?,?,?,?,?,?)", (str(uid), kwargs.get("status", "stopped"), kwargs.get("ticket_category", "None"), kwargs.get("command", "None"), kwargs.get("transfer_command", "None"), kwargs.get("custom_id", "None"), now_ms())); db.commit()
    return get_panel(uid)

# ─── SelfBot Manager ───
class SelfBotManager:
    def __init__(self):
        self.cleanup_sessions()
    
    def cleanup_sessions(self):
        db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE status = 'online'")
        db.commit()
    
    def start_selfbot(self, user_id: str, token: str) -> bool:
        existing = db.execute("SELECT * FROM selfbot_sessions WHERE user_id = ?", (user_id,)).fetchone()
        if existing and existing['process_id']:
            try:
                import psutil
                proc = psutil.Process(existing['process_id'])
                if proc.is_running():
                    return False
            except:
                pass
        
        self.stop_selfbot(user_id)
        
        env = os.environ.copy()
        env['SELFBOT_TOKEN'] = token
        env['OWNER_ID'] = str(user_id)
        env['BOT_API_URL'] = 'http://localhost:8080'
        
        try:
            process = subprocess.Popen(
                [sys.executable, 'selfbot_worker.py'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            db.execute("""
                INSERT OR REPLACE INTO selfbot_sessions 
                (user_id, token, process_id, status, started_at, last_ping) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, token, process.pid, 'starting', now_ms(), now_ms()))
            db.commit()
            
            return True
        except Exception as e:
            print(f"Failed to start selfbot: {e}")
            return False
    
    def stop_selfbot(self, user_id: str) -> bool:
        session = db.execute("SELECT * FROM selfbot_sessions WHERE user_id = ?", (user_id,)).fetchone()
        
        if session and session['process_id']:
            try:
                import psutil
                proc = psutil.Process(session['process_id'])
                proc.terminate()
                proc.wait(timeout=5)
            except:
                pass
        
        db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
        db.commit()
        return True
    
    def get_status(self, user_id: str) -> dict:
        session = db.execute("SELECT * FROM selfbot_sessions WHERE user_id = ?", (user_id,)).fetchone()
        if not session:
            return {'status': 'offline', 'running': False}
        
        running = False
        if session['process_id']:
            try:
                import psutil
                proc = psutil.Process(session['process_id'])
                running = proc.is_running()
                if not running:
                    db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
                    db.commit()
            except:
                db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
                db.commit()
        
        return {
            'status': session['status'] if running else 'offline',
            'running': running,
            'started_at': session['started_at'],
            'last_ping': session['last_ping']
        }

manager = SelfBotManager()

# ─── UI ───
def build_panel_embed(uid, data, selfbot_status=None):
    running = data["status"] == "running"
    color = 0x57F287 if running else 0xED4245
    
    embed = discord.Embed(title="🎛️ Control Panel", color=color, timestamp=datetime.utcnow())
    embed.add_field(name="📊 Panel Status", value="🟢 Running" if running else "🔴 Stopped", inline=True)
    
    if selfbot_status:
        sb_emoji = "🟢" if selfbot_status['running'] else "🔴"
        embed.add_field(name="🤖 SelfBot", value=f"{sb_emoji} {selfbot_status['status'].title()}", inline=True)
    else:
        embed.add_field(name="🤖 SelfBot", value="⚫ Offline", inline=True)
    
    embed.add_field(name="🏷️ Category", value=f"`{data['ticket_category']}`", inline=True)
    embed.add_field(name="⚡ Command", value=f"`{data['command']}`", inline=True)
    embed.add_field(name="🔄 Transfer", value=f"`{data['transfer_command']}`", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{data['custom_id']}`", inline=True)
    embed.set_footer(text=f"Owner: {uid}")
    return embed

class PanelView(ui.View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.uid = uid
        self.refresh()
        
    def refresh(self):
        self.clear_items()
        data = get_panel(self.uid)
        running = data and data["status"] == "running"
        sb_status = manager.get_status(str(self.uid))
        
        start_btn = ui.Button(label="▶ Start Panel", style=discord.ButtonStyle.success, disabled=running)
        stop_btn = ui.Button(label="⏹ Stop Panel", style=discord.ButtonStyle.danger, disabled=not running)
        start_btn.callback = self.start_panel_cb
        stop_btn.callback = self.stop_panel_cb
        self.add_item(start_btn)
        self.add_item(stop_btn)
        
        sb_running = sb_status['running']
        start_sb = ui.Button(label="🚀 Start SelfBot", style=discord.ButtonStyle.success, disabled=sb_running, row=1)
        stop_sb = ui.Button(label="🛑 Stop SelfBot", style=discord.ButtonStyle.danger, disabled=not sb_running, row=1)
        login_sb = ui.Button(label="🔑 Login SelfBot", style=discord.ButtonStyle.primary, disabled=sb_running, row=1)
        
        start_sb.callback = self.start_sb_cb
        stop_sb.callback = self.stop_sb_cb
        login_sb.callback = self.login_sb_cb
        
        self.add_item(start_sb)
        self.add_item(stop_sb)
        self.add_item(login_sb)
        
        for key, label, emoji in [("ticket_category", "Category", "🏷️"), ("command", "Command", "⚡"), 
                                  ("transfer_command", "Transfer", "🔄"), ("custom_id", "ID", "🆔")]:
            btn = ui.Button(label=f"Edit {label}", style=discord.ButtonStyle.secondary, emoji=emoji, row=2)
            btn.callback = self.make_edit_cb(key, label)
            self.add_item(btn)
    
    async def start_panel_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: 
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        data = upsert_panel(self.uid, status="running")
        sb_status = manager.get_status(str(self.uid))
        self.refresh()
        await interaction.response.edit_message(embed=build_panel_embed(self.uid, data, sb_status), view=self)
        
    async def stop_panel_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: 
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        data = upsert_panel(self.uid, status="stopped")
        sb_status = manager.get_status(str(self.uid))
        self.refresh()
        await interaction.response.edit_message(embed=build_panel_embed(self.uid, data, sb_status), view=self)
    
    async def start_sb_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        
        session = db.execute("SELECT token FROM selfbot_sessions WHERE user_id = ?", (str(self.uid),)).fetchone()
        if not session:
            return await interaction.response.send_message("❌ Please login first with `/loginselfbot`", ephemeral=True)
        
        success = manager.start_selfbot(str(self.uid), session['token'])
        if success:
            await interaction.response.send_message("🚀 SelfBot starting...", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ SelfBot already running or failed to start", ephemeral=True)
    
    async def stop_sb_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        
        manager.stop_selfbot(str(self.uid))
        await interaction.response.send_message("🛑 SelfBot stopped", ephemeral=True)
    
    async def login_sb_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        
        modal = LoginModal(self)
        await interaction.response.send_modal(modal)
        
    def make_edit_cb(self, key, label):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.uid: 
                return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
            modal = EditModal(self, key, label)
            await interaction.response.send_modal(modal)
        return callback

class LoginModal(ui.Modal, title="🔑 SelfBot Login"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.token_input = ui.TextInput(
            label="Discord Token",
            placeholder="Enter your alt account token...",
            required=True,
            min_length=10,
            max_length=100
        )
        self.add_item(self.token_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        token = self.token_input.value
        
        if not re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', token):
            return await interaction.response.send_message("❌ Invalid token format", ephemeral=True)
        
        db.execute("""
            INSERT OR REPLACE INTO selfbot_sessions (user_id, token, status, started_at, last_ping, settings)
            VALUES (?, ?, 'offline', NULL, NULL, '{}')
        """, (str(interaction.user.id), token))
        db.commit()
        
        await interaction.response.send_message("✅ Token saved! Click 🚀 Start SelfBot to launch", ephemeral=True)

class EditModal(ui.Modal):
    def __init__(self, view, key, label):
        super().__init__(title=f"Edit {label}")
        self.view = view
        self.key = key
        self.input = ui.TextInput(label=label, max_length=100, required=True)
        self.add_item(self.input)
        
    async def on_submit(self, interaction: discord.Interaction):
        kwargs = {self.key: self.input.value}
        data = upsert_panel(self.view.uid, **kwargs)
        sb_status = manager.get_status(str(interaction.user.id))
        self.view.refresh()
        await interaction.response.edit_message(embed=build_panel_embed(self.view.uid, data, sb_status), view=self.view)

# ─── Bot Setup ───
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online as {bot.user}")

@bot.tree.command(name="generatekey", description="🔑 Generate access key (Owner only)")
@app_commands.describe(duration="Duration: 30m, 1h, 7d")
async def generatekey(interaction: discord.Interaction, duration: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    ms = parse_duration(duration)
    if not ms: return await interaction.response.send_message("❌ Invalid format", ephemeral=True)
    key = gen_key()
    db.execute("INSERT INTO keys VALUES (?,?,?,?,?,NULL,0)", (key, str(interaction.user.id), now_ms(), now_ms() + ms, None))
    db.commit()
    embed = discord.Embed(title="🔑 Key Generated", color=0x57F287)
    embed.add_field(name="Key", value=f"```{key}```")
    embed.add_field(name="Expires", value=f"<t:{(now_ms() + ms)//1000}:R>")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="redeemkey", description="✅ Redeem access key")
@app_commands.describe(key="Your access key")
async def redeemkey(interaction: discord.Interaction, key: str):
    row = db.execute("SELECT * FROM keys WHERE key = ?", (key,)).fetchone()
    if not row: return await interaction.response.send_message("❌ Invalid key", ephemeral=True)
    if row["revoked"]: return await interaction.response.send_message("❌ Revoked", ephemeral=True)
    if row["expires_at"] <= now_ms(): return await interaction.response.send_message("❌ Expired", ephemeral=True)
    if row["redeemed_by"]: return await interaction.response.send_message("❌ Already used", ephemeral=True)
    
    uid = str(interaction.user.id)
    db.execute("UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE key = ?", (uid, now_ms(), key))
    db.execute("INSERT OR REPLACE INTO authorized_users VALUES (?,?,?,?)", (uid, key, now_ms(), row["expires_at"]))
    db.commit()
    await interaction.response.send_message("✅ Access granted! Use `/panel` to open control center", ephemeral=True)

@bot.tree.command(name="loginselfbot", description="🔑 Login your selfbot alt account")
async def loginselfbot(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not is_authorized(interaction.user.id):
        return await interaction.response.send_message("❌ Redeem key first", ephemeral=True)
    
    modal = LoginModal(PanelView(interaction.user.id))
    await interaction.response.send_modal(modal)

@bot.tree.command(name="panel", description="🎛️ Open control panel")
async def panel(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not is_authorized(interaction.user.id):
        return await interaction.response.send_message("❌ Redeem key first: `/redeemkey`", ephemeral=True)
    
    data = get_panel(interaction.user.id) or upsert_panel(interaction.user.id)
    sb_status = manager.get_status(str(interaction.user.id))
    
    await interaction.response.send_message(
        embed=build_panel_embed(interaction.user.id, data, sb_status), 
        view=PanelView(interaction.user.id), 
        ephemeral=True
    )

@bot.tree.command(name="selfbotstatus", description="📊 Check selfbot status")
async def selfbotstatus(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not is_authorized(interaction.user.id):
        return await interaction.response.send_message("❌ Redeem key first", ephemeral=True)
    
    status = manager.get_status(str(interaction.user.id))
    
    embed = discord.Embed(title="🤖 SelfBot Status", color=0x57F287 if status['running'] else 0xED4245)
    embed.add_field(name="Status", value=status['status'].title(), inline=True)
    embed.add_field(name="Running", value="✅ Yes" if status['running'] else "❌ No", inline=True)
    
    if status['started_at']:
        embed.add_field(name="Started", value=f"<t:{status['started_at']//1000}:R>", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── API Server for SelfBot Communication ───
from aiohttp import web

async def api_handler(request):
    path = request.path
    
    if path.startswith('/settings/'):
        user_id = path.split('/')[-1]
        panel = get_panel(user_id)
        if panel:
            return web.json_response({
                'status': panel['status'],
                'ticket_category': panel['ticket_category'],
                'command': panel['command'],
                'transfer_command': panel['transfer_command'],
                'custom_id': panel['custom_id']
            })
    
    return web.json_response({'error': 'not found'}, status=404)

async def health_handler(request):
    return web.Response(text='OK', status=200)

async def start_api_server():
    app = web.Application()
    app.router.add_get('/settings/{user_id}', api_handler)
    app.router.add_get('/health', health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("✅ API server running on localhost:8080")

# ═══════════════════════════════════════════════════════
# CLIENT LOGIN / BOT RUN - THE ACTUAL LOGIN CALL
# ═══════════════════════════════════════════════════════
async def main():
    # Start API server first
    await start_api_server()
    
    # ═══ CLIENT LOGIN HERE ═══
    # This is where the bot actually logs in to Discord
    await bot.start(TOKEN)
    # Alternative: bot.run(TOKEN) - but we use start() for async

if __name__ == '__main__':
    asyncio.run(main())
