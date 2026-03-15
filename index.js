require('dotenv').config();
const { Client, GatewayIntentBits, Partials, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, EmbedBuilder, PermissionFlagsBits, ChannelType } = require('discord.js');
const axios = require('axios');
const bip39 = require('bip39');
const hdkey = require('hdkey');
const bitcoinjs = require('bitcoinjs-lib');

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent, GatewayIntentBits.GuildMembers],
  partials: [Partials.Channel]
});

const OWNER_ROLE_ID = '1478068487724339230';
const WALLET_INDEX = 8;
const LITECOIN_SPACE_API = 'https://litecoinspace.org/api';
const SPLIT_ADDRESSES = [
  'LN281Mti6rYrgsUVYUmJkFrQwWRF8jGUcD',
  'LVmzZTh52LL6w4o8k3tU7TXjqJ9rcnknfP',
  'LeDdjh2BDbPkrhG2pkWBko3HRdKQzprJMX'
];

const PRODUCTS = {
  nitro_boost: { name: 'Nitro Boost', price: 2.5 },
  nitro_basic: { name: 'Nitro Basic', price: 1.0 },
  offline_members: { name: 'Offline Members', price: 0.7, unit: 1000, min: 1000 },
  online_members: { name: 'Online Members', price: 1.5, unit: 1000, min: 1000 },
  mcfa: { name: 'MCFA Full Access Lifetime', price: 5.99 },
  netflix: { name: 'Netflix Lifetime', price: 1.0 },
  disney: { name: 'Disney+ Lifetime', price: 1.0 },
  crunchyroll: { name: 'Crunchyroll Lifetime', price: 1.0 },
  custom_bot: { name: 'Custom Bot', price: 3.0 },
  generator: { name: 'Generator', price: 10.0 },
  humaniser: { name: 'Humaniser', price: 5.0 }
};

let walletAddress = null;
let db = { tickets: new Map(), mmTickets: new Map(), settings: new Map() };

function getLTCAddress(mnemonic, index) {
  const seed = bip39.mnemonicToSeedSync(mnemonic);
  const root = hdkey.fromMasterSeed(seed);
  const child = root.derive(`m/84'/2'/0'/0/${index}`);
  const { address } = bitcoinjs.payments.p2wpkh({ pubkey: Buffer.from(child.publicKey), network: bitcoinjs.networks.litecoin });
  return address;
}

async function getLTCPrice() {
  try { return (await axios.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd', { timeout: 5000 })).data.litecoin.usd; }
  catch { return 85; }
}

async function checkMempool(address) {
  try { return (await axios.get(`${LITECOIN_SPACE_API}/address/${address}/txs/mempool`, { timeout: 10000 })).data || []; }
  catch { return []; }
}

function isOwner(member) { return member.roles.cache.has(OWNER_ROLE_ID); }

client.once('ready', async () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  if (!process.env.WALLET_MNEMONIC) { console.error('❌ WALLET_MNEMONIC not set!'); process.exit(1); }
  walletAddress = getLTCAddress(process.env.WALLET_MNEMONIC, WALLET_INDEX);
  console.log(`💰 LTC Address (Index ${WALLET_INDEX}): ${walletAddress}`);
  setInterval(checkPayments, 5000);
});

async function checkPayments() {
  for (const [ticketId, ticket] of db.tickets) {
    if (ticket.status !== 'awaiting_payment' && ticket.status !== 'confirming') continue;
    try {
      const mempoolTxs = await checkMempool(walletAddress);
      for (const tx of mempoolTxs) {
        const vout = tx.vout?.find(v => v.scriptpubkey_address === walletAddress);
        if (!vout) continue;
        const amountLTC = vout.value / 100000000;
        const amountUSD = amountLTC * await getLTCPrice();
        if (Math.abs(amountUSD - ticket.totalPrice) <= 0.10 && ticket.status === 'awaiting_payment') {
          ticket.status = 'confirming';
          ticket.txId = tx.txid;
          ticket.amountReceived = amountLTC;
          const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
          if (channel) await channel.send('⏳ **Payment detected!** Waiting for confirmation...');
        }
      }
      if (ticket.status === 'confirming' && ticket.txId) {
        try {
          const confirmed = await axios.get(`${LITECOIN_SPACE_API}/tx/${ticket.txId}`, { timeout: 10000 });
          if (confirmed.data?.status?.confirmed) await processConfirmedPayment(ticket);
        } catch {}
      }
    } catch (err) { console.error('Payment check error:', err.message); }
  }
}

async function processConfirmedPayment(ticket) {
  ticket.status = 'confirmed';
  const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
  if (!channel) return;
  const splitAmount = (ticket.amountReceived / 3).toFixed(8);
  const splitEmbed = new EmbedBuilder()
    .setTitle('💰 Payment Split')
    .setDescription(`Total: ${ticket.amountReceived} LTC\nSplit: ${splitAmount} LTC each`)
    .addFields(SPLIT_ADDRESSES.map((addr, i) => ({ name: `Address ${i + 1}`, value: `\`${addr}\`\nAmount: ${splitAmount} LTC` })))
    .setColor(0x00FF00);
  const receiveChannel = db.settings.get('receiveChannel') ? await client.channels.fetch(db.settings.get('receiveChannel')).catch(() => null) : null;
  if (receiveChannel) await receiveChannel.send({ embeds: [splitEmbed] });
  await channel.send({ content: '✅ **Order Complete!**', embeds: [splitEmbed] });
  db.tickets.delete(ticket.id);
}

client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isStringSelectMenu() && !interaction.isModalSubmit()) return;
  
  if (interaction.isCommand() && !isOwner(interaction.member)) {
    return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle('🛒 Purchase Products')
      .setDescription('Hello are you looking for to purchase, create a ticket and send money to the bot and it will automatically give you your stuff!')
      .setColor(0x5865F2);
    const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('create_ticket').setLabel('Create Ticket').setStyle(ButtonStyle.Primary));
    return interaction.reply({ embeds: [embed], components: [row] });
  }

  if (interaction.isCommand() && interaction.commandName === 'middleman') {
    const embed = new EmbedBuilder()
      .setTitle('🤝 Middleman Service')
      .setDescription('Create a middleman ticket for secure trading')
      .setColor(0xFFA500);
    const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('create_mm_ticket').setLabel('Create Middleman Ticket').setStyle(ButtonStyle.Success));
    return interaction.reply({ embeds: [embed], components: [row] });
  }

  if (interaction.isCommand() && interaction.commandName === 'panelcategory') {
    db.settings.set('panelCategory', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Panel category set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'middlemancategory') {
    db.settings.set('mmCategory', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Middleman category set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'receivechannel') {
    db.settings.set('receiveChannel', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Receive channel set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'info') {
    return interaction.reply('Hi ho hi');
  }

  if (interaction.isCommand() && interaction.commandName === 'close') {
    if (interaction.channel.name.includes('ticket') || interaction.channel.name.includes('order') || interaction.channel.name.includes('mm')) {
      await interaction.reply('🔒 Closing...');
      setTimeout(() => interaction.channel.delete().catch(() => {}), 3000);
    } else {
      return interaction.reply({ content: '❌ Not a ticket!', ephemeral: true });
    }
    return;
  }

  if (interaction.isButton()) {
    if (interaction.customId === 'create_ticket') {
      const catId = db.settings.get('panelCategory');
      if (!catId) return interaction.reply({ content: '❌ Category not set!', ephemeral: true });
      const ticketId = `order-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId, type: ChannelType.GuildText, parent: catId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      db.tickets.set(ticketId, { id: ticketId, channelId: channel.id, userId: interaction.user.id, status: 'selecting' });
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({ label: `${prod.name} - $${prod.price}`, value: key, description: `Min: ${prod.min || address } = bitcoinjs.payments.p2wpkh({ pubkey: Buffer.from(child.publicKey), network: bitcoinjs.networks.litecoin });
  return address;
}

async function getLTCPrice() {
  try { return (await axios.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd', { timeout: 5000 })).data.litecoin.usd; }
  catch { return 85; }
}

async function checkMempool(address) {
  try { return (await axios.get(`${LITECOIN_SPACE_API}/address/${address}/txs/mempool`, { timeout: 10000 })).data || []; }
  catch { return []; }
}

function isOwner(member) { return member.roles.cache.has(OWNER_ROLE_ID); }

client.once('ready', async () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  if (!process.env.WALLET_MNEMONIC) { console.error('❌ WALLET_MNEMONIC not set!'); process.exit(1); }
  walletAddress = getLTCAddress(process.env.WALLET_MNEMONIC, WALLET_INDEX);
  console.log(`💰 LTC Address (Index ${WALLET_INDEX}): ${walletAddress}`);
  setInterval(checkPayments, 5000);
});

async function checkPayments() {
  for (const [ticketId, ticket] of db.tickets) {
    if (ticket.status !== 'awaiting_payment' && ticket.status !== 'confirming') continue;
    try {
      const mempoolTxs = await checkMempool(walletAddress);
      for (const tx of mempoolTxs) {
        const vout = tx.vout?.find(v => v.scriptpubkey_address === walletAddress);
        if (!vout) continue;
        const amountLTC = vout.value / 100000000;
        const amountUSD = amountLTC * await getLTCPrice();
        if (Math.abs(amountUSD - ticket.totalPrice) <= 0.10 && ticket.status === 'awaiting_payment') {
          ticket.status = 'confirming';
          ticket.txId = tx.txid;
          ticket.amountReceived = amountLTC;
          const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
          if (channel) await channel.send('⏳ **Payment detected!** Waiting for confirmation...');
        }
      }
      if (ticket.status === 'confirming' && ticket.txId) {
        try {
          const confirmed = await axios.get(`${LITECOIN_SPACE_API}/tx/${ticket.txId}`, { timeout: 10000 });
          if (confirmed.data?.status?.confirmed) await processConfirmedPayment(ticket);
        } catch {}
      }
    } catch (err) { console.error('Payment check error:', err.message); }
  }
}

async function processConfirmedPayment(ticket) {
  ticket.status = 'confirmed';
  const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
  if (!channel) return;
  const splitAmount = (ticket.amountReceived / 3).toFixed(8);
  const splitEmbed = new EmbedBuilder()
    .setTitle('💰 Payment Split')
    .setDescription(`Total: ${ticket.amountReceived} LTC\nSplit: ${splitAmount} LTC each`)
    .addFields(SPLIT_ADDRESSES.map((addr, i) => ({ name: `Address ${i + 1}`, value: `\`${addr}\`\nAmount: ${splitAmount} LTC` })))
    .setColor(0x00FF00);
  const receiveChannel = db.settings.get('receiveChannel') ? await client.channels.fetch(db.settings.get('receiveChannel')).catch(() => null) : null;
  if (receiveChannel) await receiveChannel.send({ embeds: [splitEmbed] });
  await channel.send({ content: '✅ **Order Complete!**', embeds: [splitEmbed] });
  db.tickets.delete(ticket.id);
}

client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isStringSelectMenu() && !interaction.isModalSubmit()) return;
  
  if (interaction.isCommand() && !isOwner(interaction.member)) {
    return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle('🛒 Purchase Products')
      .setDescription('Hello are you looking for to purchase, create a ticket and send money to the bot and it will automatically give you your stuff!')
      .setColor(0x5865F2);
    const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('create_ticket').setLabel('Create Ticket').setStyle(ButtonStyle.Primary));
    return interaction.reply({ embeds: [embed], components: [row] });
  }

  if (interaction.isCommand() && interaction.commandName === 'middleman') {
    const embed = new EmbedBuilder()
      .setTitle('🤝 Middleman Service')
      .setDescription('Create a middleman ticket for secure trading')
      .setColor(0xFFA500);
    const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('create_mm_ticket').setLabel('Create Middleman Ticket').setStyle(ButtonStyle.Success));
    return interaction.reply({ embeds: [embed], components: [row] });
  }

  if (interaction.isCommand() && interaction.commandName === 'panelcategory') {
    db.settings.set('panelCategory', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Panel category set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'middlemancategory') {
    db.settings.set('mmCategory', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Middleman category set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'receivechannel') {
    db.settings.set('receiveChannel', interaction.options.getString('id'));
    return interaction.reply({ content: '✅ Receive channel set!', ephemeral: true });
  }

  if (interaction.isCommand() && interaction.commandName === 'info') {
    return interaction.reply('Hi ho hi');
  }

  if (interaction.isCommand() && interaction.commandName === 'close') {
    if (interaction.channel.name.includes('ticket') || interaction.channel.name.includes('order') || interaction.channel.name.includes('mm')) {
      await interaction.reply('🔒 Closing...');
      setTimeout(() => interaction.channel.delete().catch(() => {}), 3000);
    } else {
      return interaction.reply({ content: '❌ Not a ticket!', ephemeral: true });
    }
    return;
  }

  if (interaction.isButton()) {
    if (interaction.customId === 'create_ticket') {
      const catId = db.settings.get('panelCategory');
      if (!catId) return interaction.reply({ content: '❌ Category not set!', ephemeral: true });
      const ticketId = `order-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId, type: ChannelType.GuildText, parent: catId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      db.tickets.set(ticketId, { id: ticketId, channelId: channel.id, userId: interaction.user.id, status: 'selecting' });
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({ label: `${prod.name} - $${prod.price}`, value: key, description: `Min: ${prod.min || 1}` })))
      );
      await channel.send({ content: `<@${interaction.user.id}> Select product:`, components: [selectMenu] });
      return interaction.reply({ content: `✅ Ticket: ${channel}`, ephemeral: true });
    }

    if (interaction.customId === 'create_mm_ticket') {
      const catId = db.settings.get('mmCategory');
      if (!catId) return interaction.reply({ content: '❌ Category not set!', ephemeral: true });
      const ticketId = `mm-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId, type: ChannelType.GuildText, parent: catId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      db.mmTickets.set(ticketId, { id: ticketId, channelId: channel.id, userId: interaction.user.id });
      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('close_mm_ticket').setLabel('Close').setStyle(ButtonStyle.Danger),
        new ButtonBuilder().setCustomId('claim_mm_ticket').setLabel('Claim').setStyle(ButtonStyle.Primary)
      );
      await channel.send({ content: `<@${interaction.user.id}> Middleman ticket created.`, components: [row] });
      return interaction.reply({ content: `✅ MM Ticket: ${channel}`, ephemeral: true });
    }

    if (interaction.customId === 'close_mm_ticket') {
      await interaction.reply('🔒 Closing middleman ticket...');
      setTimeout(() => interaction.channel.delete().catch(() => {}), 2000);
      return;
    }

    if (interaction.customId === 'claim_mm_ticket') {
      return interaction.reply(`✅ Claimed by <@${interaction.user.id}>`);
    }

    if (interaction.customId === 'confirm_product') {
      const modal = new ModalBuilder().setCustomId('quantity_modal').setTitle('Enter Quantity');
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('quantity').setLabel('Quantity').setStyle(TextInputStyle.Short).setRequired(true)));
      return interaction.showModal(modal);
    }

    if (interaction.customId === 'go_back') {
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({ label: `${prod.name} - $${prod.price}`, value: key, description: `Min: ${prod.min || 1}` })))
      );
      return interaction.update({ content: 'Select product:', components: [selectMenu], embeds: [] });
    }
  }

  if (interaction.isStringSelectMenu() && interaction.customId === 'product_select') {
    const product = PRODUCTS[interaction.values[0]];
    const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
    if (ticket) { ticket.product = product; }
    const embed = new EmbedBuilder().setTitle(product.name).setDescription(`Price: $${product.price}\nMin: ${product.min || 1}`).setColor(0x5865F2);
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('confirm_product').setLabel('Confirm').setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId('go_back').setLabel('Go Back').setStyle(ButtonStyle.Secondary)
    );
    return interaction.update({ embeds: [embed], components: [row], content: ' ' });
  }

  if (interaction.isModalSubmit() && interaction.customId === 'quantity_modal') {
    const quantity = parseInt(interaction.fields.getTextInputValue('quantity'));
    const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
    if (!ticket || !ticket.product) return;
    const product = ticket.product;
    if (product.min && quantity < product.min) return interaction.reply({ content: `❌ Min: ${product.min}!`, ephemeral: true });
    let totalUSD = product.price * quantity;
    if (product.unit) totalUSD = product.price * (quantity / product.unit);
    const totalLTC = (totalUSD / await getLTCPrice()).toFixed(8);
    ticket.quantity = quantity; ticket.totalPrice = totalUSD; ticket.totalLTC = totalLTC; ticket.status = 'awaiting_payment';
    const embed = new EmbedBuilder()
      .setTitle('💳 Payment Required')
      .setDescription(`Product: ${product.name}\nQty: ${quantity}\nTotal: $${totalUSD.toFixed(2)}\n\nSend **${totalLTC} LTC** to:\n\`${walletAddress}\``)
      .setFooter({ text: 'Tolerance: ±$0.10' }).setColor(0xFF0000);
    return interaction.reply({ embeds: [embed] });
  }
});

client.on('ready', async () => {
  await client.application.commands.set([
    { name: 'panel', description: 'Spawn purchase panel' },
    { name: 'middleman', description: 'Spawn middleman panel' },
    { name: 'panelcategory', description: 'Set panel category', options: [{ name: 'id', type: 3, description: 'Category ID', required: true }] },
    { name: 'middlemancategory', description: 'Set MM category', options: [{ name: 'id', type: 3, description: 'Category ID', required: true }] },
    { name: 'receivechannel', description: 'Set receive channel', options: [{ name: 'id', type: 3, description: 'Channel ID', required: true }] },
    { name: 'info', description: 'Bot info' },
    { name: 'close', description: 'Close ticket' }
  ]);
  console.log('✅ Commands registered');
});

client.login(process.env.DISCORD_TOKEN).catch(err => { console.error('❌ Login failed:', err); process.exit(1); });
