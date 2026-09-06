"""HTML Report Generator — produces visual audit reports from gate results.

Includes Netflix-style attention risk dashboard (drop-off analysis).
"""

from datetime import datetime
from pathlib import Path
from typing import Any


def generate_html_report(
    report_data: dict[str, Any],
    output_path: str,
    chapter_results: list | None = None,
    novel_name: str = "My Novel",
):
    """Generate a standalone HTML audit report."""
    gates = report_data.get("gates", report_data.get("gate_results", []))
    status = report_data.get("overall_status", "unknown")
    total = len(gates)
    passed = sum(1 for g in gates if g.get("passed", True))
    blocked = sum(
        1 for g in gates if not g.get("passed", True) and g.get("severity", "") == "block"
    )
    warned = sum(1 for g in gates if not g.get("passed", True) and g.get("severity", "") == "warn")

    gate_rows = ""
    for g in sorted(gates, key=lambda x: (x.get("severity", "pass"), x.get("gate_id", ""))):
        gid = g.get("gate_id", "??")
        name = g.get("name", "")
        sev = g.get("severity", "pass")
        passed_flag = g.get("passed", True)
        msg = g.get("message", "")
        icon = "✅" if passed_flag else "❌"
        color = "#22c55e" if passed_flag else ("#ef4444" if sev == "block" else "#f59e0b")
        sev_label = {"block": "阻断", "warn": "警告", "pass": "通过"}.get(sev, sev)
        gate_rows += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{icon}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;font-family:monospace">{gid}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{name}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;color:{color};font-weight:bold">{sev_label}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;font-size:0.9em">{msg}</td>
        </tr>"""

    chapters_html = ""
    if chapter_results:
        chapters_html = """<h2 style="margin-top:30px">章节分析</h2><table style="width:100%;border-collapse:collapse;font-size:0.95em">"""
        chapters_html += """<tr style="background:#f3f4f6;font-weight:bold">
            <th style="padding:8px 12px;text-align:left">章</th>
            <th style="padding:8px 12px;text-align:left">字数</th>
            <th style="padding:8px 12px;text-align:left">鸿沟密度</th>
            <th style="padding:8px 12px;text-align:left">翻转</th>
            <th style="padding:8px 12px;text-align:left">触点</th>
            <th style="padding:8px 12px;text-align:left">情绪</th>
            <th style="padding:8px 12px;text-align:left">钩子位置</th>
        </tr>"""
        for ch in chapter_results:
            flipped = "✅" if ch.get("scene_flipped") else "❌"
            chapters_html += f"""<tr>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("chapter_index", "?") + 1}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("char_count", 0)}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("gap_density", 0):.2f}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{flipped}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("touchpoints", 0)}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("direct_emotions", 0)}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb">{ch.get("first_hook_position", "N/A")}</td>
            </tr>"""
        chapters_html += "</table>"

    # Gap density mini-chart (ASCII simulated bar chart in HTML)
    gap_bars = ""
    if chapter_results:
        densities = [ch.get("gap_density", 0) for ch in chapter_results]
        max_d = max(densities) if densities else 1
        for i, d in enumerate(densities):
            pct = max(5, int((d / max(max_d, 0.1)) * 100))
            color = "#22c55e" if 1.0 <= d <= 4.0 else ("#f59e0b" if d < 1.0 else "#ef4444")
            gap_bars += f"""<div style="margin:4px 0;display:flex;align-items:center;">
                <span style="width:30px;font-size:0.8em;color:#666">ch{i + 1}</span>
                <div style="width:{pct}%;height:20px;background:{color};border-radius:3px;min-width:8px"></div>
                <span style="margin-left:6px;font-size:0.8em">{d:.2f}</span>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文鉴 WenJian — 审计报告</title>
<style>
  body {{ font-family: -apple-system, 'Noto Sans SC', sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #f9fafb; color: #1f2937; }}
  .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }}
  .header h1 {{ margin: 0; font-size: 1.6em; }}
  .header p {{ margin: 8px 0 0; opacity: 0.9; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .stat-card {{ background: white; border-radius: 8px; padding: 16px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .stat-number {{ font-size: 2em; font-weight: bold; }}
  .stat-label {{ font-size: 0.8em; color: #6b7280; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th {{ background: #f3f4f6; padding: 8px 12px; text-align: left; font-weight: 600; }}
  tr:hover {{ background: #f9fafb; }}
  .chart-box {{ background: white; border-radius: 8px; padding: 20px; margin-top: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
</style>
</head>
<body>
<div class="header">
    <h1>📖 {novel_name}</h1>
    <p>文鉴 WenJian 审计报告 · {datetime.now().strftime("%Y-%m-%d %H:%M")} · 状态: {"✅" if status == "pass" else "⚠️" if status == "warn" else "❌"} {status.upper()}</p>
</div>

<div class="stats">
    <div class="stat-card"><div class="stat-number">{total}</div><div class="stat-label">门禁总数</div></div>
    <div class="stat-card"><div class="stat-number" style="color:#22c55e">{passed}</div><div class="stat-label">通过</div></div>
    <div class="stat-card"><div class="stat-number" style="color:#f59e0b">{warned}</div><div class="stat-label">警告</div></div>
    <div class="stat-card"><div class="stat-number" style="color:#ef4444">{blocked}</div><div class="stat-label">阻断</div></div>
</div>

<div class="chart-box">
    <h3 style="margin:0 0 12px">📊 鸿沟密度趋势</h3>
    {gap_bars or "<p style='color:#999'>暂无数据</p>"}
</div>

<h2 style="margin-top:30px">门禁详情</h2>
<table>
    <tr><th style="width:30px"></th><th style="width:80px">ID</th><th>名称</th><th style="width:60px">级别</th><th>信息</th></tr>
    {gate_rows}
</table>

{chapters_html}

<div style="margin-top:30px;padding:20px;background:#f3f4f6;border-radius:8px;text-align:center;font-size:0.8em;color:#6b7280">
    文鉴 WenJian v1.0 — 由 文鉴 WenJian 引擎生成
</div>
</body>
</html>"""

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_path_obj.write_text(html, encoding="utf-8")
    return str(output_path_obj)


def generate_attention_dashboard(
    chapter_results: list[dict],
    output_path: str,
    novel_name: str = "我的小说",
) -> str:
    """Generate Netflix-style attention risk dashboard (drop-off analysis).

    chapter_results: list of dicts from LocalAnalyzer with keys:
        gap_density, touchpoints, direct_emotions, emotion_to_touchpoint_ratio,
        scene_flipped, first_hook_position, chapter_index
    """
    if not chapter_results:
        chapter_results = []

    # Risk scoring: 0-100 per chapter
    risk_scores = []
    for i, ch in enumerate(chapter_results):
        risk = 0
        reasons = []

        # Gap density too low → risk of boredom
        gd = ch.get("gap_density", 1.0)
        if gd < 0.5:
            risk += 30
            reasons.append("鸿沟密度极低")
        elif gd < 1.0:
            risk += 15
            reasons.append("鸿沟密度偏低")

        # No scene flip → risk of stagnation
        if not ch.get("scene_flipped", True):
            risk += 20
            reasons.append("场景未翻转")

        # Emotion/touchpoint ratio too high → risk of telling not showing
        er = ch.get("emotion_to_touchpoint_ratio", 0)
        if er > 2.0:
            risk += 15
            reasons.append("情绪/触点比过高")
        elif er > 1.5:
            risk += 8
            reasons.append("情绪/触点比偏高")

        # No touchpoints → risk of flat prose
        tp = ch.get("touchpoints", 0)
        if tp < 3:
            risk += 10
            reasons.append("触点不足")

        # Hook too late → risk of early drop
        hp = ch.get("first_hook_position", 0)
        if hp > 300:
            risk += 15
            reasons.append("钩子出现过晚")

        # Dialogue density too low → risk of monotony
        dd = ch.get("dialogue_density", 0.5)
        if dd < 0.1:
            risk += 10
            reasons.append("对话密度过低")

        risk = min(risk, 100)
        risk_scores.append(
            {
                "chapter": i + 1,
                "risk": risk,
                "level": "high" if risk >= 40 else "medium" if risk >= 20 else "low",
                "reasons": reasons,
                "gap_density": gd,
                "touchpoints": tp,
                "emotion_ratio": er,
                "hook_pos": hp,
                "flipped": ch.get("scene_flipped", True),
            }
        )

    avg_risk = round(sum(r["risk"] for r in risk_scores) / max(len(risk_scores), 1), 1)
    high_risk = sum(1 for r in risk_scores if r["level"] == "high")
    medium_risk = sum(1 for r in risk_scores if r["level"] == "medium")

    bars = ""
    for r in risk_scores:
        color = (
            "#ef4444"
            if r["level"] == "high"
            else "#f59e0b"
            if r["level"] == "medium"
            else "#22c55e"
        )
        label = (
            "🔴高风险"
            if r["level"] == "high"
            else "🟡中风险"
            if r["level"] == "medium"
            else "🟢低风险"
        )
        bar_width = max(8, r["risk"])
        reasons_text = " | ".join(r["reasons"]) if r["reasons"] else "正常"
        bars += f"""<div style="margin:6px 0;display:flex;align-items:center;">
            <span style="width:40px;font-size:0.85em;color:#666">ch{r["chapter"]}</span>
            <div style="width:{bar_width}%;height:22px;background:{color};border-radius:4px;min-width:8px;display:flex;align-items:center;padding-left:6px;color:white;font-size:0.75em;font-weight:bold">{r["risk"]}</div>
            <span style="margin-left:8px;font-size:0.78em;color:#666">{label} {reasons_text[:40]}</span>
        </div>"""

    # Metric timeline table
    timeline = ""
    for r in risk_scores:
        fl = "✅" if r["flipped"] else "❌"
        timeline += f"""<tr>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">ch{r["chapter"]}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["risk"]}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["gap_density"]:.2f}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["touchpoints"]}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["emotion_ratio"]:.2f}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{fl}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["hook_pos"]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文鉴 WenJian — 注意力风险看板</title>
<style>
  body {{ font-family: -apple-system, 'Noto Sans SC', sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 24px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }}
  .header h1 {{ margin: 0; font-size: 1.4em; color: #f8fafc; }}
  .header p {{ margin: 6px 0 0; color: #94a3b8; font-size: 0.85em; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
  .stat-card {{ background: #1e293b; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #334155; }}
  .stat-number {{ font-size: 1.8em; font-weight: bold; }}
  .stat-label {{ font-size: 0.78em; color: #94a3b8; margin-top: 4px; }}
  .dashboard {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }}
  .dashboard h3 {{ margin: 0 0 12px; color: #f8fafc; font-size: 0.95em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
  th {{ background: #334155; padding: 8px; text-align: left; font-weight: 600; color: #94a3b8; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
  tr:hover {{ background: #1e293b; }}
  .netflix-note {{ padding: 12px; background: #1e293b; border-left: 3px solid #ef4444; border-radius: 4px; font-size: 0.82em; color: #94a3b8; margin-top: 16px; }}
</style>
</head>
<body>
<div class="header">
    <h1>🎬 {novel_name} — 注意力风险看板</h1>
    <p>奈飞式 drop-off 风险分析 · {datetime.now().strftime("%Y-%m-%d %H:%M")} · {len(chapter_results)} 章</p>
</div>

<div class="stats">
    <div class="stat-card"><div class="stat-number" style="color:#94a3b8">{len(chapter_results)}</div><div class="stat-label">章节数</div></div>
    <div class="stat-card"><div class="stat-number" style="color:{("#22c55e" if avg_risk < 20 else "#f59e0b" if avg_risk < 40 else "#ef4444")}">{avg_risk}</div><div class="stat-label">平均风险分</div></div>
    <div class="stat-card"><div class="stat-number" style="color:#f59e0b">{medium_risk}</div><div class="stat-label">中风险章节</div></div>
    <div class="stat-card"><div class="stat-number" style="color:#ef4444">{high_risk}</div><div class="stat-label">高风险章节</div></div>
</div>

<div class="dashboard">
    <h3>📊 逐章风险分布</h3>
    {bars or '<p style="color:#64748b;text-align:center">暂无章节数据</p>'}
</div>

<div class="dashboard">
    <h3>📋 指标时间线</h3>
    <table>
        <tr><th>章节</th><th>风险</th><th>鸿沟密度</th><th>触点</th><th>情绪/触点比</th><th>翻转</th><th>钩子位置</th></tr>
        {timeline}
    </table>
</div>

<div class="netflix-note">
    <strong>💡 奈飞式分析说明</strong><br>
    风险分数基于奈飞第二屏写作研究的关键指标合成：鸿沟密度（读者是否感到进展）、场景翻转（价值观是否变化）、触点工程（文本是否生动）、钩子位置（前段是否吸引人）。<br>
    🔴 高风险 ≥ 40  |  🟡 中风险 20-39  |  🟢 低风险 &lt; 20
</div>
</body>
</html>"""

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_path_obj.write_text(html, encoding="utf-8")
    return str(output_path_obj)
