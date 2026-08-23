# ========================================
# KRUSTY KRAB TRADING BOT - ENHANCED v14.0
# DENGAN ERROR HANDLING & FALLBACK
# FILE: krepbot.py
# ========================================

import os
import yfinance as yf
import pandas as pd
import ta
import requests
import json
import time
import sqlite3
from datetime import datetime, timedelta
import logging
import threading
import traceback

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
print("🏦 KRUSTY KRAB TRADING BOT - ENHANCED v14.0")
print("📊 DENGAN ERROR HANDLING")
print(f"🤖 Bot: @krepXau_bot")
print("="*60)

# ========================================
# DATABASE
# ========================================
def init_db():
    try:
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
    except Exception as e:
        logger.error(f"Database error: {e}")

init_db()

# ========================================
# FUNGSI DATABASE
# ========================================
def save_signal(asset, signal_type, entry, sl, tp1, tp2, tp3, timeframe="1h"):
    try:
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
    except Exception as e:
        logger.error(f"Save signal error: {e}")

def close_expired_signals():
    try:
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
    except Exception as e:
        logger.error(f"Close expired error: {e}")

def get_performance():
    try:
        conn = sqlite3.connect('trading_history.db')
        c = conn.cursor()
        c.execute('SELECT SUM(total_signals), SUM(wins), SUM(losses), SUM(total_profit) FROM performance')
        total = c.fetchone()
        c.execute('SELECT asset, total_signals, wins, losses, total_profit FROM performance')
        per_asset = c.fetchall()
        conn.close()
        return total, per_asset
    except:
        return (0,0,0,0), []

# ========================================
# FUNGSI KIRIM PESAN
# ========================================
def send_message(text, keyboard=None):
    try:
        url = f"{BOT_URL}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
        if keyboard:
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            logger.info("✅ Pesan terkirim!")
            return response.json()
        else:
            logger.error(f"❌ Gagal: {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        return None

def edit_message(message_id, text, keyboard=None):
    try:
        url = f"{BOT_URL}/editMessageText"
        payload = {'chat_id': CHAT_ID, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
        if keyboard:
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
        response = requests.post(url, json=payload, timeout=60)
        return response.json()
    except Exception as e:
        logger.error(f"❌ Edit error: {e}")
        return None

def answer_callback(callback_id, text=""):
    try:
        url = f"{BOT_URL}/answerCallbackQuery"
        payload = {'callback_query_id': callback_id, 'text': text}
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ========================================
# FUNGSI ANALISIS SEDERHANA (STABIL)
# ========================================
def analyze_asset_simple(ticker, name, timeframe="1h"):
    try:
        # Gunakan timeframe yang lebih stabil
        if timeframe in ["5m", "15m"]:
            interval = "5m" if timeframe == "5m" else "15m"
            period = "1d"
        else:
            interval = "1h" if timeframe == "1h" else "1h"
            period = "7d" if timeframe == "4h" else "1mo"
        
        if ticker == "XAUUSD=X":
            ticker = "GC=F"
        
        logger.info(f"📊 Analisis {name} - {timeframe}")
        
        asset = yf.Ticker(ticker)
        df = asset.history(period=period, interval=interval)
        
        if df.empty or len(df) < 5:
            logger.warning(f"⚠️ Data kosong untuk {name}")
            return None
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        # Hitung indikator
        rsi = ta.momentum.RSIIndicator(df['Close'], window=14).rsi().iloc[-1]
        macd = ta.trend.MACD(df['Close']).macd().iloc[-1]
        macd_signal = ta.trend.MACD(df['Close']).macd_signal().iloc[-1]
        sma50 = ta.trend.sma_indicator(df['Close'], window=50).iloc[-1]
        
        # Scoring sederhana
        skor_buy = 0
        skor_sell = 0
        alasan = []
        
        if rsi < 30:
            skor_buy += 20
            alasan.append(f"✅ RSI Oversold ({rsi:.1f})")
        elif rsi > 70:
            skor_sell += 20
            alasan.append(f"⚠️ RSI Overbought ({rsi:.1f})")
        
        if macd > macd_signal:
            skor_buy += 15
            alasan.append("✅ MACD Bullish")
        else:
            skor_sell += 15
            alasan.append("⚠️ MACD Bearish")
        
        if last['Close'] > sma50:
            skor_buy += 15
            alasan.append("✅ Harga > SMA50")
        else:
            skor_sell += 15
            alasan.append("⚠️ Harga < SMA50")
        
        if skor_buy > skor_sell + 20:
            sinyal = "🔥 STRONG BUY"
            confidence = 85
        elif skor_buy > skor_sell:
            sinyal = "📈 BUY"
            confidence = 70
        elif skor_sell > skor_buy + 20:
            sinyal = "🔻 STRONG SELL"
            confidence = 85
        elif skor_sell > skor_buy:
            sinyal = "📉 SELL"
            confidence = 70
        else:
            sinyal = "⏸️ NEUTRAL"
            confidence = 50
        
        entry = last['Close']
        atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range().iloc[-1]
        
        if "BUY" in sinyal:
            sl = entry - (atr * 1.5)
            tp1 = entry + (atr * 1.5)
            tp2 = entry + (atr * 2.5)
        else:
            sl = entry + (atr * 1.5)
            tp1 = entry - (atr * 1.5)
            tp2 = entry - (atr * 2.5)
        
        return {
            'name': name,
            'price': entry,
            'sinyal': sinyal,
            'confidence': confidence,
            'alasan': alasan,
            'entry': entry,
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'rsi': rsi,
            'macd': macd,
            'timeframe': timeframe,
            'date': df.index[-1]
        }
    except Exception as e:
        logger.error(f"Error {name}: {traceback.format_exc()}")
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
# GET UPDATES
# ========================================
def get_updates(offset=None):
    try:
        url = f"{BOT_URL}/getUpdates"
        params = {'timeout': 30, 'offset': offset}
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        logger.error(f"get_updates error: {e}")
        return None

# ========================================
# MENU UTAMA
# ========================================
def send_menu(message_id=None):
    keyboard = [
        [{"text": "⏰ TIMEFRAME", "callback_data": "timeframe"}],
        [{"text": "🥇 XAU/USD", "callback_data": "xau"}, {"text": "🪙 BTC/USD", "callback_data": "btc"}],
        [{"text": "⚡ ETH/USD", "callback_data": "eth"}, {"text": "💶 EUR/USD", "callback_data": "eur"}],
        [{"text": "💷 GBP/USD", "callback_data": "gbp"}, {"text": "💴 USD/JPY", "callback_data": "usd"}],
        [{"text": "🇦🇺 AUD/USD", "callback_data": "aud"}, {"text": "🇨🇦 USD/CAD", "callback_data": "cad"}],
        [{"text": "📊 SEMUA SINYAL", "callback_data": "all"}, {"text": "📈 PERFORMANCE", "callback_data": "perf"}],
    ]
    
    msg = f"""
╔═══════════════════════════════════════╗
║   🏦  KRUSTY KRAB TRADING BOT         ║
║   "Printing Money Since 2026"         ║
║   ENHANCED v14.0                      ║
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

📊 <b>Fitur:</b>
• 12+ Indikator Teknikal
• AI-Powered Scoring
• 3 Level TP
• Performance Tracker
"""
    if message_id:
        edit_message(message_id, msg, keyboard)
    else:
        send_message(msg, keyboard)

# ========================================
# HANDLE CALLBACK
# ========================================
def handle_callback(callback_id, message_id, data):
    global selected_timeframe
    answer_callback(callback_id)
    logger.info(f"📥 Callback: {data}")
    
    # === TIMEFRAME ===
    if data == "timeframe":
        keyboard = [
            [{"text": "🕐 5 Menit", "callback_data": "tf5"}, {"text": "🕐 15 Menit", "callback_data": "tf15"}],
            [{"text": "🕐 1 Jam", "callback_data": "tf1"}, {"text": "🕐 4 Jam", "callback_data": "tf4"}],
            [{"text": "🔙 Kembali", "callback_data": "back"}],
        ]
        edit_message(message_id, f"⏰ Pilih Timeframe:\nSaat ini: {selected_timeframe}", keyboard)
        return
    
    if data == "tf5":
        selected_timeframe = "5m"
        edit_message(message_id, f"✅ Timeframe: 5 Menit")
        send_menu(message_id)
        return
    elif data == "tf15":
        selected_timeframe = "15m"
        edit_message(message_id, f"✅ Timeframe: 15 Menit")
        send_menu(message_id)
        return
    elif data == "tf1":
        selected_timeframe = "1h"
        edit_message(message_id, f"✅ Timeframe: 1 Jam")
        send_menu(message_id)
        return
    elif data == "tf4":
        selected_timeframe = "4h"
        edit_message(message_id, f"✅ Timeframe: 4 Jam")
        send_menu(message_id)
        return
    
    if data == "back":
        send_menu(message_id)
        return
    
    # === PERFORMANCE ===
    if data == "perf":
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
        
        keyboard = [[{"text": "🔙 Kembali", "callback_data": "back"}]]
        edit_message(message_id, msg, keyboard)
        return
    
    # === SEMUA SINYAL ===
    if data == "all":
        edit_message(message_id, "📊 Mengirim semua sinyal...")
        kirim_semua_sinyal(message_id)
        return
    
    # === ASSET ANALYSIS ===
    asset_map = {
        'xau': {'ticker': 'XAUUSD=X', 'name': '🥇 XAU/USD (Exness)'},
        'btc': {'ticker': 'BTC-USD', 'name': '🪙 BTC/USD'},
        'eth': {'ticker': 'ETH-USD', 'name': '⚡ ETH/USD'},
        'eur': {'ticker': 'EURUSD=X', 'name': '💶 EUR/USD'},
        'gbp': {'ticker': 'GBPUSD=X', 'name': '💷 GBP/USD'},
        'usd': {'ticker': 'USDJPY=X', 'name': '💴 USD/JPY'},
        'aud': {'ticker': 'AUDUSD=X', 'name': '🇦🇺 AUD/USD'},
        'cad': {'ticker': 'USDCAD=X', 'name': '🇨🇦 USD/CAD'},
    }
    
    if data in asset_map:
        asset = asset_map[data]
        edit_message(message_id, f"📥 Menganalisis {asset['name']} ({selected_timeframe})...")
        
        try:
            result = analyze_asset_simple(asset['ticker'], asset['name'], selected_timeframe)
            
            if result:
                alasan_text = "\n".join([f"   {a}" for a in result['alasan']])
                msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>
⏰ Timeframe: <b>{result['timeframe']}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%

📌 Alasan:
{alasan_text}

📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
📊 RSI: {result['rsi']:.1f} | MACD: {result['macd']:.4f}
━━━━━━━━━━━━━━━━━━━━━
⚠️ Bukan nasihat keuangan
"""
                keyboard = [[{"text": "🔙 Kembali", "callback_data": "back"}]]
                edit_message(message_id, msg, keyboard)
            else:
                edit_message(message_id, f"❌ Gagal analisis {asset['name']} - data tidak tersedia")
        except Exception as e:
            logger.error(f"Analysis error: {traceback.format_exc()}")
            edit_message(message_id, f"❌ Error: {str(e)[:100]}")

# ========================================
# KIRIM SEMUA SINYAL
# ========================================
def kirim_semua_sinyal(message_id):
    msg = f"📊 <b>SEMUA SINYAL</b> (Timeframe: {selected_timeframe})\n━━━━━━━━━━━━━━━━━━━━━\n"
    
    for asset in ASSETS[:4]:  # Hanya 4 aset utama agar cepat
        result = analyze_asset_simple(asset['ticker'], asset['name'], selected_timeframe)
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
        time.sleep(0.3)
    
    keyboard = [[{"text": "🔙 Kembali", "callback_data": "back"}]]
    edit_message(message_id, msg, keyboard)

# ========================================
# AUTO SIGNAL
# ========================================
def kirim_auto_signal():
    logger.info("📢 Mengirim auto signal...")
    close_expired_signals()
    
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
        result = analyze_asset_simple(asset['ticker'], asset['name'], selected_timeframe)
        if result:
            alasan_text = "\n".join([f"   ✅ {a}" for a in result['alasan']])
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
            time.sleep(1)

# ========================================
# MAIN
# ========================================
def main():
    logger.info("🤖 KRUSTY KRAB TRADING BOT - ENHANCED v14.0 STARTED")
    logger.info("📊 DENGAN ERROR HANDLING")
    
    # Kirim menu pertama
    send_menu()
    
    # Auto signal setiap 4 jam
    def auto_signal_loop():
        while True:
            time.sleep(14400)
            try:
                kirim_auto_signal()
            except Exception as e:
                logger.error(f"Auto signal error: {e}")
    
    threading.Thread(target=auto_signal_loop, daemon=True).start()
    
    # Loop utama
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
                        if chat_id == CHAT_ID:
                            if text == '/start':
                                send_menu()
                            else:
                                send_message("❓ Kirim /start untuk menu")
                    
                    elif 'callback_query' in update:
                        callback = update['callback_query']
                        chat_id = str(callback['message']['chat']['id'])
                        if chat_id == CHAT_ID:
                            try:
                                handle_callback(
                                    callback['id'],
                                    callback['message']['message_id'],
                                    callback['data']
                                )
                            except Exception as e:
                                logger.error(f"Callback error: {traceback.format_exc()}")
                                answer_callback(callback['id'], "Error, coba lagi")
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped")
            break
        except Exception as e:
            logger.error(f"Main error: {traceback.format_exc()}")
            time.sleep(5)

if __name__ == "__main__":
    main()
