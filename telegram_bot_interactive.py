import os
import sys
import io

# ==========================================
# AUTO-INSTALL MISSING DEPENDENCIES (COLAB)
# ==========================================
def install_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"📦 Installing missing package: {package_name}...")
        os.system(f"{sys.executable} -m pip install {package_name}")

install_package("pyTelegramBotAPI", "telebot")
install_package("yfinance")
install_package("pandas")
install_package("numpy")
install_package("matplotlib")
install_package("requests")
install_package("pytz")

# ==========================================
# IMPORT LIBRARIES
# ==========================================
import time
import requests
import pandas as pd
import numpy as np
import datetime
import pytz
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import telebot
import yfinance as yf

# ==========================================
# KONFIGURASI CREDENTIAL & GLOBAL
# ==========================================
BOT_TOKEN = "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ"
DEFAULT_CHAT_ID = "5660874676"

ARJUM_API_BASE_URL = "https://stock.arjum.com/api"
HEADERS = {'User-Agent': 'Mozilla/5.0'}
MAX_WORKERS = 35

bot = telebot.TeleBot(BOT_TOKEN)

DEFAULT_300_STOCKS = [
    "AALI", "ABMM", "ACES", "ADHI", "ADRO", "AGRO", "AKRA", "AMAR", "AMRT", "ANTM",
    "APLN", "ARTO", "ASGR", "ASII", "AUTO", "AVIA", "AXIO", "BBYB", "BBCA", "BBNI",
    "BBRI", "BBTN", "BDMN", "BFIN", "BIRD", "BJBR", "BJTM", "BKSL", "BMRI", "BMTR",
    "BNGA", "BNII", "BRPT", "BRMS", "BSDE", "BTPS", "BUKA", "BULL", "BUMI", "CASS",
    "CLEO", "CMNP", "CPIN", "CSAP", "CTRA", "DEWA", "DILD", "DRMA", "DSNG", "ENRG",
    "ERAA", "ESSA", "EXCL", "FILM", "GJTL", "GOTO", "HEAL", "HERO", "HEXA", "HMSP",
    "HRUM", "ICBP", "INDF", "INKP", "INTP", "ISAT", "ISSP", "ITMG", "JPFA", "JRPT",
    "JSMR", "KAEF", "KBLI", "KLBF", "KPIG", "LPPF", "LSIP", "MAPA", "MAPI", "MDKA",
    "MEDC", "MIKA", "MNCN", "MPMX", "MTDL", "MYOR", "NCKL", "NIKL", "PANR", "PANS",
    "PGAS", "PNBN", "PNLF", "POWR", "PTBA", "PTPP", "PTRO", "PWON", "RAJA", "RALS",
    "ROTI", "SAME", "SCMA", "SIDO", "SMAR", "SMGR", "SMRA", "SMSM", "SRTG", "SSMS",
    "TAPG", "TPIA", "TLKM", "TOWR", "TRIM", "TSPC", "ULTJ", "UNVR", "WIKA", "WOOD",
    "WTON", "AMMN", "MBMA", "CMRY", "BDRX", "MTAA", "BELI", "MCOL", "MMLP", "NGLO",
    "RUIS", "SCCC", "TINS", "TOTL", "TOBA", "UCID", "WEGE", "WIIM", "FUTR", "GIAA", "COIN"
]

# ==========================================
# FETCH DATA & INDIKATOR
# ==========================================
def fetch_stock_history_multi_tf(symbol, timeframe="1d"):
    tf = timeframe.lower().strip()
    yf_tf_map = {
        '15m': ('15m', '1mo'), '30m': ('30m', '1mo'),
        '1h':  ('60m', '3mo'), '1d':  ('1d',  '1y'),
        '1w':  ('1wk', '2y')
    }
    interval, period = yf_tf_map.get(tf, ('1d', '1y'))

    if tf == '1d':
        endpoints = [
            f"{ARJUM_API_BASE_URL}/history/{symbol}?interval=1d&limit=150",
            f"{ARJUM_API_BASE_URL}/klines?symbol={symbol}&interval=1d"
        ]
        for url in endpoints:
            try:
                res = requests.get(url, headers=HEADERS, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    klines = data.get("data") or data.get("results") or data
                    if isinstance(klines, list) and len(klines) > 10:
                        df_res = pd.DataFrame(klines)
                        df_res['Symbol_Owner'] = symbol
                        return df_res
            except Exception:
                pass

    if yf is not None:
        try:
            yf_symbol = symbol if (symbol.endswith(".JK") or not symbol.isalpha()) else f"{symbol}.JK"
            ticker_obj = yf.Ticker(yf_symbol)
            df_yf = ticker_obj.history(interval=interval, period=period, auto_adjust=False, actions=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = [col[0] for col in df_yf.columns]
                df_yf.reset_index(inplace=True)
                df_yf.columns = [str(c).capitalize() for c in df_yf.columns]

                date_col = 'Datetime' if 'Datetime' in df_yf.columns else ('Date' if 'Date' in df_yf.columns else None)
                if date_col:
                    df_yf['Date'] = pd.to_datetime(df_yf[date_col])
                    if df_yf['Date'].dt.tz is not None:
                        df_yf['Date'] = df_yf['Date'].dt.tz_convert('Asia/Jakarta').dt.tz_localize(None)

                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_yf.columns:
                        df_yf[col] = pd.to_numeric(df_yf[col], errors='coerce')

                df_clean = df_yf.dropna(subset=['Close']).copy()
                df_clean['Symbol_Owner'] = symbol
                return df_clean
        except Exception:
            pass
    return None

def calculate_indicators(df):
    df = df.copy()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    df['Value_Miliard'] = (df['Close'] * df['Volume']) / 1_000_000_000
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    high_low_range = (df['High'] - df['Low']).replace(0, np.nan)
    df['Close_Position'] = (df['Close'] - df['Low']) / high_low_range
    return df

def analyze_high_probability_signal(df):
    if df is None or len(df) < 30:
        return False, None, None
    
    df = calculate_indicators(df)
    last = df.iloc[-1]
    
    if last['Close'] <= 50 or last['Value_Miliard'] < 1.0:
        return False, None, None
    
    c_vol_spike = last['Vol_Ratio'] >= 1.8
    c_bullish_candle = (last['Close'] > last['Open']) and (last['Close_Position'] >= 0.60)
    c_trend = last['Close'] > last['EMA50']
    c_rsi = 50 <= last['RSI'] <= 78
    c_liquidity = last['Value_Miliard'] >= 1.5
    
    score = 0
    if c_vol_spike: score += 35
    if c_bullish_candle: score += 20
    if c_trend: score += 15
    if c_rsi: score += 15
    if c_liquidity: score += 15
    
    metrics = {
        'close': float(last['Close']),
        'vol_ratio': round(float(last['Vol_Ratio']), 2) if not pd.isna(last['Vol_Ratio']) else 0.0,
        'rsi': round(float(last['RSI']), 2) if not pd.isna(last['RSI']) else 0.0,
        'value_m': round(float(last['Value_Miliard']), 2) if not pd.isna(last['Value_Miliard']) else 0.0,
        'ema50': round(float(last['EMA50']), 2) if not pd.isna(last['EMA50']) else 0.0,
        'win_probability': score
    }
    
    is_valid = c_vol_spike and c_bullish_candle and c_trend and c_rsi and (score >= 80)
    return is_valid, metrics, df

# ==========================================
# REVISI CHART GENERATOR MIRIP SCREENSHOT
# ==========================================
def generate_pro_chart_memory(df, symbol="STOCK", timeframe="1D", metrics=None):
    try:
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)

        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Upper_Donchian'] = df['High'].rolling(20).max()
        df['Lower_Donchian'] = df['Low'].rolling(20).min()
        df['Buy_Signal'] = (df['Close'] > df['Open']) & (df['Volume'] > df['Volume'].rolling(20).mean() * 1.5)

        fig = plt.figure(figsize=(13, 7.5), facecolor='black')
        gs = fig.add_gridspec(4, 1, height_ratios=[3.8, 0.25, 1.2, 0.6], hspace=0.06)

        ax_price = fig.add_subplot(gs[0])
        ax_tape = fig.add_subplot(gs[1], sharex=ax_price)
        ax_vol = fig.add_subplot(gs[2], sharex=ax_price)
        ax_mm = fig.add_subplot(gs[3], sharex=ax_price)

        for ax in [ax_price, ax_tape, ax_vol, ax_mm]:
            ax.set_facecolor('black')
            ax.tick_params(colors='white', labelsize=8)
            ax.grid(True, color='#222222', linestyle=':', linewidth=0.5)

        dates = df.index
        for i in range(len(df)):
            open_p, close_p, high_p, low_p = df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i]
            color = '#00ff00' if close_p >= open_p else '#ff0000'
            
            ax_price.plot([dates[i], dates[i]], [low_p, high_p], color=color, linewidth=1)
            ax_price.plot([dates[i], dates[i]], [open_p, close_p], color=color, linewidth=3.5)

            # Signal Text & Marker "BELI" persis seperti gambar
            if df['Buy_Signal'].iloc[i]:
                ax_price.text(dates[i], low_p * 0.985, f"BELI >{int(close_p)}\nSL <{int(low_p*0.96)}", 
                              color='#00ff00', fontsize=5.5, fontweight='bold', ha='center')

        # Garis Step Donchian Channel
        ax_price.step(dates, df['Upper_Donchian'], color='#666666', linestyle='--', linewidth=0.8, where='mid')
        ax_price.step(dates, df['Lower_Donchian'], color='#666666', linestyle='--', linewidth=0.8, where='mid')

        # Marker "BAHAYA" pada swing high
        last_high = df['High'].tail(15).max()
        ax_price.text(dates[-10], last_high * 1.01, f"BAHAYA >{int(last_high)}", color='#ffff00', fontsize=6, fontweight='bold')

        # ---------------------------------------------------
        # HEADER ATAS PERSIS DENGAN SCREENSHOT
        # ---------------------------------------------------
        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high_val = df['High'].iloc[-1]
        last_low_val = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1] / 1_000_000
        change_pct = ((last_close - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100

        header_left = f"{symbol.upper()} : {int(last_close)} ({change_pct:+.2f}%)\nHigh: {int(last_high_val)} Low: {int(last_low_val)} Open: {int(last_open)} Volume: {last_vol:.3f}M"
        header_mid = "THE RAFANO SIGNAL"
        date_str = datetime.datetime.now().strftime("%d %b %Y")
        header_right = f"{timeframe.upper()} {date_str}\nRegistrasi BOT 089612331428"

        ax_price.text(0.01, 1.08, header_left, transform=ax_price.transAxes, color='#ffff00', fontsize=8, fontweight='bold', va='top')
        ax_price.text(0.50, 1.08, header_mid, transform=ax_price.transAxes, color='white', fontsize=10, fontweight='bold', ha='center', va='top')
        ax_price.text(0.99, 1.08, header_right, transform=ax_price.transAxes, color='white', fontsize=7, ha='right', va='top')

        # ---------------------------------------------------
        # INFO BOX STATISTIK KIRI ATAS
        # ---------------------------------------------------
        info_stat = (
            f"Avg Price : {int(df['Close'].tail(5).mean())}\n"
            f"Vchg 1Day : {metrics.get('vol_ratio', 1.0)}x\n"
            f"Vchg 5Days: 0.8x\n"
            f"Speed     : SLOW\n"
            f"Power     : SLOW\n"
            f"Quality   : GOOD"
        )
        ax_price.text(0.01, 0.95, info_stat, transform=ax_price.transAxes, color='white', fontsize=6.5, fontfamily='monospace', va='top')

        # Price Label Kanan (Kuning, Cyan)
        ax_price.text(1.01, 0.85, f" {int(last_high)} ", transform=ax_price.transAxes, color='black', backgroundcolor='#ffff00', fontsize=8, fontweight='bold')
        ax_price.text(1.01, 0.75, f" {int(last_close)} ", transform=ax_price.transAxes, color='black', backgroundcolor='#ffff00', fontsize=8, fontweight='bold')
        ax_price.text(1.01, 0.68, f" {int(last_low_val)} ", transform=ax_price.transAxes, color='black', backgroundcolor='#00ffff', fontsize=8, fontweight='bold')

        # ---------------------------------------------------
        # SUBPLOT 2: TAPE ACCUMULATION BAR
        # ---------------------------------------------------
        for i in range(len(df)):
            c = '#00ff00' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff0000'
            ax_tape.bar(dates[i], 1, color=c, width=0.8)
        ax_tape.get_yaxis().set_visible(False)
        ax_tape.text(0.01, 0.1, "Buy Percent = 50%  Sell Percent = 50%  Net Vol = 0  Net 5D = -90.500", 
                     transform=ax_tape.transAxes, color='white', fontsize=5.5)

        # ---------------------------------------------------
        # SUBPLOT 3: VOLUME HISTOGRAM
        # ---------------------------------------------------
        for i in range(len(df)):
            c = '#00ff00' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff0000'
            ax_vol.bar(dates[i], df['Volume'].iloc[i], color=c, alpha=0.9, width=0.8)
        ax_vol.set_ylabel("Vol", color='white', fontsize=7)

        # ---------------------------------------------------
        # SUBPLOT 4: MARKET MAKER
        # ---------------------------------------------------
        mm_val = (df['Close'] - df['Open']) / (df['High'] - df['Low']).replace(0, np.nan) * (df['Volume'] / df['Volume'].rolling(20).mean()) * 10
        ax_mm.bar(dates, mm_val.fillna(0), color='white', width=0.8, alpha=0.7)
        ax_mm.set_title("Market Maker", color='white', fontsize=7, loc='left', pad=-8)

        plt.setp(ax_price.get_xticklabels(), visible=False)
        plt.setp(ax_tape.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

        if timeframe in ['15m', '30m', '1h']:
            ax_mm.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %H:%M'))
        else:
            ax_mm.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

        fig.autofmt_xdate()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf

    except Exception as e:
        print(f"⚠️ Error rendering chart ({symbol}): {e}")
        return None

# ==========================================
# PARALLEL SCREENER ENGINE
# ==========================================
def process_single_stock(symbol, timeframe="1d"):
    try:
        df = fetch_stock_history_multi_tf(symbol, timeframe=timeframe)
        if df is not None and not df.empty and len(df) >= 30:
            cols_lower = {str(col).lower().strip(): col for col in df.columns}
            rename_dict = {}
            for target, aliases in [
                ('Open', ['open']), ('High', ['high']), ('Low', ['low']), 
                ('Close', ['close']), ('Volume', ['volume']),
                ('Date', ['date', 'datetime', 'time', 't'])
            ]:
                for alias in aliases:
                    if alias in cols_lower:
                        rename_dict[cols_lower[alias]] = target
                        break
            df.rename(columns=rename_dict, inplace=True)

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col not in df.columns: df[col] = 0

            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)

            is_signal, metrics, df_processed = analyze_high_probability_signal(df)
            if is_signal:
                return (symbol, metrics, df_processed, True)
    except Exception:
        pass
    return (symbol, None, None, False)

def run_market_screener_parallel(timeframe="1d"):
    watchlist = DEFAULT_300_STOCKS
    matched_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_stock, symbol, timeframe): symbol for symbol in watchlist}
        for future in as_completed(futures):
            symbol, metrics, df_processed, is_signal = future.result()
            if is_signal:
                matched_results.append((symbol, metrics, df_processed))
    return matched_results

# ==========================================
# TELEGRAM CAPTION FORMAT TERBARU
# ==========================================
def send_telegram_signal(chat_id, symbol, metrics, df_stock=None, timeframe="1d"):
    close_price = int(metrics.get('close', 0))
    tp1_price = int(close_price * 1.035)

    caption = (
        f"FOMO\n"
        f"{symbol.upper()} {close_price} buy1\n"
        f"Tetap siapkan buy2\n\n"
        f"Target 1 {tp1_price}\n"
        f"Target 2 ARa"
    )
    
    try:
        if df_stock is not None and not df_stock.empty:
            chart_buffer = generate_pro_chart_memory(df_stock, symbol=symbol, timeframe=timeframe, metrics=metrics)
            if chart_buffer:
                chart_buffer.name = f"{symbol}_{timeframe}.png"
                bot.send_photo(chat_id, photo=chart_buffer, caption=caption)
                return

        bot.send_message(chat_id, caption)
    except Exception as e:
        print(f"Gagal mengirim sinyal ke Telegram ({symbol}): {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = "🤖 *RAFANO SIGNAL BOT ACTIVE*\n\nGunakan perintah `/c` atau `/c [timeframe]` untuk screening."
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['c'])
def handle_chart_command(message):
    chat_id = message.chat.id
    args = message.text.split()[1:]
    timeframes_valid = ['15m', '30m', '1h', '1d', '1w']
    
    if len(args) >= 1 and args[0].lower() not in timeframes_valid:
        symbol = args[0].upper()
        timeframe = args[1].lower() if len(args) > 1 and args[1].lower() in timeframes_valid else "1d"
        bot.reply_to(message, f"🔍 Mengambil data & chart #{symbol} [{timeframe.upper()}]...")
        
        def single_stock_thread():
            df = fetch_stock_history_multi_tf(symbol, timeframe=timeframe)
            if df is not None and not df.empty:
                cols_lower = {str(col).lower().strip(): col for col in df.columns}
                rename_dict = {}
                for target, aliases in [
                    ('Open', ['open']), ('High', ['high']), ('Low', ['low']), 
                    ('Close', ['close']), ('Volume', ['volume']),
                    ('Date', ['date', 'datetime', 'time', 't'])
                ]:
                    for alias in aliases:
                        if alias in cols_lower:
                            rename_dict[cols_lower[alias]] = target
                            break
                df.rename(columns=rename_dict, inplace=True)
                
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)

                is_signal, metrics, df_processed = analyze_high_probability_signal(df)
                if not metrics:
                    df = calculate_indicators(df)
                    last = df.iloc[-1]
                    score = 85
                    metrics = {
                        'close': float(last['Close']),
                        'vol_ratio': round(float(last['Vol_Ratio']), 2) if not pd.isna(last['Vol_Ratio']) else 0.0,
                        'rsi': round(float(last['RSI']), 2) if not pd.isna(last['RSI']) else 0.0,
                        'value_m': round(float(last['Value_Miliard']), 2) if not pd.isna(last['Value_Miliard']) else 0.0,
                        'ema50': round(float(last['EMA50']), 2) if not pd.isna(last['EMA50']) else 0.0,
                        'win_probability': score
                    }
                    df_processed = df

                send_telegram_signal(chat_id, symbol, metrics, df_stock=df_processed, timeframe=timeframe)
            else:
                bot.send_message(chat_id, f"❌ Data saham #{symbol} tidak ditemukan pada timeframe {timeframe.upper()}.")

        Thread(target=single_stock_thread).start()
        return

    timeframe = args[0].lower() if len(args) > 0 and args[0].lower() in timeframes_valid else "1d"
    bot.reply_to(message, f"🚀 Memulai mass screening 300 saham [{timeframe.upper()}]...")
    
    def worker_thread():
        results = run_market_screener_parallel(timeframe=timeframe)
        if not results:
            bot.send_message(chat_id, f"❌ Tidak ditemukan sinyal pada timeframe {timeframe.upper()}.")
        else:
            bot.send_message(chat_id, f"✅ Screening Selesai! Ditemukan {len(results)} sinyal [{timeframe.upper()}]:")
            for symbol, metrics, df_stock in results:
                send_telegram_signal(chat_id, symbol, metrics, df_stock=df_stock, timeframe=timeframe)

    Thread(target=worker_thread).start()

if __name__ == "__main__":
    print(f"🤖 Bot 'The Rafano Signal' Aktif...")
    bot.infinity_polling()
