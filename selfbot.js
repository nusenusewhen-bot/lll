const { Client } = require('discord.js-selfbot-v13');
const axios = require('axios');
const { HttpsProxyAgent } = require('https-proxy-agent');
const os = require('os');

// ─── Config ───
const CONFIG = {
    token: process.env.SELFBOT_TOKEN,
    botApiUrl: process.env.BOT_API_URL || 'http://localhost:8080',
    razorcapKey: process.env.RAZORCAP_API_KEY || '44b5a90f-182f-4c67-b219-ef8dfd33d7a1',
    proxies: (process.env.PROXIES || '').split(',').filter(p => p),
    fingerprintRotation: 300000, // 5 min
    claimDelay: { min: 800, max: 2500 }
};

// ─── Proxy Rotator ───
class ProxyRotator {
    constructor() {
        this.proxies = CONFIG.proxies;
        this.current = 0;
        this.working = new Map();
    }
    
    get() {
        if (this.proxies.length === 0) return null;
        const proxy = this.proxies[this.current % this.proxies.length];
        this.current++;
        return proxy;
    }
    
    async test(proxy) {
        try {
            const agent = new HttpsProxyAgent(proxy);
            await axios.get('https://discord.com/api/v9/users/@me', {
                httpsAgent: agent,
                timeout: 10000,
                headers: { 'Authorization': CONFIG.token }
            });
            return true;
        } catch {
            return false;
        }
    }
}

// ─── Fingerprint Generator ───
class Fingerprint {
    constructor() {
        this.browsers = ['Chrome/120.0.0.0', 'Firefox/121.0', 'Safari/605.1.15'];
        this.systems = ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7', 'X11; Linux x86_64'];
        this.rotate();
    }
    
    rotate() {
        this.ua = `Mozilla/5.0 (${this.systems[Math.floor(Math.random() * this.systems.length])}) AppleWebKit/537.36 (KHTML, like Gecko) ${this.browsers[Math.floor(Math.random() * this.browsers.length)]}`;
        this.screen = `${1920 + Math.floor(Math.random() * 200)}x${1080 + Math.floor(Math.random() * 200)}`;
        this.timezone = ['America/New_York', 'Europe/London', 'Asia/Tokyo'][Math.floor(Math.random() * 3)];
        this.colorDepth = [24, 32][Math.floor(Math.random() * 2)];
        this.memory = [4, 8, 16][Math.floor(Math.random() * 3)];
    }
    
    getHeaders() {
        return {
            'User-Agent': this.ua,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://discord.com/',
            'Origin': 'https://discord.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Debug-Options': 'bugReporterEnabled',
            'X-Discord-Locale': 'en-US',
            'X-Discord-Timezone': this.timezone,
            'X-Super-Properties': Buffer.from(JSON.stringify({
                os: process.platform,
                browser: 'Chrome',
                device: '',
                system_locale: 'en-US',
                browser_user_agent: this.ua,
                browser_version: '120.0.0.0',
                os_version: '10',
                referrer: '',
                referring_domain: '',
                referrer_current: '',
                referring_domain_current: '',
                release_channel: 'stable',
                client_build_number: 123456,
                client_event_source: null
            })).toString('base64')
        };
    }
}

// ─── CAPTCHA Solver ───
class CaptchaSolver {
    constructor() {
        this.endpoint = 'https://api.razorcap.cc/solve';
    }
    
    async solve(siteKey, pageUrl, type = 'hcaptcha_enterprise', rqdata = null, proxy = null) {
        try {
            const payload = {
                type,
                websiteURL: pageUrl,
                websiteKey: siteKey,
                rqdata,
                proxy
            };
            
            const res = await axios.post(this.endpoint, payload, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${CONFIG.razorcapKey}`
                },
                timeout: 30000
            });
            
            if (res.data.error) throw new Error(res.data.error);
            
            // Poll for result
            return await this.pollResult(res.data.taskId);
        } catch (err) {
            console.log('RazorCap failed:', err.message);
            return this.solveBackup(siteKey, pageUrl);
        }
    }
    
    async pollResult(taskId, attempts = 60) {
        for (let i = 0; i < attempts; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try {
                const res = await axios.get(`${this.endpoint}/result/${taskId}`, {
                    headers: { 'Authorization': `Bearer ${CONFIG.razorcapKey}` }
                });
                if (res.data.status === 'ready') return res.data.solution;
            } catch (e) {
                console.log('Poll error:', e.message);
            }
        }
        throw new Error('Timeout');
    }
    
    async solveBackup(siteKey, pageUrl) {
        // Free fallback: browser automation or manual queue
        console.log('Using backup solver...');
        // In minimal version, this would implement puppeteer/playwright
        // For now, return null to indicate failure
        return null;
    }
}

// ─── Main SelfBot ───
class SelfBot {
    constructor() {
        this.client = new Client({
            checkUpdate: false,
            patchVoice: true,
            autoRedeemNitro: false,
            ws: {
                properties: {
                    $browser: 'Discord Client',
                    $device: 'desktop',
                    $os: process.platform
                }
            }
        });
        
        this.proxy = new ProxyRotator();
        this.fp = new Fingerprint();
        this.captcha = new CaptchaSolver();
        this.settings = {
            status: 'stopped',
            categoryId: null,
            claimCmd: 'claim',
            transferCmd: null,
            transferId: null
        };
        this.claimed = new Set();
        this.channels = new Map();
        
        // Rotate fingerprint every 5 min
        setInterval(() => this.fp.rotate(), CONFIG.fingerprintRotation);
    }
    
    async start() {
        this.setupEvents();
        
        try {
            await this.client.login(CONFIG.token);
            console.log(`Logged in as ${this.client.user.tag}`);
            
            // Start polling for settings from main bot
            this.pollSettings();
            
        } catch (err) {
            if (err.message.includes('captcha')) {
                await this.handleCaptcha(err);
            } else {
                console.error('Login failed:', err);
                process.exit(1);
            }
        }
    }
    
    setupEvents() {
        this.client.on('channelCreate', (ch) => this.handleChannel(ch));
        this.client.on('guildCreate', (g) => console.log(`Joined guild: ${g.name}`));
        
        // Anti-detection: random activity
        setInterval(() => {
            const activities = ['online', 'idle', 'dnd'];
            const activity = activities[Math.floor(Math.random() * activities.length)];
            this.client.user.setStatus(activity);
        }, 300000);
    }
    
    async handleCaptcha(error) {
        console.log('CAPTCHA detected, solving...');
        try {
            const solution = await this.captcha.solve(
                'f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34',
                'https://discord.com/login',
                'hcaptcha_enterprise',
                error.captcha_rqdata,
                this.proxy.get()
            );
            
            if (solution) {
                console.log('CAPTCHA solved, retrying login...');
                // Note: Actually injecting the solution requires modifying the login flow
                // This is simplified - you'd need to use the solution token in the login request
                await this.client.login(CONFIG.token);
            }
        } catch (err) {
            console.error('CAPTCHA solve failed:', err);
            process.exit(1);
        }
    }
    
    async handleChannel(channel) {
        if (this.settings.status !== 'running') return;
        if (!this.settings.categoryId) return;
        if (channel.parentId !== this.settings.categoryId) return;
        if (this.claimed.has(channel.id)) return;
        
        console.log(`New ticket: ${channel.name}`);
        
        // Random delay to seem human
        await this.delay();
        
        try {
            // Send claim command
            await channel.send(this.settings.claimCmd);
            this.claimed.add(channel.id);
            
            // Transfer if configured
            if (this.settings.transferCmd && this.settings.transferId) {
                await this.delay(1000, 2000);
                await channel.send(`${this.settings.transferCmd} ${this.settings.transferId}`);
            }
            
            console.log(`Claimed: ${channel.id}`);
            
        } catch (err) {
            console.error(`Failed to claim ${channel.id}:`, err.message);
        }
    }
    
    async pollSettings() {
        // Poll main bot for settings updates
        while (true) {
            try {
                const res = await axios.get(`${CONFIG.botApiUrl}/settings/${this.client.user.id}`, {
                    timeout: 5000
                });
                if (res.data) {
                    this.settings = {
                        status: res.data.status || 'stopped',
                        categoryId: res.data.ticket_category,
                        claimCmd: res.data.command || 'claim',
                        transferCmd: res.data.transfer_command,
                        transferId: res.data.custom_id
                    };
                }
            } catch (err) {
                // Bot API might not be running yet
            }
            await new Promise(r => setTimeout(r, 2000));
        }
    }
    
    delay(min = CONFIG.claimDelay.min, max = CONFIG.claimDelay.max) {
        const ms = Math.floor(Math.random() * (max - min + 1)) + min;
        return new Promise(r => setTimeout(r, ms));
    }
}

// Start
const bot = new SelfBot();
bot.start();

// Keep alive for Railway
const http = require('http');
http.createServer((req, res) => res.end('SelfBot Running')).listen(process.env.PORT || 3000);
