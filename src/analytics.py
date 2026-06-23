import pandas as pd
import numpy as np
import os
from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP

def load_and_prepare_data(market_name, participant_name):
    """Load COT and Price CSVs, clean and dynamically extract the selected participant data."""
    cot_file = os.path.join(DATA_DIR_COT, f"{market_name}.csv")
    price_file = os.path.join(DATA_DIR_PRICES, f"{market_name}.csv")
    
    if not os.path.exists(cot_file) or not os.path.exists(price_file):
        raise FileNotFoundError(f"Файлы данных для {market_name} не найдены. Сначала запустите пайплайн.")
        
    # Read files
    cot_df = pd.read_csv(cot_file)
    price_df = pd.read_csv(price_file)
    
    # Parse dates
    cot_df["report_date"] = pd.to_datetime(cot_df["report_date"])
    price_df["date"] = pd.to_datetime(price_df["date"])
    
    # Sort by date for merge_asof
    cot_df = cot_df.sort_values("report_date")
    price_df = price_df.sort_values("date")
    
    # Get config for the market
    m_config = MARKETS[market_name]
    report_type = m_config["report_type"]
    
    # Get participant mappings
    p_map = PARTICIPANTS_MAP[report_type][participant_name]
    long_col = p_map["long"]
    short_col = p_map["short"]
    spread_col = p_map.get("spread")
    
    # Select and rename columns
    temp_cot = cot_df[["report_date", "open_interest"]].copy()
    
    # Map long and short
    temp_cot["long"] = pd.to_numeric(cot_df[long_col], errors="coerce").fillna(0.0)
    temp_cot["short"] = pd.to_numeric(cot_df[short_col], errors="coerce").fillna(0.0)
    
    # Map spread if available
    if spread_col and spread_col in cot_df.columns:
        temp_cot["spread"] = pd.to_numeric(cot_df[spread_col], errors="coerce").fillna(0.0)
    else:
        temp_cot["spread"] = 0.0
        
    # Merge using merge_asof (align COT date with closest preceding daily price)
    merged = pd.merge_asof(
        temp_cot,
        price_df,
        left_on="report_date",
        right_on="date",
        direction="backward"
    )
    
    # Clean merged df
    merged = merged.drop(columns=["date"])
    return merged

def calculate_metrics(df):
    """Calculate all COT metrics, indexes, Z-scores and signals."""
    df = df.copy()
    
    # 1. Base calculations
    df["net"] = df["long"] - df["short"]
    df["net_pct_oi"] = np.where(df["open_interest"] != 0, (df["net"] / df["open_interest"]) * 100, 0.0)
    
    # 2. WoW Changes
    df["wow_change_net"] = df["net"].diff(1).fillna(0.0)
    df["wow_change_net_pct_oi"] = df["net_pct_oi"].diff(1).fillna(0.0)
    df["long_change"] = df["long"].diff(1).fillna(0.0)
    df["short_change"] = df["short"].diff(1).fillna(0.0)
    df["oi_change"] = df["open_interest"].diff(1).fillna(0.0)
    df["oi_change_pct"] = np.where(df["open_interest"].shift(1) > 0, (df["open_interest"].diff(1) / df["open_interest"].shift(1)) * 100, 0.0)
    
    # Classical COT Index (156 weeks = 3 years)
    lookback = 156
    
    # Calculate Long COT Index
    min_l = df['long'].rolling(lookback, min_periods=52).min()
    max_l = df['long'].rolling(lookback, min_periods=52).max()
    df['long_index'] = np.where((max_l - min_l) > 0, (df['long'] - min_l) / (max_l - min_l) * 100, 50.0)
    
    # Calculate Short COT Index
    min_s = df['short'].rolling(lookback, min_periods=52).min()
    max_s = df['short'].rolling(lookback, min_periods=52).max()
    df['short_index'] = np.where((max_s - min_s) > 0, (df['short'] - min_s) / (max_s - min_s) * 100, 50.0)
    
    # Local WoW Spikes
    df['long_wow_pct'] = np.where(df['long'].shift(1) > 0, (df['long'] - df['long'].shift(1)) / df['long'].shift(1) * 100, 0.0)
    df['short_wow_pct'] = np.where(df['short'].shift(1) > 0, (df['short'] - df['short'].shift(1)) / df['short'].shift(1) * 100, 0.0)
    
    # Anomaly markers (Extreme zones: >90 and <10)
    df["long_index_anomaly"] = np.where((df["long_index"] >= 90) | (df["long_index"] <= 10), df["long_index"], np.nan)
    df["short_index_anomaly"] = np.where((df["short_index"] >= 90) | (df["short_index"] <= 10), df["short_index"], np.nan)

    
    # 3. Rolling COT Indexes
    # COT Index = (Net - Min_Net_N) / (Max_Net_N - Min_Net_N) * 100
    for w in [13, 26, 52]:
        rolling_min = df["net"].rolling(window=w, min_periods=min(w, 8)).min()
        rolling_max = df["net"].rolling(window=w, min_periods=min(w, 8)).max()
        denom = rolling_max - rolling_min
        df[f"cot_index_{w}w"] = np.where(denom != 0, ((df["net"] - rolling_min) / denom) * 100, 50.0)
        
    # 4. Z-Score of Net Position (52w rolling) and anomalous bands (+-2 std)
    rolling_mean = df["net"].rolling(window=52, min_periods=26).mean()
    rolling_std = df["net"].rolling(window=52, min_periods=26).std()
    df["net_mean_52w"] = rolling_mean
    df["net_std_52w"] = rolling_std
    df["net_upper_2std"] = rolling_mean + 2.0 * rolling_std
    df["net_lower_2std"] = rolling_mean - 2.0 * rolling_std
    
    df["net_zscore_52w"] = np.where(rolling_std != 0, (df["net"] - rolling_mean) / rolling_std, 0.0)
    
    # 5. Positioning Regime based on 52w COT Index
    df["regime"] = "Neutral"
    df.loc[df["cot_index_52w"] >= 90.0, "regime"] = "Extreme Long"
    df.loc[df["cot_index_52w"] <= 10.0, "regime"] = "Extreme Short"
    
    # 6. Signals: Divergence (4-week and 8-week windows)
    df["signal_bullish_div_4w"] = (df["close"] < df["close"].shift(4)) & (df["net"] > df["net"].shift(4))
    df["signal_bearish_div_4w"] = (df["close"] > df["close"].shift(4)) & (df["net"] < df["net"].shift(4))
    
    df["signal_bullish_div_8w"] = (df["close"] < df["close"].shift(8)) & (df["net"] > df["net"].shift(8))
    df["signal_bearish_div_8w"] = (df["close"] > df["close"].shift(8)) & (df["net"] < df["net"].shift(8))
    
    return df

def get_latest_signals(df):
    """Extract and format active signals for the latest week."""
    if df.empty:
        return []
        
    latest = df.iloc[-1]
    signals = []
    
    # 1. Extreme positioning signal
    if latest["regime"] == "Extreme Long":
        signals.append(("Экстремальный Лонг (COT Index 52w >= 90%)", "bearish_warning"))
    elif latest["regime"] == "Extreme Short":
        signals.append(("Экстремальный Шорт (COT Index 52w <= 10%)", "bullish_warning"))
        
    # 2. Z-Score signals (anomalous levels)
    if latest["net_zscore_52w"] >= 2.0:
        signals.append((f"Аномальный Z-Score лонг ({latest['net_zscore_52w']:.2f} std)", "bearish_warning"))
    elif latest["net_zscore_52w"] <= -2.0:
        signals.append((f"Аномальный Z-Score шорт ({latest['net_zscore_52w']:.2f} std)", "bullish_warning"))
        
    # 3. Divergence signals
    if latest["signal_bullish_div_4w"]:
        signals.append(("Бычья дивергенция (4н): цена ↓, позиции ↑", "bullish"))
    elif latest["signal_bearish_div_4w"]:
        signals.append(("Медвежья дивергенция (4н): цена ↑, позиции ↓", "bearish"))
        
    if latest["signal_bullish_div_8w"]:
        signals.append(("Бычья дивергенция (8н): цена ↓, позиции ↑", "bullish"))
    elif latest["signal_bearish_div_8w"]:
        signals.append(("Медвежья дивергенция (8н): цена ↑, позиции ↓", "bearish"))
        
    # 4. Momentum Shift
    if len(df) > 10:
        wow_changes = df["wow_change_net_pct_oi"].dropna()
        q95 = wow_changes.quantile(0.95)
        q05 = wow_changes.quantile(0.05)
        
        current_shift = latest["wow_change_net_pct_oi"]
        if current_shift >= q95:
            signals.append((f"Резкий бычий импульс (WoW +{current_shift:.1f}% OI)", "bullish"))
        elif current_shift <= q05:
            signals.append((f"Резкий медвежий импульс (WoW {current_shift:.1f}% OI)", "bearish"))
            
    # 5. Classical COT Index Extremes
    l_idx = latest["long_index"]
    s_idx = latest["short_index"]
    
    if l_idx >= 90:
        signals.append((f"🔥 Экстремальный Лонг: COT Индекс {l_idx:.1f}%. Аномальная перекупленность.", "bearish_warning"))
    elif l_idx <= 10:
        signals.append((f"📉 Исторический минимум лонгов: COT Индекс {l_idx:.1f}%. Перепроданность.", "bullish_warning"))
        
    if s_idx >= 90:
        signals.append((f"🔥 Экстремальный Шорт: COT Индекс {s_idx:.1f}%. Шорт-сквиз потенциал.", "bullish_warning"))
    elif s_idx <= 10:
        signals.append((f"📉 Исторический минимум шортов: COT Индекс {s_idx:.1f}%. Недостаток медведей.", "bearish_warning"))
            
    return signals

def get_market_analysis(market_name, participant_name):
    """Load, prepare and calculate analytics for a specific market and participant."""
    raw_df = load_and_prepare_data(market_name, participant_name)
    analytics_df = calculate_metrics(raw_df)
    return analytics_df
