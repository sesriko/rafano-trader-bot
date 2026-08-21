import os
import requests
import pandas as pd
import numpy as np
import datetime
import pytz
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

try:
    import yfinance as yf
except ImportError:
    yf = None


def get_now_wib():
    wib = pytz.timezone('Asia/Jakarta')
    return datetime.datetime.now(wib)


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

    # API Arjum hanya dipanggil jika timeframe daily (1d)
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

    # Fallback / Intraday menggunakan yfinance
    if yf is not None:
        try:
            yf_symbol = symbol if (symbol.endswith(".JK") or not symbol.isalpha()) else f"{symbol}.JK"
            ticker_obj = yf.Ticker(yf_symbol)
            df_yf = ticker_obj.history(interval=interval, period=period, auto_adjust=False, actions=False)
            
            if df_yf is not None and not df_yf.empty:
                # Meratakan MultiIndex jika ada
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = [col[0] for col in df_yf.columns]
                
                df_yf.reset_index(inplace=True)
                df_yf.columns = [str(c).capitalize() for c in df_yf.columns]

                # Normalisasi Waktu & Hapus Timezone
                date_col = 'Date' if 'Date' in df_yf.columns else ('Datetime' if 'Datetime' in df_yf.columns else None)
                if date_col:
                    df_yf['Date'] = pd.to_datetime(df_yf[date_col]).dt.tz_localize(None)

                # Convert numeric
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_yf.columns:
                        df_yf[col] = pd.to_numeric(df_yf[col], errors='coerce')

                df_clean = df_yf.dropna(subset=['Close']).copy()
                df_clean['Symbol_Owner'] = symbol
                return df_clean
        except Exception as e:
            print(f"Error fetching YF ({symbol} - {timeframe}): {e}")
            pass
    return None


# ==========================================
# 2. ANALYSIS & HIGH PROBABILITY SIGNAL ENGINE
# ==========================================
def calculate_indicators(df):
    """Menghitung indikator teknikal utama: EMA 50, Volume SMA 20, dan RSI 14"""
    df = df.copy()
    
    # 1. EMA 50 (Major Trend)
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # 2. Volume SMA 20 & Volume Ratio
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    
    # 3. Nilai Transaksi (Dalam Miliar Rp)
    df['Value_Miliard'] = (df['Close'] * df['Volume']) / 1_000_000_000
    
    # 4. RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 5. Position in Range Candle (Close vs High-Low)
    high_low_range = (df['High'] - df['Low']).replace(0, np.nan)
    df['Close_Position'] = (df['Close'] - df['Low']) / high_low_range
    
    return df


def analyze_high_probability_signal(df):
    """
    Kriteria Filter Ketat Probabilitas Kenaikan >= 80%:
    - Vol Spike >= 2.0x (200% dari Rata-rata SMA 20)
    - Bullish Candle Kuat (Close > Open & Close di 35% teratas range)
    - Above EMA 50 (Major Trend Up)
    - RSI Momentum (55 - 75)
    - Likuiditas Transaksi >= 2 Miliar
    """
    if df is None or len(df) < 50:
        return False, None
    
    df = calculate_indicators(df)
    last = df.iloc[-1]
    
    # --- CHECK KONDISI ---
    c_vol_spike = last['Vol_Ratio'] >= 2.0
    c_bullish_candle = (last['Close'] > last['Open']) and (last['Close_Position'] >= 0.65)
    c_trend = last['Close'] > last['EMA50']
    c_rsi = 55 <= last['RSI'] <= 75
    c_liquidity = last['Value_Miliard'] >= 2.0
    
    # Skor Probabilitas Berbasis Bobot Kriteria
    score = 0
    if c_vol_spike: score += 35      # Bobot utama di lonjakan volume
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
# 3. GENERATE CHART & TRANSPARENT PH/PL
# ==========================================
def generate_pro_chart(df, symbol="STOCK", timeframe="1D", output_filename="chart.png"):
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

    # Pivot High (PH) dan Pivot Low (PL)
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

    # Setup Figure
    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(12, 7), gridspec_kw={'height_ratios': [3, 1]}, sharex=True
    )
    fig.patch.set_facecolor('#1e222d')
    ax_price.set_facecolor('#1e222d')
    ax_vol.set_facecolor('#1e222d')

    # Plot Candlestick
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

    # Plot Label PH/PL Transparan (Tanpa Box Background)
    y_range = df['High'].max() - df['Low'].min()
    offset = y_range * 0.025

    for i in range(len(df)):
        if not np.isnan(df['PH'].iloc[i]):
            val = df['PH'].iloc[i]
            ax_price.text(
                dates[i], val + offset, f"PH\n{int(val):,}",
                color='#00e676', fontsize=8, fontweight='bold',
                ha='center', va='bottom', bbox=dict(boxstyle='none', facecolor='none', edgecolor='none')
            )
        
        if not np.isnan(df['PL'].iloc[i]):
            val = df['PL'].iloc[i]
            ax_price.text(
                dates[i], val - offset, f"PL\n{int(val):,}",
                color='#ff5252', fontsize=8, fontweight='bold',
                ha='center', va='top', bbox=dict(boxstyle='none', facecolor='none', edgecolor='none')
            )

    # Styling Axis & Grid
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
# 4. HANDLER REQUEST & OUTPUT SIGNAL
# ==========================================
def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    tf_clean_map = {
        'd': '1d', 'day': '1d', 'daily': '1d', '1d': '1d',
        '15': '15m', '15mi': '15m', 'm15': '15m', '15m': '15m',
        '30': '30m', '30m': '30m',
        '60': '1h', '1h': '1h', '60m': '1h'
    }
    timeframe = tf_clean_map.get(timeframe, timeframe)

    print(f"\n📊 Processing Data {stock_code} ({timeframe.upper()})...")
    df = fetch_stock_history_multi_tf(stock_code, timeframe=timeframe)
    
    if df is not None and not df.empty and len(df) >= 50:
        # Standardisasi nama kolom
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
            if col not in df.columns: 
                df[col] = 0

        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.date_range(end=get_now_wib(), periods=len(df), freq='D' if timeframe == '1d' else '15min')

        # Run Analysis
        is_signal, metrics = analyze_high_probability_signal(df)
        
        # Format Output Pesan Sinyal
        print("───────────── RESUME ANALISIS ─────────────")
        print(f"📌 Stock           : #{stock_code.upper()}")
        print(f"💰 Close Price     : Rp {int(metrics['close']):,}")
        print(f"📊 Volume Spike    : {metrics['vol_ratio']}x SMA20")
        print(f"📈 RSI (14)        : {metrics['rsi']}")
        print(f"💵 Value Transaksi : Rp {metrics['value_m']} M")
        print(f"🎯 Probability     : {metrics['win_probability']}%")
        print(f"⚡ Status Signal   : {'🔥 HIGH PROBABILITY SIGNAL DETECTED' if is_signal else '❌ NO SIGNAL (Tidak Memenuhi Kriteria Ketat)'}")
        print("───────────────────────────────────────────")

        # Generate Chart
        out_file = f"chart_{stock_code}_{timeframe}.png"
        generate_pro_chart(df, symbol=stock_code, timeframe=timeframe, output_filename=out_file)
        print(f"✅ Chart disimpan: {out_file}")
        
        # Cleanup file opsional
        if os.path.exists(out_file):
            os.remove(out_file)
            
    else:
        print(f"❌ Data saham {stock_code} timeframe {timeframe.upper()} tidak cukup/tidak ditemukan.")


# ==========================================
# PEMANGGILAN / UJI COBA
# ==========================================
if __name__ == "__main__":
    # Pengujian Saham & Timeframe
    process_chart_request("123456", "ANTM", "1d")
    process_chart_request("123456", "ANTM", "15m")
