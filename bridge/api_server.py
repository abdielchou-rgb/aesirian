"""
Æsirian Backend Bridge — FastAPI 服务器

连接前端 Electron IDE 与后端 Python 引擎。
持久化：使用 ProjectStore 作为单一数据源，每次请求按需重建运行时状态。
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import contextlib
import tempfile

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bridge.review_api import router as review_router
from core.consistency_gates import GateLevel
from core.entity_extractor import EntityExtractor
from core.export.exporter import (
    export_chapter_markdown,
    export_project_epub,
    export_project_markdown,
)
from core.llm_engine import get_llm_engine
from core.orchestrator import Orchestrator
from core.persistence.store import ProjectStore

app = FastAPI(title="Æsirian Core API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(review_router)

# ─── 持久化存储（全局单例） ───
_store: ProjectStore | None = None


def get_store() -> ProjectStore:
    """获取全局 ProjectStore 实例（惰性初始化）"""
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


def get_orchestrator() -> Orchestrator:
    """获取 Orchestrator 实例（使用全局单例 store）"""
    return Orchestrator(store=get_store())


# ─── Pydantic Schemas ───


class ImportNSEFRequest(BaseModel):
    path: str


class TextSubmitRequest(BaseModel):
    project_id: str
    text: str


class BeliefUpdateRequest(BaseModel):
    project_id: str
    character: str
    proposition: str
    value: str | bool


class ContinueSuggestionRequest(BaseModel):
    project_id: str


# ─── 静态文件 ───

static_dir = os.path.join(os.path.dirname(__file__), "..", "electron_ide", "public")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/dashboard.html")
    async def serve_dashboard():
        return FileResponse(os.path.join(static_dir, "dashboard.html"))
else:
    print(f"[WARN] 静态目录不存在: {static_dir}")

CHAPTER_1_SAMPLE = """陈默的指尖滑过水晶表面，六棱柱在暖黄色的工作灯下泛着冷光。

他修了十一年的罪忆水晶，从没见过这样的——七层加密，军用级A-7协议。

\"这不是市面上能买到的东西。\"他说。

对面的男人没有回答。曹渊从进门到现在没说超过十句话，但陈默知道他听得懂每一句。

\"开价。\"曹渊说，声音平稳得不像在谈一块可能送命的货。

陈默没有回答。他看向工坊门口，走廊里传来管道渗漏的滴答声。洛阳星港B-7层永远弥漫着冷却液和焦糖混合的气味，他闻了十一年，早就不觉得难闻了，但也绝不会想念。

\"这不是价格的问题。\"他把水晶推回去。\"军用的。我不碰军用的。\"

曹渊坐下来，在一张堆满电子垃圾的破椅子上。

\"你听说过失乐园协议吗？\"曹渊问。

陈默的手停住了。失乐园协议——星域法典第七条第十一款，没有正式名称，只有编号。

\"那是安全局的事。\"

\"现在是所有人的事了。\"曹渊说。\"有人复刻了它。在外面。已经运行了三个月。\"

\"你怎么知道？\"

\"因为我就是那个实验室的网络安全顾问。\"

陈默盯着他。修了十一年水晶，他见过太多种说谎的方式。曹渊的破绽不是说谎——是愧疚。

\"你需要我做什么？\"

\"还原水晶里的记忆。然后把结果复制到这张卡里。\"

陈默拿起数据卡看了看。序列号被打磨掉了。

\"你知道就算我做了，也可能什么都改变不了。\"

\"知道。\"

\"那你为什么还要做？\"

曹渊看向工作台上那本残破的《三言二拍》。\"因为我女儿相信因果报应。\"

他站起来，走向门口。\"三天。如果三天后我没有回来，你做了什么决定我都不怪你。\"

陈默一个人坐在工坊里，盯着桌上的水晶。六棱柱在他掌心里微微发热。

他把水晶接入读数仪。"""


@app.get("/chapter-1-sample")
async def get_chapter_1():
    return CHAPTER_1_SAMPLE


# ─── API Routes ───


class NSEFDirectRequest(BaseModel):
    package_id: str = ""
    created_at: str = ""
    source: str = "aesir"
    premise: str = ""
    unit_text: str = ""
    characters: list = []
    open_threads: list = []
    tone: str = "温暖治愈"
    conflict: str = "关系冲突"


@app.post("/import-from-pwa")
async def import_from_pwa(req: NSEFDirectRequest, orch: Orchestrator = Depends(get_orchestrator)):
    """从Æsir PWA直接接收NSEF数据（免文件）"""
    try:
        import uuid

        from nsef import CharacterSeed, NarrativeStatePackage

        # 构建 NSEF 包
        pkg = NarrativeStatePackage(
            package_id=req.package_id or uuid.uuid4().hex[:12],
            premise=req.premise or "未命名灵感",
            unit_text=req.unit_text or "",
            characters=[
                CharacterSeed(name=c.get("name", "角色"), role=c.get("role", ""))
                for c in req.characters
                if isinstance(c, dict)
            ]
            if req.characters
            else [CharacterSeed(name="主角", role="")],
            open_threads=[],
        )
        # 设置风格
        from nsef import ConflictType, Tone

        for t in Tone:
            if t.value == req.tone:
                pkg.tone = t
                break
        for c in ConflictType:
            if c.value == req.conflict:
                pkg.conflict = c
                break

        # 写入临时文件并导入
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(pkg.to_json())

        project = orch.create_project_from_nsef(tmp.name)
        return {
            "status": "ok",
            "project_id": project.project_id,
            "title": project.title,
            "characters": [{"name": c.name} for c in project.tom.get_all_characters()],
            "mind_grid_url": f"http://127.0.0.1:8765/project/{project.project_id}/mind-grid",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/project/from-nsef")
async def import_nsef(req: ImportNSEFRequest, orch: Orchestrator = Depends(get_orchestrator)):
    try:
        project = orch.create_project_from_nsef(req.path)
        return {
            "project_id": project.project_id,
            "title": project.title,
            "genre": project.genre,
            "characters": [
                {"name": c.name, "id": c.character_id} for c in project.tom.get_all_characters()
            ],
            "open_threads": [
                {
                    "thread_id": t.thread_id,
                    "description": t.description,
                }
                for t in (project.kg.get_node_by_name("") or [])
            ]
            if False
            else [],  # placeholder — NSEF注册的开端
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/project/{project_id}/mind-grid")
async def get_mind_grid(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return orch.get_mind_grid_data(project_id)


@app.post("/project/{project_id}/constraints")
async def get_constraints(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return orch.generate_scene_constraints(project_id)


@app.post("/project/{project_id}/submit-chapter")
async def submit_chapter(
    project_id: str, req: TextSubmitRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 使用实体提取器提取门禁上下文
    context = EntityExtractor.to_gate_context(req.text)

    # 生成前门禁检查（G1-G5）
    gate_results = project.gates.pre_generation_check(
        req.text,
        context={
            "facts": context["facts"],
            "char_actions": context["char_actions"],
            "identity_changes": context["identity_changes"],
            "events": context["events"],
            "movements": context["movements"],
        },
    )

    # 如果有 BLOCK 级别门禁 → 拒绝提交
    has_block = any(r.level == GateLevel.BLOCK for r in gate_results)
    if has_block:
        return {
            "submitted": False,
            "gate_results": [r.to_dict() for r in gate_results],
            "overall_score": max(
                0, 100 - sum(20 if r.level == GateLevel.BLOCK else 10 for r in gate_results)
            ),
        }

    # 提交到完整管线
    report = orch.submit_chapter(project_id, req.text)

    # 重新加载以获取更新后的章节号
    project = orch.get_project(project_id)
    current_chapter = project.current_chapter if project else 0

    # #12 跨章一致性结果（从最新章节的审计报告中提取）
    cross_chapter = []
    chapters = orch.store.get_chapters(project_id)
    if chapters:
        import json as _json

        latest = max(chapters, key=lambda c: c.number)
        try:
            latest_report = _json.loads(latest.audit_report_json or "{}")
            cross_chapter = latest_report.get("cross_chapter", [])
        except Exception:
            pass

    return {
        "submitted": True,
        "overall_score": report.overall_score,
        "gate_results": [r.to_dict() for r in gate_results],
        "audit_results": [r.to_dict() for r in report.results],
        "cross_chapter": cross_chapter,
        "plugin_gates": _run_plugins_on_submit(req.text),
        "summary": f"第{current_chapter}章提交完成，{len(report.results)}个审计提醒",
    }


def _run_plugins_on_submit(text: str) -> list[dict]:
    """#23: 提交时运行 gate 类插件（失败静默——插件不阻塞主线）"""
    try:
        from core.plugins import run_gate_plugins

        return run_gate_plugins(text)
    except Exception:
        return []


@app.post("/project/{project_id}/validate")
async def validate_text(
    project_id: str, req: TextSubmitRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    context = EntityExtractor.to_gate_context(req.text)
    results = project.gates.pre_generation_check(
        req.text,
        context={
            "facts": context["facts"],
            "char_actions": context["char_actions"],
            "identity_changes": context["identity_changes"],
            "events": context["events"],
            "movements": context["movements"],
        },
    )
    return {"gate_results": [r.to_dict() for r in results]}


@app.post("/project/{project_id}/belief")
async def update_belief(
    project_id: str, req: BeliefUpdateRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        tensions = orch.update_belief(project_id, req.character, req.proposition, req.value)
        return {
            "tensions": [
                {"type": t.type.value, "description": t.description, "intensity": t.intensity}
                for t in tensions
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/project/{project_id}/suggestions")
async def get_suggestions(
    project_id: str, _req: ContinueSuggestionRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    constraints = orch.generate_scene_constraints(project_id)
    trend = constraints.get("reader_state", {}).get("transportation_trend", "→ 平稳")

    # ── LLM 增强建议（优先） ──
    llm = get_llm_engine()
    llm_suggestions: list[dict] = []
    if llm.available():
        llm_context = {
            "premise": project.title,
            "characters": [c.name for c in project.tom.get_all_characters()],
            "tension_points": constraints.get("tension_points", []),
            "transportation_trend": trend,
            "current_chapter": project.current_chapter,
        }
        llm_suggestions = [s.to_dict() for s in llm.generate_suggestions(llm_context)]

    # ── 规则引擎降级（LLM不可用或结果不足时） ──
    rule_suggestions = _build_rule_suggestions(constraints, trend)

    # ── #13 方法论来源标注 ──
    rule_suggestions = _annotate_methodology(project_id, rule_suggestions, orch)

    # 合并去重：LLM优先，规则补齐到至少5条
    all_suggestions = llm_suggestions + rule_suggestions
    if len(all_suggestions) < 3:
        all_suggestions.append(
            {
                "type": "default",
                "text": "继续推进当前场景，追踪角色信念变化",
                "rationale": "系统追踪中",
                "source": "基线规则",
            }
        )

    return {
        "suggestions": all_suggestions[:7],
        "llm_available": llm.available(),
        "llm_count": len(llm_suggestions),
        "rule_count": len(rule_suggestions),
        "tension_count": len(constraints.get("tension_points", [])),
        "character_count": len(project.tom.get_all_characters()),
        "transportation_trend": trend,
    }


def _build_rule_suggestions(constraints: dict, trend: str) -> list[dict]:
    """生成规则基线建议——LLM不可用时的降级输出"""
    suggestions: list[dict] = []

    for tp in constraints.get("tension_points", [])[:2]:
        desc = tp.get("description", "")
        suggestion_text = tp.get("suggestion", "")
        text = f"「{desc[:30]}」— {suggestion_text[:30]}" if suggestion_text else desc[:40]
        suggestions.append(
            {
                "type": "tension",
                "text": text[:40],
                "rationale": f"强度{tp.get('intensity', 0):.1f}",
                "source": "ToM张力检测",
            }
        )

    suggestions.extend(
        {
            "type": "character",
            "text": f"{tendency['character']}倾向：{tendency['action'][:25]}"[:40],
            "rationale": f"强度{tendency['strength']:.1f}",
            "source": "ToM行动推断",
        }
        for tendency in constraints.get("character_tendencies", [])[:2]
    )

    suggestions.extend(
        {
            "type": "pattern",
            "text": f"启用「{pattern}」叙事模式"[:40],
            "rationale": "近期未使用",
            "source": "冷却矩阵",
        }
        for pattern in constraints.get("recommended_patterns", [])[:2]
    )

    if "↓" in trend:
        suggestions.append(
            {
                "type": "reader",
                "text": "读者沉浸度下降，建议引入新冲突或转折",
                "rationale": "传输度走低",
                "source": "读者模型",
            }
        )
    elif "↑" in trend:
        suggestions.append(
            {
                "type": "reader",
                "text": "读者沉浸度上升，保持当前节奏",
                "rationale": "传输度走高",
                "source": "读者模型",
            }
        )

    return suggestions


# ─── #13 方法论来源标注 ───

# 建议来源 → 方法论节点ID 映射（29节点注册表中的关键子集）
_METHODLOGY_MAP = {
    "ToM张力检测": ("M-belief", "心智理论张力模型"),
    "ToM行动推断": ("M-belief", "心智理论行动倾向"),
    "冷却矩阵": ("M-cooldown", "叙事模式冷却矩阵"),
    "读者模型": ("M-reader", "读者认知模拟"),
    "基线规则": (None, None),
}
_METHODLOGY_CACHE: dict = {}


def _get_methodology_registry():
    if "reg" not in _METHODLOGY_CACHE:
        try:
            from core.strategy_registry_builder import build_registry

            _METHODLOGY_CACHE["reg"] = build_registry()
        except Exception:
            _METHODLOGY_CACHE["reg"] = None
    return _METHODLOGY_CACHE["reg"]


def _annotate_methodology(
    project_id: str, suggestions: list[dict], orch: Orchestrator
) -> list[dict]:
    """为规则建议附加方法论出处（#13）

    source 已有引擎名；methodology 补全为 {name, source, description}
    """
    reg = _get_methodology_registry()
    nodes = {}
    if reg:
        for n in reg.all_nodes():
            nodes[n.name] = n
            # 别名匹配
            if "英雄之旅" in n.name or "Campbell" in (n.source or ""):
                nodes.setdefault("英雄之旅", n)

    # 张力/行动类建议 → 信念系统方法论节点
    belief_nodes = [
        n
        for n in (reg.all_nodes() if reg else [])
        if n.family and "belief" in str(n.family.value).lower()
    ]
    belief_node = belief_nodes[0] if belief_nodes else None

    for s in suggestions:
        src = s.get("source", "")
        methodology = None
        # 冷却矩阵推荐的叙事模式名 → 直接匹配注册表节点名
        if s.get("type") == "pattern":
            pattern = (
                (s.get("text") or "").replace("启用「", "").replace("」叙事模式", "").strip("」「 ")
            )
            node = nodes.get(pattern)
            if node:
                methodology = {
                    "name": node.name,
                    "source": node.source,
                    "description": (node.description or "")[:60],
                }
        if methodology is None and src in _METHODLOGY_MAP:
            node_id, fallback = _METHODLOGY_MAP[src]
            if node_id and belief_node and src.startswith("ToM"):
                methodology = {
                    "name": belief_node.name,
                    "source": belief_node.source,
                    "description": (belief_node.description or "")[:60],
                }
            elif fallback:
                methodology = {"name": fallback, "source": src, "description": ""}
        if methodology:
            s["methodology"] = methodology
    return suggestions


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.2.0",
        "engines": {
            "tom": "ready",
            "kg": "ready",
            "gates": "ready",
            "reader_model": "ready",
            "cooldown": "ready",
        },
        "persistence": "sqlite",
    }


# ─── Export ───

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "exports")


@app.get("/project/{project_id}/export/md")
async def export_markdown(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    safe_title = "".join(
        c for c in (project.title or "project") if c.isalnum() or c in " _-"
    ).strip()
    filename = f"{safe_title or project_id}.md"
    output_path = os.path.join(EXPORT_DIR, filename)
    export_project_markdown(project, output_path)
    return FileResponse(output_path, media_type="text/markdown", filename=filename)


@app.get("/project/{project_id}/export/epub")
async def export_epub(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        import ebooklib  # noqa: F401  # import 探活
    except ImportError as err:
        raise HTTPException(
            status_code=400,
            detail="ebooklib 未安装，请运行 pip install ebooklib 以启用 EPUB 导出",
        ) from err
    os.makedirs(EXPORT_DIR, exist_ok=True)
    safe_title = "".join(
        c for c in (project.title or "project") if c.isalnum() or c in " _-"
    ).strip()
    filename = f"{safe_title or project_id}.epub"
    output_path = os.path.join(EXPORT_DIR, filename)
    export_project_epub(project, output_path)
    return FileResponse(output_path, media_type="application/epub+zip", filename=filename)


@app.get("/project/{project_id}/chapter/{chapter_number}/export/md")
async def export_chapter(
    project_id: str, chapter_number: int, orch: Orchestrator = Depends(get_orchestrator)
):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapter = next(
        (c for c in project.chapters if c.chapter_number == chapter_number),
        None,
    )
    if not chapter:
        raise HTTPException(status_code=404, detail=f"章节 {chapter_number} 不存在")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    safe_title = "".join(
        c for c in (chapter.title or f"chapter_{chapter_number}") if c.isalnum() or c in " _-"
    ).strip()
    filename = f"ch{chapter_number:03d}_{safe_title}.md"
    output_path = os.path.join(EXPORT_DIR, filename)
    export_chapter_markdown(chapter, output_path)
    return FileResponse(output_path, media_type="text/markdown", filename=filename)


# ─── Project Management (新增) ───


@app.get("/projects")
async def list_projects(orch: Orchestrator = Depends(get_orchestrator)):
    return orch.list_projects()


@app.delete("/project/{project_id}")
async def delete_project(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    result = orch.delete_project(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"deleted": True}


@app.get("/project/{project_id}/characters")
async def get_characters(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return orch.get_characters(project_id)


@app.get("/project/{project_id}/foreshadowings")
async def get_foreshadowings(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return orch.get_open_foreshadowings(project_id)


# ─── 风格指纹报告（#11） ───


@app.get("/project/{project_id}/style-report")
async def style_report(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    """风格指纹：雷达图 + 感官分布 + 对话占比（基于已提交章节）"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = orch.store.get_chapters(project_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="尚无已提交章节——先提交至少一章再生成风格报告")

    from core.wenjian.fingerprint import extract_style_fingerprint, generate_style_dashboard

    full_text = "\n\n".join(ch.text for ch in chapters)
    sf = extract_style_fingerprint(full_text, novel_name=project.title or "未命名", author="")
    dash = generate_style_dashboard(sf)

    # 持久化快照
    radar = {i["name"]: i["value"] for i in dash.get("radar", {}).get("indicators", [])}
    sensory = dash.get("sensory_radar", {})
    pie = dash.get("dialogue_pie", {})
    orch.store.add_style_fingerprint_full(
        project_id=project_id,
        tone_vector={},
        pace_vector=dash.get("sentence_rhythm_histogram", {}).get("bins", []),
        dialogue_ratio=pie.get("dialogue", 0.0),
        sensory_channel_bias=sensory,
        pov_preference="",
        vocabulary_richness=radar.get("词汇多样性", 0.0) / 100.0,
        syntactic_complexity=radar.get("句长节奏", 0.0) / 100.0,
        conflict_distribution={},
    )
    return {
        "title": project.title,
        "chapter_count": len(chapters),
        "total_chars": len(full_text),
        "dashboard": dash,
    }


# ─── LLM 章节生成（#04） ───


class GenerateChapterRequest(BaseModel):
    prompt: str
    word_target: int = 300


@app.post("/project/{project_id}/generate-chapter")
async def generate_chapter(
    project_id: str, req: GenerateChapterRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """从一句话灵感生成章节草稿（LLM）"""
    try:
        result = orch.generate_chapter(project_id, req.prompt, req.word_target)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not result["llm_used"]:
        raise HTTPException(
            status_code=503,
            detail="LLM 不可用——请设置 DEEPSEEK_API_KEY / OPENAI_API_KEY / ZHIPU_API_KEY 等环境变量",
        )
    return result


# ─── 蓝图 W1/W2：上下文工程 + 生成质量 + 大纲规划 ───


@app.get("/api/context")
async def api_context(
    project_id: str, query: str = "", orch: Orchestrator = Depends(get_orchestrator)
):
    """W1: 分层上下文视察器（NovelAI 分层 + Morpheus 三层记忆）"""
    if not orch.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    from core.context.assembler import ContextAssembler
    from core.context.engine import ContextConfig

    cfg = ContextConfig()
    ac = ContextAssembler(orch.store, cfg).assemble(project_id, query)
    return ac.to_dict()


class GenerateQualityRequest(BaseModel):
    project_id: str
    instruction: str
    word_target: int = 500


@app.post("/api/generate-with-quality")
async def api_generate_with_quality(
    req: GenerateQualityRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """W1: 多变体生成 + 质量循环（Sudowrite 3 变体 × AnySpark 反馈轮）"""
    if not orch.get_project(req.project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    from core.generation.pipeline import GenerationPipeline

    result = GenerationPipeline(orch.store).generate_with_quality(
        req.project_id,
        req.instruction,
        req.word_target,
    )
    if not result.llm_used:
        raise HTTPException(status_code=503, detail="LLM 不可用或生成失败")
    return {
        "text": result.text,
        "score": result.score,
        "rounds": result.rounds,
        "variants": result.variants,
        "style_prompt": result.style_prompt,
        "context_tokens": result.context_tokens,
    }


class OutlineRequest(BaseModel):
    premise: str
    template: str = "three_act"
    target_chapters: int = 12


@app.post("/api/generate-outline")
async def api_generate_outline(req: OutlineRequest):
    """W2: 递归大纲生成（WriteHERE + GOAT/MICE/Dramatica 标注 + LIFO 验证）"""
    from core.planning.generator import OutlineGenerator

    ol = OutlineGenerator().generate(req.premise, req.template, req.target_chapters)
    return {
        "template": ol.template,
        "acts": [
            {
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "chapters": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "description": c.description,
                        "story_value": c.story_value,
                        "story_charge": c.story_charge,
                        "primary_pov": c.primary_pov,
                        "mice_type": c.mice_type,
                        "climax_position": c.climax_position,
                        "methodology_source": c.methodology_source,
                        "word_target": c.word_target,
                    }
                    for c in a.children
                    if c.level == "chapter"
                ],
            }
            for a in ol.root.children
        ],
        "mice_violations": ol.validate_mice_lifo(),
        "outline_json": ol.to_json(),
    }


@app.get("/api/voice-profile/{project_id}")
async def api_voice_profile(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    """W1: 从项目已写文本推导 VoiceProfile"""
    if not orch.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    from core.style.voice_profile import VoiceProfileInterview

    text = "\n\n".join(ch.text for ch in orch.store.get_chapters(project_id))
    vp = VoiceProfileInterview().extract_from_text(text)
    return {"profile": vp.__dict__, "prompt": vp.to_prompt()}


# ─── 产品化计划 W2: 质量检测 / AI续写 ───


@app.post("/api/quality")
async def api_quality(req: TextSubmitRequest):
    """W2: 五大质量检测聚合（InkOS/Barthes/Storr/Maass/ShowDon'tTell）"""
    from core.quality import get_quality_inspector

    issues = get_quality_inspector().run_all(req.text)
    return {
        "total": len(issues),
        "issues": issues,
        "families": sorted({i["family"] for i in issues}),
    }


class AIContinueRequest(BaseModel):
    project_id: str
    text: str = ""
    word_target: int = 400


@app.post("/project/{project_id}/ai-continue")
async def api_ai_continue(
    project_id: str, req: AIContinueRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """W1: AI 续写——基于当前文本尾部 + 项目上下文，生成下一段"""
    if not orch.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    from core.generation.pipeline import GenerationPipeline

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    # 续写指令：延续最近文本的语义
    tail = text[-400:]
    instruction = f"紧接着以下内容继续写（保持语气与视角连续）：\n{tail}"
    result = GenerationPipeline(orch.store).generate_with_quality(
        project_id,
        instruction,
        req.word_target,
    )
    if not result.llm_used:
        raise HTTPException(status_code=503, detail="LLM 不可用或生成失败")
    return {
        "text": result.text,
        "score": result.score,
        "variants": result.variants,
        "context_tokens": result.context_tokens,
    }


# ─── 碎片发散（#16） ───


class DivergeRequest(BaseModel):
    fragments: list[str]
    count: int = 5


@app.post("/diverge")
async def diverge(req: DivergeRequest):
    """#16: 碎片画面 → 世界线预览（无需项目，灵感期可用）"""
    try:
        return Orchestrator(store=get_store()).diverge_fragments(req.fragments, req.count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ─── 插件系统（#23） ───


@app.get("/plugins")
async def plugins_list():
    """#23: 已加载插件列表 + 加载错误"""
    from core.plugins import list_plugins, load_errors, load_plugins

    load_plugins()  # 热重载（幂等重扫）
    return {"plugins": list_plugins(), "errors": load_errors()}


@app.post("/plugins/test-gate")
async def plugins_test_gate(req: TextSubmitRequest):
    """#23: 用给定文本试运行所有 gate 插件"""
    from core.plugins import load_plugins, run_gate_plugins

    load_plugins()
    results = run_gate_plugins(req.text)
    return {"plugin_gate_results": results}


# ─── 风格市场（#21） ───


class PublishProfileRequest(BaseModel):
    project_id: str
    name: str
    description: str = ""
    genre_tags: list = []


@app.get("/style-profiles")
async def style_profiles_list(
    sort: str = "downloads", orch: Orchestrator = Depends(get_orchestrator)
):
    """#21: 浏览风格市场"""
    profiles = orch.store.get_style_profiles(sort_by=sort)
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "genre_tags": p.genre_tags,
            "download_count": p.download_count,
            "rating": p.rating,
        }
        for p in profiles
    ]


@app.post("/style-profiles")
async def publish_profile(
    req: PublishProfileRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """#21: 发布当前项目风格指纹为共享档案"""
    project = orch.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    fingerprint = orch.store.get_latest_style_fingerprint(req.project_id)
    if not fingerprint:
        raise HTTPException(status_code=400, detail="项目尚无风格指纹——先提交章节并生成风格报告")
    import json as _json

    fp_data = {
        "tone_vector": _json.loads(fingerprint.tone_vector_json or "{}"),
        "pace_vector": _json.loads(fingerprint.pace_vector_json or "{}"),
        "dialogue_ratio": fingerprint.dialogue_ratio,
        "sensory_channel_bias": _json.loads(
            getattr(fingerprint, "sensory_channel_bias_json", "{}") or "{}"
        ),
        "pov_preference": getattr(fingerprint, "pov_preference", ""),
    }
    profile = orch.store.create_style_profile(
        name=req.name.strip()[:60],
        author_id=req.project_id,
        fingerprint_json=fp_data,
        genre_tags=req.genre_tags or [],
        description=req.description[:300],
    )
    return {"id": profile.id, "name": profile.name, "published": True}


@app.post("/project/{project_id}/apply-style/{profile_id}")
async def apply_style_profile(
    project_id: str, profile_id: int, orch: Orchestrator = Depends(get_orchestrator)
):
    """#21: 应用市场风格到项目（30% 向目标档案混合）"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    profile = orch.store.get_style_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="风格档案不存在")

    target = profile.fingerprint_json or {}
    current_fp = orch.store.get_latest_style_fingerprint(project_id)
    import json as _json

    def blend(cur: dict, tgt: dict, weight: float = 0.3) -> dict:
        keys = set(cur) | set(tgt)
        out = {}
        for k in keys:
            c, t = cur.get(k), tgt.get(k)
            if isinstance(c, (int, float)) and isinstance(t, (int, float)):
                out[k] = round(c * (1 - weight) + t * weight, 4)
            elif isinstance(c, dict) and isinstance(t, dict):
                out[k] = {
                    ik: blend({"v": c[ik]}, {"v": t[ik]}, weight)["v"]
                    if isinstance(c.get(ik), (int, float)) and isinstance(t.get(ik), (int, float))
                    else (t.get(ik) if ik in t else c.get(ik))
                    for ik in set(c) | set(t)
                }
            else:
                out[k] = t if t is not None else c
        return out

    if current_fp:
        cur = {
            "tone_vector": _json.loads(current_fp.tone_vector_json or "{}"),
            "pace_vector": _json.loads(current_fp.pace_vector_json or "{}"),
            "dialogue_ratio": current_fp.dialogue_ratio,
        }
        blended = blend(cur, target, 0.3)
    else:
        blended = target

    orch.store.add_style_fingerprint_full(
        project_id=project_id,
        tone_vector=blended.get("tone_vector", {}),
        pace_vector=blended.get("pace_vector", {}),
        dialogue_ratio=blended.get("dialogue_ratio", 0.0),
        sensory_channel_bias=blended.get("sensory_channel_bias", {}),
        pov_preference=blended.get("pov_preference", ""),
    )
    orch.store.increment_profile_download(profile_id)
    orch._invalidate_cache(project_id)
    return {"applied": True, "profile": profile.name, "blend": 0.3}


# ─── 审计报告（产品化 W1: /audit） ───


@app.post("/project/{project_id}/audit")
async def api_audit(
    project_id: str, req: TextSubmitRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """W1: 章节审计——166门禁 + 跨章 + 五大质量检测"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    context = EntityExtractor.to_gate_context(req.text)
    gate_results = project.gates.pre_generation_check(
        req.text,
        context={
            "facts": context["facts"],
            "char_actions": context["char_actions"],
            "identity_changes": context["identity_changes"],
            "events": context["events"],
            "movements": context["movements"],
        },
    )
    has_block = any(r.level == GateLevel.BLOCK for r in gate_results)
    report = orch.submit_chapter(project_id, req.text) if not has_block else None

    from core.quality import get_quality_inspector

    quality = get_quality_inspector().run_all(req.text)

    return {
        "overall_score": report.overall_score
        if report
        else max(0, 100 - sum(20 if r.level == GateLevel.BLOCK else 10 for r in gate_results)),
        "gate_results": [r.to_dict() for r in gate_results],
        "audit_results": [r.to_dict() for r in (report.results if report else [])],
        "quality": quality,
        "quality_total": len(quality),
    }


# ─── 世界构建 Wiki（#18） ───


class WorldElementRequest(BaseModel):
    name: str
    element_type: str  # character / location / item / event
    description: str = ""
    properties: dict = {}


@app.get("/project/{project_id}/wiki")
async def wiki_list(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    """#18: 世界元素总览（按类型分组）"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    elements = orch.store.get_world_elements(project_id)
    groups: dict[str, list] = {"location": [], "item": [], "event": [], "other": []}
    for e in elements:
        import json as _json

        props = {}
        with contextlib.suppress(Exception):
            props = _json.loads(e.properties_json or "{}")
        entry = {
            "id": e.id,
            "name": e.name,
            "type": e.type,
            "description": e.description,
            **({"mentions": props["mentions"]} if props.get("mentions") else {}),
        }
        groups.get(e.type, groups["other"]).append(entry)
    return {
        "project_id": project_id,
        "counts": {k: len(v) for k, v in groups.items()},
        "groups": groups,
    }


@app.post("/project/{project_id}/wiki")
async def wiki_add(
    project_id: str, req: WorldElementRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """#18: 手动添加世界元素"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    el = orch.store.add_world_element(
        project_id=project_id,
        name=req.name.strip()[:60],
        element_type=req.element_type,
        description=req.description[:500],
        properties=req.properties or {},
    )
    orch._invalidate_cache(project_id)
    return {"id": el.id, "name": el.name, "type": el.type}


@app.delete("/project/{project_id}/wiki/{element_id}")
async def wiki_delete(
    project_id: str, element_id: str, orch: Orchestrator = Depends(get_orchestrator)
):
    """#18: 删除世界元素"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    from sqlmodel import Session

    from core.persistence.models import WorldElement

    with Session(orch.store.engine) as session:
        el = session.get(WorldElement, element_id)
        if not el or el.project_id != project_id:
            raise HTTPException(status_code=404, detail="世界元素不存在")
        session.delete(el)
        session.commit()
    orch._invalidate_cache(project_id)
    return {"deleted": True}


@app.post("/project/{project_id}/wiki/harvest")
async def wiki_harvest(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    """#18: 从已提交章节自动收获世界元素（实体提取→Wiki 建议）"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    from core.entity_extractor import EntityExtractor

    chapters = orch.store.get_chapters(project_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="尚无已提交章节")

    existing = {e.name for e in orch.store.get_world_elements(project_id)}
    harvested: list[dict] = []
    for ch in chapters:
        result = EntityExtractor.extract(ch.text)
        for loc in result.locations:
            if loc not in existing and len(loc) >= 2:
                existing.add(loc)
                el = orch.store.add_world_element(
                    project_id,
                    loc,
                    "location",
                    description=f"第{ch.number}章出现",
                    properties={"mentions": 1, "first_chapter": ch.number},
                )
                harvested.append({"id": el.id, "name": loc, "type": "location"})
        for item_name in result.items:
            if item_name not in existing and len(item_name) >= 2:
                existing.add(item_name)
                el = orch.store.add_world_element(
                    project_id,
                    item_name,
                    "item",
                    description=f"第{ch.number}章出现",
                    properties={"mentions": 1, "first_chapter": ch.number},
                )
                harvested.append({"id": el.id, "name": item_name, "type": "item"})
    orch._invalidate_cache(project_id)
    return {"harvested": harvested, "total_new": len(harvested)}


# ─── 假设推演（#15） ───


class SimulateRequest(BaseModel):
    hypothesis: str
    belief_changes: list = []  # [{character, proposition, value}]
    branch_count: int = 3


@app.post("/project/{project_id}/simulate")
async def simulate(
    project_id: str, req: SimulateRequest, orch: Orchestrator = Depends(get_orchestrator)
):
    """#15: "如果…会怎样"——克隆状态推演，不落盘"""
    try:
        result = orch.simulate_hypothesis(
            project_id, req.hypothesis, req.belief_changes, req.branch_count
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        return result


# ─── 章节管理 CRUD（#08） ───


@app.get("/project/{project_id}/chapters")
async def list_chapters(project_id: str, orch: Orchestrator = Depends(get_orchestrator)):
    """章节列表：章次 | 标题 | 字数 | 评分"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = orch.store.get_chapters(project_id)
    out = []
    for ch in chapters:
        score = 100.0
        try:
            import json as _json

            report = _json.loads(ch.audit_report_json or "{}")
            score = report.get("overall_score", 100.0)
        except Exception:
            pass
        out.append(
            {
                "number": ch.number,
                "title": ch.title,
                "word_count": ch.word_count,
                "score": score,
                "created_at": ch.created_at.isoformat() if ch.created_at else None,
            }
        )
    return out


@app.get("/project/{project_id}/chapters/{number}")
async def get_chapter_text(
    project_id: str, number: int, orch: Orchestrator = Depends(get_orchestrator)
):
    """单章正文 + 审计报告"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = orch.store.get_chapters(project_id)
    ch = next((c for c in chapters if c.number == number), None)
    if not ch:
        raise HTTPException(status_code=404, detail=f"章节 {number} 不存在")
    import json as _json

    try:
        report = _json.loads(ch.audit_report_json or "{}")
    except Exception:
        report = {}
    return {
        "number": ch.number,
        "title": ch.title,
        "text": ch.text,
        "word_count": ch.word_count,
        "audit_report": report,
    }


@app.delete("/project/{project_id}/chapters/{number}")
async def delete_chapter(
    project_id: str, number: int, orch: Orchestrator = Depends(get_orchestrator)
):
    """删除章节（物理删除，后续章次保持不变）"""
    project = orch.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = orch.store.get_chapters(project_id)
    ch = next((c for c in chapters if c.number == number), None)
    if not ch:
        raise HTTPException(status_code=404, detail=f"章节 {number} 不存在")
    orch.store.delete_chapter(ch.id)
    orch._invalidate_cache(project_id)
    return {"deleted": True, "number": number}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
