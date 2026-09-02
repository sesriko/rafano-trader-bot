# ============================================================
# RAFANO TRADER V9.12 - COMPLETE WORKING SCRIPT
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
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RafanoTraderFull")

ARJUM_BASE_URL = "https://stock.arjum.com/api"
ARJUM_API_KEY = "sk_live_OTn4r_••••••••"
TELEGRAM_BOT_TOKEN = "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ"

def _get_arjum_headers() -> Dict[str, str]:
    return {
        "X-API-Key": ARJUM_API_KEY,
        "Accept": "application/json"
    }

# ============================================================
# 1. MARKET DATA PROVIDER
# ============================================================

class MarketDataProvider:
    @staticmethod
    async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with session.get(url, headers=_get_arjum_headers(), timeout=10) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.debug("Fetch error %s: %s", url, e)
        return None

    @classmethod
    async def fetch_all_market_data(cls, ticker: str) -> Dict[str, Any]:
        ticker_upper = ticker.upper()
        urls = {
            "broker_summary": f"{ARJUM_BASE_URL}/broker-summary/{ticker_upper}?net=false&broker_limit=20&level_limit=25&all_data=false&flow=all",
        }
        async with aiohttp.ClientSession() as session:
            tasks = [cls._fetch_json(session, url) for url in urls.values()]
            results = await asyncio.gather(*tasks)
        return {key: val for key, val in zip(urls.keys(), results)}

    @staticmethod
    def get_history_sync(ticker: str, limit: int = 250) -> Optional[pd.DataFrame]:
        ticker_upper = ticker.upper()
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


# ============================================================
# 2. DATA STRUCTURE & PARSERS
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
    brokers_summary: str

def parse_broker_summary(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "N/A"
    
    payload = data.get("data", data)
    buyers = []
    if isinstance(payload, dict):
        # Mencari berbagai kemungkinan key struktur data response broker summary
        for key in ["buyers", "top_buyers", "broker_summary", "data", "summary"]:
            if key in payload and isinstance(payload[key], list):
                buyers = payload[key]
                break
        if not buyers and "brokers" in payload:
            buyers = payload["brokers"]
    elif isinstance(payload, list):
        buyers = payload
        
    if not buyers:
        return "Normal/Flat"
    
    formatted = []
    for b in buyers[:3]:
        if not isinstance(b, dict):
            continue
        code = b.get("broker", b.get("broker_code", b.get("code", "???")))
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
# 3. CHART & SIGNAL BUILDER
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
    
    brokers_summary = parse_broker_summary(market_data.get("broker_summary"))
    last_date = df.index[-1].strftime("%d %b %Y")
    
    score = min(max((20 if price > ema_50 else 0) + (15 if 50 <= rsi <= 75 else 5) + (15 if rel_vol > 1.2 else 0), 0), 100)
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
        brokers_summary=brokers_summary
    )
    
    chart_buf = generate_oke_saham_chart(df, ticker, ticker, last_date)
    return signal, chart_buf


# ============================================================
# 4. TELEGRAM BOT COMMAND
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
        await update.message.reply_text(f"Gagal mengambil data untuk saham {ticker}.")
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
        
        "🏛 *Top Broker Summary*\n"
        f"• Buyer: `{signal.brokers_summary}`\n\n"
        
        "💼 *Trading Plan*\n"
        f"• Entry: `Rp{signal.entry:,.0f}`\n"
        f"• Stop Loss: `Rp{signal.stop_loss:,.0f}`\n"
        f"• Target 1: `Rp{signal.target_1:,.0f}` | Target 2: `Rp{signal.target_2:,.0f}`\n"
        f"• Risk/Reward: `1:{signal.risk_reward}`"
    )
    
    await update.message.reply_photo(photo=chart_buf, caption=caption, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("oke", cmd_oke))
    logger.info("Rafano Trader Bot V9.12 is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
