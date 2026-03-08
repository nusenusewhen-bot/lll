FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    python3-dev \
    tesseract-ocr \
    libtesseract-dev \
    nodejs \
    npm \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node deps
COPY package.json .
RUN npm install

# Copy app
COPY . .

CMD ["python", "bot.py"]
