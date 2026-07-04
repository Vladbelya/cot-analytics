import logging
import pandas as pd
import numpy as np
from src.config import MARKETS

def get_price_and_news_data(assets_list):
    """Fetches 5-day price action and top news headlines for the given assets and macro proxies."""
    import yfinance as yf
    basket = "=== ДИНАМИКА ЦЕН И НОВОСТНЫЕ ЗАГОЛОВКИ ===\n"
    
    # Standard tickers to track
    tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^NDX",
        "EURUSD": "EURUSD=X",
        "Gold": "GC=F",
        "10Y Treasury": "^TNX",
        "DXY": "DX-Y.NYB",
        "Bitcoin": "BTC-USD"
    }
    
    # Add user requested assets if not in default
    for asset in assets_list:
        if asset in MARKETS:
            tickers[asset] = MARKETS[asset]["ticker"]
        elif asset not in tickers:
            tickers[asset] = asset
            
    for name, symbol in tickers.items():
        try:
            ticker_obj = yf.Ticker(symbol)
            hist = ticker_obj.history(period="5d")
            
            if not hist.empty:
                basket += f"[{name} ({symbol})] Последние 5 дней закрытия:\n"
                for dt, row in hist.iterrows():
                    date_str = dt.strftime('%Y-%m-%d')
                    basket += f"  - {date_str}: Close = {row['Close']:.2f} (Vol = {row['Volume']:,.0f})\n"
                
                # Fetch news
                news = ticker_obj.news
                if news:
                    basket += f"[{name}] Заголовки новостей:\n"
                    for item in news[:3]:
                        basket += f"  - {item.get('title', '')}\n"
        except Exception:
            continue
            
    return basket + "\n"

def get_cot_data(assets_list, use_combined=True):
    """Fetches COT data (Z-Scores, Net positions) for the requested assets."""
    from src.analytics import get_market_analysis
    basket = "=== COT ПОЗИЦИОНИРОВАНИЕ (УМНЫЕ И ДУРНЫЕ ДЕНЬГИ - 156w LOOKBACK) ===\n"
    has_data = False
    
    for asset in assets_list:
        if asset in MARKETS:
            try:
                # Try combined first, fallback to futures-only
                try:
                    df_am = get_market_analysis(asset, "Asset Manager", use_combined=use_combined)
                    df_lf = get_market_analysis(asset, "Leveraged Funds", use_combined=use_combined)
                    df_dl = get_market_analysis(asset, "Dealer", use_combined=use_combined)
                    df_rt = get_market_analysis(asset, "Retail", use_combined=use_combined)
                except Exception:
                    df_am = get_market_analysis(asset, "Asset Manager", use_combined=False)
                    df_lf = get_market_analysis(asset, "Leveraged Funds", use_combined=False)
                    df_dl = get_market_analysis(asset, "Dealer", use_combined=False)
                    df_rt = get_market_analysis(asset, "Retail", use_combined=False)
                
                if not df_am.empty and not df_lf.empty:
                    latest_am = df_am.iloc[-1]
                    latest_lf = df_lf.iloc[-1]
                    
                    basket += f"[{asset}]\n"
                    basket += f"  Asset Manager (Институционалы):\n"
                    basket += f"    Net Position: {latest_am['net']:.0f} (Wow Chg: {latest_am['wow_change_net']:+.0f})\n"
                    basket += f"    Net % OI: {latest_am['net_pct_oi']:.2f}% | Index Net % OI (3г): {latest_am['cot_index_net_pct_oi_156w']:.1f}%\n"
                    basket += f"    Z-Score % OI (3г): {latest_am['net_pct_oi_zscore_156w']:.2f} std | Режим: {latest_am['regime']}\n"
                    
                    basket += f"  Leveraged Funds (Хедж-фонды):\n"
                    basket += f"    Net Position: {latest_lf['net']:.0f} (Wow Chg: {latest_lf['wow_change_net']:+.0f})\n"
                    basket += f"    Net % OI: {latest_lf['net_pct_oi']:.2f}% | Index Net % OI (3г): {latest_lf['cot_index_net_pct_oi_156w']:.1f}%\n"
                    basket += f"    Z-Score % OI (3г): {latest_lf['net_pct_oi_zscore_156w']:.2f} std | Режим: {latest_lf['regime']}\n"
                    basket += f"    Spec Ratio (Long/Short): {latest_lf['spec_ratio']:.2f} | Динамика OI-Price: {latest_lf.get('oi_price_sentiment', 'Neutral')}\n"
                    
                    if not df_dl.empty:
                        latest_dl = df_dl.iloc[-1]
                        basket += f"  Dealer Intermediary (Дилеры):\n"
                        basket += f"    Net Position: {latest_dl['net']:.0f} | Index Net % OI (3г): {latest_dl['cot_index_net_pct_oi_156w']:.1f}%\n"
                        basket += f"    Z-Score % OI (3г): {latest_dl['net_pct_oi_zscore_156w']:.2f} std\n"
                        
                    if not df_rt.empty:
                        latest_rt = df_rt.iloc[-1]
                        basket += f"  Retail (Толпа / Ритейл):\n"
                        basket += f"    Net Position: {latest_rt['net']:.0f} | Index Net % OI (3г): {latest_rt['cot_index_net_pct_oi_156w']:.1f}%\n"
                        basket += f"    Z-Score % OI (3г): {latest_rt['net_pct_oi_zscore_156w']:.2f} std\n"
                        
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

def build_global_data_basket(assets_list, extra_context="", use_combined=True):
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
        
    # 3. COT Data (Defaulting to Combined)
    basket += get_cot_data(assets_list, use_combined=use_combined)
    
    # 4. Options Data
    basket += get_options_basket_data(assets_list)
    
    # 5. Options GEX data for Bitcoin (BTC)
    basket += "=== РАСПРЕДЕЛЕНИЕ ГАММЫ (GEX) ДЛЯ BITCOIN (BTC) ===\n"
    try:
        from src.gex_engine import get_aggregate_gex_data, calculate_gex_metrics
        gex_df, spot_price = get_aggregate_gex_data("All Exchanges")
        metrics = calculate_gex_metrics(gex_df, spot_price)
        
        g_flip = metrics.get('gamma_flip')
        c_wall = metrics.get('call_wall')
        p_wall = metrics.get('put_wall')
        v_lev = metrics.get('v')
        s_lev = metrics.get('s')
        p1_val = metrics.get('p1')
        p2_val = metrics.get('p2')
        n1_val = metrics.get('n1')
        n2_val = metrics.get('n2')
        a1_val = metrics.get('a1')
        a2_val = metrics.get('a2')
        
        basket += f"  BTC Spot Price: {spot_price:,.2f}\n"
        basket += f"  Net GEX: {metrics['total_gex']/1_000_000.0:+.2f}M USD\n"
        basket += f"  Gamma Flip: {f'{g_flip:,.2f} USD' if g_flip else 'N/A'}\n"
        basket += f"  Call Wall: {f'{c_wall:,.2f} USD' if c_wall else 'N/A'}\n"
        basket += f"  Put Wall: {f'{p_wall:,.2f} USD' if p_wall else 'N/A'}\n"
        basket += f"  Gamma Resistance (P1, P2): {f'{p1_val:,.2f}' if p1_val else 'N/A'}, {f'{p2_val:,.2f}' if p2_val else 'N/A'} USD\n"
        basket += f"  Volatility Triggers (N1, N2): {f'{n1_val:,.2f}' if n1_val else 'N/A'}, {f'{n2_val:,.2f}' if n2_val else 'N/A'} USD\n"
        basket += f"  Magnets (A1, A2): {f'{a1_val:,.2f}' if a1_val else 'N/A'}, {f'{a2_val:,.2f}' if a2_val else 'N/A'} USD\n"
        basket += f"  Max Volatility (V): {f'{v_lev:,.2f} USD' if v_lev else 'N/A'}\n"
        basket += f"  Max Stability (S): {f'{s_lev:,.2f} USD' if s_lev else 'N/A'}\n"
    except Exception as e:
        basket += f"  Ошибка расчета GEX для BTC: {e}\n"
    basket += "\n"
    
    # 6. Prices & News
    basket += get_price_and_news_data(assets_list)
    
    # 7. External Context (User URLs, PDFs)
    if extra_context:
        basket += "=== ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ ПОЛЬЗОВАТЕЛЯ (URL/PDF) ===\n"
        basket += extra_context + "\n"
        
    basket += "=====================================================\n"
    return basket
