import os
import io
import math
import time as time_module
import logging
import asyncio
import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("RAFANO_TRADER")


# ------------------------------------------------------------
# TELEGRAM
# ------------------------------------------------------------
#
# PERTAHANKAN TOKEN HARDCODED ANDA DI FALLBACK INI SESUAI
# PERMINTAAN ANDA.
#
# Saya tidak menyalin token rahasia dari pesan sebelumnya.
#
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8833563003:AAGSx750u_QXWpr91sd3yuD6LcnMXtWWrxQ"
)

TARGET_CHAT_ID = os.getenv(
    "TARGET_CHAT_ID",
    "5660874676"
)

# Backward-compatible alias used by the existing screener code.
TELEGRAM_CHAT_ID = TARGET_CHAT_ID

# Default score threshold for live signals.
MIN_SIGNAL_SCORE = 65


# ------------------------------------------------------------
# TIMEZONE
# ------------------------------------------------------------

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


# ------------------------------------------------------------
# MARKET CONFIG
# ------------------------------------------------------------

MARKET_OPEN_1 = time(9, 0)
MARKET_CLOSE_1 = time(12, 0)

MARKET_OPEN_2 = time(13, 30)
MARKET_CLOSE_2 = time(16, 0)


# ------------------------------------------------------------
# SCREENER CONFIG
# ------------------------------------------------------------

SCAN_INTERVAL_SECONDS = 300

SIGNAL_COOLDOWN_SECONDS = 3600

MIN_PRICE = 50

MIN_AVG_VALUE = 500_000_000

MIN_DAILY_ROWS = 220

MIN_INTRADAY_ROWS = 100

RELATIVE_VOLUME_THRESHOLD = 1.8

MAX_SIGNALS_PER_SCAN = 20


# ------------------------------------------------------------
# CHART RATE LIMIT
# ------------------------------------------------------------

CHART_COOLDOWN_SECONDS = 30

chart_request_cooldowns: Dict[int, datetime] = {}

signal_cooldowns: Dict[str, datetime] = {}


# ============================================================
# 2. STOCK UNIVERSE
# ============================================================

TICKERS = [
    "AALI", "ABDA", "ABMM", "ACES", "ACST", "ADEL", "ADMF", "ADMG",
    "ADRO", "AGAR", "AGII", "AGRO", "AGRS", "AHAP", "AIMS", "AISA",
    "AKRA", "AKSI", "ALDO", "ALKA", "ALMI", "ALTO", "AMAR", "AMFG",
    "AMIN", "AMRT", "ANDI", "ANJT", "ANTM", "APIC", "APII", "APLI",
    "APLN", "ARCI", "ARGO", "ARKA", "ARMY", "ARTO", "ASBI", "ASDM",
    "ASGR", "ASII", "ASJT", "ASMI", "ASRI", "ASRM", "ASSA", "ATIC",
    "AUTO", "AVIA", "BABP", "BACA", "BAJA", "BALI", "BANK", "BAPA",
    "BATA", "BBCA", "BBHI", "BBKP", "BBLD", "BBMD", "BBNI", "BBRI",
    "BBSB", "BBTN", "BBYB", "BCIC", "BCIP", "BDMN", "BEKS", "BEST",
    "BFIN", "BGTG", "BHAT", "BHIT", "BIKA", "BINA", "BIPI", "BIRD",
    "BISDE", "BISC", "BJBR", "BJTM", "BKDP", "BKSL", "BLAZ", "BLTZ",
    "BLUE", "BMAS", "BMHS", "BMRI", "BMTR", "BNBR", "BNGA", "BNII",
    "BNLI", "BOBA", "BOLA", "BOLT", "BOSS", "BPFI", "BPII", "BRPT",
    "BSDE", "BSIM", "BSWD", "BTEK", "BTPS", "BSSR", "BREN", "BRMS",
    "BRIS", "BUKA", "BUKK", "BULL", "BUMI", "BVIC", "BWPT", "BYAN",
    "CAKK", "CAMP", "CASA", "CASH", "CASS", "CEKA", "CENT", "CFIN",
    "CINT", "CITA", "CITY", "CLPI", "CMNP", "CMPP", "CNKO", "CNTX",
    "COWL", "CPIN", "CPRI", "CPRO", "CSAP", "CSIS", "CSRA", "CTBN",
    "CTRA", "CTRP", "DART", "DEWA", "DEXA", "DFAM", "DGIK", "DIGI",
    "DILD", "DIVA", "DKFT", "DLTA", "DMAS", "DNAR", "DNET", "DOID",
    "DPNS", "DSFI", "DSNG", "DSSA", "DUTI", "DVLA", "DWGL", "EAST",
    "ECII", "ENRG", "EPMT", "ERAA", "ERTX", "ESSA", "ESTI", "ETWA",
    "EXCL", "FAST", "FASW", "FISH", "FPNI", "FUTR", "GAAA", "GDST",
    "GEMA", "GGRM", "GIAA", "GJTL", "GLOB", "GLVA", "GOOD", "GOTO",
    "GPRA", "GSMF", "GTBO", "GWSA", "GZCO", "HATM", "HDFA", "HEAL",
    "HERO", "HEXA", "HITS", "HMSP", "HOKI", "HOME", "HOPE", "HRUM",
    "IATA", "IBFN", "IBST", "ICBP", "ICON", "IDPR", "IGAR", "IIKP",
    "IKAI", "IKBI", "IMPC", "INAF", "INCF", "INCI", "INDF", "INDY",
    "INKP", "INPC", "INPP", "INRU", "INTA", "INTD", "INTP", "IPCC",
    "IPCM", "IPOL", "ISAT", "ISSP", "ITMA", "ITMG", "JAST", "JAWA",
    "JECC", "JKSW", "JPFA", "JRPT", "JSMR", "JSPT", "JTPE", "KAEF",
    "KARW", "KBAG", "KBLI", "KBLM", "KDSI", "KIAS", "KICI", "KIJA",
    "KKGI", "KLBF", "KMTR", "KOBX", "KOIN", "KONI", "KOPI", "KPAL",
    "KPAS", "KPEI", "KPIG", "KRAS", "KREN", "LPCK", "LPIN", "LPKR",
    "LPLI", "LPPF", "LTLS", "LUXI", "MAIN", "MAPA", "MAPI", "MARK",
    "MASA", "MAYA", "MBAP", "MBSS", "MDLN", "MEDC", "METR", "MFIN",
    "MGNA", "MICE", "MIDI", "MIKA", "MLBI", "MLIA", "MLPT", "MMSD",
    "MNCN", "MPPA", "MPMX", "MTDL", "MTLA", "MYOR", "NATO", "NCLK",
    "NETV", "NIKL", "NISP", "PANR", "PBRX", "PGAS", "PGJO", "PNBN",
    "PNBS", "PNIN", "PNLF", "POLY", "POWR", "PRDA", "PTBA", "PTPP",
    "PSSI", "PWON", "PYFA", "RAJA", "RALS", "RANC", "RBMS", "RDMD",
    "RELI", "RICY", "RIGS", "RISE", "ROTI", "SAFE", "SAME", "SAMF",
    "SAPX", "SCCO", "SCMA", "SDPC", "SGER", "SGRO", "SHID", "SILO",
    "SIMP", "SINO", "SIPD", "SKBM", "SKLT", "SMBR", "SMDR", "SMGR",
    "SMKL", "SMMA", "SMRA", "SMSM", "SOUL", "SPTO", "SRIL", "SRTG",
    "SSMS", "SSUC", "STAA", "SUPR", "TALF", "TAPA", "TAPG", "TBIG",
    "TBLA", "TCID", "TELE", "TFCO", "TFIN", "TLKM", "TMAS", "TMPO",
    "TNCA", "TOBA", "TOTAL", "TPIA", "TPMA", "TROW", "TSPC", "TSRI",
    "TOTO", "UCID", "ULTJ", "UNIC", "UNIQ", "UNTR", "UNVR", "URBN",
    "VBNI", "VRNA", "WAPO", "WEGE", "WIFI", "WIIM", "WIMD", "WINS",
    "WIRT", "WMIC", "WOOD", "WOWS", "WSKT", "WTON", "YPAS", "YULE",
    "ZBRA"
]


# ============================================================
# 3. DATA CLASSES
# ============================================================

@dataclass
class Signal:
    ticker: str
    price: float
    score: int
    rating: str

    rsi: float
    relative_volume: float
    buy_pressure: float

    atr: float
    vwap: float

    resistance: float
    breakout: bool

    stock_return_20d: float
    ihsg_return_20d: float
    relative_strength: float

    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float

    regime: str


# ============================================================
# 4. TIME / MARKET SESSION
# ============================================================

def now_jakarta() -> datetime:
    return datetime.now(JAKARTA_TZ)


def is_market_open(now: Optional[datetime] = None) -> bool:
    """
    Basic BEI session check.

    NOTE:
    This does not yet contain the official BEI holiday calendar.
    It prevents weekend scanning and handles normal sessions.
    """

    now = now or now_jakarta()

    if now.weekday() >= 5:
        return False

    current = now.time()

    session_1 = MARKET_OPEN_1 <= current <= MARKET_CLOSE_1
    session_2 = MARKET_OPEN_2 <= current <= MARKET_CLOSE_2

    return session_1 or session_2


def current_session() -> str:
    now = now_jakarta()

    if now.weekday() >= 5:
        return "CLOSED"

    current = now.time()

    if MARKET_OPEN_1 <= current <= MARKET_CLOSE_1:
        return "SESSION_1"

    if MARKET_OPEN_2 <= current <= MARKET_CLOSE_2:
        return "SESSION_2"

    return "CLOSED"


# ============================================================
# 5. TICKER VALIDATION
# ============================================================

def normalize_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()

    if ticker.endswith(".JK"):
        ticker = ticker[:-3]

    return ticker


def is_valid_ticker(ticker: str) -> bool:
    ticker = normalize_ticker(ticker)

    return (
        ticker in TICKERS
        and ticker.isalnum()
        and len(ticker) <= 6
    )


# ============================================================
# 6. DATA FETCHING
# ============================================================

def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        # Take first level where possible.
        df.columns = df.columns.get_level_values(0)

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        logger.warning(
            "Missing columns: %s",
            missing
        )
        return pd.DataFrame()

    df = df[required].copy()

    for col in required:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    )

    df = df[~df.index.duplicated(keep="last")]

    return df


def download_daily_batch(
    tickers: List[str],
) -> Dict[str, pd.DataFrame]:

    symbols = [
        f"{ticker}.JK"
        for ticker in tickers
    ]

    logger.info(
        "Downloading daily batch: %d tickers",
        len(symbols)
    )

    try:
        raw = yf.download(
            tickers=symbols,
            period="2y",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

    except Exception as e:
        logger.exception(
            "Daily batch download failed: %s",
            e
        )
        return {}

    result = {}

    for ticker in tickers:

        symbol = f"{ticker}.JK"

        try:

            if isinstance(raw.columns, pd.MultiIndex):

                if symbol not in raw.columns.get_level_values(0):
                    continue

                df = raw[symbol]

            else:
                df = raw

            df = clean_yfinance_columns(df)

            if len(df) >= MIN_DAILY_ROWS:
                result[ticker] = df

        except Exception as e:
            logger.warning(
                "Failed parsing %s: %s",
                ticker,
                e
            )

    logger.info(
        "Daily batch complete: %d/%d valid",
        len(result),
        len(tickers)
    )

    return result


def download_intraday(
    ticker: str,
    interval: str = "15m",
) -> Optional[pd.DataFrame]:

    symbol = f"{ticker}.JK"

    try:

        df = yf.download(
            symbol,
            period="60d",
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        df = clean_yfinance_columns(df)

        if df.empty:
            return None

        return df

    except Exception as e:

        logger.warning(
            "Intraday download failed for %s: %s",
            ticker,
            e
        )

        return None


# ============================================================
# 7. INDICATORS
# ============================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def rsi_wilder(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (
        100 / (1 + rs)
    )

    # If loss is exactly zero and gain exists,
    # RSI is effectively 100.
    rsi = rsi.where(
        ~((avg_loss == 0) & (avg_gain > 0)),
        100
    )

    return rsi


def atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.Series:

    previous_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]

    tr2 = (
        df["High"] - previous_close
    ).abs()

    tr3 = (
        df["Low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


def calculate_daily_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["EMA13"] = ema(
        df["Close"],
        13
    )

    df["EMA20"] = ema(
        df["Close"],
        20
    )

    df["EMA50"] = ema(
        df["Close"],
        50
    )

    df["EMA200"] = ema(
        df["Close"],
        200
    )

    df["RSI"] = rsi_wilder(
        df["Close"],
        14
    )

    df["ATR"] = atr(
        df,
        14
    )

    df["AvgVolume20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
    )

    df["TradedValue"] = (
        df["Close"] * df["Volume"]
    )

    df["AvgTradedValue20"] = (
        df["TradedValue"]
        .rolling(20)
        .mean()
    )

    df["Resistance20"] = (
        df["High"]
        .rolling(20)
        .max()
        .shift(1)
    )

    # Candle pressure proxy.
    price_range = (
        df["High"] - df["Low"]
    ).replace(0, np.nan)

    df["BuyPressure"] = (
        (
            df["Close"] - df["Low"]
        ) / price_range
    ).clip(0, 1)

    return df


def calculate_intraday_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["EMA9"] = ema(
        df["Close"],
        9
    )

    df["EMA20"] = ema(
        df["Close"],
        20
    )

    df["EMA50"] = ema(
        df["Close"],
        50
    )

    df["RSI"] = rsi_wilder(
        df["Close"],
        14
    )

    df["ATR"] = atr(
        df,
        14
    )

    # Session VWAP
    typical_price = (
        df["High"]
        + df["Low"]
        + df["Close"]
    ) / 3

    volume = df["Volume"].replace(
        0,
        np.nan
    )

    # Reset VWAP per calendar day.
    date_key = pd.Series(
        df.index.date,
        index=df.index
    )

    cumulative_pv = (
        typical_price * volume
    ).groupby(date_key).cumsum()

    cumulative_volume = (
        volume
        .groupby(date_key)
        .cumsum()
    )

    df["VWAP"] = (
        cumulative_pv
        / cumulative_volume
    )

    # Intraday volume baseline by time-of-day.
    minute_key = (
        pd.Series(
            df.index.strftime("%H:%M"),
            index=df.index
        )
    )

    df["TimeVolumeAverage"] = (
        df["Volume"]
        .groupby(minute_key)
        .transform(
            lambda x: x.shift(1)
            .rolling(20, min_periods=5)
            .mean()
        )
    )

    # Fallback when insufficient same-time history.
    fallback_volume = (
        df["Volume"]
        .shift(1)
        .rolling(
            20,
            min_periods=5
        )
        .mean()
    )

    df["RelativeVolume"] = (
        df["Volume"]
        / df["TimeVolumeAverage"]
    )

    df["RelativeVolume"] = (
        df["RelativeVolume"]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    df["RelativeVolume"] = (
        df["RelativeVolume"]
        .fillna(
            df["Volume"] / fallback_volume
        )
    )

    price_range = (
        df["High"] - df["Low"]
    ).replace(0, np.nan)

    df["BuyPressure"] = (
        (
            df["Close"] - df["Low"]
        ) / price_range
    ).clip(0, 1)

    return df


# ============================================================
# 8. MARKET REGIME
# ============================================================

def download_ihsg_daily() -> Optional[pd.DataFrame]:

    try:

        df = yf.download(
            "^JKSE",
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        df = clean_yfinance_columns(df)

        if df.empty:
            return None

        return calculate_daily_indicators(df)

    except Exception as e:

        logger.warning(
            "IHSG download failed: %s",
            e
        )

        return None


def determine_market_regime(
    ihsg: Optional[pd.DataFrame],
) -> Tuple[str, float]:

    if ihsg is None or len(ihsg) < 50:
        return "UNKNOWN", 0.0

    last = ihsg.iloc[-1]

    close = float(last["Close"])
    ema20 = float(last["EMA20"])
    ema50 = float(last["EMA50"])

    if close > ema20 > ema50:
        return "BULL", 1.0

    if close > ema50:
        return "NEUTRAL", 0.5

    return "BEAR", 0.0


# ============================================================
# 9. RELATIVE STRENGTH
# ============================================================

def calculate_return(
    df: pd.DataFrame,
    periods: int = 20,
) -> float:

    if len(df) <= periods:
        return 0.0

    old = float(
        df["Close"].iloc[-periods - 1]
    )

    current = float(
        df["Close"].iloc[-1]
    )

    if old <= 0:
        return 0.0

    return (
        current / old - 1
    ) * 100


# ============================================================
# 10. SIGNAL ENGINE
# ============================================================

def build_signal(
    ticker: str,
    daily_df: pd.DataFrame,
    ihsg_df: Optional[pd.DataFrame],
    regime: str,
    min_score: int = MIN_SIGNAL_SCORE,
) -> Optional[Signal]:

    if daily_df is None:
        return None

    df = calculate_daily_indicators(
        daily_df
    )

    if len(df) < MIN_DAILY_ROWS:
        return None

    last = df.iloc[-1]

    required_values = [
        last["Close"],
        last["Volume"],
        last["AvgVolume20"],
        last["RSI"],
        last["ATR"],
        last["EMA20"],
        last["EMA50"],
        last["EMA200"],
        last["BuyPressure"],
        last["AvgTradedValue20"],
    ]

    if any(
        pd.isna(x)
        for x in required_values
    ):
        return None

    price = float(last["Close"])
    volume = float(last["Volume"])
    avg_volume = float(last["AvgVolume20"])

    avg_value = float(
        last["AvgTradedValue20"]
    )

    rsi = float(last["RSI"])
    atr_value = float(last["ATR"])

    ema20 = float(last["EMA20"])
    ema50 = float(last["EMA50"])
    ema200 = float(last["EMA200"])

    buy_pressure = float(
        last["BuyPressure"]
    )

    if price < MIN_PRICE:
        return None

    if avg_value < MIN_AVG_VALUE:
        return None

    if avg_volume <= 0:
        return None

    relative_volume = (
        volume / avg_volume
    )

    # --------------------------------------------------------
    # Trend
    # --------------------------------------------------------

    trend_score = 0

    if price > ema20:
        trend_score += 10

    if price > ema50:
        trend_score += 10

    if ema20 > ema50:
        trend_score += 5

    if ema50 > ema200:
        trend_score += 5

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    momentum_score = 0

    if 50 <= rsi <= 70:
        momentum_score += 10

    elif 70 < rsi <= 75:
        momentum_score += 5

    if relative_volume >= 2.5:
        momentum_score += 15

    elif relative_volume >= RELATIVE_VOLUME_THRESHOLD:
        momentum_score += 10

    # --------------------------------------------------------
    # Candle pressure
    # --------------------------------------------------------

    pressure_score = 0

    if buy_pressure >= 0.70:
        pressure_score += 10

    elif buy_pressure >= 0.60:
        pressure_score += 5

    # --------------------------------------------------------
    # Breakout
    # --------------------------------------------------------

    resistance = last["Resistance20"]

    breakout = False
    breakout_score = 0

    if not pd.isna(resistance):

        resistance = float(resistance)

        if price > resistance:
            breakout = True
            breakout_score = 15

    else:
        resistance = price

    # --------------------------------------------------------
    # Relative strength
    # --------------------------------------------------------

    stock_return = calculate_return(
        df,
        20
    )

    ihsg_return = 0.0

    if ihsg_df is not None:

        ihsg_return = calculate_return(
            ihsg_df,
            20
        )

    relative_strength = (
        stock_return - ihsg_return
    )

    rs_score = 0

    if relative_strength >= 10:
        rs_score = 10

    elif relative_strength >= 5:
        rs_score = 7

    elif relative_strength > 0:
        rs_score = 4

    # --------------------------------------------------------
    # Market regime
    # --------------------------------------------------------

    regime_score = 0

    if regime == "BULL":
        regime_score = 10

    elif regime == "NEUTRAL":
        regime_score = 5

    elif regime == "BEAR":
        regime_score = 0

    # --------------------------------------------------------
    # TOTAL SCORE
    # --------------------------------------------------------

    score = (
        trend_score
        + momentum_score
        + pressure_score
        + breakout_score
        + rs_score
        + regime_score
    )

    score = min(
        max(int(score), 0),
        100
    )

    # --------------------------------------------------------
    # Signal threshold
    # --------------------------------------------------------

    if score < min_score:
        return None

    # Avoid chasing extremely overbought candles.
    if rsi > 80:
        return None

    # --------------------------------------------------------
    # Risk engine
    # --------------------------------------------------------

    entry = price

    stop_loss = (
        entry - 1.5 * atr_value
    )

    if stop_loss <= 0:
        return None

    risk = entry - stop_loss

    target_1 = (
        entry + risk * 1.5
    )

    target_2 = (
        entry + risk * 2.5
    )

    risk_reward = (
        (target_2 - entry) / risk
        if risk > 0
        else 0
    )

    if score >= 85:
        rating = "STRONG BUY"

    elif score >= 75:
        rating = "BUY"

    else:
        rating = "WATCH"

    return Signal(
        ticker=ticker,
        price=price,
        score=score,
        rating=rating,

        rsi=round(rsi, 2),
        relative_volume=round(
            relative_volume,
            2
        ),
        buy_pressure=round(
            buy_pressure * 100,
            1
        ),

        atr=round(
            atr_value,
            2
        ),

        vwap=0.0,

        resistance=round(
            resistance,
            2
        ),

        breakout=breakout,

        stock_return_20d=round(
            stock_return,
            2
        ),

        ihsg_return_20d=round(
            ihsg_return,
            2
        ),

        relative_strength=round(
            relative_strength,
            2
        ),

        entry=round(entry, 2),
        stop_loss=round(
            stop_loss,
            2
        ),

        target_1=round(
            target_1,
            2
        ),

        target_2=round(
            target_2,
            2
        ),

        risk_reward=round(
            risk_reward,
            2
        ),

        regime=regime,
    )


# ============================================================
# 11. INTRADAY CONFIRMATION
# ============================================================

def confirm_intraday_signal(
    ticker: str,
) -> Optional[dict]:

    df = download_intraday(
        ticker,
        "15m"
    )

    if df is None:
        return None

    if len(df) < MIN_INTRADAY_ROWS:
        return None

    df = calculate_intraday_indicators(
        df
    )

    last = df.iloc[-1]

    required = [
        "Close",
        "EMA20",
        "VWAP",
        "RSI",
        "RelativeVolume",
        "BuyPressure",
    ]

    if any(
        pd.isna(last[c])
        for c in required
    ):
        return None

    close = float(last["Close"])
    ema20 = float(last["EMA20"])
    vwap = float(last["VWAP"])
    rsi = float(last["RSI"])
    relvol = float(last["RelativeVolume"])
    pressure = float(last["BuyPressure"])

    bullish = (
        close > ema20
        and close > vwap
        and rsi >= 50
        and pressure >= 0.55
        and relvol >= 1.2
    )

    return {
        "confirmed": bullish,
        "price": close,
        "vwap": vwap,
        "relative_volume": relvol,
        "rsi": rsi,
        "buy_pressure": pressure,
    }


# ============================================================
# 12. COOLDOWN
# ============================================================

def signal_allowed(
    ticker: str,
) -> bool:

    now = now_jakarta()

    last = signal_cooldowns.get(
        ticker
    )

    if last is None:
        return True

    elapsed = (
        now - last
    ).total_seconds()

    return (
        elapsed >= SIGNAL_COOLDOWN_SECONDS
    )


def mark_signal_sent(
    ticker: str,
):
    signal_cooldowns[ticker] = (
        now_jakarta()
    )


# ============================================================
# 13. CHART GENERATOR
# ============================================================

def generate_pro_chart(
    df: pd.DataFrame,
    ticker: str,
    period: str = "Daily",
) -> io.BytesIO:

    df = df.copy()

    if period == "Daily":
        df = calculate_daily_indicators(
            df
        )
    else:
        df = calculate_intraday_indicators(
            df
        )

    # Limit chart size for performance.
    max_rows = (
        220
        if period == "Daily"
        else 250
    )

    df = df.tail(max_rows)

    fig = plt.figure(
        figsize=(14, 9),
        facecolor="black"
    )

    gs = gridspec.GridSpec(
        4,
        1,
        height_ratios=[
            3.5,
            1,
            0.8,
            0.8
        ],
        hspace=0.05
    )

    ax_main = plt.subplot(gs[0])
    ax_vol = plt.subplot(
        gs[1],
        sharex=ax_main
    )
    ax_pressure = plt.subplot(
        gs[2],
        sharex=ax_main
    )
    ax_rsi = plt.subplot(
        gs[3],
        sharex=ax_main
    )

    axes = [
        ax_main,
        ax_vol,
        ax_pressure,
        ax_rsi
    ]

    for ax in axes:

        ax.set_facecolor(
            "black"
        )

        ax.tick_params(
            colors="white",
            labelsize=8
        )

        ax.grid(
            True,
            color="#222222",
            linestyle="--",
            linewidth=0.5
        )

        for spine in ax.spines.values():
            spine.set_color(
                "#444444"
            )

    x = np.arange(len(df))

    last = df.iloc[-1]

    previous = (
        df.iloc[-2]
        if len(df) > 1
        else last
    )

    change = (
        (
            last["Close"]
            - previous["Close"]
        )
        / previous["Close"]
    ) * 100

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    ax_main.text(
        0.01,
        1.04,
        (
            f"{ticker} : "
            f"{int(last['Close'])} "
            f"({change:+.2f}%)"
        ),
        transform=ax_main.transAxes,
        color="yellow",
        fontsize=13,
        fontweight="bold"
    )

    ax_main.text(
        0.50,
        1.04,
        "RAFANO TRADER",
        transform=ax_main.transAxes,
        color="white",
        fontsize=13,
        fontweight="bold",
        ha="center"
    )

    if isinstance(
        last.name,
        pd.Timestamp
    ):

        if period == "Daily":

            date_text = (
                last.name
                .strftime(
                    "%d %b %Y"
                )
            )

        else:

            date_text = (
                last.name
                .strftime(
                    "%d %b %Y %H:%M"
                )
            )

    else:

        date_text = str(
            last.name
        )

    ax_main.text(
        0.99,
        1.04,
        (
            f"{period} {date_text}\n"
            f"WIB"
        ),
        transform=ax_main.transAxes,
        color="yellow",
        fontsize=8,
        ha="right"
    )

    # --------------------------------------------------------
    # CANDLESTICKS
    # --------------------------------------------------------

    width = 0.6

    for i in range(len(df)):

        row = df.iloc[i]

        open_price = float(
            row["Open"]
        )

        close_price = float(
            row["Close"]
        )

        high = float(
            row["High"]
        )

        low = float(
            row["Low"]
        )

        color = (
            "#00FF00"
            if close_price >= open_price
            else "#FF0000"
        )

        ax_main.vlines(
            i,
            low,
            high,
            color=color,
            linewidth=1
        )

        ax_main.add_patch(
            Rectangle(
                (
                    i - width / 2,
                    min(
                        open_price,
                        close_price
                    )
                ),
                width,
                abs(
                    close_price
                    - open_price
                ),
                color=color,
            )
        )

    # --------------------------------------------------------
    # MOVING AVERAGES
    # --------------------------------------------------------

    if period == "Daily":

        ax_main.plot(
            x,
            df["EMA13"],
            color="orange",
            linewidth=1.2,
            label="EMA13"
        )

        ax_main.plot(
            x,
            df["EMA20"],
            color="red",
            linewidth=1.2,
            label="EMA20"
        )

        ax_main.plot(
            x,
            df["EMA50"],
            color="white",
            linewidth=1.2,
            label="EMA50"
        )

        ax_main.plot(
            x,
            df["EMA200"],
            color="purple",
            linewidth=1.5,
            label="EMA200"
        )

    else:

        ax_main.plot(
            x,
            df["EMA9"],
            color="orange",
            linewidth=1.0,
            label="EMA9"
        )

        ax_main.plot(
            x,
            df["EMA20"],
            color="red",
            linewidth=1.1,
            label="EMA20"
        )

        ax_main.plot(
            x,
            df["EMA50"],
            color="white",
            linewidth=1.1,
            label="EMA50"
        )

        ax_main.plot(
            x,
            df["VWAP"],
            color="#00FFFF",
            linewidth=1.2,
            label="VWAP"
        )

    ax_main.legend(
        loc="upper left",
        fontsize=7,
        facecolor="black",
        labelcolor="white"
    )

    # --------------------------------------------------------
    # INFO PANEL
    # --------------------------------------------------------

    if period == "Daily":

        info = (
            f"RSI          : "
            f"{last['RSI']:.1f}\n"
            f"ATR          : "
            f"{last['ATR']:.1f}\n"
            f"Rel Volume   : "
            f"{last['Volume'] / last['AvgVolume20']:.1f}x\n"
            f"Buy Pressure : "
            f"{last['BuyPressure'] * 100:.1f}%\n"
            f"Value 20D    : "
            f"Rp{last['AvgTradedValue20']:,.0f}"
        )

    else:

        info = (
            f"RSI          : "
            f"{last['RSI']:.1f}\n"
            f"ATR          : "
            f"{last['ATR']:.1f}\n"
            f"Rel Volume   : "
            f"{last['RelativeVolume']:.1f}x\n"
            f"Buy Pressure : "
            f"{last['BuyPressure'] * 100:.1f}%\n"
            f"VWAP         : "
            f"{last['VWAP']:.1f}"
        )

    ax_main.text(
        0.01,
        0.95,
        info,
        transform=ax_main.transAxes,
        color="white",
        fontsize=7.5,
        family="monospace",
        verticalalignment="top",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="black",
            alpha=0.65,
            edgecolor="none"
        )
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    colors = [
        "#00FF00"
        if df["Close"].iloc[i]
        >= df["Open"].iloc[i]
        else "#FF0000"
        for i in range(len(df))
    ]

    ax_vol.bar(
        x,
        df["Volume"],
        color=colors,
        width=width,
        alpha=0.8
    )

    if period == "Daily":

        ax_vol.plot(
            x,
            df["AvgVolume20"],
            color="white",
            linewidth=1
        )

    ax_vol.text(
        0.01,
        0.85,
        "VOLUME",
        transform=ax_vol.transAxes,
        color="yellow",
        fontsize=8,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # PRESSURE
    # --------------------------------------------------------

    pressure = (
        df["BuyPressure"]
        * 100
    )

    pressure_colors = [
        "#00FFFF"
        if value >= 50
        else "#FF4444"
        for value in pressure
    ]

    ax_pressure.bar(
        x,
        pressure,
        color=pressure_colors,
        width=width
    )

    ax_pressure.axhline(
        50,
        color="#555555",
        linewidth=0.8
    )

    ax_pressure.axhline(
        70,
        color="#00FF00",
        linewidth=0.6,
        linestyle="--"
    )

    ax_pressure.text(
        0.01,
        0.75,
        "CANDLE BUY PRESSURE (%)",
        transform=ax_pressure.transAxes,
        color="white",
        fontsize=7
    )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    ax_rsi.plot(
        x,
        df["RSI"],
        color="#FFD700",
        linewidth=1.2
    )

    ax_rsi.axhline(
        70,
        color="#FF4444",
        linestyle="--",
        linewidth=0.7
    )

    ax_rsi.axhline(
        50,
        color="#555555",
        linestyle="--",
        linewidth=0.7
    )

    ax_rsi.axhline(
        30,
        color="#00FF00",
        linestyle="--",
        linewidth=0.7
    )

    ax_rsi.set_ylim(
        0,
        100
    )

    ax_rsi.text(
        0.01,
        0.75,
        "RSI 14",
        transform=ax_rsi.transAxes,
        color="yellow",
        fontsize=7
    )

    # --------------------------------------------------------
    # X AXIS
    # --------------------------------------------------------

    for ax in [
        ax_main,
        ax_vol,
        ax_pressure
    ]:
        plt.setp(
            ax.get_xticklabels(),
            visible=False
        )

    step = max(
        1,
        len(df) // 7
    )

    positions = x[::step]

    labels = []

    for i in range(
        0,
        len(df),
        step
    ):

        idx = df.index[i]

        if isinstance(
            idx,
            pd.Timestamp
        ):

            if period == "Daily":

                labels.append(
                    idx.strftime(
                        "%d %b"
                    )
                )

            else:

                labels.append(
                    idx.strftime(
                        "%d %H:%M"
                    )
                )

        else:

            labels.append(
                str(idx)
            )

    ax_rsi.set_xticks(
        positions
    )

    ax_rsi.set_xticklabels(
        labels,
        color="white",
        fontsize=7
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    buffer = io.BytesIO()

    plt.savefig(
        buffer,
        format="png",
        bbox_inches="tight",
        facecolor="black",
        dpi=150
    )

    buffer.seek(0)

    plt.close(fig)

    return buffer


# ============================================================
# 14. CHART CACHE
# ============================================================

chart_cache = {}


def get_cached_chart(
    ticker: str,
    period: str,
):

    key = (
        ticker,
        period
    )

    cached = chart_cache.get(
        key
    )

    if cached is None:
        return None

    timestamp, buffer = cached

    age = (
        now_jakarta()
        - timestamp
    ).total_seconds()

    if age > 300:
        return None

    return buffer


def save_chart_cache(
    ticker: str,
    period: str,
    buffer: io.BytesIO,
):

    chart_cache[
        (ticker, period)
    ] = (
        now_jakarta(),
        buffer.getvalue()
    )


# ============================================================
# 15. CHART REQUEST
# ============================================================

async def process_chart_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ticker: str,
    period: str = "Daily",
):

    chat_id = update.effective_chat.id

    ticker = normalize_ticker(
        ticker
    )

    if not is_valid_ticker(
        ticker
    ):

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ Ticker `{ticker}` "
                f"tidak ada dalam universe "
                f"screener."
            ),
            parse_mode="Markdown"
        )

        return

    now = now_jakarta()

    last_request = (
        chart_request_cooldowns.get(
            chat_id
        )
    )

    if last_request is not None:

        elapsed = (
            now - last_request
        ).total_seconds()

        if elapsed < CHART_COOLDOWN_SECONDS:

            remaining = int(
                CHART_COOLDOWN_SECONDS
                - elapsed
            )

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⏳ Tunggu "
                    f"{remaining} detik "
                    "sebelum request chart "
                    "berikutnya."
                )
            )

            return

    chart_request_cooldowns[
        chat_id
    ] = now

    await context.bot.send_chat_action(
        chat_id=chat_id,
        action="upload_photo"
    )

    try:

        cached = get_cached_chart(
            ticker,
            period
        )

        if cached is not None:

            chart_buffer = (
                io.BytesIO(cached)
            )

        else:

            if period == "Daily":

                df = await asyncio.to_thread(
                    lambda: download_daily_batch(
                        [ticker]
                    ).get(ticker)
                )

            else:

                df = await asyncio.to_thread(
                    download_intraday,
                    ticker,
                    "15m"
                )

            if df is None or df.empty:

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ Data chart "
                        f"{ticker} tidak tersedia."
                    )
                )

                return

            chart_buffer = (
                await asyncio.to_thread(
                    generate_pro_chart,
                    df,
                    ticker,
                    period
                )
            )

            save_chart_cache(
                ticker,
                period,
                chart_buffer
            )

            chart_buffer.seek(0)

        caption = (
            f"📊 *RAFANO TRADER*\n"
            f"Ticker: *{ticker}*\n"
            f"Timeframe: *{period}*\n"
            f"Source: Market Data\n"
            f"Timezone: WIB"
        )

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=chart_buffer,
            caption=caption,
            parse_mode="Markdown"
        )

    except Exception as e:

        logger.exception(
            "Chart error %s %s: %s",
            ticker,
            period,
            e
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⚠️ Gagal membuat chart "
                f"{ticker}."
            )
        )



# ============================================================
# 16. HISTORICAL BACKTEST + TRADE JOURNAL
# ============================================================
#
# IMPORTANT:
# - Historical backtest uses DAILY data because Yahoo Finance
#   does not provide multi-year 15m history through yfinance.
# - A daily signal is generated using only data available up
#   to the signal date.
# - Entry is simulated at the NEXT day's OPEN to avoid
#   look-ahead bias.
# - SL/T1/T2 are then evaluated candle-by-candle.
# - If SL and target are both touched in the same candle,
#   the conservative assumption is that SL is hit first.
#
# This backtest is intentionally separate from the live 15M
# confirmation. It measures the underlying daily signal engine.
# ============================================================

BACKTEST_DB_PATH = os.getenv(
    "BACKTEST_DB_PATH",
    "rafano_trade_journal.sqlite3"
)

BACKTEST_DEFAULT_YEARS = 2
BACKTEST_MAX_HOLD_DAYS = 20


@dataclass
class BacktestTrade:
    ticker: str
    signal_date: str
    entry_date: str
    exit_date: str
    score: int
    rating: str
    regime: str
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    exit_price: float
    outcome: str
    r_multiple: float
    holding_days: int
    relative_strength: float
    relative_volume: float
    rsi: float
    breakout: bool


def ensure_backtest_db():
    with sqlite3.connect(BACKTEST_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                score INTEGER NOT NULL,
                rating TEXT NOT NULL,
                regime TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                target_1 REAL NOT NULL,
                target_2 REAL NOT NULL,
                exit_price REAL NOT NULL,
                outcome TEXT NOT NULL,
                r_multiple REAL NOT NULL,
                holding_days INTEGER NOT NULL,
                relative_strength REAL NOT NULL,
                relative_volume REAL NOT NULL,
                rsi REAL NOT NULL,
                breakout INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_backtest_trades(trades: List[BacktestTrade]):
    if not trades:
        return

    ensure_backtest_db()

    with sqlite3.connect(BACKTEST_DB_PATH) as conn:
        conn.executemany("""
            INSERT INTO backtest_trades (
                ticker, signal_date, entry_date, exit_date,
                score, rating, regime,
                entry, stop_loss, target_1, target_2,
                exit_price, outcome, r_multiple,
                holding_days, relative_strength,
                relative_volume, rsi, breakout, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                t.ticker,
                t.signal_date,
                t.entry_date,
                t.exit_date,
                t.score,
                t.rating,
                t.regime,
                t.entry,
                t.stop_loss,
                t.target_1,
                t.target_2,
                t.exit_price,
                t.outcome,
                t.r_multiple,
                t.holding_days,
                t.relative_strength,
                t.relative_volume,
                t.rsi,
                int(t.breakout),
                now_jakarta().isoformat(),
            )
            for t in trades
        ])
        conn.commit()


def _date_to_str(value) -> str:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _prepare_ihsg_for_backtest(
    ihsg_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    if ihsg_df is None or ihsg_df.empty:
        return None

    return calculate_daily_indicators(
        clean_yfinance_columns(ihsg_df)
    )


def _simulate_trade(
    signal: Signal,
    future_df: pd.DataFrame,
    signal_date,
    max_hold_days: int = BACKTEST_MAX_HOLD_DAYS,
) -> Optional[BacktestTrade]:

    if future_df is None or future_df.empty:
        return None

    # Signal is assumed known after signal_date's close.
    # Therefore the earliest possible entry is next day's OPEN.
    entry_row = future_df.iloc[0]

    entry_price = float(entry_row["Open"])

    if not np.isfinite(entry_price) or entry_price <= 0:
        return None

    # Rebase risk levels around actual next-open execution price.
    risk = entry_price - signal.stop_loss
    if risk <= 0:
        return None

    stop_loss = entry_price - risk
    target_1 = entry_price + risk * 1.5
    target_2 = entry_price + risk * 2.5

    window = future_df.iloc[:max_hold_days]

    outcome = "TIMEOUT"
    exit_price = float(window.iloc[-1]["Close"])
    exit_date = window.index[-1]

    for idx, row in window.iterrows():
        high = float(row["High"])
        low = float(row["Low"])

        # Conservative rule when both levels are touched
        # in the same candle.
        if low <= stop_loss and high >= target_1:
            outcome = "SL"
            exit_price = stop_loss
            exit_date = idx
            break

        if low <= stop_loss:
            outcome = "SL"
            exit_price = stop_loss
            exit_date = idx
            break

        if high >= target_2:
            outcome = "T2"
            exit_price = target_2
            exit_date = idx
            break

        if high >= target_1:
            outcome = "T1"
            exit_price = target_1
            exit_date = idx
            break

    r_multiple = (
        (exit_price - entry_price) / risk
        if risk > 0
        else 0.0
    )

    holding_days = max(
        1,
        int(
            (
                pd.Timestamp(exit_date)
                - pd.Timestamp(future_df.index[0])
            ).days
        ) + 1
    )

    return BacktestTrade(
        ticker=signal.ticker,
        signal_date=_date_to_str(signal_date),
        entry_date=_date_to_str(future_df.index[0]),
        exit_date=_date_to_str(exit_date),
        score=signal.score,
        rating=signal.rating,
        regime=signal.regime,
        entry=round(entry_price, 2),
        stop_loss=round(stop_loss, 2),
        target_1=round(target_1, 2),
        target_2=round(target_2, 2),
        exit_price=round(exit_price, 2),
        outcome=outcome,
        r_multiple=round(r_multiple, 4),
        holding_days=holding_days,
        relative_strength=signal.relative_strength,
        relative_volume=signal.relative_volume,
        rsi=signal.rsi,
        breakout=signal.breakout,
    )


def run_historical_backtest(
    years: int = BACKTEST_DEFAULT_YEARS,
    min_score: int = MIN_SIGNAL_SCORE,
    tickers: Optional[List[str]] = None,
    max_hold_days: int = BACKTEST_MAX_HOLD_DAYS,
    save_journal: bool = True,
) -> Tuple[List[BacktestTrade], dict]:

    universe = tickers or TICKERS

    logger.info(
        "BACKTEST start | years=%s | min_score=%s | tickers=%d",
        years,
        min_score,
        len(universe),
    )

    daily_data = download_daily_batch(universe)

    if not daily_data:
        return [], {
            "error": "Tidak ada daily data yang tersedia."
        }

    ihsg = download_ihsg_daily()

    if ihsg is None:
        logger.warning(
            "IHSG data unavailable; relative strength will use 0."
        )

    ihsg = _prepare_ihsg_for_backtest(ihsg)

    trades: List[BacktestTrade] = []

    for ticker, raw_df in daily_data.items():

        try:
            df = clean_yfinance_columns(raw_df)

            if len(df) < MIN_DAILY_ROWS + 2:
                continue

            # Precompute indicators once, but slice them point-in-time
            # for every historical signal date.
            df_ind = calculate_daily_indicators(df)

            for i in range(MIN_DAILY_ROWS, len(df_ind) - 1):

                history = df_ind.iloc[:i + 1].copy()

                # Only data through the signal candle is visible.
                ihsg_history = None
                if ihsg is not None:
                    ihsg_history = ihsg.loc[
                        ihsg.index <= history.index[-1]
                    ].copy()

                regime, _ = determine_market_regime(
                    ihsg_history
                )

                signal = build_signal(
                    ticker,
                    history,
                    ihsg_history,
                    regime,
                    min_score=min_score,
                )

                if signal is None:
                    continue

                # Avoid overlapping positions on the same ticker.
                if trades:
                    last_same = next(
                        (
                            t for t in reversed(trades)
                            if t.ticker == ticker
                        ),
                        None,
                    )
                    if last_same is not None:
                        if pd.Timestamp(
                            last_same.exit_date
                        ) >= pd.Timestamp(
                            history.index[-1]
                        ):
                            continue

                future = df.iloc[i + 1:].copy()

                trade = _simulate_trade(
                    signal,
                    future,
                    history.index[-1],
                    max_hold_days=max_hold_days,
                )

                if trade is not None:
                    trades.append(trade)

        except Exception as e:
            logger.exception(
                "Backtest error %s: %s",
                ticker,
                e,
            )

    stats = calculate_backtest_statistics(
        trades
    )

    if save_journal:
        save_backtest_trades(
            trades
        )

    logger.info(
        "BACKTEST complete | trades=%d | winrate=%.2f%% | expectancy=%.4fR",
        stats.get("trades", 0),
        stats.get("win_rate", 0.0),
        stats.get("expectancy_r", 0.0),
    )

    return trades, stats


def calculate_backtest_statistics(
    trades: List[BacktestTrade],
) -> dict:

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "timeouts": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "t1_rate": 0.0,
            "t2_rate": 0.0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "max_drawdown_r": 0.0,
            "avg_holding_days": 0.0,
        }

    df = pd.DataFrame([
        {
            "outcome": t.outcome,
            "r": t.r_multiple,
            "holding": t.holding_days,
        }
        for t in trades
    ])

    wins = int(
        df["outcome"].isin(["T1", "T2"]).sum()
    )
    losses = int(
        (df["outcome"] == "SL").sum()
    )
    timeouts = int(
        (df["outcome"] == "TIMEOUT").sum()
    )

    total = len(df)

    win_rate = wins / total * 100
    loss_rate = losses / total * 100

    gross_profit = float(
        df.loc[df["r"] > 0, "r"].sum()
    )

    gross_loss = abs(float(
        df.loc[df["r"] < 0, "r"].sum()
    ))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    avg_win_r = float(
        df.loc[df["r"] > 0, "r"].mean()
    ) if (df["r"] > 0).any() else 0.0

    avg_loss_r = float(
        df.loc[df["r"] < 0, "r"].mean()
    ) if (df["r"] < 0).any() else 0.0

    expectancy = float(
        df["r"].mean()
    )

    equity = df["r"].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak

    max_drawdown = float(
        drawdown.min()
    ) if not drawdown.empty else 0.0

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "t1_rate": float(
            (df["outcome"] == "T1").mean() * 100
        ),
        "t2_rate": float(
            (df["outcome"] == "T2").mean() * 100
        ),
        "expectancy_r": expectancy,
        "profit_factor": profit_factor,
        "avg_win_r": avg_win_r,
        "avg_loss_r": avg_loss_r,
        "max_drawdown_r": max_drawdown,
        "avg_holding_days": float(
            df["holding"].mean()
        ),
    }


def analyze_score_buckets(
    trades: List[BacktestTrade],
) -> List[dict]:

    if not trades:
        return []

    buckets = [
        ("60-64", 60, 64),
        ("65-69", 65, 69),
        ("70-74", 70, 74),
        ("75-79", 75, 79),
        ("80-84", 80, 84),
        ("85-89", 85, 89),
        ("90-100", 90, 100),
    ]

    rows = []

    for label, low, high in buckets:
        subset = [
            t for t in trades
            if low <= t.score <= high
        ]

        if not subset:
            continue

        stats = calculate_backtest_statistics(
            subset
        )

        rows.append({
            "bucket": label,
            "trades": stats["trades"],
            "win_rate": stats["win_rate"],
            "expectancy_r": stats["expectancy_r"],
            "profit_factor": stats["profit_factor"],
        })

    return rows


def analyze_regime(
    trades: List[BacktestTrade],
) -> List[dict]:

    rows = []

    for regime in ["BULL", "NEUTRAL", "BEAR", "UNKNOWN"]:
        subset = [
            t for t in trades
            if t.regime == regime
        ]

        if not subset:
            continue

        stats = calculate_backtest_statistics(
            subset
        )

        rows.append({
            "regime": regime,
            "trades": stats["trades"],
            "win_rate": stats["win_rate"],
            "expectancy_r": stats["expectancy_r"],
            "profit_factor": stats["profit_factor"],
        })

    return rows


def optimize_score_thresholds(
    years: int = BACKTEST_DEFAULT_YEARS,
    thresholds: Optional[List[int]] = None,
) -> List[dict]:

    thresholds = thresholds or [
        60, 65, 70, 75, 80, 85, 90
    ]

    results = []

    for threshold in thresholds:
        trades, stats = run_historical_backtest(
            years=years,
            min_score=threshold,
            save_journal=False,
        )

        results.append({
            "threshold": threshold,
            "trades": stats.get("trades", 0),
            "win_rate": stats.get("win_rate", 0.0),
            "expectancy_r": stats.get("expectancy_r", 0.0),
            "profit_factor": stats.get("profit_factor", 0.0),
            "max_drawdown_r": stats.get("max_drawdown_r", 0.0),
        })

    return results


def format_backtest_report(
    trades: List[BacktestTrade],
    stats: dict,
    years: int,
) -> str:

    pf = stats.get("profit_factor", 0.0)

    if math.isinf(pf):
        pf_text = "∞"
    else:
        pf_text = f"{pf:.2f}"

    lines = [
        "📊 RAFANO HISTORICAL BACKTEST",
        "",
        f"Period: sekitar {years} tahun",
        f"Trades: {stats['trades']}",
        f"Win Rate: {stats['win_rate']:.2f}%",
        f"Loss Rate: {stats['loss_rate']:.2f}%",
        f"T1 Hit: {stats['t1_rate']:.2f}%",
        f"T2 Hit: {stats['t2_rate']:.2f}%",
        f"Timeout: {stats['timeouts']}",
        "",
        f"Expectancy: {stats['expectancy_r']:+.3f}R",
        f"Profit Factor: {pf_text}",
        f"Average Win: {stats['avg_win_r']:+.3f}R",
        f"Average Loss: {stats['avg_loss_r']:+.3f}R",
        f"Max Drawdown: {stats['max_drawdown_r']:+.3f}R",
        f"Avg Holding: {stats['avg_holding_days']:.1f} hari",
        "",
        "⚠️ Backtest daily ini mengukur signal engine daily.",
        "Konfirmasi 15M live tidak disimulasikan untuk history multi-tahun.",
        "Hasil historis bukan jaminan profit masa depan.",
    ]

    return "\n".join(lines)


def format_score_analysis(
    trades: List[BacktestTrade],
) -> str:

    rows = analyze_score_buckets(
        trades
    )

    if not rows:
        return "Tidak ada trade untuk analisis score."

    lines = [
        "📈 ANALISIS SCORE HISTORIS",
        "",
        "Score | Trades | Win% | Avg R",
        "-----------------------------",
    ]

    for row in rows:
        lines.append(
            f"{row['bucket']:>7} | "
            f"{row['trades']:>6} | "
            f"{row['win_rate']:>5.1f}% | "
            f"{row['expectancy_r']:+.3f}R"
        )

    return "\n".join(lines)


def format_regime_analysis(
    trades: List[BacktestTrade],
) -> str:

    rows = analyze_regime(
        trades
    )

    if not rows:
        return "Tidak ada data regime."

    lines = [
        "🌐 ANALISIS MARKET REGIME",
        "",
        "Regime   | Trades | Win% | Avg R",
        "-------------------------------",
    ]

    for row in rows:
        lines.append(
            f"{row['regime']:<8} | "
            f"{row['trades']:>6} | "
            f"{row['win_rate']:>5.1f}% | "
            f"{row['expectancy_r']:+.3f}R"
        )

    return "\n".join(lines)


async def backtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat is None:
        return

    years = BACKTEST_DEFAULT_YEARS

    if context.args:
        try:
            years = max(
                1,
                min(
                    int(context.args[0]),
                    2,
                )
            )
        except ValueError:
            await update.message.reply_text(
                "Format: /backtest atau /backtest 2"
            )
            return

    await update.message.reply_text(
        "⏳ Menjalankan historical backtest.\n"
        "Karena data daily dan universe cukup besar, "
        "proses dapat memerlukan waktu."
    )

    try:
        trades, stats = await asyncio.to_thread(
            run_historical_backtest,
            years,
            MIN_SIGNAL_SCORE,
            TICKERS,
            BACKTEST_MAX_HOLD_DAYS,
            True,
        )

        report = format_backtest_report(
            trades,
            stats,
            years,
        )

        await update.message.reply_text(
            report
        )

        await update.message.reply_text(
            format_score_analysis(
                trades
            )
        )

        await update.message.reply_text(
            format_regime_analysis(
                trades
            )
        )

    except Exception as e:
        logger.exception(
            "Backtest command failed: %s",
            e,
        )

        await update.message.reply_text(
            f"⚠️ Backtest gagal: {e}"
        )


async def optimize_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat is None:
        return

    years = BACKTEST_DEFAULT_YEARS

    if context.args:
        try:
            years = max(
                1,
                min(
                    int(context.args[0]),
                    2,
                )
            )
        except ValueError:
            await update.message.reply_text(
                "Format: /optimize atau /optimize 2"
            )
            return

    await update.message.reply_text(
        "⏳ Menguji beberapa threshold score.\n"
        "Ini lebih lambat karena strategi dijalankan "
        "berulang kali."
    )

    try:
        results = await asyncio.to_thread(
            optimize_score_thresholds,
            years,
            [60, 65, 70, 75, 80, 85, 90],
        )

        lines = [
            "🧪 RAFANO SCORE OPTIMIZATION",
            "",
            "Threshold | Trades | Win% | Avg R | PF",
            "---------------------------------------",
        ]

        for row in results:
            pf = row["profit_factor"]
            pf_text = (
                "∞"
                if math.isinf(pf)
                else f"{pf:.2f}"
            )

            lines.append(
                f"{row['threshold']:>9} | "
                f"{row['trades']:>6} | "
                f"{row['win_rate']:>5.1f}% | "
                f"{row['expectancy_r']:+.3f} | "
                f"{pf_text}"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as e:
        logger.exception(
            "Optimization failed: %s",
            e,
        )

        await update.message.reply_text(
            f"⚠️ Optimasi gagal: {e}"
        )


# ============================================================
# 17. TELEGRAM HANDLERS
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🤖 RAFANO TRADER Bot Active!\n\n"
        "Fitur:\n"
        "• Volume Momentum Screener\n"
        "• Multi-timeframe confirmation\n"
        "• Relative Volume\n"
        "• EMA / RSI / ATR\n"
        "• VWAP\n"
        "• Breakout detection\n"
        "• IHSG Market Regime\n"
        "• Relative Strength\n"
        "• Risk Management\n\n"
        "Gunakan:\n"
        "/chart BBCA\n"
        "/chart TLKM\n"
        "/backtest\n"
        "/backtest 2\n"
        "/optimize"
    )


async def chart_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "Format:\n"
            "/chart BBCA"
        )

        return

    ticker = normalize_ticker(
        context.args[0]
    )

    await process_chart_request(
        update,
        context,
        ticker,
        "Daily"
    )


async def button_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    parts = query.data.split(
        "_"
    )

    if len(parts) < 2:
        return

    action = parts[0]

    ticker = normalize_ticker(
        parts[1]
    )

    period = (
        parts[2]
        if len(parts) >= 3
        else "Daily"
    )

    if action != "chart":
        return

    if period not in [
        "Daily",
        "15m"
    ]:
        return

    await process_chart_request(
        update,
        context,
        ticker,
        period
    )


# ============================================================
# 18. TELEGRAM SIGNAL MESSAGE
# ============================================================

def format_signal_message(
    signal: Signal,
) -> str:

    breakout_text = (
        "YES"
        if signal.breakout
        else "NO"
    )

    return (
        "🚨 *RAFANO TRADER SIGNAL*\n\n"

        f"📌 Saham: *{signal.ticker}*\n"
        f"💰 Harga: *Rp{signal.price:,.0f}*\n"
        f"⭐ Score: *{signal.score}/100*\n"
        f"🎯 Rating: *{signal.rating}*\n\n"

        f"📊 RSI: `{signal.rsi}`\n"
        f"📈 Relative Volume: "
        f"`{signal.relative_volume}x`\n"
        f"🟢 Buy Pressure: "
        f"`{signal.buy_pressure}%`\n"

        f"🚀 Breakout: `{breakout_text}`\n"
        f"📐 Resistance: "
        f"`Rp{signal.resistance:,.0f}`\n"

        f"💪 Relative Strength: "
        f"`{signal.relative_strength:+.2f}%`\n"

        f"🌐 Market Regime: "
        f"`{signal.regime}`\n\n"

        "💼 *Risk Plan*\n"
        f"Entry: `Rp{signal.entry:,.0f}`\n"
        f"Stop Loss: `Rp{signal.stop_loss:,.0f}`\n"
        f"Target 1: `Rp{signal.target_1:,.0f}`\n"
        f"Target 2: `Rp{signal.target_2:,.0f}`\n"
        f"Risk/Reward: "
        f"`1:{signal.risk_reward:.1f}`\n\n"

        "⚠️ Score adalah skor sistem, "
        "bukan probabilitas profit."
    )


def build_signal_keyboard(
    ticker: str,
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Daily",
                    callback_data=(
                        f"chart_{ticker}_Daily"
                    )
                ),

                InlineKeyboardButton(
                    "⏱ 15M",
                    callback_data=(
                        f"chart_{ticker}_15m"
                    )
                )
            ]
        ]
    )


# ============================================================
# 19. SCREENER
# ============================================================

async def run_screener_once(
    app: Application,
):

    started = time_module.monotonic()

    logger.info(
        "Starting RAFANO TRADER scan..."
    )

    # --------------------------------------------------------
    # Market data
    # --------------------------------------------------------

    daily_data = await asyncio.to_thread(
        download_daily_batch,
        TICKERS
    )

    if not daily_data:

        logger.error(
            "No daily data available."
        )

        return

    # --------------------------------------------------------
    # IHSG
    # --------------------------------------------------------

    ihsg_df = await asyncio.to_thread(
        download_ihsg_daily
    )

    regime, _ = determine_market_regime(
        ihsg_df
    )

    logger.info(
        "Market regime: %s",
        regime
    )

    # --------------------------------------------------------
    # Signal generation
    # --------------------------------------------------------

    candidates = []

    for ticker, df in daily_data.items():

        try:

            signal = build_signal(
                ticker,
                df,
                ihsg_df,
                regime
            )

            if signal is not None:
                candidates.append(
                    signal
                )

        except Exception as e:

            logger.exception(
                "Signal calculation error "
                "%s: %s",
                ticker,
                e
            )

    # Highest score first.
    candidates.sort(
        key=lambda x: x.score,
        reverse=True
    )

    # Limit signals per scan.
    candidates = candidates[
        :MAX_SIGNALS_PER_SCAN
    ]

    logger.info(
        "Candidates detected: %d",
        len(candidates)
    )

    sent = 0

    # --------------------------------------------------------
    # Intraday confirmation
    # --------------------------------------------------------

    for signal in candidates:

        if not signal_allowed(
            signal.ticker
        ):
            continue

        try:

            confirmation = (
                await asyncio.to_thread(
                    confirm_intraday_signal,
                    signal.ticker
                )
            )

            if confirmation is None:
                continue

            if not confirmation[
                "confirmed"
            ]:
                continue

            # Update VWAP from 15M confirmation.
            signal.vwap = round(
                confirmation["vwap"],
                2
            )

            # Send Telegram.
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=format_signal_message(
                    signal
                ),
                parse_mode="Markdown",
                reply_markup=(
                    build_signal_keyboard(
                        signal.ticker
                    )
                )
            )

            # Only mark cooldown after
            # Telegram successfully sends.
            mark_signal_sent(
                signal.ticker
            )

            sent += 1

        except Exception as e:

            logger.exception(
                "Failed sending signal %s: %s",
                signal.ticker,
                e
            )

    elapsed = (
        time_module.monotonic()
        - started
    )

    logger.info(
        "Scan complete | "
        "Universe=%d | "
        "Data=%d | "
        "Candidates=%d | "
        "Sent=%d | "
        "Regime=%s | "
        "Elapsed=%.2fs",
        len(TICKERS),
        len(daily_data),
        len(candidates),
        sent,
        regime,
        elapsed
    )


# ============================================================
# 20. SCREENER LOOP
# ============================================================

async def market_screener_job(
    app: Application,
):

    logger.info(
        "Market screener task started."
    )

    while True:

        try:

            if is_market_open():

                await run_screener_once(
                    app
                )

            else:

                logger.info(
                    "Market closed. "
                    "Session=%s",
                    current_session()
                )

        except asyncio.CancelledError:

            logger.info(
                "Screener task cancelled."
            )

            raise

        except Exception as e:

            logger.exception(
                "Screener loop error: %s",
                e
            )

        await asyncio.sleep(
            SCAN_INTERVAL_SECONDS
        )


# ============================================================
# 21. APPLICATION LIFECYCLE
# ============================================================

async def post_init(
    application: Application,
):

    logger.info(
        "Starting RAFANO TRADER..."
    )

    application.bot_data[
        "screener_task"
    ] = application.create_task(
        market_screener_job(
            application
        )
    )


async def post_shutdown(
    application: Application,
):

    task = application.bot_data.get(
        "screener_task"
    )

    if task is not None:

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass

    logger.info(
        "RAFANO TRADER shutdown complete."
    )


# ============================================================
# 22. MAIN
# ============================================================

def main():

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Telegram bot token belum dikonfigurasi."
        )

    if not TARGET_CHAT_ID:
        raise RuntimeError(
            "TARGET_CHAT_ID belum dikonfigurasi."
        )

    application = (
        ApplicationBuilder()
        .token(
            TELEGRAM_BOT_TOKEN
        )
        .post_init(
            post_init
        )
        .post_shutdown(
            post_shutdown
        )
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "chart",
            chart_command
        )
    )

    application.add_handler(
        CommandHandler(
            "backtest",
            backtest_command
        )
    )

    application.add_handler(
        CommandHandler(
            "optimize",
            optimize_command
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_callback_handler
        )
    )

    logger.info(
        "RAFANO TRADER BOT READY."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
