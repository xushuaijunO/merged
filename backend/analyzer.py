"""AI semantic analyzer: identifies common vs unique content across documents.

Streaming-aware with progress callbacks for real-time UI updates.
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from collections import defaultdict

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, MODEL,
    HTTP_VERIFY_SSL, HTTP_TRUST_ENV,
)

logger = logging.getLogger("analyzer")


@dataclass
class MergePlan:
    """Result of semantic analysis."""
    common_sections: List[dict] = field(default_factory=list)
    doc_specific: Dict[str, List[dict]] = field(default_factory=lambda: defaultdict(list))
    summary: dict = field(default_factory=dict)


def _heading_path(section: dict, parent_path: str = "") -> str:
    """Build a full heading path for a section."""
    current = f"{parent_path} > {section['heading']}" if parent_path else section['heading']
    return current


def flatten_sections(sections: List[dict], doc_name: str, parent_path: str = "") -> List[dict]:
    """Flatten section tree into a list of (heading_path, content, doc_name) entries.

    Now includes image metadata for AI-aware placement.
    """
    result = []
    for sec in sections:
        path = _heading_path(sec, parent_path)
        entry = {
            "heading_path": path,
            "heading": sec["heading"],
            "level": sec["level"],
            "paragraphs": sec["paragraphs"],
            "tables": sec["tables"],
            "image_count": sec["image_count"],
            "images": sec.get("images", []),  # Full image metadata
            "doc_name": doc_name,
            "children_count": len(sec.get("children", [])),
        }
        result.append(entry)
        result.extend(flatten_sections(sec.get("children", []), doc_name, path))
    return result


def group_by_heading(all_entries: List[dict]) -> Dict[str, List[dict]]:
    """Group flattened entries by heading path for cross-document comparison."""
    groups = defaultdict(list)
    for entry in all_entries:
        groups[entry["heading_path"]].append(entry)
    return dict(groups)


def match_similar_headings(groups: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
    """Merge groups with similar (but not identical) heading paths."""
    keys = list(groups.keys())
    merged = {}
    used = set()

    for i, key1 in enumerate(keys):
        if key1 in used:
            continue
        cluster = list(groups[key1])
        for j, key2 in enumerate(keys):
            if j <= i or key2 in used:
                continue
            parts1 = key1.split(" > ")
            parts2 = key2.split(" > ")
            if parts1[-1] == parts2[-1]:
                cluster.extend(groups[key2])
                used.add(key2)
        merged[key1] = cluster
        used.add(key1)

    return merged


def _build_analysis_prompt(heading_path: str, entries: List[dict]) -> str:
    """Build the prompt for Claude to analyze a group of matching sections.

    Now includes image metadata (dHash, positioning context) so the AI
    can decide image placement and deduplication.
    """
    docs_content = []
    for e in entries:
        text = "\n".join(e["paragraphs"])
        if not text:
            text = "(空章节，仅有标题)"

        # Build image annotations for this entry
        images = e.get("images", [])
        img_lines = []
        if images:
            img_lines.append(f"\n  📷 本章节包含 {len(images)} 张图片:")
            for k, img in enumerate(images):
                ctx_before = img.get("context_before", "")[:60]
                ctx_after = img.get("context_after", "")[:60]
                dhash_short = img.get("dhash", "")[:12]
                img_lines.append(
                    f"    图片{k+1}: dHash={dhash_short} "
                    f"| 前文「{ctx_before}...」"
                    f"| 后文「{ctx_after}...」"
                )
        docs_content.append(f"【{e['doc_name']}】\n{text}{''.join(img_lines)}")

    combined = "\n\n---\n\n".join(docs_content)

    return f"""你是一个专业的文档合并专家。以下是 {len(entries)} 个文档中同一章节「{heading_path}」的内容。

请分析这些内容：
1. **共性内容**：语义相同或高度相似的部分，请融合为一段统一、通顺的表述
2. **独有内容**：每个文档各自独有的内容，标注来源文档名
3. **图片处理**：
   - 如果多个图片的 dHash 前12位相同 → 它们是同一张图，只需保留一份
   - 在 `image_placement` 中指定每张图片应插入到共性内容或独有内容的哪句话后面
   - 为每张保留的图片生成一个简短的标题（10字以内），描述图片内容
   - 标记重复图片为 `duplicate_of`，指向保留的那个图片

注意：
- 相似的表述应合并，不要简单拼接
- 独有内容保持原文不变
- 如果某文档该章节为空或仅有标题，标记为"无实质内容"

请严格按以下JSON格式输出（不要输出其他内容）：
{{
  "common": "融合后的共性内容",
  "unique_by_doc": {{
    "文档1": ["独有内容要点1"],
    "文档2": []
  }},
  "image_placement": [
    {{
      "anchor_text": "要插入到哪句话后面（原文片段，20字以内）",
      "target": "common 或 文档名",
      "dhash": "图片的dHash值",
      "caption": "图片标题（10字以内）",
      "duplicate_of": null
    }}
  ]
}}

文档内容：
{combined}"""


def _extract_json(text: str) -> dict:
    """Robust JSON extraction from AI response that may contain markdown fences."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON block with regex
    m = re.search(r'\{[\s\S]*"common"[\s\S]*"unique_by_doc"[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # Last resort: try fixing common issues
    try:
        cleaned = re.sub(r',\s*}', '}', text)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise


def _call_claude_streaming(heading_path: str, entries: List[dict], progress_callback) -> dict:
    """Call Claude API with streaming to capture thinking blocks."""
    import anthropic
    import httpx

    prompt = _build_analysis_prompt(heading_path, entries)

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
            system="你是一个专业的文档合并与编辑助手。你的输出必须是合法的JSON格式。",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response_text = ""
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        response_text += event.delta.text
                    elif event.delta.type == "thinking_delta":
                        if progress_callback:
                            progress_callback("thinking", {
                                "heading": heading_path,
                                "thought": event.delta.thinking,
                            })
                elif event.type == "content_block_start":
                    if event.content_block.type == "thinking":
                        pass  # thinking block start
            final = stream.get_final_message()
            logger.info("AI API response | heading=%s | tokens_in=%d | tokens_out=%d",
                        heading_path,
                        final.usage.input_tokens if hasattr(final, 'usage') else 0,
                        final.usage.output_tokens if hasattr(final, 'usage') else 0)
    finally:
        http_client.close()

    if not response_text.strip():
        raise ValueError("AI返回为空")

    return _extract_json(response_text)


def analyze_with_claude(heading_path: str, entries: List[dict],
                        progress_callback: Optional[Callable] = None) -> dict:
    """Call Claude API to analyze a section group, with retry logic and progress reporting.

    Args:
        heading_path: Full heading path being analyzed
        entries: List of section entries from different documents
        progress_callback: Optional fn(event_type, data_dict) for UI progress.
            event_type: 'step_start' | 'thinking' | 'retry' | 'step_done' | 'step_error'

    Returns:
        dict with 'common', 'unique_by_doc' keys, plus optional 'error' flag
    """
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            if progress_callback and attempt == 0:
                # Signal retry on subsequent attempts
                pass

            result = _call_claude_streaming(heading_path, entries, progress_callback)

            # Validate expected keys
            if "common" not in result and "unique_by_doc" not in result:
                raise ValueError("响应缺少预期字段")

            return result

        except Exception as e:
            logger.warning("AI analysis failed for '%s' (attempt %d/%d): %s",
                           heading_path, attempt + 1, max_retries + 1, str(e))

            if attempt < max_retries:
                if progress_callback:
                    progress_callback("retry", {
                        "heading": heading_path,
                        "attempt": attempt + 1,
                        "reason": str(e)[:100],
                    })
            else:
                if progress_callback:
                    progress_callback("step_error", {
                        "heading": heading_path,
                        "error": str(e)[:100],
                    })
                return {
                    "common": "",
                    "unique_by_doc": {e2["doc_name"]: ["(AI分析失败，保留原文)"] for e2 in entries},
                    "error": True,
                }


def structural_only_analysis(groups: Dict[str, List[dict]],
                             progress_callback: Optional[Callable] = None) -> MergePlan:
    """Fallback: structural matching without AI (no API key)."""
    all_docs = set()
    for entries in groups.values():
        for e in entries:
            all_docs.add(e["doc_name"])
    doc_count = len(all_docs)

    plan = MergePlan()
    total = len(groups)
    completed = 0

    for heading_path, entries in groups.items():
        docs_in_group = {e["doc_name"] for e in entries}

        if progress_callback:
            completed += 1
            progress_callback("step_start", {
                "heading": heading_path, "current": completed, "total": total,
            })

        if len(docs_in_group) == doc_count:
            combined_text = []
            all_section_images = []
            for e in entries:
                if e["paragraphs"]:
                    combined_text.append(f"（来源：{e['doc_name']}）")
                    combined_text.extend(e["paragraphs"])
                # Collect all images from this heading group
                all_section_images.extend(e.get("images", []))
            # Deduplicate images by dHash
            from doc_parser import hamming_distance
            deduped_images = _dedup_images_by_hash(all_section_images)
            plan.common_sections.append({
                "heading": heading_path.split(" > ")[-1],
                "level": entries[0]["level"],
                "paragraphs": combined_text,
                "tables": entries[0].get("tables", []),
                "image_count": len(deduped_images),
                "images": deduped_images,  # Deduplicated image list
            })
        else:
            for e in entries:
                if e["paragraphs"] or e["tables"]:
                    plan.doc_specific[e["doc_name"]].append({
                        "heading": heading_path.split(" > ")[-1],
                        "level": e["level"],
                        "paragraphs": e["paragraphs"],
                        "tables": e.get("tables", []),
                        "image_count": e.get("image_count", 0),
                        "images": e.get("images", []),
                    })

        if progress_callback:
            progress_callback("step_done", {
                "heading": heading_path, "current": completed, "total": total,
            })

    plan.summary = {
        "common_sections": len(plan.common_sections),
        "doc_specific_total": sum(len(v) for v in plan.doc_specific.values()),
        "mode": "structural_only",
    }
    return plan


def ai_analysis(groups: Dict[str, List[dict]],
                progress_callback: Optional[Callable] = None) -> MergePlan:
    """Full AI-powered analysis using Claude API with progress reporting.

    Args:
        groups: Heading groups keyed by path
        progress_callback: fn(event_type, data) for real-time UI updates
    """
    plan = MergePlan()
    total = len(groups)
    completed = 0

    for heading_path, entries in groups.items():
        docs_in_group = {e["doc_name"] for e in entries}
        completed += 1

        if progress_callback:
            progress_callback("step_start", {
                "heading": heading_path, "current": completed, "total": total,
            })

        if len(docs_in_group) == 1:
            # Only in one document → automatically doc-specific
            e = entries[0]
            if e["paragraphs"] or e["tables"] or e.get("images"):
                plan.doc_specific[e["doc_name"]].append({
                    "heading": heading_path.split(" > ")[-1],
                    "level": e["level"],
                    "paragraphs": e["paragraphs"],
                    "tables": e.get("tables", []),
                    "image_count": e.get("image_count", 0),
                    "images": e.get("images", []),
                })
            if progress_callback:
                progress_callback("step_done", {
                    "heading": heading_path, "current": completed, "total": total,
                })
        else:
            # Multiple documents share this heading → AI analysis
            try:
                result = analyze_with_claude(heading_path, entries, progress_callback)

                # Common content
                common_text = result.get("common", "")
                image_placement = result.get("image_placement", [])
                if common_text and common_text != "无":
                    # Collect all images from all entries
                    all_section_images = []
                    for e in entries:
                        all_section_images.extend(e.get("images", []))
                    from doc_parser import hamming_distance
                    deduped_images = _dedup_images_by_hash(all_section_images)

                    plan.common_sections.append({
                        "heading": heading_path.split(" > ")[-1],
                        "full_path": heading_path,
                        "level": entries[0]["level"],
                        "paragraphs": [common_text],
                        "tables": entries[0].get("tables", []),
                        "image_count": len(deduped_images),
                        "images": deduped_images,
                        "image_placement": image_placement,
                    })

                # Unique content per document
                unique_by_doc = result.get("unique_by_doc", {})
                for doc_name, items in unique_by_doc.items():
                    if items and len(items) > 0:
                        # Find matching entry images
                        entry_images = []
                        for e in entries:
                            if e["doc_name"] == doc_name:
                                entry_images = e.get("images", [])
                                break
                        plan.doc_specific[doc_name].append({
                            "heading": f"{heading_path.split(' > ')[-1]}（独有）",
                            "level": entries[0]["level"] + 1,
                            "paragraphs": items if isinstance(items[0], str) else [str(i) for i in items],
                            "tables": [],
                            "image_count": len(entry_images),
                            "images": entry_images,
                        })

                if progress_callback:
                    progress_callback("step_done", {
                        "heading": heading_path, "current": completed, "total": total,
                    })

            except Exception as e:
                logger.error("AI analysis fatal error for '%s': %s", heading_path, str(e))
                if progress_callback:
                    progress_callback("step_error", {
                        "heading": heading_path, "error": str(e)[:100],
                    })
                for entry in entries:
                    plan.doc_specific[entry["doc_name"]].append({
                        "heading": heading_path.split(" > ")[-1],
                        "level": entry["level"],
                        "paragraphs": entry["paragraphs"],
                        "tables": entry.get("tables", []),
                        "image_count": entry.get("image_count", 0),
                        "images": entry.get("images", []),
                    })

    plan.summary = {
        "common_sections": len(plan.common_sections),
        "doc_specific_total": sum(len(v) for v in plan.doc_specific.values()),
        "mode": "ai_analysis",
    }
    return plan


def _dedup_images_by_hash(images: List[dict], threshold: int = 5) -> List[dict]:
    """Deduplicate images by dHash Hamming distance. Keeps largest (best quality)."""
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
        result.append(group[0])  # Keep the largest/best quality
    return result


def analyze_documents(docs_data: List[dict],
                      progress_callback: Optional[Callable] = None) -> MergePlan:
    """Main entry point: analyze multiple parsed documents.

    Args:
        docs_data: List of dicts from ParsedDocument.to_dict()
        progress_callback: Optional fn(event_type, data_dict) for UI progress

    Returns:
        MergePlan with common and doc-specific sections
    """
    all_entries = []
    for doc in docs_data:
        entries = flatten_sections(doc["sections"], doc["filename"])
        all_entries.extend(entries)

    raw_groups = group_by_heading(all_entries)
    groups = match_similar_headings(raw_groups)

    if ANTHROPIC_API_KEY:
        logger.info("Using AI analysis mode | model=%s | groups=%d", MODEL, len(groups))
        return ai_analysis(groups, progress_callback)
    else:
        logger.warning("API key not set, falling back to structural-only analysis")
        return structural_only_analysis(groups, progress_callback)
