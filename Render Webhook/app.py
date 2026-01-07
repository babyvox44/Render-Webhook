"""
零配置 Webhook 交易服務器
✅ 新策略只需改 Pine Script,服務器完全不動
✅ 自動識別交易所(Binance/OKX/Pionex)
✅ 支援無限個策略同時運行
✅ Telegram 通知
"""

from flask import Flask, request, jsonify
import hmac
import hashlib
import time
import requests
import json
import os
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# ==================== 環境變數讀取 ====================
def get_config():
    """從環境變數讀取配置"""
    return {
        # Binance
        "BINANCE_API_KEY": os.getenv("BINANCE_API_KEY", ""),
        "BINANCE_SECRET": os.getenv("BINANCE_SECRET", ""),
        
        # OKX
        "OKX_API_KEY": os.getenv("OKX_API_KEY", ""),
        "OKX_SECRET": os.getenv("OKX_SECRET", ""),
        "OKX_PASSPHRASE": os.getenv("OKX_PASSPHRASE", ""),
        
        # Pionex
        "PIONEX_API_KEY": os.getenv("PIONEX_API_KEY", ""),
        "PIONEX_SECRET": os.getenv("PIONEX_SECRET", ""),
        
        # Telegram
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    }

CONFIG = get_config()

# 持倉管理(key = "交易所_交易對_策略名")
positions = defaultdict(dict)
signal_history = []

# ==================== 工具函數 ====================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def is_duplicate(data):
    """防重複信號"""
    signal_id = f"{data.get('action')}_{data.get('symbol')}_{data.get('exchange')}_{time.time()//60}"
    if signal_id in signal_history:
        return True
    signal_history.append(signal_id)
    if len(signal_history) > 100:
        signal_history.pop(0)
    return False

def send_telegram(message):
    """發送 Telegram 通知"""
    if not CONFIG["TELEGRAM_BOT_TOKEN"] or not CONFIG["TELEGRAM_CHAT_ID"]:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendMessage"
        data = {
            "chat_id": CONFIG["TELEGRAM_CHAT_ID"],
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        log(f"⚠️ Telegram 失敗: {e}")
        return False

def format_symbol(symbol, exchange):
    """統一交易對格式"""
    symbol = symbol.upper().replace("USD", "USDT")
    if exchange == "okx":
        return symbol.replace("USDT", "-USDT") if "-" not in symbol else symbol
    elif exchange == "pionex":
        return symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
    return symbol

# ==================== Binance API ====================
def binance_set_leverage(symbol, leverage):
    """設置 Binance 槓桿"""
    try:
        url = "https://fapi.binance.com/fapi/v1/leverage"
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol,
            "leverage": int(leverage),
            "timestamp": timestamp
        }
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(CONFIG["BINANCE_SECRET"].encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        
        headers = {"X-MBX-APIKEY": CONFIG["BINANCE_API_KEY"]}
        response = requests.post(url, params=params, headers=headers)
        return response.status_code == 200
    except:
        return False

def binance_trade(action, symbol, quantity, stop_loss=None, leverage=None):
    """執行 Binance 交易"""
    try:
        # 設置槓桿
        if leverage:
            binance_set_leverage(symbol, leverage)
        
        # 下市價單
        url = "https://fapi.binance.com/fapi/v1/order"
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol,
            "side": "BUY" if action in ["buy", "add"] else "SELL",
            "type": "MARKET",
            "quantity": quantity,
            "timestamp": timestamp
        }
        
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(CONFIG["BINANCE_SECRET"].encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        
        headers = {"X-MBX-APIKEY": CONFIG["BINANCE_API_KEY"]}
        response = requests.post(url, params=params, headers=headers)
        
        if response.status_code == 200:
            order_data = response.json()
            avg_price = order_data.get('avgPrice', 'N/A')
            log(f"✅ Binance {action}: {symbol} x {quantity} @ {avg_price}")
            
            # 設置止損
            if action == "buy" and stop_loss:
                binance_set_stop_loss(symbol, quantity, stop_loss)
            
            return {"success": True, "price": avg_price, "data": order_data}
        else:
            log(f"❌ Binance 錯誤: {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        log(f"❌ Binance 異常: {e}")
        return {"success": False, "error": str(e)}

def binance_set_stop_loss(symbol, quantity, stop_price):
    """設置 Binance 止損單"""
    try:
        url = "https://fapi.binance.com/fapi/v1/order"
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "STOP_MARKET",
            "stopPrice": stop_price,
            "quantity": quantity,
            "timestamp": timestamp
        }
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(CONFIG["BINANCE_SECRET"].encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        
        headers = {"X-MBX-APIKEY": CONFIG["BINANCE_API_KEY"]}
        response = requests.post(url, params=params, headers=headers)
        log(f"🛡️ Binance 止損: {stop_price} - {response.status_code}")
    except Exception as e:
        log(f"❌ 止損設置失敗: {e}")

def binance_update_stop_loss(symbol, new_stop):
    """更新 Binance 止損(先取消舊單再下新單)"""
    try:
        # 取消所有止損單
        cancel_url = "https://fapi.binance.com/fapi/v1/allOpenOrders"
        timestamp = int(time.time() * 1000)
        params = {"symbol": symbol, "timestamp": timestamp}
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(CONFIG["BINANCE_SECRET"].encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        
        headers = {"X-MBX-APIKEY": CONFIG["BINANCE_API_KEY"]}
        requests.delete(cancel_url, params=params, headers=headers)
        
        # 重新設置止損
        pos_key = f"binance_{symbol}"
        if pos_key in positions and "qty" in positions[pos_key]:
            binance_set_stop_loss(symbol, positions[pos_key]["qty"], new_stop)
            log(f"📈 Binance 移動止損: {new_stop}")
            return True
        return False
    except Exception as e:
        log(f"❌ 移動止損失敗: {e}")
        return False

# ==================== OKX API ====================
def okx_trade(action, symbol, quantity, stop_loss=None, leverage=None):
    """執行 OKX 交易"""
    try:
        url = "https://www.okx.com/api/v5/trade/order"
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        
        body = {
            "instId": symbol,
            "tdMode": "cross",
            "side": "buy" if action in ["buy", "add"] else "sell",
            "ordType": "market",
            "sz": str(quantity)
        }
        
        if leverage:
            body["lever"] = str(leverage)
        
        body_str = json.dumps(body)
        sign_str = timestamp + "POST" + "/api/v5/trade/order" + body_str
        signature = hmac.new(CONFIG["OKX_SECRET"].encode(), sign_str.encode(), hashlib.sha256).hexdigest()
        
        headers = {
            "OK-ACCESS-KEY": CONFIG["OKX_API_KEY"],
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": CONFIG["OKX_PASSPHRASE"],
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, data=body_str, headers=headers)
        
        if response.status_code == 200 and response.json().get("code") == "0":
            log(f"✅ OKX {action}: {symbol} x {quantity}")
            return {"success": True, "data": response.json()}
        else:
            log(f"❌ OKX 錯誤: {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        log(f"❌ OKX 異常: {e}")
        return {"success": False, "error": str(e)}

# ==================== Pionex API (簡化版) ====================
def pionex_trade(action, symbol, quantity, stop_loss=None, leverage=None):
    """執行 Pionex 交易"""
    try:
        url = "https://api.pionex.com/api/v1/trade"
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol,
            "side": action.upper(),
            "type": "MARKET",
            "quantity": quantity,
            "timestamp": timestamp
        }
        
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(CONFIG["PIONEX_SECRET"].encode(), query.encode(), hashlib.sha256).hexdigest()
        
        headers = {
            "PIONEX-KEY": CONFIG["PIONEX_API_KEY"],
            "PIONEX-SIGNATURE": signature
        }
        
        response = requests.post(url, json=params, headers=headers)
        
        if response.status_code == 200:
            log(f"✅ Pionex {action}: {symbol} x {quantity}")
            return {"success": True, "data": response.json()}
        else:
            log(f"❌ Pionex 錯誤: {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        log(f"❌ Pionex 異常: {e}")
        return {"success": False, "error": str(e)}

# ==================== 主路由 ====================
@app.route('/webhook', methods=['POST'])
def webhook():
    """統一 Webhook 接收端點"""
    try:
        data = request.get_json()
        log(f"📩 收到信號: {json.dumps(data, ensure_ascii=False)}")
        
        # 防重複
        if is_duplicate(data):
            log("⚠️ 重複信號已忽略")
            return jsonify({"message": "Duplicate ignored"}), 200
        
        # 解析參數
        action = data.get('action', 'buy')
        symbol_raw = data.get('symbol', 'BTCUSDT')
        quantity = float(data.get('qty', 0.001))
        exchange = data.get('exchange', 'binance').lower()
        stop_loss = float(data.get('stop_loss', 0)) if data.get('stop_loss') else None
        leverage = int(data.get('leverage', 1)) if data.get('leverage') else None
        strategy_name = data.get('strategy', 'default')
        
        # 格式化交易對
        symbol = format_symbol(symbol_raw, exchange)
        
        # 處理更新止損
        if action == "update_stop":
            new_stop = float(data.get('new_stop_loss', 0))
            if exchange == "binance":
                result = binance_update_stop_loss(symbol, new_stop)
                if result:
                    # Telegram 通知
                    msg = f"""
📈 <b>移動止損</b>
━━━━━━━━━━━━━━━━
🏦 交易所: <b>{exchange.upper()}</b>
💰 交易對: <b>{symbol}</b>
🎯 新止損: <b>{new_stop}</b>
📊 策略: <b>{strategy_name}</b>
━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    send_telegram(msg)
                return jsonify({"success": result}), 200
            return jsonify({"error": "Only Binance supports trailing stop"}), 400
        
        # 執行交易
        result = None
        if exchange == 'binance':
            result = binance_trade(action, symbol, quantity, stop_loss, leverage)
        elif exchange == 'okx':
            result = okx_trade(action, symbol, quantity, stop_loss, leverage)
        elif exchange == 'pionex':
            result = pionex_trade(action, symbol, quantity, stop_loss, leverage)
        else:
            return jsonify({"error": f"Unsupported exchange: {exchange}"}), 400
        
        # 記錄持倉
        if result and result.get('success'):
            pos_key = f"{exchange}_{symbol}_{strategy_name}"
            if action in ["buy", "add"]:
                positions[pos_key] = {
                    "qty": quantity,
                    "stop_loss": stop_loss,
                    "leverage": leverage,
                    "entry_time": datetime.now().isoformat()
                }
            elif action == "sell":
                if pos_key in positions:
                    del positions[pos_key]
            
            # Telegram 通知
            emoji_map = {"buy": "🟢", "add": "🔵", "sell": "🔴"}
            emoji = emoji_map.get(action, "⚪")
            
            msg = f"""
{emoji} <b>{action.upper()} 執行成功</b>
━━━━━━━━━━━━━━━━
🏦 交易所: <b>{exchange.upper()}</b>
💰 交易對: <b>{symbol}</b>
📦 數量: <b>{quantity}</b>
💵 價格: <b>{result.get('price', 'N/A')}</b>
🎯 止損: <b>{stop_loss if stop_loss else '未設置'}</b>
⚡ 槓桿: <b>{leverage}x</b>
📊 策略: <b>{strategy_name}</b>
━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            send_telegram(msg)
        
        return jsonify(result), 200 if result.get('success') else 500
        
    except Exception as e:
        log(f"❌ 處理錯誤: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/positions', methods=['GET'])
def get_positions():
    """查看所有持倉"""
    return jsonify(dict(positions)), 200

@app.route('/health', methods=['GET'])
def health():
    """健康檢查"""
    return jsonify({
        "status": "running",
        "time": datetime.now().isoformat(),
        "positions_count": len(positions),
        "exchanges": {
            "binance": bool(CONFIG["BINANCE_API_KEY"]),
            "okx": bool(CONFIG["OKX_API_KEY"]),
            "pionex": bool(CONFIG["PIONEX_API_KEY"])
        }
    }), 200

@app.route('/', methods=['GET'])
def home():
    """首頁"""
    exchanges_status = []
    if CONFIG["BINANCE_API_KEY"]:
        exchanges_status.append("✅ Binance")
    if CONFIG["OKX_API_KEY"]:
        exchanges_status.append("✅ OKX")
    if CONFIG["PIONEX_API_KEY"]:
        exchanges_status.append("✅ Pionex")
    
    return f"""
    <h1>🤖 零配置交易機器人</h1>
    <p>狀態: <span style="color:green">運行中</span></p>
    
    <h3>📡 Webhook 端點:</h3>
    <ul>
        <li><code>POST /webhook</code> - 統一接收所有策略</li>
        <li><code>GET /positions</code> - 查看持倉</li>
        <li><code>GET /health</code> - 健康檢查</li>
    </ul>
    
    <h3>🏦 已配置交易所:</h3>
    <ul>
        {''.join([f'<li>{ex}</li>' for ex in exchanges_status])}
    </ul>
    
    <h3>💼 當前持倉 ({len(positions)}):</h3>
    <pre>{json.dumps(dict(positions), indent=2, ensure_ascii=False)}</pre>
    
    <h3>📱 Telegram:</h3>
    <p>{'✅ 已配置' if CONFIG['TELEGRAM_BOT_TOKEN'] else '❌ 未配置'}</p>
    """

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    log(f"🚀 服務器啟動於端口 {port}")
    app.run(host='0.0.0.0', port=port)