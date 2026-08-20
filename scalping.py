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

MAX_WORKERS = 35

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
  url = f'https://api.stockbit.com/v2.4/chart/kline?symbol={symbol}&resolution=D&limit=50'
  headers = BASE_HEADERS.copy()
  if token:
    headers['Authorization'] = f'Bearer {token}'

  try:
    res = requests.get(url, headers=headers, timeout=6)
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
    res = requests.get(url, headers=headers, timeout=4)
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
# 5. AUTO-FETCH ALL IHSG STOCKS (INTERNAL LIST)
# ==========================================
def get_all_ihsg_stocks():
  fallback_stocks = [
      'AALI', 'ABMM', 'ACES', 'ACST', 'ADMR', 'ADRO', 'AGII', 'AGRO', 'AKRA',
      'AKSI', 'ALKA', 'ALMI', 'AMAR', 'AMFG', 'AMIN', 'AMMS', 'AMRT', 'ANDI',
      'ANJT', 'ANTM', 'APEX', 'APIC', 'APLN', 'ARCI', 'ARKA', 'ARKO', 'ARNA',
      'ARTA', 'ARTI', 'ARTO', 'ASBI', 'ASDM', 'ASEM', 'ASGR', 'ASII', 'ASJT',
      'ASPI', 'ASRI', 'ATAP', 'AUTO', 'BABP', 'BACA', 'BAIK', 'BANK', 'BAUT',
      'BBCA', 'BBHI', 'BBKP', 'BBNI', 'BBRI', 'BBTN', 'BBYB', 'BCAP', 'BCIC',
      'BDMN', 'BEKS', 'BELI', 'BELL', 'BESS', 'BEST', 'BGTG', 'BIKA', 'BINA',
      'BINO', 'BIPI', 'BIRD', 'BISI', 'BJBR', 'BJTM', 'BKDP', 'BKSL', 'BLTZ',
      'BLUE', 'BMAS', 'BMHS', 'BMRI', 'BNBA', 'BNGA', 'BNII', 'BNLI', 'BOBA',
      'BOGA', 'BOLA', 'BOLT', 'BOSS', 'BPTR', 'BRAM', 'BRIS', 'BRMS', 'BRPT',
      'BSDE', 'BSIM', 'BSSR', 'BSWD', 'BTEK', 'BTPS', 'BUKA', 'BUKK', 'BULL',
      'BUMI', 'BUVA', 'BVIC', 'BWPT', 'BYAN', 'CAKK', 'CARS', 'CASA', 'CASH',
      'CASS', 'CBRE', 'CEKA', 'CENT', 'CFIN', 'CINT', 'CITA', 'CITY', 'CLPI',
      'CMNP', 'CMPP', 'CMRY', 'CNMA', 'COAL', 'COIN', 'COLL', 'COMP', 'CPIN',
      'CSAP', 'CSIS', 'CTRA', 'CPRO', 'DADA', 'DAST', 'DEAL', 'DEWI', 'DFAM',
      'DGNS', 'DIGI', 'DILD', 'DIVA', 'DKFT', 'DMAS', 'DMMX', 'DNAR', 'DOID',
      'DSFI', 'DSNG', 'DSSA', 'DUCK', 'DVLA', 'DWGL', 'EAST', 'ECII', 'EDGE',
      'EDMS', 'ELSA', 'ELIT', 'EMTK', 'ENRG', 'ENAK', 'EPAC', 'EPMT', 'ERAA',
      'ERTX', 'ESIP', 'ESSA', 'ESTA', 'ESTI', 'EXCL', 'FAPA', 'FASW', 'FILM',
      'FIRT', 'FIRE', 'FISH', 'FITT', 'FLMC', 'FMII', 'FOLK', 'FOOD', 'FPNI',
      'FREN', 'FUTR', 'GAMA', 'GDST', 'GEMA', 'GEMS', 'GGRP', 'GIAA', 'GJTL',
      'GLVA', 'GMFI', 'GMTD', 'GOLD', 'GOTO', 'GPRA', 'GPSO', 'GRPH', 'GREN',
      'GRIA', 'GTBO', 'GTSI', 'GULA', 'GUNA', 'GWSA', 'HADE', 'HAIS', 'HALO',
      'HDIT', 'HEAL', 'HELI', 'HERO', 'HEXA', 'HITS', 'HKMU', 'HMSP', 'HOME',
      'HOMI', 'HOPE', 'HRME', 'HRUM', 'IATA', 'IBFN', 'IBST', 'ICBP', 'ICON',
      'IDEA', 'IDPR', 'IFII', 'IFSH', 'IGAR', 'IIKP', 'IKAN', 'IKAI', 'IKPN',
      'IMAS', 'IMJS', 'IMPC', 'INAF', 'INAI', 'INCI', 'INCO', 'INDF', 'INDR',
      'INKP', 'INPC', 'INPP', 'INRU', 'INTP', 'IPCC', 'IPCM', 'IPEH', 'IPOL',
      'ISAT', 'ISSP', 'ITMA', 'ITMG', 'JAYA', 'JGLE', 'JIHD', 'JKON', 'JPFA',
      'JSMR', 'JSPT', 'JTPE', 'KAEF', 'KARW', 'KAYU', 'KBLI', 'KBLM', 'KDTN',
      'KEEN', 'KEJU', 'KETR', 'KIAS', 'KICI', 'KIJA', 'KINO', 'KKGI', 'KLBF',
      'KMDS', 'KMTR', 'KOBX', 'KOIN', 'KOPI', 'KOTA', 'KPIG', 'KRAH', 'KUAS',
      'LABS', 'LAND', 'LAPD', 'LCKM', 'LEAD', 'LIFE', 'LINK', 'LION', 'LMAS',
      'LPCK', 'LPGI', 'LPIN', 'LPPF', 'LPPS', 'LRNA', 'LSIP', 'LTLS', 'LUCK',
      'MABA', 'MAGP', 'MAIN', 'MAPA', 'MAPI', 'MARI', 'MBAP', 'MBSS', 'MBTO',
      'MCOR', 'MDKA', 'MDLA', 'MDMK', 'MEDC', 'MEGA', 'MEJA', 'MENN', 'MERK',
      'META', 'MFMI', 'MGLV', 'MGRO', 'MIDI', 'MINA', 'MIRA', 'MITI', 'MKNT',
      'MKPI', 'MLBI', 'MLIA', 'MLPL', 'MLPT', 'MMIX', 'MNCK', 'MNCN', 'MOLI',
      'MPMX', 'MPRO', 'MPPA', 'MRAT', 'MSTI', 'MTDL', 'MTEL', 'MTFN', 'MTPS',
      'MTRY', 'MYOH', 'MYOR', 'MYRX', 'NANO', 'NASA', 'NASC', 'NCKL', 'NEO',
      'NETV', 'NICK', 'NICO', 'NIKL', 'NINE', 'NOBU', 'NPGF', 'NRCA', 'NUSA',
      'NZIA', 'OASA', 'OBMD', 'OCAP', 'OKAS', 'OMRE', 'PADA', 'PAMG', 'PANI',
      'PANR', 'PBRX', 'PDES', 'PEHA', 'PGAS', 'PGEO', 'PGLI', 'PGJO', 'PICO',
      'PJAA', 'PKPK', 'PLAS', 'PMJS', 'PNBN', 'PNBS', 'PNGO', 'PNIN', 'PNLF',
      'POLA', 'POLI', 'POLL', 'POLU', 'POLY', 'POOL', 'PORT', 'POSA', 'POWR',
      'PPRO', 'PRDA', 'PSAB', 'PSDN', 'PSGO', 'PSSI', 'PTBA', 'PTDU', 'PTMP',
      'PTPW', 'PTRO', 'PUDP', 'PURA', 'PWON', 'PYFA', 'RAJA', 'RALS', 'RANC',
      'RBMS', 'RDTX', 'REAL', 'RELI', 'RICY', 'RIGS', 'RISE', 'RMKE', 'ROCK',
      'ROTI', 'RUIS', 'RUNS', 'SAFE', 'SAGE', 'SAID', 'SAME', 'SAMF', 'SAPX',
      'SATU', 'SBAT', 'SBMA', 'SCCO', 'SCNP', 'SCMA', 'SDMU', 'SDPC', 'SDRA',
      'SEMA', 'SFAN', 'SGER', 'SICO', 'SIDO', 'SILO', 'SIMP', 'SKLT', 'SKRN',
      'SKYB', 'SMAR', 'SMBR', 'SMCB', 'SMDR', 'SMGR', 'SMIL', 'SMKM', 'SMMA',
      'SMMT', 'SMRA', 'SNLK', 'SOCI', 'SOFA', 'SOLA', 'SONA', 'SOSS', 'SOTS',
      'SPMA', 'SPTO', 'SRIL', 'SRSN', 'SSIA', 'SSTM', 'STAA', 'STAR', 'STRK',
      'STTP', 'SULI', 'SUNI', 'SUPR', 'SURE', 'SWID', 'TALF', 'TAMA', 'TAPG',
      'TARA', 'TAXI', 'TBIG', 'TBLA', 'TBMS', 'TCID', 'TCPI', 'TEBE', 'TECH',
      'TELE', 'TFAS', 'TGKA', 'TGRA', 'TIFA', 'TINS', 'TIRA', 'TIRT', 'TKIM',
      'TLKM', 'TMAS', 'TMPO', 'TNCA', 'TOBA', 'TOOL', 'TOPS', 'TOSK', 'TOTL',
      'TOWR', 'TPIA', 'TPMA', 'TRIN', 'TRIS', 'TRJA', 'TRUK', 'TSPC', 'TUGU',
      'TYRE', 'UANG', 'ULTJ', 'UNIC', 'UNIQ', 'UNTR', 'UNVR', 'USER', 'VICO',
      'VINS', 'VIVA', 'VKTR', 'VOKS', 'VTNY', 'WAGE', 'WAPO', 'WEHA', 'WEGE',
      'WICO', 'WIFI', 'WIIM', 'WIKA', 'WINS', 'WIRG', 'WMPP', 'WMUU', 'WOMF',
      'WOOD', 'WOWS', 'WSBP', 'WSKT', 'WTON', 'XADO', 'XBNI', 'XBSL', 'XCID',
      'XIML', 'XIPI', 'XISC', 'XIIT', 'XLBF', 'XPDN', 'XPES', 'XPLN', 'XPRO',
      'XPSG', 'XTAN', 'XVIP', 'YELO', 'YOII', 'YPAS', 'YULE', 'ZATA', 'ZBRA',
      'ZINC', 'ZYRX'
  ]
  print(f'✅ [IHSG ENGINE] Memuat total {len(fallback_stocks)} emiten aktif secara langsung.')
  return fallback_stocks


# ==========================================
# 6. SCALPING SCORING ENGINE
# ==========================================
def calculate_scalp_score(
    vol_ratio, price_change_pct, turnover_mb, is_green_candle
):
  score = 45  # Base score dinaikkan sedikit

  if is_green_candle:
    score += 15
  if price_change_pct >= 0.5:
    score += 15
  if price_change_pct >= 2.0:
    score += 10
  if vol_ratio >= 1.2:
    score += 10
  if turnover_mb >= 0.5:
    score += 10

  if score >= 75:
    grade = '🔥 SCALP A+ (HIGH MOMENTUM)'
  elif score >= 60:
    grade = '⚡ SCALP A (GOOD MOMENTUM)'
  else:
    grade = '📈 SCALP B (WATCHLIST)'

  filled_blocks = int(round(score / 10))
  progress_bar = '█' * filled_blocks + '░' * (10 - filled_blocks)

  return score, grade, progress_bar


# ==========================================
# 7. ANALISIS TEKNIKAL SCALPING (DILONGGARKAN)
# ==========================================
def analyze_scalping_signals(ticker, stockbit_token):
  try:
    df = get_stockbit_kline(ticker, stockbit_token)
    if df is None or len(df) < 20:
      return None

    df['Vol_Avg10'] = df['Volume'].rolling(window=10).mean()
    df['ATR5'] = ta.volatility.average_true_range(
        df['High'], df['Low'], df['Close'], window=5
    )

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    close_price = float(curr['Close'])
    open_price = float(curr['Open'])
    prev_close = float(prev['Close'])
    volume_realtime = float(curr['Volume'])
    vol_avg = float(df['Vol_Avg10'].iloc[-1])
    atr5 = float(df['ATR5'].iloc[-1])

    projected_vol = calculate_projected_volume(volume_realtime)
    volume_ratio = round(projected_vol / vol_avg, 2) if vol_avg > 0 else 1.0

    price_change_pct = round(
        ((close_price - prev_close) / prev_close) * 100, 2
    )
    turnover_value = close_price * volume_realtime
    turnover_mb = round(turnover_value / 1_000_000_000, 2)

    is_green_candle = close_price >= open_price
    
    # FILTER DILONGGARKAN DI SINI:
    # 1. Perubahan harga minimal > 0.0% (asalkan hijau/naik tipis)
    # 2. Turnover minimal Rp 50 Juta (0.05 Miliar)
    is_active_moving = price_change_pct > 0.0 and turnover_value >= 50_000_000

    if is_active_moving:
      flow_text, _ = check_stockbit_flow(ticker, stockbit_token)
      score, grade, progress_bar = calculate_scalp_score(
          volume_ratio, price_change_pct, turnover_mb, is_green_candle
      )

      stop_loss = round(close_price - (1.0 * atr5), 2)
      tp1 = round(close_price + (1.0 * atr5), 2)
      tp2 = round(close_price + (2.0 * atr5), 2)

      sl_pct = round(((stop_loss - close_price) / close_price) * 100, 1)
      tp1_pct = round(((tp1 - close_price) / close_price) * 100, 1)
      tp2_pct = round(((tp2 - close_price) / close_price) * 100, 1)

      return {
          'ticker': ticker,
          'price': close_price,
          'change_pct': price_change_pct,
          'volume_ratio': volume_ratio,
          'turnover_mb': turnover_mb,
          'foreign_status': flow_text,
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
# 8. PENGIRIMAN ALERT TELEGRAM SCALPING
# ==========================================
def send_scalp_alert(data):
  ticker = data['ticker']
  chart_url = f'https://stockbit.com/symbol/{ticker}'

  msg = f"""⚡ *RAFANO SCALPING RADAR (FAST MOVE)*
📊 Stock: [{ticker}]({chart_url}) *(Buka Chart)*

🎯 *SCALP SCORE*
  • **Score** : `{data['score']} / 100` [{data['progress_bar']}]
  • **Grade** : `{data['grade']}`

📈 *MOMENTUM LIVE*
  • Price         : Rp {data['price']:,} (▲ +{data['change_pct']}%)
  • Vol Spike     : {data['volume_ratio']}x Vol Avg 10
  • Turnover      : Rp {data['turnover_mb']} Miliar
  • Foreign Flow  : {data['foreign_status']}

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
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f'Gagal kirim Telegram alert untuk {ticker}: {e}')


# ==========================================
# 9. EKSEKUSI UTAMA (MULTITHREADED)
# ==========================================
def run_scalping_bot():
  print(
      f'🚀 Running Rafano Scalping Engine (Fast Scanner x{MAX_WORKERS})...'
  )

  stockbit_token = get_stockbit_token()
  watchlist = get_all_ihsg_stocks()
  print(f'🔍 Scanning {len(watchlist)} emiten untuk Scalping...')
  signals_found = 0

  with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_ticker = {
        executor.submit(
            analyze_scalping_signals, ticker, stockbit_token
        ): ticker
        for ticker in watchlist
    }

    for future in as_completed(future_to_ticker):
      ticker = future_to_ticker[future]
      try:
        signal = future.result()
        if signal:
          send_scalp_alert(signal)
          signals_found += 1
          print(
              f'✅ Scalp Alert terkirim untuk {ticker} (Score:'
              f' {signal["score"]}/100)'
          )
      except Exception as e:
        print(f'❌ Error processing {ticker}: {e}')

  print(f'🏁 Scalp Scanning Selesai. Total Sinyal Ditemukan: {signals_found}')


if __name__ == '__main__':
  run_scalping_bot()
