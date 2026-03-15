const bip39 = require('bip39');
const bip32 = require('bip32');
const bitcoin = require('bitcoinjs-lib');
const tinysecp = require('tiny-secp256k1');
const axios = require('axios');
const { getAddressUTXOs, getFeeEstimate, LITECOINSPACE_API } = require('./blockchain');

// Litecoin network
const LITECOIN_NETWORK = {
  messagePrefix: '\x19Litecoin Signed Message:\n',
  bech32: 'ltc',
  bip32: {
    public: 0x019da462,
    private: 0x019d9cfe,
  },
  pubKeyHash: 0x30,
  scriptHash: 0x32,
  wif: 0xb0,
};

// Initialize wallet with mnemonic - ONLY USE INDEX 8
function initializeWallet(mnemonic) {
  if (!bip39.validateMnemonic(mnemonic)) {
    throw new Error('Invalid mnemonic');
  }
  
  const seed = bip39.mnemonicToSeedSync(mnemonic);
  const root = bip32.BIP32Factory(tinysecp).fromSeed(seed, LITECOIN_NETWORK);
  
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
        index: utxo.voutSeed(seed, LITECOIN_NETWORK);
  
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
