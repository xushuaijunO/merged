# Template-Driven Document Merge Design

## Overview

Transform the document merging assistant from "semantic commonality analysis" to
"template-driven content assembly". Users provide an optional template docx plus
N source docx files. The system produces a single merged docx following the
template's structure and style.

## Current vs Target

| Aspect | Current | Target |
|--------|---------|--------|
| Merge logic | AI finds common + unique across docs | Template dictates structure, AI maps source content to sections |
| Output structure | Fixed: Cover → TOC → Common → Doc-specific | Template-driven: Main doc (synthesized) + Attachments (doc-specific ops) |
| Content dedup | None | Main doc and attachments must not repeat content |
| Styling | Hardcoded styles in merger.py | Inherited from template or built-in standard |
| No template | N/A | Fall back to built-in standard format |
| Attachment count | Unlimited source docs | Each source doc may become an attachment |

## Key Insight from User's Example

6 individual operation procedure docs → 1 "运行工岗位操作规程":

- **Main document**: Synthesized common content (封面, 目录, 范围, 岗位职责,
  风险辨识, 上岗条件, 作业要求 overview, 应急处置). Content drawn from ALL
  source docs, merged and rewritten.
- **Attachments (附件A~G)**: Each source doc's unique operational details,
  preserving original content but formatted to template style.
- **No duplication**: Content appearing in the main body does NOT appear in
  attachments, and vice versa.

## Architecture

### Data Flow

```
Template (.docx) ──→ Parse ──→ Skeleton (headings, styles, page layout)
                                   │
Source docs (.docx) ──→ Parse ──→ Content entries (sections, paragraphs, images)
                                   │
                                   ▼
                          Phase 1 AI: Global Understanding
                          - Read template skeleton
                          - Read source doc summaries (headings only, not full text)
                          - Produce: output outline + attachment mapping
                                   │
                                   ▼
                          Phase 2 AI: Per-Section Generation (concurrent)
                          - For each main-doc section: synthesize from all sources
                          - For each attachment: extract unique ops from one source
                          - Ensure no cross-section duplication
                                   │
                                   ▼
                          Generate DOCX
                          - Clone template styles (or use built-in defaults)
                          - Build cover, TOC, main body, attachments
                          - Output .docx
```

### Module Changes

#### 1. `backend/template_parser.py` (NEW)

Parse a template docx and extract:
- **Style definitions**: font name, size, bold, color, line spacing for every
  paragraph style
- **Page layout**: margins, page size, headers/footers
- **Section skeleton**: ordered list of section headings with levels

```python
@dataclass
class TemplateSkeleton:
    styles: dict  # style_name → {font, size, bold, color, ...}
    page_layout: dict  # margins, page_size
    sections: list  # [{heading, level, style_name}]
    cover_elements: list  # cover-specific paragraphs
```

#### 2. `backend/builtin_template.py` (NEW)

Built-in standard format used when no template is uploaded:
- Cover: 黑体 26pt title, company info area
- TOC: auto-generated
- Headings: 黑体 at various sizes (22pt H1, 16pt H2...)
- Body: 宋体 10.5pt
- Standard section structure for document merging

#### 3. `backend/analyzer.py` (REFACTOR)

Replace the current "group-by-heading → common/unique" logic with:

- `plan_structure(skeleton, source_summaries)` → AI decides: main doc sections,
  attachment list, content boundaries
- `generate_main_section(section_heading, source_docs_full_text)` → AI synthesizes
  a main document section from all relevant source content
- `generate_attachment(attachment_name, source_doc_full_text, already_covered)` →
  AI extracts unique operational details, skipping content already in main doc

#### 4. `backend/merger.py` (REFACTOR)

Key changes:
- Accept a `TemplateSkeleton` and use its style definitions instead of hardcoded
- Generate document structure from AI plan, not fixed Part1/Part2 pattern
- Proper style application: each paragraph gets the correct style name so fonts
  and sizes come from the style definition

#### 5. `backend/agent.py` (MODIFY)

Add new tool: `upload_template` to mark one uploaded file as the template.

Modify `generate_merged_document` to use the new template-driven pipeline.

Update SYSTEM_PROMPT to describe the template-driven workflow.

#### 6. Frontend (MODIFY)

- Add "上传模板" button (optional, visually distinct from source file upload)
- Template file shown separately in chat with a label/badge
- When no template uploaded, show hint that standard format will be used

## AI Prompt Design

### Phase 1: Structure Planning

Input: template skeleton + source doc summaries (headings + paragraph counts)
Output: JSON with section plan + attachment mapping

```json
{
  "main_document": {
    "sections": [
      {"heading": "范围", "level": 2, "sources": "all"},
      {"heading": "岗位职责", "level": 2, "sources": "all"},
      ...
    ]
  },
  "attachments": [
    {"name": "附件A：三班化验操作流程", "source_doc": "C038", "sections_to_include": ["作业要求"]}
  ]
}
```

### Phase 2: Section Generation

For each main doc section, prompt includes:
- The section heading and its purpose in the document
- Full text of ALL source documents
- Explicit instruction: "Write synthesized content. Do NOT include operational
  step-by-step procedures — those belong in attachments."

For each attachment, prompt includes:
- The attachment name
- The specific source document's full text
- List of topics already covered in the main document
- Explicit instruction: "Extract UNIQUE operational procedures not covered in
  the main document. Skip any content already present in main body."

## Built-in Standard Format (No Template)

```
封面
├── 文档合并汇编 (黑体 26pt, centered)
├── 合并文档数量：N 份
├── 源文件名称列表
└── 生成日期：YYYY-MM-DD

目录 (auto-generated)

前言 (AI-written)

一、范围与规范性引用

二、内容概述 (AI-synthesized from all sources)

三、各文档内容
├── 来源文档：xxx.docx
│   └── (extracted unique content)
└── ...

附件 (source doc operational details)
```

Default styles:
- 封面标题: 黑体 26pt
- H1 章节标题: 黑体 22pt bold
- H2: 黑体 16pt
- H3: 黑体 10.5pt
- 正文: 宋体 10.5pt
- 页边距: 2.5cm top/bottom, 2.8cm left/right

## Error Handling

- Template parsing fails → fall back to built-in standard, warn user
- AI analysis fails for a section → use structural fallback (include content as-is)
- Only 1 source file → skip attachment structure, just reformat to template style
- Very large source docs → truncate with summary for AI, full content for generation

## Backward Compatibility

- Legacy `/api/upload` + `/api/merge` endpoints preserved
- Chat agent maintains existing tool names, adds `upload_template`
- Existing `_direct_merge` fallback works without template
