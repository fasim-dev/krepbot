import os
import requests
import time
import sqlite3
from datetime import datetime
import yfinance as yf
import pandas as pd
import ta
import logging
import traceback

# ========================================
# KONFIGURASI
# ========================================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "8907169595:AAHCwqL7Rc5y5iy2TmOF4--rgbpHVyvjnVE"

CHAT_ID = "8907169595"
BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================
# FUNGSI KIRIM PESAN
# ========================================
def send_message(text):
    try:
        url = f"{BOT_URL}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            logger.info("✅ Pesan terkirim")
        else:
            logger.error(f"❌ Gagal: {response.text}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

# ========================================
# FUNGSI ANALISIS (SEDERHANA & STABIL)
# ========================================
def analyze_asset(ticker, name):
    try:
        logger.info(f"📊 Menganalisis {name}...")
        
        # Ambil data dengan timeout
        asset = yf.Ticker(ticker)
        df = asset.history(period="1mo", interval="1d")
        
        if df.empty or len(df) < 10:
            send_message(f"❌ Data {name} tidak cukup")
            return None
        
        last = df.iloc[-1]
        
        # Hitung indikator sederhana
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        # Scoring sederhana
        skor_buy = 0
        skor_sell = 0
        alasan = []
        
        if last['RSI'] < 30:
            skor_buy += 20
            alasan.append(f"RSI Oversold ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            skor_sell += 20
            alasan.append(f"RSI Overbought ({last['RSI']:.1f})")
        
        if last['MACD'] > last['MACD_signal']:
            skor_buy += 15
            alasan.append("MACD Bullish")
        else:
            skor_sell += 15
            alasan.append("MACD Bearish")
        
        if last['Close'] > last['SMA50']:
            skor_buy += 15
            alasan.append("Harga > SMA50")
        else:
            skor_sell += 15
            alasan.append("Harga < SMA50")
        
        if skor_buy > skor_sell + 20:
            sinyal = "🔥 STRONG BUY"
            confidence = 85
        elif skor_buy > skor_sell:
            sinyal = "📈 WEAK BUY"
            confidence = 65
        elif skor_sell > skor_buy + 20:
            sinyal = "🔻 STRONG SELL"
            confidence = 85
        elif skor_sell > skor_buy:
            sinyal = "📉 WEAK SELL"
            confidence = 65
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
            'macd': last['MACD']
        }
        
    except Exception as e:
        logger.error(f"Error: {e}")
        send_message(f"❌ Error analisis {name}: {str(e)[:100]}")
        return None

# ========================================
# KIRIM SINYAL
# ========================================
def kirim_sinyal():
    try:
        send_message("📊 Menganalisis pasar...")
        
        assets = [
            {"ticker": "GC=F", "name": "🥇 XAU/USD"},
            {"ticker": "BTC-USD", "name": "🪙 BTC/USD"},
            {"ticker": "ETH-USD", "name": "⚡ ETH/USD"},
        ]
        
        for asset in assets:
            result = analyze_asset(asset['ticker'], asset['name'])
            if result:
                alasan_text = "\n".join([f"✅ {a}" for a in result['alasan']])
                msg = f"""
🏦 KRUSTY KRAB TRADING BOT

{result['name']}
💰 Harga: <b>${result['price']:,.2f}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%

📌 Alasan:
{alasan_text}

📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
📊 RSI: {result['rsi']:.1f}
📊 MACD: {result['macd']:.4f}
"""
                send_message(msg)
                time.sleep(1)
        
        send_message("✅ Sinyal selesai dikirim")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        send_message(f"❌ Error: {str(e)[:100]}")

# ========================================
# HANDLE PESAN
# ========================================
def handle_message(text):
    text = text.lower().strip()
    
    if text == "/start":
        send_message("""
🏦 KRUSTY KRAB TRADING BOT

📌 Perintah:
/xau - XAU/USD
/btc - BTC/USD
/eth - ETH/USD
/all - Semua sinyal
/help - Bantuan
""")
        return
    
    if text == "/help":
        send_message("""
📌 Kirim perintah:
/xau - Emas
/btc - Bitcoin
/eth - Ethereum
/all - Semua
""")
        return
    
    if text == "/all":
        kirim_sinyal()
        return
    
    asset_map = {
        "/xau": {"ticker": "GC=F", "name": "🥇 XAU/USD"},
        "/btc": {"ticker": "BTC-USD", "name": "🪙 BTC/USD"},
        "/eth": {"ticker": "ETH-USD", "name": "⚡ ETH/USD"},
    }
    
    if text in asset_map:
        asset = asset_map[text]
        result = analyze_asset(asset['ticker'], asset['name'])
        if result:
            alasan_text = "\n".join([f"✅ {a}" for a in result['alasan']])
            msg = f"""
🏦 {result['name']}
💰 ${result['price']:,.2f}
🎯 {result['sinyal']} ({result['confidence']}%)
📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
📊 RSI: {result['rsi']:.1f}
"""
            send_message(msg)
        return
    
    if text:
        send_message("❓ Kirim /start")

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
    logger.info("🤖 KRUSTY KRAB TRADING BOT STARTED")
    send_message("✅ Bot online!")
    kirim_sinyal()
    
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
                            handle_message(text)
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
