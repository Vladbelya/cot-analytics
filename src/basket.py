import json
import logging
import yfinance as yf
from src.config import MARKETS

def get_price_and_news_data(assets_list):
    """Fetches 5-day price action and top news headlines for the given assets and macro proxies."""
    macro_tickers = {
        "^GSPC": "S&P 500 (Market Benchmark)",
        "DX-Y.NYB": "US Dollar Index (DXY)",
        "^TNX": "10-Year Treasury Yield (Rates)",
        "GC=F": "Gold (Inflation/Risk Hedge)"
    }
    
    basket = "=== ЦЕНЫ И НОВОСТИ ===\n"
    all_assets = []
    
    for a in assets_list:
        a_strip = a.strip()
        if not a_strip: continue
        tk = MARKETS.get(a_strip, {}).get("ticker", a_strip)
        all_assets.append((a_strip, tk))
        
    for tk, desc in macro_tickers.items():
        if not any(t == tk for _, t in all_assets):
            all_assets.append((desc, tk))
            
    for asset_name, ticker in all_assets:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="5d")
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[0]
                pct_change = ((last_price - prev_price) / prev_price) * 100
                
                basket += f"[{asset_name} ({ticker})] Текущая цена: {last_price:.2f} | Изменение за 5д: {pct_change:+.2f}%\n"
            
            news = tk.news
            if news:
                basket += f"[{asset_name}] Заголовки:\n"
                for item in news[:3]:
                    basket += f"  - {item.get('title', '')}\n"
        except Exception:
            continue
            
    return basket + "\n"

def get_cot_data(assets_list):
    """Fetches COT data (Z-Scores, Net positions) for the requested assets."""
    from src.analytics import get_market_analysis
    basket = "=== COT ПОЗИЦИОНИРОВАНИЕ (УМНЫЕ И ДУРНЫЕ ДЕНЬГИ) ===\n"
    has_data = False
    
    for asset in assets_list:
        if asset in MARKETS:
            try:
                df_am = get_market_analysis(asset, "Asset Manager")
                df_lf = get_market_analysis(asset, "Leveraged Funds")
                if not df_am.empty and not df_lf.empty:
                    latest_am = df_am.iloc[-1]
                    latest_lf = df_lf.iloc[-1]
                    
                    basket += f"[{asset}]\n"
                    basket += f"  Asset Manager (Институционалы):\n"
                    basket += f"    Net: {latest_am['net']:.0f} (Изменение за неделю: {latest_am['wow_change_net']:.0f})\n"
                    basket += f"    Z-Score: {latest_am['net_zscore_52w']:.2f} std | Режим: {latest_am['regime']}\n"
                    
                    basket += f"  Leveraged Funds (Спекулянты):\n"
                    basket += f"    Net: {latest_lf['net']:.0f} (Изменение за неделю: {latest_lf['wow_change_net']:.0f})\n"
                    basket += f"    Z-Score: {latest_lf['net_zscore_52w']:.2f} std | Режим: {latest_lf['regime']}\n"
                    has_data = True
            except Exception as e:
                logging.error(f"COT basket error for {asset}: {e}")
                
    if not has_data:
        basket += "Нет локальных данных COT.\n"
        
    return basket + "\n"

def get_options_basket_data(assets_list):
    """Fetches Options Data (PCR, Max Pain, Anomalies) for the requested assets."""
    from src.options_data import get_options_summary_for_ticker
    basket = "=== ОПЦИОННЫЙ РЫНОК (ЖАДНОСТЬ, СТРАХ, АНОМАЛИИ) ===\n"
    has_data = False
    
    macro_tickers = {
        "^GSPC": "SPY", # Use SPY ETF for S&P 500 options
        "DX-Y.NYB": "UUP", # Dollar ETF for options
        "^TNX": "TLT", # Treasury ETF for options
        "GC=F": "GLD" # Gold ETF for options
    }
    
    all_assets = []
    for a in assets_list:
        a_strip = a.strip()
        if not a_strip: continue
        tk = MARKETS.get(a_strip, {}).get("ticker", a_strip)
        all_assets.append((a_strip, tk))
        
    for index_tk, etf_proxy in macro_tickers.items():
        if not any(t == index_tk for _, t in all_assets):
            all_assets.append((f"Proxy for {index_tk}", etf_proxy))
            
    for asset_name, ticker in all_assets:
        summary = get_options_summary_for_ticker(ticker)
        if summary:
            basket += f"[{asset_name} ({ticker}) Опционы]\n"
            basket += summary
            has_data = True
            
    if not has_data:
        basket += "Опционные данные недоступны для выбранных активов (или это крипта).\n"
        
    return basket + "\n"

def build_global_data_basket(assets_list, extra_context=""):
    """
    Combines ALL data streams into a single massive 'Basket' string.
    This serves as the raw input for the AI noise filter.
    """
    from src.macro_data import get_macro_summary
    from src.alt_data import get_all_alt_data
    
    basket = "============ ГЛОБАЛЬНАЯ КОРЗИНА ДАННЫХ ============\n\n"
    
    # 1. Macro Data
    basket += "=== ФУНДАМЕНТАЛЬНОЕ МАКРО (ФРС, ИНФЛЯЦИЯ) ===\n"
    try:
        basket += get_macro_summary() + "\n"
    except Exception as e:
        basket += f"Ошибка получения макро: {e}\n\n"
        
    # 2. Alternative Data (ETFs, Insiders)
    basket += "=== АЛЬТЕРНАТИВНЫЕ ПОТОКИ (ETF, ИНСАЙДЕРЫ) ===\n"
    try:
        basket += get_all_alt_data() + "\n"
    except Exception as e:
        basket += f"Ошибка получения альт. данных: {e}\n\n"
        
    # 3. COT Data
    basket += get_cot_data(assets_list)
    
    # 4. Options Data
    basket += get_options_basket_data(assets_list)
    
    # 5. Prices & News
    basket += get_price_and_news_data(assets_list)
    
    # 6. External Context (User URLs, PDFs)
    if extra_context:
        basket += "=== ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ ПОЛЬЗОВАТЕЛЯ (URL/PDF) ===\n"
        basket += extra_context + "\n"
        
    basket += "=====================================================\n"
    return basket
