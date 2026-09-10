# Position Sizing Calculator Bot 🤖

Fast Telegram bot for instant position sizing calculations. Public deployment on Railway.

## Features

✅ **Instant calculation** — <1s response time  
✅ **Public always-on** — Railway free tier  
✅ **Template-based input** — Copy-paste format  
✅ **Pretty output table** — Easy to read  

## Input Format

```
execute
MY.CODE
EP=2.28
SL=2.25
ATR=0.08
3★
Env : REAL
```

## Output Example

```
📊 Position Sizing — MY.5199
Environment: REAL

Input:
└ Entry Price (EP): RM2.28
└ Stop Loss (SL): RM2.25
└ ATR: 0.080
└ Risk Level: 3★ ★★★☆☆ (25 RM)

Calculation:
Lots            3 lot(s)
Qty             300 shares
Capital         RM684.00
Max Loss (SL)   RM24.00

✅ Ready to execute on moomoo
```

## Quick Deploy (Railway.app)

### 1. Create Telegram Bot Token

- Open Telegram → search `@BotFather`
- `/newbot` → give name + username
- **Copy token** (e.g., `123456:ABC...`)

### 2. Deploy to Railway

**Option A: Railway CLI (fastest)**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy from this folder
railway init
railway up

# Set environment variable
railway variables add TELEGRAM_BOT_TOKEN=your_token_here
```

**Option B: Railway Web (no CLI)**

1. Go to https://railway.app
2. Sign up (free)
3. New Project → Deploy from GitHub
4. Connect repo
5. Add variable `TELEGRAM_BOT_TOKEN` = your token
6. Deploy

### 3. Set Webhook (One-time)

Replace `YOUR_TOKEN` and `RAILWAY_URL`:

```bash
curl -X POST https://api.telegram.org/botYOUR_TOKEN/setWebhook \
  -d url=https://your-railway-url/YOUR_TOKEN
```

Railway URL looks like: `https://railway-project-name-prod.up.railway.app`

### 4. Test in Telegram

- Find your bot (@username)
- Send:
```
execute
MY.5199
EP=2.28
SL=2.25
ATR=0.08
3★
Env : REAL
```

- Get instant calculation ⚡

## Local Testing (Before Deploy)

```bash
# Install deps
pip install -r requirements.txt

# Set token
export TELEGRAM_BOT_TOKEN=your_token

# Run
python bot.py
```

Bot runs on `http://localhost:8080`

## Calculation Rules

- **Equity baseline**: RM10,000 (can adjust in code later)
- **Risk per star**: 5★=1R, 4★=0.5R, 3★=0.25R, 2★=0.125R, 1★=0.05R
- **1R = 1% of equity** = RM100 (for RM10,000)
- **SL rule**: If EP ≥ RM1, use ATR; else use manual SL
- **Lot size = floor(risk / (SL × 100))** — always floored, never rounded up
- **Bursa board lot**: 100 shares = 1 lot

## Adjusting Equity

Edit `bot.py`, line ~24:

```python
EQUITY_DEFAULT = 10000  # Change to 20000 for RM20,000 capital
```

Re-deploy: `railway up`

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Bot doesn't respond | Check webhook is set + Railway logs |
| Slow response | Restart Railway dyno |
| "Token not found" error | Add `TELEGRAM_BOT_TOKEN` env var to Railway |
| Math looks wrong | Double-check EP > SL, ATR > 0 |

## Files

- `bot.py` — Main bot code (calculation + Telegram API)
- `requirements.txt` — Python dependencies
- `Procfile` — Railway config (tells it to run bot.py)
- `README.md` — This file

## Maintenance

- **Monitor logs**: `railway logs` (CLI)
- **Scale up**: Railway free tier = 500 hrs/month (enough for always-on bot)
- **Update code**: Push to GitHub → Railway auto-deploys

---

**Built for speed.** Deploy once, use forever. ⚡
