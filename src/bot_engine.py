import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import requests

# Default state file path
STATE_FILE = "data/paper_trading_state.json"

class RiskManager:
    @staticmethod
    def calculate_position_size(balance, entry_price, stop_loss, risk_pct=0.02):
        """
        Calculates position size based on a fixed percentage of equity risk.
        Risk = Balance * risk_pct.
        Position Size = Risk / |entry_price - stop_loss|
        """
        if entry_price <= 0 or stop_loss <= 0 or entry_price == stop_loss:
            return 0.0
        
        risk_amount = balance * risk_pct
        sl_distance = abs(entry_price - stop_loss)
        size = risk_amount / sl_distance
        return float(size)

class BacktestEngine:
    @staticmethod
    def run_backtest(df, asset_name, strategy_name, start_date="2023-01-01"):
        """
        Simulates trading on historical weekly data of an asset.
        Returns:
            summary: dict (net_return, win_rate, profit_factor, max_drawdown, trade_count)
            trades: list of closed trades
        """
        # Ensure df has datetime index or column
        if "datetime" in df.columns:
            df_hist = df[df["datetime"] >= pd.to_datetime(start_date)].copy().sort_values("datetime")
        else:
            df_hist = df.copy()
            
        if len(df_hist) < 10:
            return {"net_return": 0.0, "win_rate": 0.0, "profit_factor": 1.0, "max_drawdown": 0.0, "trade_count": 0}, []

        # Generate signals Series based on strategy
        signals = BacktestEngine.generate_signals(df_hist, asset_name, strategy_name)
        
        balance = 100000.0
        position = None  # None, "LONG", "SHORT"
        entry_price = 0.0
        entry_time = None
        sl = 0.0
        tp = 0.0
        trades_log = []
        
        prices_close = df_hist["close"].values
        prices_high = df_hist.get("high", df_hist["close"]).values
        prices_low = df_hist.get("low", df_hist["close"]).values
        dates = df_hist["datetime"].tolist() if "datetime" in df_hist.columns else list(range(len(df_hist)))
        
        # Calculate dynamic average weekly true range (ATR) approximation for SL
        close_series = df_hist["close"]
        atr = float(close_series.diff().abs().rolling(12, min_periods=1).median().iloc[-1])
        if atr <= 0 or pd.isna(atr):
            atr = float(close_series.iloc[-1] * 0.03) # Fallback 3% of price
            
        for i in range(len(df_hist)):
            price = prices_close[i]
            high = prices_high[i]
            low = prices_low[i]
            date_val = str(dates[i])
            
            # 1. Check existing position for SL/TP hits on this bar
            if position == "LONG":
                # Check low for Stop Loss
                if low <= sl:
                    pnl = (sl - entry_price) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "LONG",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": sl,
                        "profit_usd": pnl,
                        "type": "SL",
                        "rationale": f"Закрытие по стоп-лоссу на уровне ${sl:,.2f}"
                    })
                    position = None
                # Check high for Take Profit
                elif high >= tp:
                    pnl = (tp - entry_price) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "LONG",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": tp,
                        "profit_usd": pnl,
                        "type": "TP",
                        "rationale": f"Закрытие по тейк-профиту на уровне ${tp:,.2f}"
                    })
                    position = None
                    
            elif position == "SHORT":
                # Check high for Stop Loss
                if high >= sl:
                    pnl = (entry_price - sl) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "SHORT",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": sl,
                        "profit_usd": pnl,
                        "type": "SL",
                        "rationale": f"Закрытие по стоп-лоссу на уровне ${sl:,.2f}"
                    })
                    position = None
                # Check low for Take Profit
                elif low <= tp:
                    pnl = (entry_price - tp) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "SHORT",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": tp,
                        "profit_usd": pnl,
                        "type": "TP",
                        "rationale": f"Закрытие по тейк-профиту на уровне ${tp:,.2f}"
                    })
                    position = None
            
            # 2. Check for new signals
            sig_val = signals[i]  # 1 for LONG, -1 for SHORT, 0 for None
            if sig_val == 1 and position != "LONG":
                # Close existing short
                if position == "SHORT":
                    pnl = (entry_price - price) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "SHORT",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "profit_usd": pnl,
                        "type": "REVERSAL",
                        "rationale": "Разворот позиции: получен противоположный сигнал Long"
                    })
                
                # Open Long
                position = "LONG"
                entry_price = price
                entry_time = date_val
                sl = price - 2.0 * atr
                tp = price + 3.0 * atr # 1.5x Risk/Reward ratio
                position_size = RiskManager.calculate_position_size(balance, price, sl, 0.02)
                
            elif sig_val == -1 and position != "SHORT":
                # Close existing long
                if position == "LONG":
                    pnl = (price - entry_price) * position_size
                    balance += pnl
                    trades_log.append({
                        "symbol": asset_name,
                        "direction": "LONG",
                        "entry_time": str(entry_time),
                        "exit_time": date_val,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "profit_usd": pnl,
                        "type": "REVERSAL",
                        "rationale": "Разворот позиции: получен противоположный сигнал Short"
                    })
                
                # Open Short
                position = "SHORT"
                entry_price = price
                entry_time = date_val
                sl = price + 2.0 * atr
                tp = price - 3.0 * atr
                position_size = RiskManager.calculate_position_size(balance, price, sl, 0.02)
                
        # Final Stats calculations
        net_return = ((balance - 100000.0) / 100000.0) * 100.0
        
        profits = [t["profit_usd"] for t in trades_log if t["profit_usd"] > 0]
        losses = [t["profit_usd"] for t in trades_log if t["profit_usd"] < 0]
        
        win_rate = (len(profits) / len(trades_log) * 100.0) if trades_log else 0.0
        
        sum_prof = sum(profits)
        sum_loss = abs(sum(losses))
        profit_factor = (sum_prof / sum_loss) if sum_loss > 0 else (sum_prof if sum_prof > 0 else 1.0)
        
        # Simple Max Drawdown calculation
        peak = 100000.0
        current_bal = 100000.0
        max_dd = 0.0
        for t in trades_log:
            current_bal += t["profit_usd"]
            if current_bal > peak:
                peak = current_bal
            dd = (peak - current_bal) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
                
        summary = {
            "net_return": net_return,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "trade_count": len(trades_log)
        }
        
        return summary, trades_log

    @staticmethod
    def generate_signals(df, asset_name, strategy_name):
        """
        Generates signal list (+1 Long, -1 Short, 0 Hold) matching the strategy name.
        """
        signals = np.zeros(len(df))
        
        # Determine if asset is BTC to allow GEX strategies
        is_btc = (asset_name == "BTC")
        
        if is_btc:
            if strategy_name == "Strategy A (COT Trend)":
                # Z-Score boundaries
                z = df.get("net_pct_oi_zscore_52w", np.zeros(len(df)))
                for i in range(1, len(df)):
                    if z.iloc[i] > 1.5:
                        signals[i] = 1
                    elif z.iloc[i] < -1.5:
                        signals[i] = -1
                        
            elif strategy_name == "Strategy B (GEX Walls)":
                # Reversion from walls
                # Simulated Gamma Flip and Walls historically
                close = df["close"].values
                for i in range(1, len(df)):
                    g_flip = close[i-1] * 0.98
                    if close[i] > g_flip:
                        if close[i] < close[i-1] * 0.96:
                            signals[i] = 1
                        elif close[i] > close[i-1] * 1.04:
                            signals[i] = -1
                            
            elif strategy_name == "Strategy C (Gamma Flip Breakout)":
                close = df["close"].values
                for i in range(1, len(df)):
                    g_flip_prev = close[i-1] * 0.99
                    g_flip_curr = close[i] * 0.99
                    if close[i-1] <= g_flip_prev and close[i] > g_flip_curr:
                        signals[i] = 1
                    elif close[i-1] >= g_flip_prev and close[i] < g_flip_curr:
                        signals[i] = -1
                        
            elif strategy_name == "Strategy D (Synergy COT+GEX)":
                z = df.get("net_pct_oi_zscore_52w", np.zeros(len(df)))
                close = df["close"].values
                for i in range(1, len(df)):
                    g_flip = close[i] * 0.99
                    if z.iloc[i] > 1.0 and close[i] > g_flip:
                        signals[i] = 1
                    elif z.iloc[i] < -1.0 and close[i] < g_flip:
                        signals[i] = -1
        else:
            # Non-BTC assets get COT strategies
            if strategy_name == "Strategy A (COT Trend)":
                z = df.get("net_pct_oi_zscore_52w", np.zeros(len(df)))
                for i in range(1, len(df)):
                    if z.iloc[i] > 1.2:
                        signals[i] = 1
                    elif z.iloc[i] < -1.2:
                        signals[i] = -1
                        
            elif strategy_name == "Strategy B (COT Contrarian)":
                z = df.get("net_pct_oi_zscore_52w", np.zeros(len(df)))
                for i in range(1, len(df)):
                    if z.iloc[i] < -1.8:
                        signals[i] = 1
                    elif z.iloc[i] > 1.8:
                        signals[i] = -1
                        
            elif strategy_name == "Strategy C (COT Crossover)":
                net = df.get("net", np.zeros(len(df)))
                for i in range(1, len(df)):
                    if net.iloc[i-1] < 0 and net.iloc[i] >= 0:
                        signals[i] = 1
                    elif net.iloc[i-1] >= 0 and net.iloc[i] < 0:
                        signals[i] = -1
                        
            elif strategy_name == "Strategy D (COT Momentum)":
                wow = df.get("wow_change_net_pct_oi", np.zeros(len(df)))
                q90 = float(wow.quantile(0.90))
                q10 = float(wow.quantile(0.10))
                for i in range(1, len(df)):
                    if wow.iloc[i] >= q90:
                        signals[i] = 1
                    elif wow.iloc[i] <= q10:
                        signals[i] = -1
                        
        return signals

class BotEngine:
    def __init__(self, data_fetcher_fn):
        self.fetch_market_df = data_fetcher_fn
        self.state = self.load_state()

    def load_state(self):
        """Loads bot trading state from JSON. Initializes if missing."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    return state
            except Exception:
                pass
                
        default_state = {
            "balance": 100000.0,
            "equity": 100000.0,
            "active_positions": {},
            "journal": [],
            "win_rate": 0.0,
            "selected_strategies": {}
        }
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(default_state, f, indent=4)
        return default_state

    def save_state(self):
        """Persists the bot state to JSON."""
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4)

    def get_live_price(self, symbol):
        """Fetches live price using Binance API (crypto) or yfinance (others)."""
        ticker_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT"
        }
        if symbol in ticker_map:
            try:
                r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_map[symbol]}", timeout=5)
                return float(r.json()["price"])
            except Exception:
                pass
                
        yf_tickers = {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "Gold": "GC=F",
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "JPY/USD": "JPY=X",
            "CAD/USD": "CAD=X",
            "AUD/USD": "AUDUSD=X",
            "CHF/USD": "CHF=X",
            "MXN/USD": "MXN=X",
            "Brent": "BZ=F",
            "Natural Gas": "NG=F",
            "S&P 500": "^GSPC",
            "Nasdaq 100": "^NDX",
            "Dow Jones": "^DJI",
            "Russell 2000": "^RUT",
            "US 10Y Yield": "^TNX"
        }
        ticker = yf_tickers.get(symbol, symbol)
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            history = tk.history(period="1d")
            if not history.empty:
                return float(history["Close"].iloc[-1])
        except Exception:
            pass
            
        return 0.0

    def update_positions_and_signals(self, gex_metrics_btc=None):
        """
        Updates active positions and scans for new entry signals.
        """
        active = self.state["active_positions"]
        journal = self.state["journal"]
        balance = self.state["balance"]
        
        symbols = [
            "BTC", "ETH", "Gold", "EUR/USD", "GBP/USD", "JPY/USD",
            "CAD/USD", "AUD/USD", "CHF/USD", "Brent", "Natural Gas",
            "S&P 500", "Nasdaq 100", "Dow Jones", "Russell 2000", "US 10Y Yield"
        ]
        
        closed_symbols = []
        equity = balance
        
        for symbol, pos in list(active.items()):
            live_price = self.get_live_price(symbol)
            if live_price <= 0:
                continue
                
            pos["current_price"] = live_price
            direction = pos["direction"]
            sl = pos["stop_loss"]
            tp = pos["take_profit"]
            entry = pos["entry_price"]
            size = pos["position_size"]
            
            if direction == "LONG":
                unrealized = (live_price - entry) * size
            else:
                unrealized = (entry - live_price) * size
            pos["unrealized_pnl"] = unrealized
            equity += unrealized
            
            if (direction == "LONG" and live_price <= sl) or (direction == "SHORT" and live_price >= sl):
                realized_pnl = (sl - entry) * size if direction == "LONG" else (entry - sl) * size
                balance += realized_pnl
                journal.append({
                    "symbol": symbol,
                    "direction": direction,
                    "entry_time": pos["entry_time"],
                    "exit_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "entry_price": entry,
                    "exit_price": sl,
                    "profit_usd": realized_pnl,
                    "type": "SL",
                    "rationale": f"Закрытие по стоп-лоссу: цена пробила защитный уровень ${sl:,.2f}"
                })
                closed_symbols.append(symbol)
                
            elif (direction == "LONG" and live_price >= tp) or (direction == "SHORT" and live_price <= tp):
                realized_pnl = (tp - entry) * size if direction == "LONG" else (entry - tp) * size
                balance += realized_pnl
                journal.append({
                    "symbol": symbol,
                    "direction": direction,
                    "entry_time": pos["entry_time"],
                    "exit_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "entry_price": entry,
                    "exit_price": tp,
                    "profit_usd": realized_pnl,
                    "type": "TP",
                    "rationale": f"Закрытие по тейк-профиту: цена достигла целевого уровня ${tp:,.2f}"
                })
                closed_symbols.append(symbol)
                
        for sym in closed_symbols:
            if sym in active:
                del active[sym]
                
        self.state["balance"] = balance
        self.state["equity"] = equity
        
        profits = [t["profit_usd"] for t in journal if t["profit_usd"] > 0]
        self.state["win_rate"] = (len(profits) / len(journal) * 100.0) if journal else 0.0
        
        for symbol in symbols:
            if symbol in active:
                continue
                
            try:
                participant = "Leveraged Funds" if symbol in ["BTC", "ETH"] else "Asset Manager"
                df = self.fetch_market_df(symbol, participant, use_combined=True)
            except Exception:
                continue
                
            if df.empty or len(df) < 5:
                continue
                
            selected_strategy = self.state["selected_strategies"].get(symbol, "Strategy A (COT Trend)")
            sig_series = BacktestEngine.generate_signals(df, symbol, selected_strategy)
            latest_sig = sig_series[-1]
            
            if latest_sig != 0:
                live_price = self.get_live_price(symbol)
                if live_price <= 0:
                    continue
                    
                close_series = df["close"]
                atr = float(close_series.diff().abs().rolling(12, min_periods=1).median().iloc[-1])
                if atr <= 0 or pd.isna(atr):
                    atr = float(live_price * 0.03)
                    
                direction = "LONG" if latest_sig == 1 else "SHORT"
                
                if direction == "LONG":
                    sl_price = live_price - 2.0 * atr
                    tp_price = live_price + 3.0 * atr
                else:
                    sl_price = live_price + 2.0 * atr
                    tp_price = live_price - 3.0 * atr
                    
                pos_size = RiskManager.calculate_position_size(balance, live_price, sl_price, 0.02)
                if pos_size <= 0:
                    continue
                    
                latest_row = df.iloc[-1]
                cot_z = latest_row.get("net_pct_oi_zscore_52w", 0.0)
                cot_index = latest_row.get("cot_index_net_pct_oi_52w", 50.0)
                
                gex_detail = ""
                if symbol == "BTC" and gex_metrics_btc is not None:
                    g_flip = gex_metrics_btc.get("gamma_flip", 0.0)
                    g_regime = "Positive Gamma" if live_price > g_flip else "Negative Gamma"
                    gex_detail = f" BTC торгуется в режиме {g_regime} (динамический флип на ${g_flip:,.0f})."
                
                rationale_text = f"Вход {direction} по {symbol} согласно стратегии '{selected_strategy}'."
                rationale_text += f" COT Index: {cot_index:.1f}% (Z-Score: {cot_z:.2f})." + gex_detail
                
                active[symbol] = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "entry_price": live_price,
                    "current_price": live_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "position_size": pos_size,
                    "unrealized_pnl": 0.0,
                    "rationale": rationale_text
                }
                
        self.state["equity"] = self.state["balance"] + sum(p["unrealized_pnl"] for p in active.values())
        self.save_state()
