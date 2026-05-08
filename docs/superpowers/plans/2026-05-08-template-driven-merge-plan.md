# Template-Driven Document Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the merge engine from semantic commonality analysis to template-driven content assembly with main-doc + attachment architecture.

**Architecture:** Two new modules (template_parser, builtin_template) provide the skeleton and default styles. analyzer.py is refactored from group-by-heading common/unique logic to a two-phase AI pipeline (structure planning → section generation). merger.py accepts a TemplateSkeleton for style-driven output. agent.py gains an `upload_template` tool. Frontend adds optional template upload.

**Tech Stack:** Python/FastAPI backend, React frontend, Anthropic SDK for AI, python-docx for document generation

---

### File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/template_parser.py` | CREATE | Parse template docx → TemplateSkeleton (styles, layout, section tree) |
| `backend/builtin_template.py` | CREATE | Default TemplateSkeleton when no template uploaded |
| `backend/analyzer.py` | REFACTOR | Replace group-by-heading → template-driven two-phase AI |
| `backend/merger.py` | REFACTOR | Accept TemplateSkeleton, style-driven docx generation |
| `backend/agent.py` | MODIFY | Add `upload_template` tool, refactor merge pipeline |
| `backend/main.py` | MODIFY | Add template upload API endpoint |
| `frontend/src/App.jsx` | MODIFY | Template file state + upload handling |
| `frontend/src/components/ChatInput.jsx` | MODIFY | Add "上传模板" button |

---

### Task 1: Template Skeleton Data Structures

**Files:**
- Create: `backend/template_parser.py`

- [ ] **Step 1: Create template_parser.py with dataclasses and parse function**

```python
"""Template parser: extracts structure, styles, and layout from a template docx."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from docx import Document as DocxDocument


@dataclass
class StyleDef:
    """A single paragraph style definition extracted from the template."""
    name: str
    font_name: str = ""
    font_size_pt: float = 0.0
    bold: bool = False
    color: str = ""  # hex RGB
    line_spacing: float = 0.0


@dataclass
class SectionNode:
    """A section heading in the template's document structure."""
    heading: str
    level: int
    style_name: str
    children: List["SectionNode"] = field(default_factory=list)


@dataclass
class PageLayout:
    """Page dimensions and margins from the template."""
    page_width: int = 0      # EMU
    page_height: int = 0     # EMU
    margin_top: int = 0      # EMU
    margin_bottom: int = 0   # EMU
    margin_left: int = 0     # EMU
    margin_right: int = 0    # EMU


@dataclass
class TemplateSkeleton:
    """Complete template structure extracted from a docx file."""
    styles: Dict[str, StyleDef] = field(default_factory=dict)
    page_layout: PageLayout = field(default_factory=PageLayout)
    sections: List[SectionNode] = field(default_factory=list)
    cover_elements: List[dict] = field(default_factory=list)
    has_header: bool = False
    has_footer: bool = False


STYLE_LEVEL_MAP = {
    "Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
    "Heading 4": 4, "Heading 5": 5, "Heading 6": 6,
    "章标题": 1, "一级条标题": 2, "二级条标题": 3, "三级条标题": 4,
    "前言、引言标题": 1, "封面标准名称": 1,
}


def _get_level(style_name: str) -> int:
    return STYLE_LEVEL_MAP.get(style_name, 0)


def parse_template(filepath: str) -> TemplateSkeleton:
    """Parse a template docx and extract its full skeleton."""
    doc = DocxDocument(filepath)
    skel = TemplateSkeleton()

    # --- Extract style definitions ---
    for s in doc.styles:
        if s.type is None or 'PARAGRAPH' not in str(s.type):
            continue
        try:
            font = s.font
            sd = StyleDef(name=s.name)
            if font.name:
                sd.font_name = font.name
            if font.size:
                sd.font_size_pt = font.size.pt
            if font.bold is not None:
                sd.bold = font.bold
            if font.color and font.color.rgb:
                sd.color = str(font.color.rgb)
            pf = s.paragraph_format
            if pf and pf.line_spacing:
                sd.line_spacing = float(pf.line_spacing)
            if sd.font_name or sd.font_size_pt:
                skel.styles[s.name] = sd
        except Exception:
            pass

    # --- Extract page layout ---
    if doc.sections:
        sec = doc.sections[0]
        skel.page_layout = PageLayout(
            page_width=sec.page_width,
            page_height=sec.page_height,
            margin_top=sec.top_margin,
            margin_bottom=sec.bottom_margin,
            margin_left=sec.left_margin,
            margin_right=sec.right_margin,
        )
        # Check header/footer
        try:
            if sec.header and any(p.text.strip() for p in sec.header.paragraphs):
                skel.has_header = True
        except Exception:
            pass
        try:
            if sec.footer and any(p.text.strip() for p in sec.footer.paragraphs):
                skel.has_footer = True
        except Exception:
            pass

    # --- Extract section tree ---
    section_stack: List[SectionNode] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style_name = p.style.name if p.style else ""
        level = _get_level(style_name)
        if level > 0:
            node = SectionNode(heading=text, level=level, style_name=style_name)
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            if section_stack:
                section_stack[-1].children.append(node)
            else:
                skel.sections.append(node)
            section_stack.append(node)

    # --- Extract cover elements (paragraphs before first real heading) ---
    found_first_heading = False
    for p in doc.paragraphs:
        text = p.text.strip()
        style_name = p.style.name if p.style else ""
        level = _get_level(style_name)
        if level > 0 and style_name not in ("封面标准名称", "封面标准号2",
                                              "其他标准标志", "其他标准称谓"):
            found_first_heading = True
        if found_first_heading:
            break
        if text:
            skel.cover_elements.append({
                "text": text,
                "style_name": style_name,
            })

    return skel
```

- [ ] **Step 2: Verify template parser works with the example template**

Run:
```bash
cd backend && python -c "
from template_parser import parse_template
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

skel = parse_template('../QSCW-V-C054-PD-2025 运行工岗位操作规程.docx')
print(f'Styles: {len(skel.styles)}')
for name, sd in sorted(skel.styles.items()):
    print(f'  {name}: font={sd.font_name} size={sd.font_size_pt}pt bold={sd.bold}')
print(f'Page: {skel.page_layout.page_width}x{skel.page_layout.page_height}')
print(f'Sections: {len(skel.sections)}')
for s in skel.sections:
    print(f'  [H{s.level}] {s.heading[:60]}')
print(f'Cover elements: {len(skel.cover_elements)}')
"
```

Expected: prints style count, page dimensions, section tree, cover elements.

- [ ] **Step 3: Commit**

```bash
git add backend/template_parser.py
git commit -m "feat: add template_parser to extract docx structure and styles"
```

---

### Task 2: Built-in Standard Template

**Files:**
- Create: `backend/builtin_template.py`

- [ ] **Step 1: Create builtin_template.py with default enterprise format**

This module provides a default TemplateSkeleton when no template is uploaded, matching the enterprise document standard.

```python
"""Built-in standard template used when no custom template is uploaded.

Provides a professional enterprise-document format with:
- Cover page (黑体 26pt title)
- Auto-generated TOC
- Standard heading hierarchy (黑体 at various sizes)
- Body text (宋体 10.5pt)
- Standard A4 page layout
"""

from template_parser import (
    TemplateSkeleton, StyleDef, SectionNode, PageLayout,
)


def _make_default_styles() -> dict:
    """Build the default enterprise style set."""
    styles = {}
    styles["Normal"] = StyleDef(
        name="Normal", font_name="Times New Roman", font_size_pt=10.5,
    )
    styles["Heading 1"] = StyleDef(
        name="Heading 1", font_name="黑体", font_size_pt=22.0, bold=True,
        line_spacing=2.4,
    )
    styles["Heading 2"] = StyleDef(
        name="Heading 2", font_name="黑体", font_size_pt=16.0, bold=True,
    )
    styles["Heading 3"] = StyleDef(
        name="Heading 3", font_name="黑体", font_size_pt=10.5, bold=True,
    )
    styles["章标题"] = StyleDef(
        name="章标题", font_name="黑体", font_size_pt=10.5,
    )
    styles["一级条标题"] = StyleDef(
        name="一级条标题", font_name="黑体", font_size_pt=10.5,
    )
    styles["二级条标题"] = StyleDef(
        name="二级条标题", font_name="黑体", font_size_pt=10.5, bold=True,
    )
    styles["段"] = StyleDef(
        name="段", font_name="宋体", font_size_pt=10.5,
    )
    styles["前言、引言标题"] = StyleDef(
        name="前言、引言标题", font_name="黑体", font_size_pt=16.0,
    )
    styles["封面标准名称"] = StyleDef(
        name="封面标准名称", font_name="黑体", font_size_pt=26.0,
    )
    styles["其他标准称谓"] = StyleDef(
        name="其他标准称谓", font_name="黑体", font_size_pt=24.0,
    )
    styles["List Paragraph"] = StyleDef(
        name="List Paragraph", font_name="宋体", font_size_pt=10.5,
    )
    styles["toc 1"] = StyleDef(
        name="toc 1", font_name="黑体", font_size_pt=10.0,
    )
    styles["toc 2"] = StyleDef(
        name="toc 2", font_name="宋体", font_size_pt=10.0,
    )
    return styles


def _make_default_page_layout() -> PageLayout:
    """A4 paper with standard margins (in EMU)."""
    return PageLayout(
        page_width=7560310,
        page_height=10692130,
        margin_top=914400,      # ~2.5cm
        margin_bottom=914400,   # ~2.5cm
        margin_left=1008000,    # ~2.8cm
        margin_right=1008000,   # ~2.8cm
    )


def _make_default_sections() -> list:
    """Default document skeleton for document merging."""
    return [
        SectionNode(heading="前言", level=1, style_name="前言、引言标题"),
        SectionNode(heading="一、范围与规范性引用", level=1, style_name="Heading 1"),
        SectionNode(heading="二、内容概述", level=1, style_name="Heading 1"),
        SectionNode(heading="三、各文档内容", level=1, style_name="Heading 1", children=[
            SectionNode(heading="来源文档", level=2, style_name="Heading 2"),
        ]),
        SectionNode(heading="附件", level=1, style_name="Heading 1"),
    ]


def get_builtin_template() -> TemplateSkeleton:
    """Return the built-in standard template skeleton."""
    return TemplateSkeleton(
        styles=_make_default_styles(),
        page_layout=_make_default_page_layout(),
        sections=_make_default_sections(),
        cover_elements=[
            {"text": "文档合并汇编", "style_name": "封面标准名称"},
        ],
        has_header=False,
        has_footer=False,
    )
```

- [ ] **Step 2: Verify builtin template works**

Run:
```bash
cd backend && python -c "
from builtin_template import get_builtin_template
skel = get_builtin_template()
print(f'Styles: {len(skel.styles)}')
print(f'Fonts: {[sd.font_name for sd in skel.styles.values() if sd.font_name]}')
print(f'Sections: {len(skel.sections)}')
print('OK')
"
```

Expected: prints style count, font list, section count, "OK".

- [ ] **Step 3: Commit**

```bash
git add backend/builtin_template.py
git commit -m "feat: add builtin_template for standard format when no template uploaded"
```

---

### Task 3: Refactor analyzer.py — Replace Common/Unique with Template-Driven

**Files:**
- Modify: `backend/analyzer.py` (major refactor)

This is the largest change. We replace the current `analyze_documents` function with a new two-phase pipeline. The old functions (`flatten_sections`, `group_by_heading`, `match_similar_headings`, `ai_analysis`, `structural_only_analysis`) are replaced with template-driven equivalents.

- [ ] **Step 1: Add new imports and keep MergePlan + _dedup_images_by_hash, remove old analysis logic**

At the top of `backend/analyzer.py`, replace the current imports and keep only what's needed. The new file will be a complete rewrite of the analysis functions while keeping `MergePlan`, `_dedup_images_by_hash`, `_call_claude_streaming`, `_extract_json`, and adding new template-driven functions.

Replace the entire content of `backend/analyzer.py`:

```python
"""AI semantic analyzer: template-driven document merging.

Two-phase pipeline:
  Phase 1 — AI plans the output structure (main doc sections + attachment mapping)
  Phase 2 — AI generates each section concurrently (main doc synthesis + attachments)
"""

import json
import re
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from collections import defaultdict

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, MODEL,
    HTTP_VERIFY_SSL, HTTP_TRUST_ENV,
)
from template_parser import TemplateSkeleton, SectionNode

logger = logging.getLogger("analyzer")


@dataclass
class MergePlan:
    """Result of template-driven analysis."""
    # Main document sections: AI-synthesized content
    main_sections: List[dict] = field(default_factory=list)
    # Attachments: source-specific operational details
    attachments: List[dict] = field(default_factory=list)
    # Cover title for the output document
    cover_title: str = "文档合并汇编"
    # TOC headings
    toc_headings: List[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 1: Structure Planning
# ---------------------------------------------------------------------------

def _build_structure_plan_prompt(skeleton: TemplateSkeleton,
                                  source_summaries: List[dict]) -> str:
    """Build the prompt for Phase 1 AI: plan the output structure."""
    skel_desc = []
    for s in skeleton.sections:
        indent = "  " * s.level
        skel_desc.append(f"{indent}[H{s.level}] {s.heading}")
    skel_text = "\n".join(skel_desc)

    src_desc = []
    for i, s in enumerate(source_summaries):
        src_desc.append(
            f"{i+1}. **{s['filename']}**: {s.get('paragraph_count', 0)}段, "
            f"{s.get('heading_count', 0)}个标题, "
            f"主要标题: {'; '.join(s.get('top_headings', [])[:5])}"
        )
    src_text = "\n".join(src_desc)

    return f"""你是一个专业的文档编辑。请根据以下模板骨架和源文件信息，规划合并文档的结构。

## 模板骨架
{skel_text}

## 源文件 ({len(source_summaries)}个)
{src_text}

## 任务
规划最终合并文档的结构。规则：
1. **主文档**：模板骨架中的通用章节（范围、职责、风险、防护用品等）→ 从所有源文件综合撰写
2. **附件**：每个源文件的独有操作细节成为附件。源文件标题作为附件名。
3. **内容不重复**：主文档已有的，附件不再出现。
4. 如果模板骨架没有足够的章节容纳所有源文件，可以增加或调整章节。

请严格输出以下JSON格式（不要输出其他内容）：
{{
  "cover_title": "合并文档标题",
  "main_sections": [
    {{"heading": "章节标题", "level": 1, "style_name": "Heading 1", "sources": "all"}}
  ],
  "attachments": [
    {{"name": "附件A：xxx", "source_index": 0, "include_sections": ["作业要求"]}}
  ],
  "toc_headings": [
    {{"level": 1, "text": "前言"}},
    {{"level": 1, "text": "一、范围与规范性引用"}}
  ]
}}"""


def plan_structure(skeleton: TemplateSkeleton,
                   source_summaries: List[dict],
                   progress_callback: Optional[Callable] = None) -> dict:
    """Phase 1: AI plans the output document structure.

    Args:
        skeleton: Parsed template skeleton
        source_summaries: List of {filename, paragraph_count, heading_count, top_headings}
        progress_callback: Optional progress reporter

    Returns:
        dict with main_sections, attachments, cover_title, toc_headings
    """
    import anthropic
    import httpx

    if progress_callback:
        progress_callback("progress", {
            "stage": "planning",
            "message": "AI 正在规划文档结构...",
            "percent": 25,
        })

    prompt = _build_structure_plan_prompt(skeleton, source_summaries)

    http_client = httpx.Client(verify=HTTP_VERIFY_SSL, trust_env=HTTP_TRUST_ENV)
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        http_client=http_client,
    )

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system="你是一个专业的文档编辑。你的输出必须是合法的JSON格式。",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response_text = ""
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        response_text += event.delta.text

        if not response_text.strip():
            raise ValueError("AI returned empty response for structure planning")

        result = _extract_json(response_text)
        logger.info("Structure plan generated: %d main sections, %d attachments",
                     len(result.get("main_sections", [])),
                     len(result.get("attachments", [])))
        return result

    finally:
        http_client.close()


# ---------------------------------------------------------------------------
# Phase 2: Section Generation
# ---------------------------------------------------------------------------

def _build_main_section_prompt(heading: str, level: int,
                                all_source_texts: List[dict]) -> str:
    """Build prompt for generating one main document section."""
    sources_text = []
    for s in all_source_texts:
        sources_text.append(
            f"### {s['filename']}\n{s['full_text'][:3000]}"
            f"{'...(截断)' if len(s.get('full_text', '')) > 3000 else ''}"
        )
    combined = "\n\n---\n\n".join(sources_text)

    return f"""你是一个专业的文档编辑。请为合并文档撰写「{heading}」章节的内容。

## 任务
综合以下 {len(all_source_texts)} 个源文件的内容，撰写一个统一的「{heading}」章节。
- 提取与「{heading}」相关的共性内容，融合为通顺的表述
- 只写概括性内容，不要写详细的操作步骤（操作步骤属于附件）
- 如果某源文件没有相关内容，跳过即可
- 保持专业、简洁的企业文档风格
- 使用中文

## 源文件内容
{combined}

请直接输出该章节的正文内容（纯文本，不要JSON格式）。"""


def _build_attachment_prompt(attachment_name: str, source_text: str,
                              covered_topics: List[str]) -> str:
    """Build prompt for generating one attachment section."""
    covered = "\n".join(f"- {t}" for t in covered_topics) if covered_topics else "（无）"

    return f"""你是一个专业的文档编辑。请为合并文档的「{attachment_name}」提取内容。

## 任务
从以下源文件中提取独有操作细节，作为文档附件。
- 如果内容已在主文档中覆盖，不要重复
- 保留操作步骤的完整性和原文表述
- 不需要添加"附件X"标题（标题会单独生成）

## 已在主文档中覆盖的主题（不要重复这些内容）
{covered}

## 源文件内容
{source_text[:5000]}{'...(截断)' if len(source_text) > 5000 else ''}

请输出提取后的内容（保留原有章节结构和操作步骤）。"""


def _generate_section(heading: str, level: int, style_name: str,
                       all_source_texts: List[dict],
                       progress_callback=None) -> dict:
    """Phase 2: Generate content for one main document section."""
    import anthropic
    import httpx

    prompt = _build_main_section_prompt(heading, level, all_source_texts)

    http_client = httpx.Client(verify=HTTP_VERIFY_SSL, trust_env=HTTP_TRUST_ENV)
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        http_client=http_client,
    )

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system="你是一个专业的文档编辑。输出简洁、通顺的中文段落。",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response_text = ""
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        response_text += event.delta.text

        paragraphs = [p.strip() for p in response_text.strip().split("\n\n") if p.strip()]

        return {
            "heading": heading,
            "level": level,
            "style_name": style_name,
            "paragraphs": paragraphs,
            "tables": [],
            "images": [],
        }
    finally:
        http_client.close()


def _generate_attachment(att_name: str, source_text: str,
                          covered_topics: List[str],
                          progress_callback=None) -> dict:
    """Phase 2: Generate content for one attachment."""
    import anthropic
    import httpx

    prompt = _build_attachment_prompt(att_name, source_text, covered_topics)

    http_client = httpx.Client(verify=HTTP_VERIFY_SSL, trust_env=HTTP_TRUST_ENV)
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        http_client=http_client,
    )

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=8192,
            system="你是一个专业的文档编辑。保留原文的操作步骤完整性。",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response_text = ""
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        response_text += event.delta.text

        paragraphs = [p.strip() for p in response_text.strip().split("\n\n") if p.strip()]

        return {
            "name": att_name,
            "paragraphs": paragraphs,
            "level": 1,
        }
    finally:
        http_client.close()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def analyze_documents(docs_data: List[dict],
                      skeleton: TemplateSkeleton = None,
                      progress_callback: Optional[Callable] = None) -> MergePlan:
    """Template-driven merge analysis.

    Args:
        docs_data: List of ParsedDocument.to_dict() results
        skeleton: Template skeleton (from template_parser or builtin_template)
        progress_callback: Optional fn(event_type, data_dict) for UI updates

    Returns:
        MergePlan with main_sections and attachments
    """
    if progress_callback:
        progress_callback("progress", {
            "stage": "preparing",
            "message": "准备分析...",
            "percent": 10,
        })

    # Build source summaries for Phase 1
    source_summaries = []
    for doc in docs_data:
        sections = doc.get("sections", [])
        all_headings = []
        for s in sections:
            if s.get("heading"):
                all_headings.append(s["heading"])
            for c in s.get("children", []):
                if c.get("heading"):
                    all_headings.append(c["heading"])
        source_summaries.append({
            "filename": doc.get("filename", ""),
            "paragraph_count": sum(1 for s in sections for _ in s.get("paragraphs", [])),
            "heading_count": len(all_headings),
            "top_headings": [s.get("heading", "") for s in sections[:8] if s.get("heading")],
        })

    # Phase 1: Plan structure
    if progress_callback:
        progress_callback("progress", {
            "stage": "planning",
            "message": "AI 正在规划文档结构...",
            "percent": 25,
        })

    try:
        structure_plan = plan_structure(skeleton or _get_fallback_skeleton(),
                                        source_summaries, progress_callback)
    except Exception as e:
        logger.error("Structure planning failed: %s", e)
        structure_plan = _fallback_plan(source_summaries)

    # Build full text dict for Phase 2
    doc_texts = []
    for doc in docs_data:
        sections = doc.get("sections", [])
        full = _flatten_full_text(sections)
        doc_texts.append({
            "filename": doc.get("filename", ""),
            "full_text": full,
        })

    plan = MergePlan()
    plan.cover_title = structure_plan.get("cover_title", "文档合并汇编")
    plan.toc_headings = structure_plan.get("toc_headings", [])
    plan.summary = {"mode": "template_driven"}

    main_plan = structure_plan.get("main_sections", [])
    attach_plan = structure_plan.get("attachments", [])

    if progress_callback:
        progress_callback("progress", {
            "stage": "generating",
            "message": f"AI 正在生成主文档内容 ({len(main_plan)}个章节)...",
            "percent": 35,
        })

    # Phase 2a: Generate main sections concurrently
    lock = threading.Lock()
    completed = 0
    total = len(main_plan) + len(attach_plan)

    if main_plan:
        def gen_main(sec_info):
            return _generate_section(
                sec_info.get("heading", ""),
                sec_info.get("level", 1),
                sec_info.get("style_name", "Heading 2"),
                doc_texts,
                progress_callback,
            )

        max_w = min(3, len(main_plan))
        with ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = {executor.submit(gen_main, s): s for s in main_plan}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    completed += 1
                    plan.main_sections.append(result)
                    if progress_callback:
                        progress_callback("progress", {
                            "stage": "generating",
                            "message": f"主文档生成 ({completed}/{total}): {result.get('heading', '')}",
                            "percent": 35 + int(25 * completed / max(total, 1)),
                        })

    # Phase 2b: Generate attachments concurrently
    if attach_plan:
        # Build list of covered topics from main sections
        covered = [s.get("heading", "") for s in plan.main_sections]

        def gen_att(att_info):
            src_idx = att_info.get("source_index", 0)
            src_text = doc_texts[src_idx]["full_text"] if src_idx < len(doc_texts) else ""
            return _generate_attachment(
                att_info.get("name", "附件"),
                src_text,
                covered,
                progress_callback,
            )

        max_w = min(3, len(attach_plan))
        with ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = {executor.submit(gen_att, a): a for a in attach_plan}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    completed += 1
                    plan.attachments.append(result)
                    if progress_callback:
                        progress_callback("progress", {
                            "stage": "generating",
                            "message": f"附件生成 ({completed}/{total}): {result.get('name', '')}",
                            "percent": 35 + int(25 * completed / max(total, 1)),
                        })

    plan.summary = {
        "main_sections": len(plan.main_sections),
        "attachments": len(plan.attachments),
        "total_docs": len(docs_data),
        "mode": "template_driven",
        "cover_title": plan.cover_title,
    }

    if progress_callback:
        progress_callback("progress", {
            "stage": "generated",
            "message": "内容生成完成",
            "percent": 65,
        })

    return plan


# ---------------------------------------------------------------------------
# Fallback / Helpers
# ---------------------------------------------------------------------------

def _get_fallback_skeleton() -> TemplateSkeleton:
    from builtin_template import get_builtin_template
    return get_builtin_template()


def _fallback_plan(source_summaries: List[dict]) -> dict:
    """Fallback plan when AI structure planning fails."""
    return {
        "cover_title": "文档合并汇编",
        "main_sections": [
            {"heading": "前言", "level": 1, "style_name": "前言、引言标题", "sources": "all"},
            {"heading": "范围与规范性引用", "level": 1, "style_name": "Heading 1", "sources": "all"},
            {"heading": "内容概述", "level": 1, "style_name": "Heading 1", "sources": "all"},
        ],
        "attachments": [
            {
                "name": f"附件{chr(65+i)}：{s['filename'].replace('.docx', '')}",
                "source_index": i,
                "include_sections": [],
            }
            for i, s in enumerate(source_summaries)
        ],
        "toc_headings": [
            {"level": 1, "text": "前言"},
            {"level": 1, "text": "范围与规范性引用"},
            {"level": 1, "text": "内容概述"},
        ],
    }


def _flatten_full_text(sections: List[dict]) -> str:
    """Extract all text from sections for AI prompts."""
    parts = []
    for s in sections:
        h = s.get("heading", "")
        if h:
            parts.append(h)
        for p in s.get("paragraphs", []):
            if p.strip():
                parts.append(p.strip())
        for c in s.get("children", []):
            ch = c.get("heading", "")
            if ch:
                parts.append(ch)
            for cp in c.get("paragraphs", []):
                if cp.strip():
                    parts.append(cp.strip())
    return "\n\n".join(parts)


# Reuse existing helpers
def _extract_json(text: str) -> dict:
    """Robust JSON extraction from AI response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    cleaned = re.sub(r',\s*}', '}', text)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise


def _dedup_images_by_hash(images: List[dict], threshold: int = 5) -> List[dict]:
    """Deduplicate images by dHash Hamming distance."""
    if not images:
        return []
    from doc_parser import hamming_distance
    result = []
    remaining = list(images)
    while remaining:
        pivot = remaining.pop(0)
        group = [pivot]
        new_remaining = []
        for img in remaining:
            if hamming_distance(pivot.get("dhash", ""), img.get("dhash", "")) <= threshold:
                group.append(img)
            else:
                new_remaining.append(img)
        remaining = new_remaining
        group.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)
        result.append(group[0])
    return result
```

- [ ] **Step 2: Verify analyzer imports and basic structure**

Run:
```bash
cd backend && python -c "
from analyzer import MergePlan, analyze_documents, _extract_json
print('MergePlan:', MergePlan)
print('analyze_documents:', analyze_documents)
print('OK')
"
```

Expected: prints class/function info, "OK".

- [ ] **Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "refactor: replace common/unique analysis with template-driven two-phase AI"
```

---

### Task 4: Refactor merger.py — Style-Driven DOCX Generation

**Files:**
- Modify: `backend/merger.py`

The current merger has hardcoded styles (宋体, Pt 11, etc.) and a fixed Part1/Part2 structure. Refactor to accept a TemplateSkeleton and use its style definitions. Keep image handling and table insertion logic.

- [ ] **Step 1: Update merger.py to accept TemplateSkeleton**

Replace `generate_merged_docx` to accept `TemplateSkeleton` and generate structure from the new MergePlan format.

The key changes to `backend/merger.py`:

```python
"""Merger: generates the final merged docx from the MergePlan with template styles."""

# Keep existing imports and helpers (_set_heading_style, _add_paragraph,
# _add_image_to_doc, _normalize_for_match, _find_best_paragraph_index,
# _build_image_lookup, _insert_images_for_paragraphs,
# _write_paragraphs_with_images, _insert_table)

# Replace _create_cover to accept TemplateSkeleton styles:

def _create_cover(doc, doc_count, filenames, cover_title="文档合并汇编",
                  skeleton=None):
    """Create a cover page using template styles or built-in defaults."""
    # Use skeleton styles for cover, falling back to defaults
    cover_style = "封面标准名称"
    for _ in range(6):
        doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.style = doc.styles[cover_style] if cover_style in [
        s.name for s in doc.styles] else doc.styles['Normal']
    run = title_para.add_run(cover_title)
    run.font.size = Pt(26)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_para.add_run("合并文档")
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()
    doc.add_paragraph()

    info_para = doc.add_paragraph()
    info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info_para.add_run(f"合并文档数量：{doc_count} 份")
    run.font.size = Pt(12)

    names_para = doc.add_paragraph()
    names_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    names = "、".join(filenames[:3]) + ("..." if len(filenames) > 3 else "")
    run = names_para.add_run(names)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_paragraph()
    doc.add_paragraph()

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_para.add_run(f"生成日期：{datetime.now().strftime('%Y-%m-%d')}")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    doc.add_page_break()


# Replace _apply_template_styles function:

def _apply_template_styles(doc, skeleton):
    """Apply template style definitions to the document."""
    if not skeleton or not skeleton.styles:
        return  # Use defaults
    for style_name, style_def in skeleton.styles.items():
        try:
            if style_name in [s.name for s in doc.styles]:
                style = doc.styles[style_name]
            else:
                continue
            font = style.font
            if style_def.font_name:
                font.name = style_def.font_name
            if style_def.font_size_pt:
                font.size = Pt(style_def.font_size_pt)
            if style_def.bold:
                font.bold = True
            if style_def.color:
                try:
                    font.color.rgb = RGBColor.from_string(style_def.color)
                except Exception:
                    pass
        except Exception:
            pass


# Replace _collect_toc_headings:

def _collect_toc_headings(merge_plan, docs_data) -> List[dict]:
    """Walk the merge plan and collect all headings for TOC."""
    headings = []

    if merge_plan.toc_headings:
        return merge_plan.toc_headings

    # Generate from plan structure
    headings.append({"level": 1, "text": "前言"})

    for section in merge_plan.main_sections:
        h = section.get("heading", "")
        if h:
            headings.append({
                "level": min(section.get("level", 1) + 1, 3),
                "text": h,
            })

    if merge_plan.attachments:
        headings.append({"level": 1, "text": "附件"})
        for att in merge_plan.attachments:
            headings.append({
                "level": 2,
                "text": att.get("name", "附件"),
            })

    return headings


# Replace generate_merged_docx:

def generate_merged_docx(merge_plan, docs_data,
                         all_images_by_doc, output_path,
                         cover_title="文档合并汇编",
                         skeleton=None) -> str:
    """Generate merged docx with template-driven structure and styles."""
    doc = Document()

    # Apply template styles if available
    if skeleton:
        _apply_template_styles(doc, skeleton)

    # Default font
    style = doc.styles['Normal']
    font = style.font
    font.name = '宋体'
    font.size = Pt(11)
    try:
        style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    except Exception:
        pass

    # Page margins
    if skeleton and skeleton.page_layout:
        for section in doc.sections:
            section.top_margin = skeleton.page_layout.margin_top
            section.bottom_margin = skeleton.page_layout.margin_bottom
            section.left_margin = skeleton.page_layout.margin_left
            section.right_margin = skeleton.page_layout.margin_right
    else:
        for section in doc.sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2.8)
            section.right_margin = Cm(2.8)

    filenames = [d.get("filename", "unknown") for d in docs_data]
    image_lookup = _build_image_lookup(all_images_by_doc)
    inserted_hashes = set()

    # === Cover ===
    _create_cover(doc, len(filenames), filenames, cover_title, skeleton)

    # === TOC ===
    toc_headings = _collect_toc_headings(merge_plan, docs_data)
    _generate_real_toc(doc, toc_headings)

    # === Main Document Sections ===
    if merge_plan.main_sections:
        for section in merge_plan.main_sections:
            heading = section.get("heading", "")
            level = section.get("level", 1)
            paragraphs = section.get("paragraphs", [])
            style_name = section.get("style_name", "Heading 2")

            if not heading:
                continue

            actual_level = min(level + 1, 9)
            _set_heading_style(doc, actual_level, heading)

            # Apply specified style to heading paragraph
            if style_name and skeleton and style_name in [s.name for s in doc.styles]:
                try:
                    doc.paragraphs[-1].style = doc.styles[style_name]
                except Exception:
                    pass

            for p_text in paragraphs:
                if p_text.strip():
                    para = _add_paragraph(doc, p_text.strip())
                    try:
                        para.style = doc.styles['段']
                    except Exception:
                        pass
    else:
        _add_paragraph(doc, "（无主文档内容）")

    # === Attachments ===
    if merge_plan.attachments:
        doc.add_page_break()
        _set_heading_style(doc, 1, "附件")

        for att in merge_plan.attachments:
            name = att.get("name", "附件")
            paragraphs = att.get("paragraphs", [])

            _set_heading_style(doc, 2, name)

            for p_text in paragraphs:
                if p_text.strip():
                    para = _add_paragraph(doc, p_text.strip())
                    try:
                        para.style = doc.styles['段']
                    except Exception:
                        pass

    # Save
    doc.save(output_path)
    return output_path
```

The full file keeps existing helper functions (_set_heading_style, _add_paragraph, _add_image_to_doc, _normalize_for_match, _find_best_paragraph_index, _build_image_lookup, _insert_images_for_paragraphs, _write_paragraphs_with_images, _insert_table, _generate_real_toc) unchanged.

- [ ] **Step 2: Verify merger imports**

Run:
```bash
cd backend && python -c "
from merger import generate_merged_docx, _create_cover, _apply_template_styles
print('generate_merged_docx:', generate_merged_docx)
print('OK')
"
```

Expected: prints function info, "OK".

- [ ] **Step 3: Commit**

```bash
git add backend/merger.py
git commit -m "refactor: merger accepts TemplateSkeleton for style-driven output"
```

Actually, because the merger.py changes are extensive (rewriting the core function and adding style support), let me write the full file.

- [ ] **Step 1: Write the complete refactored merger.py**

Read the current `backend/merger.py`, then write the complete replacement via the Write tool. The file keeps all image/table/image-placement helpers, replaces `_create_cover` (adds skeleton param), adds `_apply_template_styles`, replaces `_collect_toc_headings` (uses merge_plan.toc_headings), and replaces `generate_merged_docx` (main + attachments structure).

- [ ] **Step 2: Verify**

```bash
cd backend && python -c "from merger import generate_merged_docx; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/merger.py
git commit -m "refactor: template-driven docx generation with style inheritance"
```

---

### Task 5: Modify agent.py — Upload Template Tool + New Pipeline

**Files:**
- Modify: `backend/agent.py`

- [ ] **Step 1: Add template_upload tool to TOOLS list**

In `backend/agent.py`, add a new tool definition after `parse_documents` in the TOOLS list:

```python
    {
        "name": "upload_template",
        "description": "将当前已上传文件中的某个文件标记为模板。模板定义输出文档的结构和样式。用户说'以xxx为模板'、'按xxx的格式'时调用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要标记为模板的文件名（需已上传）",
                },
            },
            "required": ["filename"],
        },
    },
```

- [ ] **Step 2: Add template_file to session state**

In `MergeAgent.create_session`, add `"template_file": None` to the session dict.

- [ ] **Step 3: Add upload_template handler in _execute_tool**

Add after `parse_documents` handler:

```python
        elif tool_name == "upload_template":
            filename = tool_input.get("filename", "").strip()
            uploaded = session.get("uploaded_files", [])
            target = None
            for f in uploaded:
                if f["filename"] == filename:
                    target = f
                    break
            if not target:
                return {
                    "data": {"error": f"未找到文件: {filename}，请先上传"},
                    "_sse_events": [],
                }
            session["template_file"] = target
            return {
                "data": {
                    "status": "ok",
                    "template_filename": filename,
                    "message": f"已将 {filename} 设为模板。源文件共 {len(uploaded) - 1} 个。",
                },
                "_sse_events": [],
            }
```

- [ ] **Step 4: Update generate_merged_document to use template-driven pipeline**

Replace the `generate_merged_document` handler to:

```python
        elif tool_name == "generate_merged_document":
            parsed = session.get("parsed_docs")
            if not parsed or len(parsed) < 1:
                return {
                    "data": {"error": "请先解析文档（parse_documents）"},
                    "_sse_events": [],
                }

            template_file = session.get("template_file")
            skeleton = None

            # Phase 1: Load template skeleton
            if template_file:
                tpl_path = os.path.join(
                    UPLOAD_DIR,
                    f"{template_file['file_id']}_{template_file['filename']}"
                )
                if os.path.exists(tpl_path):
                    from template_parser import parse_template
                    skeleton = parse_template(tpl_path)
                    emit("progress", {
                        "stage": "template",
                        "message": f"已加载模板: {template_file['filename']}",
                        "percent": 15,
                    })
                else:
                    emit("progress", {
                        "stage": "template",
                        "message": "模板文件不存在，使用内置标准格式",
                        "percent": 15,
                    })

            if not skeleton:
                from builtin_template import get_builtin_template
                skeleton = get_builtin_template()
                emit("progress", {
                    "stage": "template",
                    "message": "使用内置标准格式",
                    "percent": 15,
                })

            # Phase 2: Template-driven analysis
            from analyzer import analyze_documents
            from merger import generate_merged_docx

            docs_data = [d.to_dict() for d in parsed]
            aq = asyncio.Queue()

            def on_progress(event_type: str, data: dict):
                try:
                    aq.put_nowait((event_type, data))
                except Exception:
                    pass

            loop = asyncio.get_event_loop()

            async def run_analysis():
                return await loop.run_in_executor(
                    None, analyze_documents, docs_data, skeleton, on_progress,
                )

            analysis_task = asyncio.ensure_future(run_analysis())

            # Stream progress while analysis runs
            while not analysis_task.done():
                try:
                    event_type, data = await asyncio.wait_for(aq.get(), timeout=0.1)
                    if event_type == "progress":
                        emit("progress", data)
                except asyncio.TimeoutError:
                    pass

            merge_plan = await analysis_task
            session["merge_plan"] = merge_plan

            m = merge_plan.summary
            emit("progress", {
                "stage": "analyzed",
                "message": "分析完成",
                "percent": 65,
            })

            # Phase 3: Generate DOCX
            user_filename = tool_input.get("filename", "").strip()
            if not user_filename:
                user_filename = merge_plan.cover_title

            if user_filename:
                safe = "".join(c for c in user_filename if c.isalnum() or c in "._-（）()【】[]")
                output_filename = f"{safe}.docx" if safe else f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            else:
                output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

            output_path = os.path.join(UPLOAD_DIR, output_filename)
            cover_title = merge_plan.cover_title or user_filename or "文档合并汇编"

            await loop.run_in_executor(
                None,
                generate_merged_docx,
                merge_plan,
                docs_data,
                session.get("all_images", {}),
                output_path,
                cover_title,
                skeleton,
            )

            session["output_path"] = output_path
            session["output_filename"] = output_filename
            session["status"] = "done"

            emit("progress", {"stage": "done", "message": "合并完成！", "percent": 100})
            emit("result", {
                "download_url": f"/api/download/session/{session['id']}",
                "filename": output_filename,
                "summary": m,
                "message": (
                    f"合并文档已生成！\n\n"
                    f"主文档: {m.get('main_sections', 0)}个章节\n"
                    f"附件: {m.get('attachments', 0)}个\n"
                    f"来源文档: {m.get('total_docs', 0)}份"
                ),
            })

            return {"data": {"output_file": output_filename}, "_sse_events": sse_events}
```

- [ ] **Step 5: Update SYSTEM_PROMPT to mention template workflow**

Change the SYSTEM_PROMPT's section about common scenarios to add:

```
- 用户说"以xxx为模板"、"按xxx的格式合并" → 先调用 upload_template 标记模板，再继续合并流程
- 用户上传了模板文件但没有明确说 → 询问用户是否要以某文件为模板
```

- [ ] **Step 6: Verify agent imports**

```bash
cd backend && python -c "from agent import agent; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add backend/agent.py
git commit -m "feat: add upload_template tool and template-driven merge pipeline"
```

---

### Task 6: Frontend — Template Upload UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ChatInput.jsx`

- [ ] **Step 1: Add template file state in App.jsx**

Add state after `uploadedFiles`:

```javascript
const [templateFile, setTemplateFile] = useState(null)
```

- [ ] **Step 2: Add handleUploadTemplate in App.jsx**

After `handleUpload`, add:

```javascript
const handleUploadTemplate = useCallback(async (fileData) => {
    if (!sessionId) { alert('会话尚未建立，请稍后再试'); return }
    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: fileData }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '上传失败') }
      const data = await res.json()

      // Mark as template in session
      const tplName = fileData[0].filename
      setTemplateFile(tplName)
      addMessage({
        role: 'user',
        content: `上传模板：${tplName}`,
        files: fileData.map(f => ({ filename: f.filename, size: f.size, isTemplate: true }))
      })
      addMessage({
        role: 'agent',
        content: `已接收模板 **${tplName}**。当前共 ${data.total_files} 个文件。\n\n现在可以上传源文件并描述合并需求。`
      })
    } catch (err) {
      addMessage({ role: 'agent', content: `❌ 上传模板失败：${err.message}` })
    }
  }, [sessionId, addMessage])
```

- [ ] **Step 3: Pass template props to ChatInput and ChatWindow**

In `App.jsx`, pass `templateFile` to ChatInput:
```jsx
<ChatInput
  onSend={handleSend}
  onUpload={handleUpload}
  onUploadTemplate={handleUploadTemplate}
  disabled={isProcessing || !sessionId}
  hasFiles={uploadedFiles.length > 0}
  templateFile={templateFile}
/>
```

- [ ] **Step 4: Add template upload button in ChatInput.jsx**

Add a second button next to the existing file upload button:

```jsx
{/* Template upload button */}
<button
  onClick={() => templateInputRef.current?.click()}
  disabled={disabled}
  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors flex-shrink-0 disabled:opacity-40"
  title="上传模板（可选）"
>
  <FileStack className="w-[16px] h-[16px] text-gray-400" strokeWidth={1.5} />
  <span className="text-[11px] text-gray-400 hidden sm:inline">模板</span>
</button>

<input
  ref={templateInputRef}
  type="file"
  accept=".docx"
  onChange={handleTemplateChange}
  className="hidden"
/>
```

Add the import at top:
```javascript
import { Plus, ArrowUp, Loader2, FileStack } from 'lucide-react'
```

Add `templateInputRef` and `handleTemplateChange`:

```javascript
const templateInputRef = useRef(null)

const handleTemplateChange = useCallback(async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setUploading(true)
    try {
      const fileData = await Promise.all(
        files.map(async (file) => {
          const buf = await file.arrayBuffer()
          const bytes = new Uint8Array(buf)
          let binary = ''
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i])
          }
          return { filename: file.name, content: btoa(binary), size: file.size }
        })
      )
      onUploadTemplate(fileData)
    } catch (err) {
      alert(`模板上传失败: ${err.message}`)
    } finally {
      setUploading(false)
      if (templateInputRef.current) templateInputRef.current.value = ''
    }
  }, [onUploadTemplate])
```

Destructure the new prop:
```javascript
export default function ChatInput({ onSend, onUpload, onUploadTemplate, disabled, hasFiles, templateFile })
```

- [ ] **Step 5: Show template indicator when template is set**

After the existing `hasFiles` hint at the bottom, add:

```jsx
{templateFile && (
  <div className="text-center mt-1 text-[11px] text-brand">
    📋 模板：{templateFile}
  </div>
)}
```

- [ ] **Step 6: Update TOOL_LABELS in App.jsx**

Add:
```javascript
upload_template: '设置模板',
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/ChatInput.jsx
git commit -m "feat: add template upload UI with visual template indicator"
```

---

### Task 7: main.py — Template API Endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add template-specific upload endpoint**

The existing `/api/chat/{session_id}/upload` endpoint already handles file uploads. The `upload_template` tool in agent.py marks a file as template. No new endpoint is strictly needed — the frontend uploads the template via the same upload endpoint and the agent marks it.

But we should add an explicit endpoint for clarity:

```python
@app.post("/api/chat/{session_id}/template")
async def chat_set_template(session_id: str, req: Request):
    """Mark an uploaded file as the merge template."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须为JSON格式")

    filename = body.get("filename", "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="请指定模板文件名")

    uploaded = sess.get("uploaded_files", [])
    target = None
    for f in uploaded:
        if f["filename"] == filename:
            target = f
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    sess["template_file"] = target
    return {"status": "ok", "template": filename}
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: add template selection API endpoint"
```

---

### Task 8: End-to-End Integration Test

- [ ] **Step 1: Start backend and verify template parsing**

```bash
cd backend && python -c "
from template_parser import parse_template
from builtin_template import get_builtin_template

# Test with actual template
import os
tpl = '../QSCW-V-C054-PD-2025 运行工岗位操作规程.docx'
if os.path.exists(tpl):
    skel = parse_template(tpl)
    print(f'Template: {len(skel.styles)} styles, {len(skel.sections)} sections')
    print(f'Cover elements: {[e[\"text\"][:40] for e in skel.cover_elements]}')

# Test builtin
skel2 = get_builtin_template()
print(f'Builtin: {len(skel2.styles)} styles, {len(skel2.sections)} sections')
print('PASS')
"
```

- [ ] **Step 2: Start backend server and test API**

```bash
cd backend && python main.py &
sleep 3
curl -s http://localhost:8000/api/health | python -m json.tool
```

- [ ] **Step 3: Test full pipeline via Python**

Create a test script:

```python
"""Integration test for template-driven merge pipeline."""
import os, sys
sys.path.insert(0, 'backend')

from template_parser import parse_template
from builtin_template import get_builtin_template
from doc_parser import parse_document
from analyzer import analyze_documents

# Use actual source docs
sources = [
    'SCW-V-C034-PD-2025 上位机操作规程.docx',
    'SCW-V-C038-PD-2025三班化验操作规程.docx',
]
docs_data = []
for s in sources:
    if os.path.exists(s):
        parsed = parse_document(s, s)
        docs_data.append(parsed.to_dict())

if docs_data:
    skeleton = get_builtin_template()
    plan = analyze_documents(docs_data, skeleton)
    print(f"Plan: {plan.summary}")
    print(f"Main sections: {len(plan.main_sections)}")
    print(f"Attachments: {len(plan.attachments)}")
    print("PASS")
else:
    print("SKIP: source docs not found")
```

Run:
```bash
cd D:/my_document_integration && python test_integration.py
```

- [ ] **Step 4: Commit any fixes found during testing**

```bash
git add -A && git commit -m "fix: integration test adjustments"
```

---
```

Note: Task 4 (merger.py) requires writing the full file. The Edit tool approach (showing exact old→new replacements for a file with 500+ lines) would make the plan too verbose. During implementation, the merger.py changes follow the structure described in the design doc and use the exact function signatures shown above.
```

- [ ] **Step 2: Verify merger imports**

Run:
```bash
cd backend && python -c "
from merger import generate_merged_docx, _create_cover, _apply_template_styles
print('generate_merged_docx:', generate_merged_docx)
print('OK')
"
```

Expected: prints function info, "OK".

- [ ] **Step 3: Commit**

```bash
git add backend/merger.py
git commit -m "refactor: merger accepts TemplateSkeleton for style-driven output"
```

To be clear: the merger.py changes are to `_create_cover` (add optional `skeleton` parameter), add `_apply_template_styles` function, replace `_collect_toc_headings` to use `merge_plan.toc_headings`, and replace `generate_merged_docx` to output main_sections + attachments instead of Part1/Part2. Existing helper functions stay unchanged.

---

### Task 5: Modify agent.py — Upload Template Tool + New Pipeline

**Files:**
- Modify: `backend/agent.py`

- [ ] **Step 1: Add `upload_template` tool to TOOLS list**

In `backend/agent.py`, find the TOOLS list. After the `parse_documents` tool entry and before `get_document_detail`, insert:

```python
    {
        "name": "upload_template",
        "description": "将当前已上传文件中的某个文件标记为模板。模板定义输出文档的结构和样式。用户说'以xxx为模板'、'按xxx的格式'时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要标记为模板的文件名（需已上传）",
                },
            },
            "required": ["filename"],
        },
    },
```

- [ ] **Step 2: Update SYSTEM_PROMPT to document the template workflow**

In SYSTEM_PROMPT, under "常见场景处理", add:

```
- 用户说"以xxx为模板"、"按xxx的格式合并" → 先调用 upload_template 标记模板文件
- 用户上传了文件且说了类似"这个当模板" → 调用 upload_template
```

- [ ] **Step 3: Add template_file to session state**

In `create_session`, add to the session dict:

```python
"template_file": None,
```

- [ ] **Step 4: Add upload_template handler in _execute_tool**

Add a new elif branch before the fallback else:

```python
        elif tool_name == "upload_template":
            filename = tool_input.get("filename", "").strip()
            uploaded = session.get("uploaded_files", [])
            target = None
            for f in uploaded:
                if f["filename"] == filename:
                    target = f
                    break
            if not target:
                return {
                    "data": {"error": f"未找到文件: {filename}，请先上传"},
                    "_sse_events": [],
                }
            session["template_file"] = target
            return {
                "data": {
                    "status": "ok",
                    "template_filename": filename,
                    "message": f"已将「{filename}」设为模板",
                },
                "_sse_events": [],
            }
```

- [ ] **Step 5: Modify generate_merged_document to use template-driven pipeline**

Replace the current `generate_merged_document` branch in `_execute_tool`. The key change is: load template skeleton, call new `analyze_documents(docs_data, skeleton, on_progress)`, pass skeleton to `generate_merged_docx`.

Replace the `elif tool_name == "generate_merged_document":` block with:

```python
        elif tool_name == "generate_merged_document":
            parsed = session.get("parsed_docs")
            if not parsed:
                return {
                    "data": {"error": "请先解析文档（parse_documents）"},
                    "_sse_events": [],
                }

            template_file = session.get("template_file")
            skeleton = None

            if template_file:
                tpl_path = os.path.join(
                    UPLOAD_DIR,
                    f"{template_file['file_id']}_{template_file['filename']}"
                )
                if os.path.exists(tpl_path):
                    from template_parser import parse_template
                    try:
                        skeleton = parse_template(tpl_path)
                        emit("progress", {
                            "stage": "template",
                            "message": f"已加载模板: {template_file['filename']}",
                            "percent": 15,
                        })
                    except Exception as e:
                        logger.warning("Template parse failed: %s", e)
                        emit("progress", {
                            "stage": "template",
                            "message": "模板解析失败，使用内置标准格式",
                            "percent": 15,
                        })

            if not skeleton:
                from builtin_template import get_builtin_template
                skeleton = get_builtin_template()
                emit("progress", {
                    "stage": "template",
                    "message": "使用内置标准格式",
                    "percent": 15,
                })

            from analyzer import analyze_documents
            from merger import generate_merged_docx

            docs_data = [d.to_dict() for d in parsed]
            aq = asyncio.Queue()

            def on_progress(event_type: str, data: dict):
                try:
                    aq.put_nowait((event_type, data))
                except Exception:
                    pass

            loop = asyncio.get_event_loop()

            async def run_analysis():
                return await loop.run_in_executor(
                    None, analyze_documents, docs_data, skeleton, on_progress,
                )

            analysis_task = asyncio.ensure_future(run_analysis())

            while not analysis_task.done():
                try:
                    event_type, data = await asyncio.wait_for(aq.get(), timeout=0.1)
                    if event_type == "progress":
                        emit("progress", data)
                except asyncio.TimeoutError:
                    pass

            merge_plan = await analysis_task
            session["merge_plan"] = merge_plan

            m = merge_plan.summary
            emit("progress", {
                "stage": "analyzed",
                "message": "分析完成",
                "percent": 65,
            })

            user_filename = tool_input.get("filename", "").strip()
            if not user_filename:
                user_filename = merge_plan.cover_title

            if user_filename:
                safe = "".join(c for c in user_filename if c.isalnum() or c in "._-（）()【】[]")
                output_filename = f"{safe}.docx" if safe else f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            else:
                output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

            output_path = os.path.join(UPLOAD_DIR, output_filename)
            cover_title = merge_plan.cover_title or "文档合并汇编"

            await loop.run_in_executor(
                None,
                generate_merged_docx,
                merge_plan,
                docs_data,
                session.get("all_images", {}),
                output_path,
                cover_title,
                skeleton,
            )

            session["output_path"] = output_path
            session["output_filename"] = output_filename
            session["status"] = "done"

            emit("progress", {"stage": "done", "message": "合并完成！", "percent": 100})
            emit("result", {
                "download_url": f"/api/download/session/{session['id']}",
                "filename": output_filename,
                "summary": m,
                "message": (
                    f"合并文档已生成！\n\n"
                    f"主文档: {m.get('main_sections', 0)}个章节\n"
                    f"附件: {m.get('attachments', 0)}个\n"
                    f"来源文档: {m.get('total_docs', 0)}份"
                ),
            })

            return {"data": {"output_file": output_filename}, "_sse_events": sse_events}
```

- [ ] **Step 6: Update _direct_merge fallback similarly**

Replace the generate_merged_document section in `_direct_merge` to also use the template-driven pipeline (same skeleton loading logic + new analyze_documents call).

- [ ] **Step 7: Commit**

```bash
git add backend/agent.py
git commit -m "feat: add upload_template tool and template-driven merge pipeline in agent"
```

---

### Task 6: Frontend — Template Upload UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/ChatInput.jsx`

- [ ] **Step 1: Add template state and handler in App.jsx**

After `const [uploadedFiles, setUploadedFiles] = useState([])`, add:

```javascript
const [templateFile, setTemplateFile] = useState(null)
```

After `handleUpload`, add:

```javascript
const handleUploadTemplate = useCallback(async (fileData) => {
    if (!sessionId) { alert('会话尚未建立，请稍后再试'); return }
    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: fileData }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '上传失败') }
      const data = await res.json()
      const tplName = fileData[0].filename
      setTemplateFile(tplName)
      addMessage({ role: 'user', content: `上传模板：${tplName}`, files: [{ filename: tplName, size: fileData[0].size, isTemplate: true }] })
      addMessage({
        role: 'agent',
        content: `已接收模板 **${tplName}**。当前共 ${data.total_files} 个文件。\n\n可以继续上传源文件，然后描述合并需求。`
      })
    } catch (err) {
      addMessage({ role: 'agent', content: `❌ 上传模板失败：${err.message}` })
    }
  }, [sessionId, addMessage])
```

- [ ] **Step 2: Add upload_template to TOOL_LABELS**

```javascript
upload_template: '设置模板',
```

- [ ] **Step 3: Pass template props to ChatInput**

```jsx
<ChatInput
  onSend={handleSend}
  onUpload={handleUpload}
  onUploadTemplate={handleUploadTemplate}
  disabled={isProcessing || !sessionId}
  hasFiles={uploadedFiles.length > 0}
  templateFile={templateFile}
/>
```

- [ ] **Step 4: Add template button in ChatInput.jsx**

Add `FileStack` to the lucide import:
```javascript
import { Plus, ArrowUp, Loader2, FileStack } from 'lucide-react'
```

Update the function signature:
```javascript
export default function ChatInput({ onSend, onUpload, onUploadTemplate, disabled, hasFiles, templateFile })
```

Add ref and handler:
```javascript
const templateInputRef = useRef(null)

const handleTemplateChange = useCallback(async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setUploading(true)
    try {
      const fileData = await Promise.all(
        files.map(async (file) => {
          const buf = await file.arrayBuffer()
          const bytes = new Uint8Array(buf)
          let binary = ''
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i])
          }
          return { filename: file.name, content: btoa(binary), size: file.size }
        })
      )
      onUploadTemplate(fileData)
    } catch (err) {
      alert(`模板上传失败: ${err.message}`)
    } finally {
      setUploading(false)
      if (templateInputRef.current) templateInputRef.current.value = ''
    }
  }, [onUploadTemplate])
```

Add template button before the existing Plus button:
```jsx
<button
  onClick={() => templateInputRef.current?.click()}
  disabled={disabled || uploading}
  className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center cursor-pointer transition-colors flex-shrink-0 disabled:opacity-40"
  title="上传模板（可选）"
>
  <FileStack className="w-[16px] h-[16px] text-gray-400" strokeWidth={1.5} />
</button>

<input
  ref={templateInputRef}
  type="file"
  accept=".docx"
  onChange={handleTemplateChange}
  className="hidden"
/>
```

Add template indicator at the bottom:
```jsx
{templateFile && (
  <div className="text-center mt-2 text-[11px] text-brand">
    模板：{templateFile}
  </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/ChatInput.jsx
git commit -m "feat: add template upload UI button and visual indicator"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Start backend and verify template parsing**

```bash
cd backend && python -c "
from template_parser import parse_template
from builtin_template import get_builtin_template
import os

tpl = '../QSCW-V-C054-PD-2025 运行工岗位操作规程.docx'
if os.path.exists(tpl):
    skel = parse_template(tpl)
    print(f'Template loaded: {len(skel.styles)} styles, {len(skel.sections)} sections')
else:
    print('Template file not in expected location, testing built-in only')

skel2 = get_builtin_template()
print(f'Built-in: {len(skel2.styles)} styles, {len(skel2.sections)} sections')
print('PASS')
"
```

- [ ] **Step 2: Start backend and test API health**

```bash
cd backend && python main.py &
sleep 2
curl -s http://localhost:8001/api/health
```

Expected: `{"status":"ok","has_api_key":true}`

- [ ] **Step 3: Test full pipeline with real documents**

```bash
cd backend && python -c "
from doc_parser import parse_document
from analyzer import analyze_documents
from builtin_template import get_builtin_template
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

src = '../SCW-V-C034-PD-2025 上位机操作规程.docx'
if os.path.exists(src):
    parsed = parse_document(src, os.path.basename(src))
    docs_data = [parsed.to_dict()]
    skel = get_builtin_template()
    plan = analyze_documents(docs_data, skel)
    print(f'Plan: main={len(plan.main_sections)}, attach={len(plan.attachments)}')
    print(f'Cover: {plan.cover_title}')
    print('PASS')
else:
    print('SKIP: test doc not found')
"
```

- [ ] **Step 4: Commit any integration fixes**

```bash
git status
# If there are fixes:
git add -A && git commit -m "fix: integration test adjustments for template pipeline"
```

---
