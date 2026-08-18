import datetime
import io
import logging
import os
import time
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests
import pytz
import yfinance as yf

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuration Telegram & Timezone
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
TZ_WIB = pytz.timezone("Asia/Jakarta")

# List Emiten IHSG untuk Di-scan (Tambahkan sesuai kebutuhan)
TICKERS = ["KAEF.JK", "FUTR.JK", "NIKL.JK", "GIAA.JK", "BBRI.JK", "TLKM.JK"]


# ==========================================
# 1. INDIKATOR & SIGNAL ENGINE (EMA 50)
# ==========================================
def calculate_indicators(df):
    """Menghitung EMA 50, RSI 14, MACD, dan Volume MA."""
    df = df.copy()

    # Fixed EMA 50 sebagai Trend Engine
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # RSI 14
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # Volume MA 20
    df["Vol_MA20"] = df["Volume"].rolling(window=20).mean()

    return df


def check_volume_spike_signal(df):
    """Deteksi Volume Spike & Sinyal Konfirmasi menggunakan EMA 50."""
    if len(df) < 50:
        return False, "Data tidak cukup"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Kondisi: Harga di atas EMA 50 & Volume > 2x Volume MA20
    above_ema50 = last["Close"] > last["EMA_50"]
    volume_spike = last["Volume"] > (2.0 * last["Vol_MA20"])
    bullish_candle = last["Close"] > last["Open"]

    is_signal = above_ema50 and volume_spike and bullish_candle
    reason = (
        f"Vol Spike ({last['Volume']/last['Vol_MA20']:.1f}x MA20) & Above EMA50"
        if is_signal
        else "No Signal"
    )

    return is_signal, reason


def calculate_buy_signal_strength(df):
    """Kalkulasi skor kekuatan sinyal (0-100%) berbasis EMA 50."""
    if len(df) < 50:
        return 0

    last = df.iloc[-1]
    score = 0

    # Filter Trend Utama: EMA 50 (Max 30 Poin)
    if last["Close"] > last["EMA_50"]:
        score += 30

    # Volume Spike (Max 30 Poin)
    if last["Volume"] > (2 * last["Vol_MA20"]):
        score += 30
    elif last["Volume"] > last["Vol_MA20"]:
        score += 15

    # Momentum RSI (Max 20 Poin)
    if 50 <= last["RSI"] <= 70:
        score += 20

    # MACD Bullish Crossover (Max 20 Poin)
    if last["MACD"] > last["MACD_Signal"]:
        score += 20

    return score


# ==========================================
# 2. VISUALIZER & TELEGRAM SENDER
# ==========================================
def generate_chart(df, ticker, timeframe="1D"):
    """Membuat chart candlesticks dengan overlay EMA 50 dan Volume."""
    df_plot = df.tail(60).copy()

    # Penyesuaian Timezone WIB pada Index Dataframe
    if df_plot.index.tzinfo is None:
        df_plot.index = df_plot.index.tzlocalize("UTC").tz_convert(TZ_WIB)
    else:
        df_plot.index = df_plot.index.tz_convert(TZ_WIB)

    apds = [
        mpf.make_addplot(df_plot["EMA_50"], color="orange", width=1.5),
    ]

    fig, axes = mpf.plot(
        df_plot,
        type="candle",
        style="charles",
        title=f"\n{ticker} - {timeframe} (EMA 50 System)",
        volume=True,
        addplot=apds,
        returnfig=True,
        figsize=(10, 6),
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def send_telegram_alert(photo_buf, caption):
    """Mengirim pesan dan chart ke Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("chart.png", photo_buf, "image/png")}
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"}

    try:
        response = requests.post(url, data=data, files=files, timeout=10)
        return response.json()
    except Exception as e:
        logging.error(f"Gagal mengirim Telegram Alert: {e}")
        return None


# ==========================================
# 3. CORE SCREENER PROCESS
# ==========================================
def run_scan_process(tickers, interval="1d", period="3mo"):
    """Eksekusi screening emiten berdasarkan parameter yang ditentukan."""
    now_wib = datetime.datetime.now(TZ_WIB)
    logging.info(
        f"Memulai Scan [{interval}] pada {now_wib.strftime('%Y-%m-%d %H:%M:%S WIB')}"
    )

    for ticker in tickers:
        try:
            data = yf.download(
                ticker, period=period, interval=interval, progress=False
            )
            if data.empty or len(data) < 50:
                continue

            # Flatten MultiIndex Columns jika ada (efek yfinance terbaru)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            df = calculate_indicators(data)
            is_signal, reason = check_volume_spike_signal(df)

            if is_signal:
                score = calculate_buy_signal_strength(df)
                last = df.iloc[-1]

                caption = (
                    f"🚀 <b>RAFANO SIGNAL (EMA 50) ALERT</b>\n"
                    f"<b>Emiten:</b> {ticker}\n"
                    f"<b>Timeframe:</b> {interval}\n"
                    f"<b>Harga Terakhir:</b> {last['Close']:.0f}\n"
                    f"<b>Kekuatan Sinyal:</b> {score}%\n"
                    f"<b>RSI:</b> {last['RSI']:.1f}\n"
                    f"<b>Keterangan:</b> {reason}\n"
                    f"<i>Waktu: {now_wib.strftime('%H:%M:%S WIB')}</i>"
                )

                chart_buf = generate_chart(df, ticker, timeframe=interval)
                send_telegram_alert(chart_buf, caption)
                logging.info(f"Signal dikirim untuk {ticker}")

        except Exception as e:
            logging.error(f"Error processing {ticker}: {e}")


def is_market_open():
    """Mengecek apakah saat ini jam bursa IHSG aktif (Senin-Jumat, 09:00 - 16:00 WIB)."""
    now_wib = datetime.datetime.now(TZ_WIB)
    if now_wib.weekday() >= 5:  # Sabtu & Minggu Libur
        return False
    start_time = now_wib.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = now_wib.replace(hour=16, minute=0, second=0, microsecond=0)
    return start_time <= now_wib <= end_time


# ==========================================
# 4. MAIN POLLING LOOP
# ==========================================
def main():
    """Fungsi Utama Bot Loop."""
    logging.info("=== RAFANO TRADER BOT (EMA 50 ENGINE) STARTED ===")
    last_scan_time = 0
    scan_interval_seconds = 300  # Scan setiap 5 menit saat bursa buka

    while True:
        try:
            current_time = time.time()

            # Jalankan scanner secara berkala saat market aktif
            if (
                is_market_open()
                and (current_time - last_scan_time) > scan_interval_seconds
            ):
                run_scan_process(TICKERS, interval="5m", period="5d")
                last_scan_time = current_time

            # Tidur sejenak untuk menghemat CPU dan menghindari rate-limit
            time.sleep(10)

        except KeyboardInterrupt:
            logging.info("Bot dihentikan oleh user.")
            break
        except Exception as e:
            logging.error(f"Error pada Loop Utama: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()
