import os
import pandas as pd
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATA_DIR_MACRO = "data/macro"

# FRED Series IDs mapped to human-readable names
FRED_SERIES = {
    "WALCL": {"name": "Баланс ФРС (WALCL, млн $)", "type": "liquidity"},
    "M2SL": {"name": "Денежная масса M2 (млрд $)", "type": "liquidity"},
    "DGS10": {"name": "10-Летние Облигации (%)", "type": "rates"},
    "DGS2": {"name": "2-Летние Облигации (%)", "type": "rates"},
    "CPIAUCSL": {"name": "Инфляция CPI (Индекс)", "type": "economy"},
    "UNRATE": {"name": "Безработица (%)", "type": "economy"}
}

def init_directories():
    os.makedirs(DATA_DIR_MACRO, exist_ok=True)

def fetch_fred_data():
    """
    Скачивает макроэкономические данные напрямую из FRED (через CSV эндпоинты).
    """
    init_directories()
    results = {}
    
    for series_id, info in FRED_SERIES.items():
        logging.info(f"Загрузка макро-индикатора: {info['name']} ({series_id})...")
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            df = pd.read_csv(url, na_values=".")
            
            if not df.empty:
                # The CSV has columns: DATE or observation_date, SERIES_ID
                df = df.rename(columns={df.columns[0]: 'date', df.columns[1]: 'value'})
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df = df.dropna()
                
                filepath = os.path.join(DATA_DIR_MACRO, f"{series_id}.csv")
                df.to_csv(filepath, index=False, encoding='utf-8')
                logging.info(f"Успешно сохранен {series_id} ({len(df)} записей).")
                results[series_id] = df
            else:
                logging.warning(f"Данные для {series_id} пусты.")
        except Exception as e:
            logging.error(f"Ошибка при загрузке {series_id}: {e}")
            
    return results

def get_macro_summary():
    """
    Читает локальные CSV и возвращает краткую текстовую выжимку текущего состояния макро.
    """
    summary_text = "ОФИЦИАЛЬНАЯ МАКРОЭКОНОМИКА (FRED США):\n"
    
    # WALCL
    try:
        df = pd.read_csv(os.path.join(DATA_DIR_MACRO, "WALCL.csv"))
        latest = df['value'].iloc[-1]
        prev = df['value'].iloc[-2]
        change = latest - prev
        trend = "СЖАТИЕ ЛИКВИДНОСТИ (QT)" if change < 0 else "ПЕЧАТНЫЙ СТАНОК (QE)"
        summary_text += f"- Баланс ФРС: {latest:,.0f} млн $ ({trend}: изменение на {change:,.0f} млн $).\n"
    except: pass

    # M2
    try:
        df = pd.read_csv(os.path.join(DATA_DIR_MACRO, "M2SL.csv"))
        latest = df['value'].iloc[-1]
        prev = df['value'].iloc[-2]
        trend = "Падает" if latest < prev else "Растет"
        summary_text += f"- Денежная масса M2: {latest:,.1f} млрд $ ({trend}).\n"
    except: pass
    
    # Yield Curve
    try:
        df10 = pd.read_csv(os.path.join(DATA_DIR_MACRO, "DGS10.csv"))
        df2 = pd.read_csv(os.path.join(DATA_DIR_MACRO, "DGS2.csv"))
        y10 = df10['value'].iloc[-1]
        y2 = df2['value'].iloc[-1]
        spread = y10 - y2
        curve_status = "ИНВЕРТИРОВАНА (СИГНАЛ РЕЦЕССИИ!)" if spread < 0 else "НОРМАЛЬНАЯ"
        summary_text += f"- Кривая доходности (10Y - 2Y Spread): {spread:+.2f}% -> {curve_status}\n"
        summary_text += f"  * Доходность 10-леток: {y10:.2f}%\n"
    except: pass
    
    # Inflation and Unemployment
    try:
        df_cpi = pd.read_csv(os.path.join(DATA_DIR_MACRO, "CPIAUCSL.csv"))
        df_un = pd.read_csv(os.path.join(DATA_DIR_MACRO, "UNRATE.csv"))
        
        cpi_latest = df_cpi['value'].iloc[-1]
        cpi_prev_year = df_cpi['value'].iloc[-13] if len(df_cpi) >= 13 else df_cpi['value'].iloc[0]
        cpi_yoy = ((cpi_latest - cpi_prev_year) / cpi_prev_year) * 100
        
        un_latest = df_un['value'].iloc[-1]
        
        summary_text += f"- Инфляция (CPI YoY оценка): ~{cpi_yoy:.1f}%\n"
        summary_text += f"- Уровень безработицы: {un_latest:.1f}%\n"
    except: pass
    
    return summary_text

def update_macro_ai_analysis():
    """Generates an AI analysis of the current macro metrics and saves it."""
    from src.agent import get_gemini_client
    from src import gemini_utils
    try:
        client = get_gemini_client()
        raw_metrics = get_macro_summary()
        prompt = f"""You are a top-tier Macro Strategist at a Hedge Fund.
The user wants to know EXACTLY how the current macro metrics impact their portfolio. Do NOT just list the metrics. Provide a deep, insightful analysis of the causality.

CURRENT RAW METRICS:
{raw_metrics}

INSTRUCTIONS:
1. Write the analysis ENTIRELY IN RUSSIAN.
2. ZERO WATER. No textbook definitions (e.g. don't explain what CPI is).
3. Explain the CAUSALITY: What does the change in liquidity (Fed Balance Sheet, M2) and Yield Curve mean right now?
4. Explicitly state the expected impact on:
   - S&P 500 / Nasdaq (Risk-on Equities)
   - Crypto / Bitcoin (High beta liquidity sponges)
   - Bonds / Safe Havens
5. Format beautifully with markdown. Provide a clear "ВЫВОД" (Conclusion)."""
        
        response = gemini_utils.generate_content_with_retry(
            client=client,
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        filepath = os.path.join(DATA_DIR_MACRO, "ai_analysis.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)
        logging.info("AI Macro Analysis updated.")
    except Exception as e:
        logging.error(f"Failed to generate AI macro analysis: {e}")

def get_macro_ai_analysis():
    """Returns the cached AI macro analysis."""
    filepath = os.path.join(DATA_DIR_MACRO, "ai_analysis.md")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "AI анализ макроданных еще не сгенерирован. Нажмите 'Обновить Макро-Данные'."

if __name__ == "__main__":
    print("Обновление макроэкономических данных...")
    fetch_fred_data()
    print("\n--- Сводка ---")
    print(get_macro_summary())
