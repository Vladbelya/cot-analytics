import requests
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_economic_calendar():
    """
    Fetches the economic calendar from ForexFactory JSON feed.
    """
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Filter for high/medium impact and major currencies
        major_currencies = ["USD", "EUR", "GBP", "JPY", "CNY"]
        filtered_events = []
        
        for item in data:
            if item.get("country") in major_currencies and item.get("impact") in ["High", "Medium"]:
                # Parse date
                try:
                    dt = datetime.fromisoformat(item["date"])
                    date_str = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H:%M")
                except:
                    date_str = item.get("date", "")
                    time_str = ""
                    
                filtered_events.append({
                    "date": date_str,
                    "time": time_str,
                    "event": item.get("title", ""),
                    "impact": "🔴 Высокая" if item.get("impact") == "High" else "🟠 Средняя",
                    "forecast": item.get("forecast", ""),
                    "previous": item.get("previous", ""),
                    "currency": item.get("country", "")
                })
                
        return filtered_events
    except Exception as e:
        return {"error": str(e)}

def analyze_calendar_events(events):
    """
    Use the LLM to generate analysis for upcoming events.
    """
    from src.agent import get_gemini_client, load_knowledge_base
    
    client = get_gemini_client()
    kb = load_knowledge_base()
    
    events_str = ""
    for ev in events:
        events_str += f"- {ev['date']} {ev['time']} | {ev['currency']} | {ev['event']} | Прогноз: {ev['forecast']} | Пред: {ev['previous']}\n"
        
    prompt = f"""You are an elite AI Macro Strategist.
    Analyze the following upcoming high/medium impact macroeconomic events for this week.
    
    EVENTS:
    {events_str}
    
    KNOWLEDGE BASE (Context):
    {kb}
    
    INSTRUCTIONS:
    1. The output MUST be entirely in Russian.
    2. Write a synthesized brief about the general tone of the week (e.g. "Неделя инфляции", "Затишье перед ФРС").
    3. Provide your analysis in beautifully formatted Markdown, using bold text, bullet points, and headers. DO NOT USE HTML.
    4. Provide likely market scenarios (ВВЕРХ/ВНИЗ для SPY/BTC) depending on the outcomes of the most critical events.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Ошибка при генерации анализа: {e}"
