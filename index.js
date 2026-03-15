require('dotenv').config();
const { Client, GatewayIntentBits, Partials, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, StringSelectMenuOptionBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, EmbedBuilder, PermissionFlagsBits, ChannelType } = require('discord.js');
const axios = require('axios');
const bip39 = require('bip39');
const hdkey = require('hdkey');
const bitcoinjs = require('bitcoinjs-lib');
const { createHash } = require('crypto');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ],
  partials: [Partials.Channel]
});

const OWNER_ROLE_ID = '1478068487724339230';
const WALLET_INDEX = 8;
const LITECOIN_SPACE_API = 'https://litecoinspace.org/api';

// Split addresses (33/33/33)
const SPLIT_ADDRESSES = [
  'LN281Mti6rYrgsUVYUmJkFrQwWRF8jGUcD',
  'LVmzZTh52LL6w4o8k3tU7TXjqJ9rcnknfP',
  'LeDdjh2BDbPkrhG2pkWBko3HRdKQzprJMX'
];

// Product catalog
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
let db = { tickets: new Map(), panels: new Map(), settings: new Map() };

// Generate LTC address from mnemonic
function getLTCAddress(mnemonic, index) {
  const seed = bip39.mnemonicToSeedSync(mnemonic);
  const root = hdkey.fromMasterSeed(seed);
  const path = `m/84'/2'/0'/0/${index}`;
  const child = root.derive(path);
  const { address } = bitcoinjs.payments.p2wpkh({
    pubkey: Buffer.from(child.publicKey),
    network: bitcoinjs.networks.litecoin
  });
  return address;
}

// Get LTC price
async function getLTCPrice() {
  try {
    const res = await axios.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd', { timeout: 5000 });
    return res.data.litecoin.usd;
  } catch {
    return 85;
  }
}

// Check address balance via litecoinspace
async function checkAddressBalance(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}`, { timeout: 10000 });
    const data = res.data;
    const funded = data.chain_stats?.funded_txo_sum || 0;
    const spent = data.chain_stats?.spent_txo_sum || 0;
    const balance = (funded - spent) / 100000000;
    return { balance, txs: data.chain_stats?.tx_count || 0 };
  } catch (err) {
    console.error('Balance check error:', err.message);
    return { balance: 0, txs: 0 };
  }
}

// Check mempool for new transactions
async function checkMempool(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}/txs/mempool`, { timeout: 10000 });
    return res.data || [];
  } catch {
    return [];
  }
}

// Convert USD to LTC
function usdToLTC(usdAmount, ltcPrice) {
  return (usdAmount / ltcPrice).toFixed(8);
}

// Check if user has owner role
function isOwner(member) {
  return member.roles.cache.has(OWNER_ROLE_ID);
}

client.once('ready', async () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  
  if (!process.env.WALLET_MNEMONIC) {
    console.error('❌ WALLET_MNEMONIC not set!');
    process.exit(1);
  }
  
  walletAddress = getLTCAddress(process.env.WALLET_MNEMONIC, WALLET_INDEX);
  console.log(`💰 Using LTC Address (Index ${WALLET_INDEX}): ${walletAddress}`);
  
  // Start payment checker
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
        const ltcPrice = await getLTCPrice();
        const amountUSD = amountLTC * ltcPrice;
        const expectedUSD = ticket.totalPrice;
        const tolerance = 0.10;
        
        if (Math.abs(amountUSD - expectedUSD) <= tolerance || (amountUSD >= expectedUSD - tolerance && amountUSD <= expectedUSD + tolerance)) {
          if (ticket.status === 'awaiting_payment') {
            ticket.status = 'confirming';
            ticket.txId = tx.txid;
            ticket.amountReceived = amountLTC;
            
            const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
            if (channel) {
              await channel.send('⏳ **Payment detected in mempool!** Waiting for confirmation...');
            }
          }
        }
      }
      
      // Check confirmed balance
      const { balance, txs } = await checkAddressBalance(walletAddress);
      if (ticket.status === 'confirming' && ticket.txId) {
        const confirmed = await axios.get(`${LITECOIN_SPACE_API}/tx/${ticket.txId}`, { timeout: 10000 }).catch(() => null);
        if (confirmed && confirmed.data?.status?.confirmed) {
          await processConfirmedPayment(ticket);
        }
      }
    } catch (err) {
      console.error('Payment check error:', err.message);
    }
  }
}

async function processConfirmedPayment(ticket) {
  ticket.status = 'confirmed';
  
  const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
  if (!channel) return;
  
  await channel.send('✅ **Payment Confirmed!** Processing split...');
  
  // Split payment
  const totalLTC = ticket.amountReceived;
  const splitAmount = (totalLTC / 3).toFixed(8);
  
  const receiveChannelId = db.settings.get('receiveChannel');
  const receiveChannel = receiveChannelId ? await client.channels.fetch(receiveChannelId).catch(() => null) : null;
  
  const splitEmbed = new EmbedBuilder()
    .setTitle('💰 Payment Split')
    .setDescription(`Total: ${totalLTC} LTC\nSplit: ${splitAmount} LTC each (33/33/33)`)
    .addFields(
      SPLIT_ADDRESSES.map((addr, i) => ({ name: `Address ${i + 1}`, value: `\`${addr}\`\nAmount: ${splitAmount} LTC`, inline: false }))
    )
    .setColor(0x00FF00)
    .setTimestamp();
  
  if (receiveChannel) {
    await receiveChannel.send({ embeds: [splitEmbed] });
  }
  
  await channel.send({
    content: '✅ **Order Complete!** Payment received and split.',
    embeds: [splitEmbed]
  });
  
  db.tickets.delete(ticket.id);
}

// Commands
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isStringSelectMenu() && !interaction.isModalSubmit()) return;
  
  // Owner check for commands
  if (interaction.isCommand()) {
    const member = interaction.member;
    if (!isOwner(member)) {
      return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
    }
  }
  
  // /panel command
  if (interaction.isCommand() && interaction.commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle('🛒 Purchase Products')
      .setDescription('Hello are you looking for to purchase, create a ticket and send money to the bot and it will automatically give you your stuff!')
      .setColor(0x5865F2);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('create_ticket')
        .setLabel('Create Ticket')
        .setStyle(ButtonStyle.Primary)
    );
    
    await interaction.reply({ embeds: [embed], components: [row] });
  }
  
  // /middleman command
  if (interaction.isCommand() && interaction.commandName === 'middle/api/v3/simple/price?ids=litecoin&vs_currencies=usd', { timeout: 5000 });
    return res.data.litecoin.usd;
  } catch {
    return 85;
  }
}

// Check address balance via litecoinspace
async function checkAddressBalance(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}`, { timeout: 10000 });
    const data = res.data;
    const funded = data.chain_stats?.funded_txo_sum || 0;
    const spent = data.chain_stats?.spent_txo_sum || 0;
    const balance = (funded - spent) / 100000000;
    return { balance, txs: data.chain_stats?.tx_count || 0 };
  } catch (err) {
    console.error('Balance check error:', err.message);
    return { balance: 0, txs: 0 };
  }
}

// Check mempool for new transactions
async function checkMempool(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}/txs/mempool`, { timeout: 10000 });
    return res.data || [];
  } catch {
    return [];
  }
}

// Convert USD to LTC
function usdToLTC(usdAmount, ltcPrice) {
  return (usdAmount / ltcPrice).toFixed(8);
}

// Check if user has owner role
function isOwner(member) {
  return member.roles.cache.has(OWNER_ROLE_ID);
}

client.once('ready', async () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  
  if (!process.env.WALLET_MNEMONIC) {
    console.error('❌ WALLET_MNEMONIC not set!');
    process.exit(1);
  }
  
  walletAddress = getLTCAddress(process.env.WALLET_MNEMONIC, WALLET_INDEX);
  console.log(`💰 Using LTC Address (Index ${WALLET_INDEX}): ${walletAddress}`);
  
  // Start payment checker
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
        const ltcPrice = await getLTCPrice();
        const amountUSD = amountLTC * ltcPrice;
        const expectedUSD = ticket.totalPrice;
        const tolerance = 0.10;
        
        if (Math.abs(amountUSD - expectedUSD) <= tolerance || (amountUSD >= expectedUSD - tolerance && amountUSD <= expectedUSD + tolerance)) {
          if (ticket.status === 'awaiting_payment') {
            ticket.status = 'confirming';
            ticket.txId = tx.txid;
            ticket.amountReceived = amountLTC;
            
            const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
            if (channel) {
              await channel.send('⏳ **Payment detected in mempool!** Waiting for confirmation...');
            }
          }
        }
      }
      
      // Check confirmed balance
      const { balance, txs } = await checkAddressBalance(walletAddress);
      if (ticket.status === 'confirming' && ticket.txId) {
        const confirmed = await axios.get(`${LITECOIN_SPACE_API}/tx/${ticket.txId}`, { timeout: 10000 }).catch(() => null);
        if (confirmed && confirmed.data?.status?.confirmed) {
          await processConfirmedPayment(ticket);
        }
      }
    } catch (err) {
      console.error('Payment check error:', err.message);
    }
  }
}

async function processConfirmedPayment(ticket) {
  ticket.status = 'confirmed';
  
  const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
  if (!channel) return;
  
  await channel.send('✅ **Payment Confirmed!** Processing split...');
  
  // Split payment
  const totalLTC = ticket.amountReceived;
  const splitAmount = (totalLTC / 3).toFixed(8);
  
  const receiveChannelId = db.settings.get('receiveChannel');
  const receiveChannel = receiveChannelId ? await client.channels.fetch(receiveChannelId).catch(() => null) : null;
  
  const splitEmbed = new EmbedBuilder()
    .setTitle('💰 Payment Split')
    .setDescription(`Total: ${totalLTC} LTC\nSplit: ${splitAmount} LTC each (33/33/33)`)
    .addFields(
      SPLIT_ADDRESSES.map((addr, i) => ({ name: `Address ${i + 1}`, value: `\`${addr}\`\nAmount: ${splitAmount} LTC`, inline: false }))
    )
    .setColor(0x00FF00)
    .setTimestamp();
  
  if (receiveChannel) {
    await receiveChannel.send({ embeds: [splitEmbed] });
  }
  
  await channel.send({
    content: '✅ **Order Complete!** Payment received and split.',
    embeds: [splitEmbed]
  });
  
  db.tickets.delete(ticket.id);
}

// Commands
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isStringSelectMenu() && !interaction.isModalSubmit()) return;
  
  // Owner check for commands
  if (interaction.isCommand()) {
    const member = interaction.member;
    if (!isOwner(member)) {
      return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
    }
  }
  
  // /panel command
  if (interaction.isCommand() && interaction.commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle('🛒 Purchase Products')
      .setDescription('Hello are you looking for to purchase, create a ticket and send money to the bot and it will automatically give you your stuff!')
      .setColor(0x5865F2);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('create_ticket')
        .setLabel('Create Ticket')
        .setStyle(ButtonStyle.Primary)
    );
    
    await interaction.reply({ embeds: [embed], components: [row] });
  }
  
  // /middleman command
  if (interaction.isCommand() && interaction.commandName === 'middleman') {
    const embed = new EmbedBuilder()
      .setTitle('🤝 Middleman Service')
      .setDescription('Create a middleman ticket for secure trading')
      .setColor(0xFFA500);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('create_mm_ticket')
        .setLabel('Create Middleman Ticket')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId('close_mm')
        .setLabel('Close')
        .setStyle(ButtonStyle.Danger),
      new ButtonBuilder()
        .setCustomId('claim_mm')
        .setLabel('Claim')
        .setStyle(ButtonStyle.Primary)
    );
    
    await interaction.reply({ embeds: [embed], components: [row] });
  }
  
  // /panelcategory command
  if (interaction.isCommand() && interaction.commandName === 'panelcategory') {
    const categoryId = interaction.options.getString('id');
    db.settings.set('panelCategory', categoryId);
    await interaction.reply({ content: `✅ Panel tickets will go to <#${categoryId}>`, ephemeral: true });
  }
  
  // /middlemancategory command
  if (interaction.isCommand() && interaction.commandName === 'middlemancategory') {
    const categoryId = interaction.options.getString('id');
    db.settings.set('mmCategory', categoryId);
    await interaction.reply({ content: `✅ Middleman tickets will go to <#${categoryId}>`, ephemeral: true });
  }
  
  // /receivechannel command
  if (interaction.isCommand() && interaction.commandName === 'receivechannel') {
    const channelId = interaction.options.getString('id');
    db.settings.set('receiveChannel', channelId);
    await interaction.reply({ content: `✅ Split notifications will go to <#${channelId}>`, ephemeral: true });
  }
  
  // /info command
  if (interaction.isCommand() && interaction.commandName === 'info') {
    await interaction.reply('Hi ho hi');
  }
  
  // /close command
  if (interaction.isCommand() && interaction.commandName === 'close') {
    const channel = interaction.channel;
    if (channel.name.includes('ticket') || channel.name.includes('order') || channel.name.includes('mm')) {
      await interaction.reply('🔒 Closing ticket...');
      setTimeout(() => channel.delete().catch(() => {}), 3000);
    } else {
      await interaction.reply({ content: '❌ Not a ticket channel!', ephemeral: true });
    }
  }
  
  // Button handlers
  if (interaction.isButton()) {
    // Create product ticket
    if (interaction.customId === 'create_ticket') {
      const categoryId = db.settings.get('panelCategory');
      if (!categoryId) return interaction.reply({ content: '❌ Panel category not set!', ephemeral: true });
      
      const ticketId = `order-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId,
        type: ChannelType.GuildText,
        parent: categoryId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      
      db.tickets.set(ticketId, { id: ticketId, channelId: channel.id, userId: interaction.user.id, status: 'selecting' });
      
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select a product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({
            label: `${prod.name} - $${prod.price}${prod.unit ? ` per ${prod.unit}` : ''}`,
            value: key,
            description: `Min: ${prod.min || 1}`
          })))
      );
      
      await channel.send({
        content: `<@${interaction.user.id}> Select your product:`,
        components: [selectMenu]
      });
      
      await interaction.reply({ content: `✅ Ticket created: ${channel}`, ephemeral: true });
    }
    
    // Create middleman ticket
    if (interaction.customId === 'create_mm_ticket') {
      const categoryId = db.settings.get('mmCategory');
      if (!categoryId) return interaction.reply({ content: '❌ Middleman category not set!', ephemeral: true });
      
      const ticketId = `mm-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId,
        type: ChannelType.GuildText,
        parent: categoryId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      
      await channel.send(`<@${interaction.user.id}> Middleman ticket created. Waiting for middleman...`);
      await interaction.reply({ content: `✅ Middleman ticket: ${channel}`, ephemeral: true });
    }
    
    // Close button
    if (interaction.customId === 'close_mm' || interaction.customId === 'close_ticket') {
      await interaction.reply('🔒 Closing...');
      setTimeout(() => interaction.channel.delete().catch(() => {}), 2000);
    }
    
    // Claim button (middleman)
    if (interaction.customId === 'claim_mm') {
      await interaction.reply(`✅ Claimed by <@${interaction.user.id}>`);
    }
    
    // Confirm product
    if (interaction.customId === 'confirm_product') {
      const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
      if (!ticket) return;
      
      const modal = new ModalBuilder()
        .setCustomId('quantity_modal')
        .setTitle('Enter Quantity');
      
      const quantityInput = new TextInputBuilder()
        .setCustomId('quantity')
        .setLabel('Quantity/Amount')
        .setStyle(TextInputStyle.Short)
        .setPlaceholder('Enter amount (min 1)')
        .setRequired(true);
      
      modal.addComponents(new ActionRowBuilder().addComponents(quantityInput));
      await interaction.showModal(modal);
    }
    
    // Go back
    if (interaction.customId === 'go_back') {
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select a product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({
            label: `${prod.name} - $${prod.price}${prod.unit ? ` per ${prod.unit}` : ''}`,
            value: key,
            description: `Min: ${prod.min || 1}`
          })))
      );
      
      await interaction.update({
        content: 'Select your product:',
        components: [selectMenu],
        embeds: []
      });
    }
  }
  
  // Select menu handler
  if (interaction.isStringSelectMenu() && interaction.customId === 'product_select') {
    const productKey = interaction.values[0];
    const product = PRODUCTS[productKey];
    const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
    
    if (ticket) {
      ticket.product = product;
      ticket.productKey = productKey;
    }
    
    const embed = new EmbedBuilder()
      .setTitle(product.name)
      .setDescription(`Price: $${product.price}${product.unit ? ` per ${product.unit}` : ''}\nMinimum: ${product.min || 1}`)
      .setColor(0x5865F2);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('confirm_product')
        .setLabel('Confirm Product')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId('go_back')
        .setLabel('Go Back to Selection')
        .setStyle(ButtonStyle.Secondary)
    );
    
/api/v3/simple/price?ids=litecoin&vs_currencies=usd', { timeout: 5000 });
    return res.data.litecoin.usd;
  } catch {
    return 85;
  }
}

// Check address balance via litecoinspace
async function checkAddressBalance(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}`, { timeout: 10000 });
    const data = res.data;
    const funded = data.chain_stats?.funded_txo_sum || 0;
    const spent = data.chain_stats?.spent_txo_sum || 0;
    const balance = (funded - spent) / 100000000;
    return { balance, txs: data.chain_stats?.tx_count || 0 };
  } catch (err) {
    console.error('Balance check error:', err.message);
    return { balance: 0, txs: 0 };
  }
}

// Check mempool for new transactions
async function checkMempool(address) {
  try {
    const res = await axios.get(`${LITECOIN_SPACE_API}/address/${address}/txs/mempool`, { timeout: 10000 });
    return res.data || [];
  } catch {
    return [];
  }
}

// Convert USD to LTC
function usdToLTC(usdAmount, ltcPrice) {
  return (usdAmount / ltcPrice).toFixed(8);
}

// Check if user has owner role
function isOwner(member) {
  return member.roles.cache.has(OWNER_ROLE_ID);
}

client.once('ready', async () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  
  if (!process.env.WALLET_MNEMONIC) {
    console.error('❌ WALLET_MNEMONIC not set!');
    process.exit(1);
  }
  
  walletAddress = getLTCAddress(process.env.WALLET_MNEMONIC, WALLET_INDEX);
  console.log(`💰 Using LTC Address (Index ${WALLET_INDEX}): ${walletAddress}`);
  
  // Start payment checker
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
        const ltcPrice = await getLTCPrice();
        const amountUSD = amountLTC * ltcPrice;
        const expectedUSD = ticket.totalPrice;
        const tolerance = 0.10;
        
        if (Math.abs(amountUSD - expectedUSD) <= tolerance || (amountUSD >= expectedUSD - tolerance && amountUSD <= expectedUSD + tolerance)) {
          if (ticket.status === 'awaiting_payment') {
            ticket.status = 'confirming';
            ticket.txId = tx.txid;
            ticket.amountReceived = amountLTC;
            
            const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
            if (channel) {
              await channel.send('⏳ **Payment detected in mempool!** Waiting for confirmation...');
            }
          }
        }
      }
      
      // Check confirmed balance
      const { balance, txs } = await checkAddressBalance(walletAddress);
      if (ticket.status === 'confirming' && ticket.txId) {
        const confirmed = await axios.get(`${LITECOIN_SPACE_API}/tx/${ticket.txId}`, { timeout: 10000 }).catch(() => null);
        if (confirmed && confirmed.data?.status?.confirmed) {
          await processConfirmedPayment(ticket);
        }
      }
    } catch (err) {
      console.error('Payment check error:', err.message);
    }
  }
}

async function processConfirmedPayment(ticket) {
  ticket.status = 'confirmed';
  
  const channel = await client.channels.fetch(ticket.channelId).catch(() => null);
  if (!channel) return;
  
  await channel.send('✅ **Payment Confirmed!** Processing split...');
  
  // Split payment
  const totalLTC = ticket.amountReceived;
  const splitAmount = (totalLTC / 3).toFixed(8);
  
  const receiveChannelId = db.settings.get('receiveChannel');
  const receiveChannel = receiveChannelId ? await client.channels.fetch(receiveChannelId).catch(() => null) : null;
  
  const splitEmbed = new EmbedBuilder()
    .setTitle('💰 Payment Split')
    .setDescription(`Total: ${totalLTC} LTC\nSplit: ${splitAmount} LTC each (33/33/33)`)
    .addFields(
      SPLIT_ADDRESSES.map((addr, i) => ({ name: `Address ${i + 1}`, value: `\`${addr}\`\nAmount: ${splitAmount} LTC`, inline: false }))
    )
    .setColor(0x00FF00)
    .setTimestamp();
  
  if (receiveChannel) {
    await receiveChannel.send({ embeds: [splitEmbed] });
  }
  
  await channel.send({
    content: '✅ **Order Complete!** Payment received and split.',
    embeds: [splitEmbed]
  });
  
  db.tickets.delete(ticket.id);
}

// Commands
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand() && !interaction.isButton() && !interaction.isStringSelectMenu() && !interaction.isModalSubmit()) return;
  
  // Owner check for commands
  if (interaction.isCommand()) {
    const member = interaction.member;
    if (!isOwner(member)) {
      return interaction.reply({ content: '❌ Owner only!', ephemeral: true });
    }
  }
  
  // /panel command
  if (interaction.isCommand() && interaction.commandName === 'panel') {
    const embed = new EmbedBuilder()
      .setTitle('🛒 Purchase Products')
      .setDescription('Hello are you looking for to purchase, create a ticket and send money to the bot and it will automatically give you your stuff!')
      .setColor(0x5865F2);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('create_ticket')
        .setLabel('Create Ticket')
        .setStyle(ButtonStyle.Primary)
    );
    
    await interaction.reply({ embeds: [embed], components: [row] });
  }
  
  // /middleman command
  if (interaction.isCommand() && interaction.commandName === 'middleman') {
    const embed = new EmbedBuilder()
      .setTitle('🤝 Middleman Service')
      .setDescription('Create a middleman ticket for secure trading')
      .setColor(0xFFA500);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('create_mm_ticket')
        .setLabel('Create Middleman Ticket')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId('close_mm')
        .setLabel('Close')
        .setStyle(ButtonStyle.Danger),
      new ButtonBuilder()
        .setCustomId('claim_mm')
        .setLabel('Claim')
        .setStyle(ButtonStyle.Primary)
    );
    
    await interaction.reply({ embeds: [embed], components: [row] });
  }
  
  // /panelcategory command
  if (interaction.isCommand() && interaction.commandName === 'panelcategory') {
    const categoryId = interaction.options.getString('id');
    db.settings.set('panelCategory', categoryId);
    await interaction.reply({ content: `✅ Panel tickets will go to <#${categoryId}>`, ephemeral: true });
  }
  
  // /middlemancategory command
  if (interaction.isCommand() && interaction.commandName === 'middlemancategory') {
    const categoryId = interaction.options.getString('id');
    db.settings.set('mmCategory', categoryId);
    await interaction.reply({ content: `✅ Middleman tickets will go to <#${categoryId}>`, ephemeral: true });
  }
  
  // /receivechannel command
  if (interaction.isCommand() && interaction.commandName === 'receivechannel') {
    const channelId = interaction.options.getString('id');
    db.settings.set('receiveChannel', channelId);
    await interaction.reply({ content: `✅ Split notifications will go to <#${channelId}>`, ephemeral: true });
  }
  
  // /info command
  if (interaction.isCommand() && interaction.commandName === 'info') {
    await interaction.reply('Hi ho hi');
  }
  
  // /close command
  if (interaction.isCommand() && interaction.commandName === 'close') {
    const channel = interaction.channel;
    if (channel.name.includes('ticket') || channel.name.includes('order') || channel.name.includes('mm')) {
      await interaction.reply('🔒 Closing ticket...');
      setTimeout(() => channel.delete().catch(() => {}), 3000);
    } else {
      await interaction.reply({ content: '❌ Not a ticket channel!', ephemeral: true });
    }
  }
  
  // Button handlers
  if (interaction.isButton()) {
    // Create product ticket
    if (interaction.customId === 'create_ticket') {
      const categoryId = db.settings.get('panelCategory');
      if (!categoryId) return interaction.reply({ content: '❌ Panel category not set!', ephemeral: true });
      
      const ticketId = `order-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId,
        type: ChannelType.GuildText,
        parent: categoryId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      
      db.tickets.set(ticketId, { id: ticketId, channelId: channel.id, userId: interaction.user.id, status: 'selecting' });
      
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select a product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({
            label: `${prod.name} - $${prod.price}${prod.unit ? ` per ${prod.unit}` : ''}`,
            value: key,
            description: `Min: ${prod.min || 1}`
          })))
      );
      
      await channel.send({
        content: `<@${interaction.user.id}> Select your product:`,
        components: [selectMenu]
      });
      
      await interaction.reply({ content: `✅ Ticket created: ${channel}`, ephemeral: true });
    }
    
    // Create middleman ticket
    if (interaction.customId === 'create_mm_ticket') {
      const categoryId = db.settings.get('mmCategory');
      if (!categoryId) return interaction.reply({ content: '❌ Middleman category not set!', ephemeral: true });
      
      const ticketId = `mm-${Date.now()}`;
      const channel = await interaction.guild.channels.create({
        name: ticketId,
        type: ChannelType.GuildText,
        parent: categoryId,
        permissionOverwrites: [
          { id: interaction.guild.id, deny: [PermissionFlagsBits.ViewChannel] },
          { id: interaction.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages] }
        ]
      });
      
      await channel.send(`<@${interaction.user.id}> Middleman ticket created. Waiting for middleman...`);
      await interaction.reply({ content: `✅ Middleman ticket: ${channel}`, ephemeral: true });
    }
    
    // Close button
    if (interaction.customId === 'close_mm' || interaction.customId === 'close_ticket') {
      await interaction.reply('🔒 Closing...');
      setTimeout(() => interaction.channel.delete().catch(() => {}), 2000);
    }
    
    // Claim button (middleman)
    if (interaction.customId === 'claim_mm') {
      await interaction.reply(`✅ Claimed by <@${interaction.user.id}>`);
    }
    
    // Confirm product
    if (interaction.customId === 'confirm_product') {
      const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
      if (!ticket) return;
      
      const modal = new ModalBuilder()
        .setCustomId('quantity_modal')
        .setTitle('Enter Quantity');
      
      const quantityInput = new TextInputBuilder()
        .setCustomId('quantity')
        .setLabel('Quantity/Amount')
        .setStyle(TextInputStyle.Short)
        .setPlaceholder('Enter amount (min 1)')
        .setRequired(true);
      
      modal.addComponents(new ActionRowBuilder().addComponents(quantityInput));
      await interaction.showModal(modal);
    }
    
    // Go back
    if (interaction.customId === 'go_back') {
      const selectMenu = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('product_select')
          .setPlaceholder('Select a product')
          .addOptions(Object.entries(PRODUCTS).map(([key, prod]) => ({
            label: `${prod.name} - $${prod.price}${prod.unit ? ` per ${prod.unit}` : ''}`,
            value: key,
            description: `Min: ${prod.min || 1}`
          })))
      );
      
      await interaction.update({
        content: 'Select your product:',
        components: [selectMenu],
        embeds: []
      });
    }
  }
  
  // Select menu handler
  if (interaction.isStringSelectMenu() && interaction.customId === 'product_select') {
    const productKey = interaction.values[0];
    const product = PRODUCTS[productKey];
    const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
    
    if (ticket) {
      ticket.product = product;
      ticket.productKey = productKey;
    }
    
    const embed = new EmbedBuilder()
      .setTitle(product.name)
      .setDescription(`Price: $${product.price}${product.unit ? ` per ${product.unit}` : ''}\nMinimum: ${product.min || 1}`)
      .setColor(0x5865F2);
    
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId('confirm_product')
        .setLabel('Confirm Product')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId('go_back')
        .setLabel('Go Back to Selection')
        .setStyle(ButtonStyle.Secondary)
    );
    
    await interaction.update({ embeds: [embed], components: [row], content: ' ' });
  }
  
  // Modal submit handler
  if (interaction.isModalSubmit() && interaction.customId === 'quantity_modal') {
    const quantity = parseInt(interaction.fields.getTextInputValue('quantity'));
    const ticket = Array.from(db.tickets.values()).find(t => t.channelId === interaction.channel.id);
    
    if (!ticket || !ticket.product) return;
    
    const product = ticket.product;
    if (product.min && quantity < product.min) {
      return interaction.reply({ content: `❌ Minimum quantity is ${product.min}!`, ephemeral: true });
    }
    
    let totalUSD = product.price * quantity;
    if (product.unit) {
      totalUSD = product.price * (quantity / product.unit);
    }
    
    const ltcPrice = await getLTCPrice();
    const totalLTC = usdToLTC(totalUSD, ltcPrice);
    
    ticket.quantity = quantity;
    ticket.totalPrice = totalUSD;
    ticket.totalLTC = totalLTC;
    ticket.status = 'awaiting_payment';
    
    const embed = new EmbedBuilder()
      .setTitle('💳 Payment Required')
      .setDescription(`Product: ${product.name}\nQuantity: ${quantity}\nTotal: $${totalUSD.toFixed(2)} USD\n\nSend **${totalLTC} LTC** to:\n\`${walletAddress}\``)
      .setFooter({ text: 'Tolerance: ±$0.10 | Confirming in mempool...' })
      .setColor(0xFF0000);
    
    await interaction.reply({ embeds: [embed] });
  }
});

// Register commands
client.on('ready', async () => {
  const commands = [
    { name: 'panel', description: 'Spawn purchase panel' },
    { name: 'middleman', description: 'Spawn middleman panel' },
    { name: 'panelcategory', description: 'Set panel ticket category', options: [{ name: 'id', type: 3, description: 'Category ID', required: true }] },
    { name: 'middlemancategory', description: 'Set middleman ticket category', options: [{ name: 'id', type: 3, description: 'Category ID', required: true }] },
    { name: 'receivechannel', description: 'Set channel for split notifications', options: [{ name: 'id', type: 3, description: 'Channel ID', required: true }] },
    { name: 'info', description: 'Bot info' },
    { name: 'close', description: 'Close current ticket' }
  ];
  
  try {
    await client.application.commands.set(commands);
    console.log('✅ Commands registered');
  } catch (err) {
    console.error('Command registration error:', err);
  }
});

client.login(process.env.DISCORD_TOKEN).catch(err => {
  console.error('❌ Login failed:', err);
  process.exit(1);
});
