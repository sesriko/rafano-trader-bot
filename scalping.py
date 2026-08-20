from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
import os
import pandas as pd

try:
  from tradingview_ta import Analysis, Interval, TA_Handler
except ImportError:
  os.system('pip install tradingview-ta ta')
  from tradingview_ta import Analysis, Interval, TA_Handler

try:
  import ta
except ImportError:
  os.system('pip install ta')
  import ta

# ==========================================
# 1. KONFIGURASI KREDENSIAL & TELEGRAM
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

MAX_WORKERS = 15


# ==========================================
# 2. DAFTAR EMITEN IHSG LENGKAP & AKTIF
# ==========================================
def get_all_ihsg_stocks():
  stocks = [
      'AALI',
      'ABMM',
      'ACES',
      'ADMR',
      'ADRO',
      'AGII',
      'AGRO',
      'AKRA',
      'AMAR',
      'AMFG',
      'AMRT',
      'ANJT',
      'ANTM',
      'APLN',
      'ARCI',
      'ARKO',
      'ARNA',
      'ARTO',
      'ASII',
      'ASRI',
      'AUTO',
      'BABP',
      'BACA',
      'BBCA',
      'BBHI',
      'BBKP',
      'BBNI',
      'BBRI',
      'BBTN',
      'BBYB',
      'BCAP',
      'BDMN',
      'BELI',
      'BEST',
      'BIRD',
      'BISI',
      'BJBR',
      'BJTM',
      'BKSL',
      'BMAS',
      'BMRI',
      'BNBA',
      'BNGA',
      'BNII',
      'BRIS',
      'BRMS',
      'BRPT',
      'BSDE',
      'BSSR',
      'BTPS',
      'BUKA',
      'BULL',
      'BUMI',
      'BVIC',
      'BWPT',
      'BYAN',
      'CARS',
      'CPRO',
      'CPIN',
      'CSAP',
      'CTRA',
      'DADA',
      'DEWI',
      'DILD',
      'DMAS',
      'DOID',
      'DSNG',
      'DSSA',
      'ELSA',
      'EMTK',
      'ENRG',
      'ERAA',
      'ESSA',
      'EXCL',
      'FASW',
      'FILM',
      'FPNI',
      'FREN',
      'FUTR',
      'GEMS',
      'GIAA',
      'GJTL',
      'GMFI',
      'GOLD',
      'GOTO',
      'GPRA',
      'GTBO',
      'HEAL',
      'HERO',
      'HEXA',
      'HMSP',
      'HRUM',
      'IATA',
      'ICBP',
      'IMAS',
      'IMPC',
      'INAF',
      'INCO',
      'INDF',
      'INKP',
      'INTP',
      'IPCC',
      'ISAT',
      'ISSP',
      'ITMG',
      'JPFA',
      'JSMR',
      'KAEF',
      'KKGI',
      'KLBF',
      'KOPI',
      'KPIG',
      'LEAD',
      'LPPF',
      'LSIP',
      'MAPI',
      'MBAP',
      'MDKA',
      'MEDC',
      'MEGA',
      'MIKA',
      'MLPL',
      'MNCN',
      'MPMX',
      'MTEL',
      'MYOR',
      'NCKL',
      'NICL',
      'NIKI',
      'NOBU',
      'PANI',
      'PGAS',
      'PGEO',
      'PNBN',
      'PNLF',
      'PTBA',
      'PTRO',
      'PWON',
      'RALS',
      'RMKE',
      'ROTI',
      'SCMA',
      'SIDO',
      'SILO',
      'SIMP',
      'SMDR',
      'SMGR',
      'SMRA',
      'SOCI',
      'SSIA',
      'STAA',
      'TBIG',
      'TBLA',
      'TINS',
      'TKIM',
      'TLKM',
      'TMAS',
      'TOWR',
      'TPIA',
      'TRIS',
      'ULTJ',
      'UNTR',
      'UNVR',
      'VKTR',
      'WIFI',
      'WIIM',
      'WIKA',
      'WINS',
      'WSKT',
  ]
  return sorted(list(set(stocks)))


# ==========================================
# 3. SCALPING SCORING ENGINE
# ==========================================
def calculate_scalp_score(
    vol_ratio, price_change_pct, turnover_mb, is_green_candle
):
  score = 40

  if is_green_candle:
    score += 15
  if price_change_pct >= 1.5:
    score += 15
  if price_change_pct >= 4.0:
    score += 10
  if vol_ratio >= 1.8:
    score += 10
  if turnover_mb >= 2.0:
    score += 10

  if score >= 80:
    grade = '🔥 SCALP A+ (HIGH MOMENTUM)'
  elif score >= 65:
    grade = '⚡ SCALP A (GOOD MOMENTUM)'
  else:
    grade = '📈 SCALP B (WATCHLIST)'

  filled_blocks = int(round(score / 10))
  progress_bar = '█' * filled_blocks + '░' * (10 - filled_blocks)

  return score, grade, progress_bar


# ==========================================
# 4. ANALISIS TRADINGVIEW (PURE SCALPING)
# ==========================================
def analyze_autoscan_signals(ticker):
  try:
    # Menggunakan Interval 15 Menit untuk menangkap momentum scalping real-time
    handler = TA_Handler(
        symbol=ticker,
        exchange='IDX',
        screener='indonesia',
        interval=Interval.INTERVAL_15M,
    )

    analysis = handler.get_analysis()
    indicators = analysis.indicators

    close_price = float(indicators.get('close', 0))
    open_price = float(indicators.get('open', 0))
    volume = float(indicators.get('volume', 0))
    vol_sma20 = float(indicators.get('SMA20', volume))

    # EMA Major 200 & EMA Trigger 50 (Sesuai aturan setting Anda)
    ema_major = float(indicators.get('EMA200', 0))
    ema_trigger = float(indicators.get('EMA50', 0))

    if close_price <= 0 or ema_major <= 0 or ema_trigger <= 0:
      return None

    change_from_open = (
        ((close_price - open_price) / open_price) * 100
        if open_price > 0
        else 0.0
    )
    price_change_pct = round(change_from_open, 2)

    turnover_value = close_price * volume
    turnover_mb = round(turnover_value / 1_000_000_000, 2)
    volume_ratio = round(volume / vol_sma20, 2) if vol_sma20 > 0 else 1.0

    is_green_candle = close_price >= open_price

    # ==========================================
    # ATURAN SCALPING MURNI
    # ==========================================
    # 1. Trend: Di atas EMA Major 200 dan EMA Trigger 50
    is_uptrend = close_price > ema_major and close_price > ema_trigger

    # 2. Momentum Scalping: Kenaikan minimal +1% (tanpa batas atas agar saham kencang tetap masuk),
    #    volume melonjak minimal 1.5x dari rata-rata, dan candle hijau.
    is_price_valid = price_change_pct >= 1.0
    is_volume_spike = volume_ratio >= 1.5
    is_liquidity_valid = turnover_mb >= 1.0

    is_scalp_ready = (
        is_uptrend
        and is_price_valid
        and is_volume_spike
        and is_liquidity_valid
        and is_green_candle
    )

    if is_scalp_ready:
      score, grade, progress_bar = calculate_scalp_score(
          volume_ratio, price_change_pct, turnover_mb, is_green_candle
      )

      approx_atr = close_price * 0.012
      stop_loss = round(close_price - (1.0 * approx_atr), 2)
      tp1 = round(close_price + (1.2 * approx_atr), 2)
      tp2 = round(close_price + (2.5 * approx_atr), 2)

      sl_pct = round(((stop_loss - close_price) / close_price) * 100, 1)
      tp1_pct = round(((tp1 - close_price) / close_price) * 100, 1)
      tp2_pct = round(((tp2 - close_price) / close_price) * 100, 1)

      return {
          'ticker': ticker,
          'price': close_price,
          'change_pct': price_change_pct,
          'volume_ratio': volume_ratio,
          'turnover_mb': turnover_mb,
          'stop_loss': stop_loss,
          'sl_pct': sl_pct,
          'tp1': tp1,
          'tp1_pct': tp1_pct,
          'tp2': tp2,
          'tp2_pct': tp2_pct,
          'score': score,
          'grade': grade,
          'progress_bar': progress_bar,
      }
  except Exception:
    pass

  return None


# ==========================================
# 5. KIRIM ALERT TELEGRAM
# ==========================================
def send_autoscan_alert(data):
  ticker = data['ticker']
  chart_url = f'https://stockbit.com/symbol/{ticker}'

  msg = f"""⚡ *RAFANO PURE SCALPING RADAR (15m)*
📊 Stock: [{ticker}]({chart_url}) *(Buka Chart)*

🎯 *SCALP SCORE*
  • **Score** : `{data['score']} / 100` [{data['progress_bar']}]
  • **Grade** : `{data['grade']}`

📈 *MOMENTUM LIVE*
  • Price         : Rp {data['price']:,} (▲ +{data['change_pct']}%)
  • Vol Ratio     : {data['volume_ratio']}x Vol SMA
  • Turnover      : Rp {data['turnover_mb']} Miliar

───────────────
🎯 *SCALPING QUICK PLAN*
  • Buy/Entry     : Rp {data['price']:,}
  • Target 1 (TP1): Rp {data['tp1']:,} (+{data['tp1_pct']}%)
  • Target 2 (TP2): Rp {data['tp2']:,} (+{data['tp2_pct']}%)
  • Fast Stop Loss: Rp {data['stop_loss']:,} ({data['sl_pct']}%)

───────────────
⚠️ *Fast Execution & Strict Risk Management.*"""

  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
  payload = {
      'chat_id': TELEGRAM_CHAT_ID,
      'text': msg,
      'parse_mode': 'Markdown',
      'disable_web_page_preview': True,
  }

  try:
    import requests

    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f'Gagal kirim Telegram alert untuk {ticker}: {e}')


# ==========================================
# 6. EKSEKUSI UTAMA
# ==========================================
def run_autoscan_bot():
  print(
      f'🚀 Running Rafano Pure Scalping Engine (15m Interval | x{MAX_WORKERS}'
      ' Workers)...'
  )

  watchlist = get_all_ihsg_stocks()
  print(
      f'🔍 Scanning {len(watchlist)} emiten IDX dengan aturan Pure Scalping...'
  )
  signals_found = 0

  with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_ticker = {
        executor.submit(analyze_autoscan_signals, ticker): ticker
        for ticker in watchlist
    }

    for future in as_completed(future_to_ticker):
      ticker = future_to_ticker[future]
      try:
        signal = future.result()
        if signal:
          send_autoscan_alert(signal)
          signals_found += 1
          print(
              f'✅ Scalp Alert terkirim untuk {ticker} (Score:'
              f' {signal["score"]}/100)'
          )
      except Exception as e:
        print(f'❌ Error processing {ticker}: {e}')

  print(f'🏁 Scan Selesai. Total Sinyal Scalping Ditemukan: {signals_found}')


if __name__ == '__main__':
  run_autoscan_bot()
