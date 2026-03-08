FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    gcc \
    tesseract-ocr \
    libtesseract-dev \
    nodejs \
    npm \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json .
RUN npm install

COPY . .

CMD ["python", "bot.py"]
