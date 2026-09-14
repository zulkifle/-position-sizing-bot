#!/usr/bin/env python3
"""
Position Sizing Calculator Telegram Bot
Fast & lightweight — Railway deployment ready
"""

import os
import re
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
EQUITY_DEFAULT = 10000  # RM (default if not specified in input)
BURSA_LOT_SIZE = 100    # Shares per lot
R_MULTIPLIER = {
    1: 1.0,      # 5★
    0.5: 0.5,    # 4★
    0.25: 0.25,  # 3★
}

# Bursa Malaysia Trading Fees
BROKERAGE_RATE = 0.0003  # 0.03%
PLATFORM_FEE = 3.00      # RM3 per order
CLEARING_FEE_RATE = 0.0003  # 0.03%
STAMP_DUTY_PER_1000 = 1.00  # RM1 per RM1,000 (or part thereof), capped at RM1,000

def calculate_bursa_fees(transaction_amount: float) -> dict:
    """Calculate Bursa Malaysia trading fees for a transaction"""
    import math

    brokerage = round(transaction_amount * BROKERAGE_RATE, 2)
    clearing = round(transaction_amount * CLEARING_FEE_RATE, 2)

    # Stamp duty: RM1 per RM1,000 (or part thereof), capped at RM1,000
    stamp_units = math.ceil(transaction_amount / 1000)
    stamp_duty = min(stamp_units * STAMP_DUTY_PER_1000, 1000)

    total_fees = round(brokerage + PLATFORM_FEE + clearing + stamp_duty, 2)

    return {
        'brokerage': brokerage,
        'platform_fee': PLATFORM_FEE,
        'clearing': clearing,
        'stamp_duty': stamp_duty,
        'total': total_fees,
    }


async def calculate_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse request and calculate position size"""

    message_text = update.message.text.strip()

    # Skip if not a calculation request (must have MY. code + EP/SL/ATR)
    if 'MY.' not in message_text or 'EP=' not in message_text:
        return

    try:
        # Parse input
        lines = [line.strip() for line in message_text.split('\n') if line.strip()]

        if len(lines) < 4:
            await update.message.reply_text(
                "❌ Format error.\n\n"
                "Expected:\n"
                "`MY.CODE\n"
                "EP=2.28\n"
                "SL=2.25\n"
                "ATR=0.08\n"
                "STAR=3\n"
                "Env : REAL`\n\n"
                "(STAR: use 1-5 for star rating OR 1/0.5/0.25/0.125/0.05 for R-value)\n"
                "(Env line optional, defaults to SIMULATE)",
                parse_mode="Markdown"
            )
            return

        # Extract values
        code = lines[0].strip()  # MY.CODE is first line

        ep = None
        sl = None
        atr = None
        stars = None
        equity = EQUITY_DEFAULT  # Default to RM10,000
        env = "SIMULATE"

        for line in lines[1:]:
            if line.startswith('EP='):
                ep = float(line.replace('EP=', '').strip())
            elif line.startswith('SL='):
                sl = float(line.replace('SL=', '').strip())
            elif line.startswith('ATR='):
                atr = float(line.replace('ATR=', '').strip())
            elif line.startswith('EQUITY='):
                equity = float(line.replace('EQUITY=', '').strip())
            elif 'STAR' in line.upper() and '=' in line:
                # Handle "STAR=3" or "STAR=0.25" format
                try:
                    star_value_str = line.split('=')[1].strip()
                    star_value = float(star_value_str)

                    # Map to star rating (1-5)
                    if star_value in [1, 2, 3, 4, 5]:
                        # Direct star rating (1-5)
                        stars = int(star_value)
                    elif star_value == 1.0:
                        stars = 5  # 1R = 5 star
                    elif star_value == 0.5:
                        stars = 4  # 0.5R = 4 star
                    elif star_value == 0.25:
                        stars = 3  # 0.25R = 3 star
                    elif star_value == 0.125:
                        stars = 2  # 0.125R = 2 star
                    elif star_value == 0.05:
                        stars = 1  # 0.05R = 1 star
                    else:
                        stars = None
                except (ValueError, IndexError):
                    stars = None
            elif 'Env' in line or 'REAL' in line or 'SIMULATE' in line:
                env = 'REAL' if 'REAL' in line else 'SIMULATE'

        if not all([ep, sl, atr, stars]):
            raise ValueError("Missing EP, SL, ATR, or star rating")

        # Calculate
        result = calculate_sizing(code, ep, sl, atr, stars, equity)

        # Format response
        response = format_response(code, ep, sl, atr, stars, result, env, equity)

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Calculation error: {e}")


def calculate_sizing(code: str, ep: float, sl: float, atr: float, stars: int, equity: float = EQUITY_DEFAULT) -> dict:
    """Calculate position size using position-size-calculator rules"""

    # Validate
    if ep <= 0 or sl <= 0 or atr <= 0:
        raise ValueError("EP, SL, ATR must be positive")
    if ep <= sl:
        raise ValueError("EP must be > SL")
    if stars not in [1, 2, 3, 4, 5]:
        raise ValueError("Stars must be 1-5")
    if equity <= 0:
        raise ValueError("EQUITY must be positive")

    # Map stars to R multiplier
    if stars == 5:
        r_mult = 1.0
    elif stars == 4:
        r_mult = 0.5
    elif stars == 3:
        r_mult = 0.25
    elif stars == 2:
        r_mult = 0.125
    else:  # 1★
        r_mult = 0.05

    # Risk calculation
    # 1R = 1% of equity
    risk_amount = equity * r_mult * 0.01

    # Use ATR-based Max SL if EP ≥ RM1, else use manual SL
    if ep >= 1.0:
        effective_sl = atr
    else:
        effective_sl = ep - sl

    # Initial lot size = floor(risk_amount / (effective_sl × 100))
    initial_lot_size = int(risk_amount / (effective_sl * BURSA_LOT_SIZE))
    if initial_lot_size < 1:
        initial_lot_size = 1

    # Adjust lot size so total max loss = target risk
    lot_size = initial_lot_size
    target_loss = risk_amount

    while lot_size > 0:
        qty = lot_size * BURSA_LOT_SIZE
        capital = ep * qty
        max_loss_price = effective_sl * qty

        # Calculate fees
        entry_fees = calculate_bursa_fees(capital)
        exit_fees = calculate_bursa_fees(sl * qty)

        # Total max loss (price + fees)
        total_max_loss = max_loss_price + entry_fees['total'] + exit_fees['total']

        # Check if within target risk
        if total_max_loss <= target_loss:
            # Found the right lot size
            break

        # Otherwise, reduce lot size and try again
        lot_size -= 1

    # If lot_size became 0, use 1 lot (minimum)
    if lot_size < 1:
        lot_size = 1
        qty = lot_size * BURSA_LOT_SIZE
        capital = ep * qty
        max_loss_price = effective_sl * qty
        entry_fees = calculate_bursa_fees(capital)
        exit_fees = calculate_bursa_fees(sl * qty)
        total_max_loss = max_loss_price + entry_fees['total'] + exit_fees['total']

    # Final values
    total_capital = capital + entry_fees['total']
    adjusted = lot_size != initial_lot_size  # Track if lot size was adjusted

    return {
        'lots': lot_size,
        'initial_lots': initial_lot_size,
        'adjusted': adjusted,
        'qty': qty,
        'capital': capital,
        'entry_fees': entry_fees,
        'exit_fees': exit_fees,
        'total_capital': total_capital,
        'max_loss': max_loss_price,
        'max_loss_with_fees': total_max_loss,
        'risk_amount': risk_amount,
        'effective_sl': effective_sl,
    }


def format_response(code: str, ep: float, sl: float, atr: float, stars: int, result: dict, env: str, equity: float = EQUITY_DEFAULT) -> str:
    """Format calculation as pretty table with fees"""

    r_label = {1: "0.05R", 2: "0.125R", 3: "0.25R", 4: "0.5R", 5: "1R"}[stars]
    entry_fees = result['entry_fees']
    exit_fees = result['exit_fees']

    response = (
        f"📊 *Position Sizing — {code}*\n"
        f"Environment: `{env}`\n\n"
        f"*Input:*\n"
        f"└ Entry Price (EP): RM{ep:.2f}\n"
        f"└ Stop Loss (SL): RM{sl:.2f}\n"
        f"└ ATR: {atr:.3f}\n"
        f"└ Risk Level: {stars}STAR ({r_label}, RM{result['risk_amount']:.0f})\n\n"
        f"*Calculation:*\n"
        f"```\n"
        f"Lots            {result['lots']} lot(s)"
    )

    if result['adjusted']:
        response += f" (adjusted from {result['initial_lots']})"

    response += (
        f"\n"
        f"Qty             {result['qty']:.0f} shares\n"
        f"Entry Value     RM{result['capital']:.2f}\n"
        f"```\n"
        f"*Bursa Fees (Entry):*\n"
        f"├ Brokerage     RM{entry_fees['brokerage']:.2f}\n"
        f"├ Platform      RM{entry_fees['platform_fee']:.2f}\n"
        f"├ Clearing      RM{entry_fees['clearing']:.2f}\n"
        f"└ Stamp Duty    RM{entry_fees['stamp_duty']:.2f}\n"
        f"*Entry Fees:    RM{entry_fees['total']:.2f}*\n\n"
        f"*Total Capital Needed: RM{result['total_capital']:.2f}*\n\n"
        f"*Max Loss (at SL):*\n"
        f"├ Price Loss    RM{result['max_loss']:.2f}\n"
        f"├ Entry Fees    RM{entry_fees['total']:.2f}\n"
        f"└ Exit Fees     RM{exit_fees['total']:.2f}\n"
        f"*Total Max Loss: RM{result['max_loss_with_fees']:.2f}*\n\n"
        f"✅ Ready to execute on moomoo\n"
    )

    return response


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🤖 *Position Sizing Bot*\n\n"
        "Send:\n"
        "`MY.CODE\n"
        "EP=price\n"
        "SL=price\n"
        "ATR=value\n"
        "STAR=3\n"
        "EQUITY=10000\n"
        "Env : REAL`\n\n"
        "*Optional:*\n"
        "EQUITY: Your capital (defaults to 10000)\n"
        "Env: REAL or SIMULATE (defaults to SIMULATE)\n\n"
        "*STAR options:*\n"
        "Star rating: `STAR=1` to `STAR=5`\n"
        "Or R-value: `STAR=1` (1R), `STAR=0.5` (0.5R), etc.\n\n"
        "Get instant position size calculation! ⚡",
        parse_mode="Markdown"
    )


def main():
    """Start the bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

    # Create application
    app = Application.builder().token(token).build()

    # Add handlers
    app.add_handler(MessageHandler(filters.COMMAND, start))
    app.add_handler(MessageHandler(filters.TEXT, calculate_position))

    # Start webhook (Railway)
    port = int(os.getenv('PORT', 8080))
    app.run_webhook(
        listen='0.0.0.0',
        port=port,
        url_path=token,
        webhook_url=f"{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost')}/{token}"
    )


if __name__ == '__main__':
    main()
