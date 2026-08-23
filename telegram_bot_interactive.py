import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches

# ==========================================
# KONFIGURASI TELEGRAM BOT & TIMEZONE
# ==========================================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Ganti dengan Token Bot Telegram Anda
WIB = pytz.timezone('Asia/Jakarta')

def get_now_wib():
    return datetime.now(WIB)

def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending reply: {e}")

def send_photo_reply(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
            requests.post(url, data=data, files=files, timeout=30)
    except Exception as e:
        print(f"Error sending photo: {e}")

# ==========================================
# HELPER & FORMATTING UTILITIES
# ==========================================
def safe_int(val):
    try:
        if pd.isna(val) or np.isnan(val): return 0
        return int(round(val))
    except:
        return 0

def format_large_number(num, show_sign=False):
    if pd.isna(num) or np.isnan(num): return "0"
    sign = "+" if show_sign and num > 0 else ""
    abs_num = abs(num)
    if abs_num >= 1e9:
        return f"{sign}{num/1e9:.2f}B"
    elif abs_num >= 1e6:
        return f"{sign}{num/1e6:.2f}M"
    elif abs_num >= 1e3:
        return f"{sign}{num/1e3:.2f}K"
    else:
        return f"{sign}{num:.2f}"

def round_to_ihsg_fraction(price):
    if price <= 0 or pd.isna(price): return 0
    if price < 200:
        return round(price)
    elif price < 500:
        return round(price / 2) * 2
    elif price < 2000:
        return round(price / 5) * 5
    elif price < 5000:
        return round(price / 10) * 10
    else:
        return round(price / 25) * 25

# ==========================================
# INDIKATOR TEKNIKAL & KETENTUAN LOGIS
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_atr(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()

def calculate_vsa_metrics(df):
    high, low, close, open_p, vol = df['High'], df['Low'], df['Close'], df['Open'], df['Volume']
    spread = (high - low).replace(0, 0.001)
    close_pos = (close - low) / spread
    
    vol_buy = vol * close_pos
    vol_sell = vol * (1.0 - close_pos)
    
    buy_ratio = vol_buy / vol.replace(0, 1)
    net_vol_vsa = vol_buy - vol_sell
    
    df['Vol_Buy'] = vol_buy
    df['Vol_Sell'] = vol_sell
    df['Net_Vol_VSA'] = net_vol_vsa
    
    return df, buy_ratio.tolist()

def calculate_buy_signal_strength(df):
    if len(df) < 5:
        return 50, "NEUTRAL"
    
    c_last = df['Close'].iloc[-1]
    o_last = df['Open'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    rsi = df['RSI14'].iloc[-1]
    vol_last = df['Volume'].iloc[-1]
    v1_vol = df['V1'].iloc[-1]
    
    buy_ratio = df['Vol_Buy'].iloc[-1] / max(1, df['Volume'].iloc[-1])
    net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
    
    score = 0
    if c_last > ema50: score += 25
    if c_last > o_last: score += 15
    if vol_last >= v1_vol * 1.2: score += 20
    if buy_ratio >= 0.60: score += 20
    if net_5d_vol > 0: score += 20
    
    if score >= 80:
        label = "VERY STRONG 🚀"
    elif score >= 60:
        label = "STRONG 🔥"
    elif score >= 40:
        label = "MODERATE ⚖️"
    else:
        label = "WEAK ⚠️"
        
    return score, label

# ==========================================
# DATA FETCHING (YFINANCE)
# ==========================================
def fetch_stock_history_multi_tf(symbol, timeframe="1d"):
    symbol_formatted = f"{symbol.upper()}.JK" if not symbol.endswith(".JK") else symbol.upper()
    
    interval_map = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '60m', '1d': '1d', '1w': '1wk'
    }
    period_map = {
        '1m': '5d', '5m': '1m', '15m': '1m', '30m': '1m', '1h': '3m', '1d': '1y', '1w': '2y'
    }
    
    tf_clean = timeframe.lower().strip()
    interval = interval_map.get(tf_clean, '1d')
    period = period_map.get(tf_clean, '1y')
    
    try:
        ticker = yf.Ticker(symbol_formatted)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        if df.index.tz is not None:
            df.index = df.index.tz_convert(WIB)
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

# ==========================================
# GENERATE CHART FUNCTION (FIXED AXIS)
# ==========================================
def generate_pro_chart(df, symbol="ANTM", timeframe="1d", sector_info="Industrial Sector | IHSG", output_filename="chart_output.png"):
    try:
        tf_clean = timeframe.lower().strip()
        is_intraday = tf_clean in ['1m', '5m', '15m', '30m', '1h']

        df.columns = [str(col).lower().capitalize() for col in df.columns]
        df = df.ffill().bfill()

        # Pastikan Index bertipe Datetime
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df = df.sort_index()

        last_close = df['Close'].iloc[-1]
        last_open = df['Open'].iloc[-1]
        last_high = df['High'].iloc[-1]
        last_low = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]

        # Indikator Tambahan (EMA 50 tetap digunakan sesuai konfigurasi)
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI14'] = calculate_rsi(df['Close'], period=14)
        df['Trend_Curve'] = df['EMA50']
        df['ATR'] = calculate_atr(df, period=14)

        df['Pivot_High'] = df['High'].rolling(window=12, min_periods=1).max()
        df['Pivot_Low'] = df['Low'].rolling(window=12, min_periods=1).min()
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()

        df, buy_ratios = calculate_vsa_metrics(df)
        net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
        net_vol_today = df['Net_Vol_VSA'].iloc[-1]
        last_rsi = round(df['RSI14'].iloc[-1], 2)
        
        signal_score, score_lbl = calculate_buy_signal_strength(df)

        if 'MM' not in df.columns:
            df['MM'] = (df['Close'] - df['EMA50']) / df['EMA50'] * 1000 + np.sin(np.linspace(0, 10, len(df))) * 15 - 10.9258

        plt.style.use('dark_background')
        
        fig = plt.figure(figsize=(18, 10), dpi=150, facecolor='#000000')
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

        ax_main.plot(x_indices, df['Trend_Curve'], color='#ffffff', linewidth=1.5, linestyle='-')
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
            
            net_5d_i = df['Net_Vol_VSA'].iloc[max(0, i-4):i+1].sum()
            is_bandar_accum_i = net_5d_i > 0

            is_accum_trend = (c_price > 50) and (c_price > ema_50) and (c_price > o_price) and (vol_curr >= vol_avg * 1.0) and (b_ratio >= 0.55) and is_bandar_accum_i

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
        ax_main.set_xlim(-4, len(df) + 2)

        # DASHBOARD BOX
        status_color = "#00ff00" if latest_setup["status"] == "BUY ACCUMULATION" else "#ffff00"
        dashboard_text = (
            f" 📊 RAFANO TRADER DASHBOARD\n"
            f" -------------------------\n"
            f" O: {safe_int(last_open)}  H: {safe_int(last_high)}  L: {safe_int(last_low)}  C: {safe_int(last_close)}\n"
            f" VOL: {format_large_number(last_vol)}\n"
            f" -------------------------\n"
            f" SCORE : {signal_score}% ({score_lbl})\n"
            f" STATUS: {latest_setup['status']}\n"
            f" ENTRY : {latest_setup['entry'] if latest_setup['entry'] > 0 else last_close}\n"
            f" TP1    : {latest_setup['tp1'] if latest_setup['tp1'] > 0 else round_to_ihsg_fraction(last_close*1.035)}\n"
            f" TP2    : {latest_setup['tp2'] if latest_setup['tp2'] > 0 else round_to_ihsg_fraction(last_close*1.07)}\n"
            f" SL     : {latest_setup['danger'] if latest_setup['danger'] > 0 else round_to_ihsg_fraction(last_close*0.95)}"
        )
        
        ax_main.text(0.015, 0.96, dashboard_text, transform=ax_main.transAxes, verticalalignment='top', horizontalalignment='left',
                     fontfamily='monospace', fontsize=8.5, color=status_color,
                     bbox=dict(boxstyle='round,pad=0.4', facecolor='#000000', alpha=0.70, edgecolor='#333333'))

        stat_text_right = (
            f"RSI (14)    : {last_rsi}\n"
            f"BANDAR 1W  : {'ACCUM' if net_5d_vol > 0 else 'DISTRIB'}\n"
            f"NET VOL 1D : {format_large_number(net_vol_today, show_sign=True)}\n"
            f"VSA BUY    : {safe_int(buy_ratios[-1]*100)}%"
        )
        ax_main.text(0.985, 0.96, stat_text_right, transform=ax_main.transAxes, verticalalignment='top', horizontalalignment='right',
                     fontfamily='monospace', fontsize=8.5, color='#00ffff',
                     bbox=dict(boxstyle='round,pad=0.4', facecolor='#000000', alpha=0.70, edgecolor='#333333'))

        # BADGES
        latest_ph, latest_pl = df['Pivot_High'].iloc[-1], df['Pivot_Low'].iloc[-1]
        
        ax_main.text(1.01, latest_ph, f" {safe_int(latest_ph)} ", 
                     transform=ax_main.get_yaxis_transform(),
                     color='black', backgroundcolor='#ffff00', 
                     fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)
                     
        ax_main.text(1.01, latest_pl, f" {safe_int(latest_pl)} ", 
                     transform=ax_main.get_yaxis_transform(),
                     color='black', backgroundcolor='#00ffff', 
                     fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)

        # HEADER
        fig.text(0.01, 0.975, f"{symbol}", color='#ffffff', fontsize=16, fontweight='bold')
        fig.text(0.45, 0.975, "RAFANO TRADER", color='#ffffff', fontsize=15, fontweight='bold')
        
        last_date_str = get_now_wib().strftime('%d %b %Y')
        fig.text(0.88, 0.975, f"{tf_clean.upper()} {last_date_str}", color='#ffff00', fontsize=10, fontweight='bold', ha='right')

        fig.text(0.01, 0.945, sector_info, color='#888888', fontsize=8.5)

        for i in range(len(df)):
            c, o = df['Close'].iloc[i], df['Open'].iloc[i]
            bar_color = color_neutral if abs(c - o) / max(1, o) < 0.0005 else (color_up if c >= o else color_down)
            ax_bar.add_patch(patches.Rectangle((i - 0.5, 0), 1.0, 1.0, color=bar_color))
        ax_bar.set_ylim(0, 1)
        ax_bar.axis('off')

        ax_vol.bar(x_indices, df['Vol_Sell'], color='#ff0000', width=0.8, align='center')
        ax_vol.bar(x_indices, df['Vol_Buy'], bottom=df['Vol_Sell'], color='#00ff00', width=0.8, align='center')
        ax_vol.plot(x_indices, df['V1'], color='#ffffff', linewidth=1.0, linestyle='-')
        
        net_vol_str = format_large_number(net_vol_today, show_sign=True)
        net_5d_str = format_large_number(net_5d_vol, show_sign=True)
        last_buy_pct = safe_int(buy_ratios[-1] * 100)
        vol_text = (f"Buy: {last_buy_pct}%  Sell: {100 - last_buy_pct}%  Net 1D: {net_vol_str}  Net 5D: {net_5d_str}")
        ax_vol.text(0.01, 0.85, vol_text, transform=ax_vol.transAxes, color='#00ffff', fontsize=8, fontweight='bold')
        ax_vol.set_ylim(0, df['Volume'].max() * 1.35)

        mm_colors = ['#ffff00' if v >= 0 else '#555555' for v in df['MM']]
        ax_mm.bar(x_indices, df['MM'], color=mm_colors, width=0.4)
        ax_mm.text(0.01, 0.80, "Market Maker", transform=ax_mm.transAxes, color='#ffff00', fontsize=8, fontweight='bold')
        
        ax_mm.text(1.01, df['MM'].iloc[-1], f" {df['MM'].iloc[-1]:.2f} ", 
                   transform=ax_mm.get_yaxis_transform(),
                   color='black', backgroundcolor='#ffff00', 
                   fontsize=8.5, fontweight='bold', va='center', ha='left', clip_on=False)

        # =========================================================
        # MENAMPILKAN FORMAT TANGGAL ATAU JAM PADA SUMBU X
        # =========================================================
        step = max(1, len(df) // 8)
        ticks = list(range(0, len(df), step))
        
        if is_intraday:
            labels = [df.index[k].strftime("%H:%M") for k in ticks]
        else:
            labels = [df.index[k].strftime("%b %y") if len(df) > 100 else df.index[k].strftime("%d %b") for k in ticks]

        ax_mm.set_xticks(ticks)
        ax_mm.set_xticklabels(labels, color='white', fontsize=9, rotation=0)

        plt.setp(ax_main.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

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
# PROCESS CHART & CAPTION GENERATION
# ==========================================
def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    if timeframe in ['d', 'day', 'daily', '1d']: timeframe = '1d'
    if timeframe in ['5', '5mi', 'm5']: timeframe = '5m'
    if timeframe in ['15', '15mi', 'm15']: timeframe = '15m'

    send_reply(chat_id, f"📊 *Generating Chart {stock_code.upper()} ({timeframe.upper()})...*")
    df = fetch_stock_history_multi_tf(stock_code, timeframe=timeframe)
    
    if df is not None and not df.empty and len(df) >= 5:
        column_mapping = {
            'date': 'Date', 'datetime': 'Date', 'time': 'Date', 't': 'Date',
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }
        df.rename(columns=lambda x: column_mapping.get(str(x).lower().strip(), x), inplace=True)
        
        # Hitung Metrik Ringkasan
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
        df, buy_ratios = calculate_vsa_metrics(df)
        
        last_close = safe_int(df['Close'].iloc[-1])
        prev_close = safe_int(df['Close'].iloc[-2]) if len(df) > 1 else last_close
        change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0

        last_vol = df['Volume'].iloc[-1]
        v1_vol = df['V1'].iloc[-1]
        vol_spike = (last_vol / v1_vol) if v1_vol > 0 else 0.0

        score, score_label = calculate_buy_signal_strength(df)
        buy_pct = safe_int(buy_ratios[-1] * 100)
        net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
        bandar_status = "ACCUM" if net_5d_vol > 0 else "DISTRIB"

        # Output Nama File
        output_file = f"chart_{stock_code}_{timeframe}.png"
        chart_file = generate_pro_chart(
            df, 
            symbol=stock_code.upper(), 
            timeframe=timeframe, 
            sector_info=f"IDX:{stock_code.upper()} | RAFANO TRADER ENGINE", 
            output_filename=output_file
        )
        
        # Format Caption Persis Sesuai Permintaan
        caption = (
            f"*{stock_code.upper()}* — Harga `{last_close}` ({change_pct:+.2f}%)\n"
            f"    ├  Buy Strength Score: `{score}%` ({score_label})\n"
            f"    ├ Vol Spike: `{vol_spike:.1f}x V1` | Buy Vol: `{buy_pct}%`\n"
            f"    └ Bandar 1W: `{format_large_number(net_5d_vol, show_sign=True)}` ({bandar_status})"
        )
        
        send_photo_reply(chat_id, chart_file, caption=caption)
        
        if os.path.exists(chart_file):
            os.remove(chart_file)
    else:
        send_reply(chat_id, f"❌ Data historis untuk `{stock_code.upper()}` ({timeframe.upper()}) tidak ditemukan.")

# ==========================================
# MAIN ROUTINE / TEST RUN
# ==========================================
if __name__ == "__main__":
    # Contoh pengujian lokal tanpa polling Telegram
    print("Menjalankan testing perbaikan chart...")
    process_chart_request(chat_id="12345678", stock_code="CARS", timeframe="5m")
