import os
import time
import logging
import datetime
import threading
import requests
import pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
from concurrent.futures import ThreadPoolExecutor

try:
    import yfinance as yf
except ImportError:
    yf = None

# ==========================================
# KONFIGURASI ZONA WAKTU (WIB)
# ==========================================
TIMEZONE_WIB = pytz.timezone('Asia/Jakarta')

def get_now_wib():
    return datetime.datetime.now(TIMEZONE_WIB)

# ==========================================
# FILTER LOGS TERMINAL
# ==========================================
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# ==========================================
# KONFIGURASI BOT TELEGRAM & API
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "5660874676")

ARJUM_API_BASE_URL = "https://stock.arjum.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SCREENER_ACTIVE = True

# ==========================================
# COOLDOWN TRACKER (60 MENIT)
# ==========================================
LAST_SENT_SIGNALS = {}
COOLDOWN_SECONDS = 3600  
LAST_RESET_DATE = ""

def filter_signals_with_cooldown(signals):
    global LAST_RESET_DATE, LAST_SENT_SIGNALS
    current_time = time.time()
    today_str = get_now_wib().strftime('%Y-%m-%d')

    if LAST_RESET_DATE != today_str:
        LAST_SENT_SIGNALS.clear()
        LAST_RESET_DATE = today_str

    filtered_list = []
    for sig in signals:
        sym = sig['symbol']
        last_sent = LAST_SENT_SIGNALS.get(sym, 0)

        if (current_time - last_sent) >= COOLDOWN_SECONDS:
            filtered_list.append(sig)
            LAST_SENT_SIGNALS[sym] = current_time

    return filtered_list

# Universe 300 Saham IHSG
TOP_300_IHSG = [
    "ACES", "ADHI", "ADMR", "ADRO", "AGRO", "AGRS", "AHAP", "AISA", "AKRA", "ALDO", 
    "AMAR", "AMFG", "AMMM", "AMMN", "AMMS", "AMRT", "ANDI", "ANJT", "ANTM", "APEX", 
    "APIC", "APLN", "ARCI", "ARKO", "ARTO", "ASBI", "ASGR", "ASHA", "ASII", "ASRI", 
    "AUTO", "AVIA", "AXIO", "BABP", "BACA", "BALI", "BANK", "BAPA", "BBCA", "BBHI", 
    "BBKP", "BBLD", "BBMD", "BBNI", "BBRI", "BBRM", "BBTN", "BBYB", "BCIC", "BDMN", 
    "BEST", "BFIN", "BHIT", "BIKE", "BIPI", "BIPP", "BIRD", "BISI", "BJBR", "BJTM", 
    "BKSL", "BLUE", "BMAS", "BMBL", "BMHS", "BMRI", "BMTR", "BNBR", "BNGA", "BNII", 
    "BNLI", "BOLT", "BRAM", "BRMS", "BRPT", "BSDE", "BSIM", "BSSR", "BSWD", "BTEC", 
    "BTON", "BUKA", "BULL", "BUMI", "BVIC", "BWPT", "BYAN", "CARE", "CARS", "CASA", 
    "CASS", "CEKA", "CENT", "CFIN", "CINT", "CITA", "CITY", "CLPI", "CMNP", "CMPP", 
    "CMRY", "CNTX", "COAL", "CPIN", "CPRI", "CPRO", "CRAB", "CSAP", "CSRA", "CTBN", 
    "CTRA", "DART", "DEWA", "DGIK", "DIGI", "DILD", "DIVA", "DKFT", "DLTA", "DMAS", 
    "DNAR", "DNET", "DPNS", "DRMA", "DSNG", "DUTI", "DVLA", "ECII", "ELSA", "ELTY", 
    "EMTK", "ENRG", "ERAA", "ESSA", "FASW", "FILM", "FIRE", "FPNI", "FUTR", "GDST", 
    "GEMS", "GIAA", "GJTL", "GNKF", "GOTO", "GPRA", "GRPH", "GSMF", "GTBO", "GWSA", 
    "GZCO", "HAIS", "HATM", "HDIT", "HEAL", "HERO", "HEXA", "HILL", "HITS", "HMSP", 
    "HOKI", "HOME", "HOPE", "HRUM", "IATA", "IBFN", "IBOS", "ICBP", "ICON", "IDPR", 
    "IFSH", "IGAR", "IIKP", "IKAI", "IKBI", "IMPC", "INAF", "INAI", "INCF", "INCI", 
    "INDF", "INKP", "INPC", "INPP", "INTP", "IPCC", "IPPE", "IRRA", "ISAT", "ISSP", 
    "ITMG", "JARR", "JECC", "JAST", "JIHD", "JKON", "JSPT", "JPFA", "JRPT", "JSMR", 
    "JTEX", "KAEF", "KAST", "KBLI", "KBLM", "KDSI", "KEEN", "KIJA", "KKGI", "KLBF", 
    "KMDS", "KMTR", "KOBX", "KOPI", "KPIG", "KRAS", "LAJU", "LPCK", "LPKR", "LPLI", 
    "LPPF", "LTLS", "MAHA", "MAPA", "MAPI", "MARK", "MASB", "MBAP", "MBMA", "MBTO", 
    "MCOR", "MDKA", "MEDC", "MGRO", "MLPT", "MMLP", "MNCN", "MPOW", "MPPA", "MRAT", 
    "MSIN", "MTDL", "MTLA", "MYOR", "NANO", "NCKL", "NELI", "NICK", "NIKL", "NISP", 
    "NSIC", "OASA", "OKAS", "OMRE", "PALM", "PANI", "PANR", "PBSD", "PBID", "PGLI", 
    "PGAS", "PGUN", "PMMP", "PUDP", "PNBS", "PNIN", "PNLF", "POLI", "POLL", "POLY", 
    "PORT", "POWR", "PPGL", "PPRE", "PTBA", "PTPP", "PTRO", "PWON", "PYFA", "RAJA", 
    "RALS", "RANC", "RBMS", "RDTX", "RELI", "RICY", "RIGS", "RMKO", "ROTI", "SAFE", 
    "SAMF", "SAME", "SAMR", "SBAT", "SCCO", "SCMA", "SDMU", "SFAN", "SGER", "SGRO", 
    "SILO", "SIMP", "SINO", "SIPD", "SKLT", "SMAR", "SMDM", "SMDR", "SMGR", "SMRA", 
    "SMOT", "SMSM", "SOCI", "SPTO", "SRTG", "SSIA", "SSMS", "STAA", "TAPG", "TBLA", 
    "TBIG", "TEBE", "TFCO", "TINU", "TINS", "TKIM", "TLDN", "TLKM", "TMAS", "TOBA", 
    "TPIA", "TRIM", "TRIS", "TRST", "TRUK", "TSPC", "TOTO", "UANG", "UCID", "ULTJ", 
    "UNIC", "UNIQ", "UNTR", "UNVR", "VICI", "VINS", "VKTR", "VRNA", "WAPO", "WEGE", 
    "WIFI", "WIIM", "WINS", "WIRT", "WOOD", "WSBP", "WSIH", "WTON", "YPAS", "YULE", 
    "ZBRA", "ZINC"
]

# ==========================================
# HELPER FRAKSI HARGA IHSG & BURSA
# ==========================================
def round_to_ihsg_fraction(price):
    if pd.isna(price) or price <= 0: return 0
    price = float(price)
    if price < 200: tick = 1
    elif price < 500: tick = 2
    elif price < 2000: tick = 5
    elif price < 5000: tick = 10
    else: tick = 25
    return int(round(price / tick) * tick)

def safe_int(val, default=0):
    try:
        if pd.isna(val) or np.isinf(val): return default
        return int(val)
    except Exception:
        return default

def format_large_number(val, show_sign=False):
    if pd.isna(val) or val == 0: return "0"
    abs_val = abs(val)
    sign = "+" if (show_sign and val > 0) else ("-" if val < 0 else "")
    if abs_val >= 1_000_000_000: return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{sign}{abs_val / 1_000_000:,.0f}M"
    elif abs_val >= 1_000: return f"{sign}{abs_val / 1_000:,.0f}K"
    else: return f"{sign}{val:,.0f}"

def is_market_open():
    now = get_now_wib()
    weekday = now.weekday()
    if weekday >= 5: return False
    current_time = now.time()
    if weekday == 4:
        s1_start, s1_end = datetime.time(9, 0), datetime.time(11, 30)
        s2_start, s2_end = datetime.time(14, 0), datetime.time(15, 50)
    else:
        s1_start, s1_end = datetime.time(9, 0), datetime.time(12, 0)
        s2_start, s2_end = datetime.time(13, 30), datetime.time(15, 50)
    return (s1_start <= current_time <= s1_end) or (s2_start <= current_time <= s2_end)

# ==========================================
# METRIK RSI, VSA, & SCORE
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 0.00001)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50)

def calculate_vsa_metrics(df):
    price_range = (df['High'] - df['Low']).replace(0, 0.1)
    body_move = df['Close'] - df['Open']
    buy_ratio = np.where(
        price_range <= 0.1, 0.50,
        np.where(df['Close'] >= df['Open'], 
                 0.55 + (body_move / price_range) * 0.4, 
                 0.45 + (body_move / price_range) * 0.4)
    )
    buy_ratio = np.clip(buy_ratio, 0.05, 0.95)
    df['Vol_Buy'] = df['Volume'] * buy_ratio
    df['Vol_Sell'] = df['Volume'] - df['Vol_Buy']
    df['Net_Vol_VSA'] = df['Vol_Buy'] - df['Vol_Sell']
    df['Net_Val_VSA'] = df['Net_Vol_VSA'] * df['Close']
    return df, buy_ratio

def calculate_buy_signal_strength(df):
    if len(df) < 20: return 0, "NO DATA"
    last_row = df.iloc[-1]
    last_close, last_open, last_vol = last_row['Close'], last_row['Open'], last_row['Volume']
    avg_vol_v1 = last_row['V1']
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    ema_50 = df['EMA50'].iloc[-1]
    df, buy_ratios = calculate_vsa_metrics(df)
    last_buy_ratio = buy_ratios[-1]
    net_5d_val = df['Net_Val_VSA'].tail(5).sum()

    score = 0
    if last_close > ema_50: score += 25
    vol_multiple = last_vol / avg_vol_v1 if avg_vol_v1 > 0 else 0
    if vol_multiple >= 2.5: score += 25
    elif vol_multiple >= 2.0: score += 20
    elif vol_multiple >= 1.8: score += 15

    if last_buy_ratio >= 0.75: score += 20
    elif last_buy_ratio >= 0.65: score += 15
    elif last_buy_ratio >= 0.55: score += 10

    if net_5d_val > 0: score += 20
    if last_close > last_open: score += 10

    if score >= 85: label = "VERY STRONG"
    elif score >= 70: label = "STRONG BUY"
    elif score >= 50: label = "WEAK BUY"
    else: label = "NO SIGNAL"

    return score, label

def check_volume_spike_signal(df, symbol, threshold_multiplier=2.0, min_value_traded=500_000_000):
    if len(df) < 20: return False, {}
    last_row = df.iloc[-1]
    last_close, last_vol = last_row['Close'], last_row['Volume']
    if last_close <= 50 or last_vol == 0: return False, {}
    value_traded = last_close * last_vol
    if value_traded < min_value_traded: return False, {}

    df, buy_ratios = calculate_vsa_metrics(df)
    avg_vol_v1, last_open, last_buy_ratio = last_row['V1'], last_row['Open'], buy_ratios[-1]
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI14'] = calculate_rsi(df['Close'], period=14)
    
    ema_50 = df['EMA50'].iloc[-1]
    last_rsi = round(df['RSI14'].iloc[-1], 2)
    net_5d_val = df['Net_Val_VSA'].tail(5).sum()
    is_bandar_accum = net_5d_val > 0

    if (last_close > ema_50) and (last_rsi <= 75) and (last_vol >= (avg_vol_v1 * threshold_multiplier)) and is_bandar_accum and (last_buy_ratio > 0.65) and (last_close > last_open):
        vol_multiple = last_vol / avg_vol_v1 if avg_vol_v1 > 0 else 0
        change_pct = ((last_close / df['Close'].iloc[-2]) - 1) * 100 if len(df) > 1 else 0.0
        score, score_label = calculate_buy_signal_strength(df)

        return True, {
            "symbol": symbol, "close": safe_int(last_close), "change_pct": change_pct,
            "vol_multiple": vol_multiple, "buy_ratio": safe_int(last_buy_ratio * 100),
            "volume": safe_int(last_vol), "value_traded": value_traded,
            "bandar_5d_val": net_5d_val, "rsi": last_rsi, "score": score, "score_label": score_label
        }
    return False, {}

# ==========================================
# CHART GENERATOR (RAFANO TRADER DESIGN)
# ==========================================
def generate_pro_chart(df, symbol="BIPI", timeframe="1d", sector_info="Astrindo Nusantara Infrastruktur Tbk. | Energy, Coal", output_filename="chart_output.png"):
    try:
        col_map = {c: str(c).lower().strip() for c in df.columns}
        df.rename(columns=col_map, inplace=True)
        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 
            'close': 'Close', 'volume': 'Volume',
            'date': 'Date', 'datetime': 'Date', 'time': 'Date', 't': 'Date'
        }, inplace=True)

        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

        df = df.ffill().bfill()
        if isinstance(df.index, pd.DatetimeIndex): df = df.sort_index()

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # EMA Indikator
        df['EMA13'] = df['Close'].ewm(span=13, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
        df['V2'] = df['Volume'].rolling(50, min_periods=1).mean()

        df, buy_ratios = calculate_vsa_metrics(df)
        net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
        net_vol_today = df['Net_Vol_VSA'].iloc[-1]
        
        # NBSA & MM Data Dinamis
        df['NBSA'] = df['Net_Val_VSA']
        if 'MM' not in df.columns:
            df['MM'] = (df['Close'] - df['EMA50']) / df['EMA50'] * 1000 - 44.05

        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high = df['High'].iloc[-1]
        last_low = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close
        change_pct = ((last_close - prev_close) / prev_close) * 100

        plt.style.use('dark_background')
        fig = plt.figure(figsize=(18, 10), dpi=300, facecolor='#000000')
        
        # Layout Subpanel 4 Grid
        gs = gridspec.GridSpec(4, 1, height_ratios=[4.5, 1.2, 0.7, 0.8], hspace=0.02)

        ax_main = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax_main)
        ax_nbsa = fig.add_subplot(gs[2], sharex=ax_main)
        ax_mm = fig.add_subplot(gs[3], sharex=ax_main)

        fig.subplots_adjust(left=0.03, right=0.94, top=0.92, bottom=0.05)

        for ax in [ax_main, ax_vol, ax_nbsa, ax_mm]:
            ax.set_facecolor('#000000')
            ax.grid(True, color='#222222', linestyle=':', linewidth=0.5)
            ax.tick_params(colors='white', labelsize=9)
            ax.yaxis.tick_right()

        x_indices = np.arange(len(df))
        color_up, color_down = '#00ff00', '#ff0000'

        # Render Candlesticks
        for i in range(len(df)):
            open_p, high_p, low_p, close_p = df['Open'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['Close'].iloc[i]
            if close_p >= open_p:
                body_top, body_bottom = close_p, open_p
                body_height = max(0.2, close_p - open_p)
                ax_main.plot([i, i], [high_p, body_top], color=color_up, linewidth=1.0)
                ax_main.plot([i, i], [low_p, body_bottom], color=color_up, linewidth=1.0)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1.0, edgecolor=color_up, facecolor='none')
                ax_main.add_patch(rect)
            else:
                body_top, body_bottom = open_p, close_p
                body_height = max(0.2, open_p - close_p)
                ax_main.plot([i, i], [low_p, high_p], color=color_down, linewidth=1.0)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1.0, edgecolor=color_down, facecolor=color_down)
                ax_main.add_patch(rect)

        # Plot Garis EMA
        ax_main.plot(x_indices, df['EMA13'], color='#ffff00', linewidth=1.2, label='EMA 13')
        ax_main.plot(x_indices, df['EMA20'], color='#ff0000', linewidth=1.2, label='EMA 20')
        ax_main.plot(x_indices, df['EMA50'], color='#ffffff', linewidth=1.3, label='EMA 50')
        ax_main.plot(x_indices, df['EMA200'], color='#a020f0', linewidth=1.6, label='EMA 200')

        # Header Atas
        fig.text(0.03, 0.965, f"{symbol} :    {safe_int(last_close)} ({change_pct:+.2f}%)", color='#ffff00', fontsize=15, fontweight='bold')
        fig.text(0.03, 0.945, f"{sector_info}", color='#888888', fontsize=8.5)
        fig.text(0.50, 0.965, "RAFANO TRADER", color='#ffffff', fontsize=16, fontweight='bold', ha='center')
        
        last_date_str = get_now_wib().strftime('%d %b %Y')
        fig.text(0.94, 0.965, f"Daily {last_date_str}", color='#ffffff', fontsize=10, fontweight='bold', ha='right')

        sub_info_ohlc = f"High:{safe_int(last_high)}    Low:{safe_int(last_low)}    Open:{safe_int(last_open)}    Volume:{safe_int(last_vol):,}    V1:{safe_int(df['V1'].iloc[-1]):,}    V2:{safe_int(df['V2'].iloc[-1]):,}"
        fig.text(0.03, 0.930, sub_info_ohlc, color='#00ffff', fontsize=8.5, fontfamily='monospace')

        # Left Panel Overlay
        avg_price = (last_high + last_low + last_close) / 3
        stat_left = (
            f"Avg Price    : {avg_price:.1f}\n"
            f"Vchg 1 Day   : 1.3 x\n"
            f"Vchg 5 Days  : 0.3 x\n"
            f"Speed        : SLOW\n"
            f"Power        : TURBO\n"
            f"Safety       : BAD\n"
            f"\n"
            f"EMA 13       : {df['EMA13'].iloc[-1]:.1f}\n"
            f"EMA 20       : {df['EMA20'].iloc[-1]:.1f}\n"
            f"EMA 50       : {df['EMA50'].iloc[-1]:.1f}\n"
            f"EMA 200      : {df['EMA200'].iloc[-1]:.1f}"
        )
        ax_main.text(0.01, 0.96, stat_left, transform=ax_main.transAxes, verticalalignment='top', horizontalalignment='left',
                     fontfamily='monospace', fontsize=8, color='#ffffff',
                     bbox=dict(boxstyle='square,pad=0.2', facecolor='#000000', alpha=0.5, edgecolor='none'))

        # Right Price Tag
        last_ema200 = df['EMA200'].iloc[-1]
        ax_main.text(1.005, last_ema200, f" EMA 200 ", transform=ax_main.get_yaxis_transform(),
                     color='white', backgroundcolor='#a020f0', fontsize=8, fontweight='bold', va='center', clip_on=False)
        ax_main.text(1.005, last_close, f" {safe_int(last_close)} ", transform=ax_main.get_yaxis_transform(),
                     color='black', backgroundcolor='#00ff00' if last_close >= last_open else '#ff0000', 
                     fontsize=8, fontweight='bold', va='center', clip_on=False)

        # Panel Volume Stack
        ax_vol.bar(x_indices, df['Vol_Sell'], color='#ff0000', width=0.8, align='center')
        ax_vol.bar(x_indices, df['Vol_Buy'], bottom=df['Vol_Sell'], color='#00ff00', width=0.8, align='center')
        ax_vol.plot(x_indices, df['V1'], color='#ffffff', linewidth=0.8)

        buy_pct = safe_int(buy_ratios[-1] * 100)
        vol_info_text = f"Buy Percent = {buy_pct}%   Sell Percent = {100-buy_pct}%   Net Vol = {safe_int(net_vol_today):,}   Net 5D = {safe_int(net_5d_vol):,}"
        ax_vol.text(0.01, 0.88, vol_info_text, transform=ax_vol.transAxes, color='#ffff00', fontsize=8, fontweight='bold')

        # Panel NBSA (Perhitungan Dinamis)
        nbsa_colors = ['#00ffff' if val >= 0 else '#ff0000' for val in df['NBSA']]
        ax_nbsa.bar(x_indices, df['NBSA'], color=nbsa_colors, width=0.6)
        
        sum_nbsa = df['NBSA'].iloc[-1]
        nbsa_str = format_large_number(sum_nbsa, show_sign=True)
        total_val = (df['Close'] * df['Volume']).iloc[-1]
        nbsa_val_pct = (abs(sum_nbsa) / total_val * 100) if total_val > 0 else 0.0
        
        ax_nbsa.text(0.01, 0.75, f"NBSA Rp. {nbsa_str}   NBSA Value : {nbsa_val_pct:.1f}%", transform=ax_nbsa.transAxes, color='#ffff00', fontsize=8)

        # Panel Market Maker
        mm_colors = ['#ffffff' if val >= 0 else '#888888' for val in df['MM']]
        ax_mm.bar(x_indices, df['MM'], color=mm_colors, width=0.4)
        ax_mm.text(0.01, 0.75, "Market Maker", transform=ax_mm.transAxes, color='#ffff00', fontsize=8)
        ax_mm.set_ylim(-200, 200)

        # Axis Datetime
        step = max(1, len(df) // 7)
        ax_mm.set_xticks(x_indices[::step])
        if isinstance(df.index, pd.DatetimeIndex):
            ax_mm.set_xticklabels([df.index[k].strftime("%b") for k in range(0, len(df), step)])

        plt.setp(ax_main.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)
        plt.setp(ax_nbsa.get_xticklabels(), visible=False)

        plt.savefig(output_filename, dpi=300, bbox_inches='tight', pad_inches=0.05, facecolor=fig.get_facecolor(), format='png')
        return output_filename
    finally:
        plt.clf()
        plt.close('all')

# ==========================================
# FETCH DATA & SCANNER
# ==========================================
def fetch_stock_history_multi_tf(symbol, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    yf_tf_map = {
        '1m': ('1m', '1d'), '5m': ('5m', '5d'), '15m': ('15m', '1mo'),
        '30m': ('30m', '1mo'), '1h': ('1h', '3mo'), '1d': ('1d', '1y'),
        '1w': ('1wk', '2y'), '1mth': ('1mo', '5y')
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
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df_yf.reset_index(inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_yf.columns:
                        df_yf[col] = pd.to_numeric(df_yf[col], errors='coerce')
                df_clean = df_yf.dropna(subset=['Close']).copy()
                df_clean['Symbol_Owner'] = symbol
                return df_clean
        except Exception:
            pass
    return None

def scan_single_symbol_tf(symbol, timeframe="1d"):
    try:
        df = fetch_stock_history_multi_tf(symbol, timeframe=timeframe)
        if df is not None and len(df) >= 20:
            column_mapping = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
            df.rename(columns=lambda x: column_mapping.get(str(x).lower().strip(), x), inplace=True)
            df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
            has_spike, info = check_volume_spike_signal(df, symbol, threshold_multiplier=2.0)
            if has_spike:
                info['timeframe'] = timeframe
                return info
    except Exception:
        pass
    return None

def run_scan_process_custom_tf(timeframe="1d"):
    detected_signals = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(scan_single_symbol_tf, sym, timeframe) for sym in TOP_300_IHSG]
        for f in futures:
            res = f.result()
            if res:
                detected_signals.append(res)
    detected_signals.sort(key=lambda x: x.get('score', 0), reverse=True)
    return detected_signals

# ==========================================
# TELEGRAM BROADCASTER & HANDLER
# ==========================================
def send_reply(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"❌ Error Send Message: {e}")

def send_photo_reply(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            requests.post(url, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}, files={'photo': photo}, timeout=30)
    except Exception as e: print(f"❌ Error Send Photo: {e}")

def broadcast_screening_results(signals, title_header, tf_code, target_chat_id=None):
    if target_chat_id is None: target_chat_id = TARGET_CHAT_ID
    now_str = get_now_wib().strftime('%d %b %Y %H:%M WIB')
    
    header_msg = (
        f"{title_header}\n"
        f"Waktu Scan: {now_str}\n"
        f"Total Sinyal Terkirim: {len(signals)} Emiten\n"
        f"Filter Cooldown: 60 Menit Jeda per Emiten\n"
        f"========================================\n\n"
    )

    if not signals:
        send_reply(target_chat_id, f"{header_msg}Tidak ditemukan emiten yang memenuhi kriteria.")
        return

    current_msg = header_msg
    inline_keyboard = []

    for idx, item in enumerate(signals, 1):
        item_str = (
            f"{idx}. {item['symbol']} — Harga {item['close']} ({item['change_pct']:+.2f}%)\n"
            f"    ├  Buy Strength Score: {item['score']}% ({item['score_label']})\n"
            f"    ├  RSI (14): {item['rsi']}\n"
            f"    ├ Vol Spike: {item['vol_multiple']:.1f}x V1 | Buy Vol: {item['buy_ratio']}%\n"
            f"    └ Bandar 1W: {format_large_number(item['bandar_5d_val'], show_sign=True)} (ACCUM)\n\n"
        )
        
        inline_keyboard.append([
            {"text": f"📈 {item['symbol']} (Daily)", "callback_data": f"chart_{item['symbol']}_1d"},
            {"text": f"📊 {item['symbol']} ({tf_code.upper()})", "callback_data": f"chart_{item['symbol']}_{tf_code}"}
        ])

        if len(current_msg) + len(item_str) > 3800:
            send_reply(target_chat_id, current_msg, reply_markup={"inline_keyboard": inline_keyboard})
            time.sleep(0.5)
            current_msg = item_str
            inline_keyboard = []
        else:
            current_msg += item_str
    
    if current_msg:
        send_reply(target_chat_id, current_msg, reply_markup={"inline_keyboard": inline_keyboard})

def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    if timeframe in ['d', 'day', 'daily', '1d']: timeframe = '1d'
    if timeframe in ['5', '5mi', 'm5']: timeframe = '5m'
    if timeframe in ['15', '15mi', 'm15']: timeframe = '15m'

    send_reply(chat_id, f"📊 *Generating chart {stock_code.upper()}...*")
    df = fetch_stock_history_multi_tf(stock_code, timeframe=timeframe)
    
    if df is not None and not df.empty and len(df) >= 20:
        col_map = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
        df.rename(columns=lambda x: col_map.get(str(x).lower().strip(), x), inplace=True)
        
        output_img = f"chart_{stock_code}_{timeframe}.png"
        chart_file = generate_pro_chart(df, symbol=stock_code.upper(), timeframe=timeframe, sector_info=f"{stock_code.upper()} | IHSG", output_filename=output_img)
        
        caption = f"📊 *chart: {stock_code.upper()}*"
        send_photo_reply(chat_id, chart_file, caption=caption)
        
        if os.path.exists(chart_file):
            os.remove(chart_file)
    else:
        send_reply(chat_id, f"❌ Data saham untuk *{stock_code.upper()}* tidak ditemukan atau data kurang memadai.")

# ==========================================
# BOT LISTENER & SCREENER LOOP
# ==========================================
def telegram_polling():
    offset = None
    print("🤖 Telegram Bot Listener Active...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            res = requests.get(url, params=params, timeout=35)
            if res.status_code == 200:
                updates = res.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    
                    if "message" in upd and "text" in upd["message"]:
                        chat_id = upd["message"]["chat"]["id"]
                        text = upd["message"]["text"].strip()
                        
                        if text.lower().startswith("/c ") or text.lower().startswith("/chart "):
                            parts = text.split()
                            if len(parts) >= 2:
                                sym = parts[1].upper()
                                tf = parts[2].lower() if len(parts) >= 3 else "1d"
                                threading.Thread(target=process_chart_request, args=(chat_id, sym, tf)).start()
                        elif text.lower() == "/scan":
                            send_reply(chat_id, "🔍 *Menjalankan Manual Screening IHSG...*")
                            signals = run_scan_process_custom_tf("1d")
                            filtered = filter_signals_with_cooldown(signals)
                            broadcast_screening_results(filtered, "🚨 *MANUAL SCREENER RESULT*", "1d", target_chat_id=chat_id)

                    elif "callback_query" in upd:
                        cb = upd["callback_query"]
                        cb_id = cb["id"]
                        chat_id = cb["message"]["chat"]["id"]
                        cb_data = cb["data"]
                        
                        if cb_data.startswith("chart_"):
                            _, sym, tf = cb_data.split("_")
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id})
                            threading.Thread(target=process_chart_request, args=(chat_id, sym, tf)).start()
        except Exception:
            time.sleep(3)

def scheduled_screener_loop():
    print("📈 Automatic Market Screener Engine Started...")
    while True:
        try:
            if is_market_open() and SCREENER_ACTIVE:
                print(f"[{get_now_wib().strftime('%H:%M:%S')}] Executing Market Scan...")
                signals = run_scan_process_custom_tf("1d")
                filtered_signals = filter_signals_with_cooldown(signals)
                if filtered_signals:
                    broadcast_screening_results(filtered_signals, "🚀 *VOLUME ENGINE SPIKE SIGNAL*", "1d")
            time.sleep(300)
        except Exception as e:
            print(f"❌ Error Screener Loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    t_bot = threading.Thread(target=telegram_polling, daemon=True)
    t_screener = threading.Thread(target=scheduled_screener_loop, daemon=True)
    
    t_bot.start()
    t_screener.start()
    
    while True:
        time.sleep(1)
