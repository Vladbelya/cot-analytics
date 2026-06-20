import yfinance as yf
import pandas as pd
import logging
from datetime import datetime

def _calculate_max_pain(calls, puts):
    """Calculates the Max Pain strike price."""
    # Combine all strikes
    strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
    min_pain = float('inf')
    max_pain_strike = 0
    
    for strike in strikes:
        pain = 0
        # Call pain: intrinsic value of calls if expiration is at 'strike'
        # Call expires in the money if strike > call_strike
        for _, c in calls.iterrows():
            if strike > c['strike']:
                pain += (strike - c['strike']) * c['openInterest']
                
        # Put pain: intrinsic value of puts if expiration is at 'strike'
        # Put expires in the money if strike < put_strike
        for _, p in puts.iterrows():
            if strike < p['strike']:
                pain += (p['strike'] - strike) * p['openInterest']
                
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = strike
            
    return max_pain_strike

def _find_anomalies(df, type_name):
    """Finds anomalous option activity where Volume significantly exceeds Open Interest."""
    anomalies = []
    for _, row in df.iterrows():
        vol = row.get('volume', 0)
        oi = row.get('openInterest', 0)
        
        # Check for NaN and basic volume threshold to avoid noise on illiquid strikes
        if pd.isna(vol) or pd.isna(oi):
            continue
            
        if vol > 500 and vol > (oi * 2):
            ratio = vol / max(oi, 1)
            anomalies.append({
                "type": type_name,
                "strike": row['strike'],
                "volume": vol,
                "oi": oi,
                "ratio": ratio,
                "lastPrice": row['lastPrice']
            })
    return anomalies

def get_options_summary_for_ticker(ticker_symbol):
    """Fetches option data for the nearest expiration and calculates key metrics."""
    try:
        tk = yf.Ticker(ticker_symbol)
        expirations = tk.options
        
        if not expirations:
            return None # No options available for this ticker
            
        # Get the closest expiration
        nearest_exp = expirations[0]
        chain = tk.option_chain(nearest_exp)
        
        calls = chain.calls.fillna(0) if not chain.calls.empty else pd.DataFrame(columns=['strike', 'openInterest', 'volume', 'lastPrice'])
        puts = chain.puts.fillna(0) if not chain.puts.empty else pd.DataFrame(columns=['strike', 'openInterest', 'volume', 'lastPrice'])
        
        if calls.empty and puts.empty:
            return None
        
        # 1. Put/Call Ratio (Volume)
        total_call_vol = calls['volume'].sum()
        total_put_vol = puts['volume'].sum()
        pcr = total_put_vol / total_call_vol if total_call_vol > 0 else 0
        
        # 2. Max Pain
        max_pain = _calculate_max_pain(calls, puts)
        
        # 3. Anomalous Activity
        call_anomalies = _find_anomalies(calls, "CALL")
        put_anomalies = _find_anomalies(puts, "PUT")
        all_anomalies = sorted(call_anomalies + put_anomalies, key=lambda x: x['ratio'], reverse=True)
        
        # Current price for context
        hist = tk.history(period="1d")
        current_price = hist['Close'].iloc[-1] if not hist.empty else 0
        
        # Build Summary String
        summary = f"  - Экспирация: {nearest_exp}\n"
        summary += f"  - Текущая цена акции: {current_price:.2f}\n"
        summary += f"  - Max Pain (Максимальная боль): {max_pain:.2f} (Маркет-мейкерам выгодно тянуть цену сюда)\n"
        
        # PCR Interpretation
        pcr_status = "НОРМА"
        if pcr > 1.2:
            pcr_status = "ЭКСТРЕМАЛЬНЫЙ СТРАХ (Жди Шорт-Сквиз)"
        elif pcr < 0.6:
            pcr_status = "ЭКСТРЕМАЛЬНАЯ ЖАДНОСТЬ (Риск обвала)"
            
        summary += f"  - Put/Call Ratio: {pcr:.2f} [{pcr_status}]\n"
        
        if all_anomalies:
            summary += f"  - 🔴 АНОМАЛЬНАЯ АКТИВНОСТЬ (Умные деньги заходят в позу):\n"
            # Show top 5 anomalies
            for anom in all_anomalies[:5]:
                direction = "БЫЧИЙ СИГНАЛ" if anom['type'] == "CALL" else "МЕДВЕЖИЙ СИГНАЛ"
                summary += f"    * {anom['type']} Strike {anom['strike']} | Объем: {anom['volume']:.0f} (в {anom['ratio']:.1f}x раз больше Открытого Интереса) | {direction}\n"
        else:
            summary += f"  - Аномальных объемов (Volume > 2x OI) на ближайшей экспирации не обнаружено.\n"
            
        return summary
    except Exception as e:
        logging.error(f"Error fetching options for {ticker_symbol}: {e}")
        return None
