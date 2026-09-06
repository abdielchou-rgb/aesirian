"""
Æsirian 导出器 — Markdown / EPUB / 章节级导出

将项目状态序列化为可读文件。EPUB 依赖 ebooklib，缺失时自动降级为 Markdown。
"""
from __future__ import annotations

import os

from core.orchestrator import ProjectState, ChapterInfo


# ═══════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════

def _ensure_dir(path: str) -> str:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return path


def _character_rows(project: ProjectState) -> list[tuple[str, str, str]]:
    rows = []
    for char in project.tom.get_all_characters():
        role = ""
        kg_node = None
        for node in project.kg.nodes.values():
            if node.name == char.name and node.type.value == "角色":
                kg_node = node
                break
        if kg_node:
            role = kg_node.properties.get("role", "")
        description = ", ".join(
            f"{g.description}(优先级{g.priority})"
            for g in char.active_goals[:2]
        )
        rows.append((char.name, role, description))
    return rows


# ═══════════════════════════════════════════
# Markdown 导出
# ═══════════════════════════════════════════

def export_project_markdown(project: ProjectState, output_path: str) -> str:
    """导出完整项目为单个 Markdown 文件，返回写入路径。"""
    _ensure_dir(output_path)

    lines: list[str] = []
    lines.append(f"# {project.title}")
    lines.append("")
    if project.genre:
        lines.append(f"**Genre:** {project.genre}")
    if project.premise:
        lines.append(f"**Premise:** {project.premise}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not project.chapters:
        lines.append("_(暂无章节)_")
    else:
        for ch in project.chapters:
            lines.append(f"## Chapter {ch.chapter_number}: {ch.title}")
            lines.append("")
            lines.append(ch.text)
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## Characters")
    lines.append("")
    rows = _character_rows(project)
    if not rows:
        lines.append("_(暂无角色)_")
    else:
        lines.append("| Name | Role | Description |")
        lines.append("|------|------|-------------|")
        for name, role, desc in rows:
            lines.append(f"| {name} | {role} | {desc} |")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def export_chapter_markdown(chapter: ChapterInfo, output_path: str) -> str:
    """导出单个章节为 Markdown 文件，返回写入路径。"""
    _ensure_dir(output_path)
    lines = [
        f"# Chapter {chapter.chapter_number}: {chapter.title}",
        "",
        chapter.text,
        "",
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


# ═══════════════════════════════════════════
# EPUB 导出
# ═══════════════════════════════════════════

def export_project_epub(project: ProjectState, output_path: str) -> str:
    """导出为 EPUB。ebooklib 未安装时降级为 Markdown 并返回其路径。"""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        md_path = output_path.rsplit(".", 1)[0] + ".md"
        return export_project_markdown(project, md_path)

    _ensure_dir(output_path)

    book = epub.EpubBook()
    book.set_identifier(project.project_id)
    book.set_title(project.title or "Æsirian Export")
    book.set_language("zh-CN")
    if project.premise:
        book.add_metadata("DC", "description", project.premise)

    chapters = []
    for ch in project.chapters:
        c = epub.EpubHtml(
            title=ch.title,
            file_name=f"chapter_{ch.chapter_number:03d}.xhtml",
            lang="zh-CN",
        )
        body = ch.text.replace("\n", "<br/>")
        c.content = f"<h1>Chapter {ch.chapter_number}: {ch.title}</h1><p>{body}</p>"
        book.add_item(c)
        chapters.append(c)

    book.toc = tuple(chapters)
    book.spine = ["nav"] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(output_path, book, {})
    return output_path
