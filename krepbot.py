# ========================================
# KRUSTY KRAB TRADING BOT - ULTIMATE EDITION v11.0
# XAU/USD (EXNESS) | BTC | ETH | FOREX MAJOR
# TIMEFRAME: 5M, 15M, 1H, 4H
# DENGAN SUPPORT/RESISTANCE, AUTO CLOSE, NOTIFIKASI
# ========================================

import os
import yfinance as yf
import pandas as pd
import ta
import requests
import time
import sqlite3
import json
import schedule
import threading
from datetime import datetime, timedelta
import logging

# ========================================
# KONFIGURASI
# ========================================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "8907169595:AAHCwqL7Rc5y5iy2TmOF4--rgbpHVyvjnVE"

CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
if not CHAT_ID:
    CHAT_ID = "743527023"

BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("="*60)
print("🏦 KRUSTY KRAB TRADING BOT - ULTIMATE EDITION v11.0")
print("📊 XAU/USD (EXNESS) | BTC | ETH | FOREX MAJOR")
print("📊 TIMEFRAME: 5M | 15M | 1H | 4H")
print("📊 NOTIFIKASI OTOMATIS | SUPPORT/RESISTANCE")
print(f"🤖 Bot: @krepXau_bot")
print("="*60)

# ========================================
# DATABASE
# ========================================
def init_db():
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            sl_price REAL NOT NULL,
            tp1_price REAL NOT NULL,
            tp2_price REAL NOT NULL,
            tp3_price REAL NOT NULL,
            result TEXT,
            profit REAL,
            timeframe TEXT DEFAULT '1h',
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL UNIQUE,
            total_signals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_profit REAL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

init_db()

# ========================================
# FUNGSI DATABASE
# ========================================
def save_signal(asset, signal_type, entry, sl, tp1, tp2, tp3, timeframe="1h"):
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO signals (asset, signal_type, entry_price, sl_price, tp1_price, tp2_price, tp3_price, timeframe)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (asset, signal_type, entry, sl, tp1, tp2, tp3, timeframe))
    c.execute('''
        INSERT INTO performance (asset, total_signals) 
        VALUES (?, 1)
        ON CONFLICT(asset) DO UPDATE SET total_signals = total_signals + 1
    ''', (asset,))
    conn.commit()
    conn.close()

def close_expired_signals():
    """Tutup sinyal yang sudah kadaluarsa (>24 jam)"""
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, asset, entry_price, signal_type, sl_price, tp1_price, created_at 
        FROM signals 
        WHERE status = 'ACTIVE'
    ''')
    active = c.fetchall()
    
    for signal in active:
        signal_id, asset, entry, signal_type, sl, tp1, created_at = signal
        created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        
        if datetime.now() - created_time > timedelta(hours=24):
            c.execute('''
                UPDATE signals 
                SET status = 'EXPIRED', result = 'EXPIRED', closed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (signal_id,))
    
    conn.commit()
    conn.close()

def get_performance():
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('SELECT SUM(total_signals), SUM(wins), SUM(losses), SUM(total_profit) FROM performance')
    total = c.fetchone()
    c.execute('SELECT asset, total_signals, wins, losses, total_profit FROM performance')
    per_asset = c.fetchall()
    conn.close()
    return total, per_asset

# ========================================
# FUNGSI KIRIM PESAN
# ========================================
def send_message(text, keyboard=None):
    url = f"{BOT_URL}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            logger.info("✅ Pesan terkirim!")
            return response.json()
        else:
            logger.error(f"❌ Gagal: {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return None

def edit_message(message_id, text, keyboard=None):
    url = f"{BOT_URL}/editMessageText"
    payload = {'chat_id': CHAT_ID, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        logger.error(f"❌ Edit error: {e}")
        return None

def answer_callback(callback_id, text=""):
    url = f"{BOT_URL}/answerCallbackQuery"
    payload = {'callback_query_id': callback_id, 'text': text}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ========================================
# FUNGSI SUPPORT & RESISTANCE
# ========================================
def calculate_support_resistance(df):
    try:
        high = df['High'].tail(20).max()
        low = df['Low'].tail(20).min()
        close = df['Close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    except:
        return None

def get_sr_text(sr):
    if not sr:
        return ""
    return f"""
📊 <b>SUPPORT & RESISTANCE:</b>
🔺 R3: ${sr['r3']:,.2f}
🔺 R2: ${sr['r2']:,.2f}
🔺 R1: ${sr['r1']:,.2f}
📍 PIVOT: ${sr['pivot']:,.2f}
🔻 S1: ${sr['s1']:,.2f}
🔻 S2: ${sr['s2']:,.2f}
🔻 S3: ${sr['s3']:,.2f}
"""

# ========================================
# FUNGSI FUNDAMENTAL
# ========================================
def get_fundamental_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        fundamental = {
            'pe_ratio': info.get('trailingPE', 'N/A'),
            'eps': info.get('trailingEps', 'N/A'),
            'profit_margin': info.get('profitMargins', 'N/A'),
            'revenue_growth': info.get('revenueGrowth', 'N/A'),
            'debt_to_equity': info.get('debtToEquity', 'N/A'),
            'return_on_equity': info.get('returnOnEquity', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
        }
        return fundamental
    except:
        return None

def analyze_fundamental(ticker, name, price):
    try:
        fund = get_fundamental_data(ticker)
        if not fund:
            return None
        
        alasan = []
        skor = 0
        
        if fund['pe_ratio'] != 'N/A':
            pe = fund['pe_ratio']
            if pe < 15:
                skor += 15
                alasan.append(f"✅ PE Ratio {pe:.2f} (Under-valued)")
            elif pe > 25:
                skor -= 15
                alasan.append(f"⚠️ PE Ratio {pe:.2f} (Over-valued)")
            else:
                alasan.append(f"📊 PE Ratio {pe:.2f} (Fair value)")
        
        if fund['eps'] != 'N/A' and fund['eps'] > 0:
            skor += 10
            alasan.append(f"✅ EPS Positive (${fund['eps']:.2f})")
        elif fund['eps'] != 'N/A':
            skor -= 10
            alasan.append(f"⚠️ EPS Negative (${fund['eps']:.2f})")
        
        if fund['profit_margin'] != 'N/A':
            pm = fund['profit_margin']
            if pm > 0.1:
                skor += 10
                alasan.append(f"✅ Profit Margin: {pm*100:.1f}%")
            elif pm > 0.05:
                skor += 5
                alasan.append(f"📊 Profit Margin: {pm*100:.1f}%")
            else:
                skor -= 5
                alasan.append(f"⚠️ Profit Margin: {pm*100:.1f}%")
        
        if fund['revenue_growth'] != 'N/A':
            rg = fund['revenue_growth']
            if rg > 0.1:
                skor += 15
                alasan.append(f"✅ Revenue Growth: {rg*100:.1f}%")
            elif rg > 0.05:
                skor += 8
                alasan.append(f"📊 Revenue Growth: {rg*100:.1f}%")
            elif rg < 0:
                skor -= 10
                alasan.append(f"⚠️ Revenue Growth: {rg*100:.1f}%")
        
        if fund['debt_to_equity'] != 'N/A':
            de = fund['debt_to_equity']
            if de < 50:
                skor += 10
                alasan.append(f"✅ Debt/Equity: {de:.1f}%")
            elif de < 100:
                alasan.append(f"📊 Debt/Equity: {de:.1f}%")
            else:
                skor -= 10
                alasan.append(f"⚠️ Debt/Equity: {de:.1f}%")
        
        if fund['return_on_equity'] != 'N/A':
            roe = fund['return_on_equity']
            if roe > 0.15:
                skor += 10
                alasan.append(f"✅ ROE: {roe*100:.1f}%")
            elif roe > 0.05:
                alasan.append(f"📊 ROE: {roe*100:.1f}%")
            else:
                skor -= 5
                alasan.append(f"⚠️ ROE: {roe*100:.1f}%")
        
        sector_text = f"📊 Sektor: {fund['sector']} | {fund['industry']}"
        
        if skor >= 25:
            signal = "🔥 FUNDAMENTAL BULLISH"
        elif skor >= 10:
            signal = "📈 FUNDAMENTAL POSITIF"
        elif skor <= -25:
            signal = "🔻 FUNDAMENTAL BEARISH"
        elif skor <= -10:
            signal = "📉 FUNDAMENTAL NEGATIF"
        else:
            signal = "⏸️ FUNDAMENTAL NEUTRAL"
        
        return {
            'signal': signal,
            'skor': skor,
            'alasan': alasan,
            'sector': sector_text
        }
    except:
        return None

# ========================================
# FUNGSI ANALISIS UTAMA
# ========================================
def analyze_asset(ticker, name, timeframe="1h"):
    try:
        tf_map = {
            "5m": {"interval": "5m", "period": "1d"},
            "15m": {"interval": "15m", "period": "5d"},
            "1h": {"interval": "1h", "period": "1mo"},
            "4h": {"interval": "1h", "period": "2mo"},
        }
        
        interval = tf_map.get(timeframe, {"interval": "1h", "period": "1mo"})["interval"]
        period = tf_map.get(timeframe, {"interval": "1h", "period": "1mo"})["period"]
        
        if ticker == "XAUUSD=X":
            ticker = "GC=F"
        
        logger.info(f"📊 Analisis {name} - Timeframe: {timeframe}")
        
        asset = yf.Ticker(ticker)
        df = asset.history(period=period, interval=interval)
        
        if df.empty or len(df) < 20:
            logger.warning(f"⚠️ Data kosong untuk {name}")
            return None

        # ===== INDIKATOR TEKNIKAL =====
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=200)
        df['BB_high'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_hband()
        df['BB_low'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_lband()
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        df['StochRSI'] = ta.momentum.StochRSIIndicator(df['Close'], window=14).stochrsi()
        df['Volume_ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume'], window=14).money_flow_index()
        df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14).adx()

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        high_20 = df['High'].tail(20).max()
        low_20 = df['Low'].tail(20).min()
        fib_382 = high_20 - (high_20 - low_20) * 0.382
        fib_618 = high_20 - (high_20 - low_20) * 0.618

        # ===== SCORING =====
        skor_buy, skor_sell, alasan = 0, 0, []

        if last['RSI'] < 30:
            skor_buy += 20
            alasan.append(f"✅ RSI Oversold ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            skor_sell += 20
            alasan.append(f"⚠️ RSI Overbought ({last['RSI']:.1f})")

        if last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal']:
            skor_buy += 25
            alasan.append("✅ MACD Golden Cross")
        elif last['MACD'] < last['MACD_signal'] and prev['MACD'] >= prev['MACD_signal']:
            skor_sell += 25
            alasan.append("⚠️ MACD Death Cross")

        if last['Close'] > last['SMA50']:
            skor_buy += 20
            alasan.append("✅ Harga > SMA50")
        else:
            skor_sell += 20
            alasan.append("⚠️ Harga < SMA50")

        if last['Close'] < last['BB_low']:
            skor_buy += 15
            alasan.append("✅ Harga di BB Lower")
        elif last['Close'] > last['BB_high']:
            skor_sell += 15
            alasan.append("⚠️ Harga di BB Upper")

        if last['StochRSI'] < 0.2:
            skor_buy += 10
            alasan.append(f"✅ StochRSI Oversold ({last['StochRSI']:.2f})")
        elif last['StochRSI'] > 0.8:
            skor_sell += 10
            alasan.append(f"⚠️ StochRSI Overbought ({last['StochRSI']:.2f})")

        if last['Volume_ratio'] > 1.5:
            if skor_buy > skor_sell:
                skor_buy += 10
                alasan.append("✅ Volume tinggi (konfirmasi)")
            else:
                skor_sell += 10
                alasan.append("⚠️ Volume tinggi (konfirmasi)")

        if last['MFI'] < 20:
            skor_buy += 10
            alasan.append(f"✅ MFI Oversold ({last['MFI']:.1f})")
        elif last['MFI'] > 80:
            skor_sell += 10
            alasan.append(f"⚠️ MFI Overbought ({last['MFI']:.1f})")

        if last['ADX'] > 25:
            if skor_buy > skor_sell:
                skor_buy += 10
                alasan.append(f"✅ ADX Trend Kuat ({last['ADX']:.1f})")
            else:
                skor_sell += 10
                alasan.append(f"⚠️ ADX Trend Kuat ({last['ADX']:.1f})")

        # ===== KEPUTUSAN =====
        total_skor = skor_buy + skor_sell
        if total_skor > 0:
            if skor_buy > skor_sell + 30:
                sinyal, confidence = "🔥 STRONG BUY", 90
            elif skor_buy > skor_sell + 15:
                sinyal, confidence = "📈 BUY", 75
            elif skor_buy > skor_sell:
                sinyal, confidence = "📈 WEAK BUY", 60
            elif skor_sell > skor_buy + 30:
                sinyal, confidence = "🔻 STRONG SELL", 90
            elif skor_sell > skor_buy + 15:
                sinyal, confidence = "📉 SELL", 75
            elif skor_sell > skor_buy:
                sinyal, confidence = "📉 WEAK SELL", 60
            else:
                sinyal, confidence = "⏸️ NEUTRAL", 50
        else:
            sinyal, confidence = "⏸️ NEUTRAL", 50

        # ===== LEVEL =====
        atr, entry = last['ATR'], last['Close']
        if "BUY" in sinyal:
            sl, tp1, tp2 = entry - (atr * 1.5), entry + (atr * 1.5), entry + (atr * 2.5)
            tp3 = entry + (atr * 4.0)
        elif "SELL" in sinyal:
            sl, tp1, tp2 = entry + (atr * 1.5), entry - (atr * 1.5), entry - (atr * 2.5)
            tp3 = entry - (atr * 4.0)
        else:
            sl, tp1, tp2 = entry - atr, entry + atr, entry + (atr * 2)
            tp3 = entry + (atr * 3)

        # ===== SIMPAN SINYAL =====
        if "STRONG" in sinyal or "BUY" in sinyal or "SELL" in sinyal:
            direction = "BUY" if "BUY" in sinyal else "SELL"
            save_signal(name.split()[0], direction, entry, sl, tp1, tp2, tp3, timeframe)

        # ===== SUPPORT & RESISTANCE =====
        sr = calculate_support_resistance(df)
        sr_text = get_sr_text(sr)

        # ===== FUNDAMENTAL =====
        fundamental = analyze_fundamental(ticker, name, entry)
        fundamental_text = ""
        if fundamental and fundamental['alasan']:
            fund_alasan = "\n".join([f"   {a}" for a in fundamental['alasan']])
            fundamental_text = f"""
📊 <b>FUNDAMENTAL ANALYSIS</b>
🎯 {fundamental['signal']} (Skor: {fundamental['skor']})

{fund_alasan}
{fundamental.get('sector', '')}
"""
        else:
            if "BTC" in name or "ETH" in name:
                fundamental_text = "📊 <b>FUNDAMENTAL:</b> Data tidak tersedia untuk crypto"
            elif "USD" in name or "EUR" in name or "GBP" in name:
                fundamental_text = "📊 <b>FUNDAMENTAL:</b> Data tidak tersedia untuk forex"
            else:
                fundamental_text = "📊 <b>FUNDAMENTAL:</b> Data tidak tersedia"

        return {
            'name': name,
            'price': entry,
            'sinyal': sinyal,
            'confidence': confidence,
            'alasan': alasan[:5],
            'entry': entry,
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'rsi': last['RSI'],
            'macd': last['MACD'],
            'sma50': last['SMA50'],
            'sma200': last['SMA200'],
            'bb_high': last['BB_high'],
            'bb_low': last['BB_low'],
            'atr': last['ATR'],
            'volume_ratio': last['Volume_ratio'],
            'mfi': last['MFI'],
            'adx': last['ADX'],
            'fib_382': fib_382,
            'fib_618': fib_618,
            'skor_buy': skor_buy,
            'skor_sell': skor_sell,
            'date': df.index[-1],
            'timeframe': timeframe,
            'fundamental': fundamental_text,
            'sr_text': sr_text
        }
    except Exception as e:
        logger.error(f"Error {name}: {e}")
        return None

# ========================================
# DAFTAR ASET
# ========================================
ASSETS = [
    {"ticker": "XAUUSD=X", "name": "🥇 XAU/USD (Exness)"},
    {"ticker": "BTC-USD", "name": "🪙 BTC/USD"},
    {"ticker": "ETH-USD", "name": "⚡ ETH/USD"},
    {"ticker": "EURUSD=X", "name": "💶 EUR/USD"},
    {"ticker": "GBPUSD=X", "name": "💷 GBP/USD"},
    {"ticker": "USDJPY=X", "name": "💴 USD/JPY"},
    {"ticker": "AUDUSD=X", "name": "🇦🇺 AUD/USD"},
    {"ticker": "USDCAD=X", "name": "🇨🇦 USD/CAD"},
]

selected_timeframe = "1h"

# ========================================
# NOTIFIKASI OTOMATIS
# ========================================
def send_auto_signal():
    """Kirim sinyal otomatis setiap 4 jam"""
    logger.info("📢 Mengirim notifikasi otomatis...")
    
    # Tutup sinyal expired dulu
    close_expired_signals()
    
    # Kirim sinyal untuk aset utama
    main_assets = [
        {"ticker": "XAUUSD=X", "name": "🥇 XAU/USD (Exness)"},
        {"ticker": "BTC-USD", "name": "🪙 BTC/USD"},
        {"ticker": "ETH-USD", "name": "⚡ ETH/USD"},
    ]
    
    msg = f"""
╔═══════════════════════════════════════╗
║   🔔 NOTIFIKASI OTOMATIS              ║
║   ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB  ║
╚═══════════════════════════════════════╝

📊 <b>SINYAL HARIAN</b>
⏰ Timeframe: <b>{selected_timeframe}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    send_message(msg)
    time.sleep(1)
    
    for asset in main_assets:
        result = analyze_asset(asset['ticker'], asset['name'], selected_timeframe)
        if result:
            alasan_text = "\n".join([f"   {a}" for a in result['alasan']])
            msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>
🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%

📌 Alasan:
{alasan_text}

📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
━━━━━━━━━━━━━━━━━━━━━
"""
            send_message(msg)
            time.sleep(1.5)

def start_scheduler():
    """Jalankan scheduler untuk notifikasi otomatis"""
    # Kirim setiap 4 jam
    schedule.every(4).hours.do(send_auto_signal)
    
    # Kirim sinyal pertama saat startup
    time.sleep(5)
    send_auto_signal()
    
    while True:
        schedule.run_pending()
        time.sleep(30)

# ========================================
# HANDLE CALLBACK
# ========================================
def handle_callback(callback_id, message_id, data):
    global selected_timeframe
    answer_callback(callback_id)
    
    tf_map = {
        'tf_5m': '5m',
        'tf_15m': '15m',
        'tf_1h': '1h',
        'tf_4h': '4h',
    }
    
    asset_map = {
        'xau': {'ticker': 'XAUUSD=X', 'name': '🥇 XAU/USD (Exness)'},
        'btc': {'ticker': 'BTC-USD', 'name': '🪙 BTC/USD'},
        'eth': {'ticker': 'ETH-USD', 'name': '⚡ ETH/USD'},
        'eur': {'ticker': 'EURUSD=X', 'name': '💶 EUR/USD'},
        'gbp': {'ticker': 'GBPUSD=X', 'name': '💷 GBP/USD'},
        'usd': {'ticker': 'USDJPY=X', 'name': '💴 USD/JPY'},
        'aud': {'ticker': 'AUDUSD=X', 'name': '🇦🇺 AUD/USD'},
        'usdcad': {'ticker': 'USDCAD=X', 'name': '🇨🇦 USD/CAD'},
        'all': None,
        'menu': None,
        'back': None,
    }
    
    if data == 'menu' or data == 'back':
        send_menu(message_id)
        return
    
    if data == 'timeframe':
        keyboard = [
            [{"text": "🕐 5 Menit", "callback_data": "tf_5m"}, {"text": "🕐 15 Menit", "callback_data": "tf_15m"}],
            [{"text": "🕐 1 Jam", "callback_data": "tf_1h"}, {"text": "🕐 4 Jam", "callback_data": "tf_4h"}],
            [{"text": "🔙 Kembali", "callback_data": "menu"}],
        ]
        edit_message(message_id, f"""
📊 <b>PILIH TIMEFRAME</b>
━━━━━━━━━━━━━━━━━━━━━

⏰ Timeframe saat ini: <b>{selected_timeframe}</b>

• <b>5 Menit</b> - Scalping (Entry cepat)
• <b>15 Menit</b> - Scalping / Intraday
• <b>1 Jam</b> - Swing Trading
• <b>4 Jam</b> - Trend / Swing
""", keyboard)
        return
    
    if data in tf_map:
        selected_timeframe = tf_map[data]
        edit_message(message_id, f"✅ Timeframe berubah ke: <b>{selected_timeframe}</b>")
        send_menu(message_id)
        return
    
    if data == 'all':
        edit_message(message_id, f"📊 Mengirim semua sinyal (Timeframe: {selected_timeframe})...")
        send_all_signals(message_id)
        return
    
    if data == 'performance':
        close_expired_signals()
        total, per_asset = get_performance()
        total_signals, wins, losses, total_profit = total
        winrate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
        
        msg = f"""
📊 <b>PERFORMANCE TRACKER</b>
━━━━━━━━━━━━━━━━━━━━━

📈 Total: {total_signals or 0} sinyal
✅ Win: {wins or 0} | ❌ Loss: {losses or 0}
🏆 Winrate: <b>{winrate}%</b>
💰 Profit: <b>${total_profit or 0:,.2f}</b>

📊 <b>PER ASET:</b>
"""
        for asset, total, win, loss, profit in per_asset:
            asset_winrate = round((win / total) * 100, 1) if total > 0 else 0
            msg += f"\n{asset}: {total} sinyal | {asset_winrate}% | ${profit or 0:,.2f}"
        
        keyboard = [[{"text": "🔙 Kembali", "callback_data": "menu"}]]
        edit_message(message_id, msg, keyboard)
        return
    
    if data in asset_map and data != 'all':
        asset = asset_map[data]
        edit_message(message_id, f"📥 Menganalisis {asset['name']} (Timeframe: {selected_timeframe})...")
        result = analyze_asset(asset['ticker'], asset['name'], selected_timeframe)
        
        if result:
            alasan_text = "\n".join([f"   {a}" for a in result['alasan']])
            msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>
⏰ Timeframe: <b>{result['timeframe']}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%
📊 Skor: {result['skor_buy']}/{result['skor_sell']}

📌 <b>Alasan Teknikal:</b>
{alasan_text}

{result['fundamental']}
{result['sr_text']}

⚡ <b>LEVEL EXNESS:</b>
📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f} ({abs(result['sl']/result['entry']-1)*100:.2f}%)
🎯 TP1: ${result['tp1']:,.2f} (R:R 1:1.5)
🎯 TP2: ${result['tp2']:,.2f} (R:R 1:2.5)
🎯 TP3: ${result['tp3']:,.2f} (R:R 1:4.0)

📊 <b>INDIKATOR:</b>
• RSI: {result['rsi']:.1f}
• MACD: {result['macd']:.4f}
• SMA50: ${result['sma50']:,.2f}
• SMA200: ${result['sma200']:,.2f}
• BB Upper: ${result['bb_high']:,.2f}
• BB Lower: ${result['bb_low']:,.2f}
• ATR: ${result['atr']:.2f}
• Volume: {result['volume_ratio']:.1f}x
• MFI: {result['mfi']:.1f}
• ADX: {result['adx']:.1f}
• Fib 61.8%: ${result['fib_618']:,.2f}
• Fib 38.2%: ${result['fib_382']:,.2f}
━━━━━━━━━━━━━━━━━━━━━
⚠️ Bukan nasihat keuangan
💡 Gunakan untuk referensi
"""
            keyboard = [[{"text": "🔙 Kembali", "callback_data": "menu"}]]
            edit_message(message_id, msg, keyboard)
        else:
            edit_message(message_id, f"❌ Gagal analisis {asset['name']}")

# ========================================
# SEND MENU
# ========================================
def send_menu(message_id=None):
    keyboard = [
        [{"text": "⏰ TIMEFRAME", "callback_data": "timeframe"}],
        [{"text": "🥇 XAU/USD", "callback_data": "xau"}, {"text": "🪙 BTC/USD", "callback_data": "btc"}],
        [{"text": "⚡ ETH/USD", "callback_data": "eth"}, {"text": "💶 EUR/USD", "callback_data": "eur"}],
        [{"text": "💷 GBP/USD", "callback_data": "gbp"}, {"text": "💴 USD/JPY", "callback_data": "usd"}],
        [{"text": "🇦🇺 AUD/USD", "callback_data": "aud"}, {"text": "🇨🇦 USD/CAD", "callback_data": "usdcad"}],
        [{"text": "📊 SEMUA SINYAL", "callback_data": "all"}, {"text": "📈 PERFORMANCE", "callback_data": "performance"}],
    ]
    
    msg = f"""
╔═══════════════════════════════════════╗
║   🏦  KRUSTY KRAB TRADING BOT         ║
║   "Printing Money Since 2026"         ║
║   ULTIMATE EDITION v11.0              ║
╚═══════════════════════════════════════╝

📊 <b>PILIH ASET:</b>
⏰ Timeframe: <b>{selected_timeframe}</b>

🥇 <b>XAU/USD</b> - Exness (Emas)
🪙 <b>BTC/USD</b> - Bitcoin
⚡ <b>ETH/USD</b> - Ethereum

💶 <b>EUR/USD</b> - Euro
💷 <b>GBP/USD</b> - Pound
💴 <b>USD/JPY</b> - Yen
🇦🇺 <b>AUD/USD</b> - Aussie
🇨🇦 <b>USD/CAD</b> - Loonie

📊 <b>Fitur Lengkap:</b>
• 12+ Indikator Teknikal
• AI-Powered Scoring
• 3 Level TP
• Database History
• Performance Tracker
• 4 Timeframe (5M, 15M, 1H, 4H)
• Fundamental Analysis
• Support & Resistance
• Auto Close Signal (24 jam)
• Notifikasi Otomatis (4 jam sekali)
"""
    if message_id:
        edit_message(message_id, msg, keyboard)
    else:
        send_message(msg, keyboard)

# ========================================
# SEND ALL SIGNALS
# ========================================
def send_all_signals(message_id):
    close_expired_signals()
    msg = f"📊 <b>SEMUA SINYAL</b> (Timeframe: {selected_timeframe})\n━━━━━━━━━━━━━━━━━━━━━\n"
    
    for asset in ASSETS:
        result = analyze_asset(asset['ticker'], asset['name'], selected_timeframe)
        if result:
            msg += f"""
{result['name']}
💰 ${result['price']:,.2f}
🎯 {result['sinyal']} ({result['confidence']}%)
📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP: ${result['tp1']:,.2f} | ${result['tp2']:,.2f}
━━━━━━━━━━━━━━━━━━━━━
"""
        time.sleep(0.5)
    
    keyboard = [[{"text": "🔙 Kembali", "callback_data": "menu"}]]
    edit_message(message_id, msg, keyboard)

# ========================================
# GET UPDATES
# ========================================
def get_updates(offset=None):
    url = f"{BOT_URL}/getUpdates"
    params = {'timeout': 30, 'offset': offset}
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except:
        return None

# ========================================
# MAIN
# ========================================
def main():
    logger.info("🤖 KRUSTY KRAB TRADING BOT v11.0 STARTED")
    logger.info("📊 ULTIMATE EDITION - ALL FEATURES")
    logger.info("📌 Kirim /start ke @krepXau_bot")
    
    # Tutup sinyal expired
    close_expired_signals()
    
    # Kirim menu pertama
    send_menu()
    
    # Start scheduler di thread terpisah
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    last_update_id = None
    while True:
        try:
            updates = get_updates(last_update_id)
            if updates and updates.get('ok'):
                for update in updates.get('result', []):
                    last_update_id = update['update_id'] + 1
                    
                    if 'message' in update:
                        chat_id = str(update['message']['chat']['id'])
                        text = update['message'].get('text', '')
                        if chat_id == CHAT_ID and text == '/start':
                            send_menu()
                    
                    elif 'callback_query' in update:
                        callback = update['callback_query']
                        chat_id = str(callback['message']['chat']['id'])
                        if chat_id == CHAT_ID:
                            handle_callback(
                                callback['id'],
                                callback['message']['message_id'],
                                callback['data']
                            )
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
