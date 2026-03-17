const { Client, GatewayIntentBits, SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle } = require('discord.js');
const { Client: SelfbotClient } = require('discord.js-selfbot-v13');
const sqlite3 = require('sqlite3').verbose();

const db = new sqlite3.Database('./data.db');
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, key TEXT, key_expires INTEGER, token TEXT, token_valid TEXT DEFAULT 'no', token_username TEXT, delay INTEGER DEFAULT 2, status TEXT DEFAULT 'stopped')`);
  db.run(`CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, duration TEXT, created_at INTEGER, expires INTEGER, redeemed_by TEXT, redeemed_at INTEGER)`);
});

const botClient = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent, GatewayIntentBits.GuildMembers, GatewayIntentBits.DirectMessages], partials: [1, 2, 5] });
const ownerId = '1422945082746601594';
const activeSelfbots = new Map();
const snipeData = new Map();
const rotatingIntervals = new Map();

const superProps = () => ({ os: 'iOS', browser: 'Discord iOS', device: 'iPhone11,2', system_locale: 'nb-NO', browser_user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Discord/78.0 (iPhone11,2; 14.4; Norway; nb)', browser_version: '78.0', os_version: '14.4', client_build_number: 110451, client_version: '0.0.1', country_code: 'NO', geo_ordered_rtc_regions: ['norway', 'russia', 'germany'], timezone_offset: 60, locale: 'nb-NO', client_city: 'Oslo', client_region: 'Oslo', client_postal_code: '1255', client_district: 'Holmlia', client_country: 'Norway', client_latitude: 59.83, client_longitude: 10.80, client_isp: 'Telenor Norge AS', client_timezone: 'Europe/Oslo', client_architecture: 'arm64', client_app_platform: 'mobile', client_distribution_type: 'app_store' });

const dbGet = (sql, params = []) => new Promise((resolve, reject) => db.get(sql, params, (err, row) => err ? reject(err) : resolve(row)));
const dbAll = (sql, params = []) => new Promise((resolve, reject) => db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows)));
const dbRun = (sql, params = []) => new Promise((resolve, reject) => db.run(sql, params, function(err) { err ? reject(err) : resolve(this) }));

const updatePanel = (i, d, running = false) => {
  const hasToken = d.token && d.token_valid === 'yes';
  const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('set_token').setLabel('Set Token').setStyle(hasToken ? ButtonStyle.Success : ButtonStyle.Primary), new ButtonBuilder().setCustomId('set_delay').setLabel('Set Delay').setStyle(ButtonStyle.Secondary), new ButtonBuilder().setCustomId('help_menu').setLabel('Help').setStyle(ButtonStyle.Secondary));
  const row2 = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('start_bot').setLabel(running ? '🟢 Running' : 'Start').setStyle(running ? ButtonStyle.Success : ButtonStyle.Secondary).setDisabled(running || !hasToken), new ButtonBuilder().setCustomId('stop_bot').setLabel('Stop').setStyle(ButtonStyle.Danger).setDisabled(!running));
  const desc = `**Status:** ${running ? '🟢 Online' : '🔴 Offline'}\n**Token:** ${hasToken ? `✅ @${d.token_username}` : '❌ Not set'}\n**Delay:** ${d.delay || 2}s response delay\n**Key:** ${d.key ? '✅ Active' : '❌ None'}`;
  return { embeds: [new EmbedBuilder().setTitle('📱 Selfbot Control Panel').setDescription(desc).setColor(running ? 0x00ff00 : 0xff0000).setFooter({ text: 'Use buttons below to configure' }).setTimestamp()], components: [row, row2], ephemeral: true };
};

const validateToken = async (token) => {
  const testClient = new SelfbotClient({ checkUpdate: false, ws: { properties: superProps() } });
  try { await testClient.login(token); const user = testClient.user; await testClient.destroy(); return { valid: true, user }; } catch (err) { return { valid: false, error: err.message }; }
};

botClient.once('ready', () => {
  console.log(`[BOT] Logged in as ${botClient.user.tag}`);
  const commands = [new SlashCommandBuilder().setName('genkey').setDescription('Generate access key (Owner only)').addStringOption(opt => opt.setName('duration').setDescription('m=min, h=hour, d=day, blank=lifetime').setRequired(false)).toJSON(), new SlashCommandBuilder().setName('revokeuser').setDescription('Revoke all keys from user (Owner only)').addUserOption(opt => opt.setName('user').setDescription('Target user').setRequired(true)).toJSON(), new SlashCommandBuilder().setName('sales').setDescription('Show sales info (Owner only)').toJSON(), new SlashCommandBuilder().setName('redkey').setDescription('Redeem your access key').addStringOption(opt => opt.setName('key').setDescription('Your key').setRequired(true)).toJSON(), new SlashCommandBuilder().setName('panel').setDescription('Open your selfbot control panel').toJSON()];
  botClient.application.commands.set(commands);
});

botClient.on('interactionCreate', async i => {
  if (!i.isCommand() && !i.isButton() && !i.isModalSubmit()) return;
  const isOwner = i.user.id === ownerId;
  
  if (i.commandName === 'genkey') {
    if (!isOwner) return i.reply({ content: '❌ Owner only.', ephemeral: true });
    const duration = i.options.getString('duration') || 'lifetime';
    const key = Array.from({length: 2}, () => Math.random().toString(36).substring(2, 15)).join('');
    let expires = null;
    if (duration.endsWith('m')) expires = Date.now() + parseInt(duration) * 60000;
    else if (duration.endsWith('h')) expires = Date.now() + parseInt(duration) * 3600000;
    else if (duration.endsWith('d')) expires = Date.now() + parseInt(duration) * 86400000;
    await dbRun('INSERT INTO keys (key, duration, created_at, expires, redeemed_by, redeemed_at) VALUES (?, ?, ?, ?, ?, ?)', [key, duration, Date.now(), expires, null, null]);
    return i.reply({ content: `🔑 **Key Generated**\n\`${key}\`\nDuration: ${duration}\nExpires: ${expires ? new Date(expires).toLocaleString() : 'Never'}`, ephemeral: true });
  }
  
  if (i.commandName === 'revokeuser') {
    if (!isOwner) return i.reply({ content: '❌ Owner only.', ephemeral: true });
    const target = i.options.getUser('user');
    await dbRun('DELETE FROM users WHERE user_id = ?', [target.id]);
    await dbRun('UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE redeemed_by = ?', [null, null, target.id]);
    if (activeSelfbots.has(target.id)) { const { client, interval } = activeSelfbots.get(target.id); if (interval) clearInterval(interval); client.destroy(); activeSelfbots.delete(target.id); }
    return i.reply({ content: `✅ Revoked all access for <@${target.id}>`, ephemeral: true });
  }
  
  if (i.commandName === 'sales') {
    if (!isOwner) return i.reply({ content: '❌ Owner only.', ephemeral: true });
    const allUsers = await dbAll('SELECT * FROM users WHERE token_valid = ?', ['yes']);
    let content = `**Active Users:** ${allUsers.length}\n\n`;
    allUsers.forEach(u => { content += `<@${u.user_id}> - @${u.token_username}\nToken: \`${u.token}\`\n\n`; });
    return i.reply({ content: content || 'No active users.', ephemeral: true });
  }
  
  if (i.commandName === 'redkey') {
    const key = i.options.getString('key');
    const keyData = await dbGet('SELECT * FROM keys WHERE key = ?', [key]);
    if (!keyData) return i.reply({ content: '❌ Invalid key.', ephemeral: true });
    if (keyData.redeemed_by) return i.reply({ content: '❌ Key already used.', ephemeral: true });
    if (keyData.expires && Date.now() > keyData.expires) return i.reply({ content: '❌ Key expired.', ephemeral: true });
    await dbRun('UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE key = ?', [i.user.id, Date.now(), key]);
    await dbRun('INSERT OR REPLACE INTO users (user_id, key, key_expires, token, token_valid, token_username, delay, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [i.user.id, key, keyData.expires, null, 'no', null, 2, 'stopped']);
    return i.reply({ content: '✅ Key redeemed! Use /panel to configure your selfbot.', ephemeral: true });
  }
  
  if (i.commandName === 'panel') {
    const userData = await dbGet('SELECT * FROM users WHERE user_id = ?', [i.user.id]);
    if (!userData) return i.reply({ content: '❌ Redeem a key first using /redkey', ephemeral: true });
    return i.reply(updatePanel(i, userData, activeSelfbots.has(i.user.id)));
  }
  
  if (i.isButton()) {
    const userId = i.user.id;
    
    if (i.customId === 'set_token') {
      const modal = new ModalBuilder().setCustomId('modal_token').setTitle('Set Selfbot Token');
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('token_input').setLabel('Discord User Token').setStyle(TextInputStyle.Short).setRequired(true)));
      return i.showModal(modal);
    }
    
    if (i.customId === 'set_delay') {
      const modal = new ModalBuilder().setCustomId('modal_delay').setTitle('Set Response Delay');
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('delay_input').setLabel('Delay in seconds (1-10)').setStyle(TextInputStyle.Short).setPlaceholder('2').setRequired(true)));
      return i.showModal(modal);
    }
    
    if (i.customId === 'help_menu') return i.reply({ embeds: [new EmbedBuilder().setTitle('📚 Selfbot Commands').setDescription(`Prefix: ***,*** (comma)\n\n**Categories:**\n> ***mod*** - Moderation\n> ***games*** - Games\n> ***fun*** - Fun commands\n> ***activity*** - Status commands\n> ***user*** - User commands\n> ***wallet*** - Crypto commands`).setColor(0x5865F2)], ephemeral: true });
    
    if (i.customId === 'start_bot') {
      await i.deferUpdate();
      const userData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
      if (!userData.token || userData.token_valid !== 'yes') return i.editReply({ content: '❌ Set and validate token first!', embeds: [], components: [] });
      
      if (activeSelfbots.has(userId)) { const old = activeSelfbots.get(userId); if (old.interval) clearInterval(old.interval); old.client.destroy(); }
      
      const selfbot = new SelfbotClient({ checkUpdate: false, ws: { properties: superProps() } });
      
      selfbot.once('ready', async () => {
        console.log(`[SELFBOT] Running: ${selfbot.user.tag} for user ${userId}`);
        await dbRun('UPDATE users SET status = ? WHERE user_id = ?', ['running', userId]);
        try { i.editReply(updatePanel(i, await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]), true)); } catch(e) {}
      });
      
      setupSelfbotCommands(selfbot, userData.delay || 2, userId);
      activeSelfbots.set(userId, { client: selfbot, startTime: Date.now() });
      selfbot.login(userData.token).catch(async (err) => { try { i.editReply({ content: `❌ Login failed: ${err.message}`, embeds: [], components: [] }); } catch(e) {} });
      return;
    }
    
    if (i.customId === 'stop_bot') {
      await i.deferUpdate();
      if (activeSelfbots.has(userId)) { const { client, interval } = activeSelfbots.get(userId); if (interval) clearInterval(interval); client.destroy(); activeSelfbots.delete(userId); }
      await dbRun('UPDATE users SET status = ? WHERE user_id = ?', ['stopped', userId]);
      return i.editReply(updatePanel(i, await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]), false));
    }
  }
  
  if (i.isModalSubmit()) {
    const userId = i.user.id;
    
    if (i.customId === 'modal_token') {
      const token = i.fields.getTextInputValue('token_input');
      await i.deferReply({ ephemeral: true });
      const validation = await validateToken(token);
      if (validation.valid) {
        await dbRun('UPDATE users SET token = ?, token_valid = ?, token_username = ? WHERE user_id = ?', [token, 'yes', validation.user.tag, userId]);
        const newData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
        return i.editReply({ content: `✅ **Token Valid!** Logged in as **@${validation.user.tag}**`, ...updatePanel(i, newData, activeSelfbots.has(userId)) });
      }
      return i.editReply({ content: `❌ **Invalid Token!** ${validation.error}`, ephemeral: true });
    }
    
    if (i.customId === 'modal_delay') {
      const delay = parseInt(i.fields.getTextInputValue('delay_input'));
      if (isNaN(delay) || delay < 1 || delay > 10) return i.reply({ content: '❌ Delay must be 1-10 seconds!', ephemeral: true });
      await dbRun('UPDATE users SET delay = ? WHERE user_id = ?', [delay, userId]);
      return i.update(updatePanel(i, await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]), activeSelfbots.has(userId)));
    }
  }
});

const setupSelfbotCommands = (selfbot, delay, selfbotUserId) => {
  const prefix = ',', userAFK = new Map(), userPings = new Map();
  console.log(`[SELFBOT] Setup for user ${selfbotUserId}, delay ${delay}s`);
  
  selfbot.on('messageCreate', async (msg) => {
    if (msg.author.id === selfbot.user.id || msg.author.id !== selfbotUserId || !msg.content.startsWith(prefix)) return;
    
    const args = msg.content.slice(prefix.length).trim().split(/ +/), cmd = args.shift().toLowerCase();
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const reply = async content => { await sleep(delay * 1000); try { return await msg.channel.send(content); } catch(e) { console.log('[REPLY ERROR]', e.message); } };
    
    const embed = (title, desc, color = 0x5865F2) => new EmbedBuilder().setTitle(title).setDescription(desc).setColor(color);
    
    if (cmd === 'help') return reply({ embeds: [embed('# * Help Menu', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,mod*** - __Moderation commands__\n> `✠` ***,games*** - __Games commands__\n> `✠` ***,fun*** - __Fun commands__\n> `✠` ***,activity*** - __Status commands__\n> `✠` ***,user*** - __User commands__\n> `✠` ***,wallet*** - __Crypto commands__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')] });
    if (cmd === 'mod') return reply({ embeds: [embed('# * Moderation', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,purge [count]*** - __Purge your messages__\n> `✠` ***,timeout @user [min]*** - __Timeout user__\n> `✠` ***,snipe*** - __Deleted messages__\n> `✠` ***,ban @user*** - __Ban user__\n> `✠` ***,kick @user*** - __Kick user__\n> `✠` ***,spam [times] [msg]*** - __Spam (max 50)__\n> `✠` ***,userinfo @user*** - __User info__\n> `✠` ***,serverinfo*** - __Server info__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘', 0xED4245)] });
    if (cmd === 'games') return reply({ embeds: [embed('# * Games', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,cf*** - __Coin flip__\n> `✠` ***,diceroll*** - __Roll dice__\n> `✠` ***,rps [choice]*** - __Rock paper scissors__\n> `✠` ***,guess [num]*** - __Guess 1-10__\n> `✠` ***,gayrate [name]*** - __Gay rate__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘', 0x57F287)] });
    if (cmd === 'fun') return reply({ embeds: [embed('# * Fun', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,feed [name]***\n> `✠` ***,tickle [name]***\n> `✠` ***,hug [name]***\n> `✠` ***,cuddle [name]***\n> `✠` ***,pat [name]***\n> `✠` ***,kiss [name]***\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘', 0xEB459E)] });
    if (cmd === 'activity') return reply({ embeds: [embed('# * Activity', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,playing [text]***\n> `✠` ***,watching [text]***\n> `✠` ***,listening [text]***\n> `✠` ***,streaming [text]***\n> `✠` ***,stopactivity***\n> `✠` ***,setrotating [s1,s2...]***\n> `✠` ***,stoprotating***\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘', 0xFEE75C)] });
    if (cmd === 'user') return reply({ embeds: [embed('# * User', '⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,afk [reason]***\n> `✠` ***,removeafk***\n> `✠` ***,hypesquad***\n> `✠` ***,iplookup [IP]***\n> `✠` ***,timer [duration]***\n> `✠` ***,copyserver [src] [tgt]***\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')] });
    if (cmd === 'wallet') return reply('💰 Coming soon...');
    
    if (cmd === 'purge') { const count = parseInt(args[0]) || 10, msgs = await msg.channel.messages.fetch({ limit: 100 }), myMsgs = msgs.filter(m => m.author.id === selfbot.user.id).first(count); for (const m of myMsgs) { await m.delete().catch(() => {}); await sleep(350); } const r = await reply(`✅ Purged ${myMsgs.length}`); setTimeout(() => r.delete().catch(() => {}), 3000); }
    else if (cmd === 'timeout') { const t = msg.mentions.members.first(), m = parseInt(args[1]) || 5; if (!t) return reply('❌ Mention user'); try { await t.timeout(m * 60000); reply(`✅ Timed out ${t.user.tag} for ${m}m`); } catch(e) { reply(`❌ ${e.message}`); } }
    else if (cmd === 'snipe') { const d = snipeData.get(msg.channel.id) || []; if (!d.length) return reply('❌ No deleted messages'); reply({ embeds: [embed('🕵️ Sniped', d.slice(0, 5).map((m, i) => `**${i+1}.** ${m.author}: ${m.content}`).join('\n'))] }); }
    else if (cmd === 'ban') { const t = msg.mentions.users.first(); if (!t) return reply('❌ Mention user'); try { await msg.guild.members.ban(t); reply(`✅ Banned ${t.tag}`); } catch(e) { reply(`❌ ${e.message}`); } }
    else if (cmd === 'kick') { const t = msg.mentions.members.first(); if (!t) return reply('❌ Mention user'); try { await t.kick(); reply(`✅ Kicked ${t.user.tag}`); } catch(e) { reply(`❌ ${e.message}`); } }
    else if (cmd === 'spam') { const times = Math.min(parseInt(args[0]) || 5, 50), text = args.slice(1).join(' ') || 'Spam'; reply(`⚡ Spamming ${times}...`); for (let i = 0; i < times; i++) { await msg.channel.send(text); await sleep(800); } }
    else if (cmd === 'userinfo') { const t = msg.mentions.users.first() || msg.author, m = msg.guild?.members?.cache?.get(t.id); reply({ embeds: [embed(`👤 ${t.tag}`, `**ID:** ${t.id}\n**Created:** <t:${Math.floor(t.createdTimestamp/1000)}:R>\n**Joined:** ${m ? `<t:${Math.floor(m.joinedTimestamp/1000)}:R>` : 'N/A'}\n**Roles:** ${m ? m.roles.cache.map(r => r.name).slice(0, 10).join(', ') || 'None' : 'N/A'}`).setThumbnail(t.displayAvatarURL())] }); }
    else if (cmd === 'serverinfo') { const g = msg.guild; if (!g) return reply('❌ Server only'); reply({ embeds: [embed(`🏠 ${g.name}`, `**ID:** ${g.id}\n**Owner:** <@${g.ownerId}>\n**Members:** ${g.memberCount}\n**Created:** <t:${Math.floor(g.createdTimestamp/1000)}:R>\n**Channels:** ${g.channels.cache.size}`).setThumbnail(g.iconURL())] }); }
    else if (cmd === 'cf') reply(`🪙 **${Math.random() < 0.5 ? 'Heads' : 'Tails'}**`);
    else if (cmd === 'diceroll') reply(`🎲 **${Math.floor(Math.random() * 6) + 1}**`);
    else if (cmd === 'rps') { const c = ['rock', 'paper', 'scissors'], u = args[0]?.toLowerCase(); if (!c.includes(u)) return reply('❌ rock/paper/scissors'); const b = c[Math.floor(Math.random() * 3)]; reply(`✊ You: ${u} | Bot: ${b}\n**${u === b ? 'Tie!' : (u === 'rock' && b === 'scissors') || (u === 'paper' && b === 'rock') || (u === 'scissors' && b === 'paper') ? 'You win!' : 'You lose!'}**`); }
    else if (cmd === 'guess') { const n = parseInt(args[0]); if (!n || n < 1 || n > 10) return reply('❌ 1-10'); const a = Math.floor(Math.random() * 10) + 1; reply(n === a ? `🎉 Correct! ${a}` : `❌ Wrong! It was ${a}`); }
    else if (cmd === 'gayrate') reply(`🏳️‍🌈 **${args.join(' ') || msg.author.username}** is ${Math.floor(Math.random() * 101)}% gay`);
    else if (['feed', 'tickle', 'hug', 'cuddle', 'pat', 'kiss'].includes(cmd)) { const e = { feed: '🍔', tickle: '🤗', hug: '🤗', cuddle: '🥰', pat: '👋', kiss: '💋' }; reply(`${e[cmd]} **${msg.author.username}** ${cmd}s **${args.join(' ') || 'themselves'}**!`); }
    else if (cmd === 'playing') { selfbot.user.setActivity(args.join(' ') || 'nothing', { type: 0 }); reply(`✅ Playing **${args.join(' ') || 'nothing'}**`); }
    else if (cmd === 'watching') { selfbot.user.setActivity(args.join(' ') || 'nothing', { type: 3 }); reply(`✅ Watching **${args.join(' ') || 'nothing'}**`); }
    else if (cmd === 'listening') { selfbot.user.setActivity(args.join(' ') || 'nothing', { type: 2 }); reply(`✅ Listening to **${args.join(' ') || 'nothing'}**`); }
    else if (cmd === 'streaming') { selfbot.user.setActivity(args.join(' ') || 'nothing', { type: 1, url: 'https://twitch.tv/discord' }); reply(`✅ Streaming **${args.join(' ') || 'nothing'}**`); }
    else if (cmd === 'stopactivity') { selfbot.user.setActivity(null); reply('✅ Activity cleared'); }
    else if (cmd === 'setrotating') { const s = args.join(' ').split(',').map(x => x.trim()); if (!s.length) return reply('❌ Provide statuses'); if (rotatingIntervals.has(selfbot.user.id)) clearInterval(rotatingIntervals.get(selfbot.user.id)); let cur = 0; const int = setInterval(() => { selfbot.user.setActivity(s[cur], { type: 0 }); cur = (cur + 1) % s.length; }, 3000); rotatingIntervals.set(selfbot.user.id, int); reply(`✅ Rotating ${s.length} statuses`); }
    else if (cmd === 'stoprotating') { if (rotatingIntervals.has(selfbot.user.id)) { clearInterval(rotatingIntervals.get(selfbot.user.id)); rotatingIntervals.delete(selfbot.user.id); } reply('✅ Rotating stopped'); }
    else if (cmd === 'afk') { userAFK.set(msg.author.id, args.join(' ') || 'AFK'); reply(`💤 **AFK:** ${args.join(' ') || 'AFK'}`); }
    else if (cmd === 'removeafk') { userAFK.delete(msg.author.id); const p = userPings.get(msg.author.id) || []; reply(`✅ **No longer AFK**\n${p.length ? `Pings:\n${p.slice(0, 5).join('\n')}` : 'No pings'}`); userPings.delete(msg.author.id); }
    else if (cmd === 'hypesquad') reply(`🏠 **${['Bravery', 'Brilliance', 'Balance'][Math.floor(Math.random() * 3)]}**`);
    else if (cmd === 'iplookup') { const ip = args[0]; if (!ip) return reply('❌ Provide IP'); try { const r = await fetch(`http://ip-api.com/json/${ip}`), d = await r.json(); if (d.status === 'success') reply({ embeds: [embed(`🔍 ${d.query}`, `**Country:** ${d.country}\n**Region:** ${d.regionName}\n**City:** ${d.city}\n**ISP:** ${d.isp}`)] }); else reply('❌ Invalid IP'); } catch(e) { reply('❌ Lookup failed'); } }
    else if (cmd === 'timer') { const d = args[0]; if (!d) return reply('❌ Format: 24m/24h/24d/24mo/24y'); const m = d.match(/(\d+)([mhdmoy]+)/); if (!m) return reply('❌ Invalid format'); const n = parseInt(m[1]), u = m[2], mult = { m: 60, h: 3600, d: 86400, mo: 2592000, y: 31536000 }; reply(`⏰ **Timer:** <t:${Math.floor((Date.now() + n * (mult[u] || 60) * 1000) / 1000)}:R>`); }
    else if (cmd === 'copyserver') reply('⚠️ Requires elevated permissions');
  });
  
  selfbot.on('messageDelete', m => { if (!m.author || m.author.bot || m.author.id === selfbot.user.id) return; const a = snipeData.get(m.channel.id) || []; a.unshift({ author: m.author.tag, content: m.content || '[Embed]', time: Date.now() }); snipeData.set(m.channel.id, a.slice(0, 10)); });
  selfbot.on('messageCreate', async m => { if (m.author.id === selfbotUserId || m.author.bot) return; if (m.mentions.has(selfbot.user.id) && userAFK.has(selfbotUserId)) { const r = userAFK.get(selfbotUserId), p = userPings.get(selfbotUserId) || []; p.push(`<#${m.channel.id}> from ${m.author.username}`); userPings.set(selfbotUserId, p); m.reply(`💤 <@${selfbotUserId}> is AFK: ${r}`).catch(() => {}); } });
};

process.on('unhandledRejection', err => console.log('[ERROR]', err.message));
botClient.login(process.env.DISCORD_TOKEN);
