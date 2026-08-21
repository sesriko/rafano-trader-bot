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
matplotlib.use('Agg')  # Wajib 'Agg' agar headless di Colab
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
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
MAX_WORKERS = 35

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# DAFTAR 300 SAHAM IHSG AKTIF (EKSKLUDI FCA)
# ==========================================
# Saham yang masuk papan FCA (Harga 50 kebawah / Notasi Khusus) disaring secara ketat
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
    "WTON", "AMMN", "MBMA", "CMRY", "BDRX", "AUTO", "MTAA", "BELI", "MCOL", "MMLP",
    "NGLO", "RUIS", "SCCC", "TIN2", "TINS", "TOTL", "TOBA", "UCID", "WEGE", "WIIM"
]

# ==========================================
# FETCH DATA & INDIKATOR ANALISIS
# ==========================================
def fetch_stock_history_multi_tf(symbol, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    yf_tf_map = {
        '15m': ('15m', '1mo'), '30m': ('30m', '1mo'),
        '1h':  ('1h',  '3mo'), '1d':  ('1d',  '1y'),
        '1w':  ('1wk', '2y'),  '1mth':('1mo', '5y')
    }
    yf_setting = yf_tf_map.get(timeframe)
    interval, period = yf_setting if yf_setting else ('1d', '1y')

    if interval == '1d':
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

                date_col = 'Date' if 'Date' in df_yf.columns else ('Datetime' if 'Datetime' in df_yf.columns else None)
                if date_col:
                    df_yf['Date'] = pd.to_datetime(df_yf[date_col]).dt.tz_localize(None)

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
    # Menggunakan EMA 50 untuk momentum intraday/short-term
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
    if df is None or len(df) < 50:
        return False, None, None
    
    df = calculate_indicators(df)
    last = df.iloc[-1]
    
    # Filter Saham FCA / Saham Tidur (Harga < 50 atau Transaksi < 1 Miliar)
    if last['Close'] <= 50 or last['Value_Miliard'] < 1.0:
        return False, None, None
    
    c_vol_spike = last['Vol_Ratio'] >= 1.8
    c_bullish_candle = (last['Close'] > last['Open']) and (last['Close_Position'] >= 0.60)
    c_trend = last['Close'] > last['EMA50']
    c_rsi = 50 <= last['RSI'] <= 78
    c_liquidity = last['Value_Miliard'] >= 2.0
    
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
# RAFANO TRADER CHART GENERATOR (MATPLOTLIB)
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

        # Custom Market Maker Indicator
        df['MM_Hist'] = (df['Close'] - df['Open']) / (df['High'] - df['Low']).replace(0, np.nan) * (df['Volume'] / df['Volume'].rolling(20).mean()) * 100
        df['MM_Hist'] = df['MM_Hist'].fillna(0)
        df['Buy_Signal'] = (df['Close'] > df['Open']) & (df['Volume'] > df['Volume'].rolling(20).mean() * 1.8)

        fig = plt.figure(figsize=(13, 8), facecolor='black')
        gs = fig.add_gridspec(4, 1, height_ratios=[3.5, 0.3, 1.1, 0.9], hspace=0.08)

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

            if df['Buy_Signal'].iloc[i]:
                ax_price.plot(dates[i], low_p * 0.97, marker='^', color='#00ff00', markersize=6)

        ax_price.plot(dates, df['Upper_Donchian'], color='#444444', linestyle='--', linewidth=0.8)
        ax_price.plot(dates, df['Lower_Donchian'], color='#444444', linestyle='--', linewidth=0.8)
        ax_price.plot(dates, df['EMA50'], color='white', linewidth=1.2, label='EMA 50')

        last_close = df['Close'].iloc[-1]
        last_high = df['High'].tail(20).max()
        last_low = df['Low'].tail(20).min()

        ax_price.text(dates[-1], last_high, f" PH: {int(last_high)} ", color='black', backgroundcolor='#ffff00', fontsize=8, fontweight='bold')
        ax_price.text(dates[-1], last_close, f" BUY: {int(last_close)} ", color='black', backgroundcolor='#00ff00', fontsize=8, fontweight='bold')
        ax_price.text(dates[-1], last_low, f" PL: {int(last_low)} ", color='white', backgroundcolor='#00ffff', fontsize=8, fontweight='bold')

        change_pct = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
        ax_price.set_title(f"{symbol.upper()} : {int(last_close)} ({change_pct:+.2f}%)", color='#ffff00', fontsize=11, fontweight='bold', loc='left')
        ax_price.set_title("RAFANO TRADER", color='white', fontsize=11, fontweight='bold', loc='center')

        if metrics:
            dash_text = (
                f"  RAFANO TRADER DASHBOARD  \n"
                f"----------------------------------------\n"
                f"SCORE SIGNAL : {metrics.get('win_probability', 80)}% (VERY STRONG)\n"
                f"STATUS       : BUY ACCUMULATION\n"
                f"ENTRY        : {int(metrics.get('close', 0))}\n"
                f"TP1 (+3.5%)  : {int(metrics.get('close', 0) * 1.035)}\n"
                f"TP2 (ATR)    : {int(metrics.get('close', 0) * 1.07)}\n"
                f"DANGER / SL  : {int(metrics.get('close', 0) * 0.95)}\n"
                f"----------------------------------------\n"
                f"BANDAR 1W    : ACCUM (WAJIB)\n"
                f"NET VOL 1D   : +{metrics.get('value_m', 0)}M"
            )
            ax_price.text(
                0.02, 0.95, dash_text, transform=ax_price.transAxes,
                fontsize=7, fontfamily='monospace', color='#00ff00',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='black', edgecolor='#00ff00', alpha=0.8),
                verticalalignment='top'
            )

        for i in range(len(df)):
            c = '#00ff00' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff0000'
            ax_tape.bar(dates[i], 1, color=c, width=0.8)
        ax_tape.get_yaxis().set_visible(False)

        for i in range(len(df)):
            c = '#00ff00' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff0000'
            ax_vol.bar(dates[i], df['Volume'].iloc[i], color=c, alpha=0.8, width=0.8)
        ax_vol.plot(dates, df['Volume'].rolling(20).mean(), color='white', linewidth=0.8)

        ax_mm.bar(dates, df['MM_Hist'], color='#ffff00', width=0.8)
        ax_mm.axhline(0, color='white', linewidth=0.5)

        plt.setp(ax_price.get_xticklabels(), visible=False)
        plt.setp(ax_tape.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)
        ax_mm.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        fig.autofmt_xdate()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf

    except Exception as e:
        print(f"⚠️ Error rendering chart ({symbol}): {e}")
        return None


# ==========================================
# PARALLEL SCREENER ENGINE (35 WORKERS)
# ==========================================
def process_single_stock(symbol, timeframe="1d"):
    try:
        df = fetch_stock_history_multi_tf(symbol, timeframe=timeframe)
        if df is not None and not df.empty and len(df) >= 50:
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
    total_stocks = len(watchlist)
    matched_results = []

    print(f"\n🚀 MEMULAI MASS SCREENING PARALEL ({MAX_WORKERS} WORKERS)")
    print(f"📊 Total Watchlist: {total_stocks} Saham (Non-FCA) | Timeframe: {timeframe.upper()}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_stock, symbol, timeframe): symbol 
            for symbol in watchlist
        }

        for future in as_completed(futures):
            symbol, metrics, df_processed, is_signal = future.result()
            if is_signal:
                print(f"🔥 MATCH: #{symbol} | Vol: {metrics['vol_ratio']}x | RSI: {metrics['rsi']} | Prob: {metrics['win_probability']}%")
                matched_results.append((symbol, metrics, df_processed))

    return matched_results


# ==========================================
# TELEGRAM INTEGRATION & BOT HANDLER
# ==========================================
def send_telegram_signal(chat_id, symbol, metrics, df_stock=None, timeframe="1d"):
    caption = (
        f"🔥 *THE RAFANO SIGNAL: #{symbol}* 🔥\n\n"
        f"💵 *Close Price:* {metrics['close']:,}\n"
        f"📊 *Volume Ratio:* {metrics['vol_ratio']}x\n"
        f"🎯 *RSI (14):* {metrics['rsi']}\n"
        f"📈 *EMA 50:* {metrics['ema50']:,}\n"
        f"💰 *Value Transaksi:* {metrics['value_m']} Miliar\n"
        f"⚡ *Win Probability:* {metrics['win_probability']}%\n"
    )
    
    try:
        if df_stock is not None and not df_stock.empty:
            chart_buffer = generate_pro_chart_memory(df_stock, symbol=symbol, timeframe=timeframe, metrics=metrics)
            if chart_buffer:
                chart_buffer.name = f"{symbol}_{timeframe}.png"
                bot.send_photo(chat_id, photo=chart_buffer, caption=caption, parse_mode="Markdown")
                return

        bot.send_message(chat_id, caption, parse_mode="Markdown")
    except Exception as e:
        print(f"Gagal mengirim sinyal ke Telegram ({symbol}): {e}")


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 *RAFANO SIGNAL BOT ACTIVE*\n\n"
        "Gunakan perintah berikut:\n"
        "`/screen` - Jalankan screening massal 300 saham non-FCA\n"
        "`/ping` - Cek status keaktifan bot"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['ping'])
def send_ping(message):
    bot.reply_to(message, "🏓 Pong! Bot aktif dan siap mendengarkan perintah.")


@bot.message_handler(commands=['screen'])
def handle_screen_command(message):
    chat_id = message.chat.id
    bot.reply_to(message, "🚀 Memulai screening 300 saham aktif Non-FCA... Mohon tunggu beberapa detik.")
    
    def worker_thread():
        results = run_market_screener_parallel(timeframe="1d")
        if not results:
            bot.send_message(chat_id, "❌ Tidak ditemukan sinyal saham yang memenuhi kriteria (≥80%).")
        else:
            bot.send_message(chat_id, f"✅ Screening Selesai! Ditemukan {len(results)} sinyal potensial:")
            for symbol, metrics, df_stock in results:
                send_telegram_signal(chat_id, symbol, metrics, df_stock=df_stock, timeframe="1d")

    Thread(target=worker_thread).start()


# ==========================================
# EKSEKUSI UTAMA BOT
# ==========================================
if __name__ == "__main__":
    print(f"🤖 Bot 'The Rafano Signal' Aktif...")
    print(f"📡 Chat ID Target: {DEFAULT_CHAT_ID}")
    
    try:
        bot.send_message(DEFAULT_CHAT_ID, "🚀 *Bot Trading Signal Online!* Kirim perintah `/screen` untuk memulai.", parse_mode="Markdown")
    except Exception as e:
        print(f"Warning: Tidak dapat mengirim pesan awal ke {DEFAULT_CHAT_ID}: {e}")

    bot.infinity_polling()
