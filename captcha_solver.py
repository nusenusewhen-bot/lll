from aiohttp import web
import asyncio
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import base64
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CaptchaServer')

class CaptchaServer:
    def __init__(self, host='localhost', port=8081):
        self.app = web.Application()
        self.host = host
        self.port = port
        self.setup_routes()
        
    def setup_routes(self):
        self.app.router.add_post('/solve/ocr', self.solve_ocr)
        self.app.router.add_get('/health', self.health)
        
    async def solve_ocr(self, request):
        """Free OCR solver for simple image CAPTCHAs"""
        try:
            data = await request.json()
            image_data = data.get('image')
            
            if not image_data:
                return web.json_response({'error': 'No image provided'}, status=400)
                
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Preprocess for better OCR
            image = image.convert('L')  # Grayscale
            image = ImageEnhance.Contrast(image).enhance(2)
            image = image.filter(ImageFilter.MedianFilter())
            
            # OCR
            text = pytesseract.image_to_string(
                image,
                config='--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            )
            
            result = text.strip().replace(' ', '').replace('\n', '')
            logger.info(f'OCR result: {result}')
            
            return web.json_response({
                'status': 'ready',
                'solution': {'token': result}
            })
            
        except Exception as e:
            logger.error(f'OCR error: {e}')
            return web.json_response({'error': str(e)}, status=500)
            
    async def health(self, request):
        return web.json_response({'status': 'ok'})
        
    def run(self):
        web.run_app(self.app, host=self.host, port=self.port)

if __name__ == '__main__':
    server = CaptchaServer()
    server.run()
