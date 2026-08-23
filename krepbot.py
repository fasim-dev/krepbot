# ========================================
# KRUSTY KRAB TRADING BOT - FIXED VERSION
# PASTI JALAN DI RAILWAY
# ========================================

import os
import yfinance as yf
import pandas as pd
import ta
import requests
import json
import time
from datetime import datetime
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
print("🤖 KRUSTY KRAB TRADING BOT - FIXED VERSION")
print(f"🤖 Bot: @krepXau_bot")
print(f"📱 Chat ID: {CHAT_ID}")
print("="*60)

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
        logger.info(f"send_message: {response.status_code}")
        return response.json()
    except Exception as e:
        logger.error(f"send_message error: {e}")
        return None

def edit_message(message_id, text, keyboard=None):
    url = f"{BOT_URL}/editMessageText"
    payload = {'chat_id': CHAT_ID, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
    try:
        response = requests.post(url, json=payload, timeout=30)
        logger.info(f"edit_message: {response.status_code}")
        return response.json()
    except Exception as e:
        logger.error(f"edit_message error: {e}")
        return None

def answer_callback(callback_id):
    url = f"{BOT_URL}/answerCallbackQuery"
    try:
        response = requests.post(url, json={'callback_query_id': callback_id}, timeout=5)
        logger.info(f"answer_callback: {response.status_code}")
    except Exception as e:
        logger.error(f"answer_callback error: {e}")

# ========================================
# FUNGSI ANALISIS SEDERHANA
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
        
        logger.info(f"📊 Analisis {name} - {timeframe}")
        
        asset = yf.Ticker(ticker)
        df = asset.history(period=period, interval=interval)
        
        if df.empty or len(df) < 10:
            logger.warning(f"⚠️ Data kosong untuk {name}")
            return None
        
        # Indikator dasar
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        # Scoring
        skor_buy = 0
        skor_sell = 0
        alasan = []
        
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
        
        atr = last['ATR']
        entry = last['Close']
        
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
            'alasan': alasan[:3],
            'entry': entry,
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'rsi': last['RSI'],
            'macd': last['MACD'],
            'timeframe': timeframe
        }
    except Exception as e:
        logger.error(f"Error {name}: {e}")
        return None

# ========================================
# GLOBAL VARIABLE
# ========================================
selected_timeframe = "1h"

# ========================================
# MENU UTAMA
# ========================================
def send_menu(message_id=None):
    keyboard = [
        [{"text": "⏰ TIMEFRAME", "callback_data": "tf"}],
        [{"text": "🥇 XAU/USD", "callback_data": "xau"}, {"text": "🪙 BTC/USD", "callback_data": "btc"}],
        [{"text": "⚡ ETH/USD", "callback_data": "eth"}, {"text": "💶 EUR/USD", "callback_data": "eur"}],
        [{"text": "💷 GBP/USD", "callback_data": "gbp"}, {"text": "💴 USD/JPY", "callback_data": "usd"}],
        [{"text": "🇦🇺 AUD/USD", "callback_data": "aud"}, {"text": "🇨🇦 USD/CAD", "callback_data": "cad"}],
    ]
    msg = f"""
🏦 <b>KRUSTY KRAB TRADING BOT</b>
"Printing Money Since 2026"

⏰ Timeframe: <b>{selected_timeframe}</b>

📊 Pilih aset di bawah:
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
    logger.info(f"📥 Callback received: {data}")
    answer_callback(callback_id)
    
    # === TIMEFRAME SELECTION ===
    if data == "tf":
        keyboard = [
            [{"text": "🕐 5 Menit", "callback_data": "tf_5m"}, {"text": "🕐 15 Menit", "callback_data": "tf_15m"}],
            [{"text": "🕐 1 Jam", "callback_data": "tf_1h"}, {"text": "🕐 4 Jam", "callback_data": "tf_4h"}],
            [{"text": "🔙 Kembali", "callback_data": "menu"}],
        ]
        edit_message(message_id, f"⏰ Pilih Timeframe:\nSaat ini: {selected_timeframe}", keyboard)
        return
    
    if data in ["tf_5m", "tf_15m", "tf_1h", "tf_4h"]:
        tf_map = {
            "tf_5m": "5m",
            "tf_15m": "15m",
            "tf_1h": "1h",
            "tf_4h": "4h"
        }
        selected_timeframe = tf_map[data]
        edit_message(message_id, f"✅ Timeframe: {selected_timeframe}")
        send_menu(message_id)
        return
    
    if data == "menu":
        send_menu(message_id)
        return
    
    # === ASSET ANALYSIS ===
    asset_map = {
        'xau': {'ticker': 'XAUUSD=X', 'name': '🥇 XAU/USD'},
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
        
        result = analyze_asset(asset['ticker'], asset['name'], selected_timeframe)
        
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
            keyboard = [[{"text": "🔙 Kembali", "callback_data": "menu"}]]
            edit_message(message_id, msg, keyboard)
        else:
            edit_message(message_id, f"❌ Gagal analisis {asset['name']}")

# ========================================
# GET UPDATES
# ========================================
def get_updates(offset=None):
    url = f"{BOT_URL}/getUpdates"
    params = {'timeout': 30, 'offset': offset}
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        logger.error(f"get_updates error: {e}")
        return None

# ========================================
# MAIN
# ========================================
def main():
    logger.info("🤖 Bot started...")
    
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
                        if chat_id == CHAT_ID:
                            if text == '/start':
                                send_menu()
                            else:
                                send_message(f"❓ Kirim /start untuk menu")
                    
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
                                logger.error(f"Callback error: {e}")
                                answer_callback(callback['id'])
            time.sleep(2)
        except Exception as e:
            logger.error(f"Main error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
