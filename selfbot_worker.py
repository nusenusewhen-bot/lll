import os
import sys
import asyncio
import aiohttp
import websockets
import json
import random
import base64
import time
import logging
import sqlite3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(f'SelfBot-{os.getpid()}')

# Get config from environment
TOKEN = os.environ.get('SELFBOT_TOKEN')
OWNER_ID = os.environ.get('OWNER_ID')
API_URL = os.environ.get('BOT_API_URL', 'http://localhost:8080')
RAZORCAP_KEY = os.environ.get('RAZORCAP_API_KEY', '44b5a90f-182f-4c67-b219-ef8dfd33d7a1')

if not TOKEN:
    logger.error("No SELFBOT_TOKEN provided!")
    sys.exit(1)

db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row

# ─── FINGERPRINT ───
class Fingerprint:
    def __init__(self):
        self.rotate()
    
    def rotate(self):
        self.ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(120,125)}.0.0.0 Safari/537.36"
        self.locale = random.choice(['en-US', 'en-GB', 'de-DE'])
        props = {"os": "Windows", "browser": "Chrome", "device": "", 
                "system_locale": self.locale, "browser_user_agent": self.ua,
                "browser_version": "120.0.0.0", "os_version": "10",
                "release_channel": "stable", "client_build_number": random.randint(240000,250000)}
        self.super = base64.b64encode(json.dumps(props).encode()).decode()
    
    def headers(self, auth=None):
        h = {
            'User-Agent': self.ua, 'Accept': '*/*', 
            'Accept-Language': f'{self.locale},en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://discord.com/', 'Origin': 'https://discord.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
            'X-Debug-Options': 'bugReporterEnabled', 'X-Discord-Locale': self.locale,
            'X-Super-Properties': self.super
        }
        if auth:
            h['Authorization'] = auth
        return h

# ─── CAPTCHA SOLVER ───
class CaptchaSolver:
    def __init__(self, fp):
        self.fp = fp
        self.session = None
    
    async def init(self):
        self.session = aiohttp.ClientSession()
    
    async def razorcap(self, site_key, page_url, rqdata=None):
        try:
            payload = {
                'type': 'hcaptcha_enterprise',
                'websiteURL': page_url,
                'websiteKey': site_key,
                'rqdata': rqdata
            }
            payload = {k: v for k, v in payload.items() if v}
            
            async with self.session.post(
                'https://api.razorcap.cc/solve',
                json=payload,
                headers={'Authorization': f'Bearer {RAZORCAP_KEY}', 'User-Agent': self.fp.ua},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                data = await r.json()
                if data.get('error'):
                    return None
                return await self._poll(data.get('taskId'))
        except Exception as e:
            logger.error(f'RazorCap: {e}')
            return None
    
    async def _poll(self, task_id, max=60):
        for _ in range(max):
            await asyncio.sleep(2)
            try:
                async with self.session.get(
                    f'https://api.razorcap.cc/solve/result/{task_id}',
                    headers={'Authorization': f'Bearer {RAZORCAP_KEY}'}
                ) as r:
                    data = await r.json()
                    if data.get('status') == 'ready':
                        return data.get('solution', {}).get('token')
            except:
                pass
        return None
    
    async def twocaptcha(self, site_key, page_url):
        key = os.environ.get('2CAPTCHA_API_KEY')
        if not key:
            return None
        try:
            async with self.session.get('http://2captcha.com/in.php', 
                                       params={'key': key, 'method': 'hcaptcha', 'sitekey': site_key, 'pageurl': page_url, 'json': 1}) as r:
                data = await r.json()
                if data.get('status') != 1:
                    return None
                cid = data.get('request')
            
            for _ in range(30):
                await asyncio.sleep(5)
                async with self.session.get('http://2captcha.com/res.php',
                                           params={'key': key, 'action': 'get', 'id': cid, 'json': 1}) as r:
                    data = await r.json()
                    if data.get('status') == 1:
                        return data.get('request')
        except Exception as e:
            logger.error(f'2Captcha: {e}')
        return None
    
    async def browser(self, site_key, page_url):
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                context = await browser.new_context(user_agent=self.fp.ua, viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                await page.goto(page_url, wait_until='networkidle')
                
                try:
                    await page.wait_for_selector('iframe[src*="hcaptcha"]', timeout=10000)
                    for frame in page.frames:
                        if 'hcaptcha' in frame.url:
                            await frame.click('#checkbox', timeout=5000)
                            await asyncio.sleep(5)
                            break
                    token = await page.evaluate('() => document.querySelector(\'textarea[name="h-captcha-response"]\')?.value')
                    await browser.close()
                    if token:
                        return token
                except:
                    pass
                await browser.close()
        except ImportError:
            pass
        except Exception as e:
            logger.error(f'Browser: {e}')
        return None
    
    async def solve(self, site_key, page_url, rqdata=None):
        await self.init()
        
        for method, args in [(self.razorcap, (site_key, page_url, rqdata)), 
                             (self.twocaptcha, (site_key, page_url)),
                             (self.browser, (site_key, page_url))]:
            result = await method(*args)
            if result:
                return result
        
        raise Exception('All solvers failed')

# ─── DISCORD SELFBOT ───
class SelfBot:
    def __init__(self):
        self.token = TOKEN
        self.owner_id = OWNER_ID
        self.fp = Fingerprint()
        self.captcha = CaptchaSolver(self.fp)
        self.ws = None
        self.session_id = None
        self.heartbeat = None
        self.settings = {
            'status': 'stopped',
            'category_id': None,
            'claim_cmd': 'claim',
            'transfer_cmd': None,
            'transfer_id': None
        }
        self.claimed = set()
        self.http = None
        self.running = False
    
    async def update_db_status(self, status):
        try:
            db.execute("UPDATE selfbot_sessions SET status = ?, last_ping = ? WHERE user_id = ?",
                      (status, int(time.time() * 1000), self.owner_id))
            db.commit()
        except Exception as e:
            logger.error(f'DB update failed: {e}')
    
    async def fetch_settings(self):
        try:
            async with self.http.get(f'{API_URL}/settings/{self.owner_id}') as r:
                if r.status == 200:
                    data = await r.json()
                    self.settings.update(data)
                    logger.info(f'Settings updated: {self.settings}')
        except Exception as e:
            logger.debug(f'Fetch settings failed: {e}')
    
    async def start(self):
        await self.captcha.init()
        self.http = aiohttp.ClientSession(headers=self.fp.headers(self.token))
        
        # Verify token works
        me = await self.api('GET', '/users/@me')
        if not me:
            logger.error('Invalid token!')
            await self.update_db_status('error_invalid_token')
            return
        
        logger.info(f'Logged in as {me.get("username")}')
        await self.update_db_status('online')
        self.running = True
        
        await asyncio.gather(
            self.gateway_loop(),
            self.settings_poller(),
            self.ping_updater(),
            self.fingerprint_rotator()
        )
    
    async def api(self, method, endpoint, json=None):
        try:
            url = f'https://discord.com/api/v9{endpoint}'
            async with self.http.request(method, url, json=json) as r:
                if r.status == 204:
                    return {}
                if r.status == 429:
                    retry = int(r.headers.get('Retry-After', 1))
                    logger.warning(f'Rate limited, waiting {retry}s')
                    await asyncio.sleep(retry)
                    return await self.api(method, endpoint, json)
                if r.status >= 400:
                    text = await r.text()
                    logger.error(f'API error {r.status}: {text[:200]}')
                    return None
                return await r.json()
        except Exception as e:
            logger.error(f'API request failed: {e}')
            return None
    
    async def send_message(self, channel_id, content):
        result = await self.api('POST', f'/channels/{channel_id}/messages', {
            'content': content,
            'nonce': str(random.randint(10**18, 10**19 - 1)),
            'tts': False
        })
        return result is not None
    
    async def gateway_loop(self):
        """Main WebSocket connection - THIS IS WHERE LOGIN HAPPENS"""
        while self.running:
            try:
                # ═══ CONNECT TO DISCORD GATEWAY ═══
                async with websockets.connect('wss://gateway.discord.gg/?v=9&encoding=json') as ws:
                    self.ws = ws
                    logger.info('Gateway connected')
                    
                    # ═══ SEND IDENTIFY (LOGIN) ═══
                    await self.identify()
                    
                    async for message in ws:
                        await self.handle_gateway_msg(json.loads(message))
                        
            except Exception as e:
                logger.error(f'Gateway error: {e}')
                await self.update_db_status('reconnecting')
                await asyncio.sleep(5)
    
    async def identify(self):
        """Send identify payload - THIS IS THE LOGIN"""
        await self.ws.send(json.dumps({
            'op': 2,
            'd': {
                'token': self.token,  # <-- TOKEN USED HERE FOR LOGIN
                'properties': {
                    'os': 'Windows',
                    'browser': 'Chrome',
                    'device': '',
                    'system_locale': self.fp.locale,
                    'browser_user_agent': self.fp.ua,
                    'browser_version': '120.0.0.0',
                    'os_version': '10',
                    'referrer': '',
                    'referring_domain': '',
                    'release_channel': 'stable',
                    'client_build_number': 245666
                },
                'presence': {
                    'status': 'online',
                    'since': 0,
                    'activities': [],
                    'afk': False
                },
                'compress': False
            }
        }))
    
    async def handle_gateway_msg(self, msg):
        op = msg.get('op')
        d = msg.get('d', {})
        
        if op == 10:  # Hello
            self.heartbeat = d['heartbeat_interval']
            asyncio.create_task(self.heartbeat_loop())
            
        elif op == 0:  # Dispatch
            t = msg.get('t')
            if t == 'READY':
                self.session_id = d.get('session_id')
                logger.info(f'Session ready: {self.session_id[:8]}...')
                await self.update_db_status('online')
                
                for guild in d.get('guilds', []):
                    logger.info(f'Guild: {guild.get("name")}')
                    
            elif t == 'CHANNEL_CREATE':
                await self.handle_channel_create(d)
    
    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(self.heartbeat / 1000)
            try:
                await self.ws.send(json.dumps({'op': 1, 'd': self.session_id}))
            except:
                break
    
    async def handle_channel_create(self, channel):
        if self.settings.get('status') != 'running':
            return
        if not self.settings.get('category_id'):
            return
        if str(channel.get('parent_id')) != str(self.settings['category_id']):
            return
        if channel['id'] in self.claimed:
            return
        
        logger.info(f'🎫 New ticket: {channel.get("name")}')
        
        delay = random.randint(800, 2500)
        logger.info(f'⏱️ Waiting {delay}ms...')
        await asyncio.sleep(delay / 1000)
        
        if await self.send_message(channel['id'], self.settings['claim_cmd']):
            self.claimed.add(channel['id'])
            logger.info(f'✅ Claimed: {channel["id"]}')
            
            if self.settings.get('transfer_cmd') and self.settings.get('transfer_id'):
                await asyncio.sleep(random.uniform(1, 2))
                transfer_msg = f"{self.settings['transfer_cmd']} {self.settings['transfer_id']}"
                if await self.send_message(channel['id'], transfer_msg):
                    logger.info(f'📤 Transferred to: {self.settings["transfer_id"]}')
        else:
            logger.error(f'❌ Failed to claim: {channel["id"]}')
    
    async def settings_poller(self):
        while self.running:
            await self.fetch_settings()
            await asyncio.sleep(2)
    
    async def ping_updater(self):
        while self.running:
            await self.update_db_status('online')
            await asyncio.sleep(30)
    
    async def fingerprint_rotator(self):
        while self.running:
            await asyncio.sleep(300)
            self.fp.rotate()
            self.http.headers.update(self.fp.headers(self.token))
            logger.info('Fingerprint rotated')

# ═══════════════════════════════════════════════════════
# CLIENT LOGIN / START - THE ACTUAL ENTRY POINT
# ═══════════════════════════════════════════════════════
async def main():
    bot = SelfBot()
    
    # ═══ START THE BOT (CONNECTS AND LOGS IN) ═══
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
