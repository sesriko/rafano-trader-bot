import os
import io
import logging
import asyncio
from datetime import datetime, time
import pandas as pd
import numpy as np
import yfinance as yf
import requests

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==========================================
# 1. KONFIGURASI & LOGGING
# ==========================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ")
TELEGRAM_CHAT_ID = os.getenv("TARGET_CHAT_ID", "5660874676")

ARJUM_API_BASE_URL = "https://stock.arjum.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

COOLDOWN_SECONDS = 3600
signal_cooldowns = {}

# Daftar 300 Saham IHSG
TICKERS = [
    "AALI", "ABDA", "ABMM", "ACES", "ACST", "ADEL", "ADMF", "ADMG", "ADRO", "AGAR",
    "AGII", "AGRO", "AGRS", "AHAP", "AIMS", "AISA", "AKRA", "AKSI", "ALDO", "ALKA",
    "ALMI", "ALTO", "AMAR", "AMFG", "AMIN", "AMRT", "ANDI", "ANJT", "ANTM", "APIC",
    "APII", "APLI", "APLN", "ARCI", "ARGO", "ARKA", "ARMY", "ARTO", "ASBI", "ASDM",
    "ASGR", "ASII", "ASJT", "ASMI", "ASRI", "ASRM", "ASSA", "ATIC", "AUTO", "AVIA",
    "BABP", "BACA", "BAJA", "BALI", "BANK", "BAPA", "BATA", "BBCA", "BBHI", "BBKP",
    "BBLD", "BBMD", "BBNI", "BBRI", "BBSB", "BBTN", "BBYB", "BCIC", "BCIP", "BDMN",
    "BEKS", "BEST", "BFIN", "BGTG", "BHAT", "BHIT", "BIKA", "BINA", "BIPI", "BIRD",
    "BISDE", "BISC", "BJBR", "BJTM", "BKDP", "BKSL", "BLAZ", "BLTZ", "BLUE", "BMAS",
    "BMHS", "BMRI", "BMTR", "BNBR", "BNGA", "BNII", "BNLI", "BOBA", "BOLA", "BOLT",
    "BOSS", "BPFI", "BPII", "BRPT", "BSDE", "BSIM", "BSWD", "BTEK", "BTPS", "BSSR",
    "BREN", "BRMS", "BRIS", "BUKA", "BUKK", "BULL", "BUMI", "BVIC", "BWPT", "BYAN",
    "CAKK", "CAMP", "CASA", "CASH", "CASS", "CEKA", "CENT", "CFIN", "CINT", "CITA",
    "CITY", "CLPI", "CMNP", "CMPP", "CNKO", "CNTX", "COWL", "CPIN", "CPRI", "CPRO",
    "CSAP", "CSIS", "CSRA", "CTBN", "CTRA", "CTRP", "DART", "DEWA", "DEXA", "DFAM",
    "DGIK", "DIGI", "DILD", "DIVA", "DKFT", "DLTA", "DMAS", "DNAR", "DNET", "DOID",
    "DPNS", "DSFI", "DSNG", "DSSA", "DUTI", "DVLA", "DWGL", "EAST", "ECII", "ENRG",
    "EPMT", "ERAA", "ERTX", "ESSA", "ESTI", "ETWA", "EXCL", "FAST", "FASW", "FISH",
    "FPNI", "FUTR", "GAAA", "GDST", "GEMA", "GGRM", "GIAA", "GJTL", "GLOB", "GLVA",
    "GOOD", "GOTO", "GPRA", "GSMF", "GTBO", "GWSA", "GZCO", "HATM", "HDFA", "HEAL",
    "HERO", "HEXA", "HITS", "HMSP", "HOKI", "HOME", "HOPE", "HRUM", "IATA", "IBFN",
    "IBST", "ICBP", "ICON", "IDPR", "IGAR", "IIKP", "IKAI", "IKBI", "IMPC", "INAF",
    "INCF", "INCI", "INDF", "INDY", "INKP", "INPC", "INPP", "INRU", "INTA", "INTD",
    "INTP", "IPCC", "IPCM", "IPOL", "ISAT", "ISSP", "ITMA", "ITMG", "JAST", "JAWA",
    "JECC", "JKSW", "JPFA", "JRPT", "JSMR", "JSPT", "JTPE", "KAEF", "KARW", "KBLI",
    "KBLM", "KBAG", "KDSI", "KIAS", "KICI", "KIJA", "KKGI", "KLBF", "KMTR", "KOBX",
    "KOIN", "KONI", "KOPI", "KPAL", "KPAS", "KPEI", "KPIG", "KRAS", "KREN", "LPCK",
    "LPIN", "LPKR", "LPLI", "LPPF", "LTLS", "LUXI", "MAIN", "MAPA", "MAPI", "MARK",
    "MASA", "MAYA", "MBAP", "MBSS", "MDLN", "MEDC", "METR", "MFIN", "MGNA", "MICE",
    "MIDI", "MIKA", "MLBI", "MLIA", "MLPT", "MMSD", "MNCN", "MPPA", "MPMX", "MTDL",
    "MTLA", "MYOR", "NATO", "NCLK", "NETV", "NIKL", "NISP", "PANR", "PBRX", "PGAS",
    "PGJO", "PNBN", "PNBS", "PNIN", "PNLF", "POLY", "POWR", "PRDA", "PTBA", "PTPP",
    "PSSI", "PWON", "PYFA", "RAJA", "RALS", "RANC", "RBMS", "RDMD", "RELI", "RICY",
    "RIGS", "RISE", "ROTI", "SAFE", "SAME", "SAMF", "SAPX", "SCCO", "SCMA", "SDPC",
    "SGER", "SGRO", "SHID", "SILO", "SIMP", "SINO", "SIPD", "SKBM", "SKLT", "SMBR",
    "SMDR", "SMGR", "SMKL", "SMMA", "SMRA", "SMSM", "SOUL", "SPTO", "SRIL", "SRTG",
    "SSMS", "SSUC", "STAA", "SUPR", "TALF", "TAPA", "TAPG", "TBIG", "TBLA", "TCID",
    "TELE", "TFCO", "TFIN", "TLKM", "TMAS", "TMPO", "TNCA", "TOBA", "TOTAL", "TPIA",
    "TPMA", "TROW", "TSPC", "TSRI", "TOTO", "UCID", "ULTJ", "UNIC", "UNIQ", "UNTR",
    "UNVR", "URBN", "VBNI", "VRNA", "WAPO", "WEGE", "WIFI", "WIIM", "WIMD", "WINS",
    "WIRT", "WMIC", "WOOD", "WOWS", "WSKT", "WTON", "YPAS", "YULE", "ZBRA"
]

# ==========================================
# 2. HELPER UTAMA & DATA FETCHING
# ==========================================
def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    session1 = time(9, 0) <= current_time <= time(12, 0)
    session2 = time(13, 30) <= current_time <= time(16, 0)
    return session1 or session2

def filter_signals_with_cooldown(signals: list) -> list:
    now = datetime.now()
    filtered = []
    for sig in signals:
        ticker = sig['ticker']
        last_time = signal_cooldowns.get(ticker)
        if last_time is None or (now - last_time).total_seconds() > COOLDOWN_SECONDS:
            signal_cooldowns[ticker] = now
            filtered.append(sig)
    return filtered

def fetch_stock_history_multi_tf(ticker: str, timeframe: str = "Daily") -> pd.DataFrame:
    try:
        # Coba ambil data dari API Arjum jika tersedia, fallback ke yfinance
        if timeframe == "Daily":
            try:
                url = f"{ARJUM_API_BASE_URL}/stock/{ticker}"
                res = requests.get(url, headers=HEADERS, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    # Sesuaikan parsing jika endpoint Arjum mengembalikan list/dict historis
                    # Jika format JSON tidak langsung cocok, fallback ke yfinance di bawah
            except Exception:
                pass

        symbol = f"{ticker}.JK" if not ticker.endswith(".JK") else ticker
        period = "1y" if timeframe == "Daily" else "1mo"
        interval = "1d" if timeframe == "Daily" else ("5m" if timeframe == "5m" else "15m")
        
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.rename(columns={
            'Open': 'Open', 'High': 'High', 'Low': 'Low', 
            'Close': 'Close', 'Volume': 'Volume'
        })
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None

# ==========================================
# 3. INDIKATOR & VSA METRICS
# ==========================================
def calculate_vsa_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['V1'] = df['Volume'].rolling(window=20).mean()
    
    # Perhitungan EMA Standar (13, 20, 50, 200)
    df['EMA13'] = df['Close'].ewm(span=13, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # VSA Metrics
    price_range = df['High'] - df['Low']
    price_range = price_range.replace(0, 0.001)
    df['Buy_Ratio'] = np.where(df['Close'] >= df['Open'], 
                              0.5 + 0.5 * ((df['Close'] - df['Open']) / price_range),
                              0.5 * (1 - (df['Open'] - df['Close']) / price_range))
    
    df['Net_Val_VSA'] = df['Volume'] * (df['Buy_Ratio'] - (1 - df['Buy_Ratio'])) * df['Close']
    df['AvgPrice'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['MM_Flow'] = (df['Close'] - df['EMA20']) / df['EMA20'] * 1000
    return df

def check_volume_spike_signal(df: pd.DataFrame, ticker: str) -> dict:
    if len(df) < 50:
        return None
        
    df = calculate_vsa_metrics(df)
    last = df.iloc[-1]
    
    val_trans = last['Close'] * last['Volume']
    if last['Close'] <= 50 or val_trans < 500_000_000:
        return None
        
    cond_trend = last['Close'] > last['EMA50']
    cond_rsi = last['RSI'] <= 75
    cond_vol = last['Volume'] >= (2.0 * last['V1'])
    cond_vsa = df['Net_Val_VSA'].tail(5).sum() > 0
    cond_candle = (last['Buy_Ratio'] > 0.65) and (last['Close'] > last['Open'])
    
    if cond_trend and cond_rsi and cond_vol and cond_vsa and cond_candle:
        score = int(last['Buy_Ratio'] * 40 + (last['Volume'] / last['V1']) * 20 + 20)
        score = min(score, 100)
        
        rating = "STRONG BUY" if score >= 80 else "BUY"
        return {
            'ticker': ticker,
            'price': int(last['Close']),
            'volume': int(last['Volume']),
            'vol_avg': int(last['V1']),
            'rsi': round(last['RSI'], 1),
            'buy_ratio': round(last['Buy_Ratio'] * 100, 1),
            'score': score,
            'rating': rating
        }
    return None

# ==========================================
# 4. CHART GENERATOR (BRANDING: RAFANO TRADER)
# ==========================================
def generate_pro_chart(df: pd.DataFrame, ticker: str, period: str = "Daily") -> io.BytesIO:
    df = df.copy()
    if 'EMA13' not in df.columns:
        df = calculate_vsa_metrics(df)
        
    fig = plt.figure(figsize=(14, 8), facecolor='black')
    gs = gridspec.GridSpec(4, 1, height_ratios=[3.5, 1, 0.8, 0.8], hspace=0.05)
    
    ax_main = plt.subplot(gs[0])
    ax_vol = plt.subplot(gs[1], sharex=ax_main)
    ax_nbsa = plt.subplot(gs[2], sharex=ax_main)
    ax_mm = plt.subplot(gs[3], sharex=ax_main)
    
    for ax in [ax_main, ax_vol, ax_nbsa, ax_mm]:
        ax.set_facecolor('black')
        ax.tick_params(colors='white', labelsize=8)
        ax.grid(True, color='#222222', linestyle='--', linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_color('#444444')

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else last_row
    chg_pct = ((last_row['Close'] - prev_row['Close']) / prev_row['Close']) * 100
    
    # --- HEADER TOP (BRANDING: RAFANO TRADER) ---
    title_left = f"{ticker} :  {int(last_row['Close'])} ({chg_pct:+.2f}%)"
    ax_main.text(0.01, 1.04, title_left, transform=ax_main.transAxes, color='yellow', fontsize=13, fontweight='bold')
    ax_main.text(0.50, 1.04, "RAFANO TRADER", transform=ax_main.transAxes, color='white', fontsize=13, fontweight='bold', ha='center')
    
    date_str = last_row.name.strftime('%d %b %Y') if isinstance(last_row.name, pd.Timestamp) else str(last_row.name)
    ax_main.text(0.99, 1.04, f"{period} {date_str}\nCommand BOT /{ticker}", transform=ax_main.transAxes, color='yellow', fontsize=8, ha='right')

    # --- MAIN CANDLESTICK ---
    x_axis = np.arange(len(df))
    width = 0.6
    
    up = df['Close'] >= df['Open']
    down = df['Close'] < df['Open']
    
    ax_main.vlines(x_axis[up], df['Low'][up], df['High'][up], color='#00FF00', linewidth=1)
    ax_main.vlines(x_axis[down], df['Low'][down], df['High'][down], color='#FF0000', linewidth=1)
    
    for i in range(len(df)):
        open_p, close_p = df['Open'].iloc[i], df['Close'].iloc[i]
        color = '#00FF00' if close_p >= open_p else '#FF0000'
        ax_main.add_patch(Rectangle((i - width/2, min(open_p, close_p)), width, abs(close_p - open_p), color=color, fill=True))

    # EMA Lines Sesuai Tampilan
    ax_main.plot(x_axis, df['EMA13'], color='orange', linewidth=1.2, label='EMA 13')
    ax_main.plot(x_axis, df['EMA20'], color='red', linewidth=1.2, label='EMA 20')
    ax_main.plot(x_axis, df['EMA50'], color='white', linewidth=1.2, label='EMA 50')
    ax_main.plot(x_axis, df['EMA200'], color='purple', linewidth=1.5, label='EMA 200')

    # Info Stats Overlay (Kiri Atas)
    vchg_1d = (last_row['Volume'] / df['Volume'].iloc[-2]) if len(df) > 1 else 1.0
    vchg_5d = (last_row['Volume'] / df['Volume'].tail(5).mean())
    
    info_text = (
        f"Avg Price   : {last_row.get('AvgPrice', last_row['Close']):.1f}\n"
        f"Vchg 1 Day  : {vchg_1d:.1f}x\n"
        f"Vchg 5 Days : {vchg_5d:.1f}x\n"
        f"Speed       : SLOW\n"
        f"Power       : TURBO\n"
        f"Safety      : BAD\n"
        f"\n"
        f"EMA 13      : {last_row['EMA13']:.1f}\n"
        f"EMA 20      : {last_row['EMA20']:.1f}\n"
        f"EMA 50      : {last_row['EMA50']:.1f}\n"
        f"EMA 200     : {last_row['EMA200']:.1f}"
    )
    ax_main.text(0.01, 0.95, info_text, transform=ax_main.transAxes, color='white', fontsize=7.5, 
                 family='monospace', verticalalignment='top', bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.6, edgecolor='none'))

    # Right Price Box
    curr_close = int(last_row['Close'])
    ax_main.text(1.005, curr_close, f" {curr_close} ", transform=ax_main.get_yaxis_transform(),
                 color='white', backgroundcolor='#555555', fontsize=8, fontweight='bold', va='center')

    # --- VOLUME SUBPLOT ---
    vol_colors = ['#00FF00' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#FF0000' for i in range(len(df))]
    ax_vol.bar(x_axis, df['Volume'], color=vol_colors, width=width, alpha=0.8)
    if 'V1' in df.columns:
        ax_vol.plot(x_axis, df['V1'], color='white', linewidth=1)
        
    buy_pct = int(last_row.get('Buy_Ratio', 0.65) * 100)
    sell_pct = 100 - buy_pct
    net_vol = last_row.get('Net_Val_VSA', 0)
    net_5d = df['Net_Val_VSA'].tail(5).sum() if 'Net_Val_VSA' in df.columns else net_vol
    
    vol_text = f"Buy Percent = {buy_pct}%   Sell Percent = {sell_pct}%   Net Vol = {net_vol:,.0f}   Net 5D = {net_5d:,.0f}"
    ax_vol.text(0.01, 0.85, vol_text, transform=ax_vol.transAxes, color='yellow', fontsize=7.5, fontweight='bold')

    # --- NBSA SUBPLOT ---
    nbsa_val = df['Net_Val_VSA'] if 'Net_Val_VSA' in df.columns else df['Volume'] * (df['Close'] - df['Open'])
    nbsa_colors = ['#00FFFF' if v >= 0 else '#FF0000' for v in nbsa_val]
    ax_nbsa.bar(x_axis, nbsa_val, color=nbsa_colors, width=width)
    ax_nbsa.text(0.01, 0.75, "NBSA Rp / Value Indicator", transform=ax_nbsa.transAxes, color='white', fontsize=7)

    # --- MARKET MAKER SUBPLOT ---
    mm_val = df['MM_Flow'] if 'MM_Flow' in df.columns else np.zeros(len(df))
    ax_mm.bar(x_axis, mm_val, color='white', width=0.3, alpha=0.7)
    ax_mm.text(0.01, 0.75, "Market Maker", transform=ax_mm.transAxes, color='yellow', fontsize=7)

    # Formatting Sumbu X
    plt.setp(ax_main.get_xticklabels(), visible=False)
    plt.setp(ax_vol.get_xticklabels(), visible=False)
    plt.setp(ax_nbsa.get_xticklabels(), visible=False)
    
    step = max(1, len(df) // 6)
    ax_mm.set_xticks(x_axis[::step])
    ax_mm.set_xticklabels([df.index[i].strftime('%b') if isinstance(df.index[i], pd.Timestamp) else str(df.index[i]) for i in range(0, len(df), step)])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor='black', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf

# ==========================================
# 5. HANDLER TELEGRAM & BOT LOGIC
# ==========================================
async def process_chart_request(update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: str, period: str = "Daily"):
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        
        df = fetch_stock_history_multi_tf(ticker, timeframe=period)
        if df is None or df.empty:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Gagal mengambil data chart untuk {ticker}.")
            return

        df = calculate_vsa_metrics(df)
        chart_buf = generate_pro_chart(df, ticker, period=period)
        
        caption = f"📊 **RAFANO TRADER Chart: {ticker} ({period})**\nPrice: Rp{int(df['Close'].iloc[-1])}"
        await context.bot.send_photo(chat_id=chat_id, photo=chart_buf, caption=caption, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error processing chart request for {ticker}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Terjadi kesalahan saat membuat chart {ticker}.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **RAFANO TRADER Bot Active!**\n\n"
        "Bot akan otomatis mengirim sinyal *Volume Spike & Akumulasi Bandar* pada jam bursa.\n"
        "Gunakan command `/chart <TICKER>` untuk melihat chart saham secara langsung."
    )

async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Gunakan format: `/chart <TICKER>` (contoh: `/chart BIPI`)")
        return
    ticker = context.args[0].upper()
    await process_chart_request(update, context, ticker, period="Daily")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    action = data[0]
    ticker = data[1]
    
    if action == "chart":
        period = data[2] if len(data) > 2 else "Daily"
        await process_chart_request(update, context, ticker, period=period)

# ==========================================
# 6. CRON TASK & MAIN RUNNER
# ==========================================
async def market_screener_job(app):
    while True:
        try:
            if is_market_open():
                logger.info("Menjalankan Auto Screener IHSG (RAFANO TRADER)...")
                detected_signals = []
                
                for ticker in TICKERS:
                    df = fetch_stock_history_multi_tf(ticker, timeframe="Daily")
                    if df is not None and not df.empty:
                        sig = check_volume_spike_signal(df, ticker)
                        if sig:
                            detected_signals.append(sig)
                
                valid_signals = filter_signals_with_cooldown(detected_signals)
                
                for sig in valid_signals:
                    msg = (
                        f"🚨 **SINYAL AKUMULASI (RAFANO TRADER)** 🚨\n\n"
                        f"Saham: **{sig['ticker']}**\n"
                        f"Harga: Rp{sig['price']}\n"
                        f"Rating: **{sig['rating']}** (Score: {sig['score']}%)\n"
                        f"Buy Ratio: {sig['buy_ratio']}%\n"
                        f"RSI: {sig['rsi']}\n"
                    )
                    keyboard = [
                        [
                            InlineKeyboardButton("Chart Daily", callback_data=f"chart_{sig['ticker']}_Daily"),
                            InlineKeyboardButton("Chart 15M", callback_data=f"chart_{sig['ticker']}_15m")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                logger.info("Bursa tutup. Screener standby...")
                
        except Exception as e:
            logger.error(f"Error pada Screener Job: {e}")
            
        await asyncio.sleep(300)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("chart", chart_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    
    loop = asyncio.get_event_loop()
    loop.create_task(market_screener_job(app))
    
    logger.info("Bot Telegram RAFANO TRADER Berhasil Dijalankan!")
    app.run_polling()

if __name__ == "__main__":
    main()
