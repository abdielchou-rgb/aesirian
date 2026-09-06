"""
Æsirian ProjectStore — SQLite-backed CRUD for narrative projects
"""
from __future__ import annotations
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)
from typing import Optional
import json
import os
import uuid
from contextlib import contextmanager

from sqlmodel import SQLModel, create_engine, Session, select, delete
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy import event

from core.persistence.models import (
    Project, Chapter, CharacterRecord, WorldElement,
    Foreshadowing, StyleFingerprint, Character,
    AuditReport, GateResult, StyleProfile, PluginConfig,
)


class ProjectStore:
    """SQLite-backed storage for Æsirian narrative projects.

    All mutations are committed immediately. The store is the single source
    of truth; the Orchestrator rebuilds its runtime engines from it.

    NOTE on in-memory mode: when the sandbox cannot persist a file (writable
    probe fails), ProjectStore falls back to a shared process-wide StaticPool
    engine so that every ProjectStore() instance in the process sees the same
    data (required for API tests and file-less E2E). Production (file-backed)
    is unaffected: each instance opens the same aesirian.db.
    """

    _memory_engine = None  # process-wide shared in-memory engine

    def __init__(self, database_url: str = None, pool_size: int = 5, max_overflow: int = 10):
        if database_url is None:
            # 测试隔离注入点：pytest fixture 通过 AESIRIAN_DB_URL 指向临时库，
            # 防止测试污染主库 aesirian.db。
            database_url = os.environ.get("AESIRIAN_DB_URL")
        if database_url is None:
            # 检测是否在沙箱环境（文件系统不支持 SQLite）
            _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            _db_path = os.path.join(_project_root, "aesirian.db")
            # 尝试创建测试文件，如果失败则使用内存模式
            try:
                _test = os.path.join(_project_root, ".write_test")
                with open(_test, 'w') as f: f.write("ok")
                os.remove(_test)
                database_url = f"sqlite:///{_db_path}"
            except (OSError, PermissionError):
                database_url = "sqlite:///:memory:"  # 内存模式（沙箱回退）

        # Configure connection pool
        if database_url == "sqlite:///:memory:":
            if ProjectStore._memory_engine is None:
                ProjectStore._memory_engine = self._build_engine(
                    "sqlite:///:memory:", pool_size, max_overflow, memory=True)
            self.engine = ProjectStore._memory_engine
            self._database_url = database_url
            SQLModel.metadata.create_all(self.engine)
            return
        else:
            self.engine = ProjectStore._build_engine(
                database_url, pool_size, max_overflow, memory=False)

        # NOTE: File-backed schema is handled by Alembic migrations
        # (`make upgrade` / `alembic upgrade head`). In-memory fallback
        # (sandbox / ephemeral test env) must self-create tables, since
        # there is no persistent schema to migrate.
        if database_url == "sqlite:///:memory:":
            SQLModel.metadata.create_all(self.engine)
        self._database_url = database_url

    @staticmethod
    def _build_engine(database_url: str, pool_size: int, max_overflow: int, memory: bool = False):
        if memory:
            eng = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            return eng
        eng = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        # Enable WAL mode for better concurrency
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-32768")  # 32MB cache
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return eng

    @contextmanager
    def session(self):
        """Provide a transactional scope around a series of operations."""
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            with Session(self.engine) as session:
                session.exec(select(1))
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════
    # Project lifecycle
    # ═══════════════════════════════════════

    def create_project(self, title: str, genre: str, premise: str, project_id: str | None = None) -> Project:
        pid = project_id or uuid.uuid4().hex[:12]
        project = Project(
            id=pid,
            title=title,
            genre=genre,
            premise=premise,
        )
        with Session(self.engine) as session:
            session.add(project)
            session.commit()
            session.refresh(project)
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        with Session(self.engine) as session:
            return session.get(Project, project_id)

    def list_projects(self) -> list[Project]:
        with Session(self.engine) as session:
            statement = select(Project).order_by(Project.updated_at.desc())
            return list(session.exec(statement).all())

    def delete_project(self, project_id: str) -> bool:
        with Session(self.engine) as session:
            project = session.get(Project, project_id)
            if not project:
                return False
            session.delete(project)
            session.commit()
            return True

    def touch_project(self, project_id: str):
        """Update the project's updated_at timestamp."""
        with Session(self.engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.updated_at = now_utc()
                session.add(project)
                session.commit()

    # ═══════════════════════════════════════
    # Chapters
    # ═══════════════════════════════════════

    def add_chapter(self, project_id: str, number: int, text: str,
                    audit_report: dict | None = None) -> Chapter:
        word_count = len(text)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        title = first_line[:60] if first_line else f"第{number}章"

        chapter = Chapter(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            number=number,
            title=title,
            text=text,
            word_count=word_count,
            audit_report_json=json.dumps(audit_report or {}, ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(chapter)
            session.commit()
            session.refresh(chapter)
        self.touch_project(project_id)
        return chapter

    def get_chapters(self, project_id: str) -> list[Chapter]:
        with Session(self.engine) as session:
            statement = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .order_by(Chapter.number)
            )
            return list(session.exec(statement).all())

    def get_latest_chapter(self, project_id: str) -> Optional[Chapter]:
        with Session(self.engine) as session:
            statement = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .order_by(Chapter.number.desc())
            )
            return session.exec(statement).first()

    def get_chapter_by_number(self, project_id: str, number: int) -> Optional[Chapter]:
        with Session(self.engine) as session:
            statement = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .where(Chapter.number == number)
            )
            return session.exec(statement).first()

    def delete_chapter(self, chapter_id: str) -> bool:
        with Session(self.engine) as session:
            chapter = session.get(Chapter, chapter_id)
            if not chapter:
                return False
            session.delete(chapter)
            session.commit()
            return True

    def update_chapter(self, chapter_id: str, text: str,
                       audit_report: dict | None = None) -> Optional[Chapter]:
        """更新章节正文（重新审计后由 API 层传入新报告）"""
        word_count = len(text)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        title = first_line[:60] if first_line else "未命名章节"
        with Session(self.engine) as session:
            chapter = session.get(Chapter, chapter_id)
            if not chapter:
                return None
            chapter.text = text
            chapter.word_count = word_count
            chapter.title = title
            if audit_report is not None:
                chapter.audit_report_json = json.dumps(audit_report, ensure_ascii=False)
            session.add(chapter)
            session.commit()
            session.refresh(chapter)
        return chapter

    # ═══════════════════════════════════════
    # Characters
    # ═══════════════════════════════════════

    def add_character(self, project_id: str, name: str, role: str,
                      traits: dict | None = None,
                      beliefs: dict | None = None,
                      goals: list | None = None,
                      secrets: list | None = None) -> Character:
        character = Character(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            name=name,
            role=role,
            traits_json=json.dumps(traits or {}, ensure_ascii=False),
            beliefs_json=json.dumps(beliefs or {}, ensure_ascii=False),
            goals_json=json.dumps(goals or [], ensure_ascii=False),
            secrets_json=json.dumps(secrets or [], ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(character)
            session.commit()
            session.refresh(character)
        self.touch_project(project_id)
        return character

    def get_characters(self, project_id: str) -> list[Character]:
        with Session(self.engine) as session:
            statement = (
                select(Character)
                .where(Character.project_id == project_id)
                .order_by(Character.name)
            )
            return list(session.exec(statement).all())

    def get_character(self, character_id: str) -> Optional[Character]:
        with Session(self.engine) as session:
            return session.get(Character, character_id)

    def update_character_beliefs(self, character_id: str, beliefs: dict) -> Optional[Character]:
        with Session(self.engine) as session:
            character = session.get(Character, character_id)
            if not character:
                return None
            character.beliefs_json = json.dumps(beliefs, ensure_ascii=False)
            session.add(character)
            session.commit()
            session.refresh(character)
        return character

    def update_character_goals(self, character_id: str, goals: list) -> Optional[Character]:
        """回写角色 goals_json（M1-6：ToM 运行时 active_goals 持久化）。"""
        with Session(self.engine) as session:
            character = session.get(Character, character_id)
            if not character:
                return None
            character.goals_json = json.dumps(goals, ensure_ascii=False)
            session.add(character)
            session.commit()
            session.refresh(character)
        return character

    # ═══════════════════════════════════════
    # World elements
    # ═══════════════════════════════════════

    def add_world_element(self, project_id: str, name: str, element_type: str,
                          description: str = "",
                          properties: dict | None = None) -> WorldElement:
        element = WorldElement(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            name=name,
            type=element_type,
            description=description,
            properties_json=json.dumps(properties or {}, ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(element)
            session.commit()
            session.refresh(element)
        self.touch_project(project_id)
        return element

    def upsert_world_element(self, project_id: str, name: str, element_type: str,
                             description: str = "",
                             properties: dict | None = None) -> tuple[WorldElement, bool]:
        """按 (project_id, name) 幂等写入世界观元素：已存在则更新，否则插入。

        返回 (记录, 是否新建)。M1-6 用于将运行时 KG 非角色节点全量回写，
        避免每次 submit_chapter 都产生重复元素。
        """
        with Session(self.engine) as session:
            existing = session.exec(
                select(WorldElement).where(
                    WorldElement.project_id == project_id,
                    WorldElement.name == name,
                )
            ).first()
            if existing is not None:
                existing.type = element_type
                existing.description = description
                existing.properties_json = json.dumps(properties or {}, ensure_ascii=False)
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing, False
        # 未命中（select 会话已关闭）走独立写路径，保证事务简单清晰
        element = WorldElement(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            name=name,
            type=element_type,
            description=description,
            properties_json=json.dumps(properties or {}, ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(element)
            session.commit()
            session.refresh(element)
        self.touch_project(project_id)
        return element, True

    def get_world_elements(self, project_id: str) -> list[WorldElement]:
        with Session(self.engine) as session:
            statement = (
                select(WorldElement)
                .where(WorldElement.project_id == project_id)
                .order_by(WorldElement.name)
            )
            return list(session.exec(statement).all())

    # ═══════════════════════════════════════
    # Foreshadowing
    # ═══════════════════════════════════════

    def add_foreshadowing(self, project_id: str, chapter_id: str,
                          description: str) -> Foreshadowing:
        foreshadowing = Foreshadowing(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            chapter_id=chapter_id,
            description=description,
            status="open",
        )
        with Session(self.engine) as session:
            session.add(foreshadowing)
            session.commit()
            session.refresh(foreshadowing)
        self.touch_project(project_id)
        return foreshadowing

    def resolve_foreshadowing(self, foreshadowing_id: str,
                              resolved_chapter: str) -> Optional[Foreshadowing]:
        with Session(self.engine) as session:
            foreshadowing = session.get(Foreshadowing, foreshadowing_id)
            if not foreshadowing:
                return None
            foreshadowing.status = "resolved"
            foreshadowing.resolved_at = now_utc()
            session.add(foreshadowing)
            session.commit()
            session.refresh(foreshadowing)
        return foreshadowing

    def get_open_foreshadowings(self, project_id: str) -> list[Foreshadowing]:
        with Session(self.engine) as session:
            statement = (
                select(Foreshadowing)
                .where(
                    Foreshadowing.project_id == project_id,
                    Foreshadowing.status == "open",
                )
                .order_by(Foreshadowing.created_at)
            )
            return list(session.exec(statement).all())

    def get_all_foreshadowings(self, project_id: str) -> list[Foreshadowing]:
        with Session(self.engine) as session:
            statement = (
                select(Foreshadowing)
                .where(Foreshadowing.project_id == project_id)
                .order_by(Foreshadowing.created_at)
            )
            return list(session.exec(statement).all())

    # ═══════════════════════════════════════
    # Style fingerprints
    # ═══════════════════════════════════════

    def add_style_fingerprint(self, project_id: str,
                              tone_vector: dict | None = None,
                              pace_vector: dict | None = None,
                              dialogue_ratio: float = 0.0) -> StyleFingerprint:
        fingerprint = StyleFingerprint(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            tone_vector_json=json.dumps(tone_vector or {}, ensure_ascii=False),
            pace_vector_json=json.dumps(pace_vector or {}, ensure_ascii=False),
            dialogue_ratio=dialogue_ratio,
        )
        with Session(self.engine) as session:
            session.add(fingerprint)
            session.commit()
            session.refresh(fingerprint)
        self.touch_project(project_id)
        return fingerprint

    def get_latest_style_fingerprint(self, project_id: str) -> Optional[StyleFingerprint]:
        with Session(self.engine) as session:
            statement = (
                select(StyleFingerprint)
                .where(StyleFingerprint.project_id == project_id)
                .order_by(StyleFingerprint.updated_at.desc())
            )
            return session.exec(statement).first()

    # ═══════════════════════════════════════
    # Audit Reports & Gate Results
    # ═══════════════════════════════════════

    def add_audit_report(self, project_id: str, chapter_id: str | None,
                         overall_score: int, results_json: dict) -> AuditReport:
        report = AuditReport(
            project_id=project_id,
            chapter_id=chapter_id,
            overall_score=overall_score,
            results_json=results_json,
        )
        with Session(self.engine) as session:
            session.add(report)
            session.commit()
            session.refresh(report)
        self.touch_project(project_id)
        return report

    def add_gate_results(self, audit_report_id: int, gate_results: list[dict]) -> list[GateResult]:
        results = []
        with Session(self.engine) as session:
            for gr in gate_results:
                gate_result = GateResult(
                    audit_report_id=audit_report_id,
                    gate_id=gr.get("gate_id", ""),
                    gate_name=gr.get("gate_name", ""),
                    level=gr.get("level", "PASS"),
                    message=gr.get("message", ""),
                    suggestion=gr.get("suggestion", ""),
                )
                session.add(gate_result)
                results.append(gate_result)
            session.commit()
            for r in results:
                session.refresh(r)
        return results

    def get_audit_reports(self, project_id: str) -> list[AuditReport]:
        with Session(self.engine) as session:
            statement = (
                select(AuditReport)
                .where(AuditReport.project_id == project_id)
                .order_by(AuditReport.created_at.desc())
            )
            return list(session.exec(statement).all())

    def get_audit_report(self, audit_report_id: int) -> Optional[AuditReport]:
        with Session(self.engine) as session:
            return session.get(AuditReport, audit_report_id)

    # ═══════════════════════════════════════
    # Style Profiles (Marketplace)
    # ═══════════════════════════════════════

    def create_style_profile(self, name: str, author_id: str,
                             fingerprint_json: dict, genre_tags: list | None = None,
                             description: str = "") -> StyleProfile:
        profile = StyleProfile(
            name=name,
            author_id=author_id,
            fingerprint_json=fingerprint_json,
            genre_tags=genre_tags or [],
            description=description,
        )
        with Session(self.engine) as session:
            session.add(profile)
            session.commit()
            session.refresh(profile)
        return profile

    def get_style_profiles(self, genre: str | None = None,
                           sort_by: str = "downloads") -> list[StyleProfile]:
        with Session(self.engine) as session:
            statement = select(StyleProfile)
            if genre:
                # Simple filter - in production would use JSON contains
                pass
            if sort_by == "downloads":
                statement = statement.order_by(StyleProfile.download_count.desc())
            elif sort_by == "rating":
                statement = statement.order_by(StyleProfile.rating.desc())
            elif sort_by == "newest":
                statement = statement.order_by(StyleProfile.created_at.desc())
            return list(session.exec(statement).all())

    def get_style_profile(self, profile_id: int) -> Optional[StyleProfile]:
        with Session(self.engine) as session:
            return session.get(StyleProfile, profile_id)

    def increment_profile_download(self, profile_id: int) -> Optional[StyleProfile]:
        with Session(self.engine) as session:
            profile = session.get(StyleProfile, profile_id)
            if profile:
                profile.download_count += 1
                session.add(profile)
                session.commit()
                session.refresh(profile)
            return profile

    # ═══════════════════════════════════════
    # Plugin Configs
    # ═══════════════════════════════════════

    def set_plugin_config(self, project_id: str, plugin_id: str,
                          enabled: bool = True, settings: dict | None = None) -> PluginConfig:
        with Session(self.engine) as session:
            statement = (
                select(PluginConfig)
                .where(PluginConfig.project_id == project_id)
                .where(PluginConfig.plugin_id == plugin_id)
            )
            config = session.exec(statement).first()
            if not config:
                config = PluginConfig(
                    project_id=project_id,
                    plugin_id=plugin_id,
                    enabled=enabled,
                    settings=settings or {},
                )
            else:
                config.enabled = enabled
                config.settings = settings or {}
            session.add(config)
            session.commit()
            session.refresh(config)
        return config

    def get_plugin_configs(self, project_id: str) -> list[PluginConfig]:
        with Session(self.engine) as session:
            statement = (
                select(PluginConfig)
                .where(PluginConfig.project_id == project_id)
            )
            return list(session.exec(statement).all())

    # ═══════════════════════════════════════
    # Enhanced Style Fingerprint
    # ═══════════════════════════════════════

    def add_style_fingerprint_full(self, project_id: str,
                                   tone_vector: dict | None = None,
                                   pace_vector: dict | None = None,
                                   dialogue_ratio: float = 0.0,
                                   sensory_channel_bias: dict | None = None,
                                   pov_preference: str = "",
                                   vocabulary_richness: float = 0.0,
                                   syntactic_complexity: float = 0.0,
                                   conflict_distribution: dict | None = None) -> StyleFingerprint:
        fingerprint = StyleFingerprint(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            tone_vector_json=json.dumps(tone_vector or {}, ensure_ascii=False),
            pace_vector_json=json.dumps(pace_vector or {}, ensure_ascii=False),
            dialogue_ratio=dialogue_ratio,
            sensory_channel_bias_json=json.dumps(sensory_channel_bias or {}, ensure_ascii=False),
            pov_preference=pov_preference,
            vocabulary_richness=vocabulary_richness,
            syntactic_complexity=syntactic_complexity,
            conflict_distribution_json=json.dumps(conflict_distribution or {}, ensure_ascii=False),
        )
        with Session(self.engine) as session:
            session.add(fingerprint)
            session.commit()
            session.refresh(fingerprint)
        self.touch_project(project_id)
        return fingerprint
