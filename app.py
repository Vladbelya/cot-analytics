import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime, timedelta

import importlib
import src.config
import src.pipeline
import src.analytics
import src.backtester
import src.gex_engine

# Force reload custom modules to fix Streamlit Cloud memory caching bugs
importlib.reload(src.config)
importlib.reload(src.pipeline)
importlib.reload(src.analytics)
importlib.reload(src.backtester)
importlib.reload(src.gex_engine)

from src.config import MARKETS, DATA_DIR_COT, DATA_DIR_PRICES, PARTICIPANTS_MAP
from src.pipeline import update_all_data, get_data_freshness
from src.analytics import get_market_analysis
from src.backtester import run_full_interpretation, SIGNAL_DEFS, FORWARD_HORIZONS
from src.gex_engine import get_aggregate_gex_data, calculate_gex_metrics, parse_expiry_date_robust, fetch_btc_price_history_binance

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

# Helper to generate the backtest statistics HTML table
def display_backtest_stats_table(df, market_name, participant_name):
    from src.backtester import run_backtests_for_all_signals
    stats = run_backtests_for_all_signals(df)
    
    if not stats:
        st.write("Нет достаточного количества исторических данных для расчета бэктестов.")
        return
        
    # --- Backtest Explanation Cheat Sheet ---
    if participant_name == "Asset Manager":
        group_desc = "🏛️ **Институционалы (Asset Managers)** — это долгосрочные 'умные деньги' (пенсионные фонды, ETF). Они торгуют без плеча."
        logic_desc = "Их логика — **следование за трендом (Trend-Following)**. Если институционалы накапливают покупки, цена исторически растет; если они массово выходят — падает."
        recommendation = "🟢 **Рекомендация бэктеста:** Повторять действия за ними. Их покупки статистически подтверждают силу тренда."
    elif participant_name == "Leveraged Funds":
        group_desc = "🚀 **Хедж-фонды (Leveraged Funds)** — это крупные спекулянты с плечом. Они агрессивно гонятся за трендом."
        logic_desc = "Их логика — **контр-индикатор на экстремумах (Contrarian)**. Они часто покупают на самом верху или шортят на самом дне. Когда их позиции достигают пиков перегрузки, это предвещает разворот рынка (шорт-сквиз или лонг-сквиз)."
        recommendation = "⚠️ **Рекомендация бэктеста:** Играть в контр-тренд. Покупать, когда спекулянты в максимальном шорте, и продавать, когда они в максимальном лонге."
    elif participant_name == "Retail":
        group_desc = "👥 **Ритейл (Retail)** — мелкие спекулянты (толпа). Часто поддаются эмоциям (FOMO и панике)."
        logic_desc = "Их логика — **контр-индикатор (Contrarian)**. Толпа обычно покупает на самом пике цены и паникует (шортит) на самом дне."
        recommendation = "⚠️ **Рекомендация бэктеста:** Играть строго против толпы на экстремумах."
    else: # Dealer
        group_desc = "🏦 **Дилеры (Dealers)** — маркет-мейкеры (крупные банки). Они обеспечивают ликвидность на рынке."
        logic_desc = "Их логика — **следование/хеджирование (Follow)**. Их позиции часто зеркальны клиентам, но они выстраивают защиту на уровнях."
        recommendation = "⚪ **Рекомендация бэктеста:** Использовать для оценки институционального спроса."
        
    # Find a signal to highlight in the helper card
    highlight_text = ""
    for s in stats:
        if s["key"] == "bullish_divergence" and 4 in s["horizons"]:
            wr_4 = s["horizons"][4]["win_rate"]
            highlight_text = f"Например, паттерн **Бычья дивергенция** у этой группы имеет **Win Rate {wr_4}%** на горизонте 4 недель."
            break
            
    summary_html = f"""
    <div style="background-color: #0e1117; border-left: 4px solid #3498db; padding: 15px; border-radius: 4px; margin-bottom: 20px; border: 1px solid #1f2937;">
        <h5 style="margin-top: 0; color: #3498db; font-size: 1.05em; margin-bottom: 8px;">💡 ШПАРГАЛКА БЭКТЕСТА: КАК ЧИТАТЬ ЭТИ ДАННЫЕ?</h5>
        <p style="margin-bottom: 8px; font-size: 0.92em; line-height: 1.4; color: #adbac7;">
            {group_desc}
        </p>
        <p style="margin-bottom: 8px; font-size: 0.92em; line-height: 1.4; color: #adbac7;">
            <strong>Логика бэктеста:</strong> {logic_desc}
        </p>
        <p style="margin-bottom: 8px; font-size: 0.92em; line-height: 1.4; color: #adbac7;">
            {recommendation}
        </p>
        {f'<p style="margin-bottom: 0; font-size: 0.88em; line-height: 1.4; color: #768390;"><em>{highlight_text}</em></p>' if highlight_text else ''}
    </div>
    """
    st.markdown(summary_html, unsafe_allow_html=True)
        
    # Prepare data for native st.dataframe
    import pandas as pd
    rows = []
    for item in stats:
        name = f"{item['icon']} {item['name']} ({'BUY' if item['direction'] == 'bullish' else 'SELL'})"
        count = item["count"]
        
        h4 = item["horizons"].get(4, {})
        h12 = item["horizons"].get(12, {})
        
        wr_4 = f"{h4['win_rate']}%" if "win_rate" in h4 else "—"
        wr_12 = f"{h12['win_rate']}%" if "win_rate" in h12 else "—"
        
        ret_4 = f"{h4['mean_return']:+.2f}%" if "mean_return" in h4 else "—"
        ret_12 = f"{h12['mean_return']:+.2f}%" if "mean_return" in h12 else "—"
        
        rows.append({
            "Сигнал (Ожидание)": name,
            "Кол-во сигналов": count,
            "Win Rate (+4н)": wr_4,
            "Win Rate (+12н)": wr_12,
            "Ср. доходность (+4н)": ret_4,
            "Ср. доходность (+12н)": ret_12
        })
        
    backtest_df = pd.DataFrame(rows)
    st.dataframe(
        backtest_df,
        use_container_width=True,
        hide_index=True
    )


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

app_mode = st.sidebar.radio("Навигация:", ["📊 Терминал COT", "📈 Интерактивный Дашборд", "🌊 BTC GEX Трекер", "🤖 Бумажный бот & Бэктесты", "📖 Паспорт Терминала"])
if app_mode == "📈 Интерактивный Дашборд":
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
                
                # 4.5. BTC GEX Уровни (for Bitcoin analysis)
                if any(x in user_assets_input.upper() for x in ["BTC", "BITCOIN"]):
                    st.markdown("### 🌊 Уровни дилеров опционов BTC (GEX)")
                    try:
                        from src.gex_engine import get_aggregate_gex_data, calculate_gex_metrics
                        gex_df, spot_price = get_aggregate_gex_data("All Exchanges")
                        gex_metrics = calculate_gex_metrics(gex_df, spot_price)
                        
                        g_flip = gex_metrics.get("gamma_flip")
                        c_wall = gex_metrics.get("call_wall")
                        p_wall = gex_metrics.get("put_wall")
                        total_gex = gex_metrics.get("total_gex", 0)
                        
                        col_g1, col_g2, col_g3, col_g4 = st.columns(4)
                        with col_g1:
                            st.metric("Цена BTC (Spot)", f"${spot_price:,.2f}")
                        with col_g2:
                            st.metric("Net GEX (BTC)", f"${total_gex/1_000_000.0:+.2f}M", delta="🟢 Positive" if total_gex >= 0 else "🔴 Negative")
                        with col_g3:
                            st.metric("Точка Gamma Flip", f"${g_flip:,.0f}" if g_flip else "Н/Д")
                        with col_g4:
                            st.metric("Стены Call / Put", f"${c_wall:,.0f} / ${p_wall:,.0f}" if (c_wall and p_wall) else "Н/Д")
                    except Exception as e:
                        st.warning(f"Данные GEX для BTC временно недоступны: {e}")
                
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
    st.title("📖 Паспорт Терминала: Методология и Источники")
    
    st.markdown("""
    ### ⚡ Общие сведения
    **«Терминал Кот»** — это аналитический комплекс, объединяющий фундаментальные макроэкономические метрики, данные по позиционированию крупных спекулянтов и хеджеров (CFTC COT), а также параметры распределения ликвидности на опционных рынках (GEX).
    
    Цель системы — предоставить трейдеру объективную картину рынка на основе реального распределения капитала, полностью исключая классический графический технический анализ.
    """)
    
    st.markdown("---")
    st.markdown("### 📊 1. Основные разделы системы")
    
    st.markdown("""
    * **📊 Терминал COT**:
      * Анализ отчетов **Commitments of Traders (CFTC)** для валют, металлов, индексов и криптовалют.
      * Оценка позиционирования четырех категорий участников: **Dealers (Дилеры)**, **Asset Managers (Институционалы)**, **Leveraged Funds (Хедж-фонды)** и **Retail (Ритейл)**.
      * Исторические графики нетто-позиций, индексы сентимента (COT Index) и расчет Z-Score для определения зон перекупленности/перепроданности.
      * Статистический модуль бэктестинга: оценка исторического Win Rate и матожидания цены после достижения экстремумов.
      
    * **📈 Интерактивный Дашборд**:
      * Сводный аналитический центр, объединяющий все потоки данных в единую картину.
      * Визуализация динамики ликвидности ФРС США (баланс WALCL, денежная масса M2, доходности гособлигаций).
      * Интеграция данных по ETF и инсайдерским сделкам.
      * Автоматическая генерация комплексного ИИ-отчета с помощью **Gemini 2.5 Pro/Flash**, который сопоставляет позиции фондов (COT) с опционными уровнями маркет-мейкеров (GEX).
      
    * **🌊 BTC GEX Трекер (Bitcoin Gamma Exposure)**:
      * Анализ позиционирования дилеров опционов на ключевых криптобиржах (**Deribit, Bybit, OKX**).
      * Расчет и визуализация уровней волатильности и зон стабильности рынка:
        * **Г (Gamma Flip)**: Граница смены режима рынка (стабильный Positive Gamma против волатильного Negative Gamma).
        * **P1/P2 (Gamma Resist.)**: Стены сопротивления.
        * **N1/N2 (Vol. Trigger)**: Поддержки и триггеры роста волатильности.
        * **A1/A2 (Magnets)**: Страйки притяжения цены.
        * **V (Max Volatility)** и **S (Max Stability)**: Внешние границы волатильности.
    """)
    
    st.markdown("---")
    st.markdown("### 🔌 2. Источники данных")
    st.markdown("""
    * **CFTC**: Еженедельные официальные отчеты по фьючерсам и опционам (в форматах Legacy и TFF).
    * **FRED (St. Louis Fed)**: Макроэкономическая статистика США.
    * **Yahoo Finance**: Спотовые котировки и параметры традиционных биржевых опционов.
    * **Deribit / Bybit / OKX API**: Живые опционные стаканы и открытый интерес по Биткоину в режиме реального времени.
    """)
    
    st.markdown("---")
    st.markdown("### 🧠 3. Роль ИИ-Агента (Gemini)")
    st.markdown("""
    ИИ-Агент выступает в роли главного макро-аналитика хедж-фонда. Он фильтрует рыночный шум, сопоставляет длинные позиции фондов в COT с живыми барьерами опционных маркет-мейкеров (GEX) и формирует целостный текстовый сценарий движения цены с рекомендациями для портфеля активов.
    """)
    
    st.stop()


elif app_mode == "🌊 BTC GEX Трекер":
    st.sidebar.subheader("Параметры GEX")
    selected_exchange_map = {
        "Все биржи (Агрегировано)": "All Exchanges",
        "Deribit": "Deribit",
        "Bybit": "Bybit",
        "OKX": "OKX"
    }
    selected_display = st.sidebar.selectbox(
        "Выберите биржу:", 
        list(selected_exchange_map.keys()), 
        index=0
    )
    selected_exchange = selected_exchange_map[selected_display]
    
    selected_window = st.sidebar.selectbox(
        "Окно графиков GEX:",
        ["24 часа", "3 дня (72 часа)", "7 дней (168 часов)"],
        index=1
    )
    
    window_hours_map = {
        "24 часа": 24,
        "3 дня (72 часа)": 72,
        "7 дней (168 часов)": 168
    }
    hours_to_load = window_hours_map[selected_window]
    
    st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)
    
    # Fetch all live options data first to get the list of expirations
    with st.spinner("Сбор опционных данных и расчет GEX..."):
        from src.gex_engine import get_aggregate_gex_data, calculate_gex_metrics
        gex_df_raw, spot_price = get_aggregate_gex_data(selected_exchange)
        
    if gex_df_raw.empty:
        st.error("Не удалось получить данные опционов. Пожалуйста, попробуйте позже.")
        st.stop()
        
    # Get sorted unique expiration dates
    exp_dates = gex_df_raw.groupby("expiry_str").agg(
        dt=("expiry_dt", "first")
    ).reset_index().dropna(subset=["dt"]).sort_values("dt")["expiry_str"].tolist()
    
    selected_expiry = st.sidebar.selectbox(
        "Выберите экспирацию:",
        ["Все экспирации (TOTAL)"] + exp_dates,
        index=0
    )
    
    st.sidebar.markdown("<div class='neon-hr'></div>", unsafe_allow_html=True)
    if st.sidebar.button("🔄 Обновить данные GEX", use_container_width=True):
        st.rerun()
    
    # Filter raw dataframe by selected expiry
    if selected_expiry != "Все экспирации (TOTAL)":
        gex_df = gex_df_raw[gex_df_raw["expiry_str"] == selected_expiry].copy()
    else:
        gex_df = gex_df_raw.copy()
        
    # Calculate GEX metrics for the filtered data
    metrics = calculate_gex_metrics(gex_df, spot_price)
    
    # Spot price header
    st.markdown(f"""
    <div class='metrics-header'>
        <span style='color: #94a3b8; font-size: 1.1em;'>Текущий спот BTC:</span>
        <span style='font-size: 2em; font-weight: 700; color: #ffffff; margin-left: 10px;'>${spot_price:,.2f}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics Row
    g_flip = metrics.get("gamma_flip")
    c_wall = metrics.get("call_wall")
    p_wall = metrics.get("put_wall")
    net_g = metrics.get("total_gex", 0.0) / 1e6
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Суммарный Net GEX", f"{net_g:+.1f}M USD/1%", delta="Хеджирование дилеров")
    with col_m2:
        st.metric("Точка Gamma Flip", f"${g_flip:,.0f}" if g_flip else "Н/Д")
    with col_m3:
        st.metric("Call Wall (Сопротивление)", f"${c_wall:,.0f}" if c_wall else "Н/Д")
    with col_m4:
        st.metric("Put Wall (Поддержка)", f"${p_wall:,.0f}" if p_wall else "Н/Д")
        
    # Badges Row
    p1 = metrics.get("p1")
    p2 = metrics.get("p2")
    n1 = metrics.get("n1")
    n2 = metrics.get("n2")
    a1 = metrics.get("a1")
    a2 = metrics.get("a2")
    v_level = metrics.get("v")
    s_level = metrics.get("s")
    flip_price = metrics.get("gamma_flip")
    
    def get_strike_gex_m(strike):
        if strike is None: return 0.0
        val = gex_df[gex_df["strike"] == strike]["gex"].sum()
        return val / 1e6
        
    def format_badge_html(name, strike, gex_m=None, color="#3498db", subtitle=""):
        if strike is None:
            return ""
        gex_str = f" ({gex_m:+.1f}M)" if gex_m is not None else ""
        return f"""<div style="background: #1e293b; border-left: 4px solid {color}; padding: 8px 12px; border-radius: 4px; min-width: 135px; flex-shrink: 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"><div style="font-size: 0.75em; color: #94a3b8; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em;">{name} {subtitle}</div><div style="font-size: 1.15em; font-weight: 700; color: #ffffff; margin: 2px 0;">${strike:,.0f}</div><div style="font-size: 0.75em; color: {color}; font-weight: 600;">{gex_str}</div></div>"""
        
    badges_html = []
    badges_html.append(format_badge_html("V", v_level, color="#f97316", subtitle="Лимит Волат."))
    badges_html.append(format_badge_html("N2", n2, get_strike_gex_m(n2), color="#ef4444", subtitle="Триггер Волат. 2"))
    badges_html.append(format_badge_html("N1", n1, get_strike_gex_m(n1), color="#ef4444", subtitle="Триггер Волат. 1"))
    badges_html.append(format_badge_html("A1", a1, get_strike_gex_m(a1), color="#8b5cf6", subtitle="Магнит Цены 1"))
    badges_html.append(format_badge_html("Flip Г", flip_price, 0.0, color="#ec4899", subtitle="Нейтраль"))
    badges_html.append(format_badge_html("A2", a2, get_strike_gex_m(a2), color="#8b5cf6", subtitle="Магнит Цены 2"))
    badges_html.append(format_badge_html("P1", p1, get_strike_gex_m(p1), color="#10b981", subtitle="Сопротивление 1"))
    badges_html.append(format_badge_html("P2", p2, get_strike_gex_m(p2), color="#10b981", subtitle="Сопротивление 2"))
    badges_html.append(format_badge_html("S", s_level, color="#10b981", subtitle="Лимит Стабильн."))
    
    full_badges_html = f"""<div style="display: flex; gap: 10px; overflow-x: auto; padding: 10px 0; margin-bottom: 25px;">
{"".join(badges_html)}
</div>"""
    
    st.markdown(full_badges_html, unsafe_allow_html=True)
    
    # GEX Profile & Price History Subplot Chart
    st.markdown("### 📊 Интерактивная карта цен и Гамма-уровней (GEX Profile)")
    st.caption(f"Слева: Свечной график цены BTC за последние {selected_window} с наложением ключевых гамма-уровней поддержки/сопротивления. Справа: Распределение экспозиции (GEX) дилеров по страйкам.")
    
    with st.spinner("Загрузка истории котировок BTC..."):
        df_hist = fetch_btc_price_history_binance(limit=hours_to_load, interval="1h")
        
    fig_gex = make_subplots(
        rows=1, cols=2, 
        shared_yaxes=True, 
        column_widths=[0.85, 0.15],
        horizontal_spacing=0.01,
        subplot_titles=(f"Цена BTC ({selected_window})", "GEX Профиль")
    )
    
    # 1. Price History Candlestick Chart (Col 1)
    if not df_hist.empty:
        fig_gex.add_trace(
            go.Candlestick(
                x=df_hist["datetime"],
                open=df_hist["open"],
                high=df_hist["high"],
                low=df_hist["low"],
                close=df_hist["close"],
                name="Цена BTC",
                increasing_line_color="#10b981",
                decreasing_line_color="#ef4444",
                hoverinfo="all"
            ),
            row=1, col=1
        )
        x_min = df_hist["datetime"].min()
        x_max = df_hist["datetime"].max()
    else:
        x_min = datetime.now() - timedelta(days=7)
        x_max = datetime.now()
        
    # 2. GEX Profile Bar (Col 2)
    strike_gex = gex_df.groupby("strike")["gex"].sum().reset_index()
    # Focus range +/- 15% of spot
    filtered_strike_gex = strike_gex[
        (strike_gex["strike"] >= spot_price * 0.85) & 
        (strike_gex["strike"] <= spot_price * 1.15)
    ].copy()
    
    if filtered_strike_gex.empty:
        filtered_strike_gex = strike_gex.copy()
        
    colors = np.where(filtered_strike_gex["gex"] >= 0, "rgba(16, 185, 129, 0.7)", "rgba(239, 68, 68, 0.7)")
    borders = np.where(filtered_strike_gex["gex"] >= 0, "#10b981", "#ef4444")
    
    fig_gex.add_trace(
        go.Bar(
            x=filtered_strike_gex["gex"],
            y=filtered_strike_gex["strike"],
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color=borders, width=1.5)
            ),
            name="Gamma Exposure",
            hovertemplate="<b>Страйк:</b> $%{y:,.0f}<br><b>GEX:</b> $%{x:,.2f}<extra></extra>"
        ),
        row=1, col=2
    )
    
    # 3. Add Colored GEX Level Bands (Green for Resist, Red for Trigger, Purple for Magnet, Pink for Flip)
    if p1 and p2:
        fig_gex.add_shape(
            type="rect",
            x0=x_min, x1=x_max,
            y0=min(p1, p2), y1=max(p1, p2),
            fillcolor="rgba(16, 185, 129, 0.08)",
            line=dict(width=0),
            layer="below",
            row=1, col=1
        )
    if n1 and n2:
        fig_gex.add_shape(
            type="rect",
            x0=x_min, x1=x_max,
            y0=min(n1, n2), y1=max(n1, n2),
            fillcolor="rgba(239, 68, 68, 0.08)",
            line=dict(width=0),
            layer="below",
            row=1, col=1
        )
    if a1 and a2:
        fig_gex.add_shape(
            type="rect",
            x0=x_min, x1=x_max,
            y0=min(a1, a2), y1=max(a1, a2),
            fillcolor="rgba(139, 92, 246, 0.05)",
            line=dict(width=0),
            layer="below",
            row=1, col=1
        )
    if flip_price:
        fig_gex.add_shape(
            type="rect",
            x0=x_min, x1=x_max,
            y0=flip_price - 150, y1=flip_price + 150,
            fillcolor="rgba(236, 72, 153, 0.08)",
            line=dict(width=0),
            layer="below",
            row=1, col=1
        )

    # 4. Add Horizontal Levels to Column 1 (Price) with staggered labels for overlaps
    levels_to_draw = []
    if p2: levels_to_draw.append((p2, "P2", "#10b981", "Gamma Resist 2"))
    if p1: levels_to_draw.append((p1, "P1", "#10b981", "Gamma Resist 1"))
    if a2: levels_to_draw.append((a2, "A2", "#8b5cf6", "Magnet 2"))
    if a1: levels_to_draw.append((a1, "A1", "#8b5cf6", "Magnet 1"))
    if flip_price: levels_to_draw.append((flip_price, "Г", "#ec4899", "Gamma Flip"))
    if n1: levels_to_draw.append((n1, "N1", "#ef4444", "Vol Trigger 1"))
    if n2: levels_to_draw.append((n2, "N2", "#ef4444", "Vol Trigger 2"))
    if v_level: levels_to_draw.append((v_level, "V", "#f97316", "Max Volatility"))
    if s_level: levels_to_draw.append((s_level, "S", "#10b981", "Max Stability"))
    
    levels_to_draw = sorted([x for x in levels_to_draw if x[0] is not None], key=lambda x: x[0])
    
    strike_counts = {}
    for val, name, color, desc in levels_to_draw:
        if spot_price * 0.85 <= val <= spot_price * 1.15:
            fig_gex.add_shape(
                type="line",
                x0=x_min, x1=x_max,
                y0=val, y1=val,
                line=dict(color=color, width=1.5, dash="dash"),
                row=1, col=1
            )
            
            rounded_strike = int(round(val))
            count = strike_counts.get(rounded_strike, 0)
            strike_counts[rounded_strike] = count + 1
            
            offset_hours = count * 18
            label_x = x_max - timedelta(hours=offset_hours)
            
            fig_gex.add_annotation(
                x=label_x,
                y=val,
                text=f"<b>{name}</b> {val:,.0f}",
                showarrow=False,
                xanchor="right" if count > 0 else "left",
                yanchor="middle",
                font=dict(color="#ffffff", size=9, family="SF Mono, Courier New, monospace"),
                bgcolor=color,
                bordercolor=color,
                borderwidth=1,
                borderpad=2,
                row=1, col=1
            )
            
    fig_gex.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
        margin=dict(l=0, r=60, t=30, b=0),
        height=600,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        yaxis=dict(
            title="Цена BTC / Страйк ($)",
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.05)",
            tickformat="$,.0f",
            range=[spot_price * 0.85, spot_price * 1.15]
        ),
        xaxis=dict(
            title="Дата/Время",
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.05)"
        ),
        xaxis2=dict(
            title="GEX ($ / 1%)",
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.05)"
        )
    )
    st.plotly_chart(fig_gex, use_container_width=True)
    
    # Top-20 Table
    st.markdown("### 📋 Топ-20 крупных опционных страйков по влиянию на рынок")
    top_gex_df = gex_df.copy()
    top_gex_df["abs_gex"] = top_gex_df["gex"].abs()
    top_gex_df = top_gex_df.sort_values("abs_gex", ascending=False).head(20)
    
    rows_html = ""
    for _, row in top_gex_df.iterrows():
        gex_val = row["gex"]
        gex_cls = "net-positive" if gex_val >= 0 else "net-negative"
        gex_str = f"${gex_val:,.2f}"
        
        rows_html += f"""<tr>
<td style="text-align: left; padding: 10px 16px;">{row['exchange']}</td>
<td class="font-mono" style="text-align: right; padding: 10px 16px; color:#ffffff; font-weight:600;">${row['strike']:,.0f}</td>
<td style="text-align: right; padding: 10px 16px;">{row['expiry_str']}</td>
<td style="text-align: right; padding: 10px 16px; color:{'#10b981' if row['option_type']=='C' else '#ef4444'}; font-weight:600;">{row['option_type']}</td>
<td class="font-mono" style="text-align: right; padding: 10px 16px;">{row['open_interest']:,.2f}</td>
<td class="font-mono" style="text-align: right; padding: 10px 16px;">{row['implied_volatility']*100:.1f}%</td>
<td style="text-align: right; padding: 10px 16px;">
<span class="{gex_cls} font-mono" style="padding: 4px 10px; border-radius: 4px; display: inline-block; min-width: 110px; text-align: right;">{gex_str}</span>
</td>
</tr>"""
        
    table_html = f"""<div class="cot-table-container">
<table class="cot-table">
<thead>
<tr>
<th style="text-align: left; font-size: 0.85em; color: #6b7280;">БИРЖА</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">СТРАЙК</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ЭКСПИРАЦИЯ</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ТИП</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">ОТКРЫТЫЙ ИНТЕРЕС</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">IV (ВОЛАТИЛЬНОСТЬ)</th>
<th style="text-align: right; font-size: 0.85em; color: #6b7280;">GEX (USD / 1%)</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>"""
    st.markdown(table_html, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📚 Справочник GEX-уровней и правила интерпретации", expanded=True):
        st.markdown("""
        ### 🧭 Как интерпретировать уровни гамма-экспозиции (GEX):
        
        * **Режим Гаммы (Gamma Regime):**
          * **🟢 Положительная Гамма (Цена выше Г / Зеленая зона):** Рынок спокойный. Дилеры совершают сделки против движения цены (продают на росте, покупают на падении), подавляя волатильность. Цена обычно флэтит или медленно дрейфует.
          * **🔴 Отрицательная Гамма (Цена ниже Г / Красная зона):** Рынок волатильный. Дилеры совершают сделки в направлении движения цены (продают при падении, покупают при росте), усиливая тренд. Возможны резкие проскальзывания, импульсы и повышенная скорость движений.
         
        * **Ключевые уровни:**
          * **Г (Gamma Flip / Regime Change):** «Линия на песке». Точка перехода между стабильностью и хаосом.
          * **P1 / P2 (Gamma Resist.):** Уровни сильного сопротивления (Call-стены). Чем больше объем (+M), тем сложнее цене пробить этот уровень вверх.
          * **N1 / N2 (Vol. Trigger):** Уровни сильной поддержки / триггеры падения. Пробитие N1 вниз часто открывает дорогу к N2 и вызывает резкое падение.
          * **A1 / A2 (Magnet):** Уровни притяжения (магниты). Цена стремится застрять на них, особенно по пятницам в день экспирации опционов (пин-риск).
          * **V (Max Volatility) и S (Max Stability):** Экстремальные границы зоны. Выход за них означает переход в фазу сильного тренда (выше S) или панического обвала (ниже V).
        """)
        
    st.stop()


elif app_mode == "🤖 Бумажный бот & Бэктесты":
    st.title("🤖 ИИ-Бот Бумажной Торговли & Квантовые Бэктесты")
    st.caption("Автоматическая симуляция торговли в реальном времени с риск-менеджментом (риск 2% на сделку) и динамической оптимизацией стратегий.")
    
    from src.bot_engine import BotEngine, BacktestEngine
    
    # 1. Initialize Bot Engine
    bot = BotEngine(data_fetcher_fn=get_market_analysis)
    
    # Live BTC GEX calculations to pass as factor filter for BTC trades
    gex_metrics_btc = None
    try:
        from src.gex_engine import get_aggregate_gex_data, calculate_gex_metrics
        gex_df_raw, spot_price = get_aggregate_gex_data("All Exchanges")
        if not gex_df_raw.empty:
            gex_metrics_btc = calculate_gex_metrics(gex_df_raw, spot_price)
    except Exception:
        pass
        
    # Trigger active trade checking and signal evaluations
    with st.spinner("Синхронизация котировок и обновление позиций..."):
        bot.update_positions_and_signals(gex_metrics_btc=gex_metrics_btc)
        
    # Get updated state
    state = bot.state
    balance = state["balance"]
    equity = state["equity"]
    active_pos = state["active_positions"]
    journal = state["journal"]
    win_rate = state["win_rate"]
    
    # 2. Portfolio Summary Cards
    st.markdown("### 💼 Состояние портфеля")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Свободный Баланс (Cash)", f"${balance:,.2f}")
    
    unrealized_total = equity - balance
    pnl_sign = "+" if unrealized_total >= 0 else ""
    col2.metric("Текущие средства (Equity)", f"${equity:,.2f}", delta=f"{pnl_sign}${unrealized_total:,.2f}")
    
    col3.metric("Активные сделки", f"{len(active_pos)} шт.")
    col4.metric("Доля прибыльных сделок (Win Rate)", f"{win_rate:.1f}%")
    
    with st.expander("📋 Активные торговые системы по всем 16 инструментам (Авто-выбор на текущий месяц)"):
        strat_rows = []
        for sym, strat in state.get("selected_strategies", {}).items():
            strat_rows.append({"Инструмент": sym, "Активная ТС": strat, "Комиссия за сделку": "0.05%"})
        if strat_rows:
            st.dataframe(pd.DataFrame(strat_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Стратегии оптимизируются...")
            
    st.markdown("---")
    
    # 3. Active Positions Section
    st.markdown("### 📈 Активные открытые позиции")
    if not active_pos:
        st.info("В данный момент нет активных позиций. Бот ожидает подходящих сигналов на рынках.")
    else:
        # Render a clean HTML table for active trades with rationales
        rows_html = ""
        for sym, pos in active_pos.items():
            dir_cls = "net-positive" if pos["direction"] == "LONG" else "net-negative"
            pnl_val = pos["unrealized_pnl"]
            pnl_cls = "net-positive" if pnl_val >= 0 else "net-negative"
            pnl_str = f"${pnl_val:,.2f}"
            
            rows_html += f"""<tr>
            <td style="text-align: left; padding: 12px 16px; font-weight:600; color:#ffffff;">{sym}</td>
            <td style="text-align: center; padding: 12px 16px;"><span class="{dir_cls}" style="padding: 4px 8px; border-radius:4px;">{pos['direction']}</span></td>
            <td class="font-mono" style="text-align: right; padding: 12px 16px;">{pos['position_size']:.4f}</td>
            <td class="font-mono" style="text-align: right; padding: 12px 16px;">${pos['entry_price']:,.2f}</td>
            <td class="font-mono" style="text-align: right; padding: 12px 16px;">${pos['current_price']:,.2f}</td>
            <td class="font-mono" style="text-align: right; padding: 12px 16px; color:#ef4444;">${pos['stop_loss']:,.2f}</td>
            <td class="font-mono" style="text-align: right; padding: 12px 16px; color:#10b981;">${pos['take_profit']:,.2f}</td>
            <td style="text-align: right; padding: 12px 16px;"><span class="{pnl_cls}" style="padding: 4px 10px; border-radius:4px;">{pnl_str}</span></td>
            <td style="text-align: left; padding: 12px 16px; font-size:0.85em; color:#94a3b8; max-width: 350px;">{pos['rationale']}</td>
            </tr>"""
            
        active_table_html = f"""<div class="cot-table-container">
        <table class="cot-table">
        <thead>
        <tr>
        <th style="text-align: left; font-size: 0.85em; color: #6b7280;">Инструмент</th>
        <th style="text-align: center; font-size: 0.85em; color: #6b7280;">Тип</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Объем</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Вход</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Текущая</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Stop Loss</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Take Profit</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Нереал. PnL</th>
        <th style="text-align: left; font-size: 0.85em; color: #6b7280;">Обоснование сделки</th>
        </tr>
        </thead>
        <tbody>
        {rows_html}
        </tbody>
        </table>
        </div>"""
        st.markdown(active_table_html, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 4. Strategy Optimizer & Manual Backtester Section
    st.markdown("### 🔬 Квантовый оптимизатор & Модуль бэктестов")
    st.markdown("Выберите инструмент для запуска серии исторических бэктестов по всем доступным стратегиям (за последние 3 года). Выявленная самая прибыльная стратегия будет автоматически назначена боту для торговли на текущий месяц.")
    
    selected_backtest_asset = st.selectbox(
        "Выберите инструмент для бэктеста:",
        list(MARKETS.keys()),
        index=0
    )
    
    # Fetch historical COT data for backtesting
    with st.spinner("Загрузка исторических данных для бэктеста..."):
        backtest_part = "Leveraged Funds" if selected_backtest_asset in ["BTC", "ETH"] else "Asset Manager"
        df_backtest_raw = get_market_analysis(selected_backtest_asset, backtest_part, use_combined=True)
        
    if df_backtest_raw.empty:
        st.error("Недостаточно данных для запуска бэктеста по выбранному активу.")
    else:
        # Define strategies to backtest
        if selected_backtest_asset == "BTC":
            strategies = [
                "Strategy A (COT Trend)",
                "Strategy B (GEX Walls)",
                "Strategy C (Gamma Flip Breakout)",
                "Strategy D (Synergy COT+GEX)"
            ]
        else:
            strategies = [
                "Strategy A (COT Trend)",
                "Strategy B (COT Contrarian)",
                "Strategy C (COT Crossover)",
                "Strategy D (COT Momentum)"
            ]
            
        results = []
        best_return = -999.0
        best_strat = None
        
        for strat in strategies:
            summary, trades = BacktestEngine.run_backtest(df_backtest_raw, selected_backtest_asset, strat)
            results.append({
                "Стратегия": strat,
                "Общая доходность": f"{summary['net_return']:+.2f}%",
                "Win Rate": f"{summary['win_rate']:.1f}%",
                "Profit Factor": f"{summary['profit_factor']:.2f}",
                "Макс. просадка": f"{summary['max_drawdown']:.1f}%",
                "Кол-во сделок": summary["trade_count"],
                "raw_return": summary["net_return"]
            })
            if summary["net_return"] > best_return:
                best_return = summary["net_return"]
                best_strat = strat
                
        results_df = pd.DataFrame(results)
        
        # Display results comparison table
        st.markdown(f"**Результаты сравнительного анализа стратегий для {selected_backtest_asset}:**")
        st.dataframe(results_df.drop(columns=["raw_return"]), use_container_width=True, hide_index=True)
        
        # Highlight best strategy
        st.success(f"🏆 **Рекомендация месяца:** Самая прибыльная стратегия для **{selected_backtest_asset}** — **'{best_strat}'** (Доходность: {best_return:+.2f}% с учетом комиссии 0.05%).")
        
        current_active_strat = state["selected_strategies"].get(selected_backtest_asset, "Strategy A (COT Trend)")
        st.info(f"Текущая активная ТС для {selected_backtest_asset} в боте: **'{current_active_strat}'** (автоматически обновляется раз в месяц).")
                
    st.markdown("---")
    
    # 5. Visual Trading Journal History
    st.markdown("### 📋 Журнал завершенных сделок (Торговая история)")
    if not journal:
        st.info("Журнал пуст. Закрытые сделки появятся здесь после срабатывания SL/TP.")
    else:
        # Build HTML table for closed trades
        journal_rows = ""
        for trade in reversed(journal):
            pnl = trade["profit_usd"]
            pnl_cls = "net-positive" if pnl >= 0 else "net-negative"
            pnl_sign = "+" if pnl > 0 else ""
            pnl_str = f"{pnl_sign}${pnl:,.2f}"
            
            journal_rows += f"""<tr>
            <td style="text-align: left; padding: 8px 12px; font-weight:600; color:#ffffff;">{trade['symbol']}</td>
            <td style="text-align: center; padding: 8px 12px;">{trade['direction']}</td>
            <td style="text-align: right; padding: 8px 12px;">${trade['entry_price']:,.2f}</td>
            <td style="text-align: right; padding: 8px 12px;">${trade['exit_price']:,.2f}</td>
            <td style="text-align: right; padding: 8px 12px;"><span class="{pnl_cls}" style="padding: 2px 6px; border-radius:3px;">{pnl_str}</span></td>
            <td style="text-align: center; padding: 8px 12px; font-size:0.9em; color:#cbd5e1;">{trade['entry_time']} / {trade['exit_time']}</td>
            <td style="text-align: left; padding: 8px 12px; font-size:0.85em; color:#94a3b8; max-width: 300px;">{trade['rationale']}</td>
            </tr>"""
            
        journal_table_html = f"""<div class="cot-table-container">
        <table class="cot-table">
        <thead>
        <tr>
        <th style="text-align: left; font-size: 0.85em; color: #6b7280;">Инструмент</th>
        <th style="text-align: center; font-size: 0.85em; color: #6b7280;">Тип</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Вход</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">Выход</th>
        <th style="text-align: right; font-size: 0.85em; color: #6b7280;">PnL USD</th>
        <th style="text-align: center; font-size: 0.85em; color: #6b7280;">Время Откр./Закр.</th>
        <th style="text-align: left; font-size: 0.85em; color: #6b7280;">Причина открытия / закрытия</th>
        </tr>
        </thead>
        <tbody>
        {journal_rows}
        </tbody>
        </table>
        </div>"""
        st.markdown(journal_table_html, unsafe_allow_html=True)
        
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
    
    # 3.5. Full Backtest Stats Table
    with st.expander("📊 Показать полную статистику исторических бэктестов (Все сигналы группы)", expanded=True):
        display_backtest_stats_table(df, selected_market, tff_participant)

    # 4. Advanced Holistic AI Report
    st.markdown(f"### 🤖 Аналитический репорт ИИ")

    from src.analytics import generate_holistic_report
    holistic_report = generate_holistic_report(selected_market, use_combined=use_combined)
    st.info(holistic_report)

# Force reload 1
