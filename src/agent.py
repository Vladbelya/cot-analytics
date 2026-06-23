import os
import json
import requests
import logging
from bs4 import BeautifulSoup
import pdfplumber
import yfinance as yf
from google import genai
from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_BASE_FILE = "data/knowledge_base.md"
TRACKED_SOURCES_FILE = "data/tracked_sources.json"

ABSORB_PROMPT = """You are a highly intelligent Financial Macro Agent.
Your task is to update your long-term Knowledge Base with new information.

EXISTING KNOWLEDGE BASE:
{existing_kb}

NEW INFORMATION SOURCED FROM '{source}':
{new_text}

INSTRUCTIONS:
1. Carefully read the NEW INFORMATION.
2. Integrate relevant macro-economic facts, asset-specific data, and key insights into the EXISTING KNOWLEDGE BASE.
3. Remove outdated or contradictory information if the new information is more recent and accurate.
4. Keep the Knowledge Base structured, detailed, and holistic. Group by topics (e.g., Macro Economy, Cryptocurrencies, Equities, Central Banks, etc.).
5. DO NOT just append; synthesize. If the new info is irrelevant noise, ignore it.
6. INCLUDE specific numbers, metrics, and data points (e.g. CPI 3.1%, rates at 5.5%).
7. Return ONLY the new updated markdown text for the Knowledge Base. 
8. THE ENTIRE KNOWLEDGE BASE MUST BE WRITTEN IN RUSSIAN. Translate any English information into Russian.
"""

REPORT_PROMPT = """You are an elite AI Hedge Fund Manager and Macro Strategist.

USER'S PORTFOLIO: {assets}

YOUR KNOWLEDGE BASE (Long-term memory):
{kb}

=== THE DATA BASKET (ALL AVAILABLE METRICS, COT, MACRO, PRICES, OPTIONS, ETFS) ===
{data_basket}
===================================================================

INSTRUCTIONS:
CRITICAL RULE 1: The report MUST be written ENTIRELY IN RUSSIAN.
CRITICAL RULE 2: You must analyze EVERY CATEGORY OF METRICS provided in the Data Basket. Do not skip any data source (Macro, COT, Options, ETFs, etc.).
CRITICAL RULE 3: For COT data, ALWAYS interpret the positions of different market participants (Asset Managers vs Leveraged Funds) SEPARATELY, highlighting their differences and conflicting interests.

STRUCTURE REQUIRED:

First, write an <internal_analysis> block. Think out loud (in Russian):
<internal_analysis>
- 1. Детальный разбор всех метрик (Metric-by-Metric Analysis). Go through every category of data provided in the Basket. For each item, analyze what is happening and the potential impact.
- How do these data points interconnect?
- Formulate the exact price impact on the user's assets.
</internal_analysis>

Second, output your final, beautifully formatted report containing ONLY these two sections:

### 1. Итоговое Умозаключение (Holistic Synthesis)
A comprehensive, detailed report combining all the metrics into one grand macro narrative. 
- What is the causal chain of events right now? 
- Where are the biggest anomalies?
- What are the "Smart money" anticipating?

### 2. ВЕРДИКТ: Влияние на твои активы (Price Impact)
For each asset in the User's Portfolio, give a clear directional bias (ВВЕРХ/ВНИЗ/ФЛЭТ) and a short summary of why.
"""

DASHBOARD_PROMPT = """You are an elite AI Hedge Fund Manager and Macro Strategist.

USER'S PORTFOLIO: {assets}

YOUR KNOWLEDGE BASE (Long-term memory):
{kb}

=== THE DATA BASKET (ALL AVAILABLE METRICS) ===
{data_basket}
===================================================================

INSTRUCTIONS:
CRITICAL RULE 1: The report MUST be written ENTIRELY IN RUSSIAN.

JSON STRUCTURE REQUIRED:
You MUST return your response strictly matching this JSON schema. Do not write any text outside of the JSON.
{
  "metrics": {
    "WALCL": "Short analysis of Fed Balance Sheet (WALCL) based on data.",
    "M2SL": "Short analysis of M2 Money Supply.",
    "RATES": "Short analysis of DGS10 and DGS2 (Rates & Yield Curve).",
    "INFLATION": "Short analysis of CPIAUCSL and UNRATE.",
    "COT": "Analysis of COT positioning, explicitly separating and comparing the positions of Asset Managers (Institutional) and Leveraged Funds (Speculators). MUST explicitly compare with the previous report, discussing inflows or outflows of longs and shorts.",
    "OPTIONS": "Analysis of Options (PCR, Max Pain, Anomalies).",
    "ETFS": "Analysis of ETF volume anomalies."
  },
  "conclusion": "A comprehensive, highly detailed final synthesis linking all these metrics together. State the ultimate causal chain and directional impact on the user's assets."
}

If any metric is missing from the Data Basket or has no data, just output "Данных нет или они в пределах нормы." for that key.
"""

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

import streamlit as st

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Bulletproof fallback: manually read .env if dotenv failed
    if not api_key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            os.environ["GEMINI_API_KEY"] = api_key
                            break
            except Exception:
                pass

    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass
            
    if not api_key:
        raise ValueError(f"API ключ GEMINI_API_KEY не найден в файле .env или Streamlit Secrets")
        
    return genai.Client(api_key=api_key)

def fetch_url_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract text from paragraphs
        paragraphs = soup.find_all('p')
        text = "\n".join([p.get_text() for p in paragraphs])
        return text[:15000] # Limit to avoid massive payloads
    except Exception as e:
        logging.error(f"Generation error: {e}")
        return f"Ошибка при генерации отчета: {e}"

from src.config import MARKETS

def fetch_realtime_news(assets_list):
    if not assets_list:
        return "Не указаны активы для поиска."
    
    # Add key macro indicators to provide background metrics
    macro_tickers = {
        "^GSPC": "S&P 500 (Market Benchmark)",
        "DX-Y.NYB": "US Dollar Index (DXY)",
        "^TNX": "10-Year Treasury Yield (Rates)",
        "GC=F": "Gold (Inflation/Risk Hedge)"
    }
    
    news_summary = ""
    
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
            
            # Get numerical metrics
            hist = tk.history(period="5d")
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[0]
                pct_change = ((last_price - prev_price) / prev_price) * 100
                
                news_summary += f"\n--- {asset_name} ({ticker}) СТАТИСТИКА ---\n"
                news_summary += f"Текущая цена/значение: {last_price:.2f}\n"
                news_summary += f"Динамика за 5 дней: {pct_change:+.2f}%\n"
            
            # Get news
            news = tk.news
            if news:
                news_summary += "Последние заголовки:\n"
                for item in news[:3]:
                    title = item.get("title", "")
                    news_summary += f"- {title}\n"
        except Exception:
            continue
            
    if not news_summary.strip():
        news_summary = "Не удалось загрузить данные ни по одному из активов."
        
    return news_summary

def extract_text_from_pdf(file_obj):
    text = ""
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text[:20000] # Limit size

def load_knowledge_base():
    if os.path.exists(KNOWLEDGE_BASE_FILE):
        try:
            with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "Knowledge Base is currently empty."
    return "Knowledge Base is currently empty."

def save_knowledge_base(content):
    os.makedirs(os.path.dirname(KNOWLEDGE_BASE_FILE), exist_ok=True)
    with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

def absorb_knowledge(new_text, source_name):
    client = get_gemini_client()
    existing_kb = load_knowledge_base()
    
    prompt = ABSORB_PROMPT.format(
        existing_kb=existing_kb,
        source=source_name,
        new_text=new_text
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    resp_text = response.text.strip()
    if resp_text.startswith("```markdown"):
        resp_text = resp_text[11:-3].strip()
    elif resp_text.startswith("```"):
        resp_text = resp_text[3:-3].strip()
        
    save_knowledge_base(resp_text)
    return True

DEFAULT_SOURCES = [
    "https://fred.stlouisfed.org/",
    "https://t.me/ClashReport",
    "https://t.me/rnintel",
    "https://t.me/AMK_Mapping",
    "https://t.me/CIG_telegram",
    "https://t.me/BellumActaNews",
    "https://x.com/deitaone?s=21",
    "https://x.com/financialjuice?s=21"
]

def load_tracked_sources():
    if os.path.exists(TRACKED_SOURCES_FILE):
        try:
            with open(TRACKED_SOURCES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data:
                    return DEFAULT_SOURCES.copy()
                return data
        except:
            return DEFAULT_SOURCES.copy()
    return DEFAULT_SOURCES.copy()

def save_tracked_sources(sources_list):
    os.makedirs(os.path.dirname(TRACKED_SOURCES_FILE), exist_ok=True)
    with open(TRACKED_SOURCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(sources_list, f, indent=4, ensure_ascii=False)

def analyze_single_source(new_text, source_name):
    client = get_gemini_client()
    
    prompt = f"""You are an elite AI Financial Advisor. 
The user just provided a new source: '{source_name}'.
Analyze this source carefully and provide a structured, insightful conclusion.
Highlight what it means for the macro environment and key assets.

CRITICAL INSTRUCTIONS:
1. The conclusion MUST be written ENTIRELY IN RUSSIAN.
2. You MUST include specific numbers, metrics, and data points mentioned in the text.

SOURCE CONTENT:
{new_text[:30000]}  # limit size just in case

Return the conclusion in beautifully formatted Markdown.
"""
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    return response.text

def generate_holistic_report(assets_string, extra_urls_string=""):
    client = get_gemini_client()
    kb = load_knowledge_base()
    
    # Parse assets
    assets_list = [a.strip() for a in assets_string.split(",") if a.strip()]
    
    # Fetch extra URLs if any
    extra_urls = [u.strip() for u in extra_urls_string.split('\n') if u.strip()]
    tracked_sources = load_tracked_sources()
    all_urls_to_scrape = list(set(extra_urls + tracked_sources))
    
    extra_context = ""
    for url in all_urls_to_scrape:
        try:
            url_text = fetch_url_text(url)
            extra_context += f"\n--- Content from {url} ---\n{url_text[:5000]}\n"
        except Exception as e:
            extra_context += f"\n--- Failed to load {url}: {e} ---\n"
            
    # Build the massive Data Basket
    from src.basket import build_global_data_basket
    data_basket = build_global_data_basket(assets_list, extra_context=extra_context)
    
    prompt = REPORT_PROMPT.format(
        assets=assets_string if assets_string else "General Market Portfolio",
        kb=kb,
        data_basket=data_basket
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro', # Use pro for deeper holistic reports
            contents=prompt
        )
    except Exception as e:
        e_str = str(e).lower()
        if "429" in e_str or "quota" in e_str or "resource_exhausted" in e_str or "503" in e_str or "unavailable" in e_str:
            response = client.models.generate_content(
                model='gemini-2.5-flash', # Fallback to flash
                contents=prompt
            )
        else:
            raise e
            
    final_report_full = response.text
    
    # Strip out the internal analysis block to give the user a clean report
    import re
    clean_report = re.sub(r'<internal_analysis>.*?</internal_analysis>', '', final_report_full, flags=re.DOTALL).strip()
    
    # Automatically save this report back into the Knowledge Base
    absorb_knowledge(clean_report, source_name="Предыдущий Сгенерированный Отчет")
            
    return clean_report

DASHBOARD_PROMPT = """You are an elite AI Hedge Fund Manager and Macro Strategist.

USER'S PORTFOLIO: {assets}

YOUR KNOWLEDGE BASE (Long-term memory):
{kb}

=== THE DATA BASKET (ALL AVAILABLE METRICS) ===
{data_basket}
===================================================================

INSTRUCTIONS:
CRITICAL RULE 1: The report MUST be written ENTIRELY IN RUSSIAN.
CRITICAL RULE 2: You MUST return your response strictly matching this JSON schema. Do not write any text outside of the JSON.

JSON STRUCTURE REQUIRED:
{{
  "metrics": {{
    "WALCL": "Short analysis of Fed Balance Sheet (WALCL) based on data.",
    "M2SL": "Short analysis of M2 Money Supply.",
    "RATES": "Short analysis of DGS10 and DGS2 (Rates & Yield Curve).",
    "INFLATION": "Short analysis of CPIAUCSL and UNRATE.",
    "COT": "Analysis of COT positioning, explicitly separating and comparing the positions of Asset Managers (Institutional) and Leveraged Funds (Speculators). MUST explicitly compare with the previous report, discussing inflows or outflows of longs and shorts.",
    "OPTIONS": "Analysis of Options (PCR, Max Pain, Anomalies).",
    "ETFS": "Analysis of ETF volume anomalies."
  }},
  "conclusion": "A comprehensive, highly detailed final synthesis linking all these metrics together. State the ultimate causal chain and directional impact on the user's assets."
}}

If any metric is missing from the Data Basket or has no data, just output "Данных нет или они в пределах нормы." for that key.
"""

def generate_dashboard_report(assets_string, extra_urls_string=""):
    client = get_gemini_client()
    kb = load_knowledge_base()
    
    assets_list = [a.strip() for a in assets_string.split(",") if a.strip()]
    
    extra_urls = [u.strip() for u in extra_urls_string.split('\n') if u.strip()]
    tracked_sources = load_tracked_sources()
    all_urls_to_scrape = list(set(extra_urls + tracked_sources))
    
    extra_context = ""
    for url in all_urls_to_scrape:
        try:
            url_text = fetch_url_text(url)
            extra_context += f"\n--- Content from {url} ---\n{url_text[:5000]}\n"
        except Exception as e:
            extra_context += f"\n--- Failed to load {url}: {e} ---\n"
            
    from src.basket import build_global_data_basket
    data_basket = build_global_data_basket(assets_list, extra_context=extra_context)
    
    prompt = DASHBOARD_PROMPT.format(
        assets=assets_string if assets_string else "General Market Portfolio",
        kb=kb,
        data_basket=data_basket
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        e_str = str(e).lower()
        if "429" in e_str or "quota" in e_str or "resource_exhausted" in e_str or "503" in e_str or "unavailable" in e_str:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                return json.loads(response.text)
            except Exception as inner_e:
                logging.error(f"JSON Fallback Generation error: {inner_e}")
                return {"error": f"Fallback failed: {inner_e}"}
        else:
            logging.error(f"JSON Generation error: {e}")
            return {"error": str(e)}

