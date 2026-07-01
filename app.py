import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime

import importlib
import src.config
import src.pipeline
import src.analytics
import src.backtester

# Force reload custom modules to fix Streamlit Cloud memory caching bugs
importlib.reload(src.config)
importlib.reload(src.pipeline)
importlib.reload(src.analytics)
importlib.reload(src.backtester)

from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP
from src.pipeline import update_all_data, get_data_freshness
from src.analytics import get_market_analysis
from src.backtester import run_full_interpretation, SIGNAL_DEFS, FORWARD_HORIZONS

# Page configuration
st.set_page_config(
    page_title="Терминал Кот",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, Professional Fintech Dark CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Hide Streamlit Defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* header {visibility: hidden;} Removed so sidebar expand button works */

    .stApp {
        background-color: #0b0f19; /* Deep institutional blue-grey */
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    h1, h2, h3, h4 {
        color: #f8fafc;
        font-weight: 600;
        letter-spacing: -0.02em;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    
    .neon-hr {
        height: 1px;
        background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.1), rgba(255,255,255,0));
        border: none;
        margin: 20px 0;
    }
    
    /* Professional Glassmorphism Cards */
    .cot-table-container, .interp-card {
        background: rgba(18, 24, 38, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 24px;
        margin-top: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .interp-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
    }
    
    .interp-card {
        border-top: 2px solid rgba(52, 152, 219, 0.5); /* Subtle blue top accent */
    }

    /* Sidebar and Input Styling */
    [data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: rgba(18, 24, 38, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
        border-color: rgba(52, 152, 219, 0.8) !important;
        box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2) !important;
    }
    
    /* Multiselect Styling */
    [data-baseweb="select"] {
        background-color: rgba(18, 24, 38, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
    }
    
    [data-baseweb="tag"] {
        background-color: rgba(52, 152, 219, 0.15) !important;
        border: 1px solid rgba(52, 152, 219, 0.3) !important;
        color: #3498db !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    
    /* Primary Button */
    button[kind="primary"] {
        background: linear-gradient(135deg, #3498db, #2980b9) !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3) !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(52, 152, 219, 0.4) !important;
    }

    /* Minimalist Table Styling */
    .cot-table {
        width: 100%;
        border-collapse: collapse;
        color: #cbd5e1;
        font-size: 0.95em;
        text-align: right;
    }
    .cot-table th, .cot-table td {
        padding: 12px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        vertical-align: middle;
    }
    .cot-table th {
        font-weight: 600;
        color: #94a3b8;
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .cot-table th:first-child, .cot-table td:first-child {
        text-align: left;
    }
    .cot-table tr:hover {
        background-color: rgba(255, 255, 255, 0.02);
    }
    .date-cell {
        color: #f8fafc;
        font-weight: 500;
    }
    .font-mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    
    /* Subtle Green/Red Cells for Net Position */
    .net-positive {
        background-color: rgba(16, 185, 129, 0.1) !important;
        color: #10b981 !important; /* Muted professional green */
        font-weight: 600;
        border-radius: 6px;
    }
    .net-negative {
        background-color: rgba(239, 68, 68, 0.1) !important;
        color: #ef4444 !important; /* Muted professional red */
        font-weight: 600;
        border-radius: 6px;
    }
    
    /* Interpretation Block */
    .interp-section {
        margin-bottom: 20px;
    }
    .interp-section:last-child {
        margin-bottom: 0;
    }
    .interp-label {
        font-size: 0.75em;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .interp-situation-line {
        color: #cbd5e1;
        font-size: 0.95em;
        line-height: 1.6;
        margin: 4px 0;
    }
    
    .interp-signal-row {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 18px;
        margin: 8px 0;
        border-radius: 8px;
        background-color: rgba(255,255,255,0.02);
        border-left: 3px solid #334155;
    }
    .interp-signal-row.bullish {
        border-left-color: #10b981;
    }
    .interp-signal-row.bearish {
        border-left-color: #ef4444;
    }
    .interp-signal-name {
        font-weight: 600;
        color: #f8fafc;
        font-size: 0.95em;
        margin-bottom: 4px;
    }
    .interp-signal-desc {
        font-size: 0.85em;
        color: #94a3b8;
        line-height: 1.5;
    }
    .bt-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        font-size: 0.85em;
    }
    .bt-table th {
        color: #6b7280;
        font-weight: 600;
        font-size: 0.8em;
        text-transform: uppercase;
        padding: 6px 10px;
        border-bottom: 1px solid #1a1d24;
        text-align: right;
    }
    .bt-table th:first-child {
        text-align: left;
    }
    .bt-table td {
        padding: 6px 10px;
        border-bottom: 1px solid #0d0f12;
        text-align: right;
        color: #d1d5db;
        font-family: 'SF Mono', Monaco, Consolas, monospace;
    }
    .bt-table td:first-child {
        text-align: left;
        color: #9ca3af;
    }
    .bt-wr-high { color: #2ecc71; font-weight: 700; }
    .bt-wr-low { color: #e74c3c; font-weight: 700; }
    .bt-wr-mid { color: #f39c12; font-weight: 700; }
    .interp-verdict {
        padding: 16px 20px;
        border-radius: 6px;
        font-size: 1.0em;
        font-weight: 600;
        line-height: 1.6;
    }
    .interp-verdict.bullish {
        background: rgba(39, 174, 96, 0.08);
        border: 1px solid rgba(39, 174, 96, 0.2);
        color: #2ecc71;
    }
    .interp-verdict.bearish {
        background: rgba(192, 57, 43, 0.08);
        border: 1px solid rgba(192, 57, 43, 0.2);
        color: #e74c3c;
    }
    .interp-verdict.neutral {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #9ca3af;
    }
    .interp-hr {
        height: 1px;
        background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.06), rgba(255,255,255,0));
        border: none;
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)

# Helper to check if data files exist
def check_data_exists():
    for market_name in MARKETS.keys():
        cot_file = os.path.join(DATA_DIR_COT, f"{market_name}_futures.csv")
        price_file = os.path.join(DATA_DIR_PRICES, f"{market_name}.csv")
        if not os.path.exists(cot_file) or not os.path.exists(price_file):
            return False
    return True

# Helper to format numbers with spaces
def fmt_num(val, show_sign=False):
    if pd.isna(val):
        return "—"
    val_int = int(round(val))
    sign = "+" if show_sign and val_int > 0 else ""
    fmt = f"{val_int:,}".replace(",", " ")
    if show_sign and val_int > 0:
        return f"+{fmt}"
    return fmt

# Helper to generate the clean historical HTML table
def generate_minimal_html_table(df, market_name, participant_name):
    df_sorted = df.sort_values("report_date", ascending=False).copy()
    
    html = f"""<div class="cot-table-container">
<h4 style="margin-top: 0; color: #ffffff; font-size: 1.1em; display: flex; justify-content: space-between; margin-bottom: 15px;">
<span>📋 ЧИСТАЯ РАЗНИЦА (LONG - SHORT): {market_name.upper()}</span>
<span style="color: #6b7280; font-size: 0.9em;">Категория: {participant_name.upper()}</span>
</h4>
<table class="cot-table">
<thead>
<tr>
<th style="text-align: left; font-size: 0.85em; color: #6b7280;">ДАТА</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЦЕНА АКТИВА</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЛОНГИ (LONG)</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ШОРТЫ (SHORT)</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЧИСТАЯ ПОЗИЦИЯ (LONG - SHORT)</th>
</tr>
</thead>
<tbody>"""
    
    # Display recent 30 rows
    for _, row in df_sorted.head(30).iterrows():
        dt_str = row["report_date"].strftime("%d.%m.%Y")
        price_str = f"{row['close']:,.2f}".replace(",", " ")
        
        net = row["net"]
        net_str = fmt_num(net, show_sign=True)
        net_cls = "net-positive" if net >= 0 else "net-negative"
        
        long_pos = row["long"]
        short_pos = row["short"]
        long_change = row["long_change"]
        short_change = row["short_change"]
        
        long_str = f"{long_pos:,.0f}".replace(",", " ")
        short_str = f"{short_pos:,.0f}".replace(",", " ")
        
        long_change_str = fmt_num(long_change, show_sign=True)
        short_change_str = fmt_num(short_change, show_sign=True)
        
        html += f"""
<tr>
<td class="date-cell" style="text-align: left; padding: 10px 16px;">{dt_str}</td>
<td class="font-mono" style="text-align: right; padding: 10px 16px;">{price_str}</td>
<td style="text-align: right; padding: 10px 16px;">
<span class="font-mono" style="color: #10b981;">{long_str}</span> <span style="font-size: 0.85em; color: #6b7280;">({long_change_str})</span>
</td>
<td style="text-align: right; padding: 10px 16px;">
<span class="font-mono" style="color: #ef4444;">{short_str}</span> <span style="font-size: 0.85em; color: #6b7280;">({short_change_str})</span>
</td>
<td style="text-align: right; padding: 10px 16px;">
<span class="{net_cls} font-mono" style="padding: 4px 10px; border-radius: 4px; display: inline-block; min-width: 110px; text-align: right;">{net_str}</span>
</td>
</tr>"""
        
    html += """
</tbody>
</table>
</div>"""
    return html

# Helper to generate the interpretation HTML block
def generate_interpretation_html(interp, market_name, participant_name):
    html = f"""<div class="interp-card">
<h4 style="margin-top: 0; color: #ffffff; font-size: 1.1em; display: flex; justify-content: space-between; margin-bottom: 18px;">
<span>🔍 ИНТЕРПРЕТАЦИЯ: {market_name.upper()}</span>
<span style="color: #6b7280; font-size: 0.9em;">{participant_name}</span>
</h4>"""

    # Section 1: Situation — what happened this week
    html += """<div class="interp-section">
<div class="interp-label">Что происходит на этой неделе</div>"""
    for line in interp["situation"]:
        html += f"""<div class="interp-situation-line">{line}</div>"""
    html += "</div>"

    html += "</div>"  # close interp-card
    return html

def draw_cot_chart(plot_df, market_name, participant_name, chart_height=650):
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.06,
        row_heights=[0.40, 0.30, 0.30]
    )
    # 1. Price
    fig.add_trace(go.Scatter(
        x=plot_df["report_date"], 
        y=plot_df["close"], 
        name="Цена", 
        line=dict(color=MARKETS.get(market_name, {}).get("color", "#ffffff"), width=2.0), 
        mode="lines"
    ), row=1, col=1)
    
    # Load backtest thresholds for active coloring and placement
    from src.analytics import load_backtest_thresholds
    thresh = load_backtest_thresholds(market_name, participant_name)
    z_up = thresh["zscore_upper"]
    z_low = thresh["zscore_lower"]
    pct_up = thresh["percentile_upper"]
    pct_low = thresh["percentile_lower"]
    rule_type = thresh["rule_type"]
    
    color_up = "rgba(231, 76, 60, 0.6)" if rule_type == "contrarian" else "rgba(46, 204, 113, 0.6)"
    color_low = "rgba(46, 204, 113, 0.6)" if rule_type == "contrarian" else "rgba(231, 76, 60, 0.6)"
    
    # 2. Z-Score (52w) of Positions
    zscore_values = plot_df["net_pct_oi_zscore_52w"]
    fig.add_trace(go.Scatter(
        x=plot_df["report_date"], 
        y=zscore_values, 
        name="Z-Score позиций (52н)", 
        line=dict(color="#f39c12", width=2.0), 
        mode="lines"
    ), row=2, col=1)
    
    # Add horizontal lines for Z-Score thresholds
    fig.add_hline(y=z_up, line_dash="dash", line_color=color_up, row=2, col=1)
    fig.add_hline(y=0.0, line_dash="dot", line_color="rgba(255, 255, 255, 0.3)", row=2, col=1)
    fig.add_hline(y=z_low, line_dash="dash", line_color=color_low, row=2, col=1)
    
    # 3. Percentile (52w) of Positions
    pct_values = plot_df["cot_index_net_pct_oi_52w"]
    fig.add_trace(go.Scatter(
        x=plot_df["report_date"], 
        y=pct_values, 
        name="Перцентиль позиций (52н)", 
        line=dict(color="#3498db", width=2.0), 
        mode="lines"
    ), row=3, col=1)
    
    # Add horizontal lines for Percentile thresholds
    fig.add_hline(y=pct_up, line_dash="dash", line_color=color_up, row=3, col=1)
    fig.add_hline(y=50.0, line_dash="dot", line_color="rgba(255, 255, 255, 0.3)", row=3, col=1)
    fig.add_hline(y=pct_low, line_dash="dash", line_color=color_low, row=3, col=1)
    
    fig.update_layout(
        height=chart_height, 
        template="plotly_dark", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
        margin=dict(l=20, r=20, t=30, b=20), 
        hovermode="x unified", 
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        hoverlabel=dict(bgcolor="#08090a", font_size=12, font_family="Inter")
    )

    
    for r in [1, 2, 3]:
        fig.update_xaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
        
    fig.update_yaxes(title_text="Цена актива", row=1, col=1)
    fig.update_yaxes(title_text="Z-Score позиций", row=2, col=1)
    fig.update_yaxes(title_text="Перцентиль позиций (%)", row=3, col=1)
    return fig



def draw_flows_chart(plot_df, market_name, chart_height=750):
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05,
        row_heights=[0.31, 0.23, 0.23, 0.23]
    )
    
    # --- Dynamic WoW Net % OI Spike Overlays (Top/Bottom 5% changes) - Anomaly Indicators ---
    wow_series = plot_df["wow_change_net_pct_oi"].dropna()
    if len(wow_series) > 10:
        q95 = wow_series.quantile(0.95)
        q05 = wow_series.quantile(0.05)
        for _, row in plot_df.iterrows():
            val = row.get("wow_change_net_pct_oi", 0)
            if val >= q95:
                fig.add_vline(x=row["report_date"], line_width=10, line_color="rgba(46, 204, 113, 0.15)", row="all", col=1, layer="below")
            elif val <= q05:
                fig.add_vline(x=row["report_date"], line_width=10, line_color="rgba(231, 76, 60, 0.15)", row="all", col=1, layer="below")

    # Row 1: Price
    fig.add_trace(go.Scatter(
        x=plot_df["report_date"], 
        y=plot_df["close"], 
        name="Цена", 
        line=dict(color=MARKETS.get(market_name, {}).get("color", "#ffffff"), width=2.0), 
        mode="lines"
    ), row=1, col=1)
    
    # Row 2: Long Flow (Приток/Отток в лонг)
    long_flow = plot_df["long_change"]
    long_colors = ["#2ecc71" if val >= 0 else "#e74c3c" for val in long_flow]
    fig.add_trace(go.Bar(
        x=plot_df["report_date"], 
        y=long_flow, 
        name="Приток/Отток в Лонг", 
        marker_color=long_colors, 
        marker_line_width=0, 
        hovertemplate="Дата: %{x}<br>Лонг поток: %{y:+.0f} контр.<extra></extra>"
    ), row=2, col=1)
    fig.add_hline(y=0.0, line_color="rgba(255, 255, 255, 0.3)", row=2, col=1)
    
    # Row 3: Short Flow (Приток/Отток в шорт)
    short_flow = plot_df["short_change"]
    short_colors = ["#2ecc71" if val >= 0 else "#e74c3c" for val in short_flow]
    fig.add_trace(go.Bar(
        x=plot_df["report_date"], 
        y=short_flow, 
        name="Приток/Отток в Шорт", 
        marker_color=short_colors, 
        marker_line_width=0, 
        hovertemplate="Дата: %{x}<br>Шорт поток: %{y:+.0f} контр.<extra></extra>"
    ), row=3, col=1)
    fig.add_hline(y=0.0, line_color="rgba(255, 255, 255, 0.3)", row=3, col=1)
    
    # Row 4: Net Delta (Чистая Дельта)
    net_delta = plot_df["wow_change_net"]
    bar_colors = ["#2ecc71" if val >= 0 else "#e74c3c" for val in net_delta]
    fig.add_trace(go.Bar(
        x=plot_df["report_date"], 
        y=net_delta, 
        name="Чистая Дельта", 
        marker_color=bar_colors, 
        marker_line_width=0, 
        hovertemplate="Дата: %{x}<br>Дельта: %{y:+.0f} контр.<extra></extra>"
    ), row=4, col=1)
    fig.add_hline(y=0.0, line_color="rgba(255, 255, 255, 0.3)", row=4, col=1)
    
    fig.update_layout(
        height=chart_height, 
        template="plotly_dark", 
        showlegend=True, 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
        margin=dict(l=20, r=20, t=30, b=20), 
        hovermode="x unified", 
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        hoverlabel=dict(bgcolor="#08090a", font_size=12, font_family="Inter")
    )
    
    for r in [1, 2, 3, 4]:
        fig.update_xaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#15181f", row=r, col=1)
        
    fig.update_yaxes(title_text="Цена", row=1, col=1)
    fig.update_yaxes(title_text="Лонг Поток", row=2, col=1)
    fig.update_yaxes(title_text="Шорт Поток", row=3, col=1)
    fig.update_yaxes(title_text="Чистая Дельта", row=4, col=1)
    
    return fig# --- Sidebar ---
st.sidebar.title("⚡ Терминал Кот")

app_mode = st.sidebar.radio("Навигация:", ["📊 Терминал COT", "📈 Интерактивный Дашборд", "🎓 Обучение кота", "📅 Календарь событий", "📖 Паспорт Терминала"])

if app_mode == "🎓 Обучение кота":
    from src.agent import (
        extract_text_from_pdf, 
        fetch_url_text, 
        absorb_knowledge, 
        load_knowledge_base,
        analyze_single_source,
        load_tracked_sources,
        save_tracked_sources
    )
    
    st.title("🎓 Обучение ИИ-Агента Кота")
    st.markdown("Здесь вы можете добавлять официальные источники, новостные каналы и отчеты, которые агент будет регулярно читать для составления макро-отчетов.")
    
    st.subheader("1. Обучение агента (Разовая загрузка знаний)")
    
    tab1, tab2, tab3 = st.tabs(["📄 PDF Отчет", "🔗 Ссылка (URL)", "📝 Текст"])
    
    with tab1:
        uploaded_file = st.file_uploader("Загрузить PDF (Bank Report, Notion и т.д.)", type="pdf")
        if st.button("Изучить PDF", use_container_width=True):
            if uploaded_file is not None:
                with st.spinner("Чтение PDF и интеграция в базу знаний..."):
                    try:
                        text = extract_text_from_pdf(uploaded_file)
                        absorb_knowledge(text, source_name=uploaded_file.name)
                        st.success("✅ Знания успешно усвоены!")
                        with st.spinner("Формируем мгновенное заключение по этому источнику..."):
                            conclusion = analyze_single_source(text, source_name=uploaded_file.name)
                            st.markdown("#### Вывод по этому источнику:")
                            st.info(conclusion)
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.warning("Сначала выберите файл.")
                
    with tab2:
        url_input = st.text_input("Введите ссылку на статью или новость:")
        if st.button("Изучить ссылку", use_container_width=True):
            if url_input:
                with st.spinner("Скрапинг сайта и интеграция в базу знаний..."):
                    try:
                        text = fetch_url_text(url_input)
                        absorb_knowledge(text, source_name=url_input)
                        st.success("✅ Статья прочитана и добавлена в память!")
                        with st.spinner("Формируем мгновенное заключение по этому источнику..."):
                            conclusion = analyze_single_source(text, source_name=url_input)
                            st.markdown("#### Вывод по этому источнику:")
                            st.info(conclusion)
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.warning("Введите ссылку.")
                
    with tab3:
        raw_text = st.text_area("Вставьте любой текст для анализа:", height=150)
        if st.button("Изучить текст", use_container_width=True):
            if raw_text.strip():
                with st.spinner("Анализ текста..."):
                    try:
                        absorb_knowledge(raw_text, source_name="Ручной ввод пользователя")
                        st.success("✅ Текст усвоен!")
                        with st.spinner("Формируем мгновенное заключение по этому источнику..."):
                            conclusion = analyze_single_source(raw_text, source_name="Ручной ввод пользователя")
                            st.markdown("#### Вывод по этому источнику:")
                            st.info(conclusion)
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.warning("Текст пуст.")
                
    st.markdown("---")
    st.subheader("2. Постоянные источники (Официальные каналы и отчеты)")
    st.markdown("Агент будет **автоматически парсить эти источники каждый раз** при генерации дашборда и репортов:")
    
    tracked_sources = load_tracked_sources()
    
    with st.form("add_source_form", clear_on_submit=True):
        col_src1, col_src2 = st.columns([4, 1])
        new_source = col_src1.text_input("Добавить новый источник для отслеживания (URL):", placeholder="https://...")
        add_btn = col_src2.form_submit_button("Добавить")
        if add_btn and new_source.strip():
            if new_source.strip() not in tracked_sources:
                tracked_sources.append(new_source.strip())
                save_tracked_sources(tracked_sources)
                st.rerun()
                
    with st.expander("Показать/скрыть текущие источники", expanded=False):
        if tracked_sources:
            for idx, src in enumerate(tracked_sources):
                col1, col2 = st.columns([5, 1])
                col1.code(src)
                if col2.button("Удалить", key=f"del_src_{idx}"):
                    tracked_sources.remove(src)
                    save_tracked_sources(tracked_sources)
                    st.rerun()
        else:
            st.info("Нет отслеживаемых источников. Агент будет опираться только на свою базу и новости.")
            
    st.markdown("---")
    st.subheader("3. База Знаний Агента")
    with st.expander("Посмотреть текущую память агента (отредактируйте файл data/knowledge_base.md напрямую при необходимости)", expanded=True):
        kb_content = load_knowledge_base()
        st.markdown(kb_content)
        
    st.stop()

elif app_mode == "📅 Календарь событий":
    st.title("📅 Календарь макроэкономических событий")
    st.markdown("Здесь публикуются результаты ключевых событий, их вероятные исходы и макроэкономические последствия.")
    
    from src.calendar import fetch_economic_calendar, analyze_calendar_events, get_event_description
    
    # Filter UI
    st.sidebar.markdown("### Настройки календаря")
    impact_filter = st.sidebar.multiselect(
        "Важность событий:",
        ["🔴 Высокая", "🟠 Средняя", "🟡 Низкая", "⚪ Нет (Holiday)"],
        default=["🔴 Высокая", "🟠 Средняя"]
    )
    
    with st.spinner("Загрузка данных экономического календаря..."):
        all_events = fetch_economic_calendar()
        
    if isinstance(all_events, dict) and "error" in all_events:
        st.error(f"Не удалось загрузить календарь: {all_events['error']}")
    elif not all_events:
        st.info("На этой неделе нет макроэкономических событий.")
    else:
        events = [ev for ev in all_events if ev["impact"] in impact_filter]
        
        if not events:
            st.warning("Нет событий, подходящих под выбранные фильтры.")
        else:
            st.success(f"Отображено {len(events)} событий.")
            
            # Action button to trigger AI analysis
            if st.button("🤖 Сгенерировать ИИ-Анализ Недели (для отфильтрованных событий)", type="primary"):
                with st.spinner("ИИ анализирует предстоящие события..."):
                    analysis = analyze_calendar_events(events)
                    st.markdown("---")
                    st.markdown("## 🧠 ИИ-Анализ предстоящих событий")
                    st.markdown("<div class='interp-card'>", unsafe_allow_html=True)
                    st.markdown(analysis)
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown("---")
            
            for ev in events:
                st.markdown(f"### {ev['date']} {ev['time']} — {ev['currency']} | {ev['event']}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Важность", ev['impact'])
                col2.metric("Прогноз", ev['forecast'] if ev['forecast'] else "—")
                col3.metric("Предыдущее", ev['previous'] if ev['previous'] else "—")
                
                with st.expander("📖 Описание события"):
                    desc = get_event_description(ev['event'])
                    st.info(desc)
                    
                st.markdown("<hr class='interp-hr'>", unsafe_allow_html=True)
            
    st.stop()

elif app_mode == "📈 Интерактивный Дашборд":
    st.title("📈 Интерактивный Дашборд и Главный Репорт")
    st.markdown("Сюда стягивается вся информация, графики, и здесь же генерируется один отчетливый репорт с настроением фондов, банков и учетом новостей.")
    
    from src.config import MARKETS
    from src.macro_data import DATA_DIR_MACRO
    from src.agent import generate_dashboard_report, generate_holistic_report
    
    st.sidebar.markdown("### Настройки портфеля")
    popular_assets = ["BTC-USD", "SPY", "GC=F", "QQQ", "GLD", "ETH-USD", "EURUSD=X", "DX-Y.NYB", "^TNX"]
    for m in MARKETS.keys():
        if m not in popular_assets:
            popular_assets.append(m)
            
    user_assets_list = st.sidebar.multiselect(
        "Твои активы:", 
        options=popular_assets,
        default=["BTC-USD", "SPY", "GC=F"]
    )
    user_assets_input = ", ".join(user_assets_list)
    
    st.sidebar.markdown("### Доп. источники для агента")
    extra_urls_input = st.sidebar.text_area("Срочные новости (URL, каждая с новой строки):", height=100)
    
    if st.button("🚀 СГЕНЕРИРОВАТЬ ДАШБОРД И ПОЛНЫЙ ОТЧЕТ", use_container_width=True, type="primary"):
        with st.spinner("ИИ анализирует данные, собирает графики и читает новости... Это займет около минуты."):
            json_data = generate_dashboard_report(user_assets_input, extra_urls_input)
            try:
                holistic_report = generate_holistic_report(user_assets_input, extra_urls_input)
            except Exception as e:
                holistic_report = f"Не удалось сгенерировать расширенный отчет: {e}"
            
            if "error" in json_data:
                st.error(f"Ошибка при генерации JSON: {json_data['error']}")
            else:
                metrics = json_data.get("metrics", {})
                
                # 1. MACRO: WALCL
                st.markdown("### 🏦 Баланс ФРС (WALCL)")
                try:
                    df_walcl = pd.read_csv(os.path.join(DATA_DIR_MACRO, "WALCL.csv"))
                    df_walcl['date'] = pd.to_datetime(df_walcl['date'])
                    fig_walcl = go.Figure(go.Scatter(x=df_walcl['date'], y=df_walcl['value'], line=dict(color='#2ecc71', width=2), fill='tozeroy'))
                    fig_walcl.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_walcl, use_container_width=True)
                except:
                    st.warning("График WALCL недоступен. Нажмите 'Обновить Макро-Данные' на вкладке Макро.")
                st.markdown(f"<div class='interp-card' style='margin-top: 0;'><div class='interp-label'>Вывод ИИ</div>{metrics.get('WALCL', 'Нет комментария')}</div>", unsafe_allow_html=True)
                
                # 2. MACRO: M2
                st.markdown("### 💵 Денежная масса (M2SL)")
                try:
                    df_m2 = pd.read_csv(os.path.join(DATA_DIR_MACRO, "M2SL.csv"))
                    df_m2['date'] = pd.to_datetime(df_m2['date'])
                    fig_m2 = go.Figure(go.Scatter(x=df_m2['date'], y=df_m2['value'], line=dict(color='#3498db', width=2), fill='tozeroy'))
                    fig_m2.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_m2, use_container_width=True)
                except:
                    st.warning("График M2 недоступен.")
                st.markdown(f"<div class='interp-card' style='margin-top: 0;'><div class='interp-label'>Вывод ИИ</div>{metrics.get('M2SL', 'Нет комментария')}</div>", unsafe_allow_html=True)
                
                # 3. MACRO: RATES
                st.markdown("### 📈 Процентные ставки (10Y & 2Y)")
                try:
                    df_10y = pd.read_csv(os.path.join(DATA_DIR_MACRO, "DGS10.csv"))
                    df_2y = pd.read_csv(os.path.join(DATA_DIR_MACRO, "DGS2.csv"))
                    df_10y['date'] = pd.to_datetime(df_10y['date'])
                    df_2y['date'] = pd.to_datetime(df_2y['date'])
                    merged_yields = pd.merge(df_10y, df_2y, on='date', suffixes=('_10y', '_2y'))
                    merged_yields['spread'] = merged_yields['value_10y'] - merged_yields['value_2y']
                    
                    fig_yield = go.Figure(go.Scatter(x=merged_yields['date'], y=merged_yields['spread'], line=dict(color='#e74c3c', width=2), fill='tozeroy'))
                    fig_yield.add_hline(y=0, line_dash="dash", line_color="white")
                    fig_yield.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_yield, use_container_width=True)
                except:
                    st.warning("График ставок недоступен.")
                st.markdown(f"<div class='interp-card' style='margin-top: 0;'><div class='interp-label'>Вывод ИИ</div>{metrics.get('RATES', 'Нет комментария')}</div>", unsafe_allow_html=True)
                
                # 4. COT
                st.markdown("### 🐋 Позиции Крупных Игроков (COT)")
                parsed_assets = [a.strip() for a in user_assets_input.split(",") if a.strip()]
                for asset in parsed_assets:
                    if asset in MARKETS:
                        try:
                            df_am = get_market_analysis(asset, "Asset Manager", use_combined=use_combined)
                            if not df_am.empty:
                                st.markdown(f"**{asset} (Asset Managers - Институционалы)**")
                                fig_am = draw_cot_chart(df_am.tail(52), asset, "Asset Manager")
                                st.plotly_chart(fig_am, use_container_width=True)
                                
                            df_lf = get_market_analysis(asset, "Leveraged Funds", use_combined=use_combined)
                            if not df_lf.empty:
                                st.markdown(f"**{asset} (Leveraged Funds - Спекулянты)**")
                                fig_lf = draw_cot_chart(df_lf.tail(52), asset, "Leveraged Funds")
                                st.plotly_chart(fig_lf, use_container_width=True)

                        except:
                            pass
                st.markdown(f"<div class='interp-card' style='margin-top: 0;'><div class='interp-label'>Вывод ИИ</div>{metrics.get('COT', 'Нет комментария')}</div>", unsafe_allow_html=True)
                
                # 5. OPTIONS & ETFS
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 🎲 Опционы")
                    st.markdown(f"<div class='interp-card' style='margin-top: 0;'>{metrics.get('OPTIONS', 'Нет комментария').replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown("### 💸 ETF Потоки")
                    st.markdown(f"<div class='interp-card' style='margin-top: 0;'>{metrics.get('ETFS', 'Нет комментария').replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                
                # 6. CONCLUSION
                st.markdown("---")
                st.markdown("## 🧠 КРАТКОЕ РЕЗЮМЕ")
                st.markdown(f"<div class='interp-card' style='border-color: #3498db; background-color: rgba(52, 152, 219, 0.05);'><div style='font-size: 1.1em; line-height: 1.6;'>{json_data.get('conclusion', 'Нет итогового отчета.').replace(chr(10), '<br>')}</div></div>", unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("## 📜 РАЗВЕРНУТЫЙ МАКРО-ОТЧЕТ КОТА")
                st.markdown("<div class='interp-card'>", unsafe_allow_html=True)
                st.markdown(holistic_report)
                st.markdown("</div>", unsafe_allow_html=True)
    
    st.stop()

elif app_mode == "📖 Паспорт Терминала":
    st.title("📖 Паспорт Терминала: Методология и Данные")
    st.markdown("### Общие сведения")
    st.markdown("Терминал представляет собой агрегатор макроэкономических, сентиментных и позиционных данных. Цель системы — сбор и первичная обработка биржевой статистики для формирования вероятностных моделей поведения активов без использования классического технического анализа (индикаторов).")
    
    st.markdown("---")
    st.markdown("### 1. Источники Данных")
    st.markdown("""
- **CFTC (Commodity Futures Trading Commission)**: Еженедельные отчеты Commitments of Traders (COT). Используются форматы Legacy (Futures Only) и TFF (Traders in Financial Futures).
- **FRED (Federal Reserve Economic Data)**: API Федерального Резервного Банка Сент-Луиса. Забор макроэкономической статистики (баланс ФРС, денежная масса, инфляция, безработица).
- **Yahoo Finance**: Источник спотовых и фьючерсных котировок, а также цепей опционов (Option Chains) для американского фондового рынка.
""")

    st.markdown("---")
    st.markdown("### 2. Отслеживаемые Метрики")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Макроэкономика и Ликвидность**
- `WALCL` (Total Assets): Текущий баланс ФРС США. Указывает на изъятие (QT) или вливание (QE) долларовой ликвидности.
- `M2SL`: Денежная масса M2.
- `DGS10` и `DGS2`: Доходности 10- и 2-летних гособлигаций США. Спред между ними используется как индикатор инверсии кривой доходности.
""")
    with col2:
        st.markdown("""
**Опционный Рынок**
- `Put/Call Ratio (PCR)`: Соотношение объема торгов пут- и колл-опционами.
- `Max Pain`: Уровень страйка с максимальным объемом открытого интереса, экспирация на котором принесет наибольшие убытки покупателям опционов.
- `Volume Anomalies`: Фиксация ситуаций, где дневной объем торгов страйка превышает открытый интерес (Volume > 2 * Open Interest).
""")

    st.markdown("""
**Позиционирование (COT)**
Данные разбиваются на 4 ключевые группы участников (согласно TFF):
- `Dealer Intermediary`: Маркет-мейкеры, хеджирующие риски.
- `Asset Manager`: Институциональные инвесторы (пенсионные фонды, ETF), торгующие без кредитного плеча.
- `Leveraged Funds`: Хедж-фонды и спекулянты, использующие плечо (часто торгуют по тренду).
- `Retail`: Мелкие некоммерческие трейдеры.
""")

    st.markdown("---")
    st.markdown("### 3. Алгоритмы анализа и Бэктестинга")
    st.markdown("""
Модуль бэктестинга (`src/backtester.py`) анализирует историю чистой позиции (Net Position = Long - Short) каждого участника и генерирует сигналы на основе перцентилей и Z-Score за периоды от 1 до 3 лет:
- **Экстремумы позиционирования**: Если группа (например, Asset Managers) достигает 100-го перцентиля (максимальный лонг за год), система помечает это как потенциальную точку разворота.
- **Расчет Win Rate**: Алгоритм проходит по историческим данным и проверяет, куда шла цена через 4, 12, 26 и 52 недели после появления аналогичного сигнала. Расчитываются средний/медианный возврат и вероятность отработки.
""")

    st.markdown("---")
    st.markdown("---")
    st.markdown("### 4. Роль ИИ-Агента и Структура Приложения")
    st.markdown("""
- **LLM (Gemini 2.5 Pro/Flash)** используется как центральный мозг для синтеза данных.
- **Интерактивный Дашборд**: ИИ сводит разрозненные числовые аномалии (COT + Макро + Опционы) и свежие новости в единый масштабный текстовый отчет.
- **Календарь событий**: ИИ автоматически анализирует предстоящие макроэкономические события (из встроенного календаря ForexFactory) и формирует сценарии реакции рынка (ВВЕРХ/ВНИЗ).
- **Обучение кота**: Пользователь может загружать собственные PDF-отчеты или ссылки на статьи, а также управлять списком "Постоянных источников", которые агент проверяет автоматически.
""")

    st.stop()


st.sidebar.markdown("Анализ позиционирования крупных участников рынка.")

# Mapping Russian labels to ASCII dictionary keys to prevent Windows encoding bugs
PARTICIPANT_DISPLAY = {
    "Leveraged Funds (Крупные спекулянты)": "Leveraged Funds",
    "Asset Manager (Институционалы)": "Asset Manager",
    "Dealer Intermediary (Дилеры/Посредники)": "Dealer",
    "Retail (Мелкие спекулянты)": "Retail"
}

st.sidebar.subheader("Параметры анализа")
selected_market = st.sidebar.selectbox("Выберите рынок:", list(MARKETS.keys()), index=0)
selected_display = st.sidebar.selectbox("Группа трейдеров:", list(PARTICIPANT_DISPLAY.keys()), index=0)
tff_participant = PARTICIPANT_DISPLAY[selected_display]

selected_report_type = st.sidebar.radio("Тип отчета COT:", ["Только фьючерсы", "Фьючерсы + Опционы"], index=1)
use_combined = (selected_report_type == "Фьючерсы + Опционы")

# Select period
period_options = {
    "1 месяц (4 недели)": 4,
    "3 месяца (12 недель)": 12,
    "6 месяцев (26 недель)": 26,
    "1 год (52 недели)": 52,
    "3 года (156 недель)": 156,
    "Вся история": 0
}
selected_period = st.sidebar.radio("Период на графике:", list(period_options.keys()), index=3)
weeks_to_show = period_options[selected_period]

st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)

# Data freshness status
st.sidebar.subheader("База данных")
freshness = get_data_freshness()
for market, info in freshness.items():
    if info.get("exists", False):
        status_color = "green" if info["status"] == "Свежие" else "orange"
        st.sidebar.markdown(f"**{market}**: {info['latest_cot']} (:{status_color}[{info['status']}])")

st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)

# Update button
if st.sidebar.button("🔄 Обновить базу данных", use_container_width=True):
    with st.sidebar.status("Обновление данных...", expanded=True) as status:
        status.write("Скачивание отчетов COT...")
        try:
            results = update_all_data()
            import time
            success_count = sum(1 for v in results.values() if v)
            status.update(label=f"Успешно обновлено {success_count}/{len(results)} рынков! Если даты не изменились - новых данных еще нет на CFTC.", state="complete", expanded=True)
            time.sleep(3)
            st.rerun()
        except Exception as e:
            status.update(label="Ошибка обновления!", state="error")
            st.sidebar.error(str(e))

# App Body
if not check_data_exists():
    st.title("⚡ Терминал Кот")
    st.info("👋 Локальные файлы данных не обнаружены. Пожалуйста, нажмите кнопку **'Обновить базу данных'** на панели слева для скачивания истории.")
else:
    # Load and calculate metrics for the selected market
    df = get_market_analysis(selected_market, tff_participant, use_combined=use_combined)
    
    st.title(f"📊 {selected_market}")
    st.caption(f"Рынок: **{MARKETS[selected_market]['display_name']}** | Категория: **{selected_display}**")
    
    # 0. Asset and Positioning Metrics Columns
    latest_row = df.iloc[-1]
    price_now = latest_row["close"]
    price_prev = df["close"].iloc[-2] if len(df) > 1 else price_now
    price_change = price_now - price_prev
    price_change_pct = (price_change / price_prev) * 100 if price_prev > 0 else 0.0
    
    pos_z = latest_row.get("net_pct_oi_zscore_52w", 0.0)
    pos_pct = latest_row.get("cot_index_net_pct_oi_52w", 50.0)
    if pd.isna(pos_z): pos_z = 0.0
    if pd.isna(pos_pct): pos_pct = 50.0
    
    if pos_pct >= 95.0 and pos_z >= 2.0:
        pos_state = "🔴 Перегрев лонгов"
    elif pos_pct >= 80.0 or pos_z >= 1.5:
        pos_state = "🟡 Перекупленность"
    elif pos_pct <= 20.0 or pos_z <= -1.5:
        pos_state = "🟢 Перепроданность"
    else:
        pos_state = "⚪ Нейтрально"
        
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(
            label="Цена актива",
            value=f"${price_now:,.2f}" if price_now >= 1.0 else f"${price_now:,.4f}",
            delta=f"{price_change_pct:+.2f}% за неделю",
            delta_color="normal"
        )
    with m_col2:
        st.metric(
            label="Z-Score позиций (52н)",
            value=f"{pos_z:.2f} std",
            delta="Сдвиг чистой позы от средней"
        )
    with m_col3:
        st.metric(
            label="Перцентиль позиций (52н)",
            value=f"{pos_pct:.1f}%",
            delta="Относительное сентимент-положение"
        )
    with m_col4:
        st.metric(
            label="Состояние позиций (1г)",
            value=pos_state,
            delta="Границы: 80% / 20%"
        )


    
    # Slice data for chart
    if weeks_to_show > 0:
        plot_df = df.tail(weeks_to_show).copy()
    else:
        plot_df = df.copy()
        
    # Rebuild Plotly chart using the helper function
    fig = draw_cot_chart(plot_df, selected_market, tff_participant, chart_height=650)
    st.plotly_chart(fig, use_container_width=True)


    
    st.markdown("### 🌊 Осциллятор Настроений (COT Index Net & Net % OI)")
    fig2 = draw_flows_chart(plot_df, selected_market, chart_height=750)
    st.plotly_chart(fig2, use_container_width=True)
    
    # 3. Simplified Historical HTML Table
    table_html = generate_minimal_html_table(df, selected_market, selected_display.split(" (")[0])
    st.markdown(table_html, unsafe_allow_html=True)
    
    # 4. Advanced Holistic AI Report
    st.markdown(f"### 🤖 Аналитический репорт ИИ")
    from src.analytics import generate_holistic_report
    holistic_report = generate_holistic_report(selected_market, use_combined=use_combined)
    st.info(holistic_report)

# Force reload 1
