"""
COT Signal Backtesting Engine.

Detects positioning signals, backtests them against historical data,
and generates Russian-language interpretations with statistics.
"""
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────
# 1. SIGNAL DEFINITIONS
# ─────────────────────────────────────────────────────────────

SIGNAL_DEFS = {
    "extreme_short": {
        "name": "Экстремальный шорт",
        "icon": "🟢",
        "direction": "bullish",  # contrarian
        "desc": "COT Index 52w ≤ 10% — крупные игроки максимально зашортили. Исторически это зона разворота вверх.",
    },
    "extreme_long": {
        "name": "Экстремальный лонг",
        "icon": "🔴",
        "direction": "bearish",  # contrarian
        "desc": "COT Index 52w ≥ 90% — крупные игроки максимально в лонге. Исторически это зона разворота вниз.",
    },
    "sharp_net_increase": {
        "name": "Резкий рост чистой позиции",
        "icon": "🟢",
        "direction": "bullish",
        "desc": "Недельное изменение net/OI в топ-5% исторических значений — агрессивное наращивание лонгов.",
    },
    "sharp_net_decrease": {
        "name": "Резкий сброс чистой позиции",
        "icon": "🔴",
        "direction": "bearish",
        "desc": "Недельное изменение net/OI в нижних 5% — агрессивный сброс/шортинг.",
    },
    "zero_cross_up": {
        "name": "Пересечение нуля вверх",
        "icon": "🟢",
        "direction": "bullish",
        "desc": "Чистая позиция перешла из минуса в плюс — участники переключились с шорта на лонг.",
    },
    "zero_cross_down": {
        "name": "Пересечение нуля вниз",
        "icon": "🔴",
        "direction": "bearish",
        "desc": "Чистая позиция перешла из плюса в минус — участники переключились с лонга на шорт.",
    },
    "bullish_divergence": {
        "name": "Бычья дивергенция",
        "icon": "🟢",
        "direction": "bullish",
        "desc": "Цена падает, но крупные игроки наращивают позиции — скрытый спрос.",
    },
    "bearish_divergence": {
        "name": "Медвежья дивергенция",
        "icon": "🔴",
        "direction": "bearish",
        "desc": "Цена растёт, но крупные игроки сокращают позиции — скрытое распределение.",
    },
}

FORWARD_HORIZONS = [1, 2, 4, 8, 12]  # weeks


# ─────────────────────────────────────────────────────────────
# 2. SIGNAL DETECTION
# ─────────────────────────────────────────────────────────────

def detect_signals_series(df):
    """
    Return a dict of signal_key -> boolean Series (True where signal fires).
    Requires df to have columns from calculate_metrics().
    """
    signals = {}

    # Extreme positioning (contrarian)
    signals["extreme_short"] = df["cot_index_52w"] <= 10.0
    signals["extreme_long"] = df["cot_index_52w"] >= 90.0

    # Sharp weekly moves (momentum)
    wow = df["wow_change_net_pct_oi"]
    q95 = wow.quantile(0.95)
    q05 = wow.quantile(0.05)
    signals["sharp_net_increase"] = wow >= q95
    signals["sharp_net_decrease"] = wow <= q05

    # Zero crossover
    net_prev = df["net"].shift(1)
    signals["zero_cross_up"] = (net_prev < 0) & (df["net"] >= 0)
    signals["zero_cross_down"] = (net_prev >= 0) & (df["net"] < 0)

    # Divergence (4-week)
    signals["bullish_divergence"] = df["signal_bullish_div_4w"]
    signals["bearish_divergence"] = df["signal_bearish_div_4w"]

    return signals


def detect_active_signals(df):
    """
    Return list of signal keys active on the latest row.
    """
    all_series = detect_signals_series(df)
    active = []
    for key, series in all_series.items():
        if series.iloc[-1]:
            active.append(key)
    return active


# ─────────────────────────────────────────────────────────────
# 3. BACKTESTING ENGINE
# ─────────────────────────────────────────────────────────────

def _compute_forward_returns(df):
    """
    Pre-compute forward percentage returns for all horizons.
    Returns a dict of horizon -> Series of % returns.
    """
    fwd = {}
    for h in FORWARD_HORIZONS:
        future_price = df["close"].shift(-h)
        fwd[h] = ((future_price - df["close"]) / df["close"]) * 100.0
    return fwd


def backtest_signal(df, signal_series, direction, horizons=None):
    """
    Backtest a single signal.
    
    Args:
        df: DataFrame with 'close' column and a datetime index/column.
        signal_series: Boolean Series — True where the signal fires.
        direction: 'bullish' or 'bearish' — expected price direction.
        horizons: List of forward weeks to test.
        
    Returns:
        dict with keys for each horizon containing statistics,
        or None if insufficient data.
    """
    if horizons is None:
        horizons = FORWARD_HORIZONS

    fwd_returns = _compute_forward_returns(df)

    # Only use signals that have enough forward data
    max_horizon = max(horizons)
    usable_mask = signal_series & signal_series.index.isin(
        df.index[:-max_horizon] if len(df) > max_horizon else pd.Index([])
    )

    # Get indices where signal fires and we have forward data
    signal_indices = df.index[usable_mask]
    n_signals = len(signal_indices)

    if n_signals < 3:
        return None

    results = {
        "count": n_signals,
        "horizons": {},
    }

    for h in horizons:
        returns_at_h = fwd_returns[h].loc[signal_indices].dropna()
        if len(returns_at_h) < 3:
            continue

        # For bearish signals, a "win" is when price goes DOWN
        if direction == "bearish":
            win_count = (returns_at_h < 0).sum()
        else:
            win_count = (returns_at_h > 0).sum()

        results["horizons"][h] = {
            "n": len(returns_at_h),
            "win_rate": round((win_count / len(returns_at_h)) * 100, 1),
            "mean_return": round(returns_at_h.mean(), 2),
            "median_return": round(returns_at_h.median(), 2),
            "min_return": round(returns_at_h.min(), 2),
            "max_return": round(returns_at_h.max(), 2),
        }

    if not results["horizons"]:
        return None

    return results


def backtest_all_active_signals(df, active_signal_keys):
    """
    Run backtests for all active signals.
    
    Returns:
        list of dicts: [{signal_key, signal_def, backtest_results}, ...]
    """
    all_signal_series = detect_signals_series(df)
    results = []

    for key in active_signal_keys:
        sig_def = SIGNAL_DEFS[key]
        bt = backtest_signal(
            df,
            all_signal_series[key],
            direction=sig_def["direction"],
        )
        results.append({
            "key": key,
            "def": sig_def,
            "backtest": bt,
        })

    return results


# ─────────────────────────────────────────────────────────────
# 4. INTERPRETATION GENERATOR
# ─────────────────────────────────────────────────────────────

def _fmt(val, sign=False):
    """Format number with space separators."""
    v = int(round(val))
    s = f"{v:,}".replace(",", " ")
    if sign and v > 0:
        return f"+{s}"
    return s


def generate_situation_text(df, participant_name="Участники"):
    """
    Generate a human-readable description of what happened this week.
    Returns a list of strings (paragraphs).
    """
    if len(df) < 2:
        return ["Недостаточно данных для анализа."]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    lines = []

    # 1. Position changes
    long_chg = latest["long_change"]
    short_chg = latest["short_change"]
    net_chg = latest["wow_change_net"]
    oi_chg = latest["oi_change"]

    # Long description
    if long_chg > 0:
        lines.append(f"📈 Лонги увеличены на {_fmt(long_chg, True)} контрактов.")
    elif long_chg < 0:
        lines.append(f"📉 Лонги сокращены на {_fmt(long_chg)} контрактов.")
    else:
        lines.append("➡️ Лонги без изменений.")

    # Short description
    if short_chg > 0:
        lines.append(f"📈 Шорты увеличены на {_fmt(short_chg, True)} контрактов.")
    elif short_chg < 0:
        lines.append(f"📉 Шорты сокращены на {_fmt(short_chg)} контрактов.")
    else:
        lines.append("➡️ Шорты без изменений.")

    # Net summary
    if net_chg > 0:
        lines.append(f"⚡ Чистая позиция сдвинулась в сторону лонга на {_fmt(net_chg, True)}.")
    elif net_chg < 0:
        lines.append(f"⚡ Чистая позиция сдвинулась в сторону шорта на {_fmt(net_chg)}.")

    # OI context
    if oi_chg > 0:
        lines.append(f"📊 Открытый интерес вырос на {_fmt(oi_chg, True)} — новые деньги входят в рынок.")
    elif oi_chg < 0:
        lines.append(f"📊 Открытый интерес упал на {_fmt(oi_chg)} — участники выходят из рынка.")

    return lines


def generate_verdict(backtest_results, df, participant_name="Участники"):
    """
    Generate a detailed, multi-paragraph analytical verdict.
    Returns (verdict_paragraphs: list[str], verdict_class: str).
    Each paragraph is an HTML string.
    """
    if not backtest_results:
        no_signal_text = _build_no_signal_verdict(df, participant_name)
        return no_signal_text, "neutral"

    latest = df.iloc[-1]
    paragraphs = []

    # ── 1. Collect scored signals ──────────────────────────────
    bullish_items = []
    bearish_items = []

    for item in backtest_results:
        sig_def = item["def"]
        bt = item["backtest"]
        direction = sig_def["direction"]

        # Best available horizon stats (prefer 4w, fallback to others)
        best_h = None
        for h in [4, 8, 2, 12, 1]:
            if bt and h in bt["horizons"]:
                best_h = h
                break

        entry = {
            "name": sig_def["name"],
            "key": item["key"],
            "bt": bt,
            "best_h": best_h,
            "direction": direction,
        }
        if direction == "bullish":
            bullish_items.append(entry)
        else:
            bearish_items.append(entry)

    # ── 2. Current action paragraph ───────────────────────────
    long_chg = latest["long_change"]
    short_chg = latest["short_change"]
    net_chg = latest["wow_change_net"]
    net_val = latest["net"]
    oi_chg = latest["oi_change"]

    action_parts = ["<strong>⚡ Текущая динамика:</strong>"]
    if long_chg > 0 and short_chg < 0:
        action_parts.append(
            f"{participant_name} одновременно наращивают лонги (+{_fmt(long_chg)}) и сокращают шорты ({_fmt(short_chg)}). "
            f"Это двойное давление — агрессивная ставка на рост."
        )
    elif long_chg < 0 and short_chg > 0:
        action_parts.append(
            f"{participant_name} сокращают лонги ({_fmt(long_chg)}) и наращивают шорты (+{_fmt(short_chg)}). "
            f"Это двойное медвежье давление — ставка на снижение."
        )
    elif long_chg > 0 and short_chg > 0:
        action_parts.append(
            f"{participant_name} наращивают и лонги (+{_fmt(long_chg)}), и шорты (+{_fmt(short_chg)}). "
            f"Рынок готовится к сильному движению, но направление пока неясно — растёт неопределённость."
        )
    elif long_chg < 0 and short_chg < 0:
        action_parts.append(
            f"{participant_name} сокращают и лонги ({_fmt(long_chg)}), и шорты ({_fmt(short_chg)}). "
            f"Идёт фиксация прибыли / выход из позиций — снижение активности."
        )
    else:
        if net_chg > 0:
            action_parts.append(f"Чистая позиция сдвинулась в сторону лонга на {_fmt(net_chg, True)}.")
        elif net_chg < 0:
            action_parts.append(f"Чистая позиция сдвинулась в сторону шорта на {_fmt(net_chg)}.")

    if oi_chg > 0:
        action_parts.append(
            f"Открытый интерес вырос на {_fmt(oi_chg, True)} — в рынок поступают новые деньги, "
            f"что подтверждает серьёзность текущего движения."
        )
    elif oi_chg < 0:
        action_parts.append(
            f"Открытый интерес упал на {_fmt(oi_chg)} — участники выходят из рынка. "
            f"Текущее движение цены может быть вызвано закрытием позиций, а не открытием новых."
        )

    if len(action_parts) > 1:
        paragraphs.append(" ".join(action_parts))

    # ── 3. Signal-by-signal reasoning ─────────────────────────
    if bullish_items or bearish_items:
        paragraphs.append("<strong>🎯 Обнаруженные сигналы:</strong>")

    for entry in bullish_items + bearish_items:
        sig_paragraph = _build_signal_reasoning(entry, df, participant_name)
        if sig_paragraph:
            paragraphs.append("• " + sig_paragraph)

    # ── 4. Final verdict with scoring ─────────────────────────
    bullish_score = 0
    bearish_score = 0
    strongest_signal = None
    strongest_wr = 0

    for entry in bullish_items:
        w, wr = _get_signal_weight(entry)
        bullish_score += w
        if wr > strongest_wr:
            strongest_wr = wr
            strongest_signal = entry
    for entry in bearish_items:
        w, wr = _get_signal_weight(entry)
        bearish_score += w
        if wr > strongest_wr:
            strongest_wr = wr
            strongest_signal = entry

    total = bullish_score + bearish_score
    if total == 0:
        paragraphs.append("Данных для количественной оценки недостаточно.")
        return paragraphs, "neutral"

    bull_pct = (bullish_score / total) * 100
    has_conflict = len(bullish_items) > 0 and len(bearish_items) > 0

    conclusion_parts = ["<strong>📋 ИТОГОВЫЙ ВЕРДИКТ:</strong>"]

    if has_conflict:
        conclusion_parts.append(
            "⚠️ <strong>Смешанный фон (Конфликт сигналов).</strong> "
            "В данный момент на рынке сталкиваются противоположные силы. "
            "Механическое суммирование факторов здесь может быть обманчивым, так как "
            "краткосрочный импульс участников рынка противоречит среднесрочным или историческим паттернам."
        )

    if bull_pct >= 65:
        verdict_class = "bullish" if not has_conflict else "neutral"
        conclusion_parts.append(
            f"🟢 <strong>БЫЧИЙ ПЕРЕВЕС.</strong> Совокупность бычьих факторов ({bull_pct:.0f}% веса) преобладает."
        )
    elif bull_pct <= 35:
        verdict_class = "bearish" if not has_conflict else "neutral"
        bear_pct = 100 - bull_pct
        conclusion_parts.append(
            f"🔴 <strong>МЕДВЕЖИЙ ПЕРЕВЕС.</strong> Совокупность медвежьих факторов ({bear_pct:.0f}% веса) преобладает."
        )
    else:
        verdict_class = "neutral"
        conclusion_parts.append(
            f"⚪ <strong>НЕЙТРАЛЬНО.</strong> Бычьи факторы ({bull_pct:.0f}%) и медвежьи ({100-bull_pct:.0f}%) "
            f"уравновешивают друг друга. Ожидается боковик или высокая волатильность."
        )

    if strongest_signal and strongest_wr > 50:
        h = strongest_signal["best_h"]
        bt = strongest_signal["bt"]
        if bt and h and h in bt["horizons"]:
            s = bt["horizons"][h]
            dir_word = "роста" if strongest_signal["direction"] == "bullish" else "снижения"
            conclusion_parts.append(
                f"<br>Доминирующий паттерн — <em>{strongest_signal['name']}</em> "
                f"(Win Rate {s['win_rate']}% на горизонте +{h} нед., "
                f"средний return {'+' if s['mean_return'] > 0 else ''}{s['mean_return']}%). "
                f"Исторически это давало статистическое преимущество в сторону {dir_word}."
            )

    # Risk caveat
    if strongest_signal and strongest_signal["bt"]:
        h = strongest_signal["best_h"]
        if h and h in strongest_signal["bt"]["horizons"]:
            worst = strongest_signal["bt"]["horizons"][h]["min_return"]
            conclusion_parts.append(
                f"<br>⚠️ <em>Риск:</em> в худшем историческом случае по этому паттерну "
                f"return составил {'+' if worst > 0 else ''}{worst}% на горизонте +{h} нед."
            )

    paragraphs.append(" ".join(conclusion_parts))
    return paragraphs, verdict_class


def _get_signal_weight(entry):
    """Return (weight, win_rate) for scoring."""
    bt = entry["bt"]
    h = entry["best_h"]
    if bt and h and h in bt["horizons"]:
        wr = bt["horizons"][h]["win_rate"]
        return wr / 50.0, wr
    return 1.0, 50.0


def _build_signal_reasoning(entry, df, participant_name="Участники"):
    """Build a narrative paragraph for a single signal."""
    name = entry["name"]
    key = entry["key"]
    bt = entry["bt"]
    h = entry["best_h"]
    direction = entry["direction"]
    latest = df.iloc[-1]

    if not bt or not h:
        return None

    s = bt["horizons"].get(h)
    if not s:
        return None

    count = bt["count"]
    wr = s["win_rate"]
    mean_r = s["mean_return"]
    median_r = s["median_return"]

    parts = []

    # Context-specific reasoning
    if key == "extreme_short":
        cot_idx = latest.get("cot_index_52w", 0)
        parts.append(
            f"Сигнал «{name}»: COT Index 52w = {cot_idx:.1f}%, что означает — "
            f"текущая чистая позиция находится у нижней границы своего 52-недельного диапазона. "
            f"{participant_name} максимально пессимистичны. Контрарианская логика: когда все уже продали, "
            f"продавать больше некому, и рынок часто разворачивается вверх."
        )
    elif key == "extreme_long":
        cot_idx = latest.get("cot_index_52w", 0)
        parts.append(
            f"Сигнал «{name}»: COT Index 52w = {cot_idx:.1f}%, что означает — "
            f"текущая чистая позиция находится у верхней границы своего 52-недельного диапазона. "
            f"{participant_name} максимально оптимистичны. Контрарианская логика: когда все уже купили, "
            f"покупать больше некому, и рынок часто разворачивается вниз."
        )
    elif key == "zero_cross_up":
        parts.append(
            f"Сигнал «{name}»: чистая позиция перешла из отрицательной в положительную зону. "
            f"Это означает, что суммарный объём лонгов впервые превысил шорты — "
            f"{participant_name} «переключились» с медвежьей ставки на бычью."
        )
    elif key == "zero_cross_down":
        parts.append(
            f"Сигнал «{name}»: чистая позиция перешла из положительной в отрицательную зону. "
            f"Шорты впервые превысили лонги — {participant_name} «переключились» на медвежью ставку."
        )
    elif key == "sharp_net_increase":
        wow_val = latest.get("wow_change_net_pct_oi", 0)
        parts.append(
            f"Сигнал «{name}»: недельное изменение net/OI = {wow_val:+.2f}%, "
            f"что входит в топ-5% исторических значений. "
            f"Такой резкий рост позиций указывает на агрессивное вхождение в лонг — "
            f"{participant_name} увидели возможность и действуют решительно."
        )
    elif key == "sharp_net_decrease":
        wow_val = latest.get("wow_change_net_pct_oi", 0)
        parts.append(
            f"Сигнал «{name}»: недельное изменение net/OI = {wow_val:+.2f}%, "
            f"что входит в нижние 5% исторических значений. "
            f"Такой резкий сброс указывает на агрессивный выход из лонгов или наращивание шортов."
        )
    elif key == "bullish_divergence":
        parts.append(
            f"Сигнал «{name}»: цена актива снизилась за последние 4 недели, "
            f"но {participant_name} наращивают чистую позицию. Это классическая дивергенция — "
            f"покупки на падении в ожидании разворота вверх."
        )
    elif key == "bearish_divergence":
        parts.append(
            f"Сигнал «{name}»: цена актива выросла за последние 4 недели, "
            f"но {participant_name} сокращают чистую позицию. Это продажи на росте — "
            f"классический признак скрытого распределения перед снижением."
        )

    # Backtest reference
    dir_word = "роста" if direction == "bullish" else "снижения"
    wr_quality = "высокий" if wr >= 60 else ("умеренный" if wr >= 50 else "ниже 50%")

    parts.append(
        f"Бэктест: за всю историю ({count} случаев) после такого сигнала цена через "
        f"{h} нед. двигалась в ожидаемом направлении ({dir_word}) в {wr}% случаев "
        f"(Win Rate — {wr_quality}). "
        f"Средний return: {'+' if mean_r > 0 else ''}{mean_r}%, "
        f"медиана: {'+' if median_r > 0 else ''}{median_r}%."
    )

    return " ".join(parts)


def _build_no_signal_verdict(df, participant_name="Участники"):
    """Build a detailed verdict when there are no active signals."""
    latest = df.iloc[-1]
    parts = []

    net = latest["net"]
    net_chg = latest["wow_change_net"]
    cot_idx = latest.get("cot_index_52w", 50)

    parts.append(
        f"Активных сигналов не обнаружено — ни один из 8 отслеживаемых паттернов не сработал."
    )

    # Provide context on where positioning is
    if 30 <= cot_idx <= 70:
        parts.append(
            f"COT Index 52w = {cot_idx:.1f}% — позиционирование находится в нейтральной зоне "
            f"(между 30% и 70%), далеко от экстремумов."
        )
    elif cot_idx < 30:
        parts.append(
            f"COT Index 52w = {cot_idx:.1f}% — позиционирование ближе к нижней границе, "
            f"но пока не достигло экстремальных уровней (≤10%)."
        )
    else:
        parts.append(
            f"COT Index 52w = {cot_idx:.1f}% — позиционирование ближе к верхней границе, "
            f"но пока не достигло экстремальных уровней (≥90%)."
        )

    if abs(net_chg) > 0:
        direction_word = "в сторону лонга" if net_chg > 0 else "в сторону шорта"
        parts.append(
            f"За неделю чистая позиция сдвинулась {direction_word} на {_fmt(abs(net_chg))}, "
            f"но масштаб изменения находится в пределах нормы (не входит в топ-5%/нижние-5%)."
        )

    parts.append(
        "Рекомендация: продолжать мониторинг. Отсутствие сигналов — это тоже информация: "
        "рынок не находится в зоне аномалий, и текущий тренд может продолжиться без резкого разворота."
    )

    return parts


def run_full_interpretation(df, participant_name="Участники"):
    """
    Main entry point. Returns a dict with all interpretation data.
    """
    active_keys = detect_active_signals(df)
    backtest_results = backtest_all_active_signals(df, active_keys)
    situation_lines = generate_situation_text(df, participant_name)
    verdict_paragraphs, verdict_class = generate_verdict(backtest_results, df, participant_name)

    return {
        "situation": situation_lines,
        "active_signals": active_keys,
        "backtest_results": backtest_results,
        "verdict_paragraphs": verdict_paragraphs,
        "verdict_class": verdict_class,
    }

