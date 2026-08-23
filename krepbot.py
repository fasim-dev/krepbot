# ========================================
# KRUSTY KRAB TRADING BOT - WEBHOOK VERSION
# PASTI JALAN DI RAILWAY
# ========================================

import os
import yfinance as yf
import pandas as pd
import ta
import requests
import json
from datetime import datetime
import logging

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "8907169595:AAHCwqL7Rc5y5iy2TmOF4--rgbpHVyvjnVE"

CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
if not CHAT_ID:
    CHAT_ID = "743527023"

BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("="*60)
print("🤖 KRUSTY KRAB TRADING BOT - WEBHOOK")
print(f"🤖 Bot: @krepXau_bot")
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
        return response.json()
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

# ========================================
# FUNGSI ANALISIS
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
        
        asset = yf.Ticker(ticker)
        df = asset.history(period=period, interval=interval)
        
        if df.empty or len(df) < 10:
            return None
        
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
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
# WEBHOOK HANDLER
# ========================================
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"📥 Webhook received: {data}")
        
        if 'callback_query' in data:
            callback = data['callback_query']
            callback_id = callback['id']
            message_id = callback['message']['message_id']
            chat_id = str(callback['message']['chat']['id'])
            
            # Answer callback
            requests.post(f"{BOT_URL}/answerCallbackQuery", 
                         json={'callback_query_id': callback_id})
            
            if chat_id == CHAT_ID:
                handle_callback(message_id, callback['data'])
        
        elif 'message' in data:
            message = data['message']
            chat_id = str(message['chat']['id'])
            text = message.get('text', '')
            
            if chat_id == CHAT_ID:
                if text == '/start':
                    send_menu()
                else:
                    send_message("❓ Kirim /start untuk menu")
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

def handle_callback(message_id, data):
    global selected_timeframe
    
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
            send_menu(message_id, msg, keyboard)
        else:
            send_menu(message_id, f"❌ Gagal analisis {asset['name']}")

def send_menu(message_id=None, text=None, keyboard=None):
    if text:
        url = f"{BOT_URL}/editMessageText"
        payload = {'chat_id': CHAT_ID, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
        if keyboard:
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard})
        requests.post(url, json=payload)
        return
    
    keyboard = [
        [{"text": "🥇 XAU/USD", "callback_data": "xau"}, {"text": "🪙 BTC/USD", "callback_data": "btc"}],
        [{"text": "⚡ ETH/USD", "callback_data": "eth"}, {"text": "💶 EUR/USD", "callback_data": "eur"}],
        [{"text": "💷 GBP/USD", "callback_data": "gbp"}, {"text": "💴 USD/JPY", "callback_data": "usd"}],
        [{"text": "🇦🇺 AUD/USD", "callback_data": "aud"}, {"text": "🇨🇦 USD/CAD", "callback_data": "cad"}],
    ]
    msg = """
🏦 <b>KRUSTY KRAB TRADING BOT</b>
"Printing Money Since 2026"

📊 Pilih aset di bawah:
"""
    send_message(msg, keyboard)

selected_timeframe = "1h"

if __name__ == "__main__":
    # Set webhook
    webhook_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
    if webhook_url:
        webhook_url = f"https://{webhook_url}/webhook"
        requests.post(f"{BOT_URL}/setWebhook", json={'url': webhook_url})
        logger.info(f"✅ Webhook set to: {webhook_url}")
    
    # Kirim menu pertama
    send_menu()
    
    # Jalankan server
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
