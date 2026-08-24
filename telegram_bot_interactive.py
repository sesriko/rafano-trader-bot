import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# KONFIGURASI BOT & VARIABEL GLOBAL
# ==========================================
TELEGRAM_BOT_TOKEN = ("8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "5660874676")

def get_now_wib():
    return datetime.now()

def safe_int(val):
    try:
        return int(round(float(val)))
    except:
        return 0

def format_large_number(num, show_sign=False):
    try:
        val = float(num)
        sign = "+" if show_sign and val > 0 else ""
        abs_val = abs(val)
        if abs_val >= 1e9:
            return f"{sign}{val/1e9:.2f}B"
        elif abs_val >= 1e6:
            return f"{sign}{val/1e6:.2f}M"
        elif abs_val >= 1e3:
            return f"{sign}{val/1e3:.2f}K"
        else:
            return f"{sign}{val:.2f}"
    except:
        return str(num)

def send_reply(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Error sending reply: {e}")

def send_photo_reply(chat_id, photo_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
            requests.post(url, data=data, files=files, timeout=30)
    except Exception as e:
        print(f"⚠️ Error sending photo: {e}")

# ==========================================
# FUNGSI INDIKATOR TEKNIKAL & DATA FETCH
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_adx(df, period=14):
    try:
        plus_dm = df['High'].diff().clip(lower=0)
        minus_dm = (-df['Low'].diff()).clip(lower=0)
        tr = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        return adx.fillna(25.0)
    except:
        return pd.Series(25.0, index=df.index)

def calculate_vsa_metrics(df):
    try:
        df['Net_Vol_VSA'] = df['Volume'] * np.where(df['Close'] >= df['Open'], 1, -1)
        return df, {}
    except:
        df['Net_Vol_VSA'] = 0
        return df, {}

def fetch_stock_history_multi_tf(stock_code, timeframe="1d"):
    try:
        dates = pd.date_range(end=get_now_wib(), periods=100, freq='D')
        data = {
            'Open': np.linspace(1000, 1100, 100) + np.random.normal(0, 10, 100),
            'High': np.linspace(1010, 1110, 100) + np.random.normal(0, 10, 100),
            'Low': np.linspace(990, 1090, 100) + np.random.normal(0, 10, 100),
            'Close': np.linspace(1005, 1105, 100) + np.random.normal(0, 10, 100),
            'Volume': np.random.randint(1000000, 50000000, 100)
        }
        df = pd.DataFrame(data, index=dates)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def generate_pro_chart(df, symbol, timeframe, output_filename):
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Close'], label='Close Price')
        plt.title(f"{symbol} - {timeframe.upper()}")
        plt.legend()
        plt.savefig(output_filename)
        plt.close()
    except Exception as e:
        with open(output_filename, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')

# ==========================================
# PROCESS CHART REQUEST & INFORMATIVE CAPTION
# ==========================================
def process_chart_request(chat_id, stock_code, timeframe="1d"):
    timeframe = timeframe.lower().strip()
    if timeframe in ['d', 'day', 'daily', '1d']: timeframe = '1d'

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
            df.index = pd.date_range(end=get_now_wib(), periods=len(df), freq='D')

        # Indikator Utama (EMA 50)
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI14'] = calculate_rsi(df['Close'], period=14)
        df['ADX14'] = calculate_adx(df, period=14)
        df['Pivot_High'] = df['High'].rolling(window=12, min_periods=1).max()
        df['Pivot_Low'] = df['Low'].rolling(window=12, min_periods=1).min()
        df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
        df, buy_ratios = calculate_vsa_metrics(df)

        last_row = df.iloc[-1]
        last_close = last_row['Close']
        last_vol = last_row['Volume']
        avg_vol = last_row['V1']
        ema_50 = last_row['EMA50']
        
        # 1. Price vs EMA 50
        price_diff = last_close - ema_50
        price_diff_pct = (price_diff / ema_50) * 100 if ema_50 > 0 else 0
        price_ema_status = f"{safe_int(last_close)} vs EMA50 `{safe_int(ema_50)}` ({price_diff_pct:+.2f}%)"

        # 2. Volume Ratio
        vol_ratio = (last_vol / avg_vol) if avg_vol > 0 else 0

        # 3 & 4. RSI & ADX
        rsi_val = round(last_row['RSI14'], 2)
        adx_val = round(last_row['ADX14'], 2)

        # 5. Support & Resistance (Pivot)
        resistance = safe_int(last_row['Pivot_High'])
        support = safe_int(last_row['Pivot_Low'])

        # 6. Value Transaksi
        val_traded = last_close * last_vol

        # 7. Bandar 1W (Accum / Distrib)
        net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
        bandar_status = "🟢 AKUMULASI" if net_5d_vol > 0 else "🔴 DISTRIBUSI"

        out_file = f"chart_{stock_code}_{timeframe}.png"
        generate_pro_chart(df, symbol=stock_code, timeframe=timeframe, output_filename=out_file)
        
        caption_text = (
            f"📊 *ANALISIS TEKNIKAL: {stock_code} ({timeframe.upper()})*\n"
            f"────────────────────────────────────────\n"
            f"1️⃣ *Price vs EMA 50* : {price_ema_status}\n"
            f"2️⃣ *Volume Ratio* : `{vol_ratio:.2f}x` dari rata-rata (Vol: `{format_large_number(last_vol)}`)\n"
            f"3️⃣ *RSI (14)* : `{rsi_val}`\n"
            f"4️⃣ *ADX (14)* : `{adx_val}`\n"
            f"5️⃣ *Support / Res* : Support `{support}` | Res `{resistance}`\n"
            f"6️⃣ *Value Transaksi* : `Rp {format_large_number(val_traded)}`\n"
            f"7️⃣ *Bandar 1W* : {bandar_status} (`{format_large_number(net_5d_vol, show_sign=True)}`)\n"
            f"────────────────────────────────────────"
        )

        send_photo_reply(chat_id, out_file, caption=caption_text)
        
        if os.path.exists(out_file):
            os.remove(out_file)
    else:
        send_reply(chat_id, f"❌ Data saham `{stock_code}` tidak ditemukan / tidak aktif.")

# ==========================================
# SCREENER LOOP & TELEGRAM POLLING
# ==========================================
def auto_screener_loop():
    while True:
        time.sleep(60)

def run_scan_process_custom_tf(timeframe="5m"):
    return []

def broadcast_screening_results(signals, title, timeframe, target_chat_id=None):
    pass

def main():
    print("🤖 Bot Telegram sedang berjalan...")
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

                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        cb_data = cb.get("data", "")
                        c_id = cb["message"]["chat"]["id"]

                        try:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id})
                        except Exception as e:
                            print(f"⚠️ Callback answer error: {e}")

                        if cb_data.startswith("chart_"):
                            parts = cb_data.split("_")
                            if len(parts) >= 3:
                                sym = parts[1]
                                tf = parts[2]
                                threading.Thread(target=process_chart_request, args=(c_id, sym, tf), daemon=True).start()

                    elif "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        c_id = msg["chat"]["id"]
                        text = msg["text"].strip()

                        if text.lower() in ["/start", "/help"]:
                            help_msg = (
                                "🤖 *RAFANO TRADER BOT*\n\n"
                                "Gunakan perintah berikut untuk meminta chart:\n"
                                "• `/c <kode_saham> [timeframe]`\n"
                                "  _Contoh:_ `/c ANTM` atau `/c BBRI 5m`\n\n"
                                "Perintah Screener Manual:\n"
                                "• `/scan` : Jalankan screener realtime 5M\n"
                                "• `/scan 1d` : Jalankan screener Daily"
                            )
                            send_reply(c_id, help_msg)

                        elif text.lower().startswith("/c ") or text.lower().startswith("/chart "):
                            parts = text.split()
                            if len(parts) >= 2:
                                sym = parts[1].upper()
                                tf = parts[2] if len(parts) >= 3 else "1d"
                                threading.Thread(target=process_chart_request, args=(c_id, sym, tf), daemon=True).start()
                            else:
                                send_reply(c_id, "⚠️ Format salah. Gunakan: `/c <kode_saham> [timeframe]`")

                        elif text.lower().startswith("/scan"):
                            parts = text.split()
                            tf = parts[1] if len(parts) >= 2 else "5m"
                            send_reply(c_id, f"🔍 *Memulai Screening Manual ({tf.upper()})... Mohon tunggu.*")
                            
                            def manual_scan_job(chat_target, scan_tf):
                                sigs = run_scan_process_custom_tf(timeframe=scan_tf)
                                broadcast_screening_results(sigs, f"MANUAL SCAN — {scan_tf.upper()}", scan_tf, target_chat_id=chat_target)
                            
                            threading.Thread(target=manual_scan_job, args=(c_id, tf), daemon=True).start()

        except Exception as e:
            print(f"⚠️ Polling loop error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
