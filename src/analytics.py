import pandas as pd
import numpy as np
import os
from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP

def load_and_prepare_data(market_name, participant_name, use_combined=False):
    """Load COT and Price CSVs, clean and dynamically extract the selected participant data."""
    suffix = "_combined" if use_combined else "_futures"
    cot_file = os.path.join(DATA_DIR_COT, f"{market_name}{suffix}.csv")
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
    df["spec_ratio"] = np.where(df["short"] > 0, df["long"] / df["short"], df["long"])
    
    # 2. WoW Changes
    df["wow_change_net"] = df["net"].diff(1).fillna(0.0)
    df["wow_change_net_pct_oi"] = df["net_pct_oi"].diff(1).fillna(0.0)
    df["long_change"] = df["long"].diff(1).fillna(0.0)
    df["short_change"] = df["short"].diff(1).fillna(0.0)
    df["oi_change"] = df["open_interest"].diff(1).fillna(0.0)
    df["oi_change_pct"] = np.where(df["open_interest"].shift(1) > 0, (df["open_interest"].diff(1) / df["open_interest"].shift(1)) * 100, 0.0)
    
    # Classical COT Index lookback
    lookback = 156
    
    # Calculate Long COT Index (Individual)
    min_l = df['long'].rolling(lookback, min_periods=52).min()
    max_l = df['long'].rolling(lookback, min_periods=52).max()
    df['long_index'] = np.where((max_l - min_l) > 0, (df['long'] - min_l) / (max_l - min_l) * 100, 50.0)
    
    # Calculate Short COT Index (Individual)
    min_s = df['short'].rolling(lookback, min_periods=52).min()
    max_s = df['short'].rolling(lookback, min_periods=52).max()
    df['short_index'] = np.where((max_s - min_s) > 0, (df['short'] - min_s) / (max_s - min_s) * 100, 50.0)
    
    # --- STANDARD NET POSITION COT INDEX (Min-Max) ---
    # 156 weeks (3 years)
    min_net_156 = df['net'].rolling(156, min_periods=52).min()
    max_net_156 = df['net'].rolling(156, min_periods=52).max()
    df['cot_index_net_156w'] = np.where((max_net_156 - min_net_156) > 0, (df['net'] - min_net_156) / (max_net_156 - min_net_156) * 100, 50.0)
    
    # 52 weeks (1 year)
    min_net_52 = df['net'].rolling(52, min_periods=26).min()
    max_net_52 = df['net'].rolling(52, min_periods=26).max()
    df['cot_index_net_52w'] = np.where((max_net_52 - min_net_52) > 0, (df['net'] - min_net_52) / (max_net_52 - min_net_52) * 100, 50.0)
    
    # --- STANDARD NET POSITION % OF OI COT INDEX (Min-Max) ---
    # 156 weeks (3 years)
    min_net_pct_oi_156 = df['net_pct_oi'].rolling(156, min_periods=52).min()
    max_net_pct_oi_156 = df['net_pct_oi'].rolling(156, min_periods=52).max()
    df['cot_index_net_pct_oi_156w'] = np.where((max_net_pct_oi_156 - min_net_pct_oi_156) > 0, (df['net_pct_oi'] - min_net_pct_oi_156) / (max_net_pct_oi_156 - min_net_pct_oi_156) * 100, 50.0)
    
    # 52 weeks (1 year)
    min_net_pct_oi_52 = df['net_pct_oi'].rolling(52, min_periods=26).min()
    max_net_pct_oi_52 = df['net_pct_oi'].rolling(52, min_periods=26).max()
    df['cot_index_net_pct_oi_52w'] = np.where((max_net_pct_oi_52 - min_net_pct_oi_52) > 0, (df['net_pct_oi'] - min_net_pct_oi_52) / (max_net_pct_oi_52 - min_net_pct_oi_52) * 100, 50.0)
    
    # Local WoW Spikes
    df['long_wow_pct'] = np.where(df['long'].shift(1) > 0, (df['long'] - df['long'].shift(1)) / df['long'].shift(1) * 100, 0.0)
    df['short_wow_pct'] = np.where(df['short'].shift(1) > 0, (df['short'] - df['short'].shift(1)) / df['short'].shift(1) * 100, 0.0)
    
    # Anomaly markers (Extreme zones: >90 and <10) based on Net % of OI Index (3-year)
    df["long_index_anomaly"] = np.where((df["long_index"] >= 90) | (df["long_index"] <= 10), df["long_index"], np.nan)
    df["short_index_anomaly"] = np.where((df["short_index"] >= 90) | (df["short_index"] <= 10), df["short_index"], np.nan)
    df["net_index_anomaly_156w"] = np.where((df["cot_index_net_pct_oi_156w"] >= 90) | (df["cot_index_net_pct_oi_156w"] <= 10), df["cot_index_net_pct_oi_156w"], np.nan)
    df["net_index_anomaly_52w"] = np.where((df["cot_index_net_pct_oi_52w"] >= 90) | (df["cot_index_net_pct_oi_52w"] <= 10), df["cot_index_net_pct_oi_52w"], np.nan)

    # 3. Rolling Percentile Ranks using Causal Percentile (kept for backward compatibility as 'cot_index_Xw')
    def rank_causal_percentile(window):
        current = window[-1]
        count_le = np.sum(window <= current)
        return (count_le / len(window)) * 100

    for w in [13, 26, 52]:
        df[f"cot_index_{w}w"] = df["net"].rolling(window=w, min_periods=min(w, 8)).apply(rank_causal_percentile, raw=True)
        
    # 4. Z-Score of Net Position and Net % OI (156w rolling and 52w rolling)
    # Z-Score Net position (52w)
    rolling_mean_52 = df["net"].rolling(window=52, min_periods=26).mean()
    rolling_std_52 = df["net"].rolling(window=52, min_periods=26).std()
    df["net_mean_52w"] = rolling_mean_52
    df["net_std_52w"] = rolling_std_52
    df["net_upper_2std"] = rolling_mean_52 + 2.0 * rolling_std_52
    df["net_lower_2std"] = rolling_mean_52 - 2.0 * rolling_std_52
    df["net_zscore_52w"] = np.where(rolling_std_52 != 0, (df["net"] - rolling_mean_52) / rolling_std_52, 0.0)
    
    # Z-Score Net position (156w)
    rolling_mean_156 = df["net"].rolling(window=156, min_periods=52).mean()
    rolling_std_156 = df["net"].rolling(window=156, min_periods=52).std()
    df["net_zscore_156w"] = np.where(rolling_std_156 != 0, (df["net"] - rolling_mean_156) / rolling_std_156, 0.0)
    
    # Z-Score Net % OI (156w) - The professional standard!
    rolling_mean_pct_156 = df["net_pct_oi"].rolling(window=156, min_periods=52).mean()
    rolling_std_pct_156 = df["net_pct_oi"].rolling(window=156, min_periods=52).std()
    df["net_pct_oi_zscore_156w"] = np.where(rolling_std_pct_156 != 0, (df["net_pct_oi"] - rolling_mean_pct_156) / rolling_std_pct_156, 0.0)
    
    # Z-Score Net % OI (52w)
    rolling_mean_pct_52 = df["net_pct_oi"].rolling(window=52, min_periods=26).mean()
    rolling_std_pct_52 = df["net_pct_oi"].rolling(window=52, min_periods=26).std()
    df["net_pct_oi_zscore_52w"] = np.where(rolling_std_pct_52 != 0, (df["net_pct_oi"] - rolling_mean_pct_52) / rolling_std_pct_52, 0.0)

    # 5. Positioning Regime based on standard 156w Net % of OI COT Index
    df["regime"] = "Neutral"
    df.loc[df["cot_index_net_pct_oi_156w"] >= 90.0, "regime"] = "Extreme Long"
    df.loc[df["cot_index_net_pct_oi_156w"] <= 10.0, "regime"] = "Extreme Short"
    
    # 6. Signals: Divergence (4-week and 8-week windows)
    df["signal_bullish_div_4w"] = (df["close"] < df["close"].shift(4)) & (df["net"] > df["net"].shift(4))
    df["signal_bearish_div_4w"] = (df["close"] > df["close"].shift(4)) & (df["net"] < df["net"].shift(4))
    
    df["signal_bullish_div_8w"] = (df["close"] < df["close"].shift(8)) & (df["net"] > df["net"].shift(8))
    df["signal_bearish_div_8w"] = (df["close"] > df["close"].shift(8)) & (df["net"] < df["net"].shift(8))
    
    # 7. OI & Price dynamics trend classification
    price_change = df["close"].diff(1)
    oi_change = df["open_interest"].diff(1)
    
    df["oi_price_sentiment"] = "Neutral"
    df.loc[(price_change > 0) & (oi_change > 0), "oi_price_sentiment"] = "Сильный восходящий тренд (Подтвержден ростом OI)"
    df.loc[(price_change > 0) & (oi_change < 0), "oi_price_sentiment"] = "Слабый восходящий импульс (Шорт-сквиз / Истощение)"
    df.loc[(price_change < 0) & (oi_change > 0), "oi_price_sentiment"] = "Сильный нисходящий тренд (Подтвержден ростом OI)"
    df.loc[(price_change < 0) & (oi_change < 0), "oi_price_sentiment"] = "Слабый нисходящий импульс (Лонг-сквиз / Капитуляция)"
    
    return df

def get_latest_signals(df):
    """Extract and format active signals for the latest week."""
    if df.empty:
        return []
        
    latest = df.iloc[-1]
    signals = []
    
    # 1. Extreme positioning signal (using 156w Net % OI Index)
    if latest["regime"] == "Extreme Long":
        signals.append(("Экстремальное позиционирование лонг (COT Index Net % OI 3г >= 90%)", "bearish_warning"))
    elif latest["regime"] == "Extreme Short":
        signals.append(("Экстремальное позиционирование шорт (COT Index Net % OI 3г <= 10%)", "bullish_warning"))
        
    # 2. Z-Score signals (anomalous levels, 156w lookback Net % OI Z-score)
    zscore = latest["net_pct_oi_zscore_156w"]
    if zscore >= 2.0:
        signals.append((f"Экстремальный Z-Score лонг 3г ({zscore:.2f} std)", "bearish_warning"))
    elif zscore <= -2.0:
        signals.append((f"Экстремальный Z-Score шорт 3г ({zscore:.2f} std)", "bullish_warning"))
        
    # 3. Divergence signals
    if latest["signal_bullish_div_4w"]:
        signals.append(("Бычья дивергенция (4н): цена ↓, чистая позиция ↑", "bullish"))
    elif latest["signal_bearish_div_4w"]:
        signals.append(("Медвежья дивергенция (4н): цена ↑, чистая позиция ↓", "bearish"))
        
    if latest["signal_bullish_div_8w"]:
        signals.append(("Бычья дивергенция (8н): цена ↓, чистая позиция ↑", "bullish"))
    elif latest["signal_bearish_div_8w"]:
        signals.append(("Медвежья дивергенция (8н): цена ↑, чистая позиция ↓", "bearish"))
        
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
            
    # 5. Spec Ratio extremes (for speculators/leveraged funds)
    if "spec_ratio" in latest:
        ratio = latest["spec_ratio"]
        if ratio >= 4.0:
            signals.append((f"⚠️ Спекулятивный перегрев: Spec Ratio = {ratio:.2f} (избыточный лонг)", "bearish_warning"))
        elif ratio <= 0.25 and ratio > 0:
            signals.append((f"⚠️ Спекулятивная паника: Spec Ratio = {ratio:.2f} (избыточный шорт)", "bullish_warning"))
            
    # 6. OI Trend Confirmation
    if "oi_price_sentiment" in latest and latest["oi_price_sentiment"] != "Neutral":
        sentiment = latest["oi_price_sentiment"]
        if "Сильный восходящий" in sentiment:
            signals.append((f"📈 Подтверждение тренда: {sentiment}", "bullish"))
        elif "Слабый восходящий" in sentiment:
            signals.append((f"⚠️ Сигнал слабости: {sentiment}", "bearish_warning"))
        elif "Сильный нисходящий" in sentiment:
            signals.append((f"📉 Подтверждение тренда: {sentiment}", "bearish"))
        elif "Слабый нисходящий" in sentiment:
            signals.append((f"⚠️ Сигнал слабости: {sentiment}", "bullish_warning"))
            
    return signals

def get_market_analysis(market_name, participant_name, use_combined=False):
    """Load, prepare and calculate analytics for a specific market and participant."""
    raw_df = load_and_prepare_data(market_name, participant_name, use_combined=use_combined)
    analytics_df = calculate_metrics(raw_df)
    return analytics_df

def generate_holistic_report(market_name, use_combined=False):
    try:
        am_df = get_market_analysis(market_name, "Asset Manager", use_combined=use_combined)
        lf_df = get_market_analysis(market_name, "Leveraged Funds", use_combined=use_combined)
        dl_df = get_market_analysis(market_name, "Dealer", use_combined=use_combined)
        rt_df = get_market_analysis(market_name, "Retail", use_combined=use_combined)
    except Exception as e:
        return f"Недостаточно данных для формирования комплексного отчета: {e}"
        
    if am_df.empty or lf_df.empty or dl_df.empty or rt_df.empty:
        return "Недостаточно данных для формирования комплексного отчета."
        
    latest_am = am_df.iloc[-1]
    latest_lf = lf_df.iloc[-1]
    latest_dl = dl_df.iloc[-1]
    latest_rt = rt_df.iloc[-1]
    
    # 1. Контекст рынка (Цена)
    price_now = latest_am["close"]
    price_1w_ago = am_df["close"].iloc[-2] if len(am_df) > 1 else price_now
    price_4w_ago = am_df["close"].iloc[-5] if len(am_df) > 4 else price_now
    
    wow_trend = "выросла" if price_now > price_1w_ago else "упала"
    mom_trend = "роста" if price_now > price_4w_ago else "падения"
    
    context = f"**📊 Контекст рынка (Цена):** За последнюю неделю цена {wow_trend} до отметки ${price_now:,.2f}. В разрезе месяца актив находится в фазе {mom_trend}."
    
    # Open Interest Dynamics
    oi_now = latest_am["open_interest"]
    oi_1w_ago = am_df["open_interest"].iloc[-2] if len(am_df) > 1 else oi_now
    oi_pct_change = ((oi_now - oi_1w_ago) / oi_1w_ago * 100) if oi_1w_ago > 0 else 0.0
    oi_word = "вырос" if oi_now > oi_1w_ago else "снизился"
    
    # Get OI sentiment from Leveraged Funds
    oi_sentiment = latest_lf.get("oi_price_sentiment", "Neutral")
    context += f" Открытый интерес {oi_word} на {abs(oi_pct_change):.1f}% и составляет {oi_now:,.0f} контрактов. Динамика OI-Price: *{oi_sentiment}*."
    
    # 2. Расстановка сил (Участники рынка)
    am_idx = latest_am["cot_index_net_pct_oi_156w"]
    lf_idx = latest_lf["cot_index_net_pct_oi_156w"]
    dl_idx = latest_dl["cot_index_net_pct_oi_156w"]
    rt_idx = latest_rt["cot_index_net_pct_oi_156w"]
    
    # Asset Managers (Institutional Investors)
    am_is_bullish = am_idx >= 80
    am_is_bearish = am_idx <= 20
    if am_is_bullish:
        am_action = f"Институциональные инвесторы настроены крайне по-бычьи (COT Index Net % OI 3г = {am_idx:.1f}%), удерживая крупный чистый лонг."
    elif am_is_bearish:
        am_action = f"Институциональные инвесторы настроены крайне по-медвежьи (COT Index Net % OI 3г = {am_idx:.1f}%), сократив чистый лонг до минимумов."
    else:
        am_action = f"Институциональные инвесторы занимают умеренную позицию (COT Index Net % OI 3г = {am_idx:.1f}%), не совершая резких перестроений."
        
    # Leveraged Funds (Large Speculators/Hedge Funds)
    lf_is_bullish = lf_idx >= 80
    lf_is_bearish = lf_idx <= 20
    if lf_is_bullish:
        lf_action = f"Крупные спекулянты (Хедж-фонды/CTA) перегружены покупками (COT Index Net % OI 3г = {lf_idx:.1f}%), что исторически несет риск лонг-сквиза."
    elif lf_is_bearish:
        lf_action = f"Крупные спекулянты агрессивно зашортили актив (COT Index Net % OI 3г = {lf_idx:.1f}%), создавая предпосылки для мощного шорт-сквиза при локальном развороте цены вверх."
    else:
        lf_action = f"Настроения крупных спекулянтов остаются сбалансированными (COT Index Net % OI 3г = {lf_idx:.1f}%)."
        
    # Dealers (Sell-Side/Hedgers)
    dl_action = f"Дилеры / Банки (Маркет-мейкеры) удерживают чистый индекс на уровне {dl_idx:.1f}%."
    
    # Retail (Crowd)
    rt_is_bullish = rt_idx >= 80
    rt_is_bearish = rt_idx <= 20
    if rt_is_bullish:
        rt_action = f"Мелкие спекулянты (Толпа / Ритейл) поддались эйфории и зашли в экстремальный лонг (COT Index Net % OI 3г = {rt_idx:.1f}%)."
    elif rt_is_bearish:
        rt_action = f"Мелкие спекулянты находятся в панике, удерживая максимальный шорт на исторических минимумах (COT Index Net % OI 3г = {rt_idx:.1f}%)."
    else:
        rt_action = f"Мелкие участники рынка (Толпа) ведут себя нейтрально (COT Index Net % OI 3г = {rt_idx:.1f}%)."
        
    forces = f"**⚖️ Расстановка сил (Участники рынка):**\n* 🏛️ **Институционалы:** {am_action}\n* 🚀 **Хедж-фонды:** {lf_action}\n* 🏦 **Дилеры (Продающая сторона):** {dl_action}\n* 👥 **Ритейл (Толпа):** {rt_action}"
    
    # Check for weekly anomalies (WoW net flow spikes)
    lf_wow_pct_oi = latest_lf.get("wow_change_net_pct_oi", 0)
    if abs(lf_wow_pct_oi) >= 5.0:
        direction_word = "увеличили" if lf_wow_pct_oi > 0 else "сократили"
        forces += f"\n* 🚨 **Аномальный поток:** Хедж-фонды резко {direction_word} чистую позицию на {abs(lf_wow_pct_oi):.1f}% от открытого интереса за неделю. Это сильный импульсный сигнал."
        
    # Spec Ratio context
    lf_spec_ratio = latest_lf.get("spec_ratio", 1.0)
    forces += f"\n* 📊 **Коэффициент спекулянтов (Spec Ratio):** Хедж-фонды имеют соотношение лонгов к шортам {lf_spec_ratio:.2f}."
    
    # 3. Вердикт (Механика)
    verdict = "**🔮 Итоговый вердикт (Механика):** Ситуация на рынке сбалансированная. Явных перекосов между трендовыми хедж-фондами и институционалами не наблюдается."
    
    if lf_is_bullish and (am_is_bearish or dl_idx <= 20):
        verdict = "**🔮 Итоговый вердикт (Риск коррекции / Long Squeeze):** Медвежий сетап. Риск полностью перешел к трендовым хедж-фондам (спекулянтам), которые загружены покупками на максимумах, в то время как маркет-мейкеры и долгосрочные инвесторы сокращают лонги. Отсутствие спекулятивного топлива для дальнейшего роста может спровоцировать волну ликвидаций и обвал."
    elif lf_is_bearish and (am_is_bullish or dl_idx >= 80):
        verdict = "**🔮 Итоговый вердикт (Потенциал роста / Short Squeeze):** Бычий сетап. Спекулянты перегружены шортами на минимумах, в то время как умные деньги (дилеры и институционалы) активно выкупают актив. Ликвидность на продажу исчерпана, любое восходящее движение вызовет закрытие стопов медведей и резкий импульсный рост цены вверх."
    elif lf_is_bullish and rt_is_bullish:
        verdict = "**🔮 Итоговый вердикт (Эйфория / Перегрев):** Рынок перегрет совместными покупками хедж-фондов и мелких спекулянтов. Тренд силен, но близок к истощению, рекомендуется проявлять осторожность."
    elif lf_is_bearish and rt_is_bearish:
        verdict = "**🔮 Итоговый вердикт (Паника / Точка входа):** На рынке царит паника спекулятивной толпы и фондов. Все участники зашортили актив, что исторически является идеальной зоной для поиска долгосрочных покупок."
        
    return f"{context}\n\n{forces}\n\n{verdict}\n"
