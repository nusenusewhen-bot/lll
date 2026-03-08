import asyncio
import aiohttp
import websockets
import json
import time
import random
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('SelfBot')

# ─── Configuration ───
CONFIG = {
    'token': os.environ.get('SELFBOT_TOKEN'),
    'owner_id': os.environ.get('OWNER_ID', '1479770170389172285'),
    'razorcap_key': os.environ.get('RAZORCAP_API_KEY', '44b5a90f-182f-4c67-b219-ef8dfd33d7a1'),
    'razorcap_url': 'https://api.razorcap.cc/solve',
    'proxies': [p.strip() for p in os.environ.get('PROXIES', '').split(',') if p.strip()],
    'bot_api_url': os.environ.get('BOT_API_URL', 'http://localhost:8080'),
    'claim_delay_min': 800,
    'claim_delay_max': 2500,
    'api_version': '9',
    'gateway_version': '9'
}

# ─── Proxy Rotator ───
class ProxyRotator:
    def __init__(self):
        self.proxies = CONFIG['proxies']
        self.current = 0
        self.working = []
        
    async def test_proxy(self, proxy: str) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    'https://discord.com/api/v9/users/@me',
                    proxy=proxy,
                    headers={'Authorization': CONFIG['token']}
                ) as resp:
                    return resp.status == 200
        except:
            return False
    
    async def get_working_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        if not self.working:
            for p in self.proxies:
                if await self.test_proxy(p):
                    self.working.append(p)
        if not self.working:
            return None
        proxy = self.working[self.current % len(self.working)]
        self.current += 1
        return proxy

# ─── Fingerprint Generator ───
class Fingerprint:
    def __init__(self):
        self.browsers = ['Chrome/120.0.0.0', 'Firefox/121.0', 'Safari/605.1.15']
        self.systems = ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7']
        self.locales = ['en-US', 'en-GB', 'de-DE']
        self.timezones = ['America/New_York', 'Europe/London', 'Asia/Tokyo']
        self.rotate()
        
    def rotate(self):
        self.ua = f"Mozilla/5.0 ({random.choice(self.systems)}) AppleWebKit/537.36 (KHTML, like Gecko) {random.choice(self.browsers)}"
        self.locale = random.choice(self.locales)
        self.timezone = random.choice(self.timezones)
        self.super_properties = self._encode_super_props()
        
    def _encode_super_props(self) -> str:
        import base64
        props = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": self.locale,
            "browser_user_agent": self.ua,
            "browser_version": "120.0.0.0",
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": random.randint(240000, 250000),
            "client_event_source": None
        }
        return base64.b64encode(json.dumps(props).encode()).decode()
    
    def get_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Accept-Language': f'{self.locale},en;q=0.9',
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
            'X-Discord-Locale': self.locale,
            'X-Discord-Timezone': self.timezone,
            'X-Super-Properties': self.super_properties
        }

# ─── CAPTCHA Solver ───
class CaptchaSolver:
    def __init__(self, proxy_rotator: ProxyRotator, fingerprint: Fingerprint):
        self.proxy_rotator = proxy_rotator
        self.fp = fingerprint
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def init(self):
        self.session = aiohttp.ClientSession()
    
    async def solve_razorcap(self, site_key: str, page_url: str, captcha_type: str = 'hcaptcha_enterprise', rqdata: Optional[str] = None) -> Optional[str]:
        try:
            proxy = await self.proxy_rotator.get_working_proxy()
            payload = {
                'type': captcha_type,
                'websiteURL': page_url,
                'websiteKey': site_key,
                'rqdata': rqdata,
                'proxy': proxy
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {CONFIG["razorcap_key"]}',
                'User-Agent': self.fp.ua
            }
            
            logger.info('Sending to RazorCap...')
            async with self.session.post(CONFIG['razorcap_url'], json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                if data.get('error'):
                    return None
                return await self._poll_razorcap(data.get('taskId'), proxy)
        except Exception as e:
            logger.error(f'RazorCap error: {e}')
            return None
    
    async def _poll_razorcap(self, task_id: str, proxy: Optional[str], max_attempts: int = 60) -> Optional[str]:
        for _ in range(max_attempts):
            await asyncio.sleep(2)
            try:
                headers = {'Authorization': f'Bearer {CONFIG["razorcap_key"]}'}
                async with self.session.get(f'{CONFIG["razorcap_url"]}/result/{task_id}', headers=headers) as resp:
                    data = await resp.json()
                    if data.get('status') == 'ready':
                        return data.get('solution', {}).get('token') or data.get('solution')
            except:
                pass
        return None
    
    async def solve_2captcha(self, site_key: str, page_url: str) -> Optional[str]:
        api_key = os.environ.get('2CAPTCHA_API_KEY')
        if not api_key:
            return None
        try:
            async with self.session.get('http://2captcha.com/in.php', params={
                'key': api_key, 'method': 'hcaptcha', 'sitekey': site_key, 'pageurl': page_url, 'json': 1
            }) as resp:
                data = await resp.json()
                if data.get('status') != 1:
                    return None
                captcha_id = data.get('request')
            
            for _ in range(30):
                await asyncio.sleep(5)
                async with self.session.get('http://2captcha.com/res.php', params={
                    'key': api_key, 'action': 'get', 'id': captcha_id, 'json': 1
                }) as resp:
                    data = await resp.json()
                    if data.get('status') == 1:
                        return data.get('request')
        except Exception as e:
            logger.error(f'2Captcha error: {e}')
        return None
    
    async def solve_browser(self, site_key: str, page_url: str) -> Optional[str]:
        """Free backup using Playwright browser automation"""
        try:
            from playwright.async_api import async_playwright
            proxy = await self.proxy_rotator.get_working_proxy()
            
            async with async_playwright() as p:
                args = ['--no-sandbox', '--disable-setuid-sandbox']
                if proxy:
                    args.append(f'--proxy-server={proxy}')
                
                browser = await p.chromium.launch(headless=True, args=args)
                context = await browser.new_context(
                    user_agent=self.fp.ua,
                    viewport={'width': 1920, 'height': 1080},
                    locale=self.fp.locale,
                    timezone_id=self.fp.timezone
                )
                
                page = await context.new_page()
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    window.chrome = { runtime: {} };
                """)
                
                await page.goto(page_url, wait_until='networkidle')
                
                try:
                    await page.wait_for_selector('iframe[src*="hcaptcha"]', timeout=10000)
                    frames = page.frames
                    hcaptcha_frame = next((f for f in frames if 'hcaptcha' in f.url), None)
                    if hcaptcha_frame:
                        await hcaptcha_frame.click('#checkbox', timeout=5000)
                        await asyncio.sleep(5)
                    
                    token = await page.evaluate('''() => document.querySelector('textarea[name="h-captcha-response"]')?.value''')
                    await browser.close()
                    if token:
                        logger.info('Browser solve success')
                        return token
                except:
                    pass
                await browser.close()
        except ImportError:
            logger.debug('Playwright not installed')
        except Exception as e:
            logger.error(f'Browser error: {e}')
        return None
    
    async def solve(self, site_key: str, page_url: str, captcha_type: str = 'hcaptcha_enterprise', rqdata: Optional[str] = None) -> str:
        await self.init()
        
        result = await self.solve_razorcap(site_key, page_url, captcha_type, rqdata)
        if result:
            return result
            
        result = await self.solve_2captcha(site_key, page_url)
        if result:
            return result
            
        result = await self.solve_browser(site_key, page_url)
        if result:
            return result
            
        raise Exception('All solvers failed')

# ─── Discord SelfBot Client ───
class DiscordSelfBot:
    def __init__(self):
        self.token = CONFIG['token']
        self.proxy_rotator = ProxyRotator()
        self.fp = Fingerprint()
        self.captcha = CaptchaSolver(self.proxy_rotator, self.fp)
        self.ws = None
        self.session_id = None
        self.heartbeat_interval = None
        self.gateway_url = 'wss://gateway.discord.gg/?v=9&encoding=json'
        self.settings = {
            'status': 'stopped',
            'category_id': None,
            'claim_cmd': 'claim',
            'transfer_cmd': None,
            'transfer_id': None
        }
        self.claimed = set()
        self.guilds = {}
        self.channels = {}
        self.http_session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        if not self.token:
            logger.error('SELFBOT_TOKEN not set!')
            return
            
        await self.captcha.init()
        self.http_session = aiohttp.ClientSession(headers={
            'Authorization': self.token,
            **self.fp.get_headers()
        })
        
        # Test token
        me = await self.api_request('GET', '/users/@me')
        if not me:
            logger.error('Invalid token or account banned')
            return
            
        logger.info(f'Starting selfbot as {me.get("username")}#{me.get("discriminator")}')
        
        # Start gateway connection
        await self.connect_gateway()
        
    async def api_request(self, method: str, endpoint: str, json_data: dict = None) -> Optional[dict]:
        try:
            url = f'https://discord.com/api/v9{endpoint}'
            async with self.http_session.request(method, url, json=json_data) as resp:
                if resp.status == 204:
                    return {}
                if resp.status == 429:
                    retry = int(resp.headers.get('Retry-After', 1))
                    logger.warning(f'Rate limited, waiting {retry}s')
                    await asyncio.sleep(retry)
                    return await self.api_request(method, endpoint, json_data)
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(f'API error {resp.status}: {text}')
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f'Request error: {e}')
            return None
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        result = await self.api_request('POST', f'/channels/{channel_id}/messages', {
            'content': content,
            'nonce': str(random.randint(1000000000000000000, 9999999999999999999)),
            'tts': False
        })
        return result is not None
    
    async def connect_gateway(self):
        """Connect to Discord Gateway WebSocket"""
        while True:
            try:
                proxy = await self.proxy_rotator.get_working_proxy()
                connector = None
                if proxy:
                    from aiohttp_socks import ProxyConnector
                    connector = ProxyConnector.from_url(proxy)
                
                async with websockets.connect(self.gateway_url, ping_interval=None, ping_timeout=None) as ws:
                    self.ws = ws
                    logger.info('Gateway connected')
                    
                    # Identify
                    await self.identify()
                    
                    # Message handler
                    async for message in ws:
                        await self.handle_gateway_msg(json.loads(message))
                        
            except Exception as e:
                logger.error(f'Gateway error: {e}')
                await asyncio.sleep(5)
    
    async def identify(self):
        """Send identify payload"""
        payload = {
            'op': 2,
            'd': {
                'token': self.token,
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
                    'referrer_current': '',
                    'referring_domain_current': '',
                    'release_channel': 'stable',
                    'client_build_number': 245666,
                    'client_event_source': None
                },
                'presence': {
                    'status': 'online',
                    'since': 0,
                    'activities': [],
                    'afk': False
                },
                'compress': False,
                'client_state': {
                    'guild_versions': {},
                    'highest_last_message_id': '0',
                    'read_state_version': 0,
                    'user_guild_settings_version': -1,
                    'user_settings_version': -1,
                    'private_channels_version': '0',
                    'api_code_version': 0
                }
            }
        }
        await self.ws.send(json.dumps(payload))
    
    async def handle_gateway_msg(self, msg: dict):
        op = msg.get('op')
        d = msg.get('d', {})
        
        if op == 10:  # Hello
            self.heartbeat_interval = d['heartbeat_interval']
            asyncio.create_task(self.heartbeat_loop())
            logger.info(f'Heartbeat interval: {self.heartbeat_interval}')
            
        elif op == 0:  # Dispatch
            t = msg.get('t')
            
            if t == 'READY':
                self.session_id = d.get('session_id')
                logger.info(f'Session ready: {self.session_id}')
                # Update guilds/channels cache
                for guild in d.get('guilds', []):
                    self.guilds[guild['id']] = guild
                    
            elif t == 'GUILD_CREATE':
                self.guilds[d['id']] = d
                
            elif t == 'CHANNEL_CREATE':
                await self.handle_channel_create(d)
                
            elif t == 'MESSAGE_CREATE':
                # Could handle claim confirmations here
                pass
    
    async def heartbeat_loop(self):
        """Send heartbeat every interval"""
        while True:
            await asyncio.sleep(self.heartbeat_interval / 1000)
            try:
                await self.ws.send(json.dumps({'op': 1, 'd': self.session_id}))
            except:
                break
    
    async def handle_channel_create(self, channel: dict):
        """Handle new channel (ticket) creation"""
        if self.settings['status'] != 'running':
            return
        if not self.settings['category_id']:
            return
        if channel.get('parent_id') != self.settings['category_id']:
            return
        if channel['id'] in self.claimed:
            return
            
        logger.info(f'New ticket: {channel.get("name")} ({channel["id"]})')
        
        # Random delay
        delay = random.randint(CONFIG['claim_delay_min'], CONFIG['claim_delay_max'])
        logger.info(f'Waiting {delay}ms...')
        await asyncio.sleep(delay / 1000)
        
        # Send claim command
        if await self.send_message(channel['id'], self.settings['claim_cmd']):
            self.claimed.add(channel['id'])
            logger.info(f'Claimed: {channel["id"]}')
            
            # Transfer if configured
            if self.settings['transfer_cmd'] and self.settings['transfer_id']:
                await asyncio.sleep(random.uniform(1, 2))
                transfer_msg = f'{self.settings["transfer_cmd"]} {self.settings["transfer_id"]}'
                if await self.send_message(channel['id'], transfer_msg):
                    logger.info(f'Transferred to: {self.settings["transfer_id"]}')
        else:
            logger.error(f'Failed to claim: {channel["id"]}')
    
    async def poll_settings(self):
        """Poll main bot for settings"""
        while True:
            try:
                async with self.http_session.get(f'{CONFIG["bot_api_url"]}/settings/{self.token.split(".")[0]}') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.settings.update(data)
                        logger.debug(f'Settings updated: {self.settings}')
            except:
                pass
            await asyncio.sleep(2)
    
    async def rotate_fingerprint(self):
        """Rotate fingerprint periodically"""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            self.fp.rotate()
            self.http_session.headers.update(self.fp.get_headers())
            logger.info('Fingerprint rotated')

def main():
    bot = DiscordSelfBot()
    
    async def run():
        await asyncio.gather(
            bot.start(),
            bot.poll_settings(),
            bot.rotate_fingerprint()
        )
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info('Shutting down...')

if __name__ == '__main__':
    main()
