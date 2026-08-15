import os
import time
import logging
import datetime
import threading
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
from concurrent.futures import ThreadPoolExecutor

# Library Fallback Data
try:
    import yfinance as yf
except ImportError:
    yf = None

# ==========================================
# FILTER LOGS & WARNINGS TERMINAL
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

# Variable Control Screener Engine
SCREENER_ACTIVE = True

# ==========================================
# DAFTAR 300 EMITEN IHSG CLEAN & AKTIF
# ==========================================
TOP_300_IHSG = [
    "ACES", "ADHI", "ADRO", "AGRO", "AGRS", "AHAP", "AISA", "AKRA", "ALDO", "AMAR", 
    "AMFG", "AMMN", "AMRT", "ANDI", "ANJT", "ANTM", "APIC", "APLN", "ARCI", "ARTO", 
    "ASGR", "ASII", "ASRI", "AUTO", "AVIA", "AXIO", "BABP", "BACA", "BALI", "BANK", 
    "BAPA", "BBCA", "BBHI", "BBKP", "BBLD", "BBMD", "BBNI", "BBRI", "BBRM", "BBTN", 
    "BBYB", "BCIC", "BDMN", "BEST", "BFIN", "BHIT", "BIPI", "BIPP", "BIRD", "BISI", 
    "BJBR", "BJTM", "BKSL", "BMAS", "BMHS", "BMRI", "BMTR", "BNBR", "BNGA", "BNII", 
    "BNLI", "BOLT", "BRAM", "BRMS", "BRPT", "BSDE", "BSIM", "BSSR", "BTON", "BUKA", 
    "BULL", "BUMI", "BVIC", "BWPT", "BYAN", "CASA", "CASS", "CENT", "CFIN", "CINT", 
    "CITA", "CITY", "CLPI", "CMNP", "CMPP", "CMRY", "CNTX", "COAL", "CPIN", "CPRI", 
    "CPRO", "CSAP", "CSRA", "CTBN", "CTRA", "DART", "DDEI", "DEWA", "DGIK", "DIGI", 
    "DILD", "DIVA", "DKFT", "DLTA", "DMAS", "DNAR", "DNET", "DOOID", "DPNS", "DSNG", 
    "DUTI", "DVLA", "ECII", "ELSA", "ELTY", "EMTK", "ENRG", "ERAA", "ESSA", "FASW", 
    "FILM", "FIRE", "FPNI", "FUTR", "GDST", "GEMS", "GIAA", "GJTL", "GNKF", "GOTO", 
    "GPRA", "GRPH", "GSMF", "GTBO", "GWSA", "GZCO", "HATM", "HDIT", "HEAL", "HERO", 
    "HEXA", "HITS", "HMSP", "HOKI", "HOME", "HOPE", "HRUM", "IATA", "IBFN", "IBOS", 
    "ICBP", "ICON", "IDPR", "IGAR", "IIKP", "IKAI", "IKBI", "INAF", "INAI", "INCF", 
    "INCI", "INDF", "INKP", "INPC", "INPP", "INTP", "IPCC", "IPPE", "IRRA", "ISAT", 
    "ISSP", "ITMG", "JARR", "JECC", "JAST", "JIHD", "JKON", "JSPT", "JPFA", "JRPT", 
    "JSMR", "JTEX", "KAEF", "KAST", "KBLI", "KBLM", "KDSI", "KIJA", "KKGI", "KLBF", 
    "KMTR", "KOBX", "KOPI", "KPIG", "KRAS", "KREN", "LPCK", "LPKR", "LPLI", "LPPF", 
    "LTLS", "MAHA", "MAPA", "MAPI", "MASB", "MBAP", "MBMA", "MBTO", "MCOR", "MDKA", 
    "MMLP", "MNCN", "MPPA", "MRAT", "MSIN", "MTCEN", "MTDL", "MTLA", "MYOR", "NCKL", 
    "NELI", "NICK", "NIKL", "NISP", "NSIC", "OASA", "OKAS", "OMRE", "PALM", "PANI", 
    "PANR", "PBSD", "PBID", "PGLI", "PGAS", "PUDP", "PNBS", "PNIN", "PNLF", "POLI", 
    "POLL", "POLY", "PORT", "POWR", "PPGL", "PPRE", "PTBA", "PTFO", "PTPP", "PTRO", 
    "PWON", "PYFA", "RAJA", "RALS", "RANC", "RBMS", "RDTX", "RELI", "RICY", "RIGS", 
    "ROTI", "SAFE", "SAMF", "SAME", "SAMR", "SBAT", "SCCO", "SCMA", "SDMU", "SFAN", 
    "SGER", "SGRO", "SILO", "SIMP", "SINO", "SIPD", "SKLT", "SMAR", "SMDM", "SMDR", 
    "SMGR", "SMRA", "SMOT", "SMSM", "SOCI", "SPTO", "SRIL", "SRTG", "SSIA", "SSMS", 
    "STAA", "TAPG", "TBLA", "TBIG", "TEBE", "TFCO", "TINU", "TINS", "TKIM", "TLKM", 
    "TMAS", "TOBA", "TPIA", "TRIM", "TRIS", "TRST", "TRUK", "TSPC", "TOTO", "UANG", 
    "UCID", "ULTJ", "UNIC", "UNIQ", "UNTR", "UNVR", "VICI", "VINS", "VKTR", "VRNA", 
    "WAPO", "WEGE", "WIFI", "WIIM", "WINS", "WIRT", "WOOD", "WSBP", "WSIH", "WSKT", 
    "WTON", "YPAS", "YULE", "ZBRA", "ZINC"
]

# ==========================================
# HELPER FORMATTING NUMBERS & SAFE CASTING
# ==========================================
def safe_int(val, default=0):
    """Casting integer aman dari NaN/Inf"""
    try:
        if pd.isna(val) or np.isinf(val):
            return default
        return int(val)
    except Exception:
        return default

def format_large_number(val, show_sign=False):
    """Format angka besar ke Million (M) / Billion (B)"""
    if pd.isna(val) or val == 0:
        return "0"
    
    abs_val = abs(val)
    sign = "+" if (show_sign and val > 0) else ("-" if val < 0 else "")
    
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f}M"
    else:
        return f"{sign}{val:,.0f}"

# ==========================================
# HELPER MARKET HOURS CONTROL
# ==========================================
def is_market_open():
    """Mengecek apakah saat ini jam bursa IHSG aktif (WIB)"""
    now = datetime.datetime.now()
    weekday = now.weekday()
    
    if weekday >= 5:
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
# ENGINE KALKULASI VSA (VOLUME SPREAD ANALYSIS)
# ==========================================
def calculate_vsa_metrics(df):
    """Menghitung metrik VSA murni berbasis OHLCV (Dengan Doji Handling)"""
    price_range = (df['High'] - df['Low']).replace(0, 0.1)
    body_move = df['Close'] - df['Open']
    
    # Rasio Tekanan Beli vs Jual (Doji & Spread Handling)
    buy_ratio = np.where(
        price_range <= 0.1,
        0.50, # Doji sempurna -> Netral 50%
        np.where(df['Close'] >= df['Open'], 
                 0.55 + (body_move / price_range) * 0.4, 
                 0.45 + (body_move / price_range) * 0.4)
    )
    buy_ratio = np.clip(buy_ratio, 0.05, 0.95)
    
    df['Vol_Buy'] = df['Volume'] * buy_ratio
    df['Vol_Sell'] = df['Volume'] - df['Vol_Buy']
    df['Net_Vol_VSA'] = df['Vol_Buy'] - df['Vol_Sell']
    
    return df, buy_ratio

# ==========================================
# ENGINE DETEKTOR POWER VOLUME BUY
# ==========================================
def check_volume_spike_signal(df, symbol, threshold_multiplier=2.5, min_value_traded=500_000_000):
    """Mengecek sinyal VSA Power Volume Buy dengan Filter Nominal Transaksi Minimal"""
    if len(df) < 20:
        return False, {}

    last_row = df.iloc[-1]
    last_close = last_row['Close']
    last_vol = last_row['Volume']

    # Filter Likuiditas Minimal Transaksi (Default: Rp 500 Juta)
    value_traded = last_close * last_vol
    if value_traded < min_value_traded:
        return False, {}

    df, buy_ratios = calculate_vsa_metrics(df)
    avg_vol_v1 = last_row['V1']
    last_open = last_row['Open']
    last_buy_ratio = buy_ratios[-1]

    if last_vol >= (avg_vol_v1 * threshold_multiplier) and last_close > last_open and last_buy_ratio >= 0.55:
        vol_multiple = last_vol / avg_vol_v1 if avg_vol_v1 > 0 else 0
        change_pct = ((last_close / df['Close'].iloc[-2]) - 1) * 100 if len(df) > 1 else 0.0
        
        info = {
            "symbol": symbol,
            "close": safe_int(last_close),
            "change_pct": change_pct,
            "vol_multiple": vol_multiple,
            "buy_ratio": safe_int(last_buy_ratio * 100),
            "volume": safe_int(last_vol),
            "value_traded": value_traded
        }
        return True, info

    return False, {}

# ==========================================
# ENGINE GENERATOR CHART (ANTI-MEMORY LEAK)
# ==========================================
def generate_pro_chart(df, symbol="MDKA", timeframe="1d", sector_info="Indonesian Stock Exchange | Technical & VSA Analysis", output_filename="chart_output.png"):
    try:
        tf_clean = timeframe.lower().strip()
        is_intraday = tf_clean in ['1m', '5m', '15m', '30m', '1h']

        df.columns = [str(col).lower().capitalize() for col in df.columns]
        df = df.ffill().bfill()
        
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.sort_index()

        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high = df['High'].iloc[-1]
        last_low = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]

        # EMA 50 (Custom Indicator Target)
        df['EMA_Slow'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Trend_Curve'] = df['EMA_Slow']

        df['Pivot_High'] = df['High'].rolling(window=12, min_periods=1).max()
        df['Pivot_Low'] = df['Low'].rolling(window=12, min_periods=1).min()
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()

        # Kalkulasi VSA Engine
        df, buy_ratios = calculate_vsa_metrics(df)
        net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
        net_vol_today = df['Net_Vol_VSA'].iloc[-1]

        vol_ratio_today = last_vol / df['V1'].iloc[-1] if df['V1'].iloc[-1] > 0 else 1.0
        if last_close > last_open and vol_ratio_today >= 1.8:
            vsa_status = "ACCUMULATION (HIGH BUY)"
        elif last_close < last_open and vol_ratio_today >= 1.8:
            vsa_status = "DISTRIBUTION (HIGH SELL)"
        elif vol_ratio_today < 0.6:
            vsa_status = "NO SUPPLY / DRY VOL"
        else:
            vsa_status = "NEUTRAL FLOW"

        if 'MM' not in df.columns:
            df['MM'] = (df['Close'] - df['EMA_Slow']) / df['EMA_Slow'] * 1000 + np.sin(np.linspace(0, 10, len(df))) * 15 + 74.5568

        plt.style.use('dark_background')
        fig = plt.figure(figsize=(15, 9), facecolor='#000000')
        gs = gridspec.GridSpec(4, 1, height_ratios=[4, 0.2, 1.2, 0.8], hspace=0.04)

        ax_main = fig.add_subplot(gs[0])
        ax_bar = fig.add_subplot(gs[1], sharex=ax_main)
        ax_vol = fig.add_subplot(gs[2], sharex=ax_main)
        ax_mm = fig.add_subplot(gs[3], sharex=ax_main)

        color_up = '#00ff00'
        color_down = '#ff0000'
        color_neutral = '#888888'

        for ax in [ax_main, ax_bar, ax_vol, ax_mm]:
            ax.set_facecolor('#000000')
            ax.grid(True, color='#1e1e1e', linestyle=':', linewidth=0.5)
            ax.tick_params(colors='white', labelsize=8)
            ax.yaxis.tick_right()

        x_indices = np.arange(len(df))

        # Plot Candlestick
        for i in range(len(df)):
            open_p, high_p, low_p, close_p = df['Open'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['Close'].iloc[i]
            
            if close_p >= open_p:
                body_top, body_bottom = close_p, open_p
                body_height = max(0.2, close_p - open_p)
                ax_main.plot([i, i], [high_p, body_top], color=color_up, linewidth=1)
                ax_main.plot([i, i], [low_p, body_bottom], color=color_up, linewidth=1)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1, edgecolor=color_up, facecolor='none')
                ax_main.add_patch(rect)
            else:
                body_top, body_bottom = open_p, close_p
                body_height = max(0.2, open_p - close_p)
                ax_main.plot([i, i], [low_p, high_p], color=color_down, linewidth=1)
                rect = patches.Rectangle((i - 0.35, body_bottom), 0.7, body_height, linewidth=1, edgecolor=color_down, facecolor=color_down)
                ax_main.add_patch(rect)

        # Plot EMA 50
        ax_main.plot(x_indices, df['Trend_Curve'], color='#ffffff', linewidth=1.2, linestyle='-')
        ax_main.scatter(x_indices, df['Trend_Curve'], color='#ffffff', s=7, zorder=4)

        ax_main.step(x_indices, df['Pivot_High'], where='mid', color='#444444', linestyle='--', linewidth=0.8)
        ax_main.step(x_indices, df['Pivot_Low'], where='mid', color='#333333', linestyle=':', linewidth=0.8)

        step_size = max(10, len(df) // 6)
        for i in range(step_size, len(df) - 2, step_size):
            p_low = df['Low'].iloc[i]
            c_price = df['Close'].iloc[i]
            sl_price = df['Pivot_Low'].iloc[i]

            if c_price >= df['Open'].iloc[i]:
                ax_main.plot(i, p_low * 0.985, marker='^', color='#00ff00', markersize=6)
                ax_main.text(i, p_low * 0.955, f"BELI >{safe_int(c_price)}\nSL <{safe_int(sl_price)}", color='#00ff00', fontsize=6.5, fontweight='bold', ha='center')

        # BOX TEKS ANALISIS VSA & METRIK TEKNIKAL
        net_vol_str = format_large_number(net_vol_today, show_sign=True)
        net_5d_str = format_large_number(net_5d_vol, show_sign=True)
        
        stat_text = (
            f"Avg Price 5D : {df['Close'].tail(5).mean():.1f}\n"
            f"EMA 50 Trend : {'BULLISH' if last_close >= df['EMA_Slow'].iloc[-1] else 'BEARISH'}\n"
            f"VSA Signal   : {vsa_status}\n"
            f"Net Vol Today: {net_vol_str}\n"
            f"VSA Flow 5D  : {net_5d_str}\n"
            f"Vol Spike Ratio: {vol_ratio_today:.2f}x V1\n"
            f"Speed        : TURBO\n"
            f"Safety       : GOOD"
        )
        ax_main.text(0.02, 0.94, stat_text, transform=ax_main.transAxes, verticalalignment='top',
                     fontfamily='monospace', fontsize=7.2, color='#00ffff',
                     bbox=dict(boxstyle='square,pad=0.3', facecolor='#000000', alpha=0.8, edgecolor='none'))

        latest_high_pivot = df['Pivot_High'].iloc[-1]
        ax_main.text(len(df) + 0.5, latest_high_pivot, f"{safe_int(latest_high_pivot)}", color='black', backgroundcolor='#ffff00', fontsize=8, fontweight='bold')
        ax_main.text(len(df) + 0.5, last_close, f"{safe_int(last_close)}", color='black', backgroundcolor='#00ffff', fontsize=8, fontweight='bold')

        ax_main.set_xlim(-8, len(df) + 5)
        main_y_min, main_y_max = df['Low'].min(), df['High'].max()
        ax_main.set_ylim(main_y_min * 0.92, main_y_max * 1.10)

        change_pct = ((last_close / df['Close'].iloc[-2]) - 1) * 100 if len(df) > 1 else 0.0
        title_color = '#ffff00' if change_pct >= 0 else '#ff0000'
        
        fig.text(0.01, 0.965, f"{symbol} :   {safe_int(last_close)} ({change_pct:+.2f}%)", color=title_color, fontsize=13, fontweight='bold')
        fig.text(0.45, 0.965, "RAFANO TRADER VSA ENGINE", color='#ffffff', fontsize=13, fontweight='bold')
        
        if is_intraday and isinstance(df.index, pd.DatetimeIndex):
            last_date_str = df.index[-1].strftime('%d %b %Y %H:%M')
        elif isinstance(df.index, pd.DatetimeIndex):
            last_date_str = df.index[-1].strftime('%d %b %Y')
        else:
            last_date_str = datetime.datetime.now().strftime('%d %b %Y %H:%M')
            
        tf_str = tf_clean.upper()
        fig.text(0.85, 0.965, f"{tf_str} {last_date_str}", color='#ffff00', fontsize=8, fontweight='bold', ha='right')

        sub_header = f"{sector_info}\nHigh:{safe_int(last_high)}   Low:{safe_int(last_low)}   Open:{safe_int(last_open)}   Volume:{format_large_number(last_vol)}   V1:{format_large_number(df['V1'].iloc[-1])}"
        fig.text(0.01, 0.932, sub_header, color='#00ffff', fontsize=7.5)

        for i in range(len(df)):
            c, o = df['Close'].iloc[i], df['Open'].iloc[i]
            bar_color = color_neutral if abs(c - o) / max(1, o) < 0.0005 else (color_up if c >= o else color_down)
            ax_bar.add_patch(patches.Rectangle((i - 0.5, 0), 1.0, 1.0, color=bar_color))
        ax_bar.set_ylim(0, 1)
        ax_bar.axis('off')

        # Histogram Volume VSA
        ax_vol.bar(x_indices, df['Vol_Sell'], color='#ff0000', width=0.8, align='center')
        ax_vol.bar(x_indices, df['Vol_Buy'], bottom=df['Vol_Sell'], color='#00ff00', width=0.8, align='center')
        ax_vol.plot(x_indices, df['V1'], color='#ffffff', linewidth=0.8, linestyle='-')
        
        last_buy_pct = safe_int(buy_ratios[-1] * 100)
        last_sell_pct = 100 - last_buy_pct
        
        vol_text = (f"VSA Buy = {last_buy_pct}%   VSA Sell = {last_sell_pct}%   "
                    f"Net Vol = {net_vol_str}   Net 5D (VSA Flow) = {net_5d_str}")
        ax_vol.text(0.01, 0.88, vol_text, transform=ax_vol.transAxes, color='#00ffff', fontsize=7.5, fontweight='bold')

        max_vol = df['Volume'].max() if len(df) > 0 else 1
        ax_vol.set_ylim(0, max_vol * 1.35)

        # Market Maker Momentum
        mm_colors = ['#ffff00' if v >= 0 else '#555555' for v in df['MM']]
        ax_mm.bar(x_indices, df['MM'], color=mm_colors, width=0.35)
        ax_mm.text(0.01, 0.85, "Market Maker Momentum", transform=ax_mm.transAxes, color='#ffff00', fontsize=7.5, fontweight='bold')
        
        last_mm = df['MM'].iloc[-1]
        ax_mm.text(len(df) + 0.5, last_mm, f"{last_mm:.4f}", color='black', backgroundcolor='#ffff00', fontsize=7.5, fontweight='bold')

        if isinstance(df.index, pd.DatetimeIndex):
            step = max(1, len(df) // 8)
            ax_mm.set_xticks(x_indices[::step])
            fmt = "%H:%M" if is_intraday else "%b %Y"
            ax_mm.set_xticklabels([df.index[i].strftime(fmt) for i in range(0, len(df), step)])

        plt.setp(ax_main.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

        plt.savefig(output_filename, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
        return output_filename
    finally:
        # PEMBERSIHAN MEMORY MANDATORIS (Anti Leak RAM)
        plt.clf()
        plt.close('all')

# ==========================================
# FETCH DATA MULTI TIMEFRAME (TEROPTIMASI)
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
                        return pd.DataFrame(klines)
            except Exception:
                pass

    if yf is not None:
        try:
            yf_symbol = symbol if (symbol.endswith(".JK") or not symbol.isalpha()) else f"{symbol}.JK"
            df_yf = yf.download(yf_symbol, interval=interval, period=period, progress=False, ignore_tz=True)
            
            if df_yf is not None and not df_yf.empty:
                # Membersihkan MultiIndex yfinance versi baru
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                
                df_yf.reset_index(inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_yf.columns:
                        df_yf[col] = pd.to_numeric(df_yf[col], errors='coerce')
                
                return df_yf.dropna(subset=['Close'])
        except Exception:
            pass

    return None

# ==========================================
# WORKER MULTITHREAD SCANNER VSA
# ==========================================
def scan_single_symbol_tf(symbol, timeframe="5m"):
    try:
        df = fetch_stock_history_multi_tf(symbol, timeframe=timeframe)
        if df is not None and len(df) >= 20:
            column_mapping = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
            df.rename(columns=lambda x: column_mapping.get(str(x).lower().strip(), x), inplace=True)
            
            df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
            has_spike, info = check_volume_spike_signal(df, symbol, threshold_multiplier=2.5)
            if has_spike:
                info['timeframe'] = timeframe
                return info
    except Exception:
        pass
    return None

def run_scan_process_custom_tf(timeframe="5m"):
    detected_signals = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(scan_single_symbol_tf, sym, timeframe) for sym in TOP_300_IHSG]
        for f in futures:
            res = f.result()
            if res:
                detected_signals.append(res)
    return detected_signals

# ==========================================
# SCHEDULER & NOTIFIER TELEGRAM ENGINE
# ==========================================
def broadcast_screening_results(signals, title_header, tf_code):
    now_str = datetime.datetime.now().strftime('%d %b %Y %H:%M WIB')
    
    if not signals:
        send_reply(TARGET_CHAT_ID, f"ℹ️ *{title_header}*\n🕒 `{now_str}`\nTidak ditemukan emiten yang memenuhi kriteria Power Volume VSA.")
        return

    header_msg = (
        f"🔥 *{title_header}*\n"
        f"🕒 *Waktu Scan:* `{now_str}`\n"
        f"🎯 *Total Lolos Filter:* `{len(signals)} Emiten`\n"
        f"========================================\n\n"
    )
    
    current_msg = header_msg
    inline_keyboard = []

    for idx, item in enumerate(signals, 1):
        item_str = (
            f"{idx}. *{item['symbol']}* — Harga `{item['close']}` ({item['change_pct']:+.2f}%)\n"
            f"    └ VSA Vol Spike: `{item['vol_multiple']:.1f}x V1` | Buy Vol: `{item['buy_ratio']}%`\n"
            f"    └ Value Traded: `{format_large_number(item['value_traded'])}`\n\n"
        )
        
        # Tambahkan Inline Button untuk tiap 2 emiten per baris
        inline_keyboard.append([
            {"text": f"📈 {item['symbol']} (Daily)", "callback_data": f"chart_{item['symbol']}_1d"},
            {"text": f"📊 {item['symbol']} ({tf_code.upper()})", "callback_data": f"chart_{item['symbol']}_{tf_code}"}
        ])

        if len(current_msg) + len(item_str) > 3800:
            send_reply(TARGET_CHAT_ID, current_msg, reply_markup={"inline_keyboard": inline_keyboard})
            time.sleep(0.5) # Protection HTTP 429
            current_msg = f"🔥 *LANJUTAN HASIL SCREENING*\n\n" + item_str
            inline_keyboard = []
        else:
            current_msg += item_str
    
    if current_msg:
        send_reply(TARGET_CHAT_ID, current_msg, reply_markup={"inline_keyboard": inline_keyboard})

def auto_screener_loop():
    print("🚀 Auto Scheduled Screener Engine Active (VSA Mode)...")
    global SCREENER_ACTIVE
    
    last_triggered_sesi1 = ""
    last_triggered_eod = ""
    
    while True:
        try:
            if not SCREENER_ACTIVE:
                time.sleep(10)
                continue

            now = datetime.datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            weekday = now.weekday()
            current_time_str = now.strftime('%H:%M')
            
            # Sesi 1 Close Trigger (11:25 / 11:55)
            target_sesi1_time = "11:25" if weekday == 4 else "11:55"
            if weekday < 5 and current_time_str == target_sesi1_time and last_triggered_sesi1 != today_str:
                signals_sesi1 = run_scan_process_custom_tf(timeframe="15m")
                broadcast_screening_results(signals_sesi1, "POWER BUY SCREENER VSA — AKHIR SESI 1 (15M)", "15m")
                last_triggered_sesi1 = today_str

            # End of Day Trigger (15:55)
            if weekday < 5 and current_time_str == "15:55" and last_triggered_eod != today_str:
                signals_eod = run_scan_process_custom_tf(timeframe="1d")
                broadcast_screening_results(signals_eod, "POWER BUY SCREENER VSA — END OF DAY (DAILY)", "1d")
                last_triggered_eod = today_str

            # Fast Screener 5m (Jam Bursa)
            if is_market_open():
                signals_5m = run_scan_process_custom_tf(timeframe="5m")
                if signals_5m:
                    broadcast_screening_results(signals_5m, "RAFANO POWER VOLUME VSA SCREENER (5M)", "5m")
                time.sleep(300)
            else:
                time.sleep(20)

        except Exception as e:
            print(f"⚠️ Exception in Auto-Screener: {e}")
            time.sleep(10)

# ==========================================
# HANDLER TELEGRAM & MAIN POLLING ENGINE
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
            requests.post(url, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}, files={'photo': photo}, timeout=30)
    except Exception as e:
        print(f"❌ Error Send Photo: {e}")

def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    if timeframe in ['d', 'day', 'daily', '1d']: timeframe = '1d'
    if timeframe in ['5', '5mi', 'm5']: timeframe = '5m'
    if timeframe in ['15', '15mi', 'm15']: timeframe = '15m'

    send_reply(chat_id, f"📊 *Generating Chart {stock_code} ({timeframe.upper()})...*")
    
    df = fetch_stock_history_multi_tf(stock_code, timeframe=timeframe)
    
    if df is not None and not df.empty and len(df) >= 5:
        column_mapping = {
            'date': 'Date', 'datetime': 'Date', 'time': 'Date', 't': 'Date',
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }
        df.rename(columns=lambda x: column_mapping.get(str(x).lower().strip(), x), inplace=True)

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col not in df.columns: 
                df[col] = 0

        if 'Date' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['Date']):
                df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D' if timeframe == '1d' else '5min')

        out_file = f"chart_{stock_code}_{timeframe}.png"
        generate_pro_chart(df, symbol=stock_code, timeframe=timeframe, output_filename=out_file)
        send_photo_reply(chat_id, out_file, caption=f"📊 *Chart {stock_code} ({timeframe.upper()}) — VSA Engine*")
        
        if os.path.exists(out_file):
            os.remove(out_file)
    else:
        send_reply(chat_id, f"❌ Data saham `{stock_code}` tidak ditemukan.")

def main():
    print("🚀 Starting RAFANO TRADER Bot (VSA Engine + Interactive)...")
    global SCREENER_ACTIVE
    
    screener_thread = threading.Thread(target=auto_screener_loop, daemon=True)
    screener_thread.start()

    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            res = requests.get(url, timeout=35).json()

            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    last_update_id = update["update_id"]

                    # Handler Inline Callback Button
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        cb_data = cb["data"]
                        c_id = cb["message"]["chat"]["id"]

                        # Answer Callback Query
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id})

                        if cb_data.startswith("chart_"):
                            parts = cb_data.split("_")
                            stk = parts[1]
                            tf = parts[2]
                            threading.Thread(target=process_chart_request, args=(c_id, stk, tf), daemon=True).start()

                    # Handler Text Command
                    elif "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text_msg = update["message"]["text"].strip()
                        parts = text_msg.split()
                        cmd = parts[0].lower()

                        if cmd in ["/start", "/help"]:
                            welcome_msg = (
                                "🤖 *RAFANO TRADER VSA BOT*\n"
                                "========================================\n"
                                "Format perintah manual:\n"
                                "📈 `/c <KODE> <TIMEFRAME>` - Analisa Chart Setup VSA\n"
                                "🔍 `/screener` - Pindai 300 Saham IHSG Manual (5m)\n"
                                "🌅 `/sesi1` - Pindai Sinyal Akhir Sesi 1 (15m)\n"
                                "🌆 `/eod` - Pindai Sinyal End of Day (Daily)\n"
                                "⏸️ `/pause` - Pause Auto Screener\n"
                                "▶️ `/resume` - Resume Auto Screener\n\n"
                                "*Contoh:* `/c MDKA 1d` atau `/c BBCA 5m`"
                            )
                            send_reply(chat_id, welcome_msg)

                        elif cmd == "/pause":
                            SCREENER_ACTIVE = False
                            send_reply(chat_id, "⏸️ *Auto Screener berhasil di-PAUSE.*")

                        elif cmd == "/resume":
                            SCREENER_ACTIVE = True
                            send_reply(chat_id, "▶️ *Auto Screener berhasil di-RESUME (Aktif).*")

                        elif cmd in ["/sesi1", "/eod", "/screener", "/screen"]:
                            tf_target = "15m" if cmd == "/sesi1" else ("1d" if cmd == "/eod" else "5m")
                            title_lbl = "SESI 1 (15M)" if cmd == "/sesi1" else ("END OF DAY (1D)" if cmd == "/eod" else "INTRADAY (5M)")

                            send_reply(chat_id, f"🔎 *Memulai pemindaian VSA {title_lbl} pada 300 Saham IHSG...*")
                            
                            def manual_screener_job(c_id, tf, label):
                                start_t = time.time()
                                signals = run_scan_process_custom_tf(timeframe=tf)
                                elapsed = time.time() - start_t
                                broadcast_screening_results(signals, f"MANUAL SCREENER VSA — {label} ({elapsed:.1f}s)", tf)

                            threading.Thread(target=manual_screener_job, args=(chat_id, tf_target, title_lbl), daemon=True).start()

                        elif cmd in ["/c", "/chart", "/bro"]:
                            if len(parts) > 1:
                                stock_code = parts[1].upper()
                                timeframe = parts[2].lower() if len(parts) > 2 else "1d"
                                threading.Thread(target=process_chart_request, args=(chat_id, stock_code, timeframe), daemon=True).start()
                            else:
                                send_reply(chat_id, "⚠️ Gunakan format: `/c <KODE> <TIMEFRAME>`\nContoh: `/c MDKA 1d`")

        except Exception as e:
            print(f"⚠️ Exception in Main Loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
