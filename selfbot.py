# ═══════════════════════════════════════════════════════
# HEALTH SERVER STARTS FIRST (SYNCHRONOUS, ZERO DELAY)
# ═══════════════════════════════════════════════════════
import os
import sys
import socketserver
import http.server
import threading
import time

PORT = int(os.environ.get('PORT', 8080))

class InstantHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Silent

# Start server in background thread immediately
def boot_health():
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(('0.0.0.0', PORT), InstantHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f'[HEALTH] Server active on port {PORT}', flush=True)
        return True
    except Exception as e:
        print(f'[HEALTH] Failed: {e}', flush=True)
        return False

# BOOT HEALTH SERVER NOW
if not boot_health():
    sys.exit(1)

# Wait a moment to ensure binding
time.sleep(0.5)

# ═══════════════════════════════════════════════════════
# NOW LOAD REST OF APP
# ═══════════════════════════════════════════════════════
import asyncio
import json
import random
import base64
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SelfBot')

# Config
CONFIG = {
    'token': os.environ.get('SELFBOT_TOKEN'),
    'razorcap_key': os.environ.get('RAZORCAP_API_KEY', '44b5a90f-182f-4c67-b219-ef8dfd33d7a1'),
    'proxies': [p.strip() for p in os.environ.get('PROXIES', '').split(',') if p.strip()],
}

# Check token exists
if not CONFIG['token']:
    logger.error('SELFBOT_TOKEN not set!')
    # Keep health server alive anyway
    while True:
        time.sleep(60)

# Imports
try:
    import aiohttp
    import websockets
except ImportError as e:
    logger.error(f'Missing: {e}')
    while True:
        time.sleep(60)

# Proxy rotator
class ProxyRotator:
    def __init__(self):
        self.proxies = CONFIG['proxies']
        self.working = []
        self.idx = 0
    
    async def get(self):
        if not self.proxies:
            return None
        if not self.working:
            for p in self.proxies:
                try:
                    timeout = aiohttp.ClientTimeout(total=5)
                    async with aiohttp.ClientSession(timeout=timeout) as s:
                        async with s.get('https://discord.com/api/v9/users/@me', proxy=p, 
                                       headers={'Authorization': CONFIG['token']}) as r:
                            if r.status == 200:
                                self.working.append(p)
                except:
                    pass
        if not self.working:
            return None
        p = self.working[self.idx % len(self.working)]
        self.idx += 1
        return p

# Fingerprint
class Fingerprint:
    def __init__(self):
        self.rotate()
    
    def rotate(self):
        self.ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(120,125)}.0.0.0 Safari/537.36"
        self.locale = random.choice(['en-US', 'en-GB'])
        props = {"os": "Windows", "browser": "Chrome", "device": "", 
                "system_locale": self.locale, "browser_user_agent": self.ua,
                "browser_version": "120.0.0.0", "os_version": "10",
                "release_channel": "stable", "client_build_number": random.randint(240000,250000)}
        self.super = base64.b64encode(json.dumps(props).encode()).decode()
    
    def headers(self, auth=None):
        h = {'User-Agent': self.ua, 'Accept': '*/*', 'Accept-Language': f'{self.locale},en;q=0.9',
             'Accept-Encoding': 'gzip, deflate, br', 'Referer': 'https://discord.com/', 'Origin': 'https://discord.com',
             'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"', 'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"',
             'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
             'X-Debug-Options': 'bugReporterEnabled', 'X-Discord-Locale': self.locale,
             'X-Super-Properties': self.super}
        if auth:
            h['Authorization'] = auth
        return h

# CAPTCHA Solver
class CaptchaSolver:
    def __init__(self, proxy, fp):
        self.proxy = proxy
        self.fp = fp
        self.session = None
    
    async def init(self):
        self.session = aiohttp.ClientSession()
    
    async def razorcap(self, site_key, page_url, rqdata=None):
        try:
            proxy = await self.proxy.get()
            payload = {'type': 'hcaptcha_enterprise', 'websiteURL': page_url, 'websiteKey': site_key, 'rqdata': rqdata, 'proxy': proxy}
            payload = {k: v for k, v in payload.items() if v}
            
            async with self.session.post('https://api.razorcap.cc/solve', 
                                        json=payload,
                                        headers={'Authorization': f'Bearer {CONFIG["razorcap_key"]}', 'User-Agent': self.fp.ua},
                                        timeout=aiohttp.ClientTimeout(total=30)) as r:
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
                async with self.session.get(f'https://api.razorcap.cc/solve/result/{task_id}',
                                          headers={'Authorization': f'Bearer {CONFIG["razorcap_key"]}'}) as r:
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
            proxy = await self.proxy.get()
            args = ['--no-sandbox', '--disable-setuid-sandbox']
            if proxy:
                args.append(f'--proxy-server={proxy}')
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=args)
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
        
        result = await self.razorcap(site_key, page_url, rqdata)
        if result:
            return result
            
        result = await self.twocaptcha(site_key, page_url)
        if result:
            return result
            
        result = await self.browser(site_key, page_url)
        if result:
            return result
        
        raise Exception('All solvers failed')

# Discord SelfBot
class SelfBot:
    def __init__(self):
        self.token = CONFIG['token']
        self.proxy = ProxyRotator()
        self.fp = Fingerprint()
        self.captcha = CaptchaSolver(self.proxy, self.fp)
        self.ws = None
        self.session_id = None
        self.heartbeat = None
        self.settings = {'status': 'stopped', 'category_id': None, 'claim_cmd': 'claim', 'transfer_cmd': None, 'transfer_id': None}
        self.claimed = set()
        self.http = None
        self.running = False
    
    async def start(self):
        await self.captcha.init()
        self.http = aiohttp.ClientSession(headers=self.fp.headers(self.token))
        
        me = await self.api('GET', '/users/@me')
        if not me:
            logger.error('Invalid token')
            return
        
        logger.info(f'Logged in as {me.get("username")}')
        self.running = True
        
        await asyncio.gather(self.gateway(), self.poll_settings(), self.rotate_fp())
    
    async def api(self, method, endpoint, json=None):
        try:
            url = f'https://discord.com/api/v9{endpoint}'
            async with self.http.request(method, url, json=json) as r:
                if r.status == 204:
                    return {}
                if r.status == 429:
                    await asyncio.sleep(int(r.headers.get('Retry-After', 1)))
                    return await self.api(method, endpoint, json)
                if r.status >= 400:
                    return None
                return await r.json()
        except Exception as e:
            logger.error(f'API: {e}')
            return None
    
    async def send(self, channel_id, content):
        return await self.api('POST', f'/channels/{channel_id}/messages', {
            'content': content, 'nonce': str(random.randint(10**18, 10**19-1)), 'tts': False
        })
    
    async def gateway(self):
        while self.running:
            try:
                async with websockets.connect('wss://gateway.discord.gg/?v=9&encoding=json') as ws:
                    self.ws = ws
                    await self.identify()
                    
                    async for msg in ws:
                        await self.handle(json.loads(msg))
            except Exception as e:
                logger.error(f'Gateway: {e}')
                await asyncio.sleep(5)
    
    async def identify(self):
        await self.ws.send(json.dumps({
            'op': 2, 'd': {
                'token': self.token,
                'properties': {'os': 'Windows', 'browser': 'Chrome', 'device': '', 'system_locale': self.fp.locale,
                              'browser_user_agent': self.fp.ua, 'browser_version': '120.0.0.0', 'os_version': '10',
                              'release_channel': 'stable', 'client_build_number': 245666},
                'presence': {'status': 'online', 'since': 0, 'activities': [], 'afk': False},
                'compress': False
            }
        }))
    
    async def handle(self, msg):
        op = msg.get('op')
        d = msg.get('d', {})
        
        if op == 10:
            self.heartbeat = d['heartbeat_interval']
            asyncio.create_task(self.beat())
        
        elif op == 0:
            t = msg.get('t')
            if t == 'READY':
                self.session_id = d.get('session_id')
            elif t == 'CHANNEL_CREATE':
                await self.on_channel(d)
    
    async def beat(self):
        while True:
            await asyncio.sleep(self.heartbeat / 1000)
            try:
                await self.ws.send(json.dumps({'op': 1, 'd': self.session_id}))
            except:
                break
    
    async def on_channel(self, ch):
        if self.settings['status'] != 'running':
            return
        if not self.settings['category_id'] or str(ch.get('parent_id')) != str(self.settings['category_id']):
            return
        if ch['id'] in self.claimed:
            return
        
        logger.info(f'New ticket: {ch.get("name")}')
        await asyncio.sleep(random.randint(800, 2500) / 1000)
        
        if await self.send(ch['id'], self.settings['claim_cmd']):
            self.claimed.add(ch['id'])
            logger.info(f'Claimed {ch["id"]}')
            
            if self.settings['transfer_cmd'] and self.settings['transfer_id']:
                await asyncio.sleep(random.uniform(1, 2))
                await self.send(ch['id'], f'{self.settings["transfer_cmd"]} {self.settings["transfer_id"]}')
    
    async def poll_settings(self):
        while self.running:
            try:
                async with self.http.get(f'{os.environ.get("BOT_API_URL", "http://localhost:8080")}/settings/{self.token.split(".")[0]}') as r:
                    if r.status == 200:
                        self.settings.update(await r.json())
            except:
                pass
            await asyncio.sleep(2)
    
    async def rotate_fp(self):
        while self.running:
            await asyncio.sleep(300)
            self.fp.rotate()
            self.http.headers.update(self.fp.headers(self.token))

# Main
async def main():
    bot = SelfBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
