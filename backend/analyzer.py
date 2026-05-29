"""AI semantic analyzer: template-driven document merging.

Pipeline:
  1. Structure Planning — AI reads all docs + template chapters, plans body chapters + appendix mapping
  2. Section Synthesis — AI generates each body chapter from all source docs concurrently
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


# ---------------------------------------------------------------------------
# Phase 1: Structure Planning
# ---------------------------------------------------------------------------

def _extract_template_body_chapters(template_sections: List[SectionNode]) -> List[dict]:
    """Extract body chapters from the correctly-structured template tree.

    The tree (built via outlineLvl) has L2 items as chapters and L3+ items
    as sub-sections. We flatten this into main_sections for the merger.
    章标题-styled nodes are filtered out (they are appendix content).
    """
    chapters: List[dict] = []

    def _walk(nodes: List[SectionNode], parent_is_chapter: bool = False):
        for node in nodes:
            heading = node.heading.strip()
            style = node.style_name or ""
            if not heading:
                continue
            if node.style_name in ("封面标准名称", "封面标准号2", "其他标准标志",
                                    "其他标准称谓", "其他发布日期", "其他实施日期"):
                continue
            if heading.startswith("附件") or heading.startswith("附录"):
                continue
            if any(k in heading for k in ("目录", "目次")):
                continue

            # 前言-level → recurse into children (they ARE the chapters)
            if style in ("前言、引言标题", "前言、引言标题") or heading in ("前言",):
                _walk(node.children)
                continue

            # 章标题 → skip entirely (appendix content)
            if style == "章标题":
                continue

            # L2 node → chapter; deeper nodes → sub-sections
            if node.level == 2:
                sub_headings = []
                for child in node.children:
                    if child.level >= 3:
                        # Convert template's absolute level to relative prompt
                        # level: chapter=L2 → L2 child=L3 → prompt level=2 (##)
                        # deep child=L4 → prompt level=3 (###)
                        prompt_level = max(2, child.level - 1)
                        sub_headings.append({
                            "text": child.heading.strip(),
                            "level": prompt_level,
                        })
                chapters.append({
                    "heading": heading,
                    "level": 1,
                    "style_name": "Heading 2",
                    "subheadings": sub_headings,
                })
            elif node.level >= 3 and parent_is_chapter:
                # Deep node under a chapter → still need to handle
                # (This catches edge cases like 章标题 with children)
                pass

    _walk(template_sections)
    return chapters


def _build_structure_plan_prompt(template_sections: List[SectionNode],
                                  doc_summaries: List[dict],
                                  has_template: bool) -> str:
    """Build prompt for AI to plan the output document structure."""

    if has_template:
        # Render full template tree as AI reference (auto-numbering heads)
        def _render_tree(nodes, depth=0):
            lines = []
            for s in nodes:
                heading = s.heading.strip()
                if not heading: continue
                if heading.startswith("附件") or heading.startswith("附录"): continue
                if "目录" in heading or "目次" in heading: continue
                if s.style_name in ("封面标准名称", "封面标准号2", "其他标准标志",
                                     "其他标准称谓", "其他发布日期", "其他实施日期"): continue
                if s.style_name in ("章标题",): continue  # appendix content, not body
                lines.append("  " * depth + f"[H{s.level}] {heading}")
                lines += _render_tree(s.children, depth + 1)
            return lines

        tree_lines = _render_tree(template_sections)
        tree_text = "\n".join(tree_lines) if tree_lines else "（模板无明确正文标题，请根据源文件内容自行确定）"

        template_instruction = f"""## 参考模板结构

以下是上传的模板文档的章节树结构（含层级）。请**参考**这个结构来规划合并文档的章节，但最终的章节标题和数量需要根据源文件实际内容来合理确定，不要生搬硬套模板：

{tree_text}"""
    else:
        template_instruction = """## 无模板

请通读所有源文件的内容概要，自行归纳出统一的章节标题体系。通常是企业操作规程的标准结构（范围、规范性引用文件、职责、风险辨识、上岗条件、作业要求、应急处置等），但具体标题必须根据源文件实际内容来确定，不要生搬硬套。"""

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

规划最终统一操作规程的结构。这是一个凝练整合的过程，不是简单拼接：

1. **主文档正文**：从所有源文件中综合提炼共性的、概括性的内容，按模板章节组织为统一的正文章节。写作风格参考企业操作规程：简洁、专业、原则性表述。
2. **附件**：每个源文件对应一个附件，附件名使用"附件A：源文件文档名"、"附件B：源文件文档名"等格式。附件保留各源文件的详细操作步骤。
3. **不重复原则**：主文档已有的概括性内容，附件中不再赘述。主文档通过"具体操作参照《附件X：XXX》"引用附件。
4. **无"来源文档"标识**：主文档中不出现"来源文档：XXX"等字样。
5. **无"共性/独有"标识**：文档是一个统一的操作规程，不区分共性独有。

请严格输出以下JSON格式（不要输出其他任何内容）：
{{
  "cover_title": "统一操作规程的标题",
  "main_sections": [
    {{"heading": "第1章标题", "level": 1, "style_name": "Heading 2"}},
    {{"heading": "第2章标题", "level": 1, "style_name": "Heading 2"}}
  ],
  "attachments": [
    {{"name": "附件A：源文件1的标题", "source_index": 0}},
    {{"name": "附件B：源文件2的标题", "source_index": 1}}
  ],
  "toc_headings": [
    {{"level": 1, "text": "前言"}},
    {{"level": 2, "text": "1 范围"}},
    {{"level": 2, "text": "2 规范性引用文件"}}
  ]
}}"""


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
            max_tokens=8192,
            system="你是一个专业的企业文档编辑。输出必须是合法的完整JSON格式，每个标题只出现一次，不要重复。",
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
        # Deduplicate main_sections by heading
        seen = set()
        unique_sections = []
        for s in result.get("main_sections", []):
            h = s.get("heading", "")
            if h and h not in seen:
                seen.add(h)
                unique_sections.append(s)
        result["main_sections"] = unique_sections
        logger.info("Structure plan: %d main sections, %d attachments",
                     len(result.get("main_sections", [])),
                     len(result.get("attachments", [])))
        return result

    finally:
        http_client.close()


# ---------------------------------------------------------------------------
# Phase 2: Section Synthesis
# ---------------------------------------------------------------------------

def _build_section_synthesis_prompt(heading: str, all_source_texts: List[dict],
                                     attachment_names: List[str],
                                     subheadings: Optional[List] = None) -> str:
    """Build prompt for synthesizing one body chapter from all source docs."""
    sources_text = []
    for s in all_source_texts:
        sources_text.append(
            f"### 源文件：{s['filename']}\n{s['full_text'][:4000]}"
            f"{'...(内容截断)' if len(s.get('full_text', '')) > 4000 else ''}"
        )
    combined = "\n\n---\n\n".join(sources_text)

    att_refs = "\n".join(f"- 《{a}》" for a in attachment_names) if attachment_names else "（无）"

    if subheadings:
        outline_lines = []
        for sh in subheadings:
            text = sh.get("text", "") if isinstance(sh, dict) else str(sh)
            lvl = max(2, int(sh.get("level", 2))) if isinstance(sh, dict) else 2
            if not text:
                continue
            marker = "#" * lvl
            indent = "  " * (lvl - 2)
            outline_lines.append(f"{indent}{marker} {text}")
        outline_block = "\n".join(outline_lines)
        structure_constraint = f"""

## 强制子标题结构
本章节必须按以下多级层次组织内容。**每条都不可省略、不可调顺序、不可改文字、不可增加未列出的新标题**（模板固定结构）：
```
{outline_block}
```
格式约定：## 为二级 (N.1)、### 为三级 (N.1.1)、#### 为四级。不要在标题里写数字。"""
    else:
        structure_constraint = ""

    return f"""你是一个专业的企业文档编辑。请为统一操作规程撰写「{heading}」章节的内容。

## 任务
综合以下 {len(all_source_texts)} 个源文件的内容，撰写一个统一的「{heading}」章节。
{structure_constraint}

撰写要求：
- 提取所有源文件中与「{heading}」相关的内容，融合为通顺、精炼的表述
- 只写概括性、原则性的内容，不写详细的分步操作步骤
- 如果某操作有详细步骤在附件中，引用附件：如"具体操作参照《附件A：XXX》"
- **子标题标记**：如果该章节下有多个子主题，二级标题以"## "开头（如"## 岗位与巡检"），三级标题以"### "开头（如"### 浑浊度测定方法"）。操作子步骤标签（如"操作前准备"、"操作过程"）使用"**标签名**"加粗正文格式，不要用###标题标记。不要自行添加任何数字编号，编号由系统自动生成
- **内容用列表组织**：子标题下的内容尽量用"a) xxx\nb) xxx\nc) xxx"或"1. xxx\n2. xxx"的编号列表形式逐条列出，清晰易读
- **表格必须内联完整输出**：如果需要表格，**必须**用 markdown 格式 `| 列1 | 列2 |\\n|---|---|\\n| 值1 | 值2 |` 完整输出。严禁"见表1"等只有引用没有表格的写法
- **不要给章节标题本身加编号**（标题编号由系统自动添加），直接写正文内容
- **不要使用markdown格式**：不要使用*斜体*等markdown标记，操作子步骤标签可使用**加粗**突出（如**操作前准备**、**操作过程**）
- 保持企业标准文档的专业、简洁风格
- 不要标注"共性"、"独有"等字样
- 不要标注"来源文档"等字样
- 使用中文

## 可引用的附件
{att_refs}

## 源文件内容
{combined}

请直接输出该章节的正文内容（纯文本段落，可用编号列表如1. 2. 3.和子标题如6.1、6.2，可用|表格|，不要JSON格式）。"""


def _synthesize_section(heading: str, all_source_texts: List[dict],
                         attachment_names: List[str],
                         progress_callback=None,
                         subheadings: Optional[List] = None) -> dict:
    """Phase 2: AI synthesizes one body chapter from all source docs."""
    import anthropic
    import httpx

    prompt = _build_section_synthesis_prompt(heading, all_source_texts, attachment_names,
                                             subheadings=subheadings)

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
            system="你是一个专业的企业文档编辑。输出简洁、通顺的中文段落，不要JSON格式。",
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


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_plan(doc_summaries: List[dict]) -> dict:
    """Fallback when AI structure planning fails."""
    return {
        "cover_title": "操作规程汇编",
        "main_sections": [
            {"heading": "前言", "level": 1, "style_name": "前言、引言标题"},
        ],
        "attachments": [
            {
                "name": f"附件{chr(65 + i)}：{_clean_filename_for_attachment(s['filename'])}",
                "source_index": i,
            }
            for i, s in enumerate(doc_summaries)
        ],
        "toc_headings": [
            {"level": 1, "text": "前言"},
        ],
    }


def _clean_filename_for_attachment(filename: str) -> str:
    """Extract a clean title from a source filename."""
    name = filename.replace('.docx', '').replace('.DOCX', '')
    # Remove doc number patterns like SCW-V-C038-PD-2025
    name = re.sub(r'[A-Z]+-V-C\d+-PD-\d{4}\s*', '', name)
    name = name.strip()
    return name or filename


def _clean_attachment_name(raw_name: str, filename: str) -> str:
    """Clean attachment name: remove .docx, doc numbers like SCW-V-C038-PD-2025."""
    name = raw_name.strip()
    # Remove .docx suffix
    name = re.sub(r'\.docx$', '', name, flags=re.IGNORECASE)
    # Remove doc number patterns: XX-V-CXXX-PD-XXXX
    name = re.sub(r'[A-Z]+-V-C\d+-PD-\d{4}\s*', '', name)
    # Remove leading numbers and dots
    name = re.sub(r'^[\d\.、\s]+', '', name)
    # Remove trailing spaces
    name = name.strip()
    # Ensure it starts with 附件 + letter
    if not name.startswith("附件"):
        name = f"附件{chr(65 + _attachment_counter())}：{name or filename.replace('.docx', '')}"
    return name


_attach_counter = 0


def _attachment_counter():
    global _attach_counter
    _attach_counter += 1
    return _attach_counter - 1


def _build_doc_summaries(docs_data: List[dict]) -> List[dict]:
    """Build summaries of each source doc for Phase 1 structure planning."""
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
        template_sections: Template chapter structure (from template_parser).
                          None or empty = AI derives chapters from source docs.
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
    # With template: directly extract chapters from the template tree
    # (outlineLvl-based parsing gives correct hierarchy).
    # Without template: AI plans from scratch.
    if has_template:
        template_chapters = _extract_template_body_chapters(template_sections)
        if template_chapters:
            structure_plan = None
            if ANTHROPIC_API_KEY:
                try:
                    structure_plan = plan_structure(
                        template_sections, doc_summaries, has_template, progress_callback,
                    )
                except Exception:
                    pass
            if not structure_plan:
                structure_plan = _fallback_plan(doc_summaries)
            structure_plan["main_sections"] = template_chapters
        else:
            if ANTHROPIC_API_KEY:
                try:
                    structure_plan = plan_structure(
                        template_sections or [], doc_summaries, has_template, progress_callback,
                    )
                except Exception as e:
                    logger.error("Structure planning failed: %s, using fallback", e)
                    structure_plan = _fallback_plan(doc_summaries)
            else:
                structure_plan = _fallback_plan(doc_summaries)
    else:
        if ANTHROPIC_API_KEY:
            try:
                structure_plan = plan_structure(
                    template_sections or [], doc_summaries, has_template, progress_callback,
                )
            except Exception as e:
                logger.error("Structure planning failed: %s, using fallback", e)
                structure_plan = _fallback_plan(doc_summaries)
        else:
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
    total_main = len(main_plan)

    attachment_names = [a.get("name", "") for a in attach_plan]

    if main_plan and ANTHROPIC_API_KEY:
        # Preserve original order: map heading → original index
        heading_order = {s.get("heading", ""): i for i, s in enumerate(main_plan)}

        def gen_main(sec_info):
            return _synthesize_section(
                sec_info.get("heading", ""),
                doc_texts,
                attachment_names,
                progress_callback,
                subheadings=sec_info.get("subheadings") or None,
            )

        results_by_heading = {}
        max_w = min(3, len(main_plan))
        with ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = {executor.submit(gen_main, s): s for s in main_plan}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    completed += 1
                    results_by_heading[result.get("heading", "")] = result
                    if progress_callback:
                        progress_callback("progress", {
                            "stage": "generating",
                            "message": f"主文档生成 ({completed}/{total_main}): {result.get('heading', '')}",
                            "percent": 35 + int(30 * completed / max(total_main, 1)),
                        })

        # Sort results by original plan order
        plan.main_sections = sorted(
            results_by_heading.values(),
            key=lambda r: heading_order.get(r.get("heading", ""), 999),
        )
    elif main_plan:
        # No API key: use empty sections from plan
        for sec in main_plan:
            plan.main_sections.append({
                "heading": sec.get("heading", ""),
                "paragraphs": ["（需要AI分析，请配置API Key）"],
                "tables": [],
                "images": [],
            })

    # Phase 2b: Attachments — use source doc content directly (no AI regeneration)
    # Each source doc maps to one appendix
    for att_info in attach_plan:
        src_idx = att_info.get("source_index", -1)
        if 0 <= src_idx < len(docs_data):
            src_doc = docs_data[src_idx]
            att_text = _flatten_full_text(src_doc.get("sections", []))
            raw_name = att_info.get("name", f"附件{chr(65 + src_idx)}")
            clean_name = _clean_attachment_name(raw_name, src_doc.get("filename", ""))
            plan.attachments.append({
                "name": clean_name,
                "paragraphs": [att_text],  # Kept for fallback when sections are empty
                "sections": src_doc.get("sections", []),  # Structured sections for rendering
                "level": 1,
                "source_index": src_idx,
            })
        with lock:
            completed += 1
            if progress_callback:
                progress_callback("progress", {
                    "stage": "generating",
                    "message": f"附件处理 ({completed + total_main}/{total_main + len(attach_plan)}): {att_info.get('name', '')}",
                    "percent": 35 + int(30 * (completed + total_main) / max(total_main + len(attach_plan), 1)),
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
