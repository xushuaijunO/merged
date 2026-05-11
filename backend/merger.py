"""Merger: generates the final unified operating procedure docx.

Heading hierarchy (all black, visible in Word navigation pane):
  Heading 1: 目录, 前言, 1-7 body chapters, 附件A-N titles
  Heading 2: sub-sections (1.1, 1.2...)
  Heading 3: sub-sub-sections (1.1.1...)
"""

import os
import io as std_io
import re
from typing import List, Dict, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_LEADER
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from analyzer import MergePlan

LINES_PER_PAGE = 28
BLACK = RGBColor(0, 0, 0)


# ====================================================================
# Heading helpers — all black, all use Word heading styles for nav pane
# ====================================================================

def _h1(doc, text):
    """Heading 1: 目录, 前言, chapter titles, appendix titles."""
    h = doc.add_heading(text, level=1)
    for run in h.runs:
        run.font.color.rgb = BLACK
        run.font.name = "黑体"
    return h


def _h2(doc, text):
    """Heading 2: sub-sections like 1.1, 1.2."""
    h = doc.add_heading(text, level=2)
    for run in h.runs:
        run.font.color.rgb = BLACK
        run.font.name = "黑体"
    return h


def _h3(doc, text):
    """Heading 3: sub-sub-sections like 1.1.1."""
    h = doc.add_heading(text, level=3)
    for run in h.runs:
        run.font.color.rgb = BLACK
        run.font.name = "黑体"
    return h


def _body(doc, text):
    """Normal body paragraph (宋体 10.5pt)."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(10.5)
    run.font.name = "宋体"
    run.font.color.rgb = BLACK
    return p


def _table(doc, rows: List[List[str]]):
    """Insert a table with header row styled."""
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncols)
    tbl.style = 'Table Grid'
    for ri, row in enumerate(rows):
        for ci, cell_text in enumerate(row):
            if ci < ncols:
                cell = tbl.rows[ri].cells[ci]
                cell.text = str(cell_text)
                # Style header row
                if ri == 0:
                    for p in cell.paragraphs:
                        for run in p.runs:
                            run.bold = True
                            run.font.size = Pt(9)
    doc.add_paragraph()


def _add_image_to_doc(doc, image_blob, content_type, caption="", width_inches=5.0):
    image_stream = std_io.BytesIO(image_blob)
    try:
        if caption:
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.add_run(f"【图】{caption}")
        doc.add_picture(image_stream, width=Inches(width_inches))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        pass


# ====================================================================
# Template styles
# ====================================================================

def _apply_template_styles(doc, skeleton):
    if not skeleton or not skeleton.styles:
        return
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


# ====================================================================
# Cover
# ====================================================================

def _clone_cover_from_template(doc, template_path, cover_title=""):
    if not template_path or not os.path.exists(template_path):
        _create_default_cover(doc, cover_title)
        return

    src_doc = Document(template_path)
    cover_paras = []
    for para in src_doc.paragraphs:
        text = para.text.strip()
        style_name = para.style.name if para.style else ""
        if style_name in ("toc 1", "toc 2", "TOC 1", "TOC 2") or text == "目    录":
            break
        if "目录" in text and len(text) < 10:
            break
        cover_paras.append(para)
        if len(cover_paras) >= 20:
            break

    while len(cover_paras) > 1 and not cover_paras[-1].text.strip():
        cover_paras.pop()

    title_replaced = False
    for src_para in cover_paras:
        text = src_para.text.strip()
        style_name = src_para.style.name if src_para.style else ""
        is_title = (style_name == "封面标准名称" or
                     (("标题" in style_name or "名称" in style_name) and len(text) > 3))

        new_para = doc.add_paragraph()
        _copy_paragraph_format(src_para, new_para)

        if is_title and cover_title and not title_replaced:
            new_para.clear()
            run = new_para.add_run(cover_title)
            _copy_run_format(src_para.runs[0] if src_para.runs else None, run)
            title_replaced = True
        else:
            for src_run in src_para.runs:
                new_run = new_para.add_run(src_run.text)
                _copy_run_format(src_run, new_run)

    doc.add_page_break()


def _copy_paragraph_format(src_para, dst_para):
    dst_para.alignment = src_para.alignment
    pf = src_para.paragraph_format
    if pf:
        if pf.space_before:
            dst_para.paragraph_format.space_before = pf.space_before
        if pf.space_after:
            dst_para.paragraph_format.space_after = pf.space_after
        if pf.line_spacing:
            dst_para.paragraph_format.line_spacing = pf.line_spacing


def _copy_run_format(src_run, dst_run):
    if src_run is None:
        return
    if src_run.font.name:
        dst_run.font.name = src_run.font.name
    if src_run.font.size:
        dst_run.font.size = src_run.font.size
    if src_run.bold:
        dst_run.bold = src_run.bold
    if src_run.italic:
        dst_run.italic = src_run.italic
    if src_run.font.color and src_run.font.color.rgb:
        dst_run.font.color.rgb = src_run.font.color.rgb


def _create_default_cover(doc, cover_title=""):
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("上海浦东威立雅自来水有限公司企业标准")
    run.font.size = Pt(16)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(cover_title or "操作规程")
    run.font.size = Pt(26)
    run.bold = True
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("上海浦东威立雅自来水有限公司  发布")
    run.font.size = Pt(14)
    doc.add_page_break()


# ====================================================================
# TOC
# ====================================================================

def _estimate_page_numbers(headings: List[dict],
                           main_sections: List[dict],
                           attachments: List[dict]) -> List[int]:
    pages = []
    current_page = 3  # cover=1, toc=2
    pages.append(current_page)
    current_page += 1  # preface
    for section in main_sections:
        pages.append(current_page)
        para_text = "\n".join(section.get("paragraphs", []))
        line_count = max(1, para_text.count('\n') + 1)
        current_page += max(1, (line_count + 4) // LINES_PER_PAGE)
    for att in attachments:
        pages.append(current_page)
        para_text = "\n".join(att.get("paragraphs", []))
        line_count = max(1, para_text.count('\n') + 1)
        current_page += max(1, (line_count + 2) // LINES_PER_PAGE)
    return pages


def _generate_text_toc(doc, headings: List[dict],
                       main_sections: List[dict],
                       attachments: List[dict]):
    page_nums = _estimate_page_numbers(headings, main_sections, attachments)
    _h1(doc, "目    录")
    doc.add_paragraph()

    for i, item in enumerate(headings):
        level = item.get("level", 2)
        text = item.get("text", "")
        if not text:
            continue

        para = doc.add_paragraph()
        indent = max(0, level - 1) * 0.6
        para.paragraph_format.left_indent = Cm(indent)

        tab_stops = para.paragraph_format.tab_stops
        tab_stops.add_tab_stop(
            Cm(14.5), alignment=WD_ALIGN_PARAGRAPH.RIGHT, leader=WD_TAB_LEADER.DOTS
        )

        run = para.add_run(text)
        run.font.size = Pt(11) if level <= 2 else Pt(10)
        run.font.name = "宋体"
        run.font.color.rgb = BLACK

        run2 = para.add_run("\t")
        page_str = str(page_nums[i]) if i < len(page_nums) else ""
        run3 = para.add_run(page_str)
        run3.font.size = Pt(11) if level <= 2 else Pt(10)

    doc.add_page_break()


# ====================================================================
# Preface
# ====================================================================

def _generate_preface(doc, template_path=None):
    doc.add_page_break()
    _h1(doc, "前    言")
    doc.add_paragraph()

    if template_path and os.path.exists(template_path):
        src_doc = Document(template_path)
        in_preface = False
        copied = 0
        for para in src_doc.paragraphs:
            text = para.text.strip()
            style = para.style.name if para.style else ""
            if "前言" in text and ("前言、引言标题" in style or len(text) <= 6):
                in_preface = True
                continue
            if in_preface:
                if style in ("Heading 1", "Heading 2", "章标题", "一级条标题",
                              "前言、引言标题") and text and "前言" not in text:
                    break
                if text:
                    _body(doc, text)
                    copied += 1
                    if copied > 10:
                        break

    last_text = doc.paragraphs[-1].text.strip() if doc.paragraphs else ""
    if not last_text or last_text == "前    言":
        _body(doc, "本标准按照企业标准编写规范起草。")
        _body(doc, "本标准由上海浦东威立雅自来水有限公司浦东水厂生产管理科提出并归口。")
        _body(doc, "本标准起草部门：浦东水厂生产管理科。")

    doc.add_page_break()


# ====================================================================
# TOC heading collector
# ====================================================================

def _collect_toc_headings(merge_plan, docs_data) -> List[dict]:
    headings = [{"level": 1, "text": "前言"}]
    for i, section in enumerate(merge_plan.main_sections):
        h = section.get("heading", "")
        if h and "前言" not in h and "目录" not in h:
            clean = re.sub(r'^[\d.、\s]+', '', h).strip()
            headings.append({"level": 1, "text": f"{i + 1} {clean}"})
    if merge_plan.attachments:
        for att in merge_plan.attachments:
            headings.append({"level": 1, "text": att.get("name", "附件")})
    return headings


# ====================================================================
# Appendix content cleaning
# ====================================================================

# Headings already covered in body chapters — skip in appendices
BODY_SKIP = [
    '范围', '规范性引用文件', '岗位职责', '岗位风险辨识',
    '上岗条件', '劳动防护用品', '应急处置要求',
    '管理职责', '作业范围', '前言', '目录', '目次',
]
_ws_re = re.compile(r'\s+')


def _norm(s: str) -> str:
    return _ws_re.sub('', s).strip()


def _clean_appendix_content(text: str) -> str:
    """Remove body-covered sections from appendix. Number kept sections hierarchically.

    Tracks heading depth to assign proper numbering:
    - Top-level sections: 1., 2., 3.
    - Sub-sections: 1.1, 1.2, 2.1...
    """
    lines = text.split('\n')
    result = []
    in_skip = False
    section_stack = [0]  # [major, minor, ...]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue

        if stripped.startswith('【') and stripped.endswith('】'):
            inner = stripped.strip('【】')
            inner_norm = _norm(inner)

            # Check if covered in body
            is_covered = False
            for h in BODY_SKIP:
                if inner_norm.startswith(_norm(h)):
                    is_covered = True
                    break
            if inner_norm.startswith('_') or inner_norm in ('前言', '目录', '目次'):
                is_covered = True

            if is_covered:
                in_skip = True
                continue

            # Determine depth: check if this is a sub-heading
            # Heuristic: sub-headings from source docs are shorter and more specific
            depth = 1  # default top-level
            # If we detect this as a sub-section (based on source doc heading level hints)
            # just treat all kept non-covered headings as top-level for now
            in_skip = False
            section_stack[0] += 1
            section_stack = [section_stack[0]]
            num = f"{section_stack[0]}."
            result.append(f"【{num} {inner}】")
            continue

        if in_skip:
            # Resume when we hit next real section
            if stripped.startswith('【'):
                in_skip = False
                # Re-process this line
                continue
            continue

        result.append(stripped)

    return '\n'.join(result)


# ====================================================================
# Table detection helpers
# ====================================================================

def _is_table_row(line: str) -> bool:
    """Check if a line looks like a table row (pipe-separated or tab-separated)."""
    return '|' in line and line.count('|') >= 2


def _parse_table_lines(lines: List[str]) -> Optional[List[List[str]]]:
    """Parse pipe-separated or tab-separated lines into a table."""
    if not lines or not _is_table_row(lines[0]):
        return None
    rows = []
    for line in lines:
        if _is_table_row(line):
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                rows.append(cells)
        elif not line.strip():
            break
        else:
            break
    return rows if len(rows) >= 2 else None


# ====================================================================
# Main generator
# ====================================================================

def generate_merged_docx(merge_plan, docs_data,
                         all_images_by_doc, output_path,
                         cover_title="",
                         skeleton=None,
                         template_path=None) -> str:
    doc = Document()

    if skeleton:
        _apply_template_styles(doc, skeleton)

    # Default font
    style = doc.styles['Normal']
    font = style.font
    font.name = '宋体'
    font.size = Pt(10.5)
    try:
        style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    except Exception:
        pass

    # Page margins
    if skeleton and skeleton.page_layout and skeleton.page_layout.margin_top:
        for s in doc.sections:
            s.top_margin = skeleton.page_layout.margin_top
            s.bottom_margin = skeleton.page_layout.margin_bottom
            s.left_margin = skeleton.page_layout.margin_left
            s.right_margin = skeleton.page_layout.margin_right
    else:
        for s in doc.sections:
            s.top_margin = Cm(2.5)
            s.bottom_margin = Cm(2.5)
            s.left_margin = Cm(2.8)
            s.right_margin = Cm(2.0)

    # ================================================================
    # 1. COVER
    # ================================================================
    final_title = merge_plan.cover_title or cover_title or "操作规程"
    _clone_cover_from_template(doc, template_path, final_title)

    # ================================================================
    # 2. TOC
    # ================================================================
    toc_headings = _collect_toc_headings(merge_plan, docs_data)
    _generate_text_toc(doc, toc_headings, merge_plan.main_sections, merge_plan.attachments)

    # ================================================================
    # 3. PREFACE — Heading 1, same level as body chapters
    # ================================================================
    _generate_preface(doc, template_path)

    # ================================================================
    # 4. BODY CHAPTERS — Heading 1, sub-sections Heading 2, sub-sub Heading 3
    # ================================================================
    if merge_plan.main_sections:
        chapter_idx = 0
        for section in merge_plan.main_sections:
            heading = section.get("heading", "")
            paragraphs = section.get("paragraphs", [])
            tables = section.get("tables", [])

            if not heading or "前言" in heading or "目录" in heading:
                continue

            clean_heading = re.sub(r'^[\d.、\s]+', '', heading).strip()
            numbered = f"{chapter_idx + 1} {clean_heading}"

            # Heading 1 for chapter title (same level as 前言)
            _h1(doc, numbered)

            # Write content with sub-section detection
            for p_text in paragraphs:
                if not p_text.strip():
                    continue

                # Check if entire paragraph is a table
                p_lines = p_text.strip().split('\n')
                table_rows = _parse_table_lines(p_lines)
                if table_rows:
                    _table(doc, table_rows)
                    continue

                for line in p_lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Detect heading patterns: "1.1 xxx", "1.1.1 xxx"
                    sub2_match = re.match(r'^(\d+)\.(\d+)\s+(.+)', line)
                    sub3_match = re.match(r'^(\d+)\.(\d+)\.(\d+)\s+(.+)', line)

                    if sub3_match:
                        # Sub-sub-section → Heading 3
                        c, s, ss, title = sub3_match.groups()
                        new_line = f"{chapter_idx + 1}.{s}.{ss} {title}"
                        _h3(doc, new_line)
                    elif sub2_match:
                        # Sub-section → Heading 2
                        old_c, sub_n, title = sub2_match.groups()
                        new_line = f"{chapter_idx + 1}.{sub_n} {title}"
                        _h2(doc, new_line)
                    elif re.match(r'^\d+[\.\、]', line):
                        # Numbered list item → body text
                        _body(doc, line)
                    else:
                        _body(doc, line)

            # Dedicated tables from merge plan
            for tbl_rows in tables:
                _table(doc, tbl_rows)

            # Images
            for img_info in section.get("images", []):
                dhash = img_info.get("dhash", "")
                for doc_name, img_list in all_images_by_doc.items():
                    for img in img_list:
                        if hasattr(img, 'dhash') and img.dhash == dhash:
                            _add_image_to_doc(doc, img.blob, img.content_type,
                                              caption=img_info.get("caption", ""))
                            break

            doc.add_paragraph()
            chapter_idx += 1

    # ================================================================
    # 5. APPENDICES
    # ================================================================
    if merge_plan.attachments:
        for att in merge_plan.attachments:
            doc.add_page_break()

            name = att.get("name", "附件")
            paragraphs = att.get("paragraphs", [])

            _h1(doc, name)
            doc.add_paragraph()

            for p_text in paragraphs:
                if not p_text.strip():
                    continue
                cleaned = _clean_appendix_content(p_text.strip())

                for chunk in cleaned.split("\n\n"):
                    chunk = chunk.strip()
                    if not chunk:
                        continue

                    for line in chunk.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("【") and line.endswith("】"):
                            inner = line.strip("【】")
                            # Only make a heading if it looks like a REAL section heading:
                            # - Not ending with sentence punctuation 。；！
                            # - Not a long sentence (>20 chars, likely operational content)
                            # - Not ending with a parenthetical note
                            is_sentence_end = inner.endswith('。') or inner.endswith('；') or inner.endswith('！')
                            is_long = len(inner) > 20
                            is_operational = any(kw in inner for kw in ['打开', '关闭', '按下', '检查', '确认', '启动', '停止'])
                            if not is_sentence_end and not is_long and not is_operational and len(inner) > 3:
                                _h2(doc, inner)
                            else:
                                _body(doc, inner)
                        else:
                            _body(doc, line)

    doc.save(output_path)
    return output_path
