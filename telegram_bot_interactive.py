import os
import time
import requests
import pandas as pd
import numpy as np
import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ==========================================
# KONFIGURASI GLOBAL & API
# ==========================================
ARJUM_API_BASE_URL = "https://stock.arjum.com/api"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
MAX_WORKERS = 35  # Set ke 35 Worker paralel

try:
    import yfinance as yf
except ImportError:
    yf = None


def get_now_wib():
    wib = pytz.timezone('Asia/Jakarta')
    return datetime.datetime.now(wib)


# ==========================================
# DAFTAR 300+ SAHAM IHSG (WATCHLIST DEFAULT)
# ==========================================
DEFAULT_300_STOCKS = [
    "AALI", "ABDA", "ABMM", "ACES", "ACST", "ADCP", "ADHI", "ADRO", "AGII", "AGRO",
    "AGRS", "AHAP", "AISA", "AKRA", "ALDO", "AMAR", "AMFG", "AMMN", "AMRT", "ANJT",
    "ANTM", "APIC", "APLN", "ARTO", "ASGR", "ASII", "ASRI", "AUTO", "AVIA", "AXIO",
    "BABP", "BBYB", "BBCA", "BBNI", "BBRI", "BBTN", "BCIC", "BDMN", "BEKS", "BEST",
    "BFIN", "BGTG", "BHAT", "BHIT", "BIPI", "BIRD", "BISP", "BJBR", "BJTM", "BKSL",
    "BKRAS", "BMRI", "BMTR", "BNGA", "BNII", "BNLI", "BPTR", "BRPT", "BRMS", "BSDE",
    "BSIM", "BSSR", "BTPS", "BUKA", "BULL", "BUMI", "BVIC", "CASA", "CASS", "CENT",
    "CFIN", "CINT", "CITA", "CITY", "CLEO", "CLPI", "CMNP", "CMPP", "CNTX", "CPIN",
    "CRAB", "CSAP", "CTRA", "DART", "DEWA", "DGNS", "DILD", "DIVA", "DKFT", "DLTA",
    "DMAS", "DOOID", "DRMA", "DSNG", "EAST", "ECII", "ENRG", "ERAA", "ERTX", "ESSA",
    "EXCL", "FAST", "FASW", "FILM", "FINN", "FIRE", "FMII", "FORU", "FPNI", "FUTR",
    "GAAA", "GDST", "GGRM", "GIAA", "GJTL", "GNBF", "GOOD", "GPRA", "GSMF", "GOTO",
    "HEAL", "HERO", "HEXA", "HITS", "HMSP", "HOKI", "HOME", "HOPE", "HRUM", "IATA",
    "IBFN", "IBST", "ICBP", "ICON", "IDPR", "IGAR", "IIKP", "IKAI", "IKBI", "IMJS",
    "INCF", "INDF", "INKP", "INPC", "INPP", "INRU", "INTD", "INTP", "IPCC", "IPPE",
    "IPTV", "IRRA", "ISAT", "ISSP", "ITMG", "JARR", "JAST", "JECC", "JMAS", "JPFA",
    "JRPT", "JSMR", "JSPT", "JTPE", "KAEF", "KARW", "KBLI", "KBLM", "KBAG", "KDSI",
    "KIJA", "KKGI", "KLBF", "KMTR", "KOBX", "KOPI", "KPIG", "KRAS", "KREN", "LPCK",
    "LPKR", "LPPF", "LRMT", "LSIP", "LTLS", "MAPA", "MAPI", "MASB", "MAHA", "MBSS",
    "MCOR", "MDKA", "MDRN", "MEDC", "MEGA", "METR", "MFIN", "MIKA", "MMLP", "MNCN",
    "MPPA", "MPMX", "MRAT", "MROA", "MSIN", "MTDL", "MTLA", "MYOR", "MYRX", "NCKL",
    "NELY", "NIKL", "PPRE", "PANR", "PANS", "PBID", "PBSA", "PGAS", "PGUN", "PJAA",
    "PKPK", "PLIN", "PNBN", "PNBS", "PNIN", "PNLF", "POLI", "POWR", "PPGL", "PTBA",
    "PTFO", "PTPP", "PTRO", "PWON", "PYFA", "RAJA", "RALS", "RANC", "RBMS", "RDTX",
    "RELI", "RICY", "RIGS", "RING", "ROTI", "SAFE", "SAME", "SAMF", "SCMA", "SIDO",
    "SIMP", "SIPD", "SKLT", "SMAR", "SMBR", "SMCB", "SMGR", "SMRA", "SMSM", "SOCI",
    "SRTG", "SSMS", "STTP", "TAPG", "TPIA", "TLKM", "TOWR", "TRIM", "TRIS", "TRUK",
    "TSPC", "TNSO", "ULTJ", "UNVR", "VICI", "VINS", "WIFIK", "WIKA", "WMUU", "WOOD",
    "WSBP", "WTON", "YPAS", "ZBRA", "ZYRX"
]


# ==========================================
# 1. FETCH DATA MULTI-TIMEFRAME
# ==========================================
def fetch_stock_history_multi_tf(symbol, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    yf_tf_map = {
        '15m': ('15m', '1mo'),
        '30m': ('30m', '1mo'),
        '1h':  ('1h',  '3mo'),
        '1d':  ('1d',  '1y'),
        '1w':  ('1wk', '2y'),
        '1mth':('1mo', '5y')
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


# ==========================================
# 2. INDIKATOR & LOGIKA FILTER SINYAL KETAT
# ==========================================
def calculate_indicators(df):
    df = df.copy()
    
    # EMA 50 (Major Trend)
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # Volume SMA 20 & Ratio
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    
    # Value Transaksi (Miliar Rp)
    df['Value_Miliard'] = (df['Close'] * df['Volume']) / 1_000_000_000
    
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Candle Body Position
    high_low_range = (df['High'] - df['Low']).replace(0, np.nan)
    df['Close_Position'] = (df['Close'] - df['Low']) / high_low_range
    
    return df


def analyze_high_probability_signal(df):
    if df is None or len(df) < 50:
        return False, None
    
    df = calculate_indicators(df)
    last = df.iloc[-1]
    
    c_vol_spike = last['Vol_Ratio'] >= 2.0
    c_bullish_candle = (last['Close'] > last['Open']) and (last['Close_Position'] >= 0.65)
    c_trend = last['Close'] > last['EMA50']
    c_rsi = 55 <= last['RSI'] <= 75
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
    
    is_valid = c_vol_spike and c_bullish_candle and c_trend and c_rsi and c_liquidity and (score >= 80)
    return is_valid, metrics


# ==========================================
# 3. GENERATE CHART PRO
# ==========================================
def generate_pro_chart(df, symbol="STOCK", timeframe="1D", output_filename="chart.png"):
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

    left_right = 3
    df['PH'] = np.nan
    df['PL'] = np.nan

    for i in range(left_right, len(df) - left_right):
        high_window = df['High'].iloc[i - left_right : i + left_right + 1]
        if df['High'].iloc[i] == high_window.max():
            df.iloc[i, df.columns.get_loc('PH')] = df['High'].iloc[i]

        low_window = df['Low'].iloc[i - left_right : i + left_right + 1]
        if df['Low'].iloc[i] == low_window.min():
            df.iloc[i, df.columns.get_loc('PL')] = df['Low'].iloc[i]

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(12, 7), gridspec_kw={'height_ratios': [3, 1]}, sharex=True
    )
    fig.patch.set_facecolor('#1e222d')
    ax_price.set_facecolor('#1e222d')
    ax_vol.set_facecolor('#1e222d')

    dates = df.index
    for i in range(len(df)):
        open_p = df['Open'].iloc[i]
        close_p = df['Close'].iloc[i]
        high_p = df['High'].iloc[i]
        low_p = df['Low'].iloc[i]
        
        color = '#26a69a' if close_p >= open_p else '#ef5350'
        
        ax_price.plot([dates[i], dates[i]], [low_p, high_p], color=color, linewidth=1)
        ax_price.plot([dates[i], dates[i]], [open_p, close_p], color=color, linewidth=4)
        
        vol = df['Volume'].iloc[i]
        ax_vol.bar(dates[i], vol, color=color, alpha=0.6, width=0.6)

    # Label PH/PL tanpa bbox
    y_range = df['High'].max() - df['Low'].min()
    offset = y_range * 0.025

    for i in range(len(df)):
        if not np.isnan(df['PH'].iloc[i]):
            val = df['PH'].iloc[i]
            ax_price.text(
                dates[i], val + offset, f"PH\n{int(val):,}",
                color='#00e676', fontsize=8, fontweight='bold',
                ha='center', va='bottom'
            )
        
        if not np.isnan(df['PL'].iloc[i]):
            val = df['PL'].iloc[i]
            ax_price.text(
                dates[i], val - offset, f"PL\n{int(val):,}",
                color='#ff5252', fontsize=8, fontweight='bold',
                ha='center', va='top'
            )

    ax_price.set_title(f"{symbol.upper()} — {timeframe.upper()}", color='white', fontsize=12, fontweight='bold', loc='left')
    ax_price.grid(True, color='#2a2e39', linestyle='--', linewidth=0.5)
    ax_vol.grid(True, color='#2a2e39', linestyle='--', linewidth=0.5)

    ax_price.tick_params(colors='white')
    ax_vol.tick_params(colors='white')

    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter('%d %b' if timeframe == '1d' else '%d %b %H:%M'))
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.savefig(output_filename, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()


# ==========================================
# 4. PARALLEL WORKER ENGINE (35 WORKERS)
# ==========================================
def process_single_stock(symbol, timeframe="1d", generate_chart=True):
    """Fungsi pembantu yang dijalankan oleh masing-masing worker"""
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

            is_signal, metrics = analyze_high_probability_signal(df)

            if is_signal:
                if generate_chart:
                    out_file = f"signal_{symbol}_{timeframe}.png"
                    generate_pro_chart(df, symbol=symbol, timeframe=timeframe, output_filename=out_file)
                return (symbol, metrics, True)
    except Exception:
        pass
    
    return (symbol, None, False)


def get_watchlist(filepath="stocks.txt"):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
            if len(stocks) > 0:
                print(f"📁 Memuat {len(stocks)} saham dari {filepath}")
                return stocks
    print(f"📋 Memuat {len(DEFAULT_300_STOCKS)} saham dari Watchlist Default")
    return DEFAULT_300_STOCKS


def run_market_screener_parallel(timeframe="1d", generate_chart=True):
    watchlist = get_watchlist()
    total_stocks = len(watchlist)
    matched_results = []

    print(f"\n🚀 MEMULAI MASS SCREENING PARALEL ({MAX_WORKERS} WORKERS)")
    print(f"📊 Total Watchlist: {total_stocks} Saham | Timeframe: {timeframe.upper()}")
    print("=" * 65)

    start_time = time.time()
    completed_count = 0

    # Eksekusi Multithreading dengan 35 Worker
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_stock, symbol, timeframe, generate_chart): symbol 
            for symbol in watchlist
        }

        for future in as_completed(futures):
            completed_count += 1
            symbol, metrics, is_signal = future.result()
            
            print(f" Progress: [{completed_count}/{total_stocks}] - Checking #{symbol}...", end="\r")

            if is_signal:
                print(f"\n🔥 MATCH: #{symbol} | Vol: {metrics['vol_ratio']}x | RSI: {metrics['rsi']} | Prob: {metrics['win_probability']}%")
                matched_results.append((symbol, metrics))

    elapsed_time = round(time.time() - start_time, 2)
    print("\n" + "=" * 65)
    print(f"⏱️ Screening Selesai dalam {elapsed_time} detik.")
    print(f"✅ Ditemukan {len(matched_results)} sinyal berkualitas tinggi (≥80%).")
    return matched_results


# ==========================================
# EKSEKUSI UTAMA
# ==========================================
if __name__ == "__main__":
    signals = run_market_screener_parallel(timeframe="1d", generate_chart=True)
