"""
Æsirian MCP Server — Model Context Protocol (stdio, JSON-RPC 2.0)

⚠️ DEPRECATED（M1-3 · engineering-plan-v11.md §3.1 M1-3）
    本文件为旧版 stdio-only MCP server（JSON-RPC 2.0 手写分发），已停止演进。
    统一入口为 mcp_server_fast.py（FastMCP：stdio / SSE / HTTP 多传输，
    10 工具 + Pydantic 结构化输入 + 健康检查）。
    本模块仅因既有引用保留兼容（tests/test_mcp_server.py、历史
    `claude mcp add` 配置中的旧进程），不做新功能演进；
    新代码 / 新启动路径一律基于 mcp_server_fast.py；
    计划于 V1.2 完成引用迁移后移除本文件。

AI agent 可调用的 Æsirian 分析能力。所有底层模块均已被
L2 (pytest) / L3 (Playwright) 验证。

Exposed tools:
  - analyze_chapter   : 167 道文鉴门禁审计（zero-API）
  - style_fingerprint : 风格指纹提取 + 6维雷达
  - simulate          : 假设推演（克隆式，不污染主线）
  - diverge           : 碎片 → 世界线发散
  - tom_query         : 查询项目角色信念状态 + 张力
  - list_projects     : 列出持久化项目
  - generate          : LLM 章节生成
  - export_markdown   : 导出项目为 Markdown

Usage（本文件已 DEPRECATED，请使用统一入口 mcp_server_fast.py）:
  python mcp_server_fast.py --transport stdio
  claude mcp add aesirian -- python mcp_server_fast.py --transport stdio
  # 本文件 serve_stdio 仅保留兼容旧引用（tests/test_mcp_server.py、旧配置）
"""
from __future__ import annotations

import json
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))


def _get_orchestrator():
    from core.orchestrator import Orchestrator
    from core.persistence.store import ProjectStore
    return Orchestrator(store=ProjectStore())


TOOL_DEFINITIONS = [
    {
        "name": "analyze_chapter",
        "description": "Run 167-gate wenjian audit on chapter text (zero-API). Returns pass/warn/block results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Chapter text to analyze"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "style_fingerprint",
        "description": "Extract style fingerprint: 6-dim radar (虚词/词汇/句长/标点/对话/感官) + sensory distribution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Novel text"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "simulate",
        "description": "What-if simulation on a project: clone ToM, apply belief changes, return plot branches. Does NOT mutate the main project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "hypothesis": {"type": "string", "description": "e.g. 如果主角发现配角在撒谎"},
                "belief_changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "character": {"type": "string"},
                            "proposition": {"type": "string"},
                            "value": {"type": "boolean"},
                        },
                    },
                },
            },
            "required": ["project_id", "hypothesis"],
        },
    },
    {
        "name": "diverge",
        "description": "Fragment divergence: 2-8 scene fragments -> 5 worldline previews (genre x structure, 5 beats + opening).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fragments": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["fragments"],
        },
    },
    {
        "name": "tom_query",
        "description": "Query a project's character belief states + current tensions (Theory of Mind engine).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "list_projects",
        "description": "List all persisted projects.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate",
        "description": "LLM-generate a chapter draft (200-500 chars) from a one-line prompt. Requires LLM env keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "premise": {"type": "string", "description": "One-line idea"},
            },
            "required": ["premise"],
        },
    },
    {
        "name": "export_markdown",
        "description": "Export a project's full novel as Markdown (returns text).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
]

SERVER_INFO = {
    "name": "aesirian",
    "version": "1.0.0",
    "protocolVersion": "2024-11-05",
}


# ─── Tool handlers ──────────────────────────

def _tool_analyze_chapter(args: dict) -> dict:
    text = args.get("text", "").strip()
    if not text:
        return {"error": "text is required"}
    from wenjian.audit.pipeline import AuditPipeline
    pipe = AuditPipeline()
    ctx = pipe._enrich_context({"text": text, "title": "mcp"})
    report = pipe.run_full(ctx)
    results = [r.to_dict() if hasattr(r, "to_dict") else r for r in report.gate_results]
    failed = [r for r in results if not r.get("passed", True)]
    return {
        "total_gates": len(results),
        "failed": len(failed),
        "issues": failed[:20],
        "overall_score": getattr(report, "overall_score", None),
    }


def _tool_style_fingerprint(args: dict) -> dict:
    text = args.get("text", "").strip()
    if not text:
        return {"error": "text is required"}
    from core.wenjian.fingerprint import extract_style_fingerprint, generate_style_dashboard
    sf = extract_style_fingerprint(text, novel_name="mcp")
    return generate_style_dashboard(sf)


def _tool_simulate(args: dict) -> dict:
    orch = _get_orchestrator()
    try:
        return orch.simulate_hypothesis(
            args["project_id"], args.get("hypothesis", ""),
            args.get("belief_changes", []), 3,
        )
    except ValueError as e:
        return {"error": str(e)}


def _tool_diverge(args: dict) -> dict:
    orch = _get_orchestrator()
    try:
        return orch.diverge_fragments(args.get("fragments", []), 5)
    except ValueError as e:
        return {"error": str(e)}


def _tool_tom_query(args: dict) -> dict:
    orch = _get_orchestrator()
    try:
        mg = orch.get_mind_grid_data(args["project_id"])
    except ValueError as e:
        return {"error": str(e)}
    chars = []
    for c in mg.get("characters", []):
        chars.append({
            "name": c.get("name"),
            "world_beliefs": c.get("world_beliefs", {}),
            "active_goals": c.get("active_goals", []),
            "secret_count": c.get("secret_count", 0),
        })
    return {
        "characters": chars,
        "tension_points": mg.get("tension_points", []),
        "chapter": mg.get("chapter"),
        "transportation_trend": mg.get("transportation_trend"),
    }


def _tool_list_projects(args: dict) -> dict:
    orch = _get_orchestrator()
    return {"projects": orch.list_projects()}


def _tool_generate(args: dict) -> dict:
    premise = args.get("premise", "").strip()
    if not premise:
        return {"error": "premise is required"}
    from core.llm_engine import get_llm_engine
    llm = get_llm_engine()
    if not llm.available():
        return {"error": "LLM unavailable — set DEEPSEEK_API_KEY / OPENAI_API_KEY / ZHIPU_API_KEY"}
    text = llm.generate_chapter(premise, {"characters": [], "current_chapter": 1}, 300)
    if not text:
        return {"error": "generation failed (quality gate)"}
    return {"text": text, "chars": len(text)}


def _tool_export_markdown(args: dict) -> dict:
    orch = _get_orchestrator()
    try:
        project = orch.get_project(args["project_id"])
    except ValueError as e:
        return {"error": str(e)}
    if not project:
        return {"error": f"project {args['project_id']} not found"}
    import tempfile
    from core.export.exporter import export_project_markdown
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.close()
    export_project_markdown(project, tmp.name)
    with open(tmp.name, encoding="utf-8") as f:
        content = f.read()
    os.unlink(tmp.name)
    return {"markdown": content, "chapters": len(project.chapters)}


TOOL_HANDLERS = {
    "analyze_chapter": _tool_analyze_chapter,
    "style_fingerprint": _tool_style_fingerprint,
    "simulate": _tool_simulate,
    "diverge": _tool_diverge,
    "tom_query": _tool_tom_query,
    "list_projects": _tool_list_projects,
    "generate": _tool_generate,
    "export_markdown": _tool_export_markdown,
}


# ─── JSON-RPC 2.0 plumbing ──────────────────────────

def _handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": SERVER_INFO["protocolVersion"],
        "capabilities": {"tools": {}},
        "serverInfo": SERVER_INFO,
    }


def _handle_tools_list(params: dict) -> dict:
    return {"tools": TOOL_DEFINITIONS}


def _handle_tools_call(params: dict) -> dict:
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    if name not in TOOL_HANDLERS:
        return {"error": {"code": -32601, "message": f"Tool not found: {name}"}}
    try:
        result = TOOL_HANDLERS[name](arguments)
        if isinstance(result, dict) and "error" in result:
            return {"error": {"code": -32000, "message": str(result["error"])}}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
    except Exception as e:
        return {"error": {"code": -32000, "message": f"{name}: {e}"}}


def dispatch_request(msg: dict) -> str | None:
    method: str = msg.get("method", "")
    msg_id = msg.get("id")
    params: dict = msg.get("params", {})

    if method == "initialize":
        return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": _handle_initialize(params)}, ensure_ascii=False)
    if method == "tools/list":
        return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": _handle_tools_list(params)}, ensure_ascii=False)
    if method == "tools/call":
        result = _handle_tools_call(params)
        if "error" in result:
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": result["error"]}, ensure_ascii=False)
        return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}, ensure_ascii=False)
    if method in ("notifications/initialized", "initialized"):
        return None
    return json.dumps({"jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}}, ensure_ascii=False)


def serve_stdio():
    """DEPRECATED（M1-3）兼容入口：仅保留旧引用（tests/test_mcp_server.py 等）使用；新进程请走 mcp_server_fast.py。"""
    print("aesirian MCP server ready", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": f"Parse error: {e}"}}) + "\n")
            sys.stdout.flush()
            continue
        try:
            response = dispatch_request(msg)
            if response is not None:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"),
                                         "error": {"code": -32603, "message": f"Internal error: {e}"}}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve_stdio()