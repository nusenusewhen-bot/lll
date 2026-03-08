import requests
import time
import os
from PIL import Image
import pytesseract
import base64
import json

RAZORCAP_KEY = os.getenv("RAZORCAP_API_KEY", "44b5a90f-182f-4c67-b219-ef8dfd33d7a1")
RAZORCAP_URL = "https://api.razorcap.cc/solve"

class CaptchaSolver:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
    def solve_razorcap(self, site_key, page_url, captcha_type="hcaptcha_enterprise", rqdata=None, proxy=None):
        """Primary solver - RazorCap API"""
        try:
            payload = {
                "type": captcha_type,
                "websiteURL": page_url,
                "websiteKey": site_key,
                "rqdata": rqdata,
                "proxy": proxy
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            resp = self.session.post(
                RAZORCAP_URL,
                json=payload,
                headers={"Authorization": f"Bearer {RAZORCAP_KEY}", "Content-Type": "application/json"},
                timeout=30
            )
            
            if resp.status_code != 200:
                print(f"RazorCap error: {resp.text}")
                return None
                
            data = resp.json()
            if data.get("error"):
                print(f"RazorCap API error: {data['error']}")
                return None
                
            task_id = data.get("taskId")
            if not task_id:
                return None
                
            # Poll for result
            return self._poll_razorcap(task_id)
            
        except Exception as e:
            print(f"RazorCap failed: {e}")
            return None
            
    def _poll_razorcap(self, task_id, max_attempts=60, interval=2):
        """Poll for RazorCap result"""
        for _ in range(max_attempts):
            try:
                resp = self.session.get(
                    f"{RAZORCAP_URL}/result/{task_id}",
                    headers={"Authorization": f"Bearer {RAZORCAP_KEY}"},
                    timeout=10
                )
                data = resp.json()
                
                if data.get("status") == "ready":
                    return data.get("solution")
                    
                time.sleep(interval)
            except Exception as e:
                print(f"Poll error: {e}")
                time.sleep(interval)
                
        return None
        
    def solve_ocr(self, image_path_or_url):
        """Free backup #1 - OCR for simple image CAPTCHAs"""
        try:
            if image_path_or_url.startswith("http"):
                img_data = self.session.get(image_path_or_url).content
                with open("temp_captcha.png", "wb") as f:
                    f.write(img_data)
                image_path = "temp_captcha.png"
            else:
                image_path = image_path_or_url
                
            image = Image.open(image_path).convert("L")  # Grayscale
            # Enhance contrast
            pixels = image.load()
            for i in range(image.width):
                for j in range(image.height):
                    if pixels[i, j] > 128:
                        pixels[i, j] = 255
                    else:
                        pixels[i, j] = 0
                        
            text = pytesseract.image_to_string(image, config="--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
            
            if image_path == "temp_captcha.png":
                os.remove(image_path)
                
            return text.strip()
        except Exception as e:
            print(f"OCR failed: {e}")
            return None
            
    def solve_browser(self, site_key, page_url):
        """Free backup #2 - Browser automation (requires selenium/playwright)"""
        # This is a placeholder - you'd implement actual browser automation here
        # For now, returns None to trigger next backup
        print("Browser solver not implemented in minimal version")
        return None
        
    def solve(self, site_key=None, page_url=None, image_url=None, captcha_type="hcaptcha_enterprise", rqdata=None, proxy=None):
        """
        Master solve method - tries all solvers in order:
        1. RazorCap (paid, reliable)
        2. OCR (free, for images)
        3. Browser automation (free, last resort)
        """
        solution = None
        
        # Try RazorCap first for hCaptcha/reCaptcha
        if site_key and page_url and RAZORCAP_KEY:
            print("Attempting RazorCap...")
            solution = self.solve_razorcap(site_key, page_url, captcha_type, rqdata, proxy)
            if solution:
                print("RazorCap success!")
                return solution
                
        # Try OCR for image CAPTCHAs
        if image_url:
            print("Attempting OCR...")
            solution = self.solve_ocr(image_url)
            if solution:
                print(f"OCR success: {solution}")
                return solution
                
        # Try browser automation
        if site_key and page_url:
            print("Attempting browser solver...")
            solution = self.solve_browser(site_key, page_url)
            if solution:
                return solution
                
        raise Exception("All CAPTCHA solvers failed")

# Singleton instance
solver = CaptchaSolver()

if __name__ == "__main__":
    # Test
    result = solver.solve(
        site_key="f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34",
        page_url="https://discord.com/login"
    )
    print(f"Result: {result}")

