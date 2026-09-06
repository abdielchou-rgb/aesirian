"""Initial migration - create all Æsirian tables.

Revision ID: 001
Revises: 
Create Date: 2026-09-05
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('title', sa.String(200), default='', index=True),
        sa.Column('genre', sa.String(50), default=''),
        sa.Column('premise', sa.Text, default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('style_profile_json', sa.Text, default='{}'),
    )

    # Chapters table
    op.create_table(
        'chapters',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('number', sa.Integer, default=0, nullable=False),
        sa.Column('title', sa.String(200), default=''),
        sa.Column('text', sa.Text, default=''),
        sa.Column('word_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('audit_report_json', sa.Text, default='{}'),
    )
    op.create_index('ix_chapters_project_number', 'chapters', ['project_id', 'number'], unique=True)

    # Characters table
    op.create_table(
        'characters',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('name', sa.String(100), default=''),
        sa.Column('role', sa.String(100), default=''),
        sa.Column('traits_json', sa.Text, default='{}'),
        sa.Column('beliefs_json', sa.Text, default='{}'),
        sa.Column('goals_json', sa.Text, default='[]'),
        sa.Column('secrets_json', sa.Text, default='[]'),
    )
    op.create_index('ix_characters_project_name', 'characters', ['project_id', 'name'])

    # World Elements table
    op.create_table(
        'world_elements',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('name', sa.String(200), default=''),
        sa.Column('type', sa.String(50), default=''),
        sa.Column('description', sa.Text, default=''),
        sa.Column('properties_json', sa.Text, default='{}'),
    )
    op.create_index('ix_world_elements_project_type', 'world_elements', ['project_id', 'type'])

    # Foreshadowings table
    op.create_table(
        'foreshadowings',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('chapter_id', sa.String(32), default=''),
        sa.Column('description', sa.Text, default=''),
        sa.Column('status', sa.String(20), default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_foreshadowings_project_status', 'foreshadowings', ['project_id', 'status'])

    # Style Fingerprints table
    op.create_table(
        'style_fingerprints',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('tone_vector_json', sa.Text, default='{}'),
        sa.Column('pace_vector_json', sa.Text, default='{}'),
        sa.Column('dialogue_ratio', sa.Float, default=0.0),
        sa.Column('sensory_channel_bias_json', sa.Text, default='{}'),
        sa.Column('pov_preference', sa.String(50), default=''),
        sa.Column('vocabulary_richness', sa.Float, default=0.0),
        sa.Column('syntactic_complexity', sa.Float, default=0.0),
        sa.Column('conflict_distribution_json', sa.Text, default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Audit Reports table
    op.create_table(
        'audit_reports',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('chapter_id', sa.String(32), sa.ForeignKey('chapters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('overall_score', sa.Integer, default=0),
        sa.Column('results_json', sa.JSON().with_variant(sqlite.JSON, 'sqlite'), default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_reports_project_created', 'audit_reports', ['project_id', 'created_at'])

    # Gate Results table
    op.create_table(
        'gate_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('audit_report_id', sa.Integer, sa.ForeignKey('audit_reports.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('gate_id', sa.String(20), nullable=False),
        sa.Column('gate_name', sa.String(100), default=''),
        sa.Column('level', sa.String(10), default='PASS'),
        sa.Column('message', sa.Text, default=''),
        sa.Column('suggestion', sa.Text, default=''),
    )

    # Style Profiles table (marketplace)
    op.create_table(
        'style_profiles',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, default=''),
        sa.Column('author_id', sa.String(50), default=''),
        sa.Column('fingerprint_json', sa.JSON().with_variant(sqlite.JSON, 'sqlite'), default=sa.text("'{}'")),
        sa.Column('genre_tags', sa.JSON().with_variant(sqlite.JSON, 'sqlite'), default=sa.text("'[]'")),
        sa.Column('download_count', sa.Integer, default=0),
        sa.Column('rating', sa.Float, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Plugin Configs table
    op.create_table(
        'plugin_configs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.id', ondelete='CASCADE'), index=True, nullable=False),
        sa.Column('plugin_id', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('settings', sa.JSON().with_variant(sqlite.JSON, 'sqlite'), default=sa.text("'{}'")),
    )
    op.create_index('ix_plugin_configs_project_plugin', 'plugin_configs', ['project_id', 'plugin_id'], unique=True)


def downgrade() -> None:
    # Drop in reverse order due to foreign keys
    op.drop_index('ix_plugin_configs_project_plugin', table_name='plugin_configs')
    op.drop_table('plugin_configs')

    op.drop_table('style_profiles')

    op.drop_table('gate_results')

    op.drop_index('ix_audit_reports_project_created', table_name='audit_reports')
    op.drop_table('audit_reports')

    op.drop_table('style_fingerprints')

    op.drop_index('ix_foreshadowings_project_status', table_name='foreshadowings')
    op.drop_table('foreshadowings')

    op.drop_index('ix_world_elements_project_type', table_name='world_elements')
    op.drop_table('world_elements')

    op.drop_index('ix_characters_project_name', table_name='characters')
    op.drop_table('characters')

    op.drop_index('ix_chapters_project_number', table_name='chapters')
    op.drop_table('chapters')

    op.drop_table('projects')