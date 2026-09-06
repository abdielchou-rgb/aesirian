"""P1-6 (2026-09-07): 退役旧 llm_engine / mcp_server——shim import 即告警。

背景（深度审计 S2.2.1）：旧 `core/llm_engine.py`（requests 直连多供应商）与
`mcp_server.py`（stdio-only JSON-RPC）已自注 DEPRECATED，但生产代码仍
`from core.llm_engine import get_llm_engine`（7 处），存在"两套生成路径"与
"双 MCP 入口"。

修复：
- 生产调用方（generation/planning/style/orchestrator/bridge/api_server）已迁移到
  `core.pydantic_ai_engine.get_llm_engine()`（LLMEngineCompat，Pydantic AI 门面）。
- `core.llm_engine.get_llm_engine()` 现委托到 Compat，不再实例化旧 LLMEngine
  （消除第二套生成路径）；模块 import 即 DeprecationWarning。
- `LLMSuggestion` 提升为 pydantic_ai_engine 的统一类型（旧模块不再作为类型来源）。
- `mcp_server.py` import 即 DeprecationWarning（生产走 mcp_server_fast.py）。

本测试固化：import 旧模块触发告警；生产模块不再 import 旧入口；
Compat 与旧门面返回同一单例（同构）。

Run: python -X utf8 -m pytest tests/test_deprecated_retirement.py -v
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))


def test_import_llm_engine_emits_deprecation():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import importlib

        import core.llm_engine as m  # noqa: F401

        importlib.reload(m)
        assert any(issubclass(x.category, DeprecationWarning) for x in w), (
            "import core.llm_engine 应触发 DeprecationWarning"
        )


def test_import_mcp_server_emits_deprecation():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import importlib

        import mcp_server  # noqa: F401

        importlib.reload(mcp_server)
        assert any(issubclass(x.category, DeprecationWarning) for x in w), (
            "import mcp_server 应触发 DeprecationWarning"
        )


def test_production_modules_import_from_pydantic_ai_engine():
    """生产模块不再 from core.llm_engine import get_llm_engine。"""
    ROOT = Path(__file__).resolve().parents[1]
    offenders = []
    for rel in [
        "core/generation/pipeline.py",
        "core/planning/generator.py",
        "core/style/voice_profile.py",
        "core/orchestrator.py",
        "bridge/api_server.py",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "from core.llm_engine import" in text:
            offenders.append(rel)
    assert offenders == [], f"生产模块仍 import 旧 llm_engine: {offenders}"
    # 统一入口确认存在
    from core.pydantic_ai_engine import LLMSuggestion, get_llm_engine  # noqa: F401


def test_legacy_get_llm_engine_delegates_to_compat():
    """旧门面委托到 Compat——二者返回同一单例，不再实例化旧 LLMEngine。"""
    from core.llm_engine import get_llm_engine as old_get
    from core.pydantic_ai_engine import get_llm_engine as new_get

    # 用反射绕过 DeprecationWarning 噪音
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        new_eng = new_get()
        old_eng = old_get()
    assert new_eng is old_eng, "旧/新 get_llm_engine 应返回同一 Compat 单例（同构委托）"


def test_llmsuggestion_is_unified_type():
    """LLMSuggestion 统一由 pydantic_ai_engine 提供。"""
    from core.pydantic_ai_engine import LLMSuggestion

    s = LLMSuggestion(type="tension", text="他推开门", rationale="制造悬念", source="mckee")
    assert s.to_dict()["type"] == "tension"
    assert s.to_dict()["text"] == "他推开门"
