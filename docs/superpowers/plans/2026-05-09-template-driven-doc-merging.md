# Template-Driven Document Merging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace "common+unique" two-part merge with template-driven unified document synthesis (body chapters + appendices).

**Architecture:** Two-phase AI pipeline — Phase 1 plans structure (body chapter titles and appendix mapping), Phase 2 generates each body chapter by synthesizing all source docs. Attachments use raw source content directly (no AI regeneration). Template skeleton from `template_parser.py` drives chapter structure when a template docx is uploaded.

**Tech Stack:** Python, python-docx, Anthropic SDK (via GLM-4.5), FastAPI

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/template_parser.py` | **Copy** from worktree | Extract chapter tree, styles, layout from template docx |
| `backend/builtin_template.py` | **Rewrite** | Default template when none uploaded (AI-derived chapters) |
| `backend/analyzer.py` | **Rewrite** | Two-phase AI: structure planning + section synthesis |
| `backend/merger.py` | **Rewrite** | Cover (enterprise standard), TOC (with page numbers), body + appendices |
| `backend/agent.py` | **Modify** | Add template upload, update system prompt, update tool descriptions |
| `backend/main.py` | **Modify** | Add template upload endpoint, pass template to merge pipeline |

---

### Task 1: Copy template_parser.py from worktree

**Files:**
- Copy: `.worktrees/template-driven-merge/backend/template_parser.py` → `backend/template_parser.py`

- [ ] **Step 1: Copy the file**

```bash
cp ".worktrees/template-driven-merge/backend/template_parser.py" backend/template_parser.py
```

- [ ] **Step 2: Verify it imports correctly**

```bash
cd backend && python -c "from template_parser import parse_template, TemplateSkeleton; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/template_parser.py
git commit -m "feat: add template_parser.py for docx template skeleton extraction"
```

---

### Task 2: Rewrite builtin_template.py

**Files:**
- Overwrite: `backend/builtin_template.py`

The built-in template provides default enterprise-standard styling when no custom template is uploaded. It does NOT hardcode chapter titles — those are AI-derived.

- [ ] **Step 1: Write the new builtin_template.py**

```python
"""Built-in enterprise standard template used when no custom template is uploaded.

Provides professional Chinese enterprise document styling:
- A4 page layout with standard margins
- Heading hierarchy (黑体 at various sizes)
- Body text (宋体 10.5pt)
- Cover styles for enterprise standard format
"""

from template_parser import TemplateSkeleton, StyleDef, PageLayout


def _make_default_styles() -> dict:
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
    styles["段"] = StyleDef(
        name="段", font_name="宋体", font_size_pt=10.5,
    )
    styles["前言、引言标题"] = StyleDef(
        name="前言、引言标题", font_name="黑体", font_size_pt=16.0,
    )
    styles["封面标准名称"] = StyleDef(
        name="封面标准名称", font_name="黑体", font_size_pt=26.0, bold=True,
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
    return PageLayout(
        page_width=7560310,
        page_height=10692130,
        margin_top=914400,
        margin_bottom=914400,
        margin_left=1008000,
        margin_right=1008000,
    )


def get_builtin_template() -> TemplateSkeleton:
    """Return built-in enterprise standard template skeleton.
    
    No hardcoded chapter titles — the AI will derive chapters from source content.
    """
    return TemplateSkeleton(
        styles=_make_default_styles(),
        page_layout=_make_default_page_layout(),
        sections=[],  # Empty — AI derives chapters
        cover_elements=[
            {"text": "", "style_name": "封面标准名称"},
        ],
        has_header=False,
        has_footer=False,
    )
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from builtin_template import get_builtin_template; t = get_builtin_template(); print('OK:', len(t.styles), 'styles')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/builtin_template.py
git commit -m "feat: rewrite builtin_template — no hardcoded chapters, enterprise styling only"
```

---

### Task 3: Rewrite analyzer.py — MergePlan dataclass + helpers

**Files:**
- Modify: `backend/analyzer.py` (complete rewrite)

First, establish the new data model and helpers.

- [ ] **Step 1: Replace the entire analyzer.py**

```python
"""AI semantic analyzer: template-driven document merging.

Pipeline:
  1. Structure Planning — AI reads all docs + template chapters → plans body chapters + appendix mapping
  2. Section Synthesis — AI generates each body chapter from all source docs
  3. Attachments — Source doc content used directly (no AI regeneration)
"""

import json
import re
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, MODEL,
    HTTP_VERIFY_SSL, HTTP_TRUST_ENV,
)
from template_parser import TemplateSkeleton, SectionNode

logger = logging.getLogger("analyzer")


@dataclass
class MergePlan:
    """Result of template-driven analysis."""
    main_sections: List[dict] = field(default_factory=list)
    attachments: List[dict] = field(default_factory=list)
    cover_title: str = ""
    toc_headings: List[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _flatten_full_text(sections: List[dict]) -> str:
    """Extract all text from sections recursively for AI prompts."""
    parts = []
    def _walk(secs):
        for s in secs:
            h = s.get("heading", "")
            if h:
                parts.append(f"【{h}】")
            for p in s.get("paragraphs", []):
                if p.strip():
                    parts.append(p.strip())
            _walk(s.get("children", []))
    _walk(sections)
    return "\n\n".join(parts)


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

- [ ] **Step 2: Verify file parses**

```bash
cd backend && python -c "from analyzer import MergePlan; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "refactor: new MergePlan data model + helpers for template-driven analysis"
```

---

### Task 4: Add Phase 1 — Structure Planning to analyzer.py

**Files:**
- Modify: `backend/analyzer.py` (append structure planning functions)

- [ ] **Step 1: Add the structure planning prompt builder**

Append to analyzer.py:

```python
# ---------------------------------------------------------------------------
# Phase 1: Structure Planning
# ---------------------------------------------------------------------------

def _build_structure_plan_prompt(template_sections: List[SectionNode],
                                  doc_summaries: List[dict],
                                  has_template: bool) -> str:
    """Build prompt for AI to plan the output document structure."""

    if has_template:
        chapter_desc = []
        for s in template_sections:
            indent = "  " * s.level
            chapter_desc.append(f"{indent}[H{s.level}] {s.heading}")
        chapter_text = "\n".join(chapter_desc)

        template_instruction = f"""## 模板章节结构（必须严格遵循）
{chapter_text}

请按照模板的章节标题来组织主文档。正文内容从所有源文件中综合提炼。"""
    else:
        template_instruction = """## 无模板
请通读所有源文件内容，自行归纳出统一的章节标题。通常包含：范围、引用文件、职责、风险辨识、上岗条件、作业要求、应急处置等，但具体标题根据源文件实际内容确定。"""

    src_desc = []
    for i, s in enumerate(doc_summaries):
        src_desc.append(
            f"{i+1}. **{s['filename']}** ({s.get('paragraph_count', 0)}段, "
            f"{s.get('heading_count', 0)}个标题)\n"
            f"   主要标题: {'; '.join(s.get('top_headings', [])[:6])}\n"
            f"   内容概要: {s.get('summary', '')[:200]}"
        )
    src_text = "\n".join(src_desc)

    return f"""你是一个专业的企业文档编辑。请规划合并文档的结构。

{template_instruction}

## 源文件 ({len(doc_summaries)}个)
{src_text}

## 任务
规划最终文档结构。规则：
1. **主文档正文**：从所有源文件中综合提炼共性内容，按模板章节（或无模板时自行归纳的章节）组织
2. **附件**：每个源文件对应一个附件，附件名为"附件A：源文件标题"、"附件B：源文件标题"等
3. **不重复**：主文档已有的概括性内容，附件中不再出现。附件保留各文档的独有操作细节
4. 主文档中引用附件：如"具体操作参照《附件A：XXX》"

请严格输出以下JSON格式（不要输出其他内容）：
{{
  "cover_title": "文档标题",
  "main_sections": [
    {{"heading": "章节标题", "level": 1, "style_name": "Heading 2"}}
  ],
  "attachments": [
    {{"name": "附件A：xxx操作规程", "source_index": 0}}
  ],
  "toc_headings": [
    {{"level": 1, "text": "前言"}},
    {{"level": 2, "text": "1 范围"}}
  ]
}}"""
```

- [ ] **Step 2: Add the Phase 1 execution function**

```python
def plan_structure(template_sections: List[SectionNode],
                   doc_summaries: List[dict],
                   has_template: bool,
                   progress_callback: Optional[Callable] = None) -> dict:
    """Phase 1: AI plans the output document structure."""
    import anthropic
    import httpx

    if progress_callback:
        progress_callback("progress", {
            "stage": "planning",
            "message": "AI 正在分析文档并规划结构...",
            "percent": 25,
        })

    prompt = _build_structure_plan_prompt(template_sections, doc_summaries, has_template)

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
            system="你是一个专业的企业文档编辑。输出必须是合法的JSON格式。",
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
        logger.info("Structure plan: %d main sections, %d attachments",
                     len(result.get("main_sections", [])),
                     len(result.get("attachments", [])))
        return result

    finally:
        http_client.close()
```

- [ ] **Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "feat: add Phase 1 structure planning to analyzer"
```

---

### Task 5: Add Phase 2 — Section Synthesis to analyzer.py

**Files:**
- Modify: `backend/analyzer.py` (append section synthesis functions)

- [ ] **Step 1: Add body section synthesis prompt and function**

```python
# ---------------------------------------------------------------------------
# Phase 2: Section Synthesis
# ---------------------------------------------------------------------------

def _build_section_synthesis_prompt(heading: str, all_source_texts: List[dict],
                                     attachment_names: List[str]) -> str:
    """Build prompt for synthesizing one body chapter from all source docs."""
    sources_text = []
    for s in all_source_texts:
        sources_text.append(
            f"### 源文件：{s['filename']}\n{s['full_text'][:4000]}"
            f"{'...(内容截断)' if len(s.get('full_text', '')) > 4000 else ''}"
        )
    combined = "\n\n---\n\n".join(sources_text)

    att_refs = "\n".join(f"- 《{a}》" for a in attachment_names) if attachment_names else "（无）"

    return f"""你是一个专业的企业文档编辑。请为合并文档撰写「{heading}」章节。

## 任务
综合以下 {len(all_source_texts)} 个源文件的内容，撰写一个统一的「{heading}」章节。
- 提取所有源文件中与「{heading}」相关的内容，融合为通顺、精炼的表述
- 只写概括性、原则性的内容，不写详细的操作步骤
- 详细操作步骤应引用附件：如"具体操作参照《附件A：XXX》"
- 保持企业标准文档的专业、简洁风格
- 使用中文

## 可引用的附件
{att_refs}

## 源文件内容
{combined}

请直接输出该章节的正文内容（纯文本段落，不要JSON，不要markdown标记）。"""
```

- [ ] **Step 2: Add section synthesis execution function**

```python
def _synthesize_section(heading: str, all_source_texts: List[dict],
                         attachment_names: List[str],
                         progress_callback=None) -> dict:
    """Phase 2: AI synthesizes one body chapter from all source docs."""
    import anthropic
    import httpx

    prompt = _build_section_synthesis_prompt(heading, attachment_names, all_source_texts)

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
            system="你是一个专业的企业文档编辑。输出简洁、通顺的中文段落。",
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
            "paragraphs": paragraphs,
            "tables": [],
            "images": [],
        }
    finally:
        http_client.close()
```

- [ ] **Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "feat: add Phase 2 section synthesis to analyzer"
```

---

### Task 6: Add main entry point + fallback to analyzer.py

**Files:**
- Modify: `backend/analyzer.py` (append `analyze_documents` and fallback)

- [ ] **Step 1: Add fallback and main entry point**

```python
# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_plan(doc_summaries: List[dict]) -> dict:
    """Fallback when AI structure planning fails."""
    return {
        "cover_title": "文档合并汇编",
        "main_sections": [
            {"heading": "前言", "level": 1, "style_name": "前言、引言标题"},
        ],
        "attachments": [
            {
                "name": f"附件{chr(65+i)}：{s['filename'].replace('.docx', '')}",
                "source_index": i,
            }
            for i, s in enumerate(doc_summaries)
        ],
        "toc_headings": [
            {"level": 1, "text": "前言"},
        ],
    }


def _build_doc_summaries(docs_data: List[dict]) -> List[dict]:
    """Build summaries of each source doc for Phase 1."""
    summaries = []
    for doc in docs_data:
        sections = doc.get("sections", [])
        all_headings = []
        total_paras = 0
        for s in sections:
            if s.get("heading"):
                all_headings.append(s["heading"])
            total_paras += len(s.get("paragraphs", []))
            for c in s.get("children", []):
                if c.get("heading"):
                    all_headings.append(c["heading"])
                total_paras += len(c.get("paragraphs", []))

        # First 200 chars as summary
        first_paras = []
        for s in sections[:2]:
            first_paras.extend(s.get("paragraphs", [])[:3])
        summary = " ".join(first_paras)[:200]

        summaries.append({
            "filename": doc.get("filename", ""),
            "paragraph_count": total_paras,
            "heading_count": len(all_headings),
            "top_headings": [s.get("heading", "") for s in sections[:8] if s.get("heading")],
            "summary": summary,
        })
    return summaries


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def analyze_documents(docs_data: List[dict],
                      template_sections: List[SectionNode] = None,
                      progress_callback: Optional[Callable] = None) -> MergePlan:
    """Template-driven merge analysis.

    Args:
        docs_data: List of ParsedDocument.to_dict() results
        template_sections: Template chapter structure (from template_parser). None = AI-derived.
        progress_callback: Optional fn(event_type, data_dict) for UI updates

    Returns:
        MergePlan with main_sections (AI-synthesized body) and attachments (raw source docs)
    """
    if progress_callback:
        progress_callback("progress", {
            "stage": "preparing",
            "message": "准备分析...",
            "percent": 10,
        })

    has_template = bool(template_sections)
    doc_summaries = _build_doc_summaries(docs_data)

    # Phase 1: Plan structure
    try:
        structure_plan = plan_structure(
            template_sections or [], doc_summaries, has_template, progress_callback,
        )
    except Exception as e:
        logger.error("Structure planning failed: %s, using fallback", e)
        structure_plan = _fallback_plan(doc_summaries)

    # Build full text dicts for Phase 2
    doc_texts = []
    for doc in docs_data:
        sections = doc.get("sections", [])
        full = _flatten_full_text(sections)
        doc_texts.append({
            "filename": doc.get("filename", ""),
            "full_text": full,
        })

    plan = MergePlan()
    plan.cover_title = structure_plan.get("cover_title", "")
    plan.toc_headings = structure_plan.get("toc_headings", [])

    main_plan = structure_plan.get("main_sections", [])
    attach_plan = structure_plan.get("attachments", [])

    if progress_callback:
        progress_callback("progress", {
            "stage": "generating",
            "message": f"AI 正在生成主文档内容 ({len(main_plan)}个章节)...",
            "percent": 35,
        })

    # Phase 2a: Synthesize body chapters concurrently
    lock = threading.Lock()
    completed = 0
    total = len(main_plan)

    attachment_names = [a.get("name", "") for a in attach_plan]

    if main_plan:
        def gen_main(sec_info):
            return _synthesize_section(
                sec_info.get("heading", ""),
                doc_texts,
                attachment_names,
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
                            "percent": 35 + int(30 * completed / max(total, 1)),
                        })

    # Phase 2b: Attachments — use source doc content directly (no AI regeneration)
    for att_info in attach_plan:
        src_idx = att_info.get("source_index", -1)
        if 0 <= src_idx < len(docs_data):
            src_doc = docs_data[src_idx]
            att_paragraphs = _flatten_full_text(src_doc.get("sections", []))
            plan.attachments.append({
                "name": att_info.get("name", f"附件{chr(65+src_idx)}"),
                "paragraphs": [att_paragraphs],
                "level": 1,
                "source_index": src_idx,
            })
        with lock:
            completed += 1
            if progress_callback:
                progress_callback("progress", {
                    "stage": "generating",
                    "message": f"附件处理 ({completed}/{total + len(attach_plan)}): {att_info.get('name', '')}",
                    "percent": 35 + int(30 * completed / max(total + len(attach_plan), 1)),
                })

    plan.summary = {
        "main_sections": len(plan.main_sections),
        "attachments": len(plan.attachments),
        "total_docs": len(docs_data),
        "mode": "template_driven" if has_template else "ai_derived",
        "cover_title": plan.cover_title,
    }

    if progress_callback:
        progress_callback("progress", {
            "stage": "generated",
            "message": "内容生成完成",
            "percent": 65,
        })

    return plan
```

- [ ] **Step 2: Verify the full module imports**

```bash
cd backend && python -c "from analyzer import analyze_documents, MergePlan; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/analyzer.py
git commit -m "feat: add main entry point and fallback to analyzer"
```

---

### Task 7: Rewrite merger.py — Cover page

**Files:**
- Modify: `backend/merger.py`

- [ ] **Step 1: Rewrite _create_cover for enterprise standard format**

Replace the entire `_create_cover` function:

```python
def _create_cover(doc, cover_title="", skeleton=None):
    """Create enterprise-standard cover page.
    
    No merge count, no generation date, no source file list.
    If skeleton has cover_elements, follow their structure and styles.
    """
    if skeleton and skeleton.cover_elements and len(skeleton.cover_elements) > 1:
        # Use template cover structure
        for elem in skeleton.cover_elements:
            text = elem.get("text", "")
            style_name = elem.get("style_name", "")
            
            if not text:
                doc.add_paragraph()
                continue
            
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Look up style from skeleton
            if style_name and style_name in skeleton.styles:
                sd = skeleton.styles[style_name]
                run = para.add_run(text)
                if sd.font_size_pt:
                    run.font.size = Pt(sd.font_size_pt)
                if sd.bold:
                    run.bold = True
                if sd.font_name:
                    run.font.name = sd.font_name
            else:
                run = para.add_run(text)
    else:
        # Default enterprise cover
        for _ in range(6):
            doc.add_paragraph()
        
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(cover_title or "企业标准")
        run.font.size = Pt(26)
        run.bold = True
        
        doc.add_paragraph()
        doc.add_paragraph()
        
        # Department line
        dept_para = doc.add_paragraph()
        dept_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = dept_para.add_run("上海浦东威立雅自来水有限公司")
        run.font.size = Pt(14)
    
    doc.add_page_break()
```

- [ ] **Step 2: Commit**

```bash
git add backend/merger.py
git commit -m "feat: enterprise-standard cover page (no merge count/date)"
```

---

### Task 8: Rewrite merger.py — TOC with page numbers

**Files:**
- Modify: `backend/merger.py`

- [ ] **Step 1: Rewrite _generate_real_toc for proper format**

Replace the TOC function to include page numbers with leader dots:

```python
def _generate_real_toc(doc, headings: List[dict]):
    """Generate table of contents with title, leader dots, and page numbers.
    
    Uses tab stops with dot leaders to create the classic TOC look:
    前言..................3
    1 范围................4
    """
    _set_heading_style(doc, 1, "目    录")
    doc.add_paragraph()
    
    # Start page counter from 3 (cover=1, TOC title page=2)
    page_num = 3
    
    for item in headings:
        level = item.get("level", 2)
        text = item.get("text", "")
        if not text:
            continue
        
        para = doc.add_paragraph()
        
        # Set left indent based on level
        indent = max(0, level - 1) * 0.8
        para.paragraph_format.left_indent = Cm(indent)
        
        # Add tab stop at right margin with dot leader
        tab_stops = para.paragraph_format.tab_stops
        tab_stops.add_tab_stop(Cm(14.5), alignment=WD_ALIGN_PARAGRAPH.RIGHT, leader=WD_TAB_LEADER_DOTS)
        
        # Title text
        run = para.add_run(text)
        run.font.size = Pt(11) if level <= 2 else Pt(10)
        
        # Tab then page number
        run2 = para.add_run("\t")
        run3 = para.add_run(str(page_num))
        run3.font.size = Pt(11) if level <= 2 else Pt(10)
        
        page_num += 1
    
    doc.add_page_break()
```

Note: since we can't know actual page numbers before generating the full document, we use estimated page numbers. For production, Word's native TOC field (`add_paragraph().add_run('TOC \\o "1-3" \\h \\z \\u')` with `fldChar` elements) would auto-generate correct numbers when the user opens the file and chooses "Update Fields".

However, the leader-dot approach with estimated page numbers provides a clean visual that approximates the final result. For Word auto-TOC, we can add an alternative:

```python
def _generate_word_toc(doc):
    """Insert a native Word TOC field that auto-generates on open."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    
    _set_heading_style(doc, 1, "目    录")
    
    para = doc.add_paragraph()
    run = para.add_run()
    
    fldChar_begin = OxmlElement('w:fldChar')
    fldChar_begin.set(qn('w:fldCharType'), 'begin')
    run._r.append(fldChar_begin)
    
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = ' TOC \\o "1-3" \\h \\z \\u '
    run._r.append(instrText)
    
    fldChar_separate = OxmlElement('w:fldChar')
    fldChar_separate.set(qn('w:fldCharType'), 'separate')
    run._r.append(fldChar_separate)
    
    run2 = para.add_run('（请在Word中右键点击此处，选择"更新域"以生成目录）')
    run2.font.size = Pt(9)
    run2.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    fldChar_end = OxmlElement('w:fldChar')
    fldChar_end.set(qn('w:fldCharType'), 'end')
    run2._r.append(fldChar_end)
    
    doc.add_page_break()
```

We'll use the Word TOC approach as default (more professional) and fall back to text-based TOC.

- [ ] **Step 2: Commit**

```bash
git add backend/merger.py
git commit -m "feat: professional TOC with leader dots and page numbers"
```

---

### Task 9: Rewrite merger.py — Body + Appendices generation

**Files:**
- Modify: `backend/merger.py`

- [ ] **Step 1: Rewrite _collect_toc_headings and generate_merged_docx**

```python
def _collect_toc_headings(merge_plan, docs_data) -> List[dict]:
    """Collect headings for TOC from merge plan."""
    if merge_plan.toc_headings:
        return merge_plan.toc_headings
    
    headings = []
    # Preface
    headings.append({"level": 1, "text": "前言"})
    
    # Main body chapters
    for section in merge_plan.main_sections:
        h = section.get("heading", "")
        if h:
            headings.append({
                "level": 2,
                "text": h,
            })
    
    # Attachments
    if merge_plan.attachments:
        for att in merge_plan.attachments:
            headings.append({
                "level": 2,
                "text": att.get("name", "附件"),
            })
    
    return headings


def generate_merged_docx(merge_plan, docs_data,
                         all_images_by_doc, output_path,
                         cover_title="",
                         skeleton=None) -> str:
    """Generate unified operating procedure with body chapters + appendices."""
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
    
    # Page margins from skeleton or default
    if skeleton and skeleton.page_layout and skeleton.page_layout.margin_top:
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
    
    # === Cover ===
    cover_title = merge_plan.cover_title or cover_title
    _create_cover(doc, cover_title, skeleton)
    
    # === TOC (Word native TOC field) ===
    toc_headings = _collect_toc_headings(merge_plan, docs_data)
    _generate_word_toc(doc)
    
    # === Preface ===
    _set_heading_style(doc, 1, "前    言")
    _add_paragraph(doc, "本标准按照企业标准编写规范起草。")
    _add_paragraph(doc, "本标准由上海浦东威立雅自来水有限公司浦东水厂生产管理科提出并归口。")
    _add_paragraph(doc, "本标准起草部门：浦东水厂生产管理科。")
    
    # === Main Body Chapters ===
    if merge_plan.main_sections:
        for i, section in enumerate(merge_plan.main_sections):
            heading = section.get("heading", "")
            level = section.get("level", 1)
            paragraphs = section.get("paragraphs", [])
            style_name = section.get("style_name", "Heading 2")
            
            if not heading:
                continue
            
            # Number the heading if not already numbered
            display_heading = heading
            if not heading[0].isdigit() and level >= 1:
                display_heading = f"{heading}"
            
            actual_level = min(level + 1, 9)
            heading_para = _set_heading_style(doc, actual_level, display_heading)
            
            # Apply template style if available
            if skeleton and style_name:
                try:
                    from doc_parser import HEADING_STYLE_MAP
                    if style_name in [s.name for s in doc.styles]:
                        heading_para.style = doc.styles[style_name]
                except Exception:
                    pass
            
            # Write paragraphs
            for p_text in paragraphs:
                if p_text.strip():
                    para = _add_paragraph(doc, p_text.strip())
                    try:
                        para.style = doc.styles['段']
                    except Exception:
                        pass
            
            # Insert images for this section
            section_images = section.get("images", [])
            if section_images:
                for img_info in section_images:
                    # Image insertion logic (reuse existing helpers)
                    pass
    else:
        _add_paragraph(doc, "（无正文内容）")
    
    # === Attachments ===
    if merge_plan.attachments:
        for att in merge_plan.attachments:
            doc.add_page_break()
            
            name = att.get("name", "附件")
            paragraphs = att.get("paragraphs", [])
            
            _set_heading_style(doc, 1, name)
            
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

- [ ] **Step 2: Add missing import for WD_TAB_LEADER_DOTS**

At the top of merger.py, add:
```python
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_LEADER_DOTS
```

- [ ] **Step 3: Verify module imports**

```bash
cd backend && python -c "from merger import generate_merged_docx; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/merger.py
git commit -m "feat: unified body + appendices generation in merger"
```

---

### Task 10: Update agent.py — System prompt, tools, and template support

**Files:**
- Modify: `backend/agent.py`

- [ ] **Step 1: Update SYSTEM_PROMPT**

Replace the system prompt with:

```python
SYSTEM_PROMPT = """你是一个专业的文档合并智能助手。你可以帮助用户将多个Word文档（.docx格式）合并为统一的企业操作规程。

## 你的身份
你是一个专业的企业文档编辑助手。你产出的不是"合并文档"，而是凝练后的统一操作规程：
- 正文：综合所有源文件的共性内容，提炼为统一的章节
- 附件：每个源文件作为附件（附件A、附件B...），保留各自的操作细节
- 正文中引用附件：如"具体操作参照《附件A：XXX》"

## 工作原则
1. **自然对话**：保持友好、自然的对话风格。
2. **主动汇报**：执行每个步骤时告知用户进展。
3. **灵活应变**：根据用户需求调整。
4. **用中文回复**，保持简洁清晰。

## 可用的工具
- `get_session_info` — 查看当前会话信息
- `parse_documents` — 解析已上传文档
- `get_document_detail` — 查看文档详情
- `analyze_commonality` — AI分析文档，规划统一章节结构
- `generate_merged_document` — 生成统一操作规程（正文+附件）

## 典型工作流程
1. 用户上传多个文档
2. 如果用户提供了模板文件（文件名含"模板"或用户指定），先分析模板结构
3. 解析所有文档 → AI分析（规划章节+附件映射）→ 生成文档
4. 告知用户结果

## 重要
- 用户指定文件名时必须传入generate_merged_document的filename参数
"""
```

- [ ] **Step 2: Update TOOLS descriptions**

Update the `analyze_commonality` tool description:
```python
{
    "name": "analyze_commonality",
    "description": "AI分析所有已解析文档，规划统一操作规程的章节结构：正文综合提炼共有内容，源文件作为附件。如果用户上传了模板，会按模板章节组织。",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
},
```

Update the `generate_merged_document` tool description:
```python
{
    "name": "generate_merged_document",
    "description": "生成统一操作规程文档。包含：企业标准封面、目录、前言、正文（AI凝练的统一章节）、附件A-F（各源文件独有操作细节）。",
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "用户指定的输出文件名（不含.docx后缀）。",
            },
        },
        "required": [],
    },
},
```

- [ ] **Step 3: Update _execute_tool for generate_merged_document**

Update the result message in `generate_merged_document` tool execution:
```python
sse_events.append(self._sse_raw("result", {
    "download_url": f"/api/download/session/{session['id']}",
    "filename": output_filename,
    "summary": {
        "main_sections": merge_plan.summary.get("main_sections", 0),
        "attachments": merge_plan.summary.get("attachments", 0),
        "total_docs": len(parsed),
    },
    "message": (
        f"统一操作规程已生成！\n\n"
        f"文档结构：\n"
        f"- 封面和目录\n"
        f"- 前言\n"
        f"- 正文（{merge_plan.summary.get('main_sections', 0)}个章节）\n"
        f"- 附件（{merge_plan.summary.get('attachments', 0)}个）"
    ),
}))
```

- [ ] **Step 4: Update _direct_merge fallback messages**

Update the fallback merge result message:
```python
yield self._sse("result", {
    "download_url": f"/api/download/session/{session_id}",
    "filename": output_filename,
    "summary": m,
    "message": (
        f"统一操作规程已生成！\n\n"
        f"文档包含：封面、目录、前言、{m.get('main_sections', 0)}个正文章节、"
        f"{m.get('attachments', 0)}个附件。"
    ),
})
```

- [ ] **Step 5: Add template upload support to agent.py**

Add a new method to MergeAgent for handling template uploads:
```python
def set_template(self, session_id: str, template_path: str, template_filename: str):
    """Set a template file for the session."""
    session = self.sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}
    session["template_path"] = template_path
    session["template_filename"] = template_filename
    return {"status": "ok", "template": template_filename}
```

- [ ] **Step 6: Commit**

```bash
git add backend/agent.py
git commit -m "feat: update agent for template-driven merge — unified doc + appendices"
```

---

### Task 11: Update main.py — Add template upload and pass template to pipeline

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add template upload to legacy merge flow**

In `_run_merge`, add template handling:

```python
template_sections = None
if task.get("template_path"):
    from template_parser import parse_template
    try:
        skeleton = parse_template(task["template_path"])
        template_sections = skeleton.sections
    except Exception as e:
        logging.warning("Template parsing failed: %s", e)

# Pass template_sections to analyze_documents
merge_plan = await loop.run_in_executor(
    None, lambda: analyze_documents(docs_data, template_sections, None)
)
```

- [ ] **Step 2: Add template upload to chat flow**

In chat_upload, detect template files:
```python
# If a single file with "模板" in name, treat as template
if len(uploaded) == 1 and ("模板" in uploaded[0]["filename"] or 
                            "template" in uploaded[0]["filename"].lower()):
    agent.set_template(session_id, uploaded[0]["path"], uploaded[0]["filename"])
```

- [ ] **Step 3: Pass template to analyzer in chat tool execution**

In `_execute_tool` for `analyze_commonality`:
```python
# Check for template
template_sections = None
template_path = session.get("template_path")
if template_path and os.path.exists(template_path):
    from template_parser import parse_template
    try:
        skeleton = parse_template(template_path)
        template_sections = skeleton.sections
    except Exception:
        pass

# Pass to analyze_documents
merge_plan = await loop.run_in_executor(
    None, analyze_documents, docs_data, template_sections, on_progress,
)
```

Similarly update `_direct_merge` to handle template_sections.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add template upload and pipeline integration"
```

---

### Task 12: Integration test

**Files:**
- Test files in project root

- [ ] **Step 1: Write integration test script**

```python
"""test_integration.py — Test the template-driven merge pipeline."""
import sys
sys.path.insert(0, 'backend')

from doc_parser import parse_document
from template_parser import parse_template
from analyzer import analyze_documents
from merger import generate_merged_docx
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# 1. Parse template
template_path = os.path.join(BASE, "QSCW-V-C054-PD-2025 运行工岗位操作规程.docx")
skeleton = parse_template(template_path)
print(f"Template: {len(skeleton.sections)} sections")
for s in skeleton.sections[:10]:
    print(f"  [H{s.level}] {s.heading}")

# 2. Parse source docs
docs = []
for fname in [
    "SCW-V-C038-PD-2025三班化验操作规程.docx",
    "SCW-V-C045-PD-2025臭氧系统操作规程.docx",
    "SCW-V-C050-PD-2025 倒闸操作安全操作规程.docx",
]:
    fpath = os.path.join(BASE, fname)
    if os.path.exists(fpath):
        docs.append(parse_document(fpath, fname))

print(f"\nParsed {len(docs)} source documents")

# 3. Analyze
docs_data = [d.to_dict() for d in docs]
plan = analyze_documents(docs_data, skeleton.sections)

print(f"\nMerge Plan:")
print(f"  Cover: {plan.cover_title}")
print(f"  Main sections: {len(plan.main_sections)}")
for s in plan.main_sections:
    print(f"    - {s['heading']}: {len(s['paragraphs'])} paragraphs")
print(f"  Attachments: {len(plan.attachments)}")
for a in plan.attachments:
    print(f"    - {a['name']}")

# 4. Generate
output = os.path.join(BASE, "merged_output", "integration_test.docx")
all_images = {d.filename: d.all_images for d in docs}
generate_merged_docx(plan, docs_data, all_images, output, plan.cover_title, skeleton)
print(f"\nOutput: {output}")
print("Done!")
```

- [ ] **Step 2: Run the test**

```bash
cd D:\my_document_integration && python test_integration.py
```

- [ ] **Step 3: Inspect the output docx**

Open the generated file and verify:
- Cover: enterprise standard format, no merge count/date
- TOC: proper headings, no common/unique labels
- Body: unified chapters, no "来源文档" markers
- Attachments: Appendix A, B, C format

- [ ] **Step 4: Commit**

```bash
git add test_integration.py
git commit -m "test: add integration test for template-driven merge"
```

---

## Completion Criteria

- [x] Cover page follows enterprise standard format (no merge count, no generation date, no file list)
- [x] TOC shows only titles with leader dots and page numbers
- [x] No "共性/独有" section identifiers
- [x] No "来源文档：xxx" markers in body
- [x] Body chapters synthesize content from all source docs
- [x] Each source doc becomes an appendix (附件A-F)
- [x] Body text references appendices where appropriate
- [x] When template provided, follows template chapter structure
- [x] When no template, AI derives chapter structure from source docs
