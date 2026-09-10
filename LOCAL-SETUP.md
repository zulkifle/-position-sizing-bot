# Local Docker Setup (Fallback PC)

Run bot as Docker container locally on your PC, tunnel via ngrok to Telegram.

## Prerequisites

- Docker Desktop installed (Windows/Mac) or Docker Engine (Linux)
- ngrok account (free: https://ngrok.com)

## Setup

### 1. Build Docker Image

```bash
cd C:\PROJECTS\TRADEVAULT\position-sizing-bot
docker build -t position-sizing-bot:latest .
```

Or use docker-compose (easier):

```bash
docker-compose build
```

### 2. Create `.env` file

```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token_here
RAILWAY_PUBLIC_DOMAIN=your_ngrok_url_here
```

(Don't commit `.env` to git — already in .gitignore)

### 3. Run Docker Container

```bash
docker-compose up
```

Or manually:

```bash
docker run -e TELEGRAM_BOT_TOKEN=your_token_here \
           -e RAILWAY_PUBLIC_DOMAIN=localhost:8080 \
           -e PORT=8080 \
           -p 8080:8080 \
           position-sizing-bot:latest
```

Bot runs on `http://localhost:8080` inside container, exposed on host port 8080.

### 4. Start ngrok Tunnel

**New terminal:**

```bash
ngrok http 8080
```

Output:
```
Forwarding  https://abc123def456.ngrok.io -> http://localhost:8080
```

Copy the HTTPS URL.

### 5. Set Telegram Webhook

```bash
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d url=https://abc123def456.ngrok.io/<TOKEN>
```

Example:
```bash
curl -X POST https://api.telegram.org/bot8375319438:AAH6iMLzESIWm1v46YisamzoeOWm4klMFQY/setWebhook \
  -d url=https://abc123def456.ngrok.io/8375319438:AAH6iMLzESIWm1v46YisamzoeOWm4klMFQY
```

### 6. Test Telegram Bot

- Send message to your bot in Telegram
- Check logs: `docker-compose logs -f`
- Bot should respond instantly!

## Logs & Debugging

View logs:
```bash
docker-compose logs -f position-sizing-bot
```

Stop bot:
```bash
docker-compose down
```

Restart:
```bash
docker-compose up
```

## ngrok Issues

**URL changes on restart** (free tier):
- Stop ngrok
- Update webhook URL with new ngrok URL
- Restart both

**To keep same URL (paid):**
- Upgrade ngrok to paid tier
- Get reserved static domain

## Fallback Workflow

**When Railway expires:**

1. Build & run Docker locally:
   ```bash
   docker-compose up
   ```

2. Start ngrok:
   ```bash
   ngrok http 8080
   ```

3. Update Telegram webhook with new ngrok URL:
   ```bash
   curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
     -d url=https://<NGROK_URL>/<TOKEN>
   ```

4. Bot now active on your PC! ✅

5. PC must stay on 24/7 for bot to work

## Next: Migrate to K8s

When ready for permanent free hosting:
1. Push Docker image to Docker Hub
2. Deploy to Kubernetes
3. No more Railway trial/paid, no more PC-dependent

See `DOCKER.md` for K8s setup.
