import datetime
import math
import requests
import pandas as pd
import numpy as np

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_expiry_date_robust(expiry_str, exchange):
    """
    Robustly parses expiry date strings independent of system locale.
    Options on Deribit, Bybit, and OKX all expire at 08:00 UTC.
    """
    try:
        if exchange in ['deribit', 'bybit']:
            # Format: e.g. "31JUL26" or "6JUL26"
            year_str = "20" + expiry_str[-2:]
            month_str = expiry_str[-5:-2].upper()
            day_str = expiry_str[:-5]
            
            day = int(day_str)
            month = MONTH_MAP[month_str]
            year = int(year_str)
            
            return datetime.datetime(year, month, day, 8, 0, 0, tzinfo=datetime.timezone.utc)
        elif exchange == 'okx':
            # Format: e.g. "260706" (YYMMDD)
            year = int("20" + expiry_str[0:2])
            month = int(expiry_str[2:4])
            day = int(expiry_str[4:6])
            
            return datetime.datetime(year, month, day, 8, 0, 0, tzinfo=datetime.timezone.utc)
    except Exception:
        return None

def calculate_gamma_vectorized(spots, strikes, ts, ivs, r=0.0):
    """
    Vectorized Black-Scholes Gamma calculation using numpy.
    Handles boundaries and division-by-zero errors.
    """
    spots = np.maximum(np.array(spots, dtype=float), 1e-9)
    strikes = np.maximum(np.array(strikes, dtype=float), 1e-9)
    ts = np.array(ts, dtype=float)
    ivs = np.maximum(np.array(ivs, dtype=float), 1e-9)
    
    # Valid mask (positive time-to-expiry and implied volatility)
    mask = (ts > 0.0) & (ivs > 1e-4)
    
    gammas = np.zeros_like(spots)
    if not np.any(mask):
        return gammas
        
    s = spots[mask]
    k = strikes[mask]
    t = ts[mask]
    v = ivs[mask]
    
    d1 = (np.log(s / k) + (r + 0.5 * v * v) * t) / (v * np.sqrt(t))
    pdf = np.exp(-0.5 * d1 * d1) / np.sqrt(2.0 * np.pi)
    gammas[mask] = pdf / (s * v * np.sqrt(t))
    
    return gammas

def fetch_deribit_data():
    """
    Fetches real-time BTC option chain from Deribit.
    Returns a normalized DataFrame.
    """
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    results = data.get("result", [])
    if not results:
        return pd.DataFrame()
        
    records = []
    for item in results:
        inst_name = item.get("instrument_name", "")
        # Parse symbol e.g., "BTC-27MAR26-60000-C"
        parts = inst_name.split("-")
        if len(parts) < 4:
            continue
            
        expiry_str = parts[1]
        strike_val = float(parts[2])
        opt_type = parts[3].upper() # C or P
        
        oi = float(item.get("open_interest", 0.0))
        # mark_iv is in percent (e.g. 45.1), we need it as decimal (0.451)
        iv = float(item.get("mark_iv", 0.0)) / 100.0
        
        # Spot index price is usually returned under underlying_price or a similar field.
        # underlying_price here is the forward/underlying price for that option.
        spot = float(item.get("underlying_price", 0.0))
        
        # Price of option in USD: Deribit lists options in BTC, so we multiply by spot
        mark_price_btc = float(item.get("mark_price", 0.0))
        mark_price_usd = mark_price_btc * spot
        
        records.append({
            "exchange": "Deribit",
            "symbol": inst_name,
            "strike": strike_val,
            "expiry_str": expiry_str,
            "option_type": opt_type,
            "open_interest": oi,
            "implied_volatility": iv,
            "spot_price": spot,
            "mark_price_usd": mark_price_usd,
            "contract_size": 1.0
        })
        
    df = pd.DataFrame(records)
    return df

def fetch_bybit_data():
    """
    Fetches real-time BTC option chain from Bybit V5 API.
    Returns a normalized DataFrame.
    """
    url = "https://api.bybit.com/v5/market/tickers?category=option&baseCoin=BTC"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    results = data.get("result", {}).get("list", [])
    if not results:
        return pd.DataFrame()
        
    records = []
    for item in results:
        symbol = item.get("symbol", "")
        # Symbol format: "BTC-24JUL26-54000-C-USDT"
        parts = symbol.split("-")
        if len(parts) < 4:
            continue
            
        expiry_str = parts[1]
        strike_val = float(parts[2])
        opt_type = parts[3].upper()
        
        oi = float(item.get("openInterest", 0.0))
        iv = float(item.get("markIv", 0.0))
        spot = float(item.get("indexPrice", 0.0))
        mark_price_usd = float(item.get("markPrice", 0.0))
        
        records.append({
            "exchange": "Bybit",
            "symbol": symbol,
            "strike": strike_val,
            "expiry_str": expiry_str,
            "option_type": opt_type,
            "open_interest": oi,
            "implied_volatility": iv,
            "spot_price": spot,
            "mark_price_usd": mark_price_usd,
            "contract_size": 1.0
        })
        
    df = pd.DataFrame(records)
    return df

def fetch_okx_data():
    """
    Fetches real-time BTC option chain from OKX API.
    Joins option summary and open interest endpoints.
    """
    # 1. Fetch Option Summary (contains strike, IV, mark price)
    summary_url = "https://www.okx.com/api/v5/public/opt-summary?uly=BTC-USD"
    summary_response = requests.get(summary_url, timeout=10)
    summary_response.raise_for_status()
    summary_data = summary_response.json().get("data", [])
    
    if not summary_data:
        return pd.DataFrame()
        
    # 2. Fetch Open Interest
    oi_url = "https://www.okx.com/api/v5/public/open-interest?instType=OPTION&uly=BTC-USD"
    oi_response = requests.get(oi_url, timeout=10)
    oi_response.raise_for_status()
    oi_data = oi_response.json().get("data", [])
    
    # Put OI in a dict for fast lookup by instId
    oi_dict = {}
    for item in oi_data:
        inst_id = item.get("instId", "")
        parts = inst_id.split("-")
        if len(parts) >= 5:
            # BTC-USD-YYMMDD-STRIKE-TYPE
            expiry = parts[2]
            strike = float(parts[3])
            otype = parts[4].upper()
            oi_dict[(expiry, strike, otype)] = float(item.get("oi", 0.0))
            
    records = []
    for item in summary_data:
        inst_id = item.get("instId", "")
        parts = inst_id.split("-")
        if len(parts) < 5:
            continue
            
        expiry_str = parts[2] # e.g. "260706"
        strike_val = float(parts[3])
        opt_type = parts[4].upper()
        
        # Lookup OI
        oi = oi_dict.get((expiry_str, strike_val, opt_type), 0.0)
        
        iv = float(item.get("markVol", 0.0))
        # OKX forward price
        spot = float(item.get("fwdPx", 0.0))
        
        # OKX mark price is in USD
        mark_price_usd = float(item.get("lever", 0.0)) * spot # OKX lever is option price in BTC
        
        records.append({
            "exchange": "OKX",
            "symbol": inst_id,
            "strike": strike_val,
            "expiry_str": expiry_str,
            "option_type": opt_type,
            "open_interest": oi,
            "implied_volatility": iv,
            "spot_price": spot,
            "mark_price_usd": mark_price_usd,
            "contract_size": 0.01 # OKX BTC option multiplier is 0.01
        })
        
    df = pd.DataFrame(records)
    return df

def get_aggregate_gex_data(selected_exchange="All Exchanges"):
    """
    Fetches, standardizes, calculates Gamma and GEX, and aggregates data.
    """
    dfs = []
    
    # Fetch from enabled exchanges
    if selected_exchange in ["All Exchanges", "Deribit"]:
        try:
            dfs.append(fetch_deribit_data())
        except Exception as e:
            print(f"Error fetching Deribit: {e}")
            
    if selected_exchange in ["All Exchanges", "Bybit"]:
        try:
            dfs.append(fetch_bybit_data())
        except Exception as e:
            print(f"Error fetching Bybit: {e}")
            
    if selected_exchange in ["All Exchanges", "OKX"]:
        try:
            dfs.append(fetch_okx_data())
        except Exception as e:
            print(f"Error fetching OKX: {e}")
            
    # Filter empty dfs
    dfs = [d for d in dfs if not d.empty]
    
    if not dfs:
        return pd.DataFrame(), 0.0
        
    # Combine
    df = pd.concat(dfs, ignore_index=True)
    
    # Calculate robust expirations and time-to-maturity
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    df["expiry_dt"] = df.apply(lambda row: parse_expiry_date_robust(row["expiry_str"], row["exchange"].lower()), axis=1)
    
    # Drop records with invalid expiry dates or expired options
    df = df.dropna(subset=["expiry_dt"]).copy()
    df["t_years"] = df.apply(lambda row: (row["expiry_dt"] - now_utc).total_seconds() / (365.0 * 24.0 * 3600.0), axis=1)
    df = df[df["t_years"] > 0.0].copy()
    
    if df.empty:
        return pd.DataFrame(), 0.0
        
    # Calculate Spot Price (average index price across active feeds)
    spot_price = float(df["spot_price"].median())
    
    # Calculate Option Gamma
    df["gamma"] = calculate_gamma_vectorized(
        spots=df["spot_price"].values,
        strikes=df["strike"].values,
        ts=df["t_years"].values,
        ivs=df["implied_volatility"].values
    )
    
    # GEX Calculation
    # GEX = Gamma * Open Interest * Contract Size * Spot^2 * 0.01 * Direction
    # Call = +1, Put = -1 (Dealer assumed long call / short put in net aggregate models)
    df["direction"] = np.where(df["option_type"] == "C", 1.0, -1.0)
    df["gex"] = df["gamma"] * df["open_interest"] * df["contract_size"] * (df["spot_price"] ** 2) * 0.01 * df["direction"]
    
    return df, spot_price

def calculate_gex_metrics(df, spot_price):
    """
    Computes key GEX levels (Gamma Flip, Walls, Total GEX).
    """
    if df.empty:
        return {
            "total_gex": 0.0,
            "gamma_flip": None,
            "call_wall": None,
            "put_wall": None
        }
        
    total_gex = float(df["gex"].sum())
    
    # Group GEX by strike
    strike_gex = df.groupby("strike")["gex"].sum().reset_index()
    
    # Call Wall: strike with maximum positive GEX
    calls_df = df[df["option_type"] == "C"]
    if not calls_df.empty:
        call_wall = float(calls_df.groupby("strike")["gex"].sum().idxmax())
    else:
        call_wall = None
        
    # Put Wall: strike with maximum negative GEX (minimum value)
    puts_df = df[df["option_type"] == "P"]
    if not puts_df.empty:
        put_wall = float(puts_df.groupby("strike")["gex"].sum().idxmin())
    else:
        put_wall = None
        
    # P1, P2 (Resistances): Top 2 positive GEX strikes
    positive_gex = strike_gex[strike_gex["gex"] > 0].sort_values("gex", ascending=False)
    p_levels = positive_gex["strike"].head(2).tolist()
    p1 = p_levels[0] if len(p_levels) > 0 else None
    p2 = p_levels[1] if len(p_levels) > 1 else None
    
    # N1, N2 (Triggers): Top 2 negative GEX strikes (most negative)
    negative_gex = strike_gex[strike_gex["gex"] < 0].sort_values("gex", ascending=True)
    n_levels = negative_gex["strike"].head(2).tolist()
    n1 = n_levels[0] if len(n_levels) > 0 else None
    n2 = n_levels[1] if len(n_levels) > 1 else None
    
    # A1, A2 (Magnets): Top 2 absolute GEX strikes
    abs_gex = strike_gex.copy()
    abs_gex["abs_val"] = abs_gex["gex"].abs()
    abs_gex = abs_gex.sort_values("abs_val", ascending=False)
    a_levels = abs_gex["strike"].head(2).tolist()
    a1 = a_levels[0] if len(a_levels) > 0 else None
    a2 = a_levels[1] if len(a_levels) > 1 else None
    
    # V (Max Volatility): Lowest strike with negative GEX > 5% of peak negative GEX
    if not negative_gex.empty:
        peak_neg = abs(negative_gex["gex"].iloc[0])
        sig_neg_gex = negative_gex[negative_gex["gex"].abs() >= peak_neg * 0.05]
        v_level = float(sig_neg_gex["strike"].min())
    else:
        v_level = None
        
    # S (Max Stability): Highest strike with positive GEX > 5% of peak positive GEX
    if not positive_gex.empty:
        peak_pos = positive_gex["gex"].iloc[0]
        sig_pos_gex = positive_gex[positive_gex["gex"] >= peak_pos * 0.05]
        s_level = float(sig_pos_gex["strike"].max())
    else:
        s_level = None
        
    # Find Gamma Flip: where net GEX crosses 0
    # We model a range of spots around current spot and find where net GEX changes sign
    spots_range = np.linspace(spot_price * 0.5, spot_price * 1.5, 300)
    net_gex_profile = []
    
    # Pre-evaluate spots matrix to be extremely fast
    strikes = df["strike"].values
    ts = df["t_years"].values
    ivs = df["implied_volatility"].values
    ois = df["open_interest"].values
    sizes = df["contract_size"].values
    dirs = df["direction"].values
    
    for s_val in spots_range:
        gammas = calculate_gamma_vectorized(
            spots=np.full_like(strikes, s_val),
            strikes=strikes,
            ts=ts,
            ivs=ivs
        )
        # Dollar GEX at this simulated spot
        gex_vals = gammas * ois * sizes * (s_val ** 2) * 0.01 * dirs
        net_gex_profile.append(float(np.sum(gex_vals)))
        
    # Find crossing point
    gamma_flip = None
    for i in range(len(net_gex_profile) - 1):
        y1, y2 = net_gex_profile[i], net_gex_profile[i+1]
        x1, x2 = spots_range[i], spots_range[i+1]
        if (y1 <= 0 and y2 > 0) or (y1 >= 0 and y2 < 0):
            # Linear interpolation for precision
            gamma_flip = float(x1 + (0 - y1) * (x2 - x1) / (y2 - y1))
            break
            
    return {
        "total_gex": total_gex,
        "gamma_flip": gamma_flip,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "p1": p1,
        "p2": p2,
        "n1": n1,
        "n2": n2,
        "a1": a1,
        "a2": a2,
        "v": v_level,
        "s": s_level,
        "simulated_spots": list(spots_range),
        "simulated_gex": net_gex_profile
    }

def fetch_btc_price_history_binance(limit=168):
    """
    Fetches price history for BTCUSDT from Binance with a dynamic limit of hours.
    Falls back to yfinance if Binance is unavailable.
    """
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit={limit}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        records = []
        for item in data:
            dt = datetime.datetime.fromtimestamp(item[0]/1000.0, tz=datetime.timezone.utc)
            records.append({
                "datetime": dt,
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            })
        df_hist = pd.DataFrame(records)
        if not df_hist.empty:
            return df_hist
    except Exception:
        pass
        
    # Fallback to yfinance
    try:
        import yfinance as yf
        tk = yf.Ticker("BTC-USD")
        
        # Map hour limit to yfinance period
        if limit <= 24:
            period = "1d"
        elif limit <= 72:
            period = "3d"
        else:
            period = "7d"
            
        df_yf = tk.history(period=period, interval="1h").reset_index()
        if not df_yf.empty:
            df_yf = df_yf.rename(columns={
                "Datetime": "datetime", 
                "Open": "open", 
                "High": "high", 
                "Low": "low", 
                "Close": "close",
                "Volume": "volume"
            })
            return df_yf
    except Exception:
        pass
        
    return pd.DataFrame()


def calculate_historical_gex_heatmap(gex_df, df_hist):
    """
    Simulates historical GEX profiles by recalculating GEX at historical spot prices
    using the current option chain structure.
    """
    if gex_df.empty or df_hist.empty:
        return [], [], np.zeros((0,0)), [], []
        
    # We will use 40 time steps from df_hist to keep it extremely fast
    step = max(1, len(df_hist) // 40)
    df_sampled = df_hist.iloc[::step].copy()
    
    times = df_sampled["datetime"].tolist()
    spots = df_sampled["close"].tolist()
    
    min_spot = min(spots)
    max_spot = max(spots)
    
    # 4% margin below min and above max for dynamic centering
    min_strike = int((min_spot * 0.96) // 100) * 100
    max_strike = int((max_spot * 1.04) // 100) * 100
    strikes_range = list(range(min_strike, max_strike + 100, 100))
    
    opt_strikes = gex_df["strike"].values
    opt_expiries = gex_df["expiry_dt"].values
    opt_ois = gex_df["open_interest"].values
    opt_sizes = gex_df["contract_size"].values
    opt_dirs = gex_df["direction"].values
    opt_ivs = gex_df["implied_volatility"].values
    
    z_matrix = np.zeros((len(strikes_range), len(df_sampled)))
    flips = []
    
    for t_idx, (t_val, s_val) in enumerate(zip(times, spots)):
        t_val_naive = t_val.replace(tzinfo=None) if hasattr(t_val, "tzinfo") and t_val.tzinfo is not None else t_val
        # Time to maturity for each option in years at this historical time
        ts = []
        for exp in opt_expiries:
            exp_naive = exp.replace(tzinfo=None) if hasattr(exp, "tzinfo") and exp.tzinfo is not None else exp
            dt_sec = (exp_naive - t_val_naive).total_seconds()
            ts.append(max(1.0, dt_sec) / (365.0 * 24.0 * 3600.0))
        ts = np.array(ts)
        
        # Calculate gammas for the option chain at spot s_val
        gammas = calculate_gamma_vectorized(
            spots=np.full_like(opt_strikes, s_val),
            strikes=opt_strikes,
            ts=ts,
            ivs=opt_ivs
        )
        
        # Dollar GEX
        gex_vals = gammas * opt_ois * opt_sizes * (s_val ** 2) * 0.01 * opt_dirs
        
        # Distribute the GEX values to the nearest strikes in strikes_range
        for strike, gex in zip(opt_strikes, gex_vals):
            if min_strike <= strike <= max_strike:
                s_idx = min(range(len(strikes_range)), key=lambda i: abs(strikes_range[i] - strike))
                z_matrix[s_idx, t_idx] += gex
                
        # Calculate the Gamma Flip point at this spot
        sim_spots = np.linspace(s_val * 0.8, s_val * 1.2, 30)
        sim_net_gex = []
        for sim_s in sim_spots:
            sim_gammas = calculate_gamma_vectorized(
                spots=np.full_like(opt_strikes, sim_s),
                strikes=opt_strikes,
                ts=ts,
                ivs=opt_ivs
            )
            sim_gex_vals = sim_gammas * opt_ois * opt_sizes * (sim_s ** 2) * 0.01 * opt_dirs
            sim_net_gex.append(float(np.sum(sim_gex_vals)))
            
        flip = None
        for i in range(len(sim_net_gex) - 1):
            if (sim_net_gex[i] <= 0 and sim_net_gex[i+1] > 0) or (sim_net_gex[i] >= 0 and sim_net_gex[i+1] < 0):
                flip = float(sim_spots[i] + (0 - sim_net_gex[i]) * (sim_spots[i+1] - sim_spots[i]) / (sim_net_gex[i+1] - sim_net_gex[i]))
                break
        flips.append(flip if flip else s_val)
        
    return strikes_range, times, z_matrix, spots, flips
