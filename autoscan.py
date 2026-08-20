from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
import os
import pandas as pd
import requests

try:
  import ta
except ImportError:
  os.system('pip install ta')
  import ta

# ==========================================
# 1. KONFIGURASI KREDENSIAL & ENVIRONMENT
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

STOCKBIT_USERNAME = os.getenv('STOCKBIT_USERNAME')
STOCKBIT_PASSWORD = os.getenv('STOCKBIT_PASSWORD')

MAX_WORKERS = 15

BASE_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}


# ==========================================
# 2. STOCKBIT AUTHENTICATION ENGINE
# ==========================================
def get_stockbit_token():
  if not STOCKBIT_USERNAME or not STOCKBIT_PASSWORD:
    print('⚠️ [STOCKBIT] Credentials belum diset. Menggunakan Guest Mode.')
    return None

  login_url = 'https://api.stockbit.com/v2.4/login'
  payload = {'username': STOCKBIT_USERNAME, 'password': STOCKBIT_PASSWORD}

  try:
    response = requests.post(
        login_url, json=payload, headers=BASE_HEADERS, timeout=10
    )
    if response.status_code == 200:
      token = response.json().get('data', {}).get('token')
      if token:
        print('✅ [STOCKBIT] Auto-Login Berhasil!')
        return token
  except Exception as e:
    print(f'❌ [STOCKBIT] Error Login: {e}')

  return None


# ==========================================
# 3. STOCKBIT DATA FETCHERS
# ==========================================
def get_stockbit_kline(symbol, token):
  url = f'https://api.stockbit.com/v2.4/chart/kline?symbol={symbol}&resolution=D&limit=100'
  headers = BASE_HEADERS.copy()
  if token:
    headers['Authorization'] = f'Bearer {token}'

  try:
    res = requests.get(url, headers=headers, timeout=8)
    if res.status_code == 200:
      raw_data = res.json().get('data', [])
      if not raw_data:
        return None

      df = pd.DataFrame(raw_data)
      df.rename(
          columns={
              't': 'Timestamp',
              'o': 'Open',
              'h': 'High',
              'l': 'Low',
              'c': 'Close',
              'v': 'Volume',
          },
          inplace=True,
      )

      df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
      df.set_index('Date', inplace=True)
      return df
  except Exception:
    pass
  return None


def check_stockbit_flow(symbol, token):
  if not token:
    return 'N/A (Public Mode)', 0

  url = f'https://api.stockbit.com/v2.4/foreignflow/{symbol}'
  headers = BASE_HEADERS.copy()
  headers['Authorization'] = f'Bearer {token}'

  net_foreign_val = 0
  try:
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      net_foreign_val = res.json().get('data', {}).get('net_foreign_val', 0)
  except Exception:
    pass

  if net_foreign_val > 0:
    return f'NET BUY (+Rp {round(net_foreign_val / 1e9, 2)}B)', net_foreign_val
  elif net_foreign_val < 0:
    return (
        f'NET SELL (-Rp {round(abs(net_foreign_val) / 1e9, 2)}B)',
        net_foreign_val,
    )

  return 'NEUTRAL / BANDAR ACCUM', 0


# ==========================================
# 4. INTRADAY VOLUME PROJECTION
# ==========================================
def calculate_projected_volume(current_volume):
  now = datetime.now().time()
  t_start_s1, t_end_s1 = time(9, 0), time(12, 0)
  t_start_s2, t_end_s2 = time(13, 30), time(16, 0)

  elapsed_minutes = 0
  if now < t_start_s1:
    return current_volume
  elif t_start_s1 <= now <= t_end_s1:
    elapsed_minutes = (now.hour - 9) * 60 + now.minute
  elif t_end_s1 < now < t_start_s2:
    elapsed_minutes = 180
  elif t_start_s2 <= now <= t_end_s2:
    elapsed_minutes = 180 + ((now.hour - 13) * 60 + now.minute - 30)
  else:
    return current_volume

  if elapsed_minutes < 15:
    return current_volume

  projection_factor = 420.0 / elapsed_minutes
  return current_volume * projection_factor


# ==========================================
# 5. AUTO-FETCH ALL IHSG STOCKS
# ==========================================
def get_all_ihsg_stocks():
  url = 'https://raw.githubusercontent.com/mfikria/idx-stocks/main/stocks.json'
  try:
    res = requests.get(url, timeout=10)
    if res.status_code == 200:
      data = res.json()
      stocks = [item['ticker'] for item in data if len(item['ticker']) == 4]
      print(f'✅ [IHSG ENGINE] Berhasil mengambil {len(stocks)} emiten IHSG!')
      return stocks
  except Exception as e:
    print(f'⚠️ [IHSG ENGINE] Gagal fetch data IHSG: {e}')

  return ['FPNI', 'KAEF', 'GIAA', 'NIKL', 'FUTR', 'BBRI', 'BMRI', 'TLKM', 'ASII']


# ==========================================
# 6. SIGNAL SCORING ENGINE (DILONGGARKAN)
# ==========================================
def calculate_signal_score(
    vol_ratio,
    adx_val,
    rsi14,
    price_change_pct,
    is_bb_breakout,
    net_foreign_val,
    turnover_mb,
):
  score = 50  # Basis skor awal lebih longgar agar mudah masuk

  if vol_ratio >= 1.2:
    score += 15
  if price_change_pct >= 0.5:
    score += 15
  if adx_val >= 15:
    score += 10
  if is_bb_breakout:
    score += 10
  if turnover_mb >= 0.5:
    score += 10

  if score >= 80:
    grade = 'S (STRONG BUY)'
  elif score >= 65:
    grade = 'A (HIGH PROBABILITY)'
  else:
    grade = 'B (MODERATE BUY)'

  filled_blocks = int(round(score / 10))
  progress_bar = '█' * filled_blocks + '░' * (10 - filled_blocks)

  return score, grade, progress_bar


# ==========================================
# 7. ANALISIS TEKNIKAL (FILTER DILONGGARKAN)
# ==========================================
def analyze_rafano_signals(ticker, stockbit_token):
  try:
    df = get_stockbit_kline(ticker, stockbit_token)
    if df is None or len(df) < 50:
      return None

    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Vol_Avg20'] = df['Volume'].rolling(window=20).mean()

    df['ATR14'] = ta.volatility.average_true_range(
        df['High'], df['Low'], df['Close'], window=14
    )
    df['Resistance20'] = df['High'].rolling(window=20).max()
    df['SwingLow3'] = df['Low'].rolling(window=3).min()

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI14'] = 100 - (100 / (1 + (gain / loss)))

    df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)
    df['+DI'] = ta.trend.adx_pos(df['High'], df['Low'], df['Close'], window=14)
    df['-DI'] = ta.trend.adx_neg(df['High'], df['Low'], df['Close'], window=14)

    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['BB_Upper'] = bb.bollinger_hband()

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    close_price = float(curr['Close'])
    prev_close = float(prev['Close'])
    ema50 = float(curr['EMA50'])
    volume_realtime = float(curr['Volume'])
    vol_avg = float(curr['Vol_Avg20'])
    rsi14 = float(curr['RSI14'])
    atr14 = float(curr['ATR14'])
    res20 = float(prev['Resistance20'])
    swing_low3 = float(curr['SwingLow3'])

    adx_val = float(curr['ADX'])
    bb_upper = float(curr['BB_Upper'])

    projected_vol = calculate_projected_volume(volume_realtime)
    volume_ratio = round(projected_vol / vol_avg, 2) if vol_avg > 0 else 1.0

    price_change_pct = round(
        ((close_price - prev_close) / prev_close) * 100, 2
    )
    turnover_value = close_price * volume_realtime
    turnover_mb = round(turnover_value / 1_000_000_000, 2)

    # --- FILTER UTAMA (DILONGGARKAN) ---
    # Cukup pastikan harga di atas EMA 50, likuiditas wajar, dan RSI tidak jenuh beli ekstrem (>85)
    is_uptrend = close_price > ema50
    is_liquid = turnover_value >= 500_000_000  # Minimal transaksi 500 Juta
    is_not_overbought = rsi14 < 85

    if is_uptrend and is_liquid and is_not_overbought:
      is_bb_breakout = close_price >= bb_upper * 0.95
      flow_text, net_foreign_val = check_stockbit_flow(ticker, stockbit_token)

      score, grade, progress_bar = calculate_signal_score(
          vol_ratio,
          adx_val,
          rsi14,
          price_change_pct,
          is_bb_breakout,
          net_foreign_val,
          turnover_mb,
      )

      stop_loss = round(swing_low3 * 0.98, 2)
      max_sl_allowed = round(close_price * 0.93, 2)
      stop_loss = max(stop_loss, max_sl_allowed)
      sl_pct = round(((stop_loss - close_price) / close_price) * 100, 1)

      tp1_atr = close_price + (1.5 * atr14)
      tp1 = round(max(tp1_atr, res20), 2)
      if tp1 <= close_price * 1.02:
        tp1 = round(close_price * 1.03, 2)

      tp2 = round(close_price + (3.0 * atr14), 2)
      tp1_pct = round(((tp1 - close_price) / close_price) * 100, 1)
      tp2_pct = round(((tp2 - close_price) / close_price) * 100, 1)

      return {
          'ticker': ticker,
          'price': close_price,
          'change_pct': price_change_pct,
          'volume_ratio': volume_ratio,
          'turnover_mb': turnover_mb,
          'rsi': round(rsi14, 2),
          'adx': round(adx_val, 2),
          'ema50': round(ema50, 2),
          'bb_upper': round(bb_upper, 2),
          'foreign_status': flow_text,
          'stop_loss': stop_loss,
          'sl_pct': sl_pct,
          'tp1': tp1,
          'tp1_pct': tp1_pct,
          'tp2': tp2,
          'tp2_pct': tp2_pct,
          'atr': round(atr14, 2),
          'score': score,
          'grade': grade,
          'progress_bar': progress_bar,
      }
  except Exception:
    pass

  return None


# ==========================================
# 8. PENGIRIMAN ALERT TELEGRAM
# ==========================================
def send_rafano_alert(data):
  ticker = data['ticker']
  chart_url = f'https://stockbit.com/symbol/{ticker}'

  msg = f"""🔥 *RAFANO TRADER SIGNAL V9.5 (RELAXED FILTER)*
📊 Stock: [{ticker}]({chart_url}) *(Klik untuk Buka Chart)*

🎯 *SIGNAL QUALITY SCORE*
  • **Score** : `{data['score']} / 100` [{data['progress_bar']}]
  • **Grade** : `{data['grade']}`

📈 *PRICE ACTION & TREND (STOCKBIT LIVE)*
  • Close Price    : Rp {data['price']:,} (▲ +{data['change_pct']}%)
  • Trend Regime   : Above EMA 50 (Rp {data['ema50']:,}) ✓
  • ADX (14)       : {data['adx']}
  • RSI (14)       : {data['rsi']}

───────────────
📊 *ENGINE & ACCUMULATION*
  • Volatility ATR : Rp {data['atr']}
  • Vol Projection : {data['volume_ratio']}x Vol Avg 20
  • Turnover Value : Rp {data['turnover_mb']} Miliar
  • Accum Flow     : {data['foreign_status']}

───────────────
🎯 *TRADING PLAN*
  • Entry Range    : Rp {data['price']:,}
  • TP 1           : Rp {data['tp1']:,} (+{data['tp1_pct']}%)
  • TP 2           : Rp {data['tp2']:,} (+{data['tp2_pct']}%)
  • Stop Loss      : Rp {data['stop_loss']:,} ({data['sl_pct']}%)

───────────────
⚠️ *Rafano Trading Signal System.*"""

  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
  payload = {
      'chat_id': TELEGRAM_CHAT_ID,
      'text': msg,
      'parse_mode': 'Markdown',
      'disable_web_page_preview': True,
  }

  try:
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f'Gagal kirim Telegram alert untuk {ticker}: {e}')


# ==========================================
# 9. EKSEKUSI UTAMA (MULTITHREADED MAIN)
# ==========================================
def run_rafano_bot():
  print(
      f'🚀 Running Rafano Trader Signal Engine (Relaxed Mode x{MAX_WORKERS})...'
  )

  stockbit_token = get_stockbit_token()
  watchlist = get_all_ihsg_stocks()
  print(f'🔍 Scanning {len(watchlist)} saham IHSG secara paralel...')
  signals_found = 0

  with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_ticker = {
        executor.submit(
            analyze_rafano_signals, ticker, stockbit_token
        ): ticker
        for ticker in watchlist
    }

    for future in as_completed(future_to_ticker):
      ticker = future_to_ticker[future]
      try:
        signal = future.result()
        if signal:
          send_rafano_alert(signal)
          signals_found += 1
          print(
              f'✅ Alert terkirim untuk {ticker} (Score: {signal["score"]}/100'
              f' - {signal["grade"]})'
          )
      except Exception as e:
        print(f'❌ Error processing {ticker}: {e}')

  print(f'🏁 Scanning Selesai. Total Sinyal Ditemukan: {signals_found}')


if __name__ == '__main__':
  run_rafano_bot()
