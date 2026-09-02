# ============================================================
# RAFANO TRADER V9.10 - FULL INTEGRATED BOT (WITH DEBUG LOGGING)
# ============================================================

import os
import io
import asyncio
import logging
import aiohttp
import requests
import yfinance as yf
import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RafanoTraderFull")

ARJUM_BASE_URL = "https://stock.arjum.com/api"
ARJUM_API_KEY = "sk_live_OTn4r_••••••••"
TELEGRAM_BOT_TOKEN = "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ"
DEFAULT_CHAT_ID = "5660874676"

def _get_arjum_headers() -> Dict[str, str]:
    return {
        "X-API-Key": ARJUM_API_KEY,
        "Accept": "application/json"
    }

# ============================================================
# 1. MARKET DATA PROVIDER WITH DEBUG LOGGING
# ============================================================

class MarketDataProvider:
    @staticmethod
    async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with session.get(url, headers=_get_arjum_headers(), timeout=10) as response:
                text_data = await response.text()
                if response.status == 200:
                    res_json = await response.json()
                    # DEBUG: Mencetak respons mentah ke terminal untuk pengecekan data API
                    print(f"DEBUG URL [{url}] RESPONSE: {res_json}")
                    return res_json
                else:
                    print(f"DEBUG URL [{url}] STATUS CODE: {response.status}, TEXT: {text_data}")
        except Exception as e:
            logger.debug("Fetch error %s: %s", url, e)
        return None

    @classmethod
    async def fetch_all_market_data(cls, ticker: str) -> Dict[str, Any]:
        ticker_upper = ticker.upper()
        urls = {
            "analysis": f"{ARJUM_BASE_URL}/analysis/{ticker_upper}",
            "seasonal": f"{ARJUM_BASE_URL}/seasonal/{ticker_upper}",
            "financials": f"{ARJUM_BASE_URL}/financial-statements/{ticker_upper}?report_type=INCOME_STATEMENT&period=quarterly&limit=4",
            "insiders": f"{ARJUM_BASE_URL}/insiders/{ticker_upper}?page=1&limit=5",
            "history": f"{ARJUM_BASE_URL}/history/{ticker_upper}?limit=250&frame=daily",
            "bandar_1d": f"{ARJUM_BASE_URL}/bandar-volume/{ticker_upper}?period=1d",
            "bandar_5d": f"{ARJUM_BASE_URL}/bandar-volume/{ticker_upper}?period=5d",
            "bandar_20d": f"{ARJUM_BASE_URL}/bandar-volume/{ticker_upper}?period=20d",
            "foreign_1d": f"{ARJUM_BASE_URL}/foreign-flow/{ticker_upper}?period=1d",
            "foreign_5d": f"{ARJUM_BASE_URL}/foreign-flow/{ticker_upper}?period=5d",
            "foreign_20d": f"{ARJUM_BASE_URL}/foreign-flow/{ticker_upper}?period=20d",
            "broker_1d": f"{ARJUM_BASE_URL}/broker-accumulation/{ticker_upper}?period=1d&top=3",
            "broker_5d": f"{ARJUM_BASE_URL}/broker-accumulation/{ticker_upper}?period=5d&top=3",
            "broker_20d": f"{ARJUM_BASE_URL}/broker-accumulation/{ticker_upper}?period=20d&top=3",
        }
        async with aiohttp.ClientSession() as session:
            tasks = [cls._fetch_json(session, url) for url in urls.values()]
            results = await asyncio.gather(*tasks)
        return {key: val for key, val in zip(urls.keys(), results)}

    @staticmethod
    def get_history_sync(ticker: str, limit: int = 250) -> Optional[pd.DataFrame]:
        ticker_upper = ticker.upper()
        try:
            url = f"{ARJUM_BASE_URL}/analysis/{ticker_upper}"
            res = requests.get(url, headers=_get_arjum_headers(), timeout=5)
            if res.status_code == 200:
                meta = res.json()
                if meta.get("is_fca", False) or (meta.get("is_suspended", False) and meta.get("suspend_duration_days", 0) > 3):
                    return None
        except Exception:
            pass

        try:
            url = f"{ARJUM_BASE_URL}/history/{ticker_upper}?limit={limit}&frame=daily"
            res = requests.get(url, headers=_get_arjum_headers(), timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", res.json())
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    if len(df) >= 50:
                        return df.tail(limit)
        except Exception:
            pass

        try:
            yf_ticker = f"{ticker_upper}.JK" if not ticker_upper.endswith(".JK") else ticker_upper
            df_yf = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.droplevel(1)
                df_yf = df_yf.rename(columns=str.lower)
                return df_yf[['open', 'high', 'low', 'close', 'volume']].dropna().tail(limit)
        except Exception:
            pass
        return None

async def fetch_active_watchlist() -> list:
    url = f"{ARJUM_BASE_URL}/stocks/active"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_get_arjum_headers(), timeout=15) as resp:
                if resp.status == 200:
                    stocks = (await resp.json()).get("data", [])
                    return [s.get("symbol") for s in stocks if not s.get("is_fca", False) and not s.get("is_suspended", False)][:300]
    except Exception:
        pass
    return ["BBCA", "BBRI", "BMRI", "BBNI", "ASII", "ADRO", "ANTM", "GOTO", "TLKM"]


# ============================================================
# 2. DATA STRUCTURE & ROBUST PARSERS
# ============================================================

@dataclass
class CompleteSignal:
    ticker: str
    price: float
    score: int
    rating: str
    rsi: float
    relative_volume: float
    breakout: bool
    resistance: float
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float
    bandar_1d: str
    bandar_5d: str
    bandar_20d: str
    foreign_1d: str
    foreign_5d: str
    foreign_20d: str
    brokers_1d: str
    brokers_5d: str
    brokers_20d: str

def parse_status_field(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "NEUTRAL"
    if isinstance(data, str):
        return data.upper()
    payload = data.get("data", data)
    if isinstance(payload, dict):
        return str(payload.get("status", payload.get("trend", "NEUTRAL"))).upper()
    return "NEUTRAL"

def parse_brokers_with_avg_and_value(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "N/A"
    
    payload = data.get("data", data)
    brokers = []
    if isinstance(payload, dict):
        brokers = payload.get("top_buyers", payload.get("brokers", payload.get("buyer", [])))
    elif isinstance(payload, list):
        brokers = payload
        
    if not brokers:
        return "Normal/Flat"
    
    formatted = []
    for b in brokers[:3]:
        if not isinstance(b, dict):
            continue
        code = b.get("broker_code", b.get("code", b.get("broker", "???")))
        avg_price = b.get("avg_price", b.get("average", b.get("avg", 0)))
        value = b.get("value", b.get("net_value", b.get("val", 0)))
        
        val_str = ""
        try:
            if value is not None:
                abs_val = abs(float(value))
                if abs_val >= 1e9:
                    val_str = f"Rp{float(value)/1e9:.1f}B"
                elif abs_val >= 1e6:
                    val_str = f"Rp{float(value)/1e6:.1f}M"
                else:
                    val_str = f"Rp{float(value):,.0f}"
        except Exception:
            pass
                
        try:
            if avg_price and float(avg_price) > 0 and val_str:
                formatted.append(f"{code}(@Rp{float(avg_price):,.0f}|{val_str})")
            elif avg_price and float(avg_price) > 0:
                formatted.append(f"{code}(@Rp{float(avg_price):,.0f})")
            else:
                formatted.append(code)
        except Exception:
            formatted.append(str(code))
            
    return ", ".join(formatted) if formatted else "Normal/Flat"


# ============================================================
# 3. CHART GENERATOR (EMA 50 & EMA 200)
# ============================================================

def generate_oke_saham_chart(df: pd.DataFrame, ticker: str, company_name: str, last_date: str) -> io.BytesIO:
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
        
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    custom_style = mpf.make_mpf_style(
        base_mpf_style='nightclouds',
        marketcolors=mpf.make_marketcolors(up='#26a69a', down='#ef5350', edge='inherit', wick='inherit'),
        facecolor='#131722', figcolor='#131722', gridcolor='#2a2e39', gridstyle='--'
    )
    apds = [
        mpf.make_addplot(df['EMA_50'], color='#ffa726', width=1.0),
        mpf.make_addplot(df['EMA_200'], color='#29b6f6', width=1.5),
    ]
    
    buf = io.BytesIO()
    latest_row = df.iloc[-1]
    change_pct = ((latest_row['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close']) * 100
    
    fig, axes = mpf.plot(
        df, type='candle', style=custom_style, addplot=apds,
        volume=True, panel_ratios=(3, 1), figratio=(14, 8),
        figscale=1.1, returnfig=True, show_nontrading=False
    )
    
    fig.text(0.06, 0.94, f"{ticker.upper()} : {latest_row['close']:,.0f} ({change_pct:+.2f}%)", fontsize=12, fontweight='bold', color='#ffffff')
    fig.text(0.06, 0.91, f"{company_name}", fontsize=9, color='#b2b5be')
    fig.text(0.68, 0.94, f"Daily {last_date}", fontsize=9, color='#b2b5be', ha='right')
    fig.text(0.68, 0.91, f"Command BOT /oke {ticker.upper()}", fontsize=9, color='#b2b5be', ha='right')
    
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#131722')
    buf.seek(0)
    plt.close(fig)
    return buf

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = pd.concat([df['high'] - df['low'], np.abs(df['high'] - df['close'].shift()), np.abs(df['low'] - df['close'].shift())], axis=1).max(axis=1).rolling(14).mean()
    df['rel_vol'] = df['volume'] / df['volume'].rolling(20).mean()
    return df

async def build_complete_signal_async(ticker: str) -> Optional[Tuple[CompleteSignal, io.BytesIO]]:
    ticker = ticker.upper()
    df = MarketDataProvider.get_history_sync(ticker, limit=250)
    if df is None or df.empty or len(df) < 50:
        return None
        
    market_data = await MarketDataProvider.fetch_all_market_data(ticker)
    df = calculate_technical_indicators(df)
    latest = df.iloc[-1]
    
    price = float(latest['close'])
    ema_50 = float(latest['ema_50']) if not np.isnan(latest['ema_50']) else price
    rsi = float(latest['rsi']) if not np.isnan(latest['rsi']) else 50.0
    rel_vol = float(latest['rel_vol']) if not np.isnan(latest['rel_vol']) else 1.0
    atr = float(latest['atr']) if not np.isnan(latest['atr']) else (price * 0.03)
    
    bandar_1d = parse_status_field(market_data.get("bandar_1d"))
    bandar_5d = parse_status_field(market_data.get("bandar_5d"))
    bandar_20d = parse_status_field(market_data.get("bandar_20d"))
    
    foreign_1d = parse_status_field(market_data.get("foreign_1d"))
    foreign_5d = parse_status_field(market_data.get("foreign_5d"))
    foreign_20d = parse_status_field(market_data.get("foreign_20d"))
    
    brokers_1d = parse_brokers_with_avg_and_value(market_data.get("broker_1d"))
    brokers_5d = parse_brokers_with_avg_and_value(market_data.get("broker_5d"))
    brokers_20d = parse_brokers_with_avg_and_value(market_data.get("broker_20d"))
    
    analysis_res = market_data.get("analysis") or {}
    if isinstance(analysis_res, dict):
        company_name = analysis_res.get("company_name", ticker)
    else:
        company_name = ticker
        
    last_date = df.index[-1].strftime("%d %b %Y")
    
    score = min(max((20 if price > ema_50 else 0) + (15 if 50 <= rsi <= 75 else 5) + (15 if rel_vol > 1.2 else 0) +
                    (10 if bandar_20d == "ACCUMULATION" else 0) + (10 if foreign_20d == "ACCUMULATION" else 0), 0), 100)
    rating = "STRONG BUY" if score >= 80 else ("BUY" if score >= 65 else "WATCHLIST")
    
    resistance_20 = float(df['high'].rolling(20).max().iloc[-1])
    breakout = bool(price >= resistance_20)
    
    stop_loss = price - (1.5 * atr)
    target_1 = price + (2.0 * atr)
    target_2 = price + (3.5 * atr)
    risk = price - stop_loss
    risk_reward = round((target_1 - price) / risk, 1) if risk > 0 else 1.0

    signal = CompleteSignal(
        ticker=ticker, price=price, score=score, rating=rating, rsi=round(rsi, 2),
        relative_volume=round(rel_vol, 2), breakout=breakout, resistance=resistance_20,
        entry=price, stop_loss=stop_loss, target_1=target_1, target_2=target_2, risk_reward=risk_reward,
        bandar_1d=bandar_1d, bandar_5d=bandar_5d, bandar_20d=bandar_20d,
        foreign_1d=foreign_1d, foreign_5d=foreign_5d, foreign_20d=foreign_20d,
        brokers_1d=brokers_1d, brokers_5d=brokers_5d, brokers_20d=brokers_20d
    )
    
    chart_buf = generate_oke_saham_chart(df, ticker, company_name, last_date)
    return signal, chart_buf


# ============================================================
# 4. TELEGRAM COMMAND HANDLERS & EOD AUTOMATION
# ============================================================

async def cmd_oke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Format salah! Gunakan: /oke <TICKER> (Contoh: /oke BBCA)")
        return
        
    ticker = args[0].upper()
    await update.message.reply_text(f"Menganalisis data saham {ticker}...")
    
    result = await build_complete_signal_async(ticker)
    if not result:
        await update.message.reply_text(f"Gagal mengambil data untuk saham {ticker} atau saham disuspensi/FCA.")
        return
        
    signal, chart_buf = result
    breakout_text = "YES" if signal.breakout else "NO"
    
    caption = (
        "🚨 *RAFANO TRADER SIGNAL*\n\n"
        f"📌 Saham: *{signal.ticker}*\n"
        f"💰 Harga: *Rp{signal.price:,.0f}*\n"
        f"⭐ Score: *{signal.score}/100* | Rating: *{signal.rating}*\n\n"
        
        "📊 *Technical Indicators*\n"
        f"• RSI (14): `{signal.rsi}` | Rel Vol: `{signal.relative_volume}x`\n"
        f"• Breakout R20: `{breakout_text}` (Rp{signal.resistance:,.0f})\n\n"
        
        "🐋 *Bandar Volume Flow (1D / 5D / 20D)*\n"
        f"• Status: `{signal.bandar_1d}` / `{signal.bandar_5d}` / `{signal.bandar_20d}`\n\n"
        
        "🌐 *Foreign Flow (1D / 5D / 20D)*\n"
        f"• Status: `{signal.foreign_1d}` / `{signal.foreign_5d}` / `{signal.foreign_20d}`\n\n"
        
        "🏛 *Top 3 Broker Akumulasi (Avg & Value)*\n"
        f"• 1D: `{signal.brokers_1d}`\n"
        f"• 5D: `{signal.brokers_5d}`\n"
        f"• 20D: `{signal.brokers_20d}`\n\n"
        
        "💼 *Trading Plan*\n"
        f"• Entry: `Rp{signal.entry:,.0f}`\n"
        f"• Stop Loss: `Rp{signal.stop_loss:,.0f}`\n"
        f"• Target 1: `Rp{signal.target_1:,.0f}` | Target 2: `Rp{signal.target_2:,.0f}`\n"
        f"• Risk/Reward: `1:{signal.risk_reward}`"
    )
    
    await update.message.reply_photo(photo=chart_buf, caption=caption, parse_mode="Markdown")

async def run_eod_market_scanner(bot_app_or_token):
    logger.info("Running automated EOD Big Accumulation Scanner...")
    tickers = await fetch_active_watchlist()
    results = []
    
    for ticker in tickers[:150]:
        market_data = await MarketDataProvider.fetch_all_market_data(ticker)
        df = MarketDataProvider.get_history_sync(ticker, limit=50)
        if df is None or len(df) < 25:
            continue
            
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        delta = df['high'] - df['low']
        df['atr'] = pd.concat([delta, np.abs(df['high'] - df['close'].shift()), np.abs(df['low'] - df['close'].shift())], axis=1).max(axis=1).rolling(14).mean()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        close_price = float(latest['close'])
        change_pct = ((close_price - prev['close']) / prev['close']) * 100
        rel_vol = float(latest['volume'] / latest['vol_ma20']) if latest['vol_ma20'] > 0 else 1.0
        atr = float(latest['atr']) if not np.isnan(latest['atr']) else (close_price * 0.03)
        
        bandar_1d = parse_status_field(market_data.get("bandar_1d"))
        bandar_5d = parse_status_field(market_data.get("bandar_5d"))
        bandar_20d = parse_status_field(market_data.get("bandar_20d"))
        
        if bandar_1d == "ACCUMULATION" and rel_vol >= 1.3 and change_pct >= 0.5:
            analysis_res = market_data.get("analysis") or {}
            comp_name = analysis_res.get("company_name", ticker) if isinstance(analysis_res, dict) else ticker
            
            stop_loss = close_price - (1.5 * atr)
            target_1 = close_price + (2.0 * atr)
            target_2 = close_price + (3.5 * atr)
            risk = close_price - stop_loss
            rr = round((target_1 - close_price) / risk, 1) if risk > 0 else 1.0
            
            results.append({
                "ticker": ticker, "name": comp_name, "close": close_price, "change": change_pct,
                "vol": round(rel_vol, 2), "b1": bandar_1d, "b5": bandar_5d, "b20": bandar_20d,
                "br1": parse_brokers_with_avg_and_value(market_data.get("broker_1d")),
                "br5": parse_brokers_with_avg_and_value(market_data.get("broker_5d")),
                "br20": parse_brokers_with_avg_and_value(market_data.get("broker_20d")),
                "sl": stop_loss, "t1": target_1, "t2": target_2, "rr": rr
            })

    date_str = datetime.now().strftime("%d %b %Y")
    if not results:
        message = f"🌙 *EOD MARKET SCANNER REPORT*\n📅 Tanggal: {date_str}\n\nTidak ada emiten memenuhi kriteria Big Akumulasi hari ini."
    else:
        message = (
            "🌙 *EOD BIG ACCUMULATION & VOLUME SURGE SCANNER*\n"
            f"📅 Tanggal Rekap: *{date_str}* | Ditemukan: *{len(results)}* Emiten\n\n"
        )
        for idx, res in enumerate(results[:8], 1):
            message += (
                f"{idx}. *{res['ticker']}* - {res['name']}\n"
                f"   💰 Close: `Rp{res['close']:,.0f}` (`{res['change']:+.2f}%`) | Vol: `{res['vol']}x`\n"
                f"   🐋 Bandar -> 1D: `{res['b1']}` | 5D: `{res['b5']}` | 20D: `{res['b20']}`\n"
                f"   🏛 Top Broker (1D): `{res['br1']}`\n"
                f"   🏛 Top Broker (5D): `{res['br5']}`\n"
                f"   🏛 Top Broker (20D): `{res['br20']}`\n"
                f"   🎯 Plan -> SL: `Rp{res['sl']:,.0f}` | TP1: `Rp{res['t1']:,.0f}` | RR: `1:{res['rr']}`\n\n"
            )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": DEFAULT_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    async with aiohttp.ClientSession() as session:
        await session.post(url, json=payload, timeout=15)


# ============================================================
# 5. MAIN ENTRY POINT & SCHEDULER
# ============================================================

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("oke", cmd_oke))
    
    # Scheduler untuk EOD Auto Scan setiap jam 19:00 WIB
    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(run_eod_market_scanner, 'cron', hour=19, minute=0, args=[app])
    scheduler.start()
    
    logger.info("Rafano Trader Bot V9.10 is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
