const WebSocket = require('ws');
const axios = require('axios');
const sqlite3 = require('better-sqlite3');
const { randomInt } = require('crypto');
require('dotenv').config();

const TOKEN = process.env.SELFBOT_TOKEN;
const OWNER_ID = process.env.OWNER_ID;
const API_URL = process.env.BOT_API_URL || 'http://localhost:3001';
const RAZORCAP_KEY = process.env.RAZORCAP_API_KEY || '44b5a90f-182f-4c67-b219-ef8dfd33d7a1';

if (!TOKEN) {
    console.error('❌ SELFBOT_TOKEN not set');
    process.exit(1);
}

const db = sqlite3('bot.db');

class Fingerprint {
    constructor() {
        this.rotate();
    }
    
    rotate() {
        this.ua = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${randomInt(120, 126)}.0.0.0 Safari/537.36`;
        this.locale = ['en-US', 'en-GB', 'de-DE'][randomInt(0, 3)];
        const props = {
            os: 'Windows', browser: 'Chrome', device: '',
            system_locale: this.locale, browser_user_agent: this.ua,
            browser_version: '120.0.0.0', os_version: '10',
            release_channel: 'stable', client_build_number: randomInt(240000, 250001)
        };
        this.super = Buffer.from(JSON.stringify(props)).toString('base64');
    }
    
    headers(auth) {
        const h = {
            'User-Agent': this.ua, 'Accept': '*/*',
            'Accept-Language': `${this.locale},en;q=0.9`,
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://discord.com/', 'Origin': 'https://discord.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
            'X-Debug-Options': 'bugReporterEnabled', 'X-Discord-Locale': this.locale,
            'X-Super-Properties': this.super
        };
        if (auth) h.Authorization = auth;
        return h;
    }
}

class CaptchaSolver {
    constructor(fp) {
        this.fp = fp;
    }
    
    async razorcap(siteKey, pageUrl, rqdata) {
        try {
            const payload = {
                type: 'hcaptcha_enterprise',
                websiteURL: pageUrl,
                websiteKey: siteKey,
                rqdata
            };
            const { data } = await axios.post('https://api.razorcap.cc/solve', payload, {
                headers: { Authorization: `Bearer ${RAZORCAP_KEY}`, 'User-Agent': this.fp.ua },
                timeout: 30000
            });
            if (data.error) return null;
            return this.poll(data.taskId);
        } catch (e) {
            console.error('RazorCap:', e.message);
            return null;
        }
    }
    
    async poll(taskId, max = 60) {
        for (let i = 0; i < max; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try {
                const { data } = await axios.get(`https://api.razorcap.cc/solve/result/${taskId}`, {
                    headers: { Authorization: `Bearer ${RAZORCAP_KEY}` }
                });
                if (data.status === 'ready') return data.solution?.token || data.solution;
            } catch {}
        }
        return null;
    }
    
    async twocaptcha(siteKey, pageUrl) {
        const key = process.env['2CAPTCHA_API_KEY'];
        if (!key) return null;
        try {
            const { data } = await axios.get('http://2captcha.com/in.php', {
                params: { key, method: 'hcaptcha', sitekey: siteKey, pageurl: pageUrl, json: 1 }
            });
            if (data.status !== 1) return null;
            const cid = data.request;
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 5000));
                const { data: res } = await axios.get('http://2captcha.com/res.php', {
                    params: { key, action: 'get', id: cid, json: 1 }
                });
                if (res.status === 1) return res.request;
            }
        } catch (e) {
            console.error('2Captcha:', e.message);
        }
        return null;
    }
    
    async solve(siteKey, pageUrl, rqdata) {
        let result = await this.razorcap(siteKey, pageUrl, rqdata);
        if (result) return result;
        result = await this.twocaptcha(siteKey, pageUrl);
        if (result) return result;
        throw new Error('All solvers failed');
    }
}

class SelfBot {
    constructor() {
        this.token = TOKEN;
        this.ownerId = OWNER_ID;
        this.fp = new Fingerprint();
        this.captcha = new CaptchaSolver(this.fp);
        this.ws = null;
        this.sessionId = null;
        this.heartbeat = null;
        this.settings = {
            status: 'stopped',
            category_id: null,
            claim_cmd: 'claim',
            transfer_cmd: null,
            transfer_id: null
        };
        this.claimed = new Set();
        this.http = axios.create({ headers: this.fp.headers(TOKEN) });
        this.running = false;
    }
    
    updateDb(status) {
        try {
            db.prepare('UPDATE selfbot_sessions SET status = ?, last_ping = ? WHERE user_id = ?')
                .run(status, Date.now(), this.ownerId);
        } catch (e) {
            console.error('DB:', e.message);
        }
    }
    
    async fetchSettings() {
        try {
            const { data } = await this.http.get(`${API_URL}/settings/${this.ownerId}`);
            Object.assign(this.settings, data);
            console.log('Settings:', this.settings);
        } catch (e) {
            console.debug('Fetch settings:', e.message);
        }
    }
    
    async api(method, endpoint, json) {
        try {
            const url = `https://discord.com/api/v9${endpoint}`;
            const { data, status } = await this.http.request({ method, url, data: json });
            if (status === 204) return {};
            if (status === 429) {
                await new Promise(r => setTimeout(r, 1000));
                return this.api(method, endpoint, json);
            }
            if (status >= 400) return null;
            return data;
        } catch (e) {
            console.error('API:', e.message);
            return null;
        }
    }
    
    async send(channelId, content) {
        return this.api('POST', `/channels/${channelId}/messages`, {
            content,
            nonce: String(randomInt(10**18, 10**19 - 1)),
            tts: false
        });
    }
    
    async start() {
        console.log('Starting selfbot...');
        const me = await this.api('GET', '/users/@me');
        if (!me) {
            console.error('Invalid token!');
            this.updateDb('error_invalid_token');
            return;
        }
        console.log(`Logged in as ${me.username}`);
        this.updateDb('online');
        this.running = true;
        
        setInterval(() => this.fetchSettings(), 2000);
        setInterval(() => this.updateDb('online'), 30000);
        setInterval(() => {
            this.fp.rotate();
            this.http.defaults.headers = this.fp.headers(this.token);
        }, 300000);
        
        await this.gateway();
    }
    
    async gateway() {
        while (this.running) {
            try {
                this.ws = new WebSocket('wss://gateway.discord.gg/?v=9&encoding=json');
                
                this.ws.on('open', () => {
                    console.log('Gateway connected');
                    this.identify();
                });
                
                this.ws.on('message', (data) => {
                    this.handle(JSON.parse(data));
                });
                
                this.ws.on('error', (e) => {
                    console.error('WS error:', e.message);
                });
                
                this.ws.on('close', () => {
                    console.log('Gateway closed');
                });
                
                await new Promise(r => this.ws.once('close', r));
                this.updateDb('reconnecting');
                await new Promise(r => setTimeout(r, 5000));
            } catch (e) {
                console.error('Gateway:', e.message);
                await new Promise(r => setTimeout(r, 5000));
            }
        }
    }
    
    identify() {
        this.ws.send(JSON.stringify({
            op: 2,
            d: {
                token: this.token,
                properties: {
                    os: 'Windows', browser: 'Chrome', device: '',
                    system_locale: this.fp.locale, browser_user_agent: this.fp.ua,
                    browser_version: '120.0.0.0', os_version: '10',
                    release_channel: 'stable', client_build_number: 245666
                },
                presence: { status: 'online', since: 0, activities: [], afk: false },
                compress: false
            }
        }));
    }
    
    handle(msg) {
        const { op, d, t } = msg;
        
        if (op === 10) {
            this.heartbeat = d.heartbeat_interval;
            this.beat();
        } else if (op === 0) {
            if (t === 'READY') {
                this.sessionId = d.session_id;
                console.log(`Ready: ${this.sessionId.slice(0, 8)}...`);
                this.updateDb('online');
                d.guilds.forEach(g => console.log(`Guild: ${g.name}`));
            } else if (t === 'CHANNEL_CREATE') {
                this.onChannel(d);
            }
        }
    }
    
    beat() {
        setInterval(() => {
            if (this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ op: 1, d: this.sessionId }));
            }
        }, this.heartbeat);
    }
    
    async onChannel(ch) {
        if (this.settings.status !== 'running') return;
        if (!this.settings.category_id) return;
        if (String(ch.parent_id) !== String(this.settings.category_id)) return;
        if (this.claimed.has(ch.id)) return;
        
        console.log(`🎫 Ticket: ${ch.name}`);
        await new Promise(r => setTimeout(r, randomInt(800, 2501)));
        
        if (await this.send(ch.id, this.settings.claim_cmd)) {
            this.claimed.add(ch.id);
            console.log(`✅ Claimed: ${ch.id}`);
            
            if (this.settings.transfer_cmd && this.settings.transfer_id) {
                await new Promise(r => setTimeout(r, 1000 + Math.random() * 1000));
                if (await this.send(ch.id, `${this.settings.transfer_cmd} ${this.settings.transfer_id}`)) {
                    console.log('📤 Transferred');
                }
            }
        } else {
            console.error(`❌ Failed: ${ch.id}`);
        }
    }
}

const bot = new SelfBot();
bot.start().catch(e => {
    console.error('Fatal:', e);
    process.exit(1);
});
