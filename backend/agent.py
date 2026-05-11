"""AI Agent with Claude tool-use for intelligent document merging.

Uses Claude API with function calling to understand user intent,
answer questions, and orchestrate the merge pipeline.
"""

import os
import uuid
import json
import logging
import asyncio
import io
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Optional

from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, MODEL, UPLOAD_DIR,
    HTTP_VERIFY_SSL, HTTP_TRUST_ENV,
)
from doc_parser import parse_document
from analyzer import analyze_documents

logger = logging.getLogger("agent")

SYSTEM_PROMPT = """你是一个专业的文档整合智能助手。你可以帮助用户将多个Word文档（.docx格式）整合为统一的企业操作规程。

## 你的身份
你是一个专业的企业文档编辑助手。你产出的不是简单的"合并文档"，而是凝练后的统一操作规程：
- **正文**：综合所有源文件的共性内容，提炼为统一的章节。写作风格为概括性、原则性表述。
- **附件**：每个源文件对应一个附件（附件A、附件B...），保留各自的操作细节。
- **引用**：正文中通过"具体操作参照《附件A：XXX》"引用附件。
- 正文中**不出现**"共性"、"独有"、"来源文档"等字样。

## 工作原则
1. **自然对话**：保持友好、自然的对话风格。
2. **主动汇报**：执行每个步骤时告知用户进展。
3. **灵活应变**：根据用户需求调整文档结构。
4. **用中文回复**，保持简洁清晰。

## 可用的工具
- `get_session_info` — 查看当前会话中已上传的文档信息
- `parse_documents` — 解析已上传的文档，提取结构化内容（章节、图片、表格）
- `get_document_detail` — 查看某个已解析文档的详细结构和内容概要
- `analyze_commonality` — AI分析所有文档，规划统一的章节结构（正文+附件映射）
- `generate_merged_document` — 生成统一操作规程（封面、目录、前言、正文、附件A-N）

## 典型工作流程
1. 用户上传多个文档
2. 解析所有文档 → AI分析（规划统一章节+附件映射）→ 生成文档
3. 告知用户结果

## 常见场景处理
- 用户问"你能做什么" → 介绍你的能力
- 用户说"整合这些文档" → 确认后开始流程
- **重要**：用户指定文件名时必须传入generate_merged_document的filename参数
- 用户只上传1个文档 → 提醒需要至少2个
- 用户上传非docx文件 → 提示仅支持docx格式
- 用户闲聊（你好、谢谢等） → 正常回复
"""

TOOLS = [
    {
        "name": "get_session_info",
        "description": "获取当前会话中已上传文档的信息，包括文档数量、文件名和大小。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "parse_documents",
        "description": "解析所有已上传的文档，提取结构化内容。解析后会显示每个文档的章节数、图片数和表格数。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_document_detail",
        "description": "获取某个已解析文档的详细结构和内容概要，包括章节列表和每章节的段落数、图片数。",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_index": {
                    "type": "integer",
                    "description": "文档在已解析列表中的索引（从0开始）",
                },
            },
            "required": ["doc_index"],
        },
    },
    {
        "name": "analyze_commonality",
        "description": "AI分析所有已解析文档，规划统一操作规程的章节结构：正文综合提炼所有源文件的共有内容（概括性表述），每个源文件对应一个附件（保留详细操作步骤）。这是生成文档前的必要步骤。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "generate_merged_document",
        "description": "生成统一操作规程文档。包含：企业标准封面、目录、前言、正文（AI凝练的统一章节）、附件A-N（各源文件的详细操作内容）。如果用户指定了文件名，请将其作为filename参数传入。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "【重要】用户指定的输出文件名（不含.docx后缀）。用户说'叫xxx'、'命名为xxx'则传'xxx'。用户没有指定时才传空字符串。",
                },
            },
            "required": [],
        },
    },
]


class MergeAgent:
    """Orchestrates document merging via Claude-powered tool-use agent."""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self.sessions[session_id] = {
            "id": session_id,
            "history": [],
            "uploaded_files": [],
            "parsed_docs": [],
            "all_images": {},
            "merge_plan": None,
            "output_path": None,
            "output_filename": None,
            "status": "ready",
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    async def handle_message(
        self, session_id: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """Process a user message using Claude tool-use and yield SSE events."""
        session = self.sessions.get(session_id)
        if not session:
            yield self._sse("error", {"message": "会话不存在"})
            return

        session["history"].append({"role": "user", "content": user_message})
        session["status"] = "processing"

        yield self._sse("status", {"status": "thinking"})

        # Build messages for Claude
        messages = self._build_messages(session, user_message)

        try:
            # Call Claude with tools
            async for sse_msg in self._claude_loop(session, messages):
                yield sse_msg
        except Exception as e:
            logger.error("Agent error: %s", str(e))
            yield self._sse("error", {"message": f"处理出错: {str(e)}"})

        session["status"] = "ready"

    def _build_messages(self, session: dict, user_message: str) -> List[dict]:
        """Build the message list for Claude from session history."""
        messages = []

        # Build context about uploaded files
        uploaded = session["uploaded_files"]
        parsed = session["parsed_docs"]

        context_parts = []
        if uploaded:
            names = [f["filename"] for f in uploaded]
            context_parts.append(f"已上传文档 ({len(uploaded)}个): " + ", ".join(names))
        if parsed:
            context_parts.append(f"已解析文档: {len(parsed)}个")
        if session["merge_plan"]:
            m = session["merge_plan"].summary
            context_parts.append(
                f"分析已完成: {m.get('main_sections', 0)}个正文章节, "
                f"{m.get('attachments', 0)}个附件"
            )
        if session["output_path"]:
            context_parts.append(
                f"合并文档已生成: {session.get('output_filename', 'unknown')}"
            )

        if context_parts:
            context = "【当前状态】\n" + "\n".join(context_parts)
        else:
            context = "【当前状态】\n会话刚创建，还没有上传任何文档。"

        messages.append({
            "role": "user",
            "content": (
                f"{context}\n\n"
                f"【用户消息】\n{user_message}\n\n"
                "(请根据用户意图和当前状态，自主选择合适的工具来完成任务。"
                "文档合并的核心步骤包括：解析文档、分析共性与独有内容、生成合并文档。"
                "但不是每次都必须执行全部步骤——根据实际情况灵活判断。"
                "如果用户只是闲聊或询问，请直接回复，不要调用工具。)"
            ),
        })

        return messages

    async def _claude_loop(
        self, session: dict, messages: List[dict], max_turns: int = 10
    ) -> AsyncGenerator[str, None]:
        """Run the Claude tool-use loop using async Anthropic client with streaming."""
        import anthropic
        import httpx

        async_http = httpx.AsyncClient(
            verify=HTTP_VERIFY_SSL,
            trust_env=HTTP_TRUST_ENV,
        )
        client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL,
            http_client=async_http,
        )

        try:
            for turn in range(max_turns):
                tool_calls = []
                text_content = []

                try:
                    async with client.messages.stream(
                        model=MODEL,
                        max_tokens=8192,
                        system=SYSTEM_PROMPT,
                        messages=messages,
                        tools=TOOLS,
                    ) as stream:
                        async for event in stream:
                            if event.type == "content_block_delta":
                                if hasattr(event, 'delta') and hasattr(event.delta, 'type'):
                                    if event.delta.type == "text_delta":
                                        delta_text = event.delta.text
                                        text_content.append(delta_text)
                                        yield self._sse("message", {"text": delta_text})
                            elif event.type == "content_block_start":
                                if hasattr(event, 'content_block') and event.content_block.type == "tool_use":
                                    tool_calls.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input": "",
                                    })

                        response = await stream.get_final_message()

                except Exception as e:
                    logger.error("Claude API error in turn %d: %s", turn, str(e))
                    if turn == 0:
                        yield self._sse("message", {
                            "text": (
                                "抱歉，AI服务暂时不可用。我将使用基础模式为你服务。\n\n"
                                f"当前已上传 {len(session['uploaded_files'])} 个文档。"
                            ),
                        })
                        async for sse_msg in self._direct_merge(session):
                            yield sse_msg
                        return
                    return

                # Rebuild tool_calls from final response (streaming may have incomplete data)
                tool_calls = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                if not tool_calls:
                    session["history"].append({
                        "role": "assistant",
                        "content": "".join(text_content) if text_content else "(no response)",
                    })
                    return

                # Execute tool calls (with streaming support)
                tool_results = []
                for tc in tool_calls:
                    yield self._sse("tool_call", {
                        "tool": tc["name"],
                        "input": tc["input"],
                    })

                    # Use a queue so the tool can stream events in real-time
                    stream_queue: asyncio.Queue = asyncio.Queue()

                    async def run_tool():
                        result = await self._execute_tool(
                            session, tc["name"], tc["input"], stream_queue=stream_queue,
                        )
                        for sse_msg in result.get("_sse_events", []):
                            stream_queue.put_nowait(sse_msg)
                        stream_queue.put_nowait(("__done__", result))

                    tool_task = asyncio.ensure_future(run_tool())

                    # Stream events as they arrive
                    result = None
                    while True:
                        try:
                            item = await asyncio.wait_for(stream_queue.get(), timeout=0.3)
                        except asyncio.TimeoutError:
                            if tool_task.done():
                                if result is None:
                                    try:
                                        item = stream_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                else:
                                    break
                            continue

                        if isinstance(item, tuple) and item[0] == "__done__":
                            result = item[1]
                            break
                        yield item

                    if result is None:
                        try:
                            await tool_task
                        except Exception:
                            pass
                        result = {"data": {"error": "工具执行超时"}, "_sse_events": []}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": json.dumps(result.get("data", {}), ensure_ascii=False),
                    })

                # Build assistant message with all content blocks
                content_blocks = []
                for block in response.content:
                    if block.type == "text":
                        content_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                    elif block.type == "thinking":
                        content_blocks.append({
                            "type": "thinking",
                            "thinking": block.thinking,
                        })

                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": tool_results})

                session["history"].append({
                    "role": "assistant",
                    "content": f"[调用工具: {', '.join(tc['name'] for tc in tool_calls)}]",
                })

        finally:
            await async_http.aclose()

    async def _execute_tool(
        self, session: dict, tool_name: str, tool_input: dict,
        stream_queue: asyncio.Queue = None,
    ) -> dict:
        """Execute a tool and return the result with optional SSE events.

        When stream_queue is provided, events are pushed to it in real-time
        instead of being collected in the returned list.
        """
        sse_events = []

        def emit(event: str, data: dict):
            """Emit an SSE event — to stream_queue if available, else to list."""
            msg = self._sse_raw(event, data)
            if stream_queue is not None:
                try:
                    stream_queue.put_nowait(msg)
                except Exception:
                    sse_events.append(msg)
            else:
                sse_events.append(msg)

        if tool_name == "get_session_info":
            uploaded = session["uploaded_files"]
            parsed = session["parsed_docs"]

            info = {
                "uploaded_count": len(uploaded),
                "parsed_count": len(parsed),
                "files": [
                    {
                        "filename": f["filename"],
                        "size_bytes": f.get("size", 0),
                        "size_display": self._format_size(f.get("size", 0)),
                    }
                    for f in uploaded
                ],
                "ready_to_merge": len(uploaded) >= 2,
                "missing_count": max(0, 2 - len(uploaded)),
            }

            return {"data": info, "_sse_events": []}

        elif tool_name == "parse_documents":
            uploaded = session["uploaded_files"]
            if not uploaded:
                return {
                    "data": {"error": "没有已上传的文档"},
                    "_sse_events": [],
                }

            parsed_docs = []
            all_images = {}
            parse_results = []

            for i, finfo in enumerate(uploaded):
                filepath = os.path.join(
                    UPLOAD_DIR, f"{finfo['file_id']}_{finfo['filename']}"
                )

                sse_events.append(self._sse_raw("progress", {
                    "stage": "parsing",
                    "message": f"解析文档 ({i+1}/{len(uploaded)}): {finfo['filename']}",
                    "percent": 10 + int(15 * (i + 1) / len(uploaded)),
                }))

                parsed = parse_document(filepath, finfo["filename"])
                parsed_docs.append(parsed)
                all_images[finfo["filename"]] = parsed.all_images

                parse_results.append({
                    "filename": finfo["filename"],
                    "title": parsed.title,
                    "sections_count": len(parsed.sections),
                    "images_count": len(parsed.all_images),
                    "tables_count": len(parsed.all_tables),
                    "paragraphs_count": len(parsed.full_text.split("\n")),
                })

            session["parsed_docs"] = parsed_docs
            session["all_images"] = all_images

            return {
                "data": {
                    "parsed_count": len(parse_results),
                    "documents": parse_results,
                    "total_images": sum(r["images_count"] for r in parse_results),
                    "total_tables": sum(r["tables_count"] for r in parse_results),
                },
                "_sse_events": sse_events,
            }

        elif tool_name == "get_document_detail":
            parsed = session["parsed_docs"]
            idx = tool_input.get("doc_index", 0)

            if not parsed or idx >= len(parsed):
                return {
                    "data": {"error": f"文档索引 {idx} 无效，共 {len(parsed)} 个已解析文档"},
                    "_sse_events": [],
                }

            doc = parsed[idx]
            sections_info = []
            for sec in doc.sections:
                sections_info.append({
                    "heading": sec.heading,
                    "level": sec.level,
                    "paragraphs_count": len(sec.paragraphs),
                    "images_count": len(sec.images),
                    "tables_count": len(sec.tables),
                    "children_count": len(sec.children),
                })

            detail = {
                "filename": doc.filename,
                "title": doc.title,
                "sections": sections_info,
                "total_images": len(doc.all_images),
                "total_tables": len(doc.all_tables),
            }

            return {"data": detail, "_sse_events": []}

        elif tool_name == "analyze_commonality":
            parsed = session["parsed_docs"]
            if len(parsed) < 2:
                return {
                    "data": {"error": f"至少需要2个已解析文档，当前只有{len(parsed)}个"},
                    "_sse_events": [],
                }

            emit("progress", {
                "stage": "analyzing",
                "message": "正在进行AI语义分析...",
                "percent": 30,
            })

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

            docs_data = [d.to_dict() for d in parsed]
            aq: asyncio.Queue = asyncio.Queue()

            def on_progress(event_type: str, data: dict):
                try:
                    aq.put_nowait((event_type, data))
                except Exception:
                    pass

            loop = asyncio.get_event_loop()

            async def run_analysis():
                return await loop.run_in_executor(
                    None, analyze_documents, docs_data, template_sections, on_progress,
                )

            analysis_task = asyncio.ensure_future(run_analysis())

            # Stream progress events while analysis runs
            while not analysis_task.done():
                try:
                    event_type, data = await asyncio.wait_for(aq.get(), timeout=0.1)
                    if event_type == "progress":
                        emit("progress", data)
                except asyncio.TimeoutError:
                    pass

            merge_plan = await analysis_task
            session["merge_plan"] = merge_plan

            summary = merge_plan.summary
            emit("progress", {
                "stage": "analyzed",
                "message": "AI分析完成",
                "percent": 65,
            })

            return {
                "data": {
                    "main_sections": summary.get("main_sections", 0),
                    "attachments": summary.get("attachments", 0),
                    "mode": summary.get("mode", "unknown"),
                },
                "_sse_events": sse_events,
            }

        elif tool_name == "generate_merged_document":
            merge_plan = session.get("merge_plan")
            parsed = session.get("parsed_docs")

            if not merge_plan:
                return {
                    "data": {"error": "请先完成文档分析（analyze_commonality）"},
                    "_sse_events": [],
                }

            sse_events.append(self._sse_raw("progress", {
                "stage": "merging",
                "message": "正在生成合并文档...",
                "percent": 75,
            }))

            from merger import generate_merged_docx
            import re

            docs_data = [d.to_dict() for d in parsed]
            user_filename = tool_input.get("filename", "").strip()

            # Fallback: if AI didn't pass a filename, try to extract from recent user messages
            if not user_filename:
                for msg in reversed(session.get("history", [])):
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        patterns = [
                            r'合并成[：:]?\s*([^\s，。,\.\n!！?？]+)',
                            r'文件名[称叫是为]?[：:]?\s*([^\s，。,\.\n!！?？]+)',
                            r'命名为?[：:]?\s*([^\s，。,\.\n!！?？]+)',
                            r'保存为[：:]?\s*([^\s，。,\.\n!！?？]+)',
                            r'输出(?:为|成)?[：:]?\s*([^\s，。,\.\n!！?？]+)',
                            r'(?:^|(?<=[。！\n]))[叫称][：:]?\s*([^\s，。,\.\n!！?？]+)',
                        ]
                        for pattern in patterns:
                            m = re.search(pattern, content)
                            if m:
                                user_filename = m.group(1).strip().rstrip('。.!！')
                                break
                        if user_filename:
                            break

            if user_filename:
                # Remove .docx suffix if user included it
                if user_filename.lower().endswith(".docx"):
                    user_filename = user_filename[:-5]
                safe_name = "".join(c for c in user_filename if c.isalnum() or c in "._-（）()【】[]")
                if safe_name:
                    output_filename = f"{safe_name}.docx"
                    cover_title = user_filename
                else:
                    output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                    cover_title = "文档合并汇编"
            else:
                output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                cover_title = "文档合并汇编"

            output_path = os.path.join(UPLOAD_DIR, output_filename)

            # Get template skeleton for styling
            skeleton = None
            template_path = session.get("template_path")
            if template_path and os.path.exists(template_path):
                from template_parser import parse_template
                try:
                    skeleton = parse_template(template_path)
                except Exception:
                    pass

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                generate_merged_docx,
                merge_plan,
                docs_data,
                session.get("all_images", {}),
                output_path,
                cover_title,
                skeleton,
                template_path,
            )

            session["output_path"] = output_path
            session["output_filename"] = output_filename
            session["status"] = "done"

            sse_events.append(self._sse_raw("progress", {
                "stage": "done",
                "message": "合并完成！",
                "percent": 100,
            }))

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

            return {"data": {"output_file": output_filename}, "_sse_events": sse_events}

        else:
            return {"data": {"error": f"未知工具: {tool_name}"}, "_sse_events": []}

    async def _direct_merge(self, session: dict) -> AsyncGenerator[str, None]:
        """Fallback: merge without AI agent (when Claude API unavailable)."""
        session_id = session["id"]
        uploaded = session["uploaded_files"]

        # Get the last user message to check intent
        last_msg = ""
        for msg in reversed(session["history"]):
            if msg["role"] == "user":
                last_msg = msg["content"]
                break

        # Simple intent detection: short greetings/questions shouldn't trigger merge
        casual_patterns = ["你好", "谢谢", "感谢", "再见", "你是谁", "能做什么", "帮助", "help",
                          "怎么样", "如何", "什么", "hi", "hello", "?"]
        is_casual = len(last_msg) < 15 and any(p in last_msg.lower() for p in casual_patterns)

        if is_casual and not uploaded:
            yield self._sse("message", {
                "text": (
                    "你好！我是文档合并助手。👋\n\n"
                    "我可以帮你：\n"
                    "- 📎 上传并合并多个Word文档（.docx格式）\n"
                    "- 🔍 分析文档间的共性内容和独有内容\n"
                    "- 📄 生成包含目录、共性内容和独有内容的高质量合并文档\n\n"
                    "请先上传你需要合并的文档，然后告诉我你的需求。"
                ),
            })
            return

        if is_casual and uploaded:
            if len(uploaded) >= 2:
                hint = "可以开始合并了，说「合并」即可。"
            else:
                hint = f"还需要至少 {2 - len(uploaded)} 个文档才能合并。"
            yield self._sse("message", {
                "text": f"你好！当前已上传 {len(uploaded)} 个文档。\n\n{hint}\n\n有什么我可以帮助你的吗？",
            })
            return

        if len(uploaded) < 2:
            yield self._sse("message", {
                "text": f"当前只有 {len(uploaded)} 个文档，至少需要2个文档才能合并。请继续上传。",
            })
            return

        file_names = [f["filename"] for f in uploaded]
        yield self._sse("message", {
            "text": f"收到！我将为你合并 **{len(uploaded)}** 个文档：\n\n" +
                    "\n".join(f"- {n}" for n in file_names) +
                    "\n\n正在解析文档...",
        })

        parsed_docs = []
        all_images = {}

        for i, finfo in enumerate(uploaded):
            yield self._sse("progress", {
                "stage": "parsing",
                "message": f"解析文档 ({i+1}/{len(uploaded)}): {finfo['filename']}",
                "percent": 10 + int(15 * (i + 1) / len(uploaded)),
            })
            filepath = os.path.join(UPLOAD_DIR, f"{finfo['file_id']}_{finfo['filename']}")
            parsed = parse_document(filepath, finfo["filename"])
            parsed_docs.append(parsed)
            all_images[finfo["filename"]] = parsed.all_images

        session["parsed_docs"] = parsed_docs
        session["all_images"] = all_images

        # Check for template
        template_sections = None
        template_path = session.get("template_path")
        if template_path and os.path.exists(template_path):
            from template_parser import parse_template as parse_tpl
            try:
                skeleton = parse_tpl(template_path)
                template_sections = skeleton.sections
            except Exception:
                pass

        docs_info = "\n".join(
            f"- **{p.filename}**：{len(p.sections)}个章节，{len(p.all_images)}张图片，{len(p.all_tables)}个表格"
            for p in parsed_docs
        )
        yield self._sse("message", {"text": f"✅ 解析完成：\n\n{docs_info}\n\n正在AI语义分析..."})

        aq: asyncio.Queue = asyncio.Queue()

        def on_progress(event_type: str, data: dict):
            try:
                aq.put_nowait((event_type, data))
            except Exception:
                pass

        docs_data = [d.to_dict() for d in parsed_docs]
        loop = asyncio.get_event_loop()

        async def run_analysis():
            return await loop.run_in_executor(
                None, analyze_documents, docs_data, template_sections, on_progress,
            )

        analysis_task = asyncio.ensure_future(run_analysis())

        while not analysis_task.done():
            try:
                event_type, data = await asyncio.wait_for(aq.get(), timeout=0.1)
                if event_type == "progress":
                    yield self._sse("progress", data)
            except asyncio.TimeoutError:
                pass

        merge_plan = await analysis_task
        session["merge_plan"] = merge_plan

        yield self._sse("progress", {
            "stage": "analyzed", "message": "分析完成", "percent": 65,
        })

        m = merge_plan.summary
        yield self._sse("message", {
            "text": (
                f"📊 分析结果：\n"
                f"- 正文章节：**{m.get('main_sections', 0)}**个\n"
                f"- 附件：**{m.get('attachments', 0)}**个\n\n"
                f"正在生成统一操作规程..."
            ),
        })

        yield self._sse("progress", {
            "stage": "merging", "message": "生成合并文档...", "percent": 75,
        })

        from merger import generate_merged_docx

        # Get skeleton for styling
        skeleton = None
        template_path = session.get("template_path")
        if template_path and os.path.exists(template_path):
            from template_parser import parse_template as parse_tpl
            try:
                skeleton = parse_tpl(template_path)
            except Exception:
                pass

        output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        await loop.run_in_executor(
            None, generate_merged_docx, merge_plan, docs_data, all_images, output_path,
            merge_plan.cover_title, skeleton, template_path,
        )

        session["output_path"] = output_path
        session["output_filename"] = output_filename
        session["status"] = "done"

        yield self._sse("progress", {"stage": "done", "message": "合并完成！", "percent": 100})
        yield self._sse("result", {
            "download_url": f"/api/download/session/{session_id}",
            "filename": output_filename,
            "summary": m,
            "message": (
                f"🎉 **生成完成！**\n\n"
                f"文档包含：封面、目录、前言、{m.get('main_sections', 0)}个正文章节、"
                f"{m.get('attachments', 0)}个附件。"
            ),
        })

    def add_files_to_session(self, session_id: str, files: List[dict]) -> dict:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        added = []
        for f in files:
            if f["filename"].endswith(".docx"):
                session["uploaded_files"].append(f)
                added.append(f)

        return {
            "session_id": session_id,
            "total_files": len(session["uploaded_files"]),
            "added": len(added),
            "filenames": [f["filename"] for f in session["uploaded_files"]],
        }

    def set_template(self, session_id: str, template_path: str, template_filename: str):
        """Set a template file for the session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        session["template_path"] = template_path
        session["template_filename"] = template_filename
        return {"status": "ok", "template": template_filename}

    def clear_session_files(self, session_id: str):
        session = self.sessions.get(session_id)
        if session:
            session["uploaded_files"] = []
            session["parsed_docs"] = []
            session["all_images"] = {}
            session["merge_plan"] = None
            session["output_path"] = None
            session["output_filename"] = None
            session["status"] = "ready"
            session["history"] = []

    @staticmethod
    def _format_size(bytes_val: int) -> str:
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        return f"{bytes_val / (1024 * 1024):.1f} MB"

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        """Format an SSE message string."""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def _sse_raw(event: str, data: dict) -> str:
        """Same as _sse but without newline at end — for embedding in lists."""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Global agent instance
agent = MergeAgent()
