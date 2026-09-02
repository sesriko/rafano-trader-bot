# ============================================================
# RAFANO TRADER V9.3 - OPTIMIZED & ASYNCHRONOUS HYBRID BOT
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
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from functools import lru_cache

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RafanoTrader")

# Konfigurasi API & Telegram
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
# 1. ASYNCHRONOUS DATA PROVIDER MODULE (ARJUM API + FALLBACK)
# ============================================================

class AsyncMarketDataProvider:
    @staticmethod
    async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with session.get(url, headers=_get_arjum_headers(), timeout=10) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.debug("Async fetch error for %s: %s", url, e)
        return None

    @classmethod
    async def fetch_all_market_data(cls, ticker: str) -> Dict[str, Any]:
        ticker_upper = ticker.upper()
        urls = {
            "analysis": f"{ARJUM_BASE_URL}/analysis/{ticker_upper}",
            "broker": f"{ARJUM_BASE_URL}/broker-accumulation/{ticker_upper}?top=3",
            "seasonal": f"{ARJUM_BASE_URL}/seasonal/{ticker_upper}",
            "financials": f"{ARJUM_BASE_URL}/financial-statements/{ticker_upper}?report_type=INCOME_STATEMENT&period=quarterly&limit=4",
            "insiders": f"{ARJUM_BASE_URL}/insiders/{ticker_upper}?page=1&limit=5",
            "history": f"{ARJUM_BASE_URL}/history/{ticker_upper}?limit=250&frame=daily"
        }

        async with aiohttp.ClientSession() as session:
            tasks = [cls._fetch_json(session, url) for url in urls.values()]
            results = await asyncio.gather(*tasks)
            
        return {key: val for key, val in zip(urls.keys(), results)}

    @staticmethod
    def get_history_sync(ticker: str, limit: int = 250) -> Optional[pd.DataFrame]:
        ticker_upper = ticker.upper()
        
        # 1. Coba via Arjum API
        try:
            url = f"{ARJUM_BASE_URL}/history/{ticker_upper}?limit={limit}&frame=daily"
            res = requests.get(url, headers=_get_arjum_headers(), timeout=10)
            if res.status_code == 200:
                data = res.json()
                raw_data = data.get("data", data)
                if isinstance(raw_data, list) and len(raw_data) > 0:
                    df = pd.DataFrame(raw_data)
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        if col in df.columns:
                            df[col] = df[col].astype(float)
                    
                    if not df.empty and len(df) >= 50:
                        logger.info("Berhasil mengambil data history %s via Arjum API (%d baris).", ticker_upper, len(df))
                        return df.tail(limit)
        except Exception as e:
            logger.warning("Arjum History API gagal untuk %s: %s. Beralih ke yfinance...", ticker_upper, e)

        # 2. Fallback Cadangan via yfinance
        try:
            yf_ticker = f"{ticker_upper}.JK" if not ticker_upper.endswith(".JK") else ticker_upper
            df_yf = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.droplevel(1)
                df_yf = df_yf.rename(columns=str.lower)
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                if all(col in df_yf.columns for col in df_yf.columns):
                    df_yf = df_yf[required_cols].dropna()
                    logger.info("Berhasil mengambil data history %s via yfinance Fallback.", yf_ticker)
                    return df_yf.tail(limit)
        except Exception as ye:
            logger.error("yfinance Fallback juga gagal untuk %s: %s", ticker_upper, ye)

        return None


# ============================================================
# 2. DATA STRUCTURE
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
    broker_status: str
    seasonal_trend: str
    insider_action: str
    net_income_growth: str


# ============================================================
# 3. OKE SAHAM CHART GENERATOR MODULE
# ============================================================

def generate_oke_saham_chart(df: pd.DataFrame, ticker: str, company_name: str, last_date: str) -> io.BytesIO:
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
        
    df['EMA_13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean() # Major Trend
    
    custom_style = mpf.make_mpf_style(
        base_mpf_style='nightclouds',
        marketcolors=mpf.make_marketcolors(
            up='#26a69a', down='#ef5350', 
            edge='inherit', wick='inherit', 
            volume={'up': '#26a69a', 'down': '#ef5350'}
        ),
        facecolor='#131722',
        figcolor='#131722',
        gridcolor='#2a2e39',
        gridstyle='--',
        rc={
            'font.family': 'monospace',
            'text.color': 'white',
            'axes.labelcolor': 'white',
            'xtick.color': 'white',
            'ytick.color': 'white'
        }
    )
    
    apds = [
        mpf.make_addplot(df['EMA_13'], color='#29b6f6', width=0.8),
        mpf.make_addplot(df['EMA_20'], color='#ffa726', width=0.8),
        mpf.make_addplot(df['EMA_50'], color='#ab47bc', width=1.0),
        mpf.make_addplot(df['EMA_200'], color='#ef5350', width=1.2),
    ]
    
    buf = io.BytesIO()
    latest_row = df.iloc[-1]
    prev_close = df.iloc[-2]['close']
    change_pct = ((latest_row['close'] - prev_close) / prev_close) * 100
    
    fig, axes = mpf.plot(
        df, type='candle', style=custom_style, addplot=apds,
        volume=True, panel_ratios=(3, 1), figratio=(14, 8),
        figscale=1.1, returnfig=True, show_nontrading=False
    )
    
    header_title = f"{ticker.upper()} : {latest_row['close']:,.0f} ({change_pct:+.2f}%)"
    fig.text(0.06, 0.94, header_title, fontsize=12, fontweight='bold', color='#ffffff')
    fig.text(0.06, 0.91, f"{company_name}", fontsize=9, color='#b2b5be')
    fig.text(0.68, 0.94, f"Daily {last_date}", fontsize=9, color='#b2b5be', ha='right')
    fig.text(0.68, 0.91, f"Command BOT /OKE {ticker.upper()}", fontsize=9, color='#b2b5be', ha='right')
    
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#131722')
    buf.seek(0)
    plt.close(fig)
    return buf


# ============================================================
# 4. TECHNICAL ENGINE & SIGNAL BUILDER
# ============================================================

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    df['atr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    df['rel_vol'] = df['volume'] / df['volume'].rolling(20).mean()
    return df

async def build_complete_signal_async(ticker: str) -> Optional[Tuple[CompleteSignal, io.BytesIO]]:
    ticker = ticker.upper()
    df = AsyncMarketDataProvider.get_history_sync(ticker, limit=250)
    if df is None or df.empty or len(df) < 50:
        logger.warning("Data historis untuk %s tidak mencukupi.", ticker)
        return None
        
    market_data = await AsyncMarketDataProvider.fetch_all_market_data(ticker)
    df = calculate_technical_indicators(df)
    latest = df.iloc[-1]
    
    price = float(latest['close'])
    ema_200 = float(latest['ema_200']) if not np.isnan(latest['ema_200']) else price
    rsi = float(latest['rsi']) if not np.isnan(latest['rsi']) else 50.0
    rel_vol = float(latest['rel_vol']) if not np.isnan(latest['rel_vol']) else 1.0
    atr = float(latest['atr']) if not np.isnan(latest['atr']) else (price * 0.03)
    
    analysis_data = market_data.get("analysis") or {}
    broker_data = market_data.get("broker") or {}
    seasonal_data = market_data.get("seasonal") or {}
    financials_data = market_data.get("financials") or {}
    insiders_data = market_data.get("insiders") or {}
    
    broker_status = broker_data.get("status", "NEUTRAL")
    seasonal_trend = seasonal_data.get("trend", "FLAT")
    insider_action = insiders_data.get("summary", "NO_ACTION")
    net_income_growth = financials_data.get("growth_status", "STABLE")
    company_name = analysis_data.get("company_name", ticker)
    last_date = df.index[-1].strftime("%d %b %Y")
    
    trend_score = 20 if price > ema_200 else 0
    momentum_score = 15 if 50 <= rsi <= 75 else 5
    volume_score = 15 if rel_vol > 1.2 else 0
    arjum_score = (10 if broker_status == "ACCUMULATION" else 0) + (5 if seasonal_trend == "BULLISH" else 0) + (5 if net_income_growth == "GROWING" else 0)
    
    score = min(max(trend_score + momentum_score + volume_score + arjum_score, 0), 100)
    rating = "STRONG BUY" if score >= 80 else ("BUY" if score >= 65 else "WATCHLIST")
    
    resistance_20 = float(df['high'].rolling(20).max().iloc[-1])
    breakout = bool(price >= resistance_20)
    
    entry = price
    stop_loss = entry - (1.5 * atr)
    target_1 = entry + (2.0 * atr)
    target_2 = entry + (3.5 * atr)
    risk = entry - stop_loss
    risk_reward = round((target_1 - entry) / risk, 1) if risk > 0 else 1.0

    signal = CompleteSignal(
        ticker=ticker, price=price, score=score, rating=rating,
        rsi=round(rsi, 2), relative_volume=round(rel_vol, 2),
        breakout=breakout, resistance=resistance_20, entry=entry,
        stop_loss=stop_loss, target_1=target_1, target_2=target_2,
        risk_reward=risk_reward, broker_status=broker_status,
        seasonal_trend=seasonal_trend, insider_action=insider_action,
        net_income_growth=net_income_growth
    )
    
    chart_buf = generate_oke_saham_chart(df, ticker, company_name, last_date)
    return signal, chart_buf


# ============================================================
# 5. TELEGRAM SENDER MODULE & ASYNC POLLING LOOP
# ============================================================

async def send_rafano_signal_to_telegram(ticker: str, chat_id: str = DEFAULT_CHAT_ID):
    result = await build_complete_signal_async(ticker)
    if not result:
        logger.warning("Gagal memproses sinyal untuk %s", ticker)
        return False
        
    signal, chart_buf = result
    breakout_text = "YES" if signal.breakout else "NO"
    
    caption = (
        "🚨 *RAFANO TRADER SIGNAL (V9.3 OPTIMIZED)*\n\n"
        f"📌 Saham: *{signal.ticker}*\n"
        f"💰 Harga: *Rp{signal.price:,.0f}*\n"
        f"⭐ Score: *{signal.score}/100* | Rating: *{signal.rating}*\n\n"
        
        "📊 *Technical Indicators*\n"
        f"• RSI (14): `{signal.rsi}`\n"
        f"• Rel Volume: `{signal.relative_volume}x`\n"
        f"• Breakout R20: `{breakout_text}` (Rp{signal.resistance:,.0f})\n\n"
        
        "🏦 *Arjum Market Intelligence*\n"
        f"• Broker Flow: `{signal.broker_status}`\n"
        f"• Seasonal Trend: `{signal.seasonal_trend}`\n"
        f"• Net Income Growth: `{signal.net_income_growth}`\n"
        f"• Insider Action: `{signal.insider_action}`\n\n"
        
        "💼 *Trading Plan & Risk Management*\n"
        f"• Entry: `Rp{signal.entry:,.0f}`\n"
        f"• Stop Loss: `Rp{signal.stop_loss:,.0f}`\n"
        f"• Target 1: `Rp{signal.target_1:,.0f}`\n"
        f"• Target 2: `Rp{signal.target_2:,.0f}`\n"
        f"• Risk/Reward: `1:{signal.risk_reward}`"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('chat_id', chat_id)
            form.add_field('caption', caption)
            form.add_field('parse_mode', 'Markdown')
            form.add_field('photo', chart_buf.getvalue(), filename='chart.png', content_type='image/png')
            
            async with session.post(url, data=form, timeout=15) as response:
                if response.status == 200:
                    logger.info("Berhasil mengirim sinyal & chart %s ke Telegram!", ticker)
                    return True
                else:
                    err_text = await response.text()
                    logger.error("Gagal kirim Telegram: %s", err_text)
                    return False
    except Exception as e:
        logger.error("Error koneksi ke Telegram API: %s", e)
        return False

async def send_text_message(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

async def main_telegram_bot():
    logger.info("🤖 Rafano Trader Bot V9.3 Berjalan dan Mendengarkan Perintah Telegram...")
    last_update_id = 0
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
                async with session.get(url, timeout=35) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok") and data.get("result"):
                            for update in data["result"]:
                                last_update_id = update["update_id"]
                                
                                if "message" in update and "text" in update["message"]:
                                    msg = update["message"]
                                    c_id = msg["chat"]["id"]
                                    text = msg["text"].strip()
                                    
                                    if text.lower() in ["/start", "/help"]:
                                        help_text = (
                                            "🤖 *RAFANO TRADER BOT (V9.3)*\n\n"
                                            "Ketik perintah berikut untuk melihat analisis & chart:\n"
                                            "• `/oke <kode_saham>`\n"
                                            "  _Contoh:_ `/oke BBCA` atau `/oke ASII`"
                                        )
                                        await send_text_message(c_id, help_text)
                                        
                                    elif text.lower().startswith("/oke ") or text.lower().startswith("/c "):
                                        parts = text.split()
                                        if len(parts) >= 2:
                                            ticker = parts[1].upper()
                                            await send_text_message(c_id, f"🔍 *Menganalisis & merender chart {ticker}... Mohon tunggu.*")
                                            await send_rafano_signal_to_telegram(ticker, chat_id=str(c_id))
                                        else:
                                            await send_text_message(c_id, "⚠️ Format salah. Gunakan: `/oke <kode_saham>` (Contoh: `/oke BBCA`)")
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main_telegram_bot())
    except KeyboardInterrupt:
        logger.info("Bot dihentikan manual.")
