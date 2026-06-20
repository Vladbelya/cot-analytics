import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import datetime



def fetch_etf_anomalies():
    """Checks for volume and price anomalies in major ETFs."""
    etfs = {
        "SPY": "S&P 500 (Общий рынок акций США)",
        "QQQ": "Nasdaq 100 (Технологический сектор)",
        "TLT": "20+ Year Treasuries (Долгосрочные облигации США)",
        "GLD": "Gold (Золото)",
        "IBIT": "Bitcoin ETF (Криптовалюты)",
        "HYG": "High Yield Corporate Bond (Аппетит к риску)"
    }
    
    summary = "АНОМАЛИИ ОБЪЕМОВ В КЛЮЧЕВЫХ ETF:\n"
    found_anomaly = False
    
    for tk, desc in etfs.items():
        try:
            ticker = yf.Ticker(tk)
            hist = ticker.history(period="30d")
            if len(hist) > 10:
                avg_vol = hist['Volume'][:-1].mean()
                latest_vol = hist['Volume'].iloc[-1]
                
                # Check for significant volume spikes
                if avg_vol > 0 and latest_vol > (avg_vol * 1.5): # 50% above average
                    ratio = latest_vol / avg_vol
                    # Was it a green or red day?
                    close_price = hist['Close'].iloc[-1]
                    open_price = hist['Open'].iloc[-1]
                    direction = "ПОКУПКА (Приток)" if close_price > open_price else "ПРОДАЖА (Отток)"
                    
                    summary += f"- {tk} ({desc}): Всплеск объема в {ratio:.1f}x раз выше среднего (Объем: {latest_vol:,.0f}). Доминирование: {direction}.\n"
                    found_anomaly = True
        except:
            continue
            
    if not found_anomaly:
        summary += "Аномальных перетоков объемов (более 1.5x) в ключевых ETF не обнаружено.\n"
        
    return summary

def get_all_alt_data():
    """Aggregates all alternative data sources into a single block."""
    etf = fetch_etf_anomalies()
    return etf
