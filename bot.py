import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import sqlite3
import uuid
import re
import os
import time
import asyncio
import websockets
import json
from datetime import datetime
from aiohttp import web

# ─── Config ───
TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", "1479770170389172285"))
SELFBOT_TOKEN = os.environ.get("SELFBOT_TOKEN")  # The alt account token

# ─── Database ───
db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")
db.executescript("""
    CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, created_by TEXT, created_at INTEGER, expires_at INTEGER, redeemed_by TEXT, redeemed_at INTEGER, revoked INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS authorized_users (user_id TEXT PRIMARY KEY, key_used TEXT, authorized_at INTEGER, expires_at INTEGER);
    CREATE TABLE IF NOT EXISTS panels (user_id TEXT PRIMARY KEY, status TEXT DEFAULT 'stopped', ticket_category TEXT DEFAULT 'None', command TEXT DEFAULT 'None', transfer_command TEXT DEFAULT 'None', custom_id TEXT DEFAULT 'None', updated_at INTEGER);
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

# ─── SelfBot Controller ───
class SelfBotController:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.settings = {}
        self.client = None
        
    async def start(self):
        import aiohttp
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self.claimer_loop())
        
    async def claimer_loop(self):
        """Simulated selfbot - monitors channels via Discord API polling"""
        headers = {"Authorization": SELFBOT_TOKEN, "Content-Type": "application/json"}
        claimed = set()
        
        while True:
            if self.settings.get("status") != "running" or not self.settings.get("category_id"):
                await asyncio.sleep(2)
                continue
                
            try:
                # Get guild channels (simplified - you'd track specific guild)
                async with self.session.get("https://discord.com/api/v9/users/@me/guilds", headers=headers) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                        
                # Check for new channels in category (this is a simplified version)
                # In production, you'd use gateway or track channel creates
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Claimer error: {e}")
                await asyncio.sleep(5)

    def update_settings(self, uid, data):
        self.settings = {
            "user_id": str(uid),
            "status": data.get("status", "stopped"),
            "category_id": data.get("ticket_category"),
            "claim_cmd": data.get("command", "claim"),
            "transfer_cmd": data.get("transfer_command"),
            "transfer_id": data.get("custom_id")
        }
        print(f"Settings updated: {self.settings}")

claimer = SelfBotController()

# ─── UI ───
def build_embed(uid, data):
    running = data["status"] == "running"
    embed = discord.Embed(title="🎛️ Control Panel", color=0x57F287 if running else 0xED4245, timestamp=datetime.utcnow())
    embed.add_field(name="📊 Status", value="🟢 Running" if running else "🔴 Stopped", inline=True)
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
        
        start = ui.Button(label="▶ Start", style=discord.ButtonStyle.success, disabled=running)
        stop = ui.Button(label="⏹ Stop", style=discord.ButtonStyle.danger, disabled=not running)
        start.callback = self.start_cb; stop.callback = self.stop_cb
        self.add_item(start); self.add_item(stop)
        
        for key, label, emoji in [("ticket_category", "Category", "🏷️"), ("command", "Command", "⚡"), ("transfer_command", "Transfer", "🔄"), ("custom_id", "ID", "🆔")]:
            btn = ui.Button(label=f"Edit {label}", style=discord.ButtonStyle.secondary, emoji=emoji)
            btn.callback = self.make_edit_cb(key, label)
            self.add_item(btn)
            
    async def start_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        data = upsert_panel(self.uid, status="running")
        claimer.update_settings(self.uid, data)
        self.refresh()
        await interaction.response.edit_message(embed=build_embed(self.uid, data), view=self)
        
    async def stop_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        data = upsert_panel(self.uid, status="stopped")
        claimer.update_settings(self.uid, data)
        self.refresh()
        await interaction.response.edit_message(embed=build_embed(self.uid, data), view=self)
        
    def make_edit_cb(self, key, label):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.uid: return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
            modal = EditModal(self, key, label)
            await interaction.response.send_modal(modal)
        return callback

class EditModal(ui.Modal):
    def __init__(self, view, key, label):
        super().__init__(title=f"Edit {label}")
        self.view = view; self.key = key
        self.input = ui.TextInput(label=label, max_length=100)
        self.add_item(self.input)
        
    async def on_submit(self, interaction: discord.Interaction):
        kwargs = {self.key: self.input.value}
        data = upsert_panel(self.view.uid, **kwargs)
        claimer.update_settings(self.view.uid, data)
        self.view.refresh()
        await interaction.response.edit_message(embed=build_embed(self.view.uid, data), view=self.view)

# ─── Bot Setup ───
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    await bot.tree.sync()
    await claimer.start()
    print(f"✅ Bot online as {bot.user}")

@bot.tree.command(name="generatekey", description="🔑 Generate key (Owner only)")
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
    await interaction.response.send_message("✅ Access granted!", ephemeral=True)

@bot.tree.command(name="panel", description="🎛️ Open control panel")
async def panel(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not is_authorized(interaction.user.id):
        return await interaction.response.send_message("❌ Redeem key first: `/redeemkey`", ephemeral=True)
    data = get_panel(interaction.user.id) or upsert_panel(interaction.user.id)
    await interaction.response.send_message(embed=build_embed(interaction.user.id, data), view=PanelView(interaction.user.id), ephemeral=True)

bot.run(TOKEN)
