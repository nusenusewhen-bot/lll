const axios = require('axios');

const LITECOINSPACE_API = 'https://litecoinspace.org/api';

// Get LTC price in USD
async function getLtcPriceUSD() {
  try {
    const response = await axios.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd', {
      timeout: 5000
    });
    return response.data.litecoin.usd;
  } catch (error) {
    console.error('Price fetch error:', error.message);
    return 85; // Fallback price
  }
}

// Get address balance and transactions
async function getAddressInfo(address) {
  try {
    const [balanceRes, txsRes] = await Promise.all([
      axios.get(`${LITECOINSPACE_API}/address/${address}`, { timeout: 10000 }),
      axios.get(`${LITECOINSPACE_API}/address/${address}/txs`, { timeout: 10000 })
    ]);

    return {
      balance: balanceRes.data.chain_stats.funded_txo_sum - balanceRes.data.chain_stats.spent_txo_sum,
      unconfirmedBalance: balanceRes.data.mempool_stats.funded_txo_sum - balanceRes.data.mempool_stats.spent_txo_sum,
      txCount: balanceRes.data.chain_stats.tx_count,
      transactions: txsRes.data || []
    };
  } catch (error) {
    console.error('Address info error:', error.message);
    return { balance: 0, unconfirmedBalance: 0, txCount: 0, transactions: [] };
  }
}

// Get specific transaction details
async function getTransaction(txHash) {
  try {
    const response = await axios.get(`${LITECOINSPACE_API}/tx/${txHash}`, {
      timeout: 10000
    });
    return response.data;
  } catch (error) {
    console.error('Transaction fetch error:', error.message);
    return null;
  }
}

// Check for new transactions to address
async function checkNewTransactions(address, lastCheckedTx = null) {
  try {
    const info = await getAddressInfo(address);
    const transactions = info.transactions;
    
    if (!transactions.length) return [];
    
    // Filter for new incoming transactions
    const incomingTxs = transactions.filter(tx => {
      if (lastCheckedTx && tx.txid === lastCheckedTx) return false;
      
      // Check if our address is a recipient
      const isRecipient = tx.vout.some(output => 
        output.scriptpubkey_address === address
      );
      return isRecipient;
    });
    
    return incomingTxs;
  } catch (error) {
    console.error('Check transactions error:', error.message);
    return [];
  }
}

// Get UTXOs for spending
async function getAddressUTXOs(address) {
  try {
    const response = await axios.get(`${LITECOINSPACE_API}/address/${address}/utxo`, {
      timeout: 10000
    });
    return response.data || [];
  } catch (error) {
    console.error('UTXO fetch error:', error.message);
    return [];
  }
}

// Get fee estimate
async function getFeeEstimate() {
  try {
    const response = await axios.get(`${LITECOINSPACE_API}/fees/recommended`, {
      timeout: 5000
    });
    return response.data.fastestFee || 2; // sats/vbyte
  } catch (error) {
    return 2;
  }
}

module.exports = {
  getLtcPriceUSD,
  getAddressInfo,
  getTransaction,
  checkNewTransactions,
  getAddressUTXOs,
  getFeeEstimate,
  LITECOINSPACE_API
};
