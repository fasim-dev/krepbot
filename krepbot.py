# ========================================
# KRUSTY KRAB TRADING BOT - RAILWAY VERSION
# FILE: krepbot.py
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("="*60)
print("🤖 KRUSTY KRAB TRADING BOT - RAILWAY")
print(f"🤖 Bot: @krepXau_bot")
print(f"📱 Chat ID: {CHAT_ID}")
print("="*60)

# ========================================
# FUNGSI KIRIM PESAN
# ========================================
def send_message(text):
    try:
        response = requests.post(f"{BOT_URL}/sendMessage", 
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=30)
        if response.status_code == 200:
            logger.info("✅ Pesan terkirim!")
            return True
        else:
            logger.error(f"❌ Gagal: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

# ========================================
# FUNGSI ANALISIS
# ========================================
def analyze_asset(ticker, name):
    try:
        if ticker == "XAUUSD=X":
            ticker = "GC=F"
        
        asset = yf.Ticker(ticker)
        df = asset.history(period="1mo", interval="1d")
        
        if df.empty or len(df) < 10:
            return None
        
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
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
            'macd': last['MACD']
        }
    except Exception as e:
        logger.error(f"Error {name}: {e}")
        return None

# ========================================
# KIRIM SINYAL KE TELEGRAM
# ========================================
def kirim_sinyal():
    logger.info("📊 Mengirim sinyal...")
    
    # Header
    header = f"""
╔═══════════════════════════════════════╗
║   🏦  KRUSTY KRAB TRADING BOT         ║
║   "Printing Money Since 2026"         ║
╚═══════════════════════════════════════╝

📊 <b>SINYAL TRADING</b>
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    send_message(header)
    time.sleep(1)
    
    assets = [
        {"ticker": "XAUUSD=X", "name": "🥇 XAU/USD (Emas)"},
        {"ticker": "BTC-USD", "name": "🪙 BTC/USD (Bitcoin)"},
        {"ticker": "ETH-USD", "name": "⚡ ETH/USD (Ethereum)"},
    ]
    
    for asset in assets:
        result = analyze_asset(asset['ticker'], asset['name'])
        if result:
            alasan_text = "\n".join([f"   {a}" for a in result['alasan']])
            msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>
🎯 Sinyal: <b>{result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%

📌 Alasan:
{alasan_text}

📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
📊 RSI: {result['rsi']:.1f} | MACD: {result['macd']:.4f}
━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            send_message(msg)
            time.sleep(1)
        else:
            send_message(f"❌ Gagal analisis {asset['name']}")
    
    footer = """
⚠️ <b>DISCLAIMER:</b>
Ini hanya analisis teknikal, BUKAN nasihat keuangan.
Risiko sepenuhnya tanggung jawab Anda.

💡 <b>Tips:</b>
• Risk/reward minimal 1:2
• Jangan risk > 2% per trade
"""
    send_message(footer)
    logger.info("✅ Selesai!")

# ========================================
# MAIN
# ========================================
def main():
    logger.info("🤖 Bot started...")
    kirim_sinyal()
    
    # Loop setiap 4 jam
    while True:
        time.sleep(14400)  # 4 jam
        kirim_sinyal()

if __name__ == "__main__":
    main()
