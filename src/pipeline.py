import os
import json
import urllib.request
import urllib.parse
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def init_directories():
    """Create local directories if they don't exist."""
    os.makedirs(DATA_DIR_COT, exist_ok=True)
    os.makedirs(DATA_DIR_PRICES, exist_ok=True)

def fetch_cot_data(market_name, config, use_combined=False):
    """Fetch all available COT history for all participant categories from Socrata API."""
    # Standard Socrata IDs for TFF reports:
    # gpe5-46if (Futures Only), yw9f-hn96 (Combined Futures & Options)
    dataset_id = "yw9f-hn96" if use_combined else "gpe5-46if"
    cftc_code = config["cftc_code"]
    report_type = config["report_type"]
    suffix = "_combined" if use_combined else "_futures"
    
    # Define columns to fetch (all configured markets use TFF report type)
    columns = [
        "report_date_as_yyyy_mm_dd",
        "open_interest_all",
        "lev_money_positions_long",
        "lev_money_positions_short",
        "lev_money_positions_spread",
        "asset_mgr_positions_long",
        "asset_mgr_positions_short",
        "asset_mgr_positions_spread",
        "dealer_positions_long_all",
        "dealer_positions_short_all",
        "dealer_positions_spread_all",
        "nonrept_positions_long_all",
        "nonrept_positions_short_all"
    ]
    
    # Build query
    select_clause = ", ".join(columns)
    query = f"SELECT {select_clause} WHERE cftc_contract_market_code = '{cftc_code}' ORDER BY report_date_as_yyyy_mm_dd DESC LIMIT 2000"
    url = f"https://publicreporting.cftc.gov/resource/{dataset_id}.json?$query={urllib.parse.quote(query)}"
    
    logging.info(f"Загрузка COT данных ({suffix[1:]}) {market_name} из URL: {url[:100]}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                raise ValueError(f"Получен пустой ответ для {market_name}")
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Standardize date column
            df["report_date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.date
            df["open_interest"] = pd.to_numeric(df["open_interest_all"], errors="coerce")
            
            # Convert numeric columns
            numeric_cols = [c for c in columns if c not in ["report_date_as_yyyy_mm_dd", "open_interest_all"]]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                else:
                    df[col] = 0.0  # Fallback for missing columns
            
            # Drop unnecessary columns
            keep_cols = ["report_date", "open_interest"] + numeric_cols
            df = df[[c for c in keep_cols if c in df.columns]]
            
            # Save to CSV
            filepath = os.path.join(DATA_DIR_COT, f"{market_name}{suffix}.csv")
            df.to_csv(filepath, index=False, encoding='utf-8')
            logging.info(f"Успешно сохранен файл COT {market_name}{suffix} ({len(df)} недель) в {filepath}")
            return df
    except Exception as e:
        logging.error(f"Ошибка при загрузке COT {market_name}{suffix}: {e}")
        raise

def fetch_price_data(market_name, config):
    """Fetch daily historical price series from yfinance."""
    ticker = config["ticker"]
    logging.info(f"Загрузка цен для {market_name} (тикер: {ticker}) через yfinance...")
    
    try:
        ticker_df = yf.download(ticker, start="2006-01-01", progress=False)
        if ticker_df.empty:
            raise ValueError(f"yfinance вернул пустой DataFrame для {ticker}")
            
        ticker_df = ticker_df.reset_index()
        if isinstance(ticker_df.columns, pd.MultiIndex):
            ticker_df.columns = [col[0] for col in ticker_df.columns]
            
        ticker_df["Date"] = pd.to_datetime(ticker_df["Date"]).dt.date
        ticker_df = ticker_df.rename(columns={"Date": "date", "Close": "close", "Open": "open", "High": "high", "Low": "low", "Volume": "volume"})
        ticker_df = ticker_df[["date", "close"]]
        
        # Save to CSV
        filepath = os.path.join(DATA_DIR_PRICES, f"{market_name}.csv")
        ticker_df.to_csv(filepath, index=False, encoding='utf-8')
        logging.info(f"Успешно сохранен файл цен {market_name} ({len(ticker_df)} дней) в {filepath}")
        return ticker_df
    except Exception as e:
        logging.error(f"Ошибка при загрузке цен {market_name}: {e}")
        raise

def update_all_data():
    """Run update pipeline for all configured markets (both Futures and Combined)."""
    init_directories()
    results = {}
    
    for market_name, config in MARKETS.items():
        logging.info(f"=== Обновление рынка: {market_name} ===")
        try:
            # Fetch Futures Only
            fetch_cot_data(market_name, config, use_combined=False)
            # Fetch Combined F&O
            fetch_cot_data(market_name, config, use_combined=True)
            # Fetch Price Data
            fetch_price_data(market_name, config)
            results[market_name] = True
        except Exception as e:
            logging.error(f"Ошибка при обновлении {market_name}: {e}")
            results[market_name] = False
            
    return results

def get_data_freshness():
    """Check dates of last updates for all markets."""
    freshness = {}
    for market_name in MARKETS.keys():
        cot_file = os.path.join(DATA_DIR_COT, f"{market_name}_futures.csv")
        price_file = os.path.join(DATA_DIR_PRICES, f"{market_name}.csv")
        
        if os.path.exists(cot_file) and os.path.exists(price_file):
            try:
                cot_df = pd.read_csv(cot_file)
                price_df = pd.read_csv(price_file)
                
                latest_cot = cot_df["report_date"].iloc[0] if len(cot_df) > 0 else "Нет данных"
                latest_price = price_df["date"].iloc[-1] if len(price_df) > 0 else "Нет данных"
                
                latest_cot_dt = datetime.strptime(str(latest_cot), "%Y-%m-%d")
                delay = (datetime.now().date() - latest_cot_dt.date()).days
                
                freshness[market_name] = {
                    "exists": True,
                    "latest_cot": latest_cot,
                    "latest_price": latest_price,
                    "delay_days": delay,
                    "status": "Свежие" if delay <= 14 else "Устарели"
                }
            except Exception as e:
                freshness[market_name] = {
                    "exists": False,
                    "error": str(e),
                    "status": "Ошибка анализа"
                }
        else:
            freshness[market_name] = {
                "exists": False,
                "status": "Отсутствуют"
            }
    return freshness

if __name__ == "__main__":
    init_directories()
    update_all_data()
