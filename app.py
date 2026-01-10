"""
零配置 Webhook 交易服務器
✅ 新策略只需改 Pine Script,服務器完全不動
✅ 自動識別交易所(Binance/OKX/Bybit/Gate/Bitget/KuCoin)
✅ 支援無限個策略同時運行
✅ Telegram 通知
"""
from flask import Flask, request, jsonify
import ccxt
import time
import requests
import json
import os
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# ==================== 環境變數配置 ====================
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
      
        # Bybit
        "BYBIT_API_KEY": os.getenv("BYBIT_API_KEY", ""),
        "BYBIT_SECRET": os.getenv("BYBIT_SECRET", ""),
      
        # Gate.io (新增)
        "GATE_API_KEY": os.getenv("GATE_API_KEY", ""),
        "GATE_SECRET": os.getenv("GATE_SECRET", ""),
      
        # Bitget (新增)
        "BITGET_API_KEY": os.getenv("BITGET_API_KEY", ""),
        "BITGET_SECRET": os.getenv("BITGET_SECRET", ""),
        "BITGET_PASSPHRASE": os.getenv("BITGET_PASSPHRASE", ""),
      
        # KuCoin (新增)
        "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
        "KUCOIN_SECRET": os.getenv("KUCOIN_SECRET", ""),
        "KUCOIN_PASSPHRASE": os.getenv("KUCOIN_PASSPHRASE", ""),
      
        # Telegram - 通用
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
       
        # Telegram - 交易所專用 (新增支援更多交易所的 Telegram)
        "TELEGRAM_BOT_TOKEN_BINANCE": os.getenv("TELEGRAM_BOT_TOKEN_BINANCE", ""),
        "TELEGRAM_CHAT_ID_BINANCE": os.getenv("TELEGRAM_CHAT_ID_BINANCE", ""),
       
        "TELEGRAM_BOT_TOKEN_OKX": os.getenv("TELEGRAM_BOT_TOKEN_OKX", ""),
        "TELEGRAM_CHAT_ID_OKX": os.getenv("TELEGRAM_CHAT_ID_OKX", ""),
       
        "TELEGRAM_BOT_TOKEN_BYBIT": os.getenv("TELEGRAM_BOT_TOKEN_BYBIT", ""),
        "TELEGRAM_CHAT_ID_BYBIT": os.getenv("TELEGRAM_CHAT_ID_BYBIT", ""),
       
        "TELEGRAM_BOT_TOKEN_GATE": os.getenv("TELEGRAM_BOT_TOKEN_GATE", ""),
        "TELEGRAM_CHAT_ID_GATE": os.getenv("TELEGRAM_CHAT_ID_GATE", ""),
       
        "TELEGRAM_BOT_TOKEN_BITGET": os.getenv("TELEGRAM_BOT_TOKEN_BITGET", ""),
        "TELEGRAM_CHAT_ID_BITGET": os.getenv("TELEGRAM_CHAT_ID_BITGET", ""),
       
        "TELEGRAM_BOT_TOKEN_KUCOIN": os.getenv("TELEGRAM_BOT_TOKEN_KUCOIN", ""),
        "TELEGRAM_CHAT_ID_KUCOIN": os.getenv("TELEGRAM_CHAT_ID_KUCOIN", ""),
    }

CONFIG = get_config()
signal_history = []

# ==================== CCXT 交易所初始化 ====================
def init_exchange(exchange_id):
    """
    初始化 CCXT 交易所實例
   
    環境變數控制：
    - USE_SANDBOX=true → 啟用測試網（免費測試）
    - USE_SANDBOX=false → 使用正式環境（真實交易）
   
    Returns:
        ccxt.Exchange 實例或 None
    """
    use_sandbox = os.getenv('USE_SANDBOX', 'false').lower() == 'true'
   
    try:
        if exchange_id == 'binance':
            if not CONFIG["BINANCE_API_KEY"]:
                return None
            exchange = ccxt.binance({
                'apiKey': CONFIG["BINANCE_API_KEY"],
                'secret': CONFIG["BINANCE_SECRET"],
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                }
            })
           
            # 沙盒模式
            if use_sandbox:
                exchange.urls['api'] = {
                    'public': 'https://testnet.binancefuture.com/fapi/v1',
                    'private': 'https://testnet.binancefuture.com/fapi/v1'
                }
                log(f"🧪 Binance 測試網模式已啟用")
       
        elif exchange_id == 'okx':
            if not CONFIG["OKX_API_KEY"]:
                return None
            exchange = ccxt.okx({
                'apiKey': CONFIG["OKX_API_KEY"],
                'secret': CONFIG["OKX_SECRET"],
                'password': CONFIG["OKX_PASSPHRASE"],
                'options': {
                    'defaultType': 'swap',
                }
            })
           
            if use_sandbox:
                exchange.set_sandbox_mode(True)
                log(f"🧪 OKX 測試網模式已啟用")
       
        elif exchange_id == 'bybit':
            if not CONFIG["BYBIT_API_KEY"]:
                return None
            exchange = ccxt.bybit({
                'apiKey': CONFIG["BYBIT_API_KEY"],
                'secret': CONFIG["BYBIT_SECRET"],
                'options': {
                    'defaultType': 'linear',
                }
            })
           
            if use_sandbox:
                exchange.set_sandbox_mode(True)
                log(f"🧪 Bybit 測試網模式已啟用")
       
        elif exchange_id == 'gate':
            if not CONFIG["GATE_API_KEY"]:
                return None
            exchange = ccxt.gate({
                'apiKey': CONFIG["GATE_API_KEY"],
                'secret': CONFIG["GATE_SECRET"],
                'options': {
                    'defaultType': 'swap',
                }
            })
           
            if use_sandbox:
                exchange.set_sandbox_mode(True)
                log(f"🧪 Gate.io 測試網模式已啟用")
       
        elif exchange_id == 'bitget':
            if not CONFIG["BITGET_API_KEY"]:
                return None
            exchange = ccxt.bitget({
                'apiKey': CONFIG["BITGET_API_KEY"],
                'secret': CONFIG["BITGET_SECRET"],
                'password': CONFIG["BITGET_PASSPHRASE"],
                'options': {
                    'defaultType': 'swap',
                }
            })
           
            if use_sandbox:
                exchange.set_sandbox_mode(True)
                log(f"🧪 Bitget 測試網模式已啟用")
       
        elif exchange_id == 'kucoin':
            if not CONFIG["KUCOIN_API_KEY"]:
                return None
            exchange = ccxt.kucoin({
                'apiKey': CONFIG["KUCOIN_API_KEY"],
                'secret': CONFIG["KUCOIN_SECRET"],
                'password': CONFIG["KUCOIN_PASSPHRASE"],
                'options': {
                    'defaultType': 'future',
                }
            })
           
            if use_sandbox:
                exchange.set_sandbox_mode(True)
                log(f"🧪 KuCoin 測試網模式已啟用")
       
        else:
            return None
       
        mode = "測試網 🧪" if use_sandbox else "正式環境 💰"
        log(f"✅ {exchange_id.upper()} 交易所初始化成功 ({mode})")
        return exchange
       
    except Exception as e:
        log(f"❌ {exchange_id.upper()} 初始化失敗: {e}")
        return None

# 全局交易所實例緩存 (新增支援)
exchanges = {
    'binance': init_exchange('binance'),
    'okx': init_exchange('okx'),
    'bybit': init_exchange('bybit'),
    'gate': init_exchange('gate'),
    'bitget': init_exchange('bitget'),
    'kucoin': init_exchange('kucoin'),
}

# ==================== 持倉管理器 ====================
class PositionManager:
    """多空倉位自動識別管理器"""
   
    def __init__(self):
        self.positions = defaultdict(lambda: {
            "long": None,
            "short": None,
            "mode": None # hedge/oneway
        })
   
    def detect_position_mode(self, pos_key, has_long, has_short):
        """自動檢測持倉模式"""
        position = self.positions[pos_key]
       
        if position["mode"] is None:
            if has_long and has_short:
                position["mode"] = "hedge"
                log(f"🔍 檢測到雙向持倉: {pos_key}")
            else:
                position["mode"] = "oneway"
                log(f"🔍 檢測到單向持倉: {pos_key}")
       
        if position["mode"] == "oneway" and has_long and has_short:
            position["mode"] = "hedge"
            log(f"🔄 切換為雙向持倉: {pos_key}")
       
        return position["mode"]
   
    def parse_action(self, action, pos_key):
        """
        智能解析操作意圖
       
        Returns:
            (side, reduce_only, pos_type)
            - side: "buy"/"sell"
            - reduce_only: True/False
            - pos_type: "long"/"short"
        """
        position = self.positions[pos_key]
        current_mode = position.get("mode", "oneway")
       
        # ========== 明確指定方向 ==========
        if "_" in action:
            parts = action.split("_")
            action_type = parts[0] # buy/sell/add
            pos_type = parts[1] if len(parts) > 1 else None
           
            if action_type == "buy" and pos_type == "long":
                return "buy", False, "long" # 開多
            elif action_type == "sell" and pos_type == "long":
                return "sell", True, "long" # 平多
            elif action_type == "sell" and pos_type == "short":
                return "sell", False, "short" # 開空
            elif action_type == "buy" and pos_type == "short":
                return "buy", True, "short" # 平空
            elif action_type == "add" and pos_type == "long":
                return "buy", False, "long" # 加多
            elif action_type == "add" and pos_type == "short":
                return "sell", False, "short" # 加空
       
        # ========== 自動推斷 ==========
        elif action == "buy":
            if position["short"] and position["short"]["qty"] > 0:
                return "buy", True, "short" # 先平空
            else:
                return "buy", False, "long" # 開多
       
        elif action == "sell":
            if position["long"] and position["long"]["qty"] > 0:
                return "sell", True, "long" # 先平多
            else:
                return "sell", False, "short" # 開空
       
        elif action == "add":
            if position["long"] and position["long"]["qty"] > 0:
                return "buy", False, "long"
            elif position["short"] and position["short"]["qty"] > 0:
                return "sell", False, "short"
            else:
                raise ValueError("❌ 無持倉時無法加倉")
       
        raise ValueError(f"❌ 無法識別的 action: {action}")
   
    def update_position(self, pos_key, pos_type, quantity, price, stop_loss, operation, partial=False):
        """更新持倉狀態"""
        position = self.positions[pos_key]
       
        if operation in ["open", "add"]:
            if position[pos_type] is None or position[pos_type]["qty"] == 0:
                position[pos_type] = {
                    "qty": quantity,
                    "avg_price": price,
                    "stop_loss": stop_loss,
                    "entry_time": datetime.now().isoformat()
                }
                log(f"✅ 新開{pos_type}倉: {quantity} @ {price}")
            else:
                old_qty = position[pos_type]["qty"]
                old_price = position[pos_type]["avg_price"]
               
                new_qty = old_qty + quantity
                new_avg_price = (old_qty * old_price + quantity * price) / new_qty
               
                position[pos_type]["qty"] = new_qty
                position[pos_type]["avg_price"] = new_avg_price
                if stop_loss:
                    position[pos_type]["stop_loss"] = stop_loss
               
                log(f"➕ 加{pos_type}倉: {old_qty} → {new_qty}")
           
            has_long = position["long"] and position["long"]["qty"] > 0
            has_short = position["short"] and position["short"]["qty"] > 0
            self.detect_position_mode(pos_key, has_long, has_short)
       
        elif operation == "close":
            if position[pos_type] is None or position[pos_type]["qty"] == 0:
                raise ValueError(f"❌ 嘗試平倉但無 {pos_type} 倉位")
           
            current_qty = position[pos_type]["qty"]
           
            if partial and quantity < current_qty:
                position[pos_type]["qty"] -= quantity
                log(f"📉 部分平{pos_type}倉: {quantity}/{current_qty}")
            else:
                position[pos_type] = None
                log(f"🔴 全部平{pos_type}倉: {quantity}")
   
    def get_position(self, pos_key):
        return self.positions[pos_key]
   
    def get_all_positions(self):
        return {k: v for k, v in self.positions.items() if v["long"] or v["short"]}

position_manager = PositionManager()

# ==================== 工具函數 ====================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def is_duplicate(data):
    """防重複信號（10秒窗口）"""
    signal_id = (
        f"{data.get('action')}_"
        f"{data.get('symbol')}_"
        f"{data.get('exchange')}_"
        f"{data.get('qty')}_"
        f"{data.get('strategy', 'default')}_"
        f"{int(time.time()) // 10}"
    )
   
    if signal_id in signal_history:
        return True
   
    signal_history.append(signal_id)
    if len(signal_history) > 200:
        signal_history.pop(0)
    return False

def send_telegram(message, exchange=None):
    """發送 Telegram 通知"""
    token_key = f"TELEGRAM_BOT_TOKEN_{exchange.upper()}" if exchange else "TELEGRAM_BOT_TOKEN"
    chat_id_key = f"TELEGRAM_CHAT_ID_{exchange.upper()}" if exchange else "TELEGRAM_CHAT_ID"
    
    token = CONFIG.get(token_key) or CONFIG["TELEGRAM_BOT_TOKEN"]
    chat_id = CONFIG.get(chat_id_key) or CONFIG["TELEGRAM_CHAT_ID"]
    
    if not token or not chat_id:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"⚠️ Telegram 異常: {e}")
        return False

# ==================== CCXT 統一交易函數 ====================
def ccxt_trade(exchange_id, side, symbol, quantity, reduce_only=False,
               stop_loss=None, leverage=None):
    """
    CCXT 統一交易接口
   
    Args:
        exchange_id: 'binance'/'okx'/'bybit'/'gate'/'bitget'/'kucoin'
        side: 'buy'/'sell'
        symbol: 'BTC/USDT:USDT' (CCXT 統一格式)
        quantity: 數量
        reduce_only: 是否僅平倉
        stop_loss: 止損價格
        leverage: 槓桿倍數
    """
    try:
        exchange = exchanges.get(exchange_id)
        if not exchange:
            return {"success": False, "error": f"{exchange_id} 未配置"}
       
        # 設置槓桿
        if leverage:
            try:
                exchange.set_leverage(leverage, symbol)
                log(f"⚡ 槓桿設置: {leverage}x")
            except Exception as e:
                log(f"⚠️ 槓桿設置失敗: {e}")
       
        # 構建訂單參數
        params = {}
       
        # 交易所特定參數
        if exchange_id == 'binance':
            pos_key = f"{exchange_id}_{symbol}"
            position = position_manager.get_position(pos_key)
           
            if position.get("mode") == "hedge":
                if side == "buy":
                    params['positionSide'] = 'SHORT' if reduce_only else 'LONG'
                else:
                    params['positionSide'] = 'LONG' if reduce_only else 'SHORT'
            else:
                params['positionSide'] = 'BOTH'
       
        elif exchange_id == 'okx':
            params['tdMode'] = 'cross'
            if reduce_only:
                params['reduceOnly'] = True
       
        elif exchange_id == 'bybit':
            if reduce_only:
                params['reduce_only'] = True
       
        elif exchange_id == 'gate':
            params['time_in_force'] = 'ioc'  # Gate 常用即時成交
            if reduce_only:
                params['reduce_only'] = True
       
        elif exchange_id == 'bitget':
            params['marginMode'] = 'cross'
            if reduce_only:
                params['reduceOnly'] = True
            # Bitget 支持 hedge/one-way，類似 Binance
            pos_key = f"{exchange_id}_{symbol}"
            position = position_manager.get_position(pos_key)
            if position.get("mode") == "hedge":
                params['side'] = f"{side}_{'short' if reduce_only and side == 'buy' else 'long' if side == 'buy' else 'short'}"
       
        elif exchange_id == 'kucoin':
            params['marginMode'] = 'cross'
            if reduce_only:
                params['closeOrder'] = True  # KuCoin 的 reduce_only 等價
       
        # 通用 reduce_only (如果未在上面處理)
        if reduce_only and exchange_id not in ['okx', 'bybit', 'gate', 'bitget', 'kucoin']:
            params['reduceOnly'] = True
       
        # 執行市價單
        order = exchange.create_order(
            symbol=symbol,
            type='market',
            side=side,
            amount=quantity,
            params=params
        )
       
        avg_price = float(order.get('average', 0) or order.get('price', 0))
        log(f"✅ {exchange_id.upper()} {side.upper()}: {symbol} x {quantity} @ {avg_price}")
       
        # 設置止損（開倉時）
        if stop_loss and not reduce_only:
            try:
                stop_side = 'sell' if side == 'buy' else 'buy'
                stop_params = params.copy()
                stop_params['stopPrice'] = stop_loss
               
                exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=stop_side,
                    amount=quantity,
                    params=stop_params
                )
                log(f"🛡️ 止損已設置: {stop_loss}")
            except Exception as e:
                log(f"⚠️ 止損設置失敗: {e}")
       
        return {
            "success": True,
            "price": avg_price,
            "order_id": order.get('id'),
            "data": order
        }
       
    except ccxt.InsufficientFunds as e:
        log(f"❌ 餘額不足: {e}")
        return {"success": False, "error": "餘額不足"}
    except ccxt.InvalidOrder as e:
        log(f"❌ 訂單無效: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        log(f"❌ {exchange_id.upper()} 交易失敗: {e}")
        return {"success": False, "error": str(e)}

# ==================== 主路由 ====================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        log(f"📩 收到信號: {json.dumps(data, ensure_ascii=False)}")
      
        if is_duplicate(data):
            log("⚠️ 重複信號已忽略")
            return jsonify({"message": "Duplicate ignored"}), 200
      
        # 解析參數
        action = data.get('action', 'buy')
        symbol_raw = data.get('symbol', 'BTCUSDT')
        quantity = float(data.get('qty', 0.001))
        exchange_id = data.get('exchange', 'binance').lower()
        stop_loss = float(data.get('stop_loss', 0)) if data.get('stop_loss') else None
        leverage = int(data.get('leverage', 1)) if data.get('leverage') else None
        strategy_name = data.get('strategy', 'default')
        partial = data.get('partial', False)
      
        # 轉換為 CCXT 格式
        symbol = symbol_raw.replace('USDT', '/USDT:USDT').upper()
       
        pos_key = f"{exchange_id}_{symbol}_{strategy_name}"
      
        # 解析交易意圖
        try:
            side, reduce_only, pos_type = position_manager.parse_action(action, pos_key)
        except ValueError as e:
            log(str(e))
            return jsonify({"error": str(e)}), 400
       
        operation = "close" if reduce_only else ("add" if "add" in action else "open")
        log(f"🔍 解析: {side.upper()} ({operation}) - {pos_type}倉")
      
        # 執行交易
        result = ccxt_trade(
            exchange_id=exchange_id,
            side=side,
            symbol=symbol,
            quantity=quantity,
            reduce_only=reduce_only,
            stop_loss=stop_loss,
            leverage=leverage
        )
      
        # 更新持倉
        if result and result.get('success'):
            avg_price = float(result.get('price', 0))
           
            try:
                position_manager.update_position(
                    pos_key, pos_type, quantity, avg_price,
                    stop_loss, operation, partial
                )
            except ValueError as e:
                log(f"⚠️ 持倉更新警告: {e}")
          
            # Telegram 通知
            emoji_map = {
                "open": "🟢" if pos_type == "long" else "🔴",
                "add": "🔵" if pos_type == "long" else "🟠",
                "close": "⚪"
            }
            operation_name = {"open": "開倉", "add": "加倉", "close": "平倉" if not partial else "減倉"}
           
            position = position_manager.get_position(pos_key)
            current_qty = position[pos_type]["qty"] if position[pos_type] else 0
           
            msg = f"""
{emoji_map[operation]} <b>{operation_name[operation]} ({pos_type.upper()})</b>
━━━━━━━━━━━━━━━━
🏦 交易所: <b>{exchange_id.upper()}</b>
💰 交易對: <b>{symbol_raw}</b>
📦 數量: <b>{quantity}</b>
💵 價格: <b>{avg_price if avg_price else 'N/A'}</b>
📊 持倉模式: <b>{position.get('mode', 'unknown').upper()}</b>
🎯 止損: <b>{stop_loss if stop_loss else '未設置'}</b>
⚡ 槓桿: <b>{leverage}x</b>
📈 當前{pos_type}倉: <b>{current_qty}</b>
📋 策略: <b>{strategy_name}</b>
━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            send_telegram(msg, exchange=exchange_id)
      
        return jsonify(result), 200 if result.get('success') else 500
      
    except Exception as e:
        log(f"❌ 處理錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/positions', methods=['GET'])
def get_positions():
    """查詢所有持倉"""
    return jsonify(position_manager.get_all_positions()), 200

@app.route('/health', methods=['GET'])
def health():
    """健康檢查"""
    use_sandbox = os.getenv('USE_SANDBOX', 'false').lower() == 'true'
   
    return jsonify({
        "status": "running",
        "mode": "Testnet 🧪" if use_sandbox else "Production 💰",
        "time": datetime.now().isoformat(),
        "ccxt_version": ccxt.__version__,
        "exchanges": {
            "binance": exchanges['binance'] is not None,
            "okx": exchanges['okx'] is not None,
            "bybit": exchanges['bybit'] is not None,
            "gate": exchanges['gate'] is not None,
            "bitget": exchanges['bitget'] is not None,
            "kucoin": exchanges['kucoin'] is not None,
        },
        "positions": len(position_manager.get_all_positions())
    }), 200

@app.route('/', methods=['GET'])
def home():
    """首頁"""
    use_sandbox = os.getenv('USE_SANDBOX', 'false').lower() == 'true'
    mode_badge = "🧪 測試網模式" if use_sandbox else "💰 正式交易模式"
   
    status = []
    for ex_id in ['binance', 'okx', 'bybit', 'gate', 'bitget', 'kucoin']:
        if exchanges[ex_id]:
            status.append(f"✅ {ex_id.upper()}")
        else:
            status.append(f"❌ {ex_id.upper()}")
   
    return f"""
    <h1>🤖 CCXT 多交易所期貨機器人 v3.1 (支援 Gate/Bitget/KuCoin)</h1>
    <p>狀態: <span style="color:green">運行中</span></p>
    <p>當前模式: <b style="color:{'orange' if use_sandbox else 'red'}">{mode_badge}</b></p>
    <p>CCXT 版本: <b>{ccxt.__version__}</b></p>
  
    <h3>🧪 測試網說明:</h3>
    <ul>
        <li><b>測試網（Testnet/Sandbox）</b>：使用虛擬資金，零風險，適合開發測試</li>
        <li><b>正式環境（Production）</b>：使用真實資金，實際交易</li>
        <li>切換方式：設置環境變數 <code>USE_SANDBOX=true</code> 或 <code>false</code></li>
    </ul>
   
    <h3>📋 測試網註冊地址:</h3>
    <ul>
        <li>Binance Futures: <a href="https://testnet.binancefuture.com" target="_blank">testnet.binancefuture.com</a></li>
        <li>OKX Demo: <a href="https://www.okx.com/demo-trading" target="_blank">okx.com/demo-trading</a></li>
        <li>Bybit Testnet: <a href="https://testnet.bybit.com" target="_blank">testnet.bybit.com</a></li>
        <li>Gate.io Testnet: <a href="https://www.gate.io/testnet" target="_blank">gate.io/testnet</a></li>
        <li>Bitget Testnet: <a href="https://simulation.bitget.com" target="_blank">simulation.bitget.com</a></li>
        <li>KuCoin Sandbox: <a href="https://sandbox.kucoin.com" target="_blank">sandbox.kucoin.com</a></li>
    </ul>
  
    <h3>✨ 核心優勢:</h3>
    <ul>
        <li>✅ 統一 API，支持 100+ 交易所（新增 Gate/Bitget/KuCoin）</li>
        <li>✅ 一鍵切換測試網/正式環境</li>
        <li>✅ 自動適配交易所差異</li>
        <li>✅ 社區維護，自動更新</li>
        <li>✅ 多空倉智能管理</li>
    </ul>
  
    <h3>🏦 支持的交易所:</h3>
    <ul>
        {''.join([f'<li>{s}</li>' for s in status])}
    </ul>
  
    <h3>📡 API 端點:</h3>
    <ul>
        <li><code>POST /webhook</code> - 接收交易信號</li>
        <li><code>GET /positions</code> - 查詢持倉</li>
        <li><code>GET /health</code> - 健康檢查</li>
    </ul>
  
    <h3>📖 Pine Script 示例:</h3>
    <pre>
{{
  "action": "buy_long",
  "symbol": "BTCUSDT",
  "qty": "0.1",
  "exchange": "gate",  // 可以改成 bitget/kucoin 等
  "leverage": 10,
  "stop_loss": 65000,
  "strategy": "my_strategy"
}}
    </pre>
   
    <h3>🔧 環境變數配置:</h3>
    <pre>
# 測試網模式（推薦先測試）
export USE_SANDBOX=true
export GATE_API_KEY="testnet_key"  # 新增交易所範例
# ... 其他 Key
    </pre>
    """

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    use_sandbox = os.getenv('USE_SANDBOX', 'false').lower() == 'true'
   
    log(f"🚀 CCXT 交易機器人啟動於端口 {port}")
    log(f"📦 CCXT 版本: {ccxt.__version__}")
    log(f"🎯 運行模式: {'🧪 測試網（虛擬資金）' if use_sandbox else '💰 正式環境（真實資金）'}")
   
    if use_sandbox:
        log(f"⚠️ 當前為測試網模式，所有交易使用虛擬資金")
        log(f"📋 測試網註冊:")
        log(f" - Binance: https://testnet.binancefuture.com")
        log(f" - OKX: https://www.okx.com/demo-trading")
        log(f" - Bybit: https://testnet.bybit.com")
        log(f" - Gate.io: https://www.gate.io/testnet")
        log(f" - Bitget: https://simulation.bitget.com")
        log(f" - KuCoin: https://sandbox.kucoin.com")
    else:
        log(f"💰 當前為正式交易模式，請確認 API Key 正確！")
   
    log(f"🏦 已配置交易所:")
    for ex_id, ex in exchanges.items():
        log(f" {'✅' if ex else '❌'} {ex_id.upper()}")
   
    app.run(host='0.0.0.0', port=port)
