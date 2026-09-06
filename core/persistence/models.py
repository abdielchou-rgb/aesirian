"""
Æsirian SQLModel ORM models — SQLite persistence for narrative projects
"""
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)
from typing import Optional, List
import json

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, Text


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default=None, primary_key=True)
    title: str = Field(default="", index=True)
    genre: str = Field(default="")
    premise: str = Field(default="")
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    style_profile_json: str = Field(default="{}")

    chapters: List["Chapter"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    characters: List["CharacterRecord"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    world_elements: List["WorldElement"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    foreshadowings: List["Foreshadowing"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    style_fingerprints: List["StyleFingerprint"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    audit_reports: List["AuditReport"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Chapter(SQLModel, table=True):
    __tablename__ = "chapters"

    id: str = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    number: int = Field(default=0)
    title: str = Field(default="")
    text: str = Field(default="", sa_column=Column(Text))
    word_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=now_utc)
    audit_report_json: str = Field(default="{}")

    project: Optional[Project] = Relationship(back_populates="chapters")


class CharacterRecord(SQLModel, table=True):
    __tablename__ = "characters"

    id: str = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    name: str = Field(default="")
    role: str = Field(default="")
    traits_json: str = Field(default="{}")
    beliefs_json: str = Field(default="{}")
    goals_json: str = Field(default="[]")
    secrets_json: str = Field(default="[]")

    project: Optional[Project] = Relationship(back_populates="characters")


# 兼容别名 — orchestrator 引用 Character
Character = CharacterRecord


class WorldElement(SQLModel, table=True):
    __tablename__ = "world_elements"

    id: str = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    name: str = Field(default="")
    type: str = Field(default="")  # location / item / event / character / relationship / theme
    description: str = Field(default="")
    properties_json: str = Field(default="{}")

    project: Optional[Project] = Relationship(back_populates="world_elements")


class Foreshadowing(SQLModel, table=True):
    __tablename__ = "foreshadowings"

    id: str = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    chapter_id: str = Field(default="")
    description: str = Field(default="")
    status: str = Field(default="open")  # open / resolved / abandoned
    created_at: datetime = Field(default_factory=now_utc)
    resolved_at: Optional[datetime] = Field(default=None)

    project: Optional[Project] = Relationship(back_populates="foreshadowings")


class StyleFingerprint(SQLModel, table=True):
    __tablename__ = "style_fingerprints"

    id: str = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    tone_vector_json: str = Field(default="{}")
    pace_vector_json: str = Field(default="{}")
    dialogue_ratio: float = Field(default=0.0)
    sensory_channel_bias_json: str = Field(default="{}")
    pov_preference: str = Field(default="")
    vocabulary_richness: float = Field(default=0.0)
    syntactic_complexity: float = Field(default=0.0)
    conflict_distribution_json: str = Field(default="{}")
    updated_at: datetime = Field(default_factory=now_utc)

    project: Optional[Project] = Relationship(back_populates="style_fingerprints")


class AuditReport(SQLModel, table=True):
    """Audit report for a chapter"""
    __tablename__ = "audit_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    chapter_id: Optional[str] = Field(default=None, foreign_key="chapters.id")
    overall_score: int = Field(default=0)
    results_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)

    project: Optional[Project] = Relationship(back_populates="audit_reports")
    gate_results: List["GateResult"] = Relationship(back_populates="audit_report", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class GateResult(SQLModel, table=True):
    """Individual gate result within an audit report"""
    __tablename__ = "gate_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    audit_report_id: int = Field(foreign_key="audit_reports.id", index=True)
    gate_id: str
    gate_name: str = Field(default="")
    level: str  # PASS, WARN, BLOCK
    message: str = Field(default="")
    suggestion: str = Field(default="")

    audit_report: Optional[AuditReport] = Relationship(back_populates="gate_results")


class StyleProfile(SQLModel, table=True):
    """Shareable style profile (marketplace)"""
    __tablename__ = "style_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = Field(default="")
    author_id: str = Field(default="")
    fingerprint_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    genre_tags: list = Field(default_factory=list, sa_column=Column(JSON))
    download_count: int = Field(default=0)
    rating: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=now_utc)


class PluginConfig(SQLModel, table=True):
    """Project-level plugin configuration"""
    __tablename__ = "plugin_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    plugin_id: str
    enabled: bool = Field(default=True)
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))
