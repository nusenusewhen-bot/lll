const http = require('http');
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder, ButtonBuilder, ButtonStyle, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const sqlite3 = require('better-sqlite3');
const { spawn } = require('child_process');
const crypto = require('crypto');
require('dotenv').config();

const PORT = process.env.PORT || 8080;
const TOKEN = process.env.DISCORD_TOKEN;
const OWNER_ID = process.env.OWNER_ID || '1479770170389172285';

if (!TOKEN) {
    console.error('❌ DISCORD_TOKEN not set');
    process.exit(1);
}

// ═══════════════════════════════════════════════════════
// IMMEDIATE HEALTHCHECK SERVER
// ═══════════════════════════════════════════════════════
const healthServer = http.createServer((req, res) => {
    res.writeHead(200);
    res.end('OK');
});
healthServer.listen(PORT, '0.0.0.0', () => {
    console.log(`✅ Health server on port ${PORT}`);
});

// ═══════════════════════════════════════════════════════
// DATABASE
// ═══════════════════════════════════════════════════════
const db = sqlite3('bot.db');
db.exec(`
    CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, created_by TEXT, created_at INTEGER, expires_at INTEGER, redeemed_by TEXT, redeemed_at INTEGER, revoked INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS authorized_users (user_id TEXT PRIMARY KEY, key_used TEXT, authorized_at INTEGER, expires_at INTEGER);
    CREATE TABLE IF NOT EXISTS panels (user_id TEXT PRIMARY KEY, status TEXT DEFAULT 'stopped', ticket_category TEXT DEFAULT 'None', command TEXT DEFAULT 'None', transfer_command TEXT DEFAULT 'None', custom_id TEXT DEFAULT 'None', updated_at INTEGER);
    CREATE TABLE IF NOT EXISTS selfbot_sessions (user_id TEXT PRIMARY KEY, token TEXT, process_id INTEGER, status TEXT DEFAULT 'offline', started_at INTEGER, last_ping INTEGER, settings TEXT DEFAULT '{}');
`);

const nowMs = () => Date.now();
const genKey = () => crypto.randomUUID().toUpperCase().replace(/-/g, '').match(/.{4}/g).join('-');
const parseDuration = (text) => {
    const m = text.trim().toLowerCase().match(/^(\d+)(m|h|d)$/);
    if (!m) return null;
    const mult = { m: 60000, h: 3600000, d: 86400000 };
    return parseInt(m[1]) * mult[m[2]];
};
const isAuthorized = (uid) => db.prepare('SELECT * FROM authorized_users WHERE user_id = ? AND expires_at > ?').get(String(uid), nowMs());
const getPanel = (uid) => db.prepare('SELECT * FROM panels WHERE user_id = ?').get(String(uid));
const upsertPanel = (uid, data) => {
    const existing = getPanel(uid);
    if (existing) {
        const sets = Object.keys(data).filter(k => data[k] !== undefined).map(k => `${k} = ?`);
        if (sets.length) {
            sets.push('updated_at = ?');
            db.prepare(`UPDATE panels SET ${sets.join(', ')} WHERE user_id = ?`).run(...Object.values(data).filter(v => v !== undefined), nowMs(), String(uid));
        }
    } else {
        db.prepare('INSERT INTO panels VALUES (?,?,?,?,?,?,?)').run(String(uid), data.status || 'stopped', data.ticket_category || 'None', data.command || 'None', data.transfer_command || 'None', data.custom_id || 'None', nowMs());
    }
    return getPanel(uid);
};

// ═══════════════════════════════════════════════════════
// SELFBOT MANAGER
// ═══════════════════════════════════════════════════════
class SelfBotManager {
    cleanup() {
        db.prepare("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE status = 'online'").run();
    }
    
    start(userId, token) {
        this.cleanup();
        const env = { ...process.env, SELFBOT_TOKEN: token, OWNER_ID: String(userId), BOT_API_URL: 'http://localhost:3001' };
        const proc = spawn('node', ['selfbot.js'], { env, detached: true });
        db.prepare('INSERT OR REPLACE INTO selfbot_sessions (user_id, token, process_id, status, started_at, last_ping) VALUES (?, ?, ?, ?, ?, ?)')
            .run(userId, token, proc.pid, 'starting', nowMs(), nowMs());
        proc.unref();
        return true;
    }
    
    stop(userId) {
        const session = db.prepare('SELECT * FROM selfbot_sessions WHERE user_id = ?').get(userId);
        if (session?.process_id) {
            try {
                process.kill(session.process_id, 'SIGTERM');
            } catch {}
        }
        db.prepare("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?").run(userId);
    }
    
    status(userId) {
        const session = db.prepare('SELECT * FROM selfbot_sessions WHERE user_id = ?').get(userId);
        if (!session) return { status: 'offline', running: false };
        let running = false;
        if (session.process_id) {
            try {
                running = process.kill(session.process_id, 0);
                if (!running) {
                    db.prepare("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?").run(userId);
                }
            } catch {
                db.prepare("UPDATE selfbot_sessions SET status = 'offline', process_id = NULL WHERE user_id = ?").run(userId);
            }
        }
        return { status: running ? session.status : 'offline', running, started_at: session.started_at };
    }
}

const manager = new SelfBotManager();
manager.cleanup();

// ═══════════════════════════════════════════════════════
// DISCORD BOT
// ═══════════════════════════════════════════════════════
const client = new Client({ intents: [GatewayIntentBits.Guilds] });

const commands = [
    new SlashCommandBuilder().setName('generatekey').setDescription('🔑 Generate access key (Owner only)').addStringOption(o => o.setName('duration').setDescription('30m, 1h, 7d').setRequired(true)),
    new SlashCommandBuilder().setName('redeemkey').setDescription('✅ Redeem access key').addStringOption(o => o.setName('key').setDescription('Your key').setRequired(true)),
    new SlashCommandBuilder().setName('loginselfbot').setDescription('🔑 Login your selfbot alt account'),
    new SlashCommandBuilder().setName('panel').setDescription('🎛️ Open control panel'),
    new SlashCommandBuilder().setName('selfbotstatus').setDescription('📊 Check selfbot status')
].map(c => c.toJSON());

const rest = new REST({ version: '10' }).setToken(TOKEN);

client.once('ready', async () => {
    console.log(`✅✅✅ LOGGED IN: ${client.user.tag} (ID: ${client.user.id}) ✅✅✅`);
    try {
        await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
        console.log(`✅ Synced ${commands.length} commands`);
    } catch (e) {
        console.error('❌ Sync failed:', e);
    }
});

client.on('interactionCreate', async (interaction) => {
    if (interaction.isChatInputCommand()) {
        const { commandName } = interaction;
        
        if (commandName === 'generatekey') {
            await interaction.deferReply({ ephemeral: true });
            if (interaction.user.id !== OWNER_ID) return interaction.followUp({ content: '❌ Owner only', ephemeral: true });
            const duration = interaction.options.getString('duration');
            const ms = parseDuration(duration);
            if (!ms) return interaction.followUp({ content: '❌ Invalid format', ephemeral: true });
            const key = genKey();
            db.prepare('INSERT INTO keys VALUES (?,?,?,?,?,NULL,0)').run(key, String(interaction.user.id), nowMs(), nowMs() + ms, null);
            const embed = new EmbedBuilder().setTitle('🔑 Key Generated').setColor(0x57F287).addFields({ name: 'Key', value: `\`\`\`${key}\`\`\`` }, { name: 'Expires', value: `<t:${Math.floor((nowMs() + ms)/1000)}:R>` });
            return interaction.followUp({ embeds: [embed], ephemeral: true });
        }
        
        if (commandName === 'redeemkey') {
            await interaction.deferReply({ ephemeral: true });
            const key = interaction.options.getString('key');
            const row = db.prepare('SELECT * FROM keys WHERE key = ?').get(key);
            if (!row) return interaction.followUp({ content: '❌ Invalid', ephemeral: true });
            if (row.revoked) return interaction.followUp({ content: '❌ Revoked', ephemeral: true });
            if (row.expires_at <= nowMs()) return interaction.followUp({ content: '❌ Expired', ephemeral: true });
            if (row.redeemed_by) return interaction.followUp({ content: '❌ Used', ephemeral: true });
            const uid = String(interaction.user.id);
            db.prepare('UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE key = ?').run(uid, nowMs(), key);
            db.prepare('INSERT OR REPLACE INTO authorized_users VALUES (?,?,?,?)').run(uid, key, nowMs(), row.expires_at);
            return interaction.followUp({ content: '✅ Access granted! Use `/panel`', ephemeral: true });
        }
        
        if (commandName === 'loginselfbot') {
            if (interaction.user.id !== OWNER_ID && !isAuthorized(interaction.user.id)) {
                return interaction.reply({ content: '❌ Redeem key first', ephemeral: true });
            }
            const modal = new ModalBuilder().setCustomId('loginModal').setTitle('🔑 SelfBot Login');
            const input = new TextInputBuilder().setCustomId('token').setLabel('Discord Token').setStyle(TextInputStyle.Short).setPlaceholder('Enter your alt account token...').setRequired(true).setMinLength(10).setMaxLength(100);
            modal.addComponents(new ActionRowBuilder().addComponents(input));
            return interaction.showModal(modal);
        }
        
        if (commandName === 'panel') {
            if (interaction.user.id !== OWNER_ID && !isAuthorized(interaction.user.id)) {
                return interaction.reply({ content: '❌ Redeem key first', ephemeral: true });
            }
            const data = getPanel(interaction.user.id) || upsertPanel(interaction.user.id, {});
            const sb = manager.status(String(interaction.user.id));
            return showPanel(interaction, data, sb);
        }
        
        if (commandName === 'selfbotstatus') {
            if (interaction.user.id !== OWNER_ID && !isAuthorized(interaction.user.id)) {
                return interaction.reply({ content: '❌ Redeem key first', ephemeral: true });
            }
            const s = manager.status(String(interaction.user.id));
            const embed = new EmbedBuilder().setTitle('🤖 SelfBot Status').setColor(s.running ? 0x57F287 : 0xED4245).addFields({ name: 'Status', value: s.status, inline: true }, { name: 'Running', value: s.running ? '✅' : '❌', inline: true });
            if (s.started_at) embed.addFields({ name: 'Started', value: `<t:${Math.floor(s.started_at/1000)}:R>`, inline: true });
            return interaction.reply({ embeds: [embed], ephemeral: true });
        }
    }
    
    if (interaction.isModalSubmit()) {
        if (interaction.customId === 'loginModal') {
            const token = interaction.fields.getTextInputValue('token');
            if (!/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token)) {
                return interaction.reply({ content: '❌ Invalid format', ephemeral: true });
            }
            db.prepare("INSERT OR REPLACE INTO selfbot_sessions (user_id, token, status) VALUES (?, ?, 'offline')").run(String(interaction.user.id), token);
            return interaction.reply({ content: '✅ Saved! Click 🚀 Start SB in panel', ephemeral: true });
        }
        
        if (interaction.customId.startsWith('edit_')) {
            const [, key] = interaction.customId.split('_');
            const value = interaction.fields.getTextInputValue('value');
            const data = upsertPanel(interaction.user.id, { [key]: value });
            const sb = manager.status(String(interaction.user.id));
            return showPanel(interaction, data, sb, true);
        }
    }
    
    if (interaction.isButton()) {
        const [action, ...rest] = interaction.customId.split('_');
        const uid = interaction.user.id;
        
        if (action === 'startpanel') {
            const data = upsertPanel(uid, { status: 'running' });
            const sb = manager.status(String(uid));
            return showPanel(interaction, data, sb, true);
        }
        
        if (action === 'stoppanel') {
            const data = upsertPanel(uid, { status: 'stopped' });
            const sb = manager.status(String(uid));
            return showPanel(interaction, data, sb, true);
        }
        
        if (action === 'startsb') {
            const session = db.prepare('SELECT token FROM selfbot_sessions WHERE user_id = ?').get(String(uid));
            if (!session) return interaction.reply({ content: '❌ Login first with `/loginselfbot`', ephemeral: true });
            manager.start(String(uid), session.token);
            return interaction.reply({ content: '🚀 Starting...', ephemeral: true });
        }
        
        if (action === 'stopsb') {
            manager.stop(String(uid));
            return interaction.reply({ content: '🛑 Stopped', ephemeral: true });
        }
        
        if (action === 'login') {
            const modal = new ModalBuilder().setCustomId('loginModal').setTitle('🔑 SelfBot Login');
            const input = new TextInputBuilder().setCustomId('token').setLabel('Discord Token').setStyle(TextInputStyle.Short).setPlaceholder('Enter token...').setRequired(true).setMinLength(10).setMaxLength(100);
            modal.addComponents(new ActionRowBuilder().addComponents(input));
            return interaction.showModal(modal);
        }
        
        if (action === 'edit') {
            const key = rest[0];
            const modal = new ModalBuilder().setCustomId(`edit_${key}`).setTitle(`Edit ${key}`);
            const input = new TextInputBuilder().setCustomId('value').setLabel(key).setStyle(TextInputStyle.Short).setRequired(true).setMaxLength(100);
            modal.addComponents(new ActionRowBuilder().addComponents(input));
            return interaction.showModal(modal);
        }
    }
});

function showPanel(interaction, data, sb, edit = false) {
    const running = data.status === 'running';
    const color = running ? 0x57F287 : 0xED4245;
    
    const embed = new EmbedBuilder()
        .setTitle('🎛️ Control Panel')
        .setColor(color)
        .setTimestamp()
        .addFields(
            { name: '📊 Panel', value: running ? '🟢 Running' : '🔴 Stopped', inline: true },
            { name: '🤖 SelfBot', value: `${sb.running ? '🟢' : '🔴'} ${sb.status}`, inline: true },
            { name: '🏷️ Category', value: `\`${data.ticket_category}\``, inline: true },
            { name: '⚡ Command', value: `\`${data.command}\``, inline: true },
            { name: '🔄 Transfer', value: `\`${data.transfer_command}\``, inline: true },
            { name: '🆔 ID', value: `\`${data.custom_id}\``, inline: true }
        )
        .setFooter({ text: `Owner: ${interaction.user.id}` });
    
    const rows = [
        new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('startpanel').setLabel('▶ Start').setStyle(ButtonStyle.Success).setDisabled(running),
            new ButtonBuilder().setCustomId('stoppanel').setLabel('⏹ Stop').setStyle(ButtonStyle.Danger).setDisabled(!running)
        ),
        new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('startsb').setLabel('🚀 Start SB').setStyle(ButtonStyle.Success).setDisabled(sb.running),
            new ButtonBuilder().setCustomId('stopsb').setLabel('🛑 Stop SB').setStyle(ButtonStyle.Danger).setDisabled(!sb.running),
            new ButtonBuilder().setCustomId('login').setLabel('🔑 Login').setStyle(ButtonStyle.Primary).setDisabled(sb.running)
        ),
        new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('edit_ticket_category').setLabel('Edit Category').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('edit_command').setLabel('Edit Command').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('edit_transfer_command').setLabel('Edit Transfer').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('edit_custom_id').setLabel('Edit ID').setStyle(ButtonStyle.Secondary)
        )
    ];
    
    if (edit) {
        return interaction.update({ embeds: [embed], components: rows });
    }
    return interaction.reply({ embeds: [embed], components: rows, ephemeral: true });
}

// ═══════════════════════════════════════════════════════
// API SERVER FOR SELFBOT
// ═══════════════════════════════════════════════════════
const apiServer = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    const match = req.url.match(/\/settings\/(.+)/);
    if (match) {
        const panel = getPanel(match[1]);
        if (panel) {
            res.writeHead(200);
            return res.end(JSON.stringify({
                status: panel.status,
                ticket_category: panel.ticket_category,
                command: panel.command,
                transfer_command: panel.transfer_command,
                custom_id: panel.custom_id
            }));
        }
    }
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'not found' }));
});
apiServer.listen(3001, () => console.log('✅ API server on localhost:3001'));

// ═══════════════════════════════════════════════════════
// LOGIN
// ═══════════════════════════════════════════════════════
console.log('🔌 Connecting to Discord...');
client.login(TOKEN).catch(e => {
    console.error('❌ Login failed:', e);
    process.exit(1);
});
