import datetime
import os
import time
import numpy as np
import pandas as pd
import pandas_ta as ta
import requests

# ==============================================================================
# 1. KONFIGURASI BOT TELEGRAM
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ"
)
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "5660874676")

# ==============================================================================
# 2. PARAMETER INPUT BSJP
# ==============================================================================
START_HOUR = 14
START_MINUTE = 30
END_HOUR = 15
END_MINUTE = 45

VOL_MULTIPLIER = 1.8
MA_VOL_LENGTH = 20
MIN_PRICE_CHANGE = 0.5  # %
MIN_DAILY_VOL = 2000000  # Lembar saham

EMA8_LEN = 8
EMA20_LEN = 20
EMA200_LEN = 200  # Major Trend

TP1_PCT = 3.0
TP2_PCT = 6.0
TP3_PCT = 9.0
SL_PCT = 1.5


# ==============================================================================
# 3. FUNGSI KIRIM NOTIFIKASI TELEGRAM
# ==============================================================================
def send_telegram_alert(symbol, row):
    """Mengirim format pesan alert rapi ke Telegram saat sinyal BUY muncul."""
    message = (
        f"🚀 <b>SINYAL BUY BSJP PRO MOMENTUM</b> 🚀\n"
        f"----------------------------------------\n"
        f"📈 <b>Emiten:</b> #{symbol}\n"
        f"⏰ <b>Waktu:</b> {row['datetime'].strftime('%Y-%m-%d %H:%M')} WIB\n"
        f"💰 <b>Entry Price:</b> {int(row['entry_price'])}\n"
        f"----------------------------------------\n"
        f"🎯 <b>TP 1 (+{TP1_PCT}%):</b> {int(row['tp1_price'])}\n"
        f"🎯 <b>TP 2 (+{TP2_PCT}%):</b> {int(row['tp2_price'])}\n"
        f"🎯 <b>TP 3 (+{TP3_PCT}%):</b> {int(row['tp3_price'])}\n"
        f"🛡️ <b>Stop Loss (-{SL_PCT}%):</b> {int(row['sl_price'])}\n"
        f"----------------------------------------\n"
        f"📊 <b>Volume:</b> {int(row['volume']):,} lembar\n"
        f"🔥 <b>Kenaikan Candle:</b> {row['price_change_pct']:.2f}%\n"
        f"💡 <i>Filter Major Trend EMA 200: VALID</i>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Alert Telegram terkirim untuk #{symbol}")
        else:
            print(f"❌ Gagal kirim alert ke Telegram: {response.text}")
    except Exception as e:
        print(f"⚠️ Error koneksi Telegram: {e}")


# ==============================================================================
# 4. FUNGSI PEMBULATAN FRAKSI HARGA IHSG
# ==============================================================================
def ihsg_tick(price):
    if pd.isna(price):
        return np.nan
    if price < 200:
        tick = 1.0
    elif price < 500:
        tick = 2.0
    elif price < 2000:
        tick = 5.0
    elif price < 5000:
        tick = 10.0
    else:
        tick = 25.0
    return np.round(price / tick) * tick


v_ihsg_tick = np.vectorize(ihsg_tick)


# ==============================================================================
# 5. CORE STRATEGY LOGIC
# ==============================================================================
def calculate_bsjp_signals(df, timeframe_minutes=15):
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])

    # Indikator Teknikal
    df["ema8"] = ta.ema(df["close"], length=EMA8_LEN)
    df["ema20"] = ta.ema(df["close"], length=EMA20_LEN)
    df["ema200"] = ta.ema(df["close"], length=EMA200_LEN)
    df["avg_volume"] = ta.sma(df["volume"], length=MA_VOL_LENGTH)

    lookback_break = (
        4 if timeframe_minutes >= 15 else (10 if timeframe_minutes == 5 else 8)
    )
    df["highest_high"] = (
        df["high"].shift(1).rolling(window=lookback_break).max()
    )

    # Filter Waktu Sore
    hours = df["datetime"].dt.hour
    minutes = df["datetime"].dt.minute
    is_after_start = (hours > START_HOUR) | (
        (hours == START_HOUR) & (minutes >= START_MINUTE)
    )
    is_before_end = (hours < END_HOUR) | (
        (hours == END_HOUR) & (minutes <= END_MINUTE)
    )
    df["is_time_sore"] = is_after_start & is_before_end

    # Filter Kondisi Teknikal & Trend
    df["is_volume_surge"] = df["volume"] > (df["avg_volume"] * VOL_MULTIPLIER)
    df["price_change_pct"] = (df["close"] - df["open"]) / df["open"] * 100
    df["is_price_up"] = df["price_change_pct"] >= MIN_PRICE_CHANGE
    df["is_strong_candle"] = df["close"] > df["open"]
    df["is_liquid_stock"] = df["volume"] >= MIN_DAILY_VOL
    df["is_above_major_trend"] = df["close"] > df["ema200"]
    df["is_breakout"] = df["close"] > df["highest_high"]

    # Sinyal Gabungan
    df["raw_signal"] = (
        df["is_time_sore"]
        & df["is_volume_surge"]
        & df["is_price_up"]
        & df["is_strong_candle"]
        & df["is_breakout"]
        & df["is_liquid_stock"]
        & df["is_above_major_trend"]
    )

    # Maksimal 1 Sinyal Per Hari
    df["date"] = df["datetime"].dt.date
    df["bsjp_signal"] = False

    triggered_dates = set()
    for idx, row in df.iterrows():
        current_date = row["date"]
        if row["raw_signal"]:
            if current_date not in triggered_dates:
                df.at[idx, "bsjp_signal"] = True
                triggered_dates.add(current_date)

    # Kalkulasi Entry, Multi-TP & SL
    signal_mask = df["bsjp_signal"]
    df["entry_price"] = np.nan
    df["tp1_price"] = np.nan
    df["tp2_price"] = np.nan
    df["tp3_price"] = np.nan
    df["sl_price"] = np.nan

    df.loc[signal_mask, "entry_price"] = v_ihsg_tick(
        df.loc[signal_mask, "close"]
    )
    df.loc[signal_mask, "tp1_price"] = v_ihsg_tick(
        df.loc[signal_mask, "high"] * (1 + TP1_PCT / 100)
    )
    df.loc[signal_mask, "tp2_price"] = v_ihsg_tick(
        df.loc[signal_mask, "high"] * (1 + TP2_PCT / 100)
    )
    df.loc[signal_mask, "tp3_price"] = v_ihsg_tick(
        df.loc[signal_mask, "high"] * (1 + TP3_PCT / 100)
    )
    df.loc[signal_mask, "sl_price"] = v_ihsg_tick(
        df.loc[signal_mask, "low"] * (1 - SL_PCT / 100)
    )

    return df


# ==============================================================================
# 6. ENGINE SCREENER MULTI-EMITEN
# ==============================================================================
ALERTED_SIGNALS_CACHE = set()


def run_screener(stock_data_dict):
    """Menerima dictionary data saham {'ANTM': df_antm, 'BBCA': df_bbca, ...}

    Memproses screener & memicu alert otomatis ke Telegram jika sinyal baru
    muncul.
    """
    print(
        f"\n🔍 [SCREENER RUNNING] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    for symbol, df in stock_data_dict.items():
        if df is None or df.empty:
            continue

        processed_df = calculate_bsjp_signals(df, timeframe_minutes=15)

        # Ambil candle paling baru (baris terakhir)
        last_row = processed_df.iloc[-1]

        # Cek apakah candle terakhir memicu sinyal BUY
        if last_row["bsjp_signal"]:
            signal_key = f"{symbol}_{last_row['datetime']}"

            # Cek agar tidak mengirim pesan ganda untuk candle yang sama
            if signal_key not in ALERTED_SIGNALS_CACHE:
                send_telegram_alert(symbol, last_row)
                ALERTED_SIGNALS_CACHE.add(signal_key)
            else:
                print(
                    f"ℹ️ Sinyal #{symbol} pada {last_row['datetime']} sudah pernah dikirim."
                )


# ==============================================================================
# 7. TESTING / SIMULASI PENJALANAN SCREENER
# ==============================================================================
if __name__ == "__main__":
    # Data Dummy untuk Simulasi Trigger Sinyal ANTM
    dates = pd.date_range(start="2026-08-25 14:00", periods=5, freq="15min")

    df_antm = pd.DataFrame({
        "datetime": dates,
        "open": [1500, 1510, 1520, 1515, 1530],
        "high": [1520, 1525, 1580, 1540, 1550],
        "low": [1495, 1500, 1515, 1510, 1525],
        "close": [1510, 1520, 1575, 1530, 1545],
        "volume": [500000, 600000, 5000000, 800000, 900000],
    })

    watchlist = {"ANTM": df_antm}

    # Jalankan Screener
    run_screener(watchlist)
