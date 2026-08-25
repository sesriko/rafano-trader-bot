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
# HELPER FRAKSI HARGA IHSG & FORMATTING
# ==========================================
def round_to_ihsg_fraction(price):
    if pd.isna(price) or price <= 0:
        return 0
    price = float(price)
    if price < 200:
        tick = 1
    elif price < 500:
        tick = 2
    elif price < 2000:
        tick = 5
    elif price < 5000:
        tick = 10
    else:
        tick = 25
    return int(round(price / tick) * tick)

def safe_int(val, default=0):
    try:
        if pd.isna(val) or np.isinf(val):
            return default
        return int(val)
    except Exception:
        return default

def format_large_number(val, show_sign=False):
    if pd.isna(val) or val == 0:
        return "0"
    abs_val = abs(val)
    sign = "+" if (show_sign and val > 0) else ("-" if val < 0 else "")
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:,.0f}M"
    elif abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:,.0f}K"
    else:
        return f"{sign}{val:,.0f}"

def is_market_open():
    now = get_now_wib()
    weekday = now.weekday()
    if weekday >= 5: # Sabtu & Minggu libur
        return False
    current_time = now.time()
    if weekday == 4: # Jumat
        session1_start, session1_end = datetime.time(9, 0), datetime.time(11, 30)
        session2_start, session2_end = datetime.time(14, 0), datetime.time(15, 50)
    else: # Senin - Kamis
        session1_start, session1_end = datetime.time(9, 0), datetime.time(12, 0)
        session2_start, session2_end = datetime.time(13, 30), datetime.time(15, 50)
    return (session1_start <= current_time <= session1_end) or (session2_start <= current_time <= session2_end)

# ==========================================
# METRIK RSI, VSA, ATR & SCORE
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

def calculate_atr(df, period=14):
    high, low, close = df['High'], df['Low'], df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

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
    if len(df) < 20:
        return 0, "NO DATA"

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
    if len(df) < 20: 
        return False, {}
    
    last_row = df.iloc[-1]
    last_close, last_vol = last_row['Close'], last_row['Volume']

    if last_close <= 50 or last_vol == 0: 
        return False, {}

    value_traded = last_close * last_vol
    if value_traded < min_value_traded: 
        return False, {}

    df, buy_ratios = calculate_vsa_metrics(df)
    avg_vol_v1, last_open, last_buy_ratio = last_row['V1'], last_row['Open'], buy_ratios[-1]
    
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI14'] = calculate_rsi(df['Close'], period=14)
    
    ema_50 = df['EMA50'].iloc[-1]
    last_rsi = round(df['RSI14'].iloc[-1], 2)

    net_5d_val = df['Net_Val_VSA'].tail(5).sum()
    is_bandar_accum = net_5d_val > 0

    if (last_close > ema_50) and \
       (last_rsi <= 75) and \
       (last_vol >= (avg_vol_v1 * threshold_multiplier)) and \
       is_bandar_accum and \
       (last_buy_ratio > 0.65) and \
       (last_close > last_open):
        
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
# CHART GENERATOR (300 DPI & RAPAT KIRI)
# ==========================================
def generate_pro_chart(df, symbol="ANTM", timeframe="1d", sector_info="Industrial Sector | IHSG", output_filename="chart_output.png"):
    try:
        tf_clean = timeframe.lower().strip()
        is_intraday = tf_clean in ['1m', '5m', '15m', '30m', '1h']

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
        if isinstance(df.index, pd.DatetimeIndex): 
            df = df.sort_index()

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high = df['High'].iloc[-1]
        last_low = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]

        # MULTI EMA
        df['EMA8'] = df['Close'].ewm(span=8, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA125'] = df['Close'].ewm(span=125, adjust=False).mean()
        
        df['RSI14'] = calculate_rsi(df['Close'], period=14)
        df['ATR'] = calculate_atr(df, period=14)

        df['Pivot_High'] = df['High'].rolling(window=12, min_periods=1).max()
        df['Pivot_Low'] = df['Low'].rolling(window=12, min_periods=1).min()
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()

        df, buy_ratios = calculate_vsa_metrics(df)
        net_5d_val = df['Net_Val_VSA'].tail(5).sum()
        net_val_today = df['Net_Val_VSA'].iloc[-1]
        last_rsi = round(df['RSI14'].iloc[-1], 2)
        
        signal_score, score_lbl = calculate_buy_signal_strength(df)

        if 'MM' not in df.columns:
            df['MM'] = (df['Close'] - df['EMA50']) / df['EMA50'] * 1000 + np.sin(np.linspace(0, 10, len(df))) * 15 - 10.9258

        plt.style.use('dark_background')
        
        fig = plt.figure(figsize=(18, 10), dpi=300, facecolor='#000000')
        gs = gridspec.GridSpec(4, 1, height_ratios=[4, 0.2, 1.2, 0.8], hspace=0.04)

        ax_main = fig.add_subplot(gs[0])
        ax_bar = fig.add_subplot(gs[1], sharex=ax_main)
        ax_vol = fig.add_subplot(gs[2], sharex=ax_main)
        ax_mm = fig.add_subplot(gs[3], sharex=ax_main)

        color_up, color_down, color_neutral = '#00ff00', '#ff0000', '#888888'

        for ax in [ax_main, ax_bar, ax_vol, ax_mm]:
            ax.set_facecolor('#000000')
            ax.grid(True, color='#1e1e1e', linestyle=':', linewidth=0.6)
            ax.tick_params(colors='white', labelsize=10)
            ax.yaxis.tick_right()

        x_indices = np.arange(len(df))

        # Render Candlestick
        for i in range(len(df)):
            open_p, high_p, low_p, close_p = df['Open'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['Close'].iloc[i]
            if close_p >= open_p:
                body_top, body_bottom = close_p, open_p
                body_height = max(0.2, close_p - open_p)
                ax_main.plot([i, i], [high_p, body_top], color=color_up, linewidth=1.2)
                ax_main.plot([i, i], [low_p, body_bottom], color=color_up, linewidth=1.2)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1.2, edgecolor=color_up, facecolor='none')
                ax_main.add_patch(rect)
            else:
                body_top, body_bottom = open_p, close_p
                body_height = max(0.2, open_p - close_p)
                ax_main.plot([i, i], [low_p, high_p], color=color_down, linewidth=1.2)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1.2, edgecolor=color_down, facecolor=color_down)
                ax_main.add_patch(rect)

        # PLOT EMA
        ax_main.plot(x_indices, df['EMA8'], color='#00ffff', linewidth=1.0, label='EMA 8')
        ax_main.plot(x_indices, df['EMA21'], color='#ff00ff', linewidth=1.2, label='EMA 21')
        ax_main.plot(x_indices, df['EMA50'], color='#ffff00', linewidth=1.5, label='EMA 50')
        ax_main.plot(x_indices, df['EMA125'], color='#ffffff', linewidth=1.8, label='EMA 125')

        ax_main.step(x_indices, df['Pivot_High'], where='mid', color='#555555', linestyle='--', linewidth=1.0)
        ax_main.step(x_indices, df['Pivot_Low'], where='mid', color='#444444', linestyle=':', linewidth=1.0)

        last_signal_idx = -10
        latest_setup = {"status": "WAIT & SEE", "entry": 0, "tp1": 0, "tp2": 0, "danger": 0}

        for i in range(5, len(df)):
            c_price, o_price = df['Close'].iloc[i], df['Open'].iloc[i]
            vol_curr, vol_avg = df['Volume'].iloc[i], df['V1'].iloc[i]
            ema_50 = df['EMA50'].iloc[i]
            b_ratio = buy_ratios[i]
            atr_val = df['ATR'].iloc[i]
            rsi_val = df['RSI14'].iloc[i]
            
            net_5d_val_i = df['Net_Val_VSA'].iloc[max(0, i-4):i+1].sum()
            is_bandar_accum_i = net_5d_val_i > 0

            is_accum_trend = (c_price > 50) and (c_price > ema_50) and (rsi_val <= 75) and (vol_curr >= vol_avg * 2.0) and is_bandar_accum_i and (b_ratio > 0.65) and (c_price > o_price)

            if is_accum_trend and (i - last_signal_idx >= 4):
                buy_price = round_to_ihsg_fraction(c_price)
                tp1_price = round_to_ihsg_fraction(buy_price * 1.035)
                tp2_price = round_to_ihsg_fraction(buy_price + (1.5 * atr_val))
                swing_low = df['Pivot_Low'].iloc[i]
                danger_price = round_to_ihsg_fraction(min(swing_low, buy_price - (1.0 * atr_val)))

                ax_main.plot(i, df['Low'].iloc[i] * 0.985, marker='^', color='#00ff00', markersize=7, zorder=6)
                if i >= len(df) - 3:
                    ax_main.text(i, df['Low'].iloc[i] * 0.96, f"BUY @ {buy_price}", color='#00ff00', fontsize=8, fontweight='bold', ha='center',
                                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#000000', alpha=0.75, edgecolor='#00ff00'))

                latest_setup = {"status": "BUY ACCUMULATION", "entry": buy_price, "tp1": tp1_price, "tp2": tp2_price, "danger": danger_price}
                last_signal_idx = i

        max_high = df['High'].max()
        min_low = df['Low'].min()
        ax_main.set_ylim(min_low * 0.95, max_high * 1.25)
        
        # PERBAIKAN: Mengurangi margin kosong di batas kiri (dikurangi dari -4 ke -1)
        ax_main.set_xlim(-1, len(df) + 1)

        # DASHBOARD OVERLAY (RAPAT KIRI & COMPACT)
        status_color = "#00ff00" if latest_setup["status"] == "BUY ACCUMULATION" else "#ffff00"
        
        # PERBAIKAN: Hilangkan spasi berlebih agar tabel tidak terlalu longgar
        entry_val = latest_setup['entry'] if latest_setup['entry'] > 0 else last_close
        tp1_val = latest_setup['tp1'] if latest_setup['tp1'] > 0 else round_to_ihsg_fraction(last_close*1.035)
        tp2_val = latest_setup['tp2'] if latest_setup['tp2'] > 0 else round_to_ihsg_fraction(last_close*1.07)
        sl_val = latest_setup['danger'] if latest_setup['danger'] > 0 else round_to_ihsg_fraction(last_close*0.95)

        dashboard_text = (
            f"RAFANO DASHBOARD\n"
            f"-----------------------\n"
            f"O:{safe_int(last_open)} H:{safe_int(last_high)} L:{safe_int(last_low)} C:{safe_int(last_close)}\n"
            f"VOL: {format_large_number(last_vol)}\n"
            f"-----------------------\n"
            f"SCORE  : {signal_score}% ({score_lbl})\n"
            f"STATUS : {latest_setup['status']}\n"
            f"ENTRY  : {entry_val}\n"
            f"TP1    : {tp1_val}\n"
            f"TP2    : {tp2_val}\n"
            f"SL     : {sl_val}"
        )
        
        ax_main.text(0.01, 0.96, dashboard_text, transform=ax_main.transAxes, verticalalignment='top', horizontalalignment='left',
                     fontfamily='monospace', fontsize=8.5, color=status_color,
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#000000', alpha=0.75, edgecolor='#333333'))

        stat_text_right = (
            f"RSI (14)   : {last_rsi}\n"
            f"BANDAR 1W  : {'ACCUM' if net_5d_val > 0 else 'DISTRIB'}\n"
            f"VAL 1D     : {format_large_number(net_val_today, show_sign=True)}\n"
            f"VSA BUY    : {safe_int(buy_ratios[-1]*100)}%"
        )
        ax_main.text(0.985, 0.96, stat_text_right, transform=ax_main.transAxes, verticalalignment='top', horizontalalignment='right',
                     fontfamily='monospace', fontsize=8.5, color='#00ffff',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#000000', alpha=0.75, edgecolor='#333333'))

        latest_ph, latest_pl = df['Pivot_High'].iloc[-1], df['Pivot_Low'].iloc[-1]
        
        ax_main.text(1.01, latest_ph, f" {safe_int(latest_ph)} ", 
                     transform=ax_main.get_yaxis_transform(),
                     color='black', backgroundcolor='#ffff00', 
                     fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)
                     
        ax_main.text(1.01, latest_pl, f" {safe_int(latest_pl)} ", 
                     transform=ax_main.get_yaxis_transform(),
                     color='black', backgroundcolor='#00ffff', 
                     fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)

        # HEADER CHART
        fig.text(0.01, 0.975, f"{symbol}", color='#ffffff', fontsize=16, fontweight='bold')
        fig.text(0.45, 0.975, "RAFANO TRADER", color='#ffffff', fontsize=35, fontweight='bold')
        
        last_date_str = get_now_wib().strftime('%d %b %Y')
        fig.text(0.88, 0.975, f"{tf_clean.upper()} {last_date_str}", color='#ffff00', fontsize=10, fontweight='bold', ha='right')

        sub_header = f"{sector_info}"
        fig.text(0.01, 0.945, sub_header, color='#888888', fontsize=8.5)

        for i in range(len(df)):
            c, o = df['Close'].iloc[i], df['Open'].iloc[i]
            bar_color = color_neutral if abs(c - o) / max(1, o) < 0.0005 else (color_up if c >= o else color_down)
            ax_bar.add_patch(patches.Rectangle((i - 0.5, 0), 1.0, 1.0, color=bar_color))
        ax_bar.set_ylim(0, 1)
        ax_bar.axis('off')

        ax_vol.bar(x_indices, df['Vol_Sell'], color='#ff0000', width=0.8, align='center')
        ax_vol.bar(x_indices, df['Vol_Buy'], bottom=df['Vol_Sell'], color='#00ff00', width=0.8, align='center')
        ax_vol.plot(x_indices, df['V1'], color='#ffffff', linewidth=1.0, linestyle='-')
        
        net_val_str = format_large_number(net_val_today, show_sign=True)
        net_5d_val_str = format_large_number(net_5d_val, show_sign=True)
        last_buy_pct = safe_int(buy_ratios[-1] * 100)
        vol_text = (f"Buy: {last_buy_pct}%  Sell: {100 - last_buy_pct}%  Val 1D: {net_val_str}  Val 5D: {net_5d_val_str}")
        ax_vol.text(0.01, 0.85, vol_text, transform=ax_vol.transAxes, color='#00ffff', fontsize=8, fontweight='bold')
        ax_vol.set_ylim(0, df['Volume'].max() * 1.35)

        mm_colors = ['#ffff00' if v >= 0 else '#555555' for v in df['MM']]
        ax_mm.bar(x_indices, df['MM'], color=mm_colors, width=0.4)
        ax_mm.text(0.01, 0.80, "Market Maker", transform=ax_mm.transAxes, color='#ffff00', fontsize=8, fontweight='bold')
        
        ax_mm.text(1.01, df['MM'].iloc[-1], f" {df['MM'].iloc[-1]:.2f} ", 
                   transform=ax_mm.get_yaxis_transform(),
                   color='black', backgroundcolor='#ffff00', 
                   fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)

        step = max(1, len(df) // 8)
        ax_mm.set_xticks(x_indices[::step])
        if isinstance(df.index, pd.DatetimeIndex):
            fmt = "%H:%M" if is_intraday else "%b %Y"
            ax_mm.set_xticklabels([df.index[k].strftime(fmt) for k in range(0, len(df), step)])

        plt.setp(ax_main.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

        # RENDER DENGAN 300 DPI
        plt.savefig(
            output_filename, 
            dpi=300, 
            bbox_inches='tight', 
            pad_inches=0.1,
            facecolor=fig.get_facecolor(),
            format='png'
        )
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
# TELEGRAM BROADCASTER
# ==========================================
def send_reply(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Error Send Message: {e}")

def send_photo_reply(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            requests.post(
                url, 
                data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}, 
                files={'photo': photo}, 
                timeout=30
            )
    except Exception as e:
        print(f"❌ Error Send Photo: {e}")

def broadcast_screening_results(signals, title_header, tf_code, target_chat_id=None):
    if target_chat_id is None:
        target_chat_id = TARGET_CHAT_ID

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

# ==========================================
# MANUAL CHART REQUEST HANDLER
# ==========================================
def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    if timeframe in ['d', 'day', 'daily', '1d']: timeframe = '1d'
    if timeframe in ['5', '5mi', 'm5']: timeframe = '5m'
    if timeframe in ['15', '15mi', 'm15']: timeframe = '15m'

    send_reply(chat_id, f"📊 *Generating Pro Chart {stock_code.upper()} ({timeframe.upper()})...*")
    df = fetch_stock_history_multi_tf(stock_code, timeframe=timeframe)
    
    if df is not None and not df.empty and len(df) >= 20:
        col_map = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
        df.rename(columns=lambda x: col_map.get(str(x).lower().strip(), x), inplace=True)
        
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI14'] = calculate_rsi(df['Close'], period=14)
        df, buy_ratios = calculate_vsa_metrics(df)
        
        last_row = df.iloc[-1]
        last_close = safe_int(last_row['Close'])
        last_vol = last_row['Volume']
        avg_vol_v1 = last_row['V1']
        
        change_pct = ((last_close / df['Close'].iloc[-2]) - 1) * 100 if len(df) > 1 else 0.0
        score, score_label = calculate_buy_signal_strength(df)
        last_rsi = round(df['RSI14'].iloc[-1], 2)
        vol_multiple = last_vol / avg_vol_v1 if avg_vol_v1 > 0 else 0.0
        buy_ratio_pct = safe_int(buy_ratios[-1] * 100)
        
        net_5d_val = df['Net_Val_VSA'].tail(5).sum()
        bandar_status = "ACCUM" if net_5d_val > 0 else "DISTRIB"
        bandar_val_str = format_large_number(net_5d_val, show_sign=True)

        chart_file = f"chart_{stock_code.upper()}_{timeframe}_{int(time.time())}.png"
        try:
            file_path = generate_pro_chart(
                df=df, 
                symbol=stock_code.upper(), 
                timeframe=timeframe, 
                sector_info=f"{stock_code.upper()} | IHSG", 
                output_filename=chart_file
            )
            
            caption_msg = (
                f"{stock_code.upper()} — Harga {last_close} ({change_pct:+.2f}%)\n"
                f"     Buy Strength Score: {score}% ({score_label})\n"
                f"     RSI (14): {last_rsi}\n"
                f"     Vol Spike: {vol_multiple:.1f}x V1 | Buy Vol: {buy_ratio_pct}%\n"
                f"     Bandar 1W: {bandar_val_str} ({bandar_status})"
            )
            
            send_photo_reply(chat_id, file_path, caption=caption_msg)
            
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            send_reply(chat_id, f"❌ *Gagal merender chart:* `{e}`")
    else:
        send_reply(chat_id, f"⚠️ *Data historis tidak ditemukan untuk emiten {stock_code.upper()}*")

# ==========================================
# AUTO SCREENER LOOP (JAM MARKET AKTIF ONLY)
# ==========================================
def auto_screener_loop():
    print("🚀 Auto Scheduled Screener Engine Active (Active Market Hours Only)...")
    global SCREENER_ACTIVE
    last_triggered_sesi1, last_triggered_eod = "", ""
    
    while True:
        try:
            if not SCREENER_ACTIVE:
                time.sleep(10)
                continue

            if is_market_open():
                now = get_now_wib()
                today_str, current_time_str = now.strftime('%Y-%m-%d'), now.strftime('%H:%M')
                weekday = now.weekday()

                # Rekap Akhir Sesi 1
                target_sesi1_time = "11:25" if weekday == 4 else "11:55"
                if current_time_str == target_sesi1_time and last_triggered_sesi1 != today_str:
                    signals_sesi1 = run_scan_process_custom_tf(timeframe="15m")
                    broadcast_screening_results(signals_sesi1, "POWER ACCUMULATION VSA — AKHIR SESI 1 (15M)", "15m")
                    last_triggered_sesi1 = today_str

                # Rekap End of Day
                if current_time_str == "15:55" and last_triggered_eod != today_str:
                    signals_eod = run_scan_process_custom_tf(timeframe="1d")
                    broadcast_screening_results(signals_eod, "POWER ACCUMULATION VSA — END OF DAY (DAILY)", "1d")
                    last_triggered_eod = today_str

                # Real-Time Screener Daily (1D) per 10 Menit saat Market Aktif
                signals_daily = run_scan_process_custom_tf(timeframe="1d")
                filtered_daily = filter_signals_with_cooldown(signals_daily)
                if filtered_daily:
                    broadcast_screening_results(filtered_daily, "REAL-TIME SIGNAL — DAILY (1D) BUY ACCUMULATION", "1d")

                time.sleep(600)
            else:
                time.sleep(300)

        except Exception as e:
            print(f"⚠️ Exception in Auto-Screener: {e}")
            time.sleep(10)

# ==========================================
# TELEGRAM LISTENERS & HANDLER
# ==========================================
def telegram_bot_listener():
    offset = 0
    print("🤖 Telegram Command & Callback Listener Running...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=20"
            res = requests.get(url, timeout=25)
            if res.status_code == 200:
                data = res.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb.get("id")
                        cb_data = cb.get("data", "")
                        chat_id = cb["message"]["chat"]["id"]
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id})

                        if cb_data.startswith("chart_"):
                            parts = cb_data.split("_")
                            if len(parts) >= 3:
                                sym = parts[1]
                                tf = parts[2]
                                threading.Thread(target=process_chart_request, args=(chat_id, sym, tf)).start()

                    elif "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        text = msg.get("text", "").strip()
                        chat_id = msg["chat"]["id"]
                        first_word = text.split()[0].lower() if text else ""
                        
                        if first_word in ["/start", "/help"]:
                            help_msg = (
                                "🤖 *RAFANO TRADER BOT ASSISTANT*\n"
                                "========================================\n"
                                "Daftar perintah yang tersedia:\n\n"
                                "📈 `/c <KODE_SAHAM> [TIMEFRAME]`\n"
                                "  Generates Pro Technical Chart dengan Statistik Detail.\n"
                                "  _Contoh:_ `/c PTBA` atau `/c ANTM 15m`\n\n"
                                "🔍 `/scan`\n"
                                "  Menjalankan manual Instant Screener (1D).\n\n"
                                "========================================\n"
                                "⏱️ *Auto Screener:* Berjalan otomatis hanya saat jam bursa aktif."
                            )
                            send_reply(chat_id, help_msg)

                        elif first_word in ["/c", "/chart", "!chart"]:
                            parts = text.split()
                            if len(parts) >= 2:
                                sym = parts[1].upper()
                                tf = parts[2] if len(parts) >= 3 else "1d"
                                threading.Thread(target=process_chart_request, args=(chat_id, sym, tf)).start()
                            else:
                                send_reply(chat_id, "⚠️ *Format salah!*\nGunakan: `/c <KODE_SAHAM> [TIMEFRAME]`\n\n*Contoh:* `/c PTBA` atau `/c ANTM 15m`")
                        
                        elif first_word in ["/scan", "!scan"]:
                            send_reply(chat_id, "🔍 *Menjalankan manual Instant Scan (Daily)...*")
                            def manual_scan():
                                sigs = run_scan_process_custom_tf(timeframe="1d")
                                broadcast_screening_results(sigs, "REAL-TIME SIGNAL — DAILY (1D) BUY ACCUMULATION", "1d", target_chat_id=chat_id)
                            threading.Thread(target=manual_scan).start()

        except Exception as e:
            time.sleep(3)

# ==========================================
# MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    print("==========================================")
    print("🔥 RAFANO TRADER ENGINE STARTING...")
    print("==========================================")
    
    threading.Thread(target=auto_screener_loop, daemon=True).start()
    telegram_bot_listener()
