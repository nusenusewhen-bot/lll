import os
import sys

# ═══════════════════════════════════════════════════════
# IMMEDIATE HEALTHCHECK SERVER (STARTS IN <100ms)
# ═══════════════════════════════════════════════════════
import http.server
import socketserver
import threading

PORT = int(os.environ.get('PORT', 8080))

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def start_health_server():
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(('0.0.0.0', PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f'✅ Health server on port {PORT}', flush=True)
    return server

# START HEALTH SERVER IMMEDIATELY
health_server = start_health_server()

# ═══════════════════════════════════════════════════════
# NOW LOAD DISCORD BOT
# ═══════════════════════════════════════════════════════
import discord
from discord import app_commands, ui
from discord.ext import commands
import sqlite3
import uuid
import re
import time
import asyncio
import subprocess
from datetime import datetime

# Config
TOKEN = os.environ.get("DISCORD_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "1479770170389172285"))

if not TOKEN:
    print("❌ DISCORD_TOKEN not set!", flush=True)
    sys.exit(1)

print(f"🔑 Token: {TOKEN[:20]}...", flush=True)

# Database
db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
    CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, created_by TEXT, created_at INTEGER, expires_at INTEGER, redeemed_by TEXT, redeemed_at INTEGER, revoked INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS authorized_users (user_id TEXT PRIMARY KEY, key_used TEXT, authorized_at INTEGER, expires_at INTEGER);
    CREATE TABLE IF NOT EXISTS panels (user_id TEXT PRIMARY KEY, status TEXT DEFAULT 'stopped', ticket_category TEXT DEFAULT 'None', command TEXT DEFAULT 'None', transfer_command TEXT DEFAULT 'None', custom_id TEXT DEFAULT 'None', updated_at INTEGER);
    CREATE TABLE IF NOT EXISTS selfbot_sessions (user_id TEXT PRIMARY KEY, token TEXT, process_id INTEGER, status TEXT DEFAULT 'offline', started_at INTEGER, last_ping INTEGER, settings TEXT DEFAULT '{}');
""")
db.commit()

def now_ms(): return int(time.time() * 1000)
def gen_key(): return "-".join(uuid.uuid4().hex[:12].upper()[i:i+4] for i in range(0, 12, 4))
def parse_duration(text):
    m = re.match(r"^(\d+)(m|h|d)$", text.strip().lower())
    if not m: return None
    val, unit = int(m.group(1)), m.group(2)
    return val * {"m": 60000, "h": 3600000, "d": 86400000}[unit]
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

# SelfBot Manager
class SelfBotManager:
    def cleanup(self):
        db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE status = 'online'")
        db.commit()
    
    def start(self, user_id, token):
        self.cleanup()
        env = os.environ.copy()
        env['SELFBOT_TOKEN'] = token
        env['OWNER_ID'] = str(user_id)
        try:
            proc = subprocess.Popen([sys.executable, 'selfbot_worker.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            db.execute("INSERT OR REPLACE INTO selfbot_sessions (user_id, token, process_id, status, started_at, last_ping) VALUES (?, ?, ?, ?, ?, ?)", 
                      (user_id, token, proc.pid, 'starting', now_ms(), now_ms()))
            db.commit()
            return True
        except Exception as e:
            print(f"Start failed: {e}", flush=True)
            return False
    
    def stop(self, user_id):
        session = db.execute("SELECT * FROM selfbot_sessions WHERE user_id = ?", (user_id,)).fetchone()
        if session and session['process_id']:
            try:
                import psutil
                psutil.Process(session['process_id']).terminate()
            except:
                pass
        db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
        db.commit()
    
    def status(self, user_id):
        session = db.execute("SELECT * FROM selfbot_sessions WHERE user_id = ?", (user_id,)).fetchone()
        if not session:
            return {'status': 'offline', 'running': False}
        running = False
        if session['process_id']:
            try:
                import psutil
                running = psutil.Process(session['process_id']).is_running()
                if not running:
                    db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
                    db.commit()
            except:
                db.execute("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?", (user_id,))
                db.commit()
        return {'status': session['status'] if running else 'offline', 'running': running}

manager = SelfBotManager()
manager.cleanup()

# UI
def build_embed(uid, data, sb=None):
    running = data["status"] == "running"
    color = 0x57F287 if running else 0xED4245
    embed = discord.Embed(title="🎛️ Control Panel", color=color, timestamp=datetime.utcnow())
    embed.add_field(name="📊 Panel", value="🟢 Running" if running else "🔴 Stopped", inline=True)
    embed.add_field(name="🤖 SelfBot", value=f"{'🟢' if sb and sb['running'] else '🔴'} {sb['status'].title() if sb else 'Offline'}", inline=True)
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
        sb = manager.status(str(self.uid))
        
        start = ui.Button(label="▶ Start", style=discord.ButtonStyle.success, disabled=running)
        stop = ui.Button(label="⏹ Stop", style=discord.ButtonStyle.danger, disabled=not running)
        start.callback = self.start_cb; stop.callback = self.stop_cb
        self.add_item(start); self.add_item(stop)
        
        sb_run = sb['running']
        start_sb = ui.Button(label="🚀 Start SB", style=discord.ButtonStyle.success, disabled=sb_run, row=1)
        stop_sb = ui.Button(label="🛑 Stop SB", style=discord.ButtonStyle.danger, disabled=not sb_run, row=1)
        login_sb = ui.Button(label="🔑 Login", style=discord.ButtonStyle.primary, disabled=sb_run, row=1)
        start_sb.callback = self.start_sb_cb; stop_sb.callback = self.stop_sb_cb; login_sb.callback = self.login_sb_cb
        self.add_item(start_sb); self.add_item(stop_sb); self.add_item(login_sb)
        
        for key, label, emoji in [("ticket_category", "Category", "🏷️"), ("command", "Command", "⚡"), 
                                  ("transfer_command", "Transfer", "🔄"), ("custom_id", "ID", "🆔")]:
            btn = ui.Button(label=f"Edit {label}", style=discord.ButtonStyle.secondary, emoji=emoji, row=2)
            btn.callback = self.make_edit_cb(key, label)
            self.add_item(btn)
    
    async def start_cb(self, i):
        if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
        data = upsert_panel(self.uid, status="running")
        self.refresh()
        await i.response.edit_message(embed=build_embed(self.uid, data, manager.status(str(self.uid))), view=self)
        
    async def stop_cb(self, i):
        if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
        data = upsert_panel(self.uid, status="stopped")
        self.refresh()
        await i.response.edit_message(embed=build_embed(self.uid, data, manager.status(str(self.uid))), view=self)
    
    async def start_sb_cb(self, i):
        if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
        s = db.execute("SELECT token FROM selfbot_sessions WHERE user_id = ?", (str(self.uid),)).fetchone()
        if not s: return await i.response.send_message("❌ Login first with `/loginselfbot`", ephemeral=True)
        manager.start(str(self.uid), s['token'])
        await i.response.send_message("🚀 Starting...", ephemeral=True)
    
    async def stop_sb_cb(self, i):
        if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
        manager.stop(str(self.uid))
        await i.response.send_message("🛑 Stopped", ephemeral=True)
    
    async def login_sb_cb(self, i):
        if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
        await i.response.send_modal(LoginModal(self))
        
    def make_edit_cb(self, key, label):
        async def cb(i):
            if i.user.id != self.uid: return await i.response.send_message("❌ Not yours", ephemeral=True)
            await i.response.send_modal(EditModal(self, key, label))
        return cb

class LoginModal(ui.Modal, title="🔑 Login"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.inp = ui.TextInput(label="Token", placeholder="Discord token...", required=True, min_length=10, max_length=100)
        self.add_item(self.inp)
    
    async def on_submit(self, i):
        t = self.inp.value
        if not re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', t):
            return await i.response.send_message("❌ Invalid format", ephemeral=True)
        db.execute("INSERT OR REPLACE INTO selfbot_sessions (user_id, token, status) VALUES (?, ?, 'offline')", (str(i.user.id), t))
        db.commit()
        await i.response.send_message("✅ Saved! Click 🚀 Start SB", ephemeral=True)

class EditModal(ui.Modal):
    def __init__(self, view, key, label):
        super().__init__(title=f"Edit {label}")
        self.view = view; self.key = key
        self.inp = ui.TextInput(label=label, max_length=100, required=True)
        self.add_item(self.inp)
        
    async def on_submit(self, i):
        data = upsert_panel(self.view.uid, **{self.key: self.inp.value})
        self.view.refresh()
        await i.response.edit_message(embed=build_embed(self.view.uid, data, manager.status(str(i.user.id))), view=self.view)

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅✅✅ LOGGED IN: {bot.user} (ID: {bot.user.id}) ✅✅✅", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands", flush=True)
    except Exception as e:
        print(f"❌ Sync failed: {e}", flush=True)

@bot.tree.command(name="generatekey", description="🔑 Generate key (Owner only)")
@app_commands.describe(duration="30m, 1h, 7d")
async def cmd_genkey(i: discord.Interaction, duration: str):
    await i.response.defer(ephemeral=True)
    if i.user.id != OWNER_ID:
        return await i.followup.send("❌ Owner only", ephemeral=True)
    ms = parse_duration(duration)
    if not ms: return await i.followup.send("❌ Invalid format", ephemeral=True)
    key = gen_key()
    db.execute("INSERT INTO keys VALUES (?,?,?,?,?,NULL,0)", (key, str(i.user.id), now_ms(), now_ms() + ms, None))
    db.commit()
    embed = discord.Embed(title="🔑 Key Generated", color=0x57F287)
    embed.add_field(name="Key", value=f"```{key}```")
    embed.add_field(name="Expires", value=f"<t:{(now_ms() + ms)//1000}:R>")
    await i.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="redeemkey", description="✅ Redeem key")
@app_commands.describe(key="Your key")
async def cmd_redeem(i: discord.Interaction, key: str):
    await i.response.defer(ephemeral=True)
    row = db.execute("SELECT * FROM keys WHERE key = ?", (key,)).fetchone()
    if not row: return await i.followup.send("❌ Invalid", ephemeral=True)
    if row["revoked"]: return await i.followup.send("❌ Revoked", ephemeral=True)
    if row["expires_at"] <= now_ms(): return await i.followup.send("❌ Expired", ephemeral=True)
    if row["redeemed_by"]: return await i.followup.send("❌ Used", ephemeral=True)
    uid = str(i.user.id)
    db.execute("UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE key = ?", (uid, now_ms(), key))
    db.execute("INSERT OR REPLACE INTO authorized_users VALUES (?,?,?,?)", (uid, key, now_ms(), row["expires_at"]))
    db.commit()
    await i.followup.send("✅ Access granted! Use `/panel`", ephemeral=True)

@bot.tree.command(name="loginselfbot", description="🔑 Login alt account")
async def cmd_login(i: discord.Interaction):
    if i.user.id != OWNER_ID and not is_authorized(i.user.id):
        return await i.response.send_message("❌ Redeem key first", ephemeral=True)
    await i.response.send_modal(LoginModal(PanelView(i.user.id)))

@bot.tree.command(name="panel", description="🎛️ Control panel")
async def cmd_panel(i: discord.Interaction):
    if i.user.id != OWNER_ID and not is_authorized(i.user.id):
        return await i.response.send_message("❌ Redeem key first", ephemeral=True)
    data = get_panel(i.user.id) or upsert_panel(i.user.id)
    await i.response.send_message(embed=build_embed(i.user.id, data, manager.status(str(i.user.id))), view=PanelView(i.user.id), ephemeral=True)

@bot.tree.command(name="selfbotstatus", description="📊 Check status")
async def cmd_status(i: discord.Interaction):
    if i.user.id != OWNER_ID and not is_authorized(i.user.id):
        return await i.response.send_message("❌ Redeem key first", ephemeral=True)
    s = manager.status(str(i.user.id))
    embed = discord.Embed(title="🤖 SelfBot Status", color=0x57F287 if s['running'] else 0xED4245)
    embed.add_field(name="Status", value=s['status'].title(), inline=True)
    embed.add_field(name="Running", value="✅" if s['running'] else "❌", inline=True)
    if s['started_at']: embed.add_field(name="Started", value=f"<t:{s['started_at']//1000}:R>", inline=True)
    await i.response.send_message(embed=embed, ephemeral=True)

# ═══════════════════════════════════════════════════════
# START BOT - THIS IS THE LOGIN CALL
# ═══════════════════════════════════════════════════════
print("🔌 Connecting to Discord...", flush=True)

try:
    # client.run(TOKEN) - blocks forever and runs the bot
    bot.run(TOKEN)
except discord.LoginFailure as e:
    print(f"❌ Login failed: {e}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}", flush=True)
    raise
