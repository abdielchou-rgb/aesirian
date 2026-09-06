"""
Pydantic AI LLM Engine — Typed, Structured, Streaming, Tool-Enabled

Replaces raw requests-based LLM engine with Pydantic AI for:
- Type-safe structured output (Pydantic models)
- Function calling / tool use
- Streaming responses
- Multi-provider gateway (OpenAI, Anthropic, Google, etc.)
- Dependency injection
- Automatic retries with exponential backoff
- Cost tracking via Logfire
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel as GeminiModel
from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from core.observability import trace_chapter_generation, track_llm_call

logger = logging.getLogger(__name__)


# ─── Output Models ───


class ChapterDraft(BaseModel):
    """结构化章节输出"""

    title: str = Field(description="章节标题（≤15字）", max_length=60)
    text: str = Field(description="章节正文（200-500字）", min_length=100, max_length=1000)
    hooks: list[str] = Field(default_factory=list, description="结尾留钩（1-3个）")
    tension_points_addressed: list[str] = Field(
        default_factory=list, description="本章处理的张力点"
    )
    characters_appeared: list[str] = Field(default_factory=list, description="出场角色")


class LLMSuggestion(BaseModel):
    """LLM 生成的续写建议（P1-6：自旧 core/llm_engine 提升为统一类型）。

    统一生成入口 core.pydantic_ai_engine 直接产出本类型；旧模块 core.llm_engine
    已退役（import 即 DeprecationWarning），不再作为本类型的来源。
    """

    type: str = "llm"  # tension / character / reader / pattern / llm
    text: str = ""  # 续写开头（max 40字）
    rationale: str = ""  # 为什么（max 20字）
    source: str = ""  # 方法论来源

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "text": self.text[:40],
            "rationale": self.rationale[:20],
            "source": self.source[:30] if self.source else "LLM",
        }


class SceneConstraints(BaseModel):
    """场景约束输出"""

    tension_points: list[dict] = Field(default_factory=list)
    character_tendencies: list[dict] = Field(default_factory=list)
    reader_state: dict = Field(default_factory=dict)
    recommended_patterns: list[str] = Field(default_factory=list)
    cold_available_patterns: list[str] = Field(default_factory=list)
    narrative_guidance: str = Field(default="", description="一句话叙事指导")


class SimulationBranch(BaseModel):
    """假设推演分支"""

    title: str = Field(max_length=10)
    summary: str = Field(max_length=80)
    key_event: str = Field(max_length=40)


class SimulationResult(BaseModel):
    """假设推演完整结果"""

    hypothesis: str
    tensions: list[dict]
    branches: list[SimulationBranch]
    applied_beliefs: list[dict]
    llm_used: bool


class WorldlinePreview(BaseModel):
    """世界线预览"""

    id: str
    genre: str
    structure: str
    conflict_core: str = Field(max_length=25)
    beats: list[str] = Field(min_length=5, max_length=5)
    opening: str = Field(min_length=50, max_length=150)


class DivergenceResult(BaseModel):
    """碎片发散结果"""

    worldlines: list[WorldlinePreview]
    llm_used: bool
    fragment_count: int


class GenerationSuggestion(BaseModel):
    """续写建议"""

    type: str = Field(pattern="^(tension|character|reader|pattern|llm)$")
    text: str = Field(max_length=40)
    rationale: str = Field(max_length=20)
    source: str = Field(max_length=30)


class SuggestionsResult(BaseModel):
    """续写建议列表"""

    suggestions: list[GenerationSuggestion] = Field(min_length=3, max_length=5)


# ─── Tool Definitions ───


class NarrativeTools:
    """叙事工具集 - 供 Agent 调用"""

    def __init__(self, project_context: dict = None):
        self.project_context = project_context or {}

    @staticmethod
    def get_character_beliefs(ctx: RunContext[dict], character: str) -> dict:
        """获取角色的当前信念状态"""
        project = ctx.deps.get("project")
        if not project:
            return {}
        tom = project.get("tom")
        if not tom:
            return {}
        char = tom.get_character(character)
        if not char:
            return {}
        return {
            prop: {
                "value": belief.value,
                "confidence": belief.confidence,
                "source": belief.source.value,
                "is_erroneous": belief.is_erroneous,
            }
            for prop, belief in char.world_beliefs.items()
        }

    @staticmethod
    def get_tension_points(ctx: RunContext[dict]) -> list[dict]:
        """获取当前项目的戏剧张力点"""
        project = ctx.deps.get("project")
        if not project:
            return []
        tom = project.get("tom")
        if not tom:
            return []
        tensions = tom.detect_tension()
        return [
            {
                "type": t.type.value,
                "description": t.description,
                "intensity": t.intensity,
                "involved": t.involved_characters,
                "suggestion": t.suggestion,
            }
            for t in tensions
        ]

    @staticmethod
    def query_knowledge_graph(ctx: RunContext[dict], entity: str) -> dict:
        """查询知识图谱中的实体信息"""
        project = ctx.deps.get("project")
        if not project:
            return {}
        kg = project.get("kg")
        if not kg:
            return {}
        node = kg.get_node_by_name(entity)
        if not node:
            return {}
        return {
            "name": node.name,
            "type": node.type.value,
            "properties": node.properties,
            "created_at": node.created_at_chapter,
        }

    @staticmethod
    def get_cooldown_recommendations(ctx: RunContext[dict], count: int = 3) -> list[str]:
        """获取冷却矩阵推荐的叙事模式"""
        project = ctx.deps.get("project")
        if not project:
            return []
        cooldown = project.get("cooldown")
        if not cooldown:
            return []
        return cooldown.get_recommendations(count)


# ─── Model Factory ───


def create_model(provider: str = None) -> Model:
    """根据配置创建模型实例，支持多供应商自动回退"""
    # 优先级：环境变量指定 > 自动检测可用密钥
    provider = provider or os.environ.get("LLM_PROVIDER", "auto")

    models_config = [
        # OpenAI 兼容
        ("openai", "OPENAI_API_KEY", "gpt-4o-mini", "https://api.openai.com/v1"),
        ("openai", "DEEPSEEK_API_KEY", "deepseek-chat", "https://api.deepseek.com/v1"),
        ("openai", "ZHIPU_API_KEY", "glm-4-flash", "https://open.bigmodel.cn/api/paas/v4"),
        # Anthropic
        ("anthropic", "ANTHROPIC_API_KEY", "claude-3-haiku-20240307"),
        # Google
        ("google", "GOOGLE_API_KEY", "gemini-1.5-flash"),
        # Ollama 本地
        ("openai", "OLLAMA_HOST", "qwen2.5:7b", "{OLLAMA_HOST}/v1"),
    ]

    for prov, key_env, model_name, *base_url in models_config:
        api_key = os.environ.get(key_env)
        if not api_key:
            continue

        try:
            if prov == "openai":
                base = base_url[0] if base_url else "https://api.openai.com/v1"
                base = base.replace(
                    "{OLLAMA_HOST}", os.environ.get("OLLAMA_HOST", "http://localhost:11434")
                )
                return OpenAIModel(
                    model_name,
                    provider=OpenAIProvider(api_key=api_key, base_url=base),
                )
            if prov == "anthropic":
                return AnthropicModel(
                    model_name,
                    provider=AnthropicProvider(api_key=api_key),
                )
            if prov == "google":
                return GeminiModel(
                    model_name,
                    provider=GoogleProvider(api_key=api_key),
                )
        except Exception as e:
            logger.warning(f"Failed to create {prov} model {model_name}: {e}")
            continue

    raise RuntimeError(
        "No LLM provider configured. Set OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY"
    )


# ─── Agent Factory ───


def create_chapter_agent(model: Model = None, deps_type: type = dict) -> Agent:
    """创建章节生成 Agent"""
    model = model or create_model()
    return Agent(
        model,
        deps_type=deps_type,
        output_type=ChapterDraft,  # type: ignore[arg-type]  # pydantic-ai 泛型只列 str 输出，结构体输出为已知 stub 局限
        system_prompt=(
            "你是一位中文网文作家。根据用户给定的灵感和上下文，写出一段完整的小说正文。\n"
            "要求：\n"
            "1. 直接输出正文，不要任何标题、解释或元信息\n"
            "2. 有具体的场景、动作、对话或心理描写，不要空洞概述\n"
            "3. 结尾留一个钩子，让读者想继续读下去\n"
            "4. 字数约 300 字（200-500字）\n"
            "5. 必须包含 title、text、hooks、tension_points_addressed、characters_appeared 字段"
        ),
        retries=3,
    )


def create_scene_constraints_agent(model: Model = None, deps_type: type = dict) -> Agent:
    """创建场景约束生成 Agent"""
    model = model or create_model()
    return Agent(
        model,
        deps_type=deps_type,
        output_type=SceneConstraints,  # type: ignore[arg-type]  # pydantic-ai 泛型只列 str 输出，结构体输出为已知 stub 局限
        system_prompt=(
            "你是一个叙事设计师。根据项目状态输出结构化的场景写作约束。\n"
            "输出必须包含：tension_points、character_tendencies、reader_state、recommended_patterns、cold_available_patterns、narrative_guidance"
        ),
        retries=2,
    )


def create_simulation_agent(model: Model = None, deps_type: type = dict) -> Agent:
    """创建假设推演 Agent"""
    model = model or create_model()
    return Agent(
        model,
        deps_type=deps_type,
        output_type=SimulationResult,  # type: ignore[arg-type]  # pydantic-ai 泛型只列 str 输出，结构体输出为已知 stub 局限
        system_prompt=(
            "你是一个剧情推演师。基于假设和信念变更，推演出新的张力点和情节分支。\n"
            "输出必须包含：hypothesis、tensions、branches、applied_beliefs、llm_used"
        ),
        retries=2,
    )


def create_divergence_agent(model: Model = None, deps_type: type = dict) -> Agent:
    """创建碎片发散 Agent"""
    model = model or create_model()
    return Agent(
        model,
        deps_type=deps_type,
        output_type=DivergenceResult,  # type: ignore[arg-type]  # pydantic-ai 泛型只列 str 输出，结构体输出为已知 stub 局限
        system_prompt=(
            "你是一个世界观构建师。基于碎片画面，构思完整的小说世界线。\n"
            "输出必须包含：worldlines（每个包含 id、genre、structure、conflict_core、beats[5]、opening）、llm_used、fragment_count"
        ),
        retries=2,
    )


def create_suggestions_agent(model: Model = None, deps_type: type = dict) -> Agent:
    """创建续写建议 Agent"""
    model = model or create_model()
    return Agent(
        model,
        deps_type=deps_type,
        output_type=SuggestionsResult,  # type: ignore[arg-type]  # pydantic-ai 泛型只列 str 输出，结构体输出为已知 stub 局限
        system_prompt=(
            "你是一个续写建议生成器。根据上下文生成 3-5 条结构化续写建议。\n"
            "每条建议包含：type（tension/character/reader/pattern/llm）、text（≤40字）、rationale（≤20字）、source（≤30字）"
        ),
        retries=2,
    )


# ─── High-Level Interface ───


class PydanticAILEngine:
    """
    Pydantic AI 引擎统一接口

    替代原有 LLMEngine，提供：
    - 类型安全的结构化输出
    - 工具调用支持
    - 流式响应
    - 多供应商自动回退
    - 成本追踪
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._model = None
        self._chapter_agent = None
        self._constraints_agent = None
        self._simulation_agent = None
        self._divergence_agent = None
        self._suggestions_agent = None

    def _ensure_initialized(self):
        """懒加载初始化"""
        if self._chapter_agent is not None:
            return

        try:
            self._model = create_model()
            self._chapter_agent = create_chapter_agent(self._model)
            self._constraints_agent = create_scene_constraints_agent(self._model)
            self._simulation_agent = create_simulation_agent(self._model)
            self._divergence_agent = create_divergence_agent(self._model)
            self._suggestions_agent = create_suggestions_agent(self._model)
            logger.info(f"PydanticAI Engine initialized with model: {self._model}")
        except Exception:
            logger.exception("PydanticAI Engine initialization failed")
            self._model = None

    def available(self) -> bool:
        """检查是否有可用的 LLM"""
        self._ensure_initialized()
        return self._model is not None

    @property
    def model_name(self) -> str:
        return str(self._model) if self._model else "unavailable"

    # ── Chapter Generation ──

    def generate_chapter(self, premise: str, context: dict = None, word_target: int = 300) -> str:
        """生成章节（同步，返回文本）"""
        self._ensure_initialized()
        if not self.available():
            return ""

        context = context or {}
        deps = {
            "project": context,
            "premise": premise,
            "word_target": word_target,
        }

        try:
            with trace_chapter_generation(
                context.get("project_id", "unknown"), context.get("current_chapter", 1), premise
            ):
                result = self._chapter_agent.run_sync(
                    f"前提：{premise}\n目标字数：{word_target}\n上下文：{context}",
                    deps=deps,
                )
                track_llm_call(
                    model=self.model_name,
                    input_tokens=result.usage().request_tokens if result.usage() else 0,
                    output_tokens=result.usage().response_tokens if result.usage() else 0,
                    project_id=context.get("project_id"),
                )
                return result.output.text
        except Exception:
            logger.exception("Chapter generation failed")
            return ""

    async def generate_chapter_stream(
        self, premise: str, context: dict = None, word_target: int = 300
    ) -> AsyncIterator[str]:
        """流式生成章节"""
        self._ensure_initialized()
        if not self.available():
            return

        context = context or {}
        deps = {"project": context, "premise": premise, "word_target": word_target}

        async with self._chapter_agent.run_stream(
            f"前提：{premise}\n目标字数：{word_target}\n上下文：{context}",
            deps=deps,
        ) as result:
            async for chunk in result.stream_text(delta=True):
                yield chunk

    # ── Scene Constraints ──

    def generate_scene_constraints(self, context: dict) -> dict:
        """生成场景约束（结构化输出）"""
        self._ensure_initialized()
        if not self.available():
            return {}

        deps = {"project": context}
        try:
            result = self._constraints_agent.run_sync(
                f"项目状态：{context}",
                deps=deps,
            )
            return result.output.model_dump()
        except Exception:
            logger.exception("Scene constraints generation failed")
            return {}

    # ── Simulation ──

    def simulate_hypothesis(
        self,
        hypothesis: str,
        belief_changes: list[dict],
        context: dict = None,
        branch_count: int = 3,
    ) -> dict:
        """假设推演"""
        self._ensure_initialized()
        if not self.available():
            return {
                "hypothesis": hypothesis,
                "tensions": [],
                "branches": [],
                "applied_beliefs": [],
                "llm_used": False,
            }

        deps = {"project": context, "hypothesis": hypothesis, "belief_changes": belief_changes}
        try:
            result = self._simulation_agent.run_sync(
                f"假设：{hypothesis}\n信念变更：{belief_changes}\n分支数：{branch_count}",
                deps=deps,
            )
            return result.output.model_dump()
        except Exception:
            logger.exception("Simulation failed")
            return {
                "hypothesis": hypothesis,
                "tensions": [],
                "branches": [],
                "applied_beliefs": [],
                "llm_used": False,
            }

    # ── Divergence ──

    def diverge_fragments(self, fragments: list[str], count: int = 5) -> dict:
        """碎片发散"""
        self._ensure_initialized()
        if not self.available():
            return {"worldlines": [], "llm_used": False, "fragment_count": len(fragments)}

        deps = {"fragments": fragments, "count": count}
        try:
            result = self._divergence_agent.run_sync(
                f"碎片：{fragments}\n生成数量：{count}",
                deps=deps,
            )
            return result.output.model_dump()
        except Exception:
            logger.exception("Divergence failed")
            return {"worldlines": [], "llm_used": False, "fragment_count": len(fragments)}

    # ── Suggestions ──

    def generate_suggestions(self, context: dict) -> list[dict]:
        """生成续写建议"""
        self._ensure_initialized()
        if not self.available():
            return []

        deps = {"project": context}
        try:
            result = self._suggestions_agent.run_sync(
                f"上下文：{context}",
                deps=deps,
            )
            return [s.model_dump() for s in result.output.suggestions]
        except Exception:
            logger.exception("Suggestions generation failed")
            return []

    # ── Variant Generation (Sudowrite-style) ──

    def generate_variant(
        self, context_text: str, instruction: str, word_target: int = 500, temperature: float = 0.7
    ) -> str:
        """多变体生成"""
        self._ensure_initialized()
        if not self.available():
            return ""

        # 创建临时 agent 用于变体生成
        variant_agent = Agent(
            self._model,
            output_type=str,
            system_prompt=(
                "你是一位中文小说家。基于给定的故事上下文，写出接下来的正文。\n"
                "要求：\n"
                "1. 直接输出正文，不要标题、解释、元信息\n"
                "2. 与上下文的角色信念、语气、节奏保持连续\n"
                "3. 有具体场景与感官细节，结尾留钩子\n"
                f"4. 字数约{word_target}字"
            ),
            model_settings={"temperature": temperature},
        )

        try:
            result = variant_agent.run_sync(f"{context_text}\n\n{instruction}")
        except Exception:
            logger.exception("Variant generation failed")
            return ""
        else:
            return result.output


# ─── Singleton Getter ───


def get_pydantic_ai_engine() -> PydanticAILEngine:
    """获取 PydanticAI 引擎单例"""
    return PydanticAILEngine()


# ─── Backward Compatibility Wrapper ───


class LLMEngineCompat:
    """
    兼容原有 LLMEngine 接口的包装器
    逐步迁移期间使用
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._engine = get_pydantic_ai_engine()

    def available(self) -> bool:
        return self._engine.available()

    def generate_suggestions(self, context: dict) -> list:
        """兼容旧接口：返回 LLMSuggestion 列表"""
        suggestions = self._engine.generate_suggestions(context)
        return [
            LLMSuggestion(
                type=s["type"],
                text=s["text"],
                rationale=s["rationale"],
                source=s["source"],
            )
            for s in suggestions
        ]

    def enhance_scene_constraints(self, rules: dict) -> str:
        constraints = self._engine.generate_scene_constraints(rules)
        return constraints.get("narrative_guidance", "")

    def generate_chapter(self, premise: str, context: dict = None, word_target: int = 300) -> str:
        return self._engine.generate_chapter(premise, context, word_target)

    def generate_variant(
        self, context_text: str, instruction: str, word_target: int = 500, temperature: float = None
    ) -> str:
        return self._engine.generate_variant(
            context_text, instruction, word_target, temperature or 0.7
        )


def get_llm_engine() -> LLMEngineCompat:
    """获取兼容层引擎单例（保持原有 API）"""
    return LLMEngineCompat()
