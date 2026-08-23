# ========================================
# KRUSTY KRAB TRADING BOT - ENHANCED VERSION
# ========================================

import os
import requests
import time
import sqlite3
import json
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import ta
import logging

# ========================================
# KONFIGURASI
# ========================================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "8907169595:AAHCwqL7Rc5y5iy2TmOF4--rgbpHVyvjnVE"  # Fallback

CHAT_ID = "8907169595"
BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================================
# DATABASE
# ========================================
def init_db():
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    
    # Tabel sinyal
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        )
    ''')
    
    # Tabel performance
    c.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL UNIQUE,
            total_signals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            expired INTEGER DEFAULT 0,
            total_profit REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabel watchlist
    c.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL UNIQUE,
            ticker TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        ON CONFLICT(asset) DO UPDATE SET 
            total_signals = total_signals + 1,
            updated_at = CURRENT_TIMESTAMP
    ''', (asset,))
    
    conn.commit()
    signal_id = c.lastrowid
    conn.close()
    return signal_id

def update_signal_result(signal_id, result, profit):
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    
    c.execute('SELECT asset FROM signals WHERE id = ?', (signal_id,))
    asset = c.fetchone()[0]
    
    c.execute('''
        UPDATE signals 
        SET result = ?, profit = ?, closed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (result, profit, signal_id))
    
    if result == 'WIN':
        c.execute('''
            UPDATE performance 
            SET wins = wins + 1, total_profit = total_profit + ?
            WHERE asset = ?
        ''', (profit, asset))
    elif result == 'LOSS':
        c.execute('''
            UPDATE performance 
            SET losses = losses + 1, total_profit = total_profit + ?
            WHERE asset = ?
        ''', (profit, asset))
    
    conn.commit()
    conn.close()

def get_performance():
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    
    c.execute('SELECT SUM(total_signals), SUM(wins), SUM(losses), SUM(total_profit) FROM performance')
    total = c.fetchone()
    
    c.execute('SELECT asset, total_signals, wins, losses, total_profit FROM performance')
    per_asset = c.fetchall()
    
    c.execute('''
        SELECT asset, signal_type, entry_price, result, profit, created_at 
        FROM signals 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    recent = c.fetchall()
    
    conn.close()
    return total, per_asset, recent

def get_watchlist():
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('SELECT asset, ticker FROM watchlist')
    result = c.fetchall()
    conn.close()
    return result

def add_to_watchlist(asset, ticker):
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO watchlist (asset, ticker) VALUES (?, ?)', (asset, ticker))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def remove_from_watchlist(asset):
    conn = sqlite3.connect('trading_history.db')
    c = conn.cursor()
    c.execute('DELETE FROM watchlist WHERE asset = ?', (asset,))
    conn.commit()
    conn.close()

# ========================================
# FUNGSI ANALISIS (ENHANCED)
# ========================================
def analyze_asset_enhanced(ticker, name):
    """Analisis lengkap dengan 12+ indikator"""
    try:
        asset = yf.Ticker(ticker)
        df = asset.history(period="2mo", interval="1d")
        
        if df.empty or len(df) < 30:
            return None
        
        # ===== INDIKATOR LENGKAP =====
        # Momentum
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        df['StochRSI'] = ta.momentum.StochRSIIndicator(df['Close'], window=14).stochrsi()
        
        # Trend
        df['MACD'] = ta.trend.MACD(df['Close']).macd()
        df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
        df['MACD_diff'] = df['MACD'] - df['MACD_signal']
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=200)
        df['EMA12'] = ta.trend.ema_indicator(df['Close'], window=12)
        df['EMA26'] = ta.trend.ema_indicator(df['Close'], window=26)
        
        # Volatilitas
        df['BB_high'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_hband()
        df['BB_mid'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_mavg()
        df['BB_low'] = ta.volatility.BollingerBands(df['Close'], window=20).bollinger_lband()
        df['BB_width'] = df['BB_high'] - df['BB_low']
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        
        # Volume
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_ratio'] = df['Volume'] / df['Volume_SMA']
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume'], window=14).money_flow_index()
        
        # Lainnya
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close'], window=20).cci()
        df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14).adx()
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        # Fibonacci
        high_20 = df['High'].tail(20).max()
        low_20 = df['Low'].tail(20).min()
        fib_382 = high_20 - (high_20 - low_20) * 0.382
        fib_618 = high_20 - (high_20 - low_20) * 0.618
        fib_786 = high_20 - (high_20 - low_20) * 0.786
        
        # ===== SCORING SYSTEM =====
        skor_buy = 0
        skor_sell = 0
        alasan = []
        confidence = 0
        
        # 1. RSI (20)
        if last['RSI'] < 30:
            skor_buy += 20
            alasan.append(f"RSI Oversold ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            skor_sell += 20
            alasan.append(f"RSI Overbought ({last['RSI']:.1f})")
        elif last['RSI'] < 40:
            skor_buy += 10
        elif last['RSI'] > 60:
            skor_sell += 10
        
        # 2. MACD (25)
        if last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal']:
            skor_buy += 25
            alasan.append("MACD Golden Cross (Bullish)")
        elif last['MACD'] < last['MACD_signal'] and prev['MACD'] >= prev['MACD_signal']:
            skor_sell += 25
            alasan.append("MACD Death Cross (Bearish)")
        elif last['MACD'] > last['MACD_signal']:
            skor_buy += 10
            alasan.append("MACD Bullish Momentum")
        else:
            skor_sell += 10
            alasan.append("MACD Bearish Momentum")
        
        # 3. Moving Average (20)
        if last['Close'] > last['SMA50'] and last['SMA20'] > last['SMA50']:
            skor_buy += 20
            alasan.append("Trend Bullish (Harga > SMA50)")
        elif last['Close'] < last['SMA50'] and last['SMA20'] < last['SMA50']:
            skor_sell += 20
            alasan.append("Trend Bearish (Harga < SMA50)")
        elif last['Close'] > last['SMA20']:
            skor_buy += 10
        else:
            skor_sell += 10
        
        # 4. Bollinger Bands (15)
        if last['Close'] < last['BB_low']:
            skor_buy += 15
            alasan.append("Harga di BB Lower (Oversold)")
        elif last['Close'] > last['BB_high']:
            skor_sell += 15
            alasan.append("Harga di BB Upper (Overbought)")
        elif last['Close'] < last['BB_mid']:
            skor_buy += 7
        else:
            skor_sell += 7
        
        # 5. StochRSI (10)
        if last['StochRSI'] < 0.2:
            skor_buy += 10
            alasan.append(f"StochRSI Oversold ({last['StochRSI']:.2f})")
        elif last['StochRSI'] > 0.8:
            skor_sell += 10
            alasan.append(f"StochRSI Overbought ({last['StochRSI']:.2f})")
        
        # 6. Volume (10)
        if last['Volume_ratio'] > 1.5 and skor_buy > skor_sell:
            skor_buy += 10
            alasan.append("Volume Tinggi (Konfirmasi Bullish)")
        elif last['Volume_ratio'] > 1.5 and skor_sell > skor_buy:
            skor_sell += 10
            alasan.append("Volume Tinggi (Konfirmasi Bearish)")
        
        # 7. Money Flow Index (MFI) - tambahan
        if last['MFI'] < 20:
            skor_buy += 10
            alasan.append(f"MFI Oversold ({last['MFI']:.1f})")
        elif last['MFI'] > 80:
            skor_sell += 10
            alasan.append(f"MFI Overbought ({last['MFI']:.1f})")
        
        # 8. ADX (Trend Strength) - tambahan
        if last['ADX'] > 25:
            if skor_buy > skor_sell:
                skor_buy += 10
                alasan.append(f"ADX Trend Kuat ({last['ADX']:.1f})")
            else:
                skor_sell += 10
                alasan.append(f"ADX Trend Kuat ({last['ADX']:.1f})")
        
        # ===== KEPUTUSAN =====
        total_skor = skor_buy + skor_sell
        
        if total_skor > 0:
            if skor_buy > skor_sell + 30:
                sinyal = "🔥 STRONG BUY"
                confidence = 90
            elif skor_buy > skor_sell + 15:
                sinyal = "📈 BUY"
                confidence = 75
            elif skor_buy > skor_sell:
                sinyal = "📈 WEAK BUY"
                confidence = 60
            elif skor_sell > skor_buy + 30:
                sinyal = "🔻 STRONG SELL"
                confidence = 90
            elif skor_sell > skor_buy + 15:
                sinyal = "📉 SELL"
                confidence = 75
            elif skor_sell > skor_buy:
                sinyal = "📉 WEAK SELL"
                confidence = 60
            else:
                sinyal = "⏸️ NEUTRAL"
                confidence = 50
        else:
            sinyal = "⏸️ NEUTRAL"
            confidence = 50
        
        # ===== TRADING LEVELS =====
        atr = last['ATR']
        entry = last['Close']
        
        if "BUY" in sinyal:
            sl = entry - (atr * 1.5)
            tp1 = entry + (atr * 1.5)
            tp2 = entry + (atr * 2.5)
            tp3 = entry + (atr * 4.0)
        elif "SELL" in sinyal:
            sl = entry + (atr * 1.5)
            tp1 = entry - (atr * 1.5)
            tp2 = entry - (atr * 2.5)
            tp3 = entry - (atr * 4.0)
        else:
            sl = entry - atr
            tp1 = entry + atr
            tp2 = entry + (atr * 2)
            tp3 = entry + (atr * 3)
        
        # ===== RESULT =====
        return {
            'name': name,
            'ticker': ticker,
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
            'fib_786': fib_786,
            'skor_buy': skor_buy,
            'skor_sell': skor_sell
        }
    
    except Exception as e:
        logger.error(f"Error analyzing {name}: {e}")
        return None

# ========================================
# FUNGSI SEND MESSAGE
# ========================================
def send_message(text):
    url = f"{BOT_URL}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Pesan terkirim")
        else:
            logger.error(f"❌ Gagal: {response.text}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

# ========================================
# KIRIM SINYAL ENHANCED
# ========================================
def kirim_sinyal_enhanced():
    """Kirim sinyal lengkap ke Telegram"""
    logger.info("📊 Mengirim sinyal enhanced...")
    
    assets = [
        {"ticker": "GC=F", "name": "🥇 XAU/USD (Emas)"},
        {"ticker": "BTC-USD", "name": "🪙 BTC/USD (Bitcoin)"},
        {"ticker": "ETH-USD", "name": "⚡ ETH/USD (Ethereum)"},
        {"ticker": "EURUSD=X", "name": "💶 EUR/USD (Forex)"},
    ]
    
    # Header
    header = f"""
╔═══════════════════════════════════════╗
║   🏦  KRUSTY KRAB TRADING BOT         ║
║   "Printing Money Since 2026"         ║
║   VERSION 5.0 - ENHANCED              ║
╚═══════════════════════════════════════╝

📊 <b>SINYAL TRADING ENHANCED</b>
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB
📊 12+ Indikator | AI-Powered Scoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    send_message(header)
    time.sleep(1)
    
    for asset in assets:
        result = analyze_asset_enhanced(asset['ticker'], asset['name'])
        
        if not result:
            continue
        
        # Simpan sinyal STRONG ke database
        if "STRONG" in result['sinyal']:
            direction = "BUY" if "BUY" in result['sinyal'] else "SELL"
            save_signal(
                result['name'].split()[0],
                direction,
                result['entry'],
                result['sl'],
                result['tp1'],
                result['tp2'],
                result['tp3']
            )
        
        # Format pesan
        alasan_text = "\n".join([f"   ✅ {a}" for a in result['alasan']])
        
        msg = f"""
<b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%
📊 Skor BUY/SELL: {result['skor_buy']}/{result['skor_sell']}

📌 <b>Alasan:</b>
{alasan_text}

⚡ <b>LEVEL:</b>
📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
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

🔺 <b>FIBONACCI:</b>
• 61.8%: ${result['fib_618']:,.2f}
• 38.2%: ${result['fib_382']:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        send_message(msg)
        time.sleep(1.5)
    
    # Footer
    footer = """
╔═══════════════════════════════════════╗
║   💡  TIPS TRADING                    ║
╚═══════════════════════════════════════╝

✅ Gunakan risk/reward minimal 1:2
✅ Jangan risk > 2% per trade
✅ Tunggu konfirmasi candle sebelum entry
✅ Gunakan trailing stop untuk profit

⚠️ <b>DISCLAIMER:</b>
Ini hanya analisis teknikal, BUKAN nasihat keuangan.
Risiko trading sepenuhnya tanggung jawab Anda.

📌 <b>Perintah:</b>
/xau  - Sinyal XAU/USD
/btc  - Sinyal BTC/USD
/eth  - Sinyal ETH/USD
/eur  - Sinyal EUR/USD
/all  - Semua sinyal
/history - Lihat winrate
/performance - Statistik lengkap
/help - Bantuan
"""
    send_message(footer)

# ========================================
# HANDLE PESAN
# ========================================
def handle_message(text):
    text = text.lower().strip()
    
    if text == "/start":
        msg = """
🏦 <b>KRUSTY KRAB TRADING BOT v5.0</b>

📌 <b>Perintah:</b>
/xau  - Sinyal XAU/USD (Emas)
/btc  - Sinyal BTC/USD (Bitcoin)
/eth  - Sinyal ETH/USD (Ethereum)
/eur  - Sinyal EUR/USD (Forex)
/all  - Semua sinyal lengkap
/history - History & Winrate
/performance - Statistik lengkap
/help - Bantuan

⚠️ Bukan nasihat keuangan
"""
        send_message(msg)
        return
    
    if text == "/help":
        msg = """
🤖 <b>PANDUAN BOT</b>

📌 <b>Perintah:</b>
/xau  - Analisis Emas (12 indikator)
/btc  - Analisis Bitcoin
/eth  - Analisis Ethereum
/eur  - Analisis EUR/USD
/all  - Semua aset
/history - History & Winrate

📊 <b>Fitur Enhanced:</b>
• 12+ Indikator Teknikal
• AI-Powered Scoring
• Support & Resistance
• Fibonacci Level
• Risk/Reward Ratio
• Database History

⚠️ <b>Disclaimer:</b>
Bot ini hanya untuk edukasi. Bukan nasihat keuangan.
"""
        send_message(msg)
        return
    
    if text == "/history" or text == "/performance":
        total, per_asset, recent = get_performance()
        total_signals, wins, losses, total_profit = total
        
        winrate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
        
        msg = f"""
📊 <b>HISTORY & PERFORMANCE</b>
━━━━━━━━━━━━━━━━━━━

📈 <b>Total:</b> {total_signals or 0} sinyal
✅ Win: {wins or 0}
❌ Loss: {losses or 0}
🏆 Winrate: <b>{winrate}%</b>
💰 Profit: <b>${total_profit or 0:,.2f}</b>

━━━━━━━━━━━━━━━━━━━
📊 <b>Per Aset:</b>
"""
        for asset, total, win, loss, profit in per_asset:
            asset_winrate = round((win / total) * 100, 1) if total > 0 else 0
            msg += f"\n{asset}: {total} sinyal | {asset_winrate}% | ${profit or 0:,.2f}"
        
        msg += """

━━━━━━━━━━━━━━━━━━━
📅 <b>History Terbaru:</b>
"""
        for asset, signal_type, entry, result, profit, created_at in recent[:5]:
            date = created_at.split()[0]
            status = result if result else '⏳ ACTIVE'
            profit_str = f"+${profit:,.2f}" if profit and profit > 0 else f"${profit:,.2f}" if profit else "$0"
            msg += f"\n{asset} | {date} | {signal_type} | {status} | {profit_str}"
        
        send_message(msg)
        return
    
    if text == "/all":
        kirim_sinyal_enhanced()
        return
    
    # Single asset
    asset_map = {
        "/xau": {"ticker": "GC=F", "name": "🥇 XAU/USD (Emas)"},
        "/btc": {"ticker": "BTC-USD", "name": "🪙 BTC/USD (Bitcoin)"},
        "/eth": {"ticker": "ETH-USD", "name": "⚡ ETH/USD (Ethereum)"},
        "/eur": {"ticker": "EURUSD=X", "name": "💶 EUR/USD (Forex)"},
    }
    
    if text in asset_map:
        asset = asset_map[text]
        send_message(f"📥 Menganalisis {asset['name']}...")
        time.sleep(0.5)
        
        result = analyze_asset_enhanced(asset['ticker'], asset['name'])
        
        if result:
            alasan_text = "\n".join([f"✅ {a}" for a in result['alasan']])
            msg = f"""
📊 <b>{result['name']}</b>
💰 Harga: <b>${result['price']:,.2f}</b>

🎯 <b>SINYAL: {result['sinyal']}</b>
📊 Konfidensi: {result['confidence']}%

📌 Alasan:
{alasan_text}

📍 Entry: ${result['entry']:,.2f}
🛑 SL: ${result['sl']:,.2f}
🎯 TP1: ${result['tp1']:,.2f}
🎯 TP2: ${result['tp2']:,.2f}
🎯 TP3: ${result['tp3']:,.2f}

📊 RSI: {result['rsi']:.1f} | MACD: {result['macd']:.4f}
📊 MFI: {result['mfi']:.1f} | ADX: {result['adx']:.1f}

⚠️ Bukan nasihat keuangan
"""
            send_message(msg)
        else:
            send_message(f"❌ Gagal analisis {asset['name']}")
        return
    
    if text:
        send_message("❓ Kirim /start untuk menu")

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
    logger.info("="*50)
    logger.info("🏦 KRUSTY KRAB TRADING BOT v5.0 ENHANCED")
    logger.info(f"📱 Chat ID: {CHAT_ID}")
    logger.info(f"🤖 Bot: @krepXau_bot")
    logger.info("="*50)
    
    # Kirim sinyal pertama
    logger.info("📊 Mengirim sinyal enhanced...")
    kirim_sinyal_enhanced()
    
    logger.info("✅ Sinyal terkirim!")
    logger.info("📌 Bot siap menerima perintah")
    logger.info("📌 Tekan Ctrl+C untuk berhenti")
    
    # Loop untuk menangani perintah
    last_update_id = None
    while True:
        try:
            updates = get_updates(last_update_id)
            if updates and updates.get('ok'):
                for update in updates.get('result', []):
                    last_update_id = update['update_id'] + 1
                    if 'message' in update:
                        chat_id = update['message']['chat']['id']
                        text = update['message'].get('text', '')
                        if str(chat_id) == CHAT_ID:
                            handle_message(text)
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info("👋 Bot berhenti")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
