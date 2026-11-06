#!/usr/bin/env python3
"""
FCPO Morning Brief — pre-open market sentiment for Bursa Malaysia crude palm oil futures.

Two layers:
1. Scorecard (rule-based, deterministic): numbers fetched directly from MPOC (FCPO 3rd-month
   settlements) and Yahoo Finance (CBOT soyoil, Brent, USD/MYR). Each factor scores +1/0/-1.
2. Narrative (Claude + web search): overnight news, Dalian, export data, events today. Claude
   also scores Dalian and exports, which have no free price feed.

Total score >= +2 → BULLISH, <= -2 → BEARISH, otherwise NEUTRAL.

Run standalone to print a brief without Telegram:  python fcpo_brief.py
"""

import asyncio
import html
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

MYT = timezone(timedelta(hours=8))  # Malaysia has no DST
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fcpo-brief/1.0)"}

MPOC_URL = "https://www.mpoc.org.my/market-insight/daily-palm-oil-prices/"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

# Yahoo symbols → (label, threshold % for a +1/-1 score, palm-direction sign)
# sign +1: instrument up = bullish palm. USD/MYR up = weaker ringgit = palm cheaper abroad = bullish.
YAHOO_FACTORS = {
    "ZL=F": ("Soyoil CBOT", 0.3, +1),
    "BZ=F": ("Brent", 0.5, +1),
    "MYR=X": ("USD/MYR", 0.15, +1),
}

DEFAULT_MODEL = "claude-opus-5-5"
BULL_THRESHOLD = 2
BEAR_THRESHOLD = -2
NARRATIVE_LIMIT = 2800  # keeps the whole message under Telegram's 4,096-char limit

DAYS_MS = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"]
MONTHS_MS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov", "Dis"]


@dataclass
class Factor:
    name: str
    detail: str
    score: int | None  # None = data unavailable (counts as 0)


@dataclass
class MarketData:
    fcpo_contract: str | None = None
    fcpo_settlements: list[tuple[str, int]] = field(default_factory=list)  # oldest → newest
    yahoo: dict[str, dict] = field(default_factory=dict)  # symbol → {price, change_pct}
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

async def fetch_mpoc(client: httpx.AsyncClient, data: MarketData) -> None:
    """FCPO 3rd-month settlements (last ~10 trading days) from MPOC's daily price page."""
    try:
        resp = await client.get(MPOC_URL)
        resp.raise_for_status()
        page = resp.text
        rows = re.findall(r"<tr><td>(\d{1,2} \w{3} \d{2})</td><td>(\d{4,5})</td></tr>", page)
        data.fcpo_settlements = [(d, int(p)) for d, p in rows]
        m = re.search(r"\((\w{3}), (\d{2}) Contract\)", page)
        if m:
            data.fcpo_contract = f"{m.group(1)}{m.group(2)}"
        if not data.fcpo_settlements:
            data.errors.append("MPOC: settlement table not found (page layout changed?)")
    except Exception as e:
        data.errors.append(f"MPOC: {e}")


async def fetch_yahoo(client: httpx.AsyncClient, symbol: str, data: MarketData) -> None:
    """Last price + % change vs previous close for one Yahoo Finance symbol."""
    try:
        resp = await client.get(YAHOO_URL.format(symbol=symbol))
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        data.yahoo[symbol] = {
            "price": float(meta["regularMarketPrice"]),
            "change_pct": float(meta["regularMarketChangePercent"]),
        }
    except Exception as e:
        data.errors.append(f"Yahoo {symbol}: {e}")


async def fetch_market_data() -> MarketData:
    data = MarketData()
    async with httpx.AsyncClient(headers=HTTP_HEADERS, timeout=20.0, follow_redirects=True) as client:
        await asyncio.gather(
            fetch_mpoc(client, data),
            *(fetch_yahoo(client, s, data) for s in YAHOO_FACTORS),
        )
    return data


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------

def score_change(change_pct: float, threshold: float, sign: int) -> int:
    if change_pct >= threshold:
        return sign
    if change_pct <= -threshold:
        return -sign
    return 0


def build_factors(data: MarketData) -> list[Factor]:
    factors = []

    # FCPO trend: last settlement vs average of the settlements MPOC shows (~10 days)
    s = data.fcpo_settlements
    if len(s) >= 5:
        last = s[-1][1]
        avg = sum(p for _, p in s) / len(s)
        trend = +1 if last > avg else -1 if last < avg else 0
        factors.append(Factor("Trend FCPO", f"{last:,} vs purata {len(s)} hari {avg:,.0f}", trend))
    else:
        factors.append(Factor("Trend FCPO", "data tiada", None))

    for symbol, (label, threshold, sign) in YAHOO_FACTORS.items():
        q = data.yahoo.get(symbol)
        if q:
            detail = f"{q['price']:.4g} ({q['change_pct']:+.2f}%)"
            factors.append(Factor(label, detail, score_change(q["change_pct"], threshold, sign)))
        else:
            factors.append(Factor(label, "data tiada", None))
    return factors


def bias_label(total: int) -> str:
    if total >= BULL_THRESHOLD:
        return "🟢 BULLISH"
    if total <= BEAR_THRESHOLD:
        return "🔴 BEARISH"
    return "🟡 NEUTRAL"


# ---------------------------------------------------------------------------
# Claude narrative
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a commodities analyst writing a short pre-open morning brief on \
Bursa Malaysia crude palm oil futures (FCPO) for a Malaysian retail trader. He reads it on \
Telegram before the 10:30am MYT open, to know the day's sentiment before he trades.

Write in Bahasa Melayu (casual, clear), keeping market terms in English (support, resistance, \
long liquidation, open interest, etc.). Plain text only: no Markdown, no asterisks, no tables, \
no links. Use short lines and a few emoji section markers. Stay under 1,800 characters.

Use web search for the last ~24 hours. Prefer primary or reputable sources: Bursa Malaysia, \
MPOB, MPOC, Bernama, Reuters, The Edge, The Star, Business Recorder, cargo surveyors \
(Intertek/ITS, AmSpec). If sources disagree or a figure can't be verified, say so briefly \
rather than guessing. Never invent prices.

Cover, in this order:
📌 Semalam: FCPO close/settlement for the Dec and Jan contracts (and change), plus the night \
(T+1) session if reported.
🌏 Overnight: Dalian palm olein and soyoil, CBOT soyoil, crude oil, ringgit — direction and \
the reason in a few words.
📊 Fundamental: latest export estimates (ITS/AmSpec), MPOB stocks/production, Indonesia \
policy (reference price, levy, B50) — only what is new or still driving the market.
🎯 Paras: nearby support and resistance for the benchmark 3rd-month contract, based on \
reported levels or recent settlements.
⚠️ Hari ini: scheduled events today (MPOB report, export data on the 10th/15th/20th/25th/\
month-end, Indonesia announcements, holidays). Flag clearly if a major release lands today \
because it can flip the morning bias.

This is general market commentary, not personal investment advice: do not tell him to buy or \
sell.

After the brief, end with exactly these two lines (each score is -1, 0 or +1 from palm oil's \
point of view; 0 if unclear or not reported):
DALIAN: <score>
EXPORTS: <score>"""

SCORE_LINE = re.compile(r"^\s*(DALIAN|EXPORTS)\s*:\s*([+-]?[01])\s*$", re.MULTILINE)


def format_data_for_prompt(data: MarketData, factors: list[Factor], now: datetime) -> str:
    lines = [f"Today: {now:%A %d %B %Y}, {now:%H:%M} MYT."]
    if data.fcpo_settlements:
        series = ", ".join(f"{d}: {p}" for d, p in data.fcpo_settlements)
        lines.append(f"FCPO 3rd-month settlements from MPOC ({data.fcpo_contract or 'contract n/a'}): {series}")
    for f in factors:
        lines.append(f"{f.name}: {f.detail}")
    lines.append("Use these figures as ground truth where they overlap with what you find.")
    return "\n".join(lines)


async def write_narrative(data: MarketData, factors: list[Factor], now: datetime) -> tuple[str, dict[str, int]]:
    """Ask Claude (with web search) for the brief. Returns (text, {"DALIAN": n, "EXPORTS": n})."""
    import anthropic

    client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY
    model = os.getenv("FCPO_BRIEF_MODEL", DEFAULT_MODEL)
    messages = [{"role": "user", "content": format_data_for_prompt(data, factors, now)}]

    response = None
    for _ in range(4):  # resume server-side web search turns that pause
        response = await client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}],
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined the request (refusal)")

    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    scores = {k: int(v) for k, v in SCORE_LINE.findall(text)}
    text = SCORE_LINE.sub("", text).strip()
    return text, scores


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------

def score_icon(score: int | None) -> str:
    return {1: "+1", 0: " 0", -1: "-1"}.get(score, "n/a")


async def build_brief(now: datetime | None = None) -> str:
    """Full morning brief as Telegram HTML."""
    now = now or datetime.now(MYT)
    data = await fetch_market_data()
    factors = build_factors(data)

    narrative = ""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            narrative, ai_scores = await write_narrative(data, factors, now)
            factors.append(Factor("Dalian", "dari berita", ai_scores.get("DALIAN")))
            factors.append(Factor("Eksport", "dari berita", ai_scores.get("EXPORTS")))
        except Exception as e:
            logger.exception("FCPO narrative failed")
            data.errors.append(f"Claude: {e}")
    else:
        data.errors.append("ANTHROPIC_API_KEY not set — AI summary disabled, scorecard only")

    total = sum(f.score or 0 for f in factors)
    date_str = f"{DAYS_MS[now.weekday()]} {now.day} {MONTHS_MS[now.month - 1]} {now.year}"

    out = [
        f"🌴 <b>FCPO Morning Brief — {date_str}</b>",
        f"Bias: <b>{bias_label(total)}</b> (skor {total:+d})",
        "",
    ]

    if data.fcpo_settlements:
        (d1, p1) = data.fcpo_settlements[-1]
        line = f"Settlement {data.fcpo_contract or 'FCPO'} ({d1}): <b>RM{p1:,}</b>"
        if len(data.fcpo_settlements) >= 2:
            line += f" ({p1 - data.fcpo_settlements[-2][1]:+d})"
        out.append(line)

    out.append("<pre>")
    for f in factors:
        out.append(html.escape(f"{f.name:<12}{score_icon(f.score):>4}  {f.detail}"))
    out.append("</pre>")

    if narrative:
        # Cap the narrative (not the assembled HTML) so a cut never leaves a tag unclosed
        if len(narrative) > NARRATIVE_LIMIT:
            narrative = narrative[:NARRATIVE_LIMIT].rstrip() + "\n…(dipotong)"
        out += ["", html.escape(narrative)]

    if data.errors:
        out += ["", "⚠️ " + html.escape("; ".join(data.errors))]

    out += ["", "<i>Komentar pasaran umum, bukan nasihat pelaburan.</i>"]

    return "\n".join(out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(build_brief()))
