"""
Æsirian FastMCP Server — Modern async MCP server with multiple transports

Replaces legacy stdio-only server with:
- FastMCP (async, multi-transport: stdio, SSE, HTTP)
- Structured tool definitions with Pydantic models
- Connection pooling and request timeout
- Auth middleware support
- Health check endpoint
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Setup paths
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))

# ─── FastMCP App ───

mcp = FastMCP("aesirian")


# ─── Tool Input Models ───


class AnalyzeChapterInput(BaseModel):
    text: str = Field(description="Chapter text to analyze", min_length=10)


class StyleFingerprintInput(BaseModel):
    text: str = Field(description="Novel text", min_length=50)


class SimulateInput(BaseModel):
    project_id: str = Field(description="Project ID")
    hypothesis: str = Field(description="Hypothesis, e.g. 如果主角发现配角在撒谎")
    belief_changes: list[dict] = Field(default_factory=list, description="Belief changes to apply")


class DivergeInput(BaseModel):
    fragments: list[str] = Field(description="2-8 scene fragments", min_length=2, max_length=8)


class TomQueryInput(BaseModel):
    project_id: str = Field(description="Project ID")


class GenerateInput(BaseModel):
    premise: str = Field(description="One-line story idea", min_length=5)


class ExportMarkdownInput(BaseModel):
    project_id: str = Field(description="Project ID")


class AssembleFromSampleInput(BaseModel):
    text: str = Field(description="Sample story (500+ chars recommended)", min_length=30)


class EditFourCardsInput(BaseModel):
    project: dict = Field(description="FourCardProject JSON as currently displayed")
    edit: dict = Field(description="CardEdit JSON: {card, index?, field, before, after}")
    decisions: list[dict] = Field(
        default_factory=list,
        description='Optional author rulings: [{"id": <diff_id>, "action": "accept"|"reject"}]',
    )


class DemoFourCardsInput(BaseModel):
    pass


class FourCardsStatsInput(BaseModel):
    """四卡裁决统计（P3-12）——无入参。"""

    pass


# ─── Helper Functions ───


def _get_orchestrator():
    from core.orchestrator import Orchestrator
    from core.persistence.store import ProjectStore

    return Orchestrator(store=ProjectStore())


# ─── MCP Tools ───


@mcp.tool()
async def analyze_chapter(input: AnalyzeChapterInput) -> dict:
    """
    Run full 文鉴 audit on chapter text (zero-API, registry-driven gate set).
    Gate count is derived from wenjian.audit.gates.GATE_CATALOG (not hardcoded).
    Returns pass/warn/block results with overall score.
    """
    from core.wenjian.audit.gates import GATE_TOTAL
    from core.wenjian.audit.pipeline import AuditPipeline

    pipe = AuditPipeline()
    ctx = pipe._enrich_context({"text": input.text, "title": "mcp"})
    report = pipe.run_full(ctx)
    results = [r.to_dict() if hasattr(r, "to_dict") else r for r in report.gate_results]
    failed = [r for r in results if not r.get("passed", True)]
    return {
        "total_gates": len(results),
        "registry_total": GATE_TOTAL,
        "failed": len(failed),
        "issues": failed[:20],
        "overall_score": getattr(report, "overall_score", None),
    }


@mcp.tool()
async def style_fingerprint(input: StyleFingerprintInput) -> dict:
    """
    Extract style fingerprint: 6-dim radar (虚词/词汇/句长/标点/对话/感官) + sensory distribution.
    """
    from core.wenjian.fingerprint import extract_style_fingerprint, generate_style_dashboard

    sf = extract_style_fingerprint(input.text, novel_name="mcp")
    return generate_style_dashboard(sf)


@mcp.tool()
async def simulate(input: SimulateInput) -> dict:
    """
    What-if simulation on a project: clone ToM, apply belief changes, return plot branches.
    Does NOT mutate the main project.
    """
    orch = _get_orchestrator()
    try:
        return orch.simulate_hypothesis(
            input.project_id,
            input.hypothesis,
            input.belief_changes,
            3,
        )
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def diverge(input: DivergeInput) -> dict:
    """
    Fragment divergence: 2-8 scene fragments -> 5 worldline previews
    (genre x structure, 5 beats + opening).
    """
    orch = _get_orchestrator()
    try:
        return orch.diverge_fragments(input.fragments, 5)
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
async def tom_query(input: TomQueryInput) -> dict:
    """
    Query a project's character belief states + current tensions (Theory of Mind engine).
    """
    orch = _get_orchestrator()
    try:
        mg = orch.get_mind_grid_data(input.project_id)
    except ValueError as e:
        return {"error": str(e)}
    chars = [
        {
            "name": c.get("name"),
            "world_beliefs": c.get("world_beliefs", {}),
            "active_goals": c.get("active_goals", []),
            "secret_count": c.get("secret_count", 0),
        }
        for c in mg.get("characters", [])
    ]
    return {
        "characters": chars,
        "tension_points": mg.get("tension_points", []),
        "chapter": mg.get("chapter"),
        "transportation_trend": mg.get("transportation_trend"),
    }


@mcp.tool()
async def list_projects() -> dict:
    """List all persisted projects."""
    orch = _get_orchestrator()
    return {"projects": orch.list_projects()}


@mcp.tool()
async def generate(input: GenerateInput) -> dict:
    """
    LLM-generate a chapter draft (200-500 chars) from a one-line prompt.
    Requires LLM env keys (OPENAI_API_KEY, DEEPSEEK_API_KEY, etc.).
    """
    from core.pydantic_ai_engine import get_pydantic_ai_engine

    engine = get_pydantic_ai_engine()
    if not engine.available():
        return {
            "error": "LLM unavailable — set OPENAI_API_KEY / DEEPSEEK_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY"
        }

    context = {"characters": [], "current_chapter": 1}
    text = engine.generate_chapter(input.premise, context, 300)
    if not text:
        return {"error": "generation failed (quality gate)"}
    return {"text": text, "chars": len(text)}


@mcp.tool()
async def export_markdown(input: ExportMarkdownInput) -> dict:
    """Export a project's full novel as Markdown (returns text)."""
    orch = _get_orchestrator()
    try:
        project = orch.get_project(input.project_id)
    except ValueError as e:
        return {"error": str(e)}
    if not project:
        return {"error": f"project {input.project_id} not found"}

    import tempfile

    from core.export.exporter import export_project_markdown

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = tmp.name
    export_project_markdown(project, tmp_path)
    with open(tmp_path, encoding="utf-8") as f:
        content = f.read()
    os.unlink(tmp_path)
    return {"markdown": content, "chapters": len(project.chapters)}


@mcp.tool()
async def assemble_from_sample_story(input: AssembleFromSampleInput) -> dict:
    """
    FOUR-CARD stage A: sample story -> four-card structure (character bios + framework
    beats + chapter beats + sample score). LLM-enhanced, rule-driven offline fallback.
    """
    from core.diff_engine import forward_derive

    project = forward_derive(input.text)
    return {
        "project": project.model_dump(),
        "summary": project.card_summary(),
    }


@mcp.tool()
async def edit_four_cards(input: EditFourCardsInput) -> dict:
    """
    FOUR-CARD stage B: author edits one card -> propagation diffs (never silent).
    Pass project JSON as displayed + CardEdit; optional rulings accept/reject each diff.
    """
    from core.diff_engine import CardEdit, apply_diff, propose_diff
    from core.four_cards import FourCardProject

    try:
        project = FourCardProject.model_validate(input.project)
        edit = CardEdit.model_validate(input.edit)
    except Exception as e:  # pydantic 校验失败要如实暴露给作者
        return {"error": f"invalid project/edit payload: {e}"}

    diffs = propose_diff(edit, project)
    for rule in input.decisions or []:
        did = rule.get("id")
        action = rule.get("action")
        if did and action in ("accept", "reject"):
            apply_diff(project, did, accept=(action == "accept"))

    return {
        "diffs": [d.model_dump() for d in diffs],
        "pending": sum(1 for d in project.pending_diffs if d.status == "pending"),
        "project": project.model_dump(),
    }


@mcp.tool()
async def four_cards_stats(input: FourCardsStatsInput) -> dict:
    """
    P3-12: diff decision telemetry (accept/reject rate, source->target/field
    distribution). Author-trust signal for weekly gate/product tuning.
    """
    from core.diff_engine import decision_stats

    return decision_stats()


@mcp.tool()
async def demo_luoyang(input: DemoFourCardsInput) -> dict:
    """
    M3 demo: load the pre-seeded《洛阳星港》four-card demo project with 3 sample
    propagation diffs (pending). Read-only snapshot from pwa/demo/demo_luoyang_project.json
    (generated by tools/seed_demo_data.py) — never mutates engine or DB.
    """
    demo_path = os.path.join(ROOT, "pwa", "demo", "demo_luoyang_project.json")
    if not os.path.exists(demo_path):
        return {"error": "demo json missing — run: python tools/seed_demo_data.py"}
    import json as _json

    with open(demo_path, encoding="utf-8") as f:
        project = _json.load(f)
    from core.four_cards import FourCardProject

    p = FourCardProject.model_validate(project)
    return {
        "project": p.model_dump(),
        "summary": p.card_summary(),
        "sample_diffs": len(p.pending_diffs),
        "note": "演示快照：陈默/曹渊四卡 + 3 条联动提案样例（编辑任一张卡可看到新提案）",
    }


# ─── Health Check ───


@mcp.tool()
async def health_check() -> dict:
    """Health check endpoint."""
    from core.observability import health_check as obs_health

    return {
        "status": "healthy",
        "service": "aesirian-mcp",
        "version": "1.0.0",
        "observability": obs_health(),
    }


# ─── Lifespan ───


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Application lifespan handler."""
    # Startup
    from core.observability import configure_observability

    configure_observability()
    yield
    # Shutdown (cleanup if needed)


mcp.lifespan = lifespan


# ─── Entry Points ───


def run_stdio():
    """Run MCP server over stdio (for Claude Desktop)."""
    mcp.run(transport="stdio")


def run_sse(host: str = "127.0.0.1", port: int = 8765):
    """Run MCP server over SSE (for web clients)."""
    mcp.run(transport="sse", host=host, port=port)


def run_http(host: str = "127.0.0.1", port: int = 8765):
    """Run MCP server over Streamable HTTP (CORS-open for local demo UI)."""
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    app = mcp.http_app()
    # 本地开发演示期开放跨源（four_cards.html 等 MCP client 页面可直接调用）
    app = CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Æsirian MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.transport == "stdio":
        run_stdio()
    elif args.transport == "sse":
        run_sse(args.host, args.port)
    elif args.transport == "http":
        run_http(args.host, args.port)
