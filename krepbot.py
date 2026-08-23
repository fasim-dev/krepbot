# ========================================
# KRUSTY KRAB TRADING BOT - ENHANCED v6.0
# DEPLOY VERSION
# ========================================

import os
import yfinance as yf
import pandas as pd
import ta
import requests
import time
import sqlite3
import json
from datetime import datetime, timedelta
import logging

# ========================================
# KONFIGURASI - AMBIL DARI ENVIRONMENT
# ========================================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "8907169595:AAHCwqL7Rc5y5iy2TmOF4--rgbpHVyvjnVE"  # Fallback

CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
if not CHAT_ID:
    CHAT_ID = "743527023"  # Fallback

BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("="*60)
print("🏦 KRUSTY KRAB TRADING BOT - ENHANCED v6.0")
print(f"🤖 Bot: @krepXau_bot")
print(f"📱 Chat ID: {CHAT_ID}")
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
def save_signal(asset, signal_type, entry, sl, tp1, tp2, tp3):
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO signals (asset, signal_type, entry_price, sl_price, tp1_price, tp2_price, tp3_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (asset, signal_type, entry, sl, tp1, tp2, tp3))
    c.execute('''
        INSERT INTO performance (asset, total_signals) 
        VALUES (?, 1)
        ON CONFLICT(asset) DO UPDATE SET total_signals = total_signals + 1
    ''', (asset,))
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
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    if keyboard:
        payload['reply_markup'] = json.dumps({
            'inline_keyboard': keyboard
        })
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
    payload = {
        'chat_id': CHAT_ID,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if keyboard:
        payload['reply_markup'] = json.dumps({
            'inline_keyboard': keyboard
        })
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
# FUNGSI ANALISIS ENHANCED
# ========================================
def analyze_asset(ticker, name):
    try:
        asset = yf.Ticker(ticker)
        df = asset.history(period="2mo", interval="1d")
        if df.empty or len(df) < 20:
            return None

        # Indikator
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['MACD_diff'] = df['MACD'] - df['MACD_signal']
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=200)
        df['BB_high'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_hband()
        df['BB_mid'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_mavg()
        df['BB_low'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_lband()
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        df['StochRSI'] = ta.momentum.StochRSIIndicator(df['Close'], window=14).stochrsi()
        df['Volume_ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume'], window=14).money_flow_index()
        df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14).adx()

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        # Fibonacci
        high_20 = df['High'].tail(20).max()
        low_20 = df['Low'].tail(20).min()
        fib_382 = high_20 - (high_20 - low_20) * 0.382
        fib_618 = high_20 - (high_20 - low_20) * 0.618

        # Scoring
        skor_buy, skor_sell, alasan = 0, 0, []

        # RSI
        if last['RSI'] < 30:
            skor_buy += 20
            alasan.append(f"RSI Oversold ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            skor_sell += 20
            alasan.append(f"RSI Overbought ({last['RSI']:.1f})")

        # MACD
        if last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal']:
            skor_buy += 25
            alasan.append("MACD Golden Cross")
        elif last['MACD'] < last['MACD_signal'] and prev['MACD'] >= prev['MACD_signal']:
            skor_sell += 25
            alasan.append("MACD Death Cross")

        # SMA
        if last['Close'] > last['SMA50']:
            skor_buy += 20
            alasan.append("Harga > SMA50")
        else:
            skor_sell += 20
            alasan.append("Harga < SMA50")

        # BB
        if last['Close'] < last['BB_low']:
            skor_buy += 15
            alasan.append("Harga di BB Lower")
        elif last['Close'] > last['BB_high']:
            skor_sell += 15
            alasan.append("Harga di BB Upper")

        # StochRSI
        if last['StochRSI'] < 0.2:
            skor_buy += 10
            alasan.append(f"StochRSI Oversold ({last['StochRSI']:.2f})")
        elif last['StochRSI'] > 0.8:
            skor_sell += 10
            alasan.append(f"StochRSI Overbought ({last['StochRSI']:.2f})")

        # Volume
        if last['Volume_ratio'] > 1.5:
            if skor_buy > skor_sell:
                skor_buy += 10
                alasan.append("Volume tinggi (konfirmasi)")
            else:
                skor_sell += 10
                alasan.append("Volume tinggi (konfirmasi)")

        # MFI
        if last['MFI'] < 20:
            skor_buy += 10
            alasan.append(f"MFI Oversold ({last['MFI']:.1f})")
        elif last['MFI'] > 80:
            skor_sell += 10
            alasan.append(f"MFI Overbought ({last['MFI']:.1f})")

        # ADX
        if last['ADX'] > 25:
            if skor_buy > skor_sell:
                skor_buy += 10
                alasan.append(f"ADX Trend Kuat ({last['ADX']:.1f})")
            else:
                skor_sell += 10
                alasan.append(f"ADX Trend Kuat ({last['ADX']:.1f})")

        # Keputusan
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

        # Level
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

        if "STRONG" in sinyal:
            direction = "BUY" if "BUY" in sinyal else "SELL"
            save_signal(name.split()[0], direction, entry, sl, tp1, tp2, tp3)

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
            'date': df.index[-1]
        }
    except Exception as e:
        logger.error(f"Error {name}: {e}")
        return None

# ========================================
# HANDLE CALLBACK
# ========================================
def handle_callback(callback_id, message_id, data):
    answer_callback(callback_id)
    
    asset_map = {
        'xau': {'ticker': 'GC=F', 'name': '🥇 XAU/USD (Emas)'},
        'btc': {'ticker': 'BTC-USD', 'name': '🪙 BTC/USD (Bitcoin)'},
        'eth': {'ticker': 'ETH-USD', 'name': '⚡ ETH/USD (Ethereum)'},
        'eur': {'ticker': 'EURUSD=X', 'name': '💶 EUR/USD (Forex)'},
        'gbp': {'ticker': 'GBPUSD=X', 'name': '💷 GBP/USD (Forex)'},
        'usd': {'ticker': 'USDJPY=X', 'name': '💴 USD/JPY (Forex)'},
        'aud': {'ticker': 'AUDUSD=X', 'name': '🇦🇺 AUD/USD (Forex)'},
        'nzd': {'ticker': 'NZDUSD=X', 'name': '🇳🇿 NZD/USD (Forex)'},
        'usdcad': {'ticker': 'USDCAD=X', 'name': '🇨🇦 USD/CAD (Forex)'},
        'all': None,
        'menu': None,
        'back': None,
    }
    
    if data == 'menu' or data == 'back':
        send_menu(message_id)
        return
    
    if data == 'all':
        edit_message(message_id, "📊 Mengirim semua sinyal...")
        send_all_signals(message_id)
        return
    
    if data == 'performance':
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
        edit_message(message_id, f"📥 Menganalisis {asset['name']}...")
        result = analyze_asset(asset['ticker'], asset['name'])
        
        if result:
            alasan_text = "\n".join([f"   ✅ {a}" for a in result['alasan']])
            msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%
📊 Skor: {result['skor_buy']}/{result['skor_sell']}

📌 <b>Alasan:</b>
{alasan_text}

⚡ <b>LEVEL:</b>
📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
🎯 TP3: ${result['tp3']:,.2f}

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
        [{"text": "🥇 XAU/USD", "callback_data": "xau"}, {"text": "🪙 BTC/USD", "callback_data": "btc"}],
        [{"text": "⚡ ETH/USD", "callback_data": "eth"}, {"text": "💶 EUR/USD", "callback_data": "eur"}],
        [{"text": "💷 GBP/USD", "callback_data": "gbp"}, {"text": "💴 USD/JPY", "callback_data": "usd"}],
        [{"text": "🇦🇺 AUD/USD", "callback_data": "aud"}, {"text": "🇳🇿 NZD/USD", "callback_data": "nzd"}],
        [{"text": "🇨🇦 USD/CAD", "callback_data": "usdcad"}],
        [{"text": "📊 SEMUA SINYAL", "callback_data": "all"}, {"text": "📈 PERFORMANCE", "callback_data": "performance"}],
    ]
    
    msg = """
╔═══════════════════════════════════════╗
║   🏦  KRUSTY KRAB TRADING BOT         ║
║   "Printing Money Since 2026"         ║
║   VERSION 6.0 - ENHANCED              ║
╚═══════════════════════════════════════╝

📊 <b>PILIH ASET:</b>

🥇 <b>Emas</b> - Safe haven
🪙 <b>Bitcoin</b> - Crypto King
⚡ <b>Ethereum</b> - Smart Contract

💶 <b>EUR/USD</b> - Major Pair
💷 <b>GBP/USD</b> - Cable
💴 <b>USD/JPY</b> - Safe haven

🇦🇺 <b>AUD/USD</b> - Aussie
🇳🇿 <b>NZD/USD</b> - Kiwi
🇨🇦 <b>USD/CAD</b> - Loonie

📊 <b>Fitur:</b>
• 12+ Indikator Teknikal
• AI-Powered Scoring
• 3 Level TP
• Database History
• Performance Tracker
"""
    if message_id:
        edit_message(message_id, msg, keyboard)
    else:
        send_message(msg, keyboard)

# ========================================
# SEND ALL SIGNALS
# ========================================
def send_all_signals(message_id):
    assets = [
        {"ticker": "GC=F", "name": "🥇 XAU/USD (Emas)"},
        {"ticker": "BTC-USD", "name": "🪙 BTC/USD (Bitcoin)"},
        {"ticker": "ETH-USD", "name": "⚡ ETH/USD (Ethereum)"},
        {"ticker": "EURUSD=X", "name": "💶 EUR/USD (Forex)"},
        {"ticker": "GBPUSD=X", "name": "💷 GBP/USD (Forex)"},
        {"ticker": "USDJPY=X", "name": "💴 USD/JPY (Forex)"},
        {"ticker": "AUDUSD=X", "name": "🇦🇺 AUD/USD (Forex)"},
        {"ticker": "NZDUSD=X", "name": "🇳🇿 NZD/USD (Forex)"},
        {"ticker": "USDCAD=X", "name": "🇨🇦 USD/CAD (Forex)"},
    ]
    
    msg = "📊 <b>SEMUA SINYAL</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
    
    for asset in assets:
        result = analyze_asset(asset['ticker'], asset['name'])
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
    logger.info("🤖 Bot started...")
    logger.info("📌 Kirim /start ke @krepXau_bot")
    
    # Kirim menu pertama
    send_menu()
    
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
