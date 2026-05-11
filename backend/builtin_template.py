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

    No hardcoded chapter titles — AI derives chapters from source content
    when no template is provided.
    """
    return TemplateSkeleton(
        styles=_make_default_styles(),
        page_layout=_make_default_page_layout(),
        sections=[],
        cover_elements=[
            {"text": "", "style_name": "封面标准名称"},
        ],
        has_header=False,
        has_footer=False,
    )
