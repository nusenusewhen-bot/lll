require('dotenv').config();
const {
  Client,
  GatewayIntentBits,
  PermissionsBitField,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  EmbedBuilder,
  SlashCommandBuilder,
  Routes,
  REST,
  ModalBuilder,
  TextInputBuilder,
  TextInputStyle,
  StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder,
  ComponentType
} = require('discord.js');
const db = require('./database');
const { getWalletAddress, getWalletBalance, splitPayment, sendAllLTC, ltcToSatoshis } = require('./wallet');
const { getLtcPriceUSD, checkNewTransactions, getAddressInfo } = require('./blockchain');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

// Config
const OWNER_ROLE_ID = process.env.OWNER_ROLE_ID;
const SPLIT_ADDRESSES = [
  'LN281Mti6rYrgsUVYUmJkFrQwWRF8jGUcD',
  'LVmzZTh52LL6w4o8k3tU7TXjqJ9rcnknfP',
  'LeDdjh2BDbPkrhG2pkWBko3HRdKQzprJMX'
];

// Product catalog
const PRODUCTS = {
  nitro_boost: { name: 'Nitro Boost', price: 2.5 },
  nitro_basic: { name: 'Nitro Basic', price: 1 },
  offline_members: { name: 'Offline Members', price: 0.7, unit: 1000, min: 1000 },
  online_members: { name: 'Online Members', price: 1.5, unit: 1000, min: 1000 },
  mcfa: { name: 'MCFA Full Access Lifetime', price: 5.99 },
  netflix: { name: 'Netflix Lifetime', price: 1 },
  disney: { name: 'Disney Lifetime', price: 1 },
  crunchyroll: { name: 'Crunchyroll Lifetime', price: 1 },
  custom_bot: { name: 'Custom Bot', price: 3 },
  generator: { name: 'Generator', price: 10 },
  humaniser: { name: 'Humaniser', price: 5 }
};

// Check if user has owner role
function isOwner(member) {
  return member.roles.cache.has(OWNER_ROLE_ID);
}

// Register slash commands
async function registerCommands() {
  const commands = [
    new SlashCommandBuilder()
      .setName('panel')
      .setDescription('Spawn purchase panel (Owner only)'),
    new SlashCommandBuilder()
      .setName('middleman')
      .setDescription('Spawn middleman panel (Owner only)'),
    new SlashCommandBuilder()
      .setName('panelcategory')
      .setDescription('Set panel ticket category (Owner only)')
      .addStringOption(opt => opt.setName('category_id').setDescription('Category ID').setRequired(true)),
    new SlashCommandBuilder()
      .setName('middlemancategory')
      .setDescription('Set middleman ticket category (Owner only)')
      .addStringOption(opt => opt.setName('category_id').setDescription('Category ID').setRequired(true)),
    new SlashCommandBuilder()
      .setName('receivechannel')
      .setDescription('Set channel for split notifications (Owner only)')
      .addStringOption(opt => opt.setName('channel_id').setDescription('Channel ID').setRequired(true)),
    new SlashCommandBuilder()
      .setName('close')
      .setDescription('Close current ticket (Owner only)'),
    new SlashCommandBuilder()
      .setName('info')
      .setDescription('Bot info'),
    new SlashCommandBuilder()
      .setName('balance')
      .setDescription('Check bot wallet balance (OwnerSeed(seed, LITECOIN_NETWORK);
  
  // ONLY using index 8 as requested
  const node = root.derivePath(`m/84'/2'/0'/0/8`);
  const address = bitcoin.payments.p2wpkh({
    pubkey: node.publicKey,
    network: LITECOIN_NETWORK,
  }).address;
  
  return {
    node,
    address,
    index: 8
  };
}

// Get wallet address (always index 8)
function getWalletAddress(mnemonic) {
  const wallet = initializeWallet(mnemonic);
  return wallet.address;
}

// Get private key for signing
function getPrivateKey(mnemonic) {
  const wallet = initializeWallet(mnemonic);
  return wallet.node;
}

// Convert satoshis to LTC
function satoshisToLTC(satoshis) {
  return satoshis / 100000000;
}

// Convert LTC to satoshis
function ltcToSatoshis(ltc) {
  return Math.round(ltc * 100000000);
}

// Get balance for the single address
async function getWalletBalance(mnemonic) {
  const address = getWalletAddress(mnemonic);
  
  try {
    const response = await axios.get(`${LITECOINSPACE_API}/address/${address}`, {
      timeout: 10000
    });
    
    const confirmed = response.data.chain_stats.funded_txo_sum - response.data.chain_stats.spent_txo_sum;
    const unconfirmed = response.data.mempool_stats.funded_txo_sum - response.data.mempool_stats.spent_txo_sum;
    
    return {
      confirmed: satoshisToLTC(confirmed),
      unconfirmed: satoshisToLTC(unconfirmed),
      total: satoshisToLTC(confirmed + unconfirmed),
      address: address
    };
  } catch (error) {
    console.error('Balance check error:', error.message);
    return { confirmed: 0, unconfirmed: 0, total: 0, address: address };
  }
}

// Split payment 33/33/33 to three addresses
async function splitPayment(mnemonic, targetAddresses, totalAmountLTC) {
  try {
    const wallet = initializeWallet(mnemonic);
    const utxos = await getAddressUTXOs(wallet.address);
    
    if (!utxos.length) {
      throw new Error('No UTXOs available');
    }
    
    const feeRate = await getFeeEstimate();
    const psbt = new bitcoin.Psbt({ network: LITECOIN_NETWORK });
    
    let inputSum = 0;
    const inputs = [];
    
    // Add inputs
    for (const utxo of utxos) {
      const txHex = await axios.get(`${LITECOINSPACE_API}/tx/${utxo.txid}/hex`, { timeout: 10000 });
      
      psbt.addInput({
        hash: utxo.txid,
        index: utxo.vout,
        witnessUtxo: {
          script: bitcoin.address.toOutputScript(wallet.address, LITECOIN_NETWORK),
          value: utxo.value,
        },
      });
      
      inputSum += utxo.value;
      inputs.push(utxo);
      
      if (inputSum >= ltcToSatoshis(totalAmountLTC) + 10000) break;
    }
    
    const totalSats = ltcToSatoshis(totalAmountLTC);
    const splitAmount = Math.floor(totalSats / 3);
    const fee = Math.ceil((34 * 3 + 68 * inputs.length) * feeRate);
    
    // Add outputs (33% each)
    for (const addr of targetAddresses) {
      psbt.addOutput({
        address: addr,
        value: splitAmount - Math.floor(fee / 3),
      });
    }
    
    // Sign inputs
    inputs.forEach((_, idx) => {
      psbt.signInput(idx, wallet.node);
    });
    
    psbt.finalizeAllInputs();
    const txHex = psbt.extractTransaction().toHex();
    
    // Broadcast
    const broadcast = await axios.post(`${LITECOINSPACE_API}/tx`, txHex, {
      headers: { 'Content-Type': 'text/plain' },
      timeout: 15000
    });
    
    return {
      success: true,
      txHash: broadcast.data,
      splitAmount: satoshisToLTC(splitAmount),
      addresses: targetAddresses
    };
    
  } catch (error) {
    console.error('Split payment error:', error.message);
    return { success: false, error: error.message };
  }
}

// Send all LTC to a specific address (for /send command)
async function sendAllLTC(mnemonic, toAddress) {
  try {
    const wallet = initializeWallet(mnemonic);
    const utxos = await getAddressUTXOs(wallet.address);
    
    if (!utxos.length) {
      throw new Error('Wallet is empty');
    }
    
    const feeRate = await getFeeEstimate();
    const psbt = new bitcoin.Psbt({ network: LITECOIN_NETWORK });
    
    let inputSum = 0;
    
    for (const utxo of utxos) {
      psbt.addInput({
        hash: utxo.txid,
        index: utxo.vout,
        witnessUtxo: {
          script: bitcoin.address.toOutputScript(wallet.address, LITECOIN_NETWORK),
          value: utxo.value,
        },
      });
      inputSum += utxo.value;
    }
    
    const fee = Math.ceil((34 + 68 * utxos.length) * feeRate);
    const sendAmount = inputSum - fee;
    
    psbt.addOutput({
      address: toAddress,
      value: sendAmount,
    });
    
    utxos.forEach((_, idx) => {
      psbt.signInput(idx, wallet.node);
    });
    
    psbt.finalizeAllInputs();
    const txHex = psbt.extractTransaction().toHex();
    
    const broadcast = await axios.post(`${LITECOINSPACE_API}/tx`, txHex, {
      headers: { 'Content-Type': 'text/plain' },
      timeout: 15000
    });
    
    return {
      success: true,
      txHash: broadcast.data,
      amount: satoshisToLTC(sendAmount)
    };
    
  } catch (error) {
    console.error('Send error:', error.message);
    return { success: false, error: error.message };
  }
}

module.exports = {
  initializeWallet,
  getWalletAddress,
  getWalletBalance,
  splitPayment,
  sendAllLTC,
  ltcToSatoshis,
  satoshisToLTC
};
