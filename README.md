# Position Sizing Calculator Bot 🤖

Fast Telegram bot untuk calculate position sizing instantly. Public deployment on Railway.

**Untuk Bursa Malaysia trading** — Input EP/SL/ATR/star, dapat position size table terus.

## Features

✅ **Instant calculation** — <1s response time  
✅ **Public always-on** — Railway free tier (RM0)  
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

## Quick Deploy (Railway.app) — 5 Minit

### Step 1: Get Telegram Bot Token
- Open Telegram → `@BotFather`
- `/newbot` → kasih name + username
- **Copy token**

### Step 2: Deploy to Railway
1. Go to **railway.app** → Sign up (free)
2. **New Project** → **Deploy from GitHub**
3. Connect this repo
4. Railway auto-detects `Procfile` & `requirements.txt`
5. Add environment variable:
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: Token dari Step 1
6. **Deploy**

### Step 3: Get Public URL
Railway gives you: `https://railway-proj-name-prod.up.railway.app`

### Step 4: Activate Webhook
```bash
curl -X POST https://api.telegram.org/botTOKEN/setWebhook \
  -d url=https://YOUR_RAILWAY_URL/TOKEN
```

### Step 5: Test
- Find bot di Telegram
- Send order calculation request
- Get result terus! ⚡

## Calculation Rules

- **Equity baseline**: RM10,000 (adjust in code if capai RM20,000+)
- **Risk per star**: 5★=1R, 4★=0.5R, 3★=0.25R, 2★=0.125R, 1★=0.05R
- **1R = 1% of equity** = RM100
- **SL rule**: If EP ≥ RM1, use ATR; else use manual SL
- **Lot size = floor(risk / (SL × 100))** — always floor, never round up
- **Bursa board lot**: 100 shares = 1 lot

## Adjusting Equity

Edit `bot.py`, line ~24:

```python
EQUITY_DEFAULT = 10000  # Change to 20000 when reach RM20k capital
```

Push to GitHub → Railway auto-redeploys

## Files

- `bot.py` — Bot logic + calculation
- `requirements.txt` — Dependencies
- `Procfile` — Railway config
- `README.md` — This file

---

**Built untuk speed.** Deploy once, use forever. ⚡
