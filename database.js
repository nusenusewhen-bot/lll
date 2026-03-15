const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'bot.db'));

// Initialize tables
db.exec(`
  CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT UNIQUE,
    user_id TEXT,
    type TEXT,
    product TEXT,
    quantity INTEGER,
    total_usd REAL,
    ltc_amount REAL,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    tx_hash TEXT,
    amount_ltc REAL,
    confirmations INTEGER,
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
  );
`);

console.log('✅ Database initialized');

module.exports = db;
