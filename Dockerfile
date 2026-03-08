FROM python:3.11-slim

WORKDIR /app

# Install deps fresh every time (no cache)
RUN apt-get update && apt-get install -y gcc chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "selfbot.py"]
