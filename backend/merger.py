"""Merger: generates the final merged docx from the MergePlan.

Enhanced with paragraph-level image insertion and dHash deduplication.
Images are placed after the matching paragraph text, not just at section end.
"""

import os
import io as std_io
from datetime import datetime
from typing import List, Dict, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from analyzer import MergePlan


TOC_LEVELS = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_heading_style(doc, level, text):
    return doc.add_heading(text, level=min(level, 9))


def _add_paragraph(doc, text, bold=False):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold
    return para


def _add_image_to_doc(doc, image_blob, content_type, caption="", width_inches=5.0):
    """Insert an image with optional caption into the document."""
    ext = content_type.split("/")[-1]
    if ext == "jpeg":
        ext = "jpg"
    image_stream = std_io.BytesIO(image_blob)
    try:
        if caption:
            cap = _add_paragraph(doc, f"【图】{caption}", bold=False)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(image_stream, width=Inches(width_inches))
        last_para = doc.paragraphs[-1]
        last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        pass


def _normalize_for_match(text: str, max_len: int = 20) -> str:
    """Normalize text for fuzzy matching — used to find anchor paragraphs."""
    if not text:
        return ""
    t = text.strip().replace("\n", "").replace("\r", "")
    return t[:max_len]


def _find_best_paragraph_index(paragraphs: List[str], anchor_text: str,
                               context_before: str = "",
                               context_after: str = "") -> int:
    """Find the best paragraph index to insert an image after.

    Priority:
    1. Exact match on anchor_text (from AI image_placement)
    2. Fuzzy match on context_before (the paragraph right before image in source)
    3. Fuzzy match on context_after (the paragraph right after image in source)
    4. Returns -1 if no match (insert at section end)
    """
    if not paragraphs:
        return -1

    anchor = _normalize_for_match(anchor_text)
    before = _normalize_for_match(context_before)
    after = _normalize_for_match(context_after)

    # Priority 1: anchor_text exact or contains match
    if anchor:
        for i, p in enumerate(paragraphs):
            p_norm = _normalize_for_match(p, 40)
            if anchor in p_norm or p_norm in anchor:
                return i

    # Priority 2: context_before fuzzy match
    if before:
        for i, p in enumerate(paragraphs):
            p_norm = _normalize_for_match(p, 40)
            if before in p_norm or p_norm in before:
                return i

    # Priority 3: context_after fuzzy match (insert before the matching paragraph)
    if after:
        for i, p in enumerate(paragraphs):
            p_norm = _normalize_for_match(p, 40)
            if after in p_norm or p_norm in after:
                return max(0, i - 1)

    return -1


def _build_image_lookup(all_images_by_doc: dict) -> Dict[str, dict]:
    """Build a lookup: dhash → actual Image object (with blob).

    When multiple images have the same dHash, picks the largest.
    """
    lookup = {}
    for doc_name, img_list in all_images_by_doc.items():
        for img in img_list:
            dh = img.dhash if hasattr(img, 'dhash') else ""
            if not dh:
                # Try to compute it
                try:
                    from doc_parser import compute_dhash
                    dh = compute_dhash(img.blob)
                except Exception:
                    continue
            if dh not in lookup or len(img.blob) > len(lookup[dh]["blob"]):
                lookup[dh] = {
                    "blob": img.blob,
                    "content_type": img.content_type,
                    "dhash": dh,
                    "source_doc": doc_name,
                    "filename": img.filename if hasattr(img, 'filename') else "",
                    "context_before": img.context_before if hasattr(img, 'context_before') else "",
                    "context_after": img.context_after if hasattr(img, 'context_after') else "",
                }
    return lookup


def _insert_images_for_paragraphs(doc, image_infos: List[dict],
                                  image_lookup: Dict[str, dict],
                                  paragraphs_before: List[str],
                                  image_placement: List[dict] = None):
    """Insert images at precise positions relative to paragraphs.

    Args:
        doc: The Document being built
        image_infos: Image metadata list (with dhash, context_before, etc.)
        image_lookup: dhash → actual image blob data
        paragraphs_before: List of paragraph texts already added for this section
        image_placement: Optional AI-directed placement from analysis
    """
    if not image_infos:
        return

    # Keep track of how many images we've inserted after each paragraph
    # to handle multiple images after the same paragraph
    insertion_map: Dict[int, List[dict]] = {}

    for img_info in image_infos:
        dh = img_info.get("dhash", "")
        actual_img = image_lookup.get(dh)
        if not actual_img:
            # Try partial match
            for key in image_lookup:
                if key.startswith(dh[:6]) if dh else False:
                    actual_img = image_lookup[key]
                    break
        if not actual_img:
            continue

        # Determine placement
        anchor = ""
        ctx_before = img_info.get("context_before", "")
        ctx_after = img_info.get("context_after", "")

        # If AI gave us placement instructions, use them
        if image_placement:
            for ip in image_placement:
                ip_dh = ip.get("dhash", "")
                if ip_dh and dh.startswith(ip_dh[:8]):
                    anchor = ip.get("anchor_text", "")
                    if ip.get("caption"):
                        actual_img["caption"] = ip["caption"]
                    break

        best_idx = _find_best_paragraph_index(
            paragraphs_before, anchor, ctx_before, ctx_after,
        )

        # Generate caption if not set
        if not actual_img.get("caption"):
            cap_parts = []
            if ctx_before:
                cap_parts.append(ctx_before[:30])
            elif ctx_after:
                cap_parts.append(ctx_after[:30])
            if actual_img.get("source_doc"):
                cap_parts.append(f"来源: {actual_img['source_doc']}")
            actual_img["caption"] = " - ".join(cap_parts) if cap_parts else "图片"

        if best_idx not in insertion_map:
            insertion_map[best_idx] = []
        insertion_map[best_idx].append(actual_img)

    # Now insert images after their target paragraphs
    # We work backwards through paragraphs to avoid index shifting
    # (since we can only add images at the end of the doc, we use a
    # different strategy: track what to insert for each paragraph index)

    # Since python-docx doesn't support inserting at arbitrary positions,
    # we use a two-pass approach: first add all paragraphs, then insert
    # images between them by tracking paragraph objects
    #
    # Actually, the cleanest approach: during the paragraph-writing loop,
    # after writing paragraph i, check if i is in insertion_map and insert.
    # We pass the insertion_map to the caller and handle it there.


def _write_paragraphs_with_images(doc, paragraphs: List[str],
                                  images_to_insert: Dict[int, List[dict]]):
    """Write paragraphs, inserting images after matching paragraphs.

    Args:
        doc: The Document
        paragraphs: Paragraph texts to write
        images_to_insert: Map of paragraph_index → list of image dicts
    """
    for i, p_text in enumerate(paragraphs):
        if p_text.strip():
            _add_paragraph(doc, p_text.strip())
        # Insert any images that should come after this paragraph
        imgs = images_to_insert.get(i, [])
        for img in imgs:
            _add_image_to_doc(
                doc, img["blob"], img["content_type"],
                caption=img.get("caption", ""),
            )

    # Insert images with index -1 (no matching paragraph → at section end)
    fallback_imgs = images_to_insert.get(-1, [])
    if fallback_imgs:
        for img in fallback_imgs:
            _add_image_to_doc(
                doc, img["blob"], img["content_type"],
                caption=img.get("caption", ""),
            )


# ---------------------------------------------------------------------------
# Cover & TOC
# ---------------------------------------------------------------------------

def _create_cover(doc, doc_count, filenames, cover_title="文档合并汇编"):
    """Create a unified cover page."""
    for _ in range(6):
        doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
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


def _generate_real_toc(doc, headings: List[dict]):
    """Generate a text-based table of contents."""
    _set_heading_style(doc, 1, "目录")
    doc.add_paragraph()

    for item in headings:
        level = item.get("level", 2)
        text = item.get("text", "")
        if not text:
            continue
        indent = max(0, level - 1) * 0.8
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(indent)
        run = para.add_run(text)
        run.font.size = Pt(11) if level <= 2 else Pt(10)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    doc.add_page_break()


def _insert_table(doc, table_rows):
    """Insert a table into the document."""
    if not table_rows:
        return
    num_cols = len(table_rows[0]) if table_rows else 1
    table = doc.add_table(rows=len(table_rows), cols=num_cols)
    table.style = 'Table Grid'
    for ri, row_data in enumerate(table_rows):
        for ci, cell_text in enumerate(row_data):
            if ci < num_cols:
                table.rows[ri].cells[ci].text = cell_text
    doc.add_paragraph()


def _collect_toc_headings(merge_plan, docs_data) -> List[dict]:
    """Walk the merge plan and collect all headings for TOC."""
    headings = []

    headings.append({"level": 1, "text": "第一部分：共性内容"})

    if merge_plan.common_sections:
        for section in merge_plan.common_sections:
            h = section.get("heading", "")
            if h and not h.startswith("_"):
                headings.append({
                    "level": min(section.get("level", 1) + 1, 3),
                    "text": h,
                })

    headings.append({"level": 1, "text": "第二部分：各文档独有内容"})

    for doc_name, sections in merge_plan.doc_specific.items():
        headings.append({"level": 2, "text": f"来源文档：{doc_name}"})
        for section in sections:
            h = section.get("heading", "")
            if h and not h.startswith("_"):
                headings.append({
                    "level": min(section.get("level", 1) + 2, 3),
                    "text": h,
                })

    return headings


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_merged_docx(merge_plan: MergePlan, docs_data: List[dict],
                         all_images_by_doc: dict, output_path: str,
                         cover_title: str = "文档合并汇编") -> str:
    """Generate the final merged docx with precise image placement.

    Images are now inserted after the matching paragraph (using context_before /
    context_after / AI image_placement), not just at section end.
    Duplicate images (same dHash) are inserted only once.
    """
    doc = Document()

    # Default font
    style = doc.styles['Normal']
    font = style.font
    font.name = '宋体'
    font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

    # Page margins
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.8)
        section.right_margin = Cm(2.8)

    filenames = [d["filename"] for d in docs_data]

    # Build image lookup: dhash → actual blob
    image_lookup = _build_image_lookup(all_images_by_doc)

    # Track already-inserted dHashes to avoid duplicates across sections
    inserted_hashes: set = set()

    # === Cover ===
    _create_cover(doc, len(filenames), filenames, cover_title)

    # === TOC ===
    toc_headings = _collect_toc_headings(merge_plan, docs_data)
    _generate_real_toc(doc, toc_headings)

    # === Part 1: Common Content ===
    _set_heading_style(doc, 1, "第一部分：共性内容")

    if merge_plan.common_sections:
        for section in merge_plan.common_sections:
            heading = section.get("heading", "")
            level = section.get("level", 1)
            paragraphs = section.get("paragraphs", [])
            tables = section.get("tables", [])
            images = section.get("images", [])
            image_placement = section.get("image_placement", [])

            if heading.startswith("_"):
                continue

            _set_heading_style(doc, min(level + 1, 9), heading)

            # Compute which images go after which paragraph
            img_after_para: Dict[int, List[dict]] = {}
            for img_info in images:
                dh = img_info.get("dhash", "")
                if dh in inserted_hashes:
                    continue  # Already inserted in another section
                actual = image_lookup.get(dh)
                if not actual:
                    continue
                anchor = ""
                for ip in image_placement:
                    if ip.get("dhash", "") and dh.startswith(ip["dhash"][:8]):
                        anchor = ip.get("anchor_text", "")
                        if ip.get("caption"):
                            actual["caption"] = ip["caption"]
                        break
                best_idx = _find_best_paragraph_index(
                    paragraphs,
                    anchor,
                    img_info.get("context_before", ""),
                    img_info.get("context_after", ""),
                )
                if best_idx not in img_after_para:
                    img_after_para[best_idx] = []
                # Generate caption
                if not actual.get("caption"):
                    ctx = img_info.get("context_before", "") or img_info.get("context_after", "")
                    actual["caption"] = ctx[:40] if ctx else "图片"
                img_after_para[best_idx].append(actual)
                inserted_hashes.add(dh)

            _write_paragraphs_with_images(doc, paragraphs, img_after_para)

            for table_rows in tables:
                _insert_table(doc, table_rows)
    else:
        _add_paragraph(doc, "（未检测到明确的共性内容）")

    doc.add_page_break()

    # === Part 2: Document-specific Content ===
    _set_heading_style(doc, 1, "第二部分：各文档独有内容")

    doc_names = list(merge_plan.doc_specific.keys())
    for doc_name in doc_names:
        sections = merge_plan.doc_specific.get(doc_name, [])
        if not sections:
            continue

        _set_heading_style(doc, 2, f"来源文档：{doc_name}")

        # Get actual image objects for this document
        doc_images = all_images_by_doc.get(doc_name, [])
        doc_img_lookup = {}
        for img in doc_images:
            dh = img.dhash if hasattr(img, 'dhash') else ""
            if not dh:
                try:
                    from doc_parser import compute_dhash
                    dh = compute_dhash(img.blob)
                except Exception:
                    continue
            doc_img_lookup[dh] = {
                "blob": img.blob,
                "content_type": img.content_type,
                "dhash": dh,
                "source_doc": doc_name,
                "context_before": img.context_before if hasattr(img, 'context_before') else "",
                "context_after": img.context_after if hasattr(img, 'context_after') else "",
            }

        for section in sections:
            heading = section.get("heading", "")
            level = section.get("level", 1)
            paragraphs = section.get("paragraphs", [])
            images = section.get("images", [])

            if heading.startswith("_"):
                continue

            _set_heading_style(doc, min(level + 2, 9), heading)

            # Compute image placement
            img_after_para: Dict[int, List[dict]] = {}
            for img_info in images:
                dh = img_info.get("dhash", "")
                if dh in inserted_hashes:
                    continue
                actual = image_lookup.get(dh) or doc_img_lookup.get(dh)
                if not actual:
                    continue
                best_idx = _find_best_paragraph_index(
                    paragraphs,
                    "",
                    img_info.get("context_before", ""),
                    img_info.get("context_after", ""),
                )
                if best_idx not in img_after_para:
                    img_after_para[best_idx] = []
                if not actual.get("caption"):
                    ctx = img_info.get("context_before", "") or img_info.get("context_after", "")
                    actual["caption"] = ctx[:40] if ctx else f"图片（来源: {doc_name}）"
                img_after_para[best_idx].append(actual)
                inserted_hashes.add(dh)

            _write_paragraphs_with_images(doc, paragraphs, img_after_para)

            for table_rows in section.get("tables", []):
                _insert_table(doc, table_rows)

        if doc_name != doc_names[-1]:
            doc.add_page_break()

    # Save
    doc.save(output_path)
    return output_path
