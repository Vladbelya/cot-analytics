import os

new_app_content = '''import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime

from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP
from src.pipeline import update_all_data, get_data_freshness
from src.analytics import get_market_analysis
from src.backtester import run_full_interpretation, SIGNAL_DEFS, FORWARD_HORIZONS
from src.agent import (
    extract_text_from_pdf, 
    fetch_url_text, 
    absorb_knowledge, 
    generate_holistic_report, 
    load_knowledge_base,
    analyze_single_source,
    load_tracked_sources,
    save_tracked_sources
)

# Page configuration
st.set_page_config(
    page_title="Терминал Кот",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, Minimalist Dark CSS
st.markdown("""
<style>
    .stApp { background-color: #030406; color: #e2e8f0; font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3, h4 { color: #ffffff; font-weight: 700; margin-top: 10px; margin-bottom: 15px; }
    .neon-hr { height: 1px; background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.08), rgba(255,255,255,0)); border: none; margin: 15px 0; }
    .cot-table-container { background-color: #08090a; border: 1px solid #15181f; border-radius: 8px; padding: 20px; margin-top: 20px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4); }
    .cot-table { width: 100%; border-collapse: collapse; color: #d1d5db; font-size: 0.95em; text-align: right; }
    .cot-table th, .cot-table td { padding: 10px 16px; border-bottom: 1px solid #111418; vertical-align: middle; }
    .cot-table th { font-weight: 700; color: #6b7280; font-size: 0.85em; text-transform: uppercase; border-bottom: 2px solid #15181f; }
    .cot-table th:first-child, .cot-table td:first-child { text-align: left; }
    .cot-table tr:hover { background-color: rgba(255, 255, 255, 0.015); }
    .date-cell { color: #ffffff; font-weight: 600; }
    .font-mono { font-family: 'SF Mono', Monaco, Consolas, monospace; }
    .net-positive { background-color: rgba(39, 174, 96, 0.12) !important; color: #2ecc71 !important; font-weight: bold; border-radius: 4px; }
    .net-negative { background-color: rgba(192, 57, 43, 0.12) !important; color: #e74c3c !important; font-weight: bold; border-radius: 4px; }
    .interp-card { background-color: #08090a; border: 1px solid #15181f; border-radius: 8px; padding: 24px; margin-top: 24px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4); }
    .interp-section { margin-bottom: 20px; }
    .interp-label { font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.1em; color: #6b7280; font-weight: 700; margin-bottom: 10px; }
    .interp-situation-line { color: #d1d5db; font-size: 0.95em; line-height: 1.7; margin: 2px 0; }
    .interp-signal-row { display: flex; align-items: flex-start; gap: 10px; padding: 12px 16px; margin: 6px 0; border-radius: 6px; background-color: rgba(255,255,255,0.02); border-left: 3px solid #333; }
    .interp-signal-row.bullish { border-left-color: #2ecc71; }
    .interp-signal-row.bearish { border-left-color: #e74c3c; }
    .interp-signal-name { font-weight: 700; color: #ffffff; font-size: 0.95em; margin-bottom: 4px; }
    .interp-signal-desc { font-size: 0.85em; color: #9ca3af; line-height: 1.5; }
    .bt-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.85em; }
    .bt-table th { color: #6b7280; font-weight: 600; font-size: 0.8em; text-transform: uppercase; padding: 6px 10px; border-bottom: 1px solid #1a1d24; text-align: right; }
    .bt-table th:first-child { text-align: left; }
    .bt-table td { padding: 6px 10px; border-bottom: 1px solid #0d0f12; text-align: right; color: #d1d5db; font-family: 'SF Mono', Monaco, Consolas, monospace; }
    .bt-table td:first-child { text-align: left; color: #9ca3af; }
    .bt-wr-high { color: #2ecc71; font-weight: 700; }
    .bt-wr-low { color: #e74c3c; font-weight: 700; }
    .bt-wr-mid { color: #f39c12; font-weight: 700; }
    .interp-verdict { padding: 16px 20px; border-radius: 6px; font-size: 1.0em; font-weight: 600; line-height: 1.6; }
    .interp-verdict.bullish { background: rgba(39, 174, 96, 0.08); border: 1px solid rgba(39, 174, 96, 0.2); color: #2ecc71; }
    .interp-verdict.bearish { background: rgba(192, 57, 43, 0.08); border: 1px solid rgba(192, 57, 43, 0.2); color: #e74c3c; }
    .interp-verdict.neutral { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); color: #9ca3af; }
    .interp-hr { height: 1px; background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.06), rgba(255,255,255,0)); border: none; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_cached_alt_data():
    from src.alt_data import fetch_insider_trading, fetch_fed_liquidity, fetch_etf_anomalies
    return {
        "fed": fetch_fed_liquidity(),
        "insider": fetch_insider_trading(),
        "etf": fetch_etf_anomalies()
    }

def check_data_exists():
    for market_name in MARKETS.keys():
        cot_file = os.path.join(DATA_DIR_COT, f"{market_name}.csv")
        price_file = os.path.join(DATA_DIR_PRICES, f"{market_name}.csv")
        if not os.path.exists(cot_file) or not os.path.exists(price_file):
            return False
    return True

def fmt_num(val, show_sign=False):
    if pd.isna(val):
        return "—"
    val_int = int(round(val))
    sign = "+" if show_sign and val_int > 0 else ""
    fmt = f"{val_int:,}".replace(",", " ")
    if show_sign and val_int > 0:
        return f"+{fmt}"
    return fmt

def generate_minimal_html_table(df, market_name, participant_name):
    df_sorted = df.sort_values("report_date", ascending=False).copy()
    html = f"""<div class="cot-table-container">
<h4 style="margin-top: 0; color: #ffffff; font-size: 1.1em; display: flex; justify-content: space-between; margin-bottom: 15px;">
<span>📋 ЧИСТАЯ РАЗНИЦА (LONG - SHORT): {market_name.upper()}</span>
<span style="color: #6b7280; font-size: 0.9em;">Категория: {participant_name.upper()}</span></h4>
<table class="cot-table"><thead><tr>
<th style="text-align: left; font-size: 0.85em; color: #6b7280;">ДАТА</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЦЕНА АКТИВА</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЧИСТАЯ ПОЗИЦИЯ (LONG - SHORT)</th>
</tr></thead><tbody>"""
    
    for _, row in df_sorted.head(30).iterrows():
        dt_str = row["report_date"].strftime("%d.%m.%Y")
        price_str = f"{row['close']:,.2f}".replace(",", " ")
        net = row["net"]
        net_str = fmt_num(net, show_sign=True)
        net_cls = "net-positive" if net >= 0 else "net-negative"
        html += f"""<tr><td class="date-cell" style="text-align: left; padding: 10px 16px;">{dt_str}</td>
<td class="font-mono" style="text-align: right; padding: 10px 16px;">{price_str}</td>
<td style="text-align: right; padding: 10px 16px;">
<span class="{net_cls} font-mono" style="padding: 4px 10px; border-radius: 4px; display: inline-block; min-width: 110px; text-align: right;">{net_str}</span>
</td></tr>"""
    html += "</tbody></table></div>"
    return html

def generate_interpretation_html(interp, market_name, participant_name):
    html = f"""<div class="interp-card">
<h4 style="margin-top: 0; color: #ffffff; font-size: 1.1em; display: flex; justify-content: space-between; margin-bottom: 18px;">
<span>🔍 ИНТЕРПРЕТАЦИЯ: {market_name.upper()}</span>
<span style="color: #6b7280; font-size: 0.9em;">{participant_name}</span></h4>"""

    html += """<div class="interp-section"><div class="interp-label">Что происходит на этой неделе</div>"""
    for line in interp["situation"]: html += f"""<div class="interp-situation-line">{line}</div>"""
    html += "</div><hr class="interp-hr">"

    if interp["active_signals"]:
        html += """<div class="interp-section"><div class="interp-label">Активные сигналы и бэктест</div>"""
        for item in interp["backtest_results"]:
            sig_def = item["def"]
            bt = item["backtest"]
            direction = sig_def["direction"]
            html += f"""<div class="interp-signal-row {direction}"><div style="flex: 1;">
<div class="interp-signal-name">{sig_def['icon']} {sig_def['name']}</div>
<div class="interp-signal-desc">{sig_def['desc']}</div>"""
            if bt and bt["horizons"]:
                html += """<table class="bt-table"><thead><tr>
<th style="text-align: left;">Горизонт</th><th>Случаев</th><th>Win Rate</th><th>Ср. return</th><th>Медиана</th><th>Мин</th><th>Макс</th>
</tr></thead><tbody>"""
                for h in FORWARD_HORIZONS:
                    if h not in bt["horizons"]: continue
                    s = bt["horizons"][h]
                    wr = s["win_rate"]
                    wr_cls = "bt-wr-high" if wr >= 60 else "bt-wr-low" if wr <= 40 else "bt-wr-mid"
                    mean_sign = "+" if s["mean_return"] > 0 else ""
                    med_sign = "+" if s["median_return"] > 0 else ""
                    min_sign = "+" if s["min_return"] > 0 else ""
                    max_sign = "+" if s["max_return"] > 0 else ""
                    html += f"""<tr><td>+{h} нед.</td><td>{s['n']}</td><td class="{wr_cls}">{wr}%</td>
<td>{mean_sign}{s['mean_return']}%</td><td>{med_sign}{s['median_return']}%</td><td>{min_sign}{s['min_return']}%</td><td>{max_sign}{s['max_return']}%</td></tr>"""
                html += "</tbody></table>"
            else:
                html += '<div class="interp-signal-desc" style="margin-top: 6px; color: #6b7280;">⚠️ Недостаточно данных для бэктеста.</div>'
            html += "</div></div>"
        html += "</div>"
    else:
        html += """<div class="interp-section"><div class="interp-label">Активные сигналы</div>
<div class="interp-situation-line" style="color: #6b7280;">Нет активных сигналов. Позиционирование в нейтральной зоне.</div></div>"""
    html += '<hr class="interp-hr">'
    
    verdict_cls = interp["verdict_class"]
    html += f"""<div class="interp-section"><div class="interp-label">Заключение</div>
<div class="interp-verdict {verdict_cls}">"""
    for i, para in enumerate(interp["verdict_paragraphs"]):
        if i > 0: html += '<div style="margin-top: 12px;"></div>'
        html += f'<div style="line-height: 1.7;">{para}</div>'
    html += "</div></div></div>"
    return html

# --- Sidebar ---
st.sidebar.title("⚡ Терминал Кот")

if st.sidebar.button("🔄 Обновить базу данных", use_container_width=True):
    with st.sidebar.status("Обновление данных...", expanded=True) as status:
        status.write("Скачивание последних отчетов CFTC и котировок...")
        try:
            results = update_all_data()
            success_count = sum(1 for v in results.values() if v)
            status.update(label=f"Успешно обновлено {success_count}/{len(results)} рынков!", state="complete", expanded=False)
            st.rerun()
        except Exception as e:
            status.update(label="Ошибка обновления!", state="error")
            st.sidebar.error(str(e))

st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)

st.sidebar.subheader("🧠 Обучение Агента")
with st.sidebar.expander("Загрузить новые знания"):
    tab1, tab2, tab3 = st.tabs(["📄 PDF", "🔗 URL", "📝 Текст"])
    with tab1:
        uploaded_file = st.file_uploader("Загрузить PDF", type="pdf", label_visibility="collapsed")
        if st.button("Изучить PDF", use_container_width=True):
            if uploaded_file:
                with st.spinner("Чтение PDF..."):
                    try:
                        text = extract_text_from_pdf(uploaded_file)
                        absorb_knowledge(text, source_name=uploaded_file.name)
                        st.success("✅ Знания усвоены!")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
    with tab2:
        url_input = st.text_input("Введите ссылку:", label_visibility="collapsed")
        if st.button("Изучить ссылку", use_container_width=True):
            if url_input:
                with st.spinner("Скрапинг сайта..."):
                    try:
                        text = fetch_url_text(url_input)
                        absorb_knowledge(text, source_name=url_input)
                        st.success("✅ Статья добавлена в память!")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
    with tab3:
        raw_text = st.text_area("Вставьте текст:", height=100, label_visibility="collapsed")
        if st.button("Изучить текст", use_container_width=True):
            if raw_text.strip():
                with st.spinner("Анализ..."):
                    try:
                        absorb_knowledge(raw_text, source_name="Ручной ввод")
                        st.success("✅ Текст усвоен!")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

with st.sidebar.expander("Постоянные источники (Real-time)"):
    tracked_sources = load_tracked_sources()
    with st.form("add_source_form", clear_on_submit=True):
        new_source = st.text_input("Добавить URL:", placeholder="https://...")
        if st.form_submit_button("Добавить") and new_source.strip():
            if new_source.strip() not in tracked_sources:
                tracked_sources.append(new_source.strip())
                save_tracked_sources(tracked_sources)
                st.rerun()
    if tracked_sources:
        for idx, src in enumerate(tracked_sources):
            col1, col2 = st.columns([5, 1])
            col1.code(src)
            if col2.button("X", key=f"del_src_{idx}"):
                tracked_sources.remove(src)
                save_tracked_sources(tracked_sources)
                st.rerun()
    else:
        st.info("Нет источников.")

st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)
st.sidebar.subheader("Статус базы данных")
freshness = get_data_freshness()
for market, info in freshness.items():
    if info.get("exists", False):
        status_color = "green" if info["status"] == "Свежие" else "orange"
        st.sidebar.markdown(f"**{market}**: {info['latest_cot']} (:{status_color}[{info['status']}])")

# --- Main Dashboard ---
if not check_data_exists():
    st.title("⚡ Терминал Кот")
    st.info("👋 Локальные файлы данных не обнаружены. Нажмите 'Обновить базу данных' в левом меню.")
    st.stop()

st.title("📊 Глобальный Дашборд Кот")

st.subheader("🌐 Альтернативные Метрики (Smart Money)")
with st.spinner("Загрузка макро-метрик..."):
    alt_data = get_cached_alt_data()

col_fed, col_ins, col_etf = st.columns(3)
with col_fed:
    st.info(f"**ФРС:**\\n{alt_data['fed']}")
with col_ins:
    st.warning(f"**Инсайдеры:**\\n{alt_data['insider']}")
with col_etf:
    st.success(f"**Аномалии ETF:**\\n{alt_data['etf']}")

st.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)

col_sel1, col_sel2, col_sel3 = st.columns(3)
PARTICIPANT_DISPLAY = {
    "Leveraged Funds (Крупные спекулянты)": "Leveraged Funds",
    "Asset Manager (Институционалы)": "Asset Manager",
    "Dealer Intermediary (Дилеры/Посредники)": "Dealer",
    "Retail (Мелкие спекулянты)": "Retail"
}

selected_market = col_sel1.selectbox("Выберите рынок:", list(MARKETS.keys()), index=0)
selected_display = col_sel2.selectbox("Группа трейдеров:", list(PARTICIPANT_DISPLAY.keys()), index=0)
tff_participant = PARTICIPANT_DISPLAY[selected_display]

period_options = {"1 год (52 недели)": 52, "3 года (156 недель)": 156, "Вся история": 0}
selected_period = col_sel3.selectbox("Период на графике:", list(period_options.keys()), index=0)
weeks_to_show = period_options[selected_period]

df = get_market_analysis(selected_market, tff_participant)

if weeks_to_show > 0:
    plot_df = df.tail(weeks_to_show).copy()
else:
    plot_df = df.copy()

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.55, 0.45])
fig.add_trace(go.Scatter(x=plot_df["report_date"], y=plot_df["close"], name="Цена", line=dict(color=MARKETS[selected_market]["color"], width=2.0), mode="lines"), row=1, col=1)

net_values = plot_df["net"]
bar_colors = ["#2ecc71" if val >= 0 else "#e74c3c" for val in net_values]
fig.add_trace(go.Bar(x=plot_df["report_date"], y=net_values, name="Разница", marker_color=bar_colors, marker_line_width=0, hovertemplate="Дата: %{x}<br>Разница: %{y:,.0f}<extra></extra>"), row=2, col=1)

fig.update_layout(height=620, template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=20, r=20, t=30, b=20), hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(bgcolor="#08090a", font_size=12, font_family="Inter"))
for r in [1, 2]:
    fig.update_xaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
fig.update_yaxes(title_text="Цена актива", row=1, col=1)
fig.update_yaxes(title_text="Разница Long - Short", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

interp = run_full_interpretation(df)
interp_html = generate_interpretation_html(interp, selected_market, selected_display)
st.markdown(interp_html, unsafe_allow_html=True)

with st.expander("Посмотреть историю позиций (Таблица)"):
    table_html = generate_minimal_html_table(df, selected_market, selected_display.split(" (")[0])
    st.markdown(table_html, unsafe_allow_html=True)

st.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)

st.subheader("🧠 Синтез ИИ-Агента")
st.markdown(f"Сгенерировать глубокий макро-отчет и стратегию позиционирования для **{selected_market}** на основе текущих COT-метрик и последних новостей.")

if st.button(f"🚀 СГЕНЕРИРОВАТЬ ОТЧЕТ ПО {selected_market.upper()}", type="primary", use_container_width=True):
    with st.spinner("Идет глубокий ИИ-синтез... Это может занять до 30 секунд."):
        try:
            report = generate_holistic_report(selected_market)
            st.markdown("<div class='interp-card'>", unsafe_allow_html=True)
            st.markdown(report)
            st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Ошибка генерации отчета: {e}")
'''

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_app_content)

print("app.py has been rewritten successfully.")
