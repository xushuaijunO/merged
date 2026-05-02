"""FastAPI backend for Word document merging — with chat-based AI agent."""

import os
import json
import uuid
import asyncio
import base64
import logging
from datetime import datetime
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from config import UPLOAD_DIR, ANTHROPIC_API_KEY
from doc_parser import parse_document
from analyzer import analyze_documents
from merger import generate_merged_docx
from agent import agent

app = FastAPI(title="Word文档智能合并助手", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy task-based merge storage
tasks: Dict[str, dict] = {}


# ============================================================
# Health Check
# ============================================================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "has_api_key": bool(ANTHROPIC_API_KEY)}


# ============================================================
# Legacy Upload & Merge (kept for backward compatibility)
# ============================================================

@app.post("/api/upload")
async def upload_files(req: Request):
    """Upload multiple docx files via base64-encoded JSON."""
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须为JSON格式")

    files_data = body.get("files", [])
    if not files_data:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    uploaded = []
    for fdata in files_data:
        filename = fdata.get("filename", "unknown.docx")
        content_b64 = fdata.get("content", "")

        if not filename.endswith(".docx"):
            raise HTTPException(status_code=400, detail=f"仅支持docx格式: {filename}")

        try:
            content = base64.b64decode(content_b64)
        except Exception:
            raise HTTPException(status_code=400, detail=f"文件base64编码无效: {filename}")

        file_id = uuid.uuid4().hex[:8]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        uploaded.append({
            "file_id": file_id,
            "filename": filename,
            "size": len(content),
            "path": file_path,
        })

    return {"files": uploaded, "count": len(uploaded)}


async def _run_merge(task_id: str, file_infos: list):
    """Run merge pipeline and update task via SSE queue."""
    task = tasks.get(task_id)
    if not task:
        return
    queue = task["queue"]

    async def emit(event: str, data: dict):
        await queue.put({"event": event, "data": json.dumps(data, ensure_ascii=False)})

    try:
        await emit("progress", {"stage": "parsing", "message": "开始解析文档...", "percent": 5})
        parsed_docs = []
        all_images = {}

        for i, info in enumerate(file_infos):
            await emit("progress", {
                "stage": "parsing",
                "message": f"解析文档 ({i+1}/{len(file_infos)}): {info['filename']}",
                "percent": 5 + int(15 * (i + 1) / len(file_infos)),
            })
            parsed = parse_document(info["path"], info["filename"])
            parsed_docs.append(parsed)
            all_images[info["filename"]] = parsed.all_images

        await emit("progress", {"stage": "analyzing", "message": "AI语义分析中...", "percent": 25})
        docs_data = [d.to_dict() for d in parsed_docs]
        loop = asyncio.get_event_loop()
        merge_plan = await loop.run_in_executor(None, analyze_documents, docs_data)
        await emit("progress", {"stage": "analyzing", "message": "分析完成", "percent": 65})

        await emit("progress", {"stage": "merging", "message": "生成合并文档...", "percent": 75})
        output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        await loop.run_in_executor(None, generate_merged_docx, merge_plan, docs_data, all_images, output_path)

        task["output_path"] = output_path
        task["output_filename"] = output_filename
        task["summary"] = merge_plan.summary
        task["status"] = "done"

        await emit("progress", {
            "stage": "done",
            "message": "合并完成！",
            "percent": 100,
            "summary": merge_plan.summary,
            "download_url": f"/api/download/{task_id}",
        })

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        await emit("error", {"message": f"合并失败: {str(e)}"})


@app.post("/api/merge")
async def merge_files(req: Request):
    """Trigger merge for uploaded files (legacy)."""
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须为JSON格式")

    file_infos = body.get("file_paths", [])
    if len(file_infos) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个文档进行合并")

    for info in file_infos:
        if not os.path.exists(info["path"]):
            raise HTTPException(status_code=404, detail=f"文件不存在: {info['filename']}")

    task_id = uuid.uuid4().hex[:12]
    queue = asyncio.Queue()
    tasks[task_id] = {
        "id": task_id,
        "status": "running",
        "queue": queue,
        "file_count": len(file_infos),
        "output_path": None,
        "error": None,
    }

    asyncio.create_task(_run_merge(task_id, file_infos))
    return {"task_id": task_id, "status": "started"}


@app.get("/api/status/{task_id}")
async def status_stream(task_id: str):
    """SSE endpoint for legacy merge progress."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    queue = task["queue"]

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                event = msg.get("event", "message")
                data = msg.get("data", "{}")
                yield f"event: {event}\ndata: {data}\n\n"
                try:
                    payload = json.loads(data)
                    if event == "error" or payload.get("stage") == "done":
                        break
                except (json.JSONDecodeError, KeyError):
                    pass
            except asyncio.TimeoutError:
                yield f": ping\n\n"
                if task.get("status") in ("done", "error"):
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """Download the merged docx file (legacy)."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] == "running":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    if task["status"] == "error":
        raise HTTPException(status_code=500, detail=f"任务失败: {task.get('error', '未知错误')}")

    output_path = task.get("output_path")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="输出文件不存在")

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=task.get("output_filename", "merged.docx"),
    )


# ============================================================
# Chat-based Agent API (new)
# ============================================================

@app.post("/api/chat/start")
async def chat_start():
    """Create a new chat session."""
    session_id = agent.create_session()
    return {
        "session_id": session_id,
        "message": "会话已创建，请上传文档并描述你的合并需求。",
    }


@app.post("/api/chat/{session_id}/upload")
async def chat_upload(session_id: str, req: Request):
    """Upload files into a chat session."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须为JSON格式")

    files_data = body.get("files", [])
    if not files_data:
        raise HTTPException(status_code=400, detail="请上传文件")

    uploaded = []
    for fdata in files_data:
        filename = fdata.get("filename", "unknown.docx")
        content_b64 = fdata.get("content", "")

        if not filename.endswith(".docx"):
            raise HTTPException(status_code=400, detail=f"仅支持docx格式: {filename}")

        try:
            content = base64.b64decode(content_b64)
        except Exception:
            raise HTTPException(status_code=400, detail=f"文件base64编码无效: {filename}")

        file_id = uuid.uuid4().hex[:8]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        file_info = {
            "file_id": file_id,
            "filename": filename,
            "size": len(content),
            "path": file_path,
        }
        uploaded.append(file_info)

    result = agent.add_files_to_session(session_id, uploaded)
    return result


@app.post("/api/chat/{session_id}/message")
async def chat_message(session_id: str, req: Request):
    """Send a message to the agent and receive SSE streaming response."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须为JSON格式")

    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def event_generator():
        async for sse_msg in agent.handle_message(session_id, user_message):
            yield sse_msg

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/chat/{session_id}/history")
async def chat_history(session_id: str):
    """Get conversation history for a session."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")

    uploaded = [
        {"filename": f["filename"], "size": f.get("size", 0)}
        for f in sess["uploaded_files"]
    ]

    return {
        "session_id": session_id,
        "status": sess["status"],
        "files": uploaded,
        "history": sess["history"],
    }


@app.get("/api/download/session/{session_id}")
async def download_session_result(session_id: str):
    """Download the merged docx from a chat session."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not sess.get("output_path") or not os.path.exists(sess["output_path"]):
        raise HTTPException(status_code=400, detail="合并尚未完成或文件不存在")
    if not sess.get("output_path") or not os.path.exists(sess["output_path"]):
        raise HTTPException(status_code=404, detail="输出文件不存在")

    return FileResponse(
        sess["output_path"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=sess.get("output_filename", "merged.docx"),
    )


@app.post("/api/chat/{session_id}/clear")
async def chat_clear(session_id: str):
    """Clear uploaded files and reset session for a new merge."""
    sess = agent.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    agent.clear_session_files(session_id)
    return {"status": "ok", "message": "会话已重置，可以开始新的合并。"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
