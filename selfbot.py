import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import time
import random
import string
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
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
    'fingerprint_rotation': 300000,  # 5 minutes
    'claim_delay_min': 800,
    'claim_delay_max': 2500,
    'captcha_timeout': 120,
    'max_retries': 3
}

# ─── Proxy Rotator ───
class ProxyRotator:
    def __init__(self):
        self.proxies = CONFIG['proxies']
        self.current = 0
        self.working = []
        self.tested = False
        
    async def test_proxy(self, proxy: str) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(
                    'https://discord.com/api/v9/users/@me',
                    proxy=proxy,
                    headers={'Authorization': CONFIG['token']}
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.debug(f"Proxy {proxy} failed: {e}")
            return False
    
    async def get_working_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
            
        if not self.tested:
            logger.info("Testing proxies...")
            tasks = [self.test_proxy(p) for p in self.proxies]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for proxy, working in zip(self.proxies, results):
                if working is True:
                    self.working.append(proxy)
            self.tested = True
            logger.info(f"Found {len(self.working)} working proxies")
        
        if not self.working:
            return None
            
        proxy = self.working[self.current % len(self.working)]
        self.current += 1
        return proxy

# ─── Fingerprint Evasion ───
class Fingerprint:
    def __init__(self):
        self.browsers = [
            'Chrome/120.0.0.0 Safari/537.36',
            'Firefox/121.0',
            'Edg/120.0.0.0'
        ]
        self.systems = [
            'Windows NT 10.0; Win64; x64',
            'Macintosh; Intel Mac OS X 10_15_7',
            'X11; Linux x86_64'
        ]
        self.locales = ['en-US', 'en-GB', 'fr-FR', 'de-DE']
        self.timezones = ['America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney']
        self.rotate()
        
    def rotate(self):
        self.ua = f"Mozilla/5.0 ({random.choice(self.systems)}) AppleWebKit/537.36 (KHTML, like Gecko) {random.choice(self.browsers)}"
        self.locale = random.choice(self.locales)
        self.timezone = random.choice(self.timezones)
        self.screen = f"{random.randint(1920, 2560)}x{random.randint(1080, 1440)}"
        self.color_depth = random.choice([24, 32])
        self.memory = random.choice([4, 8, 16, 32])
        self.cores = random.choice([4, 6, 8, 12, 16])
        
        # Generate Discord super properties
        self.super_properties = self._generate_super_properties()
        
    def _generate_super_properties(self) -> str:
        props = {
            "os": sys.platform,
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
            "client_event_source": None,
            "design_id": 0
        }
        import base64
        return base64.b64encode(json.dumps(props).encode()).decode()
    
    def get_headers(self, auth_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Accept-Language': f'{self.locale},en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://discord.com/',
            'Origin': 'https://discord.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Debug-Options': 'bugReporterEnabled',
            'X-Discord-Locale': self.locale,
            'X-Discord-Timezone': self.timezone,
            'X-Super-Properties': self.super_properties,
            'X-Track': 'eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMC4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIwLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjI0NTY2NiwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0='
        }
        if auth_token:
            headers['Authorization'] = auth_token
        return headers

# ─── CAPTCHA Solver ───
class CaptchaSolver:
    def __init__(self, proxy_rotator: ProxyRotator, fingerprint: Fingerprint):
        self.proxy_rotator = proxy_rotator
        self.fp = fingerprint
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def solve_razorcap(self, site_key: str, page_url: str, captcha_type: str = 'hcaptcha_enterprise', rqdata: Optional[str] = None) -> Optional[str]:
        """Primary solver: RazorCap API"""
        try:
            await self.init_session()
            
            proxy = await self.proxy_rotator.get_working_proxy()
            
            payload = {
                'type': captcha_type,
                'websiteURL': page_url,
                'websiteKey': site_key,
                'rqdata': rqdata,
                'proxy': proxy
            }
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {CONFIG["razorcap_key"]}',
                'User-Agent': self.fp.ua
            }
            
            logger.info(f'Sending CAPTCHA to RazorCap: {captcha_type}')
            
            async with self.session.post(
                CONFIG['razorcap_url'],
                json=payload,
                headers=headers,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                
                if data.get('error'):
                    logger.error(f"RazorCap API error: {data['error']}")
                    return None
                    
                task_id = data.get('taskId')
                if not task_id:
                    logger.error("No taskId in RazorCap response")
                    return None
                    
                return await self._poll_razorcap(task_id, proxy)
                
        except Exception as e:
            logger.error(f'RazorCap failed: {e}')
            return None
    
    async def _poll_razorcap(self, task_id: str, proxy: Optional[str], max_attempts: int = 60) -> Optional[str]:
        """Poll for RazorCap result"""
        for i in range(max_attempts):
            try:
                await asyncio.sleep(2)
                
                headers = {
                    'Authorization': f'Bearer {CONFIG["razorcap_key"]}',
                    'User-Agent': self.fp.ua
                }
                
                async with self.session.get(
                    f'{CONFIG["razorcap_url"]}/result/{task_id}',
                    headers=headers,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    
                    if data.get('status') == 'ready':
                        token = data.get('solution', {}).get('token') or data.get('solution')
                        if token:
                            logger.info('RazorCap solved successfully')
                            return token
                            
            except Exception as e:
                logger.debug(f'Poll error: {e}')
                
        logger.error('RazorCap polling timeout')
        return None
    
    async def solve_2captcha(self, site_key: str, page_url: str) -> Optional[str]:
        """Backup #1: 2Captcha (if API key provided)"""
        api_key = os.environ.get('2CAPTCHA_API_KEY')
        if not api_key:
            return None
            
        try:
            # Submit CAPTCHA
            submit_url = 'http://2captcha.com/in.php'
            params = {
                'key': api_key,
                'method': 'hcaptcha',
                'sitekey': site_key,
                'pageurl': page_url,
                'json': 1
            }
            
            async with self.session.get(submit_url, params=params) as resp:
                data = await resp.json()
                if data.get('status') != 1:
                    return None
                captcha_id = data.get('request')
            
            # Poll for result
            result_url = 'http://2captcha.com/res.php'
            for _ in range(30):
                await asyncio.sleep(5)
                params = {
                    'key': api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                async with self.session.get(result_url, params=params) as resp:
                    data = await resp.json()
                    if data.get('status') == 1:
                        return data.get('request')
                        
        except Exception as e:
            logger.error(f'2Captcha failed: {e}')
        return None
    
    async def solve_browser(self, site_key: str, page_url: str) -> Optional[str]:
        """Backup #2: Browser automation using Playwright/Selenium"""
        # This requires playwright: pip install playwright
        # And: playwright install chromium
        
        try:
            from playwright.async_api import async_playwright
            
            proxy = await self.proxy_rotator.get_working_proxy()
            
            async with async_playwright() as p:
                browser_args = ['--no-sandbox', '--disable-setuid-sandbox']
                if proxy:
                    browser_args.append(f'--proxy-server={proxy}')
                
                browser = await p.chromium.launch(headless=True, args=browser_args)
                context = await browser.new_context(
                    user_agent=self.fp.ua,
                    viewport={'width': 1920, 'height': 1080},
                    locale=self.fp.locale,
                    timezone_id=self.fp.timezone
                )
                
                page = await context.new_page()
                
                # Inject fingerprint evasion scripts
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    window.chrome = { runtime: {} };
                """)
                
                await page.goto(page_url, wait_until='networkidle')
                
                # Wait for hCaptcha iframe
                try:
                    await page.wait_for_selector('iframe[src*="hcaptcha"]', timeout=10000)
                    
                    # Try to click checkbox
                    frames = page.frames
                    hcaptcha_frame = None
                    for frame in frames:
                        if 'hcaptcha' in frame.url:
                            hcaptcha_frame = frame
                            break
                    
                    if hcaptcha_frame:
                        await hcaptcha_frame.click('#checkbox', timeout=5000)
                        await asyncio.sleep(5)
                    
                    # Extract token
                    token = await page.evaluate('''() => {
                        const el = document.querySelector('textarea[name="h-captcha-response"]');
                        return el ? el.value : null;
                    }''')
                    
                    await browser.close()
                    
                    if token:
                        logger.info('Browser automation solved CAPTCHA')
                        return token
                        
                except Exception as e:
                    logger.debug(f'Browser solve error: {e}')
                    
                await browser.close()
                
        except ImportError:
            logger.debug('Playwright not installed, skipping browser backup')
        except Exception as e:
            logger.error(f'Browser backup failed: {e}')
            
        return None
    
    async def solve(self, site_key: str, page_url: str, captcha_type: str = 'hcaptcha_enterprise', rqdata: Optional[str] = None) -> str:
        """
        Master solve method - tries all solvers in order:
        1. RazorCap (primary)
        2. 2Captcha (backup #1)
        3. Browser automation (backup #2 - free)
        """
        await self.init_session()
        
        # Try RazorCap first
        logger.info('Attempting RazorCap...')
        result = await self.solve_razorcap(site_key, page_url, captcha_type, rqdata)
        if result:
            return result
            
        # Try 2Captcha
        logger.info('Attempting 2Captcha backup...')
        result = await self.solve_2captcha(site_key, page_url)
        if result:
            return result
            
        # Try browser automation (free)
        logger.info('Attempting browser automation backup...')
        result = await self.solve_browser(site_key, page_url)
        if result:
            return result
            
        raise Exception('All CAPTCHA solvers failed')

# ─── SelfBot Client ───
class SelfBot(commands.Bot):
    def __init__(self):
        # Use discord.py-selfbot (install: pip install discord.py-selfbot)
        super().__init__(
            command_prefix='!',
            self_bot=True,
            help_command=None
        )
        
        self.proxy_rotator = ProxyRotator()
        self.fingerprint = Fingerprint()
        self.captcha_solver = CaptchaSolver(self.proxy_rotator, self.fingerprint)
        self.settings = {
            'status': 'stopped',
            'category_id': None,
            'claim_cmd': 'claim',
            'transfer_cmd': None,
            'transfer_id': None
        }
        self.claimed_tickets = set()
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rotate fingerprint every 5 minutes
        self.fp_rotation.start()
        
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        await self.proxy_rotator.get_working_proxy()  # Test proxies on startup
        
    @tasks.loop(seconds=300)
    async def fp_rotation(self):
        self.fingerprint.rotate()
        logger.info('Rotated browser fingerprint')
        
    async def on_ready(self):
        logger.info(f'SelfBot logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'Fingerprint: {self.fingerprint.ua[:50]}...')
        
        # Start polling for settings
        self.settings_poller.start()
        
        # Anti-detection: random status changes
        self.status_changer.start()
        
    @tasks.loop(seconds=10)
    async def settings_poller(self):
        """Poll main bot for settings updates"""
        try:
            async with self.session.get(
                f'{CONFIG["bot_api_url"]}/settings/{self.user.id}',
                headers=self.fingerprint.get_headers(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.settings.update(data)
        except Exception as e:
            pass  # Bot API might be down
            
    @tasks.loop(minutes=5)
    async def status_changer(self):
        """Random status to avoid detection"""
        statuses = [discord.Status.online, discord.Status.idle, discord.Status.dnd]
        activities = [
            discord.Activity(type=discord.ActivityType.playing, name="Games"),
            discord.Activity(type=discord.ActivityType.listening, name="Spotify"),
            discord.Activity(type=discord.ActivityType.watching, name="YouTube")
        ]
        await self.change_presence(
            status=random.choice(statuses),
            activity=random.choice(activities)
        )
        
    async def on_message(self, message):
        # Skip own messages
        if message.author.id == self.user.id:
            return
            
        await self.process_commands(message)
        
        # Check if this is a new ticket in target category
        if not isinstance(message.channel, discord.TextChannel):
            return
            
        await self.check_ticket(message.channel)
        
    async def check_ticket(self, channel: discord.TextChannel):
        """Check if channel is a ticket to claim"""
        if self.settings['status'] != 'running':
            return
        if not self.settings['category_id']:
            return
        if str(channel.category_id) != str(self.settings['category_id']):
            return
        if channel.id in self.claimed_tickets:
            return
            
        logger.info(f'New ticket detected: {channel.name} ({channel.id})')
        
        # Random delay to seem human
        delay = random.randint(CONFIG['claim_delay_min'], CONFIG['claim_delay_max'])
        logger.info(f'Waiting {delay}ms before claiming...')
        await asyncio.sleep(delay / 1000)
        
        try:
            # Send typing indicator
            async with channel.typing():
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Send claim command
            claim_msg = await channel.send(self.settings['claim_cmd'])
            self.claimed_tickets.add(channel.id)
            logger.info(f'Claimed ticket {channel.id}')
            
            # Transfer if configured
            if self.settings['transfer_cmd'] and self.settings['transfer_id']:
                await asyncio.sleep(random.uniform(1, 2))
                transfer_msg = f"{self.settings['transfer_cmd']} {self.settings['transfer_id']}"
                await channel.send(transfer_msg)
                logger.info(f'Transferred ticket to {self.settings["transfer_id"]}')
                
        except discord.Forbidden:
            logger.error(f'Forbidden to send in {channel.id}')
        except discord.HTTPException as e:
            if 'captcha' in str(e).lower():
                logger.warning('CAPTCHA detected during message send')
                # Note: Handling CAPTCHA on message send requires solving and retrying
                # This is simplified - full implementation would catch the captcha sitekey
            else:
                logger.error(f'HTTP error: {e}')
                
    async def on_guild_channel_create(self, channel):
        """Alternative: Catch channel creation event directly"""
        if isinstance(channel, discord.TextChannel):
            await self.check_ticket(channel)
            
    async def handle_login_captcha(self, error_data: dict) -> bool:
        """Handle CAPTCHA challenge during login"""
        try:
            logger.info('Login CAPTCHA detected, solving...')
            
            # Extract CAPTCHA data from error
            site_key = error_data.get('captcha_sitekey', 'f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34')
            rqdata = error_data.get('captcha_rqdata')
            
            solution = await self.captcha_solver.solve(
                site_key=site_key,
                page_url='https://discord.com/login',
                captcha_type='hcaptcha_enterprise',
                rqdata=rqdata
            )
            
            if solution:
                logger.info('CAPTCHA solved, retrying login...')
                # Note: Actually using the solution requires modifying the login payload
                # This would need to be integrated with the discord.py login flow
                return True
                
        except Exception as e:
            logger.error(f'CAPTCHA handling failed: {e}')
            
        return False
        
    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

# ─── Run ───
def main():
    if not CONFIG['token']:
        logger.error('SELFBOT_TOKEN not set!')
        return
        
    bot = SelfBot()
    
    try:
        bot.run(CONFIG['token'], reconnect=True)
    except discord.LoginFailure as e:
        if 'captcha' in str(e).lower():
            logger.error('Login blocked by CAPTCHA - manual solve required or use pre-solved token')
            # In a full implementation, you'd catch the captcha data here and solve it
        else:
            raise

if __name__ == '__main__':
    main()
