from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

INK = "#111827"
MUTED = "#6b7280"
LINE = "#d1d5db"
SOFT = "#f3f4f6"
SERIES = ("#111827", "#6b7280", "#2563eb", "#9ca3af")
OUTCOME = {
    "pass": "#111827",
    "answer_or_metric_fail": "#9ca3af",
    "content_type_miss": "#d97706",
    "retrieval_miss": "#dc2626",
    "refusal_fail": "#dc2626",
    "error": "#7f1d1d",
}


def metrics_overview(path: Path, rows: list[dict[str, Any]]) -> None:
    metrics = [
        ("source_hit_at_5", "Hit@5"),
        ("content_type_hit_rate", "Type Accuracy"),
        ("mrr", "MRR"),
    ]
    _grouped_bar_chart(path, "Retrieval metrics", rows, metrics, value_max=1.0)


def hit_at_k_chart(path: Path, rows: list[dict[str, Any]], k_values: tuple[int, ...]) -> None:
    width, height = 860, 380
    left, right, top, bottom = 72, 32, 56, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = list(k_values)
    parts = [_frame(width, height), _title("Source hit@k", 28)]
    parts.extend(_y_axis(left, top, plot_w, plot_h, 1.0))
    for index, row in enumerate(rows):
        points = []
        for item in xs:
            x = left + (xs.index(item) / max(len(xs) - 1, 1)) * plot_w
            value = _number(row.get(f"source_hit_at_{item}")) or 0
            y = top + plot_h - value * plot_h
            points.append((x, y))
        color = SERIES[index % len(SERIES)]
        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        parts.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
    for index, item in enumerate(xs):
        x = left + (index / max(len(xs) - 1, 1)) * plot_w
        parts.append(_text(x, height - 38, f"@{item}", "middle", 12, MUTED))
    parts.append(_legend(rows, width - 270, 24))
    _write(path, width, height, parts)


def latency_chart(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 820, 120 + len(rows) * 54
    left, right, top = 164, 34, 58
    max_value = max((_number(row.get("avg_elapsed_ms")) or 0 for row in rows), default=1)
    max_value = max(max_value, 1)
    plot_w = width - left - right
    parts = [_frame(width, height), _title("Average latency", 28)]
    for index, row in enumerate(rows):
        y = top + index * 54
        value = _number(row.get("avg_elapsed_ms")) or 0
        bar_w = (value / max_value) * plot_w
        color = SERIES[index % len(SERIES)]
        parts.append(_text(left - 12, y + 16, row["run"], "end", 12, INK))
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w:.1f}" height="24" rx="4" fill="{color}"/>')
        parts.append(_text(left + bar_w + 8, y + 16, f"{value / 1000:.1f}s", "start", 12, MUTED))
    _write(path, width, height, parts)


def outcome_heatmap(path: Path, sample_rows: list[dict[str, Any]]) -> None:
    run_labels = _unique(row["run"] for row in sample_rows)
    sample_ids = _unique(row["id"] for row in sample_rows)
    left, top, cell_w, cell_h = 260, 62, 108, 26
    width = left + len(run_labels) * cell_w + 34
    height = top + len(sample_ids) * cell_h + 76
    by_key = {(row["run"], row["id"]): row["outcome"] for row in sample_rows}
    parts = [_frame(width, height), _title("Per-sample outcome", 24)]
    for col, run in enumerate(run_labels):
        parts.append(_text(left + col * cell_w + cell_w / 2, top - 14, run, "middle", 12, INK))
    for row_index, sample_id in enumerate(sample_ids):
        y = top + row_index * cell_h
        parts.append(_text(left - 12, y + 17, sample_id, "end", 11, MUTED))
        for col, run in enumerate(run_labels):
            outcome = by_key.get((run, sample_id), "error")
            fill = OUTCOME.get(outcome, LINE)
            x = left + col * cell_w
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="18" rx="4" fill="{fill}"/>')
    parts.append(_outcome_legend(24, height - 42))
    _write(path, width, height, parts)


def _grouped_bar_chart(
    path: Path,
    title: str,
    rows: list[dict[str, Any]],
    metrics: list[tuple[str, str]],
    value_max: float,
) -> None:
    width, height = 900, 420
    left, right, top, bottom = 76, 32, 62, 86
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(metrics)
    bar_w = min(28, group_w / (len(rows) + 1.4))
    parts = [_frame(width, height), _title(title, 28)]
    parts.extend(_y_axis(left, top, plot_w, plot_h, value_max))
    for metric_index, (key, label) in enumerate(metrics):
        group_x = left + metric_index * group_w
        for row_index, row in enumerate(rows):
            value = _number(row.get(key)) or 0
            x = group_x + (group_w - bar_w * len(rows)) / 2 + row_index * bar_w
            bar_h = (value / value_max) * plot_h
            y = top + plot_h - bar_h
            color = SERIES[row_index % len(SERIES)]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 4:.1f}" height="{bar_h:.1f}" rx="4" fill="{color}"/>')
            parts.append(_text(x + bar_w / 2 - 2, y - 6, _pct(value), "middle", 10, MUTED))
        parts.append(_text(group_x + group_w / 2, height - 42, label, "middle", 12, INK))
    parts.append(_legend(rows, width - 270, 24))
    _write(path, width, height, parts)


def _y_axis(left: int, top: int, plot_w: int, plot_h: int, value_max: float) -> list[str]:
    parts = []
    for step in range(5):
        value = value_max * step / 4
        y = top + plot_h - (value / value_max) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        parts.append(_text(left - 12, y + 4, _pct(value), "end", 11, MUTED))
    return parts


def _legend(rows: list[dict[str, Any]], x: int, y: int) -> str:
    parts = []
    for index, row in enumerate(rows):
        item_y = y + index * 20
        color = SERIES[index % len(SERIES)]
        parts.append(f'<rect x="{x}" y="{item_y}" width="12" height="12" rx="3" fill="{color}"/>')
        parts.append(_text(x + 18, item_y + 10, row["run"], "start", 12, INK))
    return "".join(parts)


def _outcome_legend(x: int, y: int) -> str:
    labels = [("pass", "pass"), ("answer_or_metric_fail", "answer/metric fail"), ("retrieval_miss", "retrieval miss")]
    parts = []
    cursor = x
    for key, label in labels:
        parts.append(f'<rect x="{cursor}" y="{y}" width="12" height="12" rx="3" fill="{OUTCOME[key]}"/>')
        parts.append(_text(cursor + 18, y + 10, label, "start", 12, MUTED))
        cursor += 154
    return "".join(parts)


def _frame(width: int, height: int) -> str:
    return f'<rect width="{width}" height="{height}" fill="white"/><rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="none" stroke="{LINE}"/>'


def _title(text: str, x: int) -> str:
    return _text(x, 34, text, "start", 16, INK, weight=600)


def _text(x: float, y: float, text: Any, anchor: str, size: int, color: str, weight: int = 400) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Inter, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(text))}</text>'


def _write(path: Path, width: int, height: int, parts: list[str]) -> None:
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        + "".join(parts)
        + "</svg>\n",
        encoding="utf-8",
    )


def _unique(values: Any) -> list[Any]:
    seen, items = set(), []
    for value in values:
        if value not in seen:
            seen.add(value)
            items.append(value)
    return items


def _number(value: Any) -> float | None:
    return value if isinstance(value, int | float) else None


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"

