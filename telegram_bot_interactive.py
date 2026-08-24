import os
import time
import threading
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# ==========================================
# KONFIGURASI BOT & TARGET CHAT
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "5660874676")

# ==========================================
# DAFTAR 300 SAHAM PILIHAN IHSG (WATCHLIST)
# ==========================================
WATCHLIST_300 = [
    "AALI", "ABDA", "ABMM", "ACES", "ACST", "ADCP", "ADHI", "ADRO", "AGAR", "AGRO",
    "AGRS", "AHAP", "AIMS", "AISA", "AKRA", "ALDO", "AMAR", "AMAR", "AMFG", "AMMN",
    "AMRT", "ANDI", "ANJT", "ANTM", "APIC", "APLN", "ARCI", "ARNA", "ARTA", "ARTO",
    "ASGR", "ASII", "ASRI", "AUTO", "AVIA", "AXIO", "BABP", "BACA", "BAJA", "BALI",
    "BANK", "BAPA", "BATA", "BBCA", "BBHI", "BBKP", "BBLD", "BBMD", "BBNI", "BBRI",
    "BBSD", "BBTN", "BBYB", "BCIC", "BDMN", "BEBS", "BEST", "BFIN", "BGOK", "BGTG",
    "BHAT", "BHIT", "BIKA", "BIMA", "BINA", "BIPI", "BIRD", "BISI", "BJBR", "BJTM",
    "BKSL", "BLAZ", "BLTZ", "BMBL", "BMRI", "BMTR", "BNBR", "BNGA", "BNII", "BNLI",
    "BOBA", "BOLA", "BOLT", "BOSS", "BSDE", "BSIM", "BSWD", "BTEK", "BTPS", "BUKA",
    "BUKK", "BULL", "BUMI", "CASA", "CASS", "CARS", "CEKA", "CENT", "CFIN", "CINT",
    "CITA", "CLEO", "CLPI", "CMNP", "CMPP", "CMRY", "CNKO", "CNTX", "COAL", "CPIN",
    "CPRI", "CSAP", "CSRA", "CTRA", "CTTH", "DART", "DDEV", "DEWA", "DGIK", "DIGI",
    "DILD", "DMAS", "DOOID", "DOOH", "DPNS", "DSNG", "DSSD", "DUTI", "DVLA", "DXFT",
    "EAST", "ECII", "ELSA", "EMTK", "ENRG", "ERAA", "ERTX", "ESSA", "FASW", "FILM",
    "FIRE", "FISH", "FMII", "FORU", "FPNI", "FUTR", "GAAA", "GDST", "GGRM", "GIAA",
    "GJTL", "GNKF", "GOTO", "GPRA", "GSMF", "GTBO", "GWSA", "HATM", "HDIT", "HEAL",
    "HERO", "HEXA", "HITS", "HMSP", "HOKI", "HOME", "HOPE", "HRTA", "HRUM", "IATA",
    "IBFN", "IBST", "ICBP", "ICON", "IDPR", "IGAR", "IIKP", "IKAI", "IKBI", "IMJS",
    "IMPC", "INAF", "INCF", "INDF", "INKP", "INPC", "INRU", "INTD", "INTP", "IPCC",
    "IPPE", "IPTV", "IRRA", "ISAT", "ISSP", "ITMG", "JARR", "JAST", "JATP", "JKON",
    "JSMU", "JTPE", "KAEF", "KBLI", "KBLM", "KBAG", "KDSI", "KIAS", "KICI", "KIJA",
    "KKGI", "KLBF", "KMTR", "KOPI", "KPIG", "KRAS", "KREN", "LPCK", "LPKR", "LPPF",
    "LSIP", "LTLS", "MAPA", "MAPI", "MASB", "MBAP", "MBSS", "MCOL", "MCOR", "MDCCA",
    "MDKA", "MDRN", "MEDC", "MEGA", "METR", "MFIN", "MIKA", "MMLP", "MNCN", "MPPA",
    "MPRO", "MPXL", "MRAT", "MREI", "MSKY", "MTDL", "MTEL", "MTFN", "MTLA", "MYOR",
    "NATO", "NCKL", "NELY", "NFCX", "NICK", "NIKL", "NISP", "NOBU", "NRCA", "OCAP",
    "OKAS", "OMRE", "PANB", "PANI", "PANR", "PBID", "PBSA", "PEGE", "PGAS", "PGJO",
    "PGLI", "PJAA", "PKPK", "PLIN", "PNBN", "PNBS", "PNIN", "PNLF", "POLI", "POLL",
    "POLY", "POWR", "PPGL", "PPRE", "PTBA", "PTFO", "PTPP", "PTSI", "PUDP", "PZZA",
    "RAAM", "RALS", "RANC", "RBMS", "RDMD", "RDTX", "RELI", "RICY", "RIGS", "RIMO",
    "ROTI", "SAFE", "SAME", "SAMF", "SAPX", "SCMA", "SDMU", "SFC",  "SGER", "SGRO",
    "SILO", "SIMP", "SMCB", "SMDR", "SMGR", "SMKL", "SMRA", "SMSM", "SRTG", "SSMS",
    "SUDI", "TALF", "TAPG", "TPIA", "TINS", "TLKM", "TOWR", "TOBA", "TRIM", "UNVR",
    "UNTR", "VICI", "VINS", "VRNA", "WAPO", "WEGE", "WIFI", "WIKA", "WOOD", "YPAS"
]

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
        if abs_val >= 1e9: return f"{sign}{val/1e9:.2f}B"
        elif abs_val >= 1e6: return f"{sign}{val/1e6:.2f}M"
        elif abs_val >= 1e3: return f"{sign}{val/1e3:.2f}K"
        else: return f"{sign}{val:.2f}"
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
# FETCHER & CALCULATOR
# ==========================================
def fetch_stock_history(stock_code, timeframe="1d"):
    try:
        symbol = stock_code.upper().strip()
        symbol_yf = f"{symbol}.JK" if not symbol.endswith(".JK") and not symbol.startswith("^") else symbol
        
        interval = "1d" if timeframe in ['1d', 'd', 'daily'] else "5m"
        period = "1y" if interval == "1d" else "7d"

        df = yf.download(tickers=symbol_yf, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df is None or df.empty or len(df) < 50:
            return None
        return df.dropna(subset=['Close'])
    except Exception as e:
        return None

def apply_indicators(df):
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['V1'] = df['Volume'].rolling(20, min_periods=1).mean()
    
    # Net Volume & VSA Buy Ratio
    spread = (df['High'] - df['Low']).replace(0, 0.001)
    close_pos = (df['Close'] - df['Low']) / spread
    vol_buy = df['Volume'] * close_pos
    vol_sell = df['Volume'] * (1.0 - close_pos)
    
    df['Vol_Buy'] = vol_buy
    df['Net_Vol_VSA'] = vol_buy - vol_sell
    return df

def generate_chart(df, symbol, timeframe, output_filename):
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        
        up = df[df['Close'] >= df['Open']]
        down = df[df['Close'] < df['Open']]
        
        ax1.vlines(df.index, df['Low'], df['High'], color='gray', linewidth=1)
        ax1.bar(up.index, up['Close'] - up['Open'], 0.6, bottom=up['Open'], color='green', alpha=0.8)
        ax1.bar(down.index, down['Close'] - down['Open'], 0.6, bottom=down['Open'], color='red', alpha=0.8)
        
        if 'EMA50' in df.columns:
            ax1.plot(df.index, df['EMA50'], label='EMA 50', color='orange', linewidth=1.5)

        ax1.set_title(f"{symbol.upper()} ({timeframe.upper()}) - Technical Chart", fontsize=11, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, linestyle='--', alpha=0.3)

        vol_colors = ['green' if c >= o else 'red' for c, o in zip(df['Close'], df['Open'])]
        ax2.bar(df.index, df['Volume'], color=vol_colors, alpha=0.7, width=0.6)
        ax2.grid(True, linestyle='--', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_filename, dpi=150)
        plt.close()
    except Exception as e:
        print(f"Error gen chart: {e}")

# ==========================================
# CORE SCREENING ENGINE (DAILY 1D)
# ==========================================
def scan_single_stock(stock_code, timeframe="1d"):
    df = fetch_stock_history(stock_code, timeframe=timeframe)
    if df is None: return None
    
    df = apply_indicators(df)
    last = df.iloc[-1]
    
    c_close = last['Close']
    c_open = last['Open']
    c_vol = last['Volume']
    v1_vol = last['V1']
    ema50 = last['EMA50']
    
    buy_ratio = last['Vol_Buy'] / max(1, c_vol)
    net_5d_vol = df['Net_Vol_VSA'].tail(5).sum()
    
    # KRITERIA SCREENING MAJORS (EMA 50 + Volume Spike + VSA Bullish)
    is_above_ema50 = c_close > ema50
    is_bullish_candle = c_close > c_open
    is_vol_spike = c_vol >= (v1_vol * 1.2)  # Volume minimal 1.2x Rata-rata 20 Hari
    is_vsa_buy = buy_ratio >= 0.55         # Rasio Beli > 55%
    is_bandar_accum = net_5d_vol > 0        # Net Vol 5 Hari Akumulasi

    if is_above_ema50 and is_bullish_candle and is_vol_spike and is_vsa_buy and is_bandar_accum:
        return {
            "symbol": stock_code,
            "close": c_close,
            "vol_ratio": c_vol / v1_vol,
            "buy_pct": buy_ratio * 100,
            "net_5d": net_5d_vol,
            "df": df
        }
    return None

def run_scan_process(timeframe="1d", target_chat=None):
    signals = []
    print(f"🔍 [SCAN START] Memulai pemindaian 300 Saham ({timeframe.upper()})...")
    
    for stock in WATCHLIST_300:
        res = scan_single_stock(stock, timeframe=timeframe)
        if res:
            signals.append(res)
            
    if signals:
        summary_msg = f"🚀 *RAFANO SCREENER ALERT ({timeframe.upper()})*\n"
        summary_msg += f"Ditemukan *{len(signals)}* saham potensial:\n"
        summary_msg += "───────────────────\n"
        
        for item in signals:
            summary_msg += (
                f"• *{item['symbol']}* @ `{safe_int(item['close'])}` | "
                f"Vol: `{item['vol_ratio']:.1f}x` | Buy: `{safe_int(item['buy_pct'])}%`\n"
            )
        send_reply(target_chat if target_chat else TARGET_CHAT_ID, summary_msg)
        
        # Kirim Chart untuk Top 3 Sinyal Terbaik (agar Telegram tidak Spam)
        for item in signals[:3]:
            out_file = f"scan_{item['symbol']}_{timeframe}.png"
            generate_chart(item['df'], item['symbol'], timeframe, out_file)
            
            caption = (
                f"🔥 *SIGNAL: {item['symbol']}*\n"
                f"Close: `{safe_int(item['close'])}` | Vol Spike: `{item['vol_ratio']:.2f}x`\n"
                f"Net Accum 1W: `{format_large_number(item['net_5d'], show_sign=True)}`"
            )
            send_photo_reply(target_chat if target_chat else TARGET_CHAT_ID, out_file, caption=caption)
            if os.path.exists(out_file): os.remove(out_file)
    else:
        if target_chat:
            send_reply(target_chat, f"🔍 Screener ({timeframe.upper()}): Tidak ada sinyal yang memenuhi kriteria.")
    print("✅ [SCAN COMPLETE]")

# ==========================================
# THREADING & LOOP (TIAP 10 MENIT)
# ==========================================
def auto_screener_loop():
    print("⏰ Auto Screener Daily aktif (Interval 10 Menit).")
    while True:
        try:
            run_scan_process(timeframe="1d", target_chat=TARGET_CHAT_ID)
        except Exception as e:
            print(f"⚠️ Error Auto Screener: {e}")
        time.sleep(600)  # Sleep 10 menit (600 detik)

def process_chart_request(chat_id, stock_code, timeframe="1d"):
    send_reply(chat_id, f"📊 *Generating Chart {stock_code.upper()} ({timeframe.upper()})...*")
    df = fetch_stock_history(stock_code, timeframe=timeframe)
    if df is not None:
        df = apply_indicators(df)
        out_file = f"chart_{stock_code.upper()}_{timeframe}.png"
        generate_chart(df, stock_code.upper(), timeframe, out_file)
        
        last = df.iloc[-1]
        caption = (
            f"📊 *{stock_code.upper()} ({timeframe.upper()})*\n"
            f"Harga: `{safe_int(last['Close'])}` | EMA50: `{safe_int(last['EMA50'])}`\n"
            f"Volume: `{format_large_number(last['Volume'])}`"
        )
        send_photo_reply(chat_id, out_file, caption=caption)
        if os.path.exists(out_file): os.remove(out_file)
    else:
        send_reply(chat_id, f"❌ Data saham `{stock_code.upper()}` tidak ditemukan.")

def main():
    print("🤖 Bot Telegram Rafano Trader Aktif...")
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
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        c_id = msg["chat"]["id"]
                        text = msg["text"].strip()

                        if text.lower().startswith("/c "):
                            parts = text.split()
                            if len(parts) >= 2:
                                sym = parts[1].upper()
                                tf = parts[2] if len(parts) >= 3 else "1d"
                                threading.Thread(target=process_chart_request, args=(c_id, sym, tf), daemon=True).start()

                        elif text.lower().startswith("/scan"):
                            parts = text.split()
                            tf = parts[1] if len(parts) >= 2 else "1d"
                            send_reply(c_id, f"🔍 *Memulai Manual Scanning ({tf.upper()})...*")
                            threading.Thread(target=run_scan_process, args=(tf, c_id), daemon=True).start()

        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
