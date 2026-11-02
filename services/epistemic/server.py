"""Local vision service. Meta API calls stay in the Next.js server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import ALLOWED_TYPES, MAX_UPLOAD_BYTES, MEMORIES_DIR
from .hypotheses import attach_external_image, sketch_hypothesis
from .links import propose_for, set_link_status
from .pipeline import build_memory, read_upload, utc_now
from .samples import living_room, record_detail
from .store import list_memories, load_memory, load_rgb, save_memory, update_memory, write_asset
from . import agent as agent_mod
from .enrich import attach_sam, attach_scene, decode_mask_png

app = FastAPI(title="ChronoSpace epistemic engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TestimonyBody(BaseModel):
    text: str
    speaker: str | None = None
    source: str = "typed"
    transcript_model: str | None = None


class HypothesisBody(BaseModel):
    claim: str
    speaker: str | None = None


class AgentBody(BaseModel):
    message: str


class ToolBody(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class LinkBody(BaseModel):
    status: str


class DateBody(BaseModel):
    capture_time: str


class ActiveHypothesisBody(BaseModel):
    hypothesis_id: str | None = None


class InvocationBody(BaseModel):
    invocation: dict[str, Any]


class MuseSceneBody(BaseModel):
    title: str | None = None
    summary: str
    audio_elements: list[str] = Field(default_factory=list)
    invocation: dict[str, Any]


class SamAttachBody(BaseModel):
    prompt: str
    object_id: str
    width: int
    height: int
    mask_png_base64: str | None = None
    mask_raw_base64: str | None = None
    confidence: float | None = None
    invocation: dict[str, Any]


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "memories": len(list_memories()),
        "depth_model": os.environ.get("DEPTH_MODEL_PATH", "models/depth_anything_v2_small_q4.onnx"),
    }


@app.get("/memories")
def memories() -> dict:
    return {"memories": list_memories()}


@app.get("/memories/{memory_id}")
def memory(memory_id: str) -> dict:
    try:
        record = load_memory(memory_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Memory not found.") from exc
    from .store import load_graph

    graph = load_graph()
    record["links"] = [
        link
        for link in graph["links"]
        if memory_id in {link["a"]["memory_id"], link["b"]["memory_id"]}
    ]
    record["collection_timeline"] = _collection_timeline()
    return record


@app.post("/reconstruct")
async def reconstruct(
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(False),
    external_models: bool = Form(False),
    use_capture_time: bool = Form(False),
    note: str = Form(""),
):
    if not rights_confirmed:
        raise HTTPException(400, "Confirm you have the right to process this photograph.")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Upload a JPEG, PNG, or WebP photograph.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Photographs are limited to 12 MB.")
    if len(data) < 32:
        raise HTTPException(400, "The upload is empty.")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(stage: str, status: str, detail: str) -> None:
        payload = {"event": "stage", "stage": stage, "status": status, "detail": detail, "at": utc_now()}
        fut = asyncio.run_coroutine_threadsafe(queue.put(payload), loop)
        fut.result()

    def work() -> None:
        try:
            rgb, capture, reliability = read_upload(data, use_capture_time)
            consent = {
                "rights_confirmed": True,
                "external_models": bool(external_models),
                "use_capture_time": bool(use_capture_time),
                "accepted_at": utc_now(),
                "note": note.strip() or None,
            }
            memory, images = build_memory(
                rgb,
                consent=consent,
                capture_time=capture,
                capture_time_reliability=reliability,
                emit=emit,
            )
            if note.strip():
                memory["scene_description"]["text"] = note.strip() + " " + memory["scene_description"]["text"]
            save_memory(memory, images)
            propose_for(memory)
            update_memory(memory)
            asyncio.run_coroutine_threadsafe(queue.put({"event": "done", "memory": memory}), loop).result()
        except ValueError as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put({"event": "error", "message": str(exc)}), loop
            ).result()
        except Exception as exc:  # noqa: BLE001
            asyncio.run_coroutine_threadsafe(
                queue.put({"event": "error", "message": f"Reconstruction failed: {exc}"}), loop
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    async def generate():
        runner = asyncio.create_task(asyncio.to_thread(work))
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
        await runner

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/memories/{memory_id}/testimony")
def add_testimony(memory_id: str, body: TestimonyBody) -> dict:
    memory = _memory_or_404(memory_id)
    result, memory, actions = agent_mod.execute_tool(
        memory,
        "add_memory_annotation",
        {"text": body.text, "speaker": body.speaker},
    )
    if body.source != "typed" and "testimony" in result:
        result["testimony"]["source"] = body.source
        result["testimony"]["transcript_model"] = body.transcript_model
        update_memory(memory)
    return {"result": result, "actions": actions, "memory": memory}


@app.post("/memories/{memory_id}/hypothesis")
def add_hypothesis(memory_id: str, body: HypothesisBody) -> dict:
    memory = _memory_or_404(memory_id)
    result, memory, actions = agent_mod.execute_tool(
        memory,
        "create_alternative_hypothesis",
        {"claim": body.claim, "speaker": body.speaker},
    )
    return {"result": result, "actions": actions, "memory": load_memory(memory_id)}


@app.post("/memories/{memory_id}/hypothesis/external")
async def add_external_hypothesis(
    memory_id: str,
    claim: str = Form(...),
    model_id: str = Form(...),
    live: bool = Form(False),
    file: UploadFile = File(...),
):
    memory = _memory_or_404(memory_id)
    data = await file.read()
    from .pipeline import read_upload

    generated, _, _ = read_upload(data, False)
    rgb = load_rgb(memory_id)
    built = attach_external_image(memory, rgb, generated, claim, None, model_id, live)
    if not built.get("created"):
        raise HTTPException(400, built.get("reason", "Hypothesis was not created."))
    write_asset(memory_id, f"hypotheses/{built['record']['id']}.png", built["rgba"])
    generated_mask = (built["rgba"][..., 3] > 0).astype(np.uint8) * 255
    write_asset(memory_id, "generated.png", generated_mask)
    memory["hypotheses"].append(built["record"])
    memory["provenances"].append(built["provenance"])
    memory["active_hypothesis_id"] = built["record"]["id"]
    memory["assets"]["hypothesis"] = built["record"]["artifact_url"]
    if live:
        memory["invocations"].append(
            {
                "id": built["provenance"]["id"],
                "model_id": model_id,
                "provider": "meta",
                "task": "image_hypothesis",
                "status": "succeeded",
                "live": True,
                "started_at": built["record"]["created_at"],
                "ended_at": built["record"]["created_at"],
                "duration_ms": None,
                "output_summary": "Muse Image pixels were composited inside the unobserved mask.",
                "error": None,
            }
        )
    update_memory(memory)
    return {"memory": memory}


@app.post("/memories/{memory_id}/active-hypothesis")
def active_hypothesis(memory_id: str, body: ActiveHypothesisBody) -> dict:
    memory = _memory_or_404(memory_id)
    if body.hypothesis_id is None:
        memory["active_hypothesis_id"] = None
        update_memory(memory)
        return {"memory": memory}
    match = next((item for item in memory["hypotheses"] if item["id"] == body.hypothesis_id), None)
    if match is None:
        raise HTTPException(404, "Hypothesis not found.")
    memory["active_hypothesis_id"] = match["id"]
    memory["assets"]["hypothesis"] = match["artifact_url"]
    update_memory(memory)
    return {"memory": memory}


@app.post("/memories/{memory_id}/invocations")
def add_invocation(memory_id: str, body: InvocationBody) -> dict:
    memory = _memory_or_404(memory_id)
    memory["invocations"].append(body.invocation)
    update_memory(memory)
    return {"ok": True}


@app.post("/memories/{memory_id}/date")
def assert_date(memory_id: str, body: DateBody) -> dict:
    memory = _memory_or_404(memory_id)
    text = body.capture_time.strip()
    if not text:
        raise HTTPException(400, "A date needs text.")
    memory["photograph"]["capture_time"] = text
    memory["photograph"]["capture_time_reliability"] = "user_asserted"
    update_memory(memory)
    return {"memory": memory}


@app.post("/agent/turn")
def agent_turn(body: AgentBody, memory_id: str) -> dict:
    memory = _memory_or_404(memory_id)
    return agent_mod.local_turn(memory, body.message)


@app.post("/agent/tool")
def agent_tool(body: ToolBody, memory_id: str) -> dict:
    memory = _memory_or_404(memory_id)
    result, memory, actions = agent_mod.execute_tool(memory, body.name, body.args)
    return {"result": result, "actions": actions, "memory_id": memory["id"]}


@app.post("/memories/{memory_id}/scene")
def scene(memory_id: str, body: MuseSceneBody) -> dict:
    memory = _memory_or_404(memory_id)
    if not memory["consent"].get("external_models"):
        raise HTTPException(403, "This memory was not consented for external models.")
    updated = attach_scene(memory, body.summary, body.title, body.audio_elements, body.invocation)
    return {"memory": updated}


@app.post("/memories/{memory_id}/sam")
def sam(memory_id: str, body: SamAttachBody) -> dict:
    memory = _memory_or_404(memory_id)
    if not memory["consent"].get("external_models"):
        raise HTTPException(403, "This memory was not consented for external models.")
    if body.mask_png_base64:
        mask_png = decode_mask_png(body.mask_png_base64)
    elif body.mask_raw_base64:
        import base64
        import io

        raw = base64.b64decode(body.mask_raw_base64)
        expected = body.width * body.height
        if len(raw) != expected:
            raise HTTPException(400, "SAM mask byte count does not match the photograph size.")
        image = Image.frombytes("L", (body.width, body.height), raw)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        mask_png = buffer.getvalue()
    else:
        raise HTTPException(400, "A SAM mask is required.")
    updated = attach_sam(
        memory,
        prompt=body.prompt,
        object_id=body.object_id,
        mask_png=mask_png,
        confidence=body.confidence,
        invocation=body.invocation,
    )
    return {"memory": updated}


class SummarizeBody(BaseModel):
    trace: list[dict[str, Any]]


@app.post("/agent/summarize")
def summarize(body: SummarizeBody) -> dict:
    return {"narration": agent_mod.summarize_trace(body.trace)}


@app.post("/links/{link_id}")
def update_link(link_id: str, body: LinkBody) -> dict:
    try:
        link = set_link_status(link_id, body.status)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Link not found.") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"link": link}


@app.get("/graph")
def graph() -> dict:
    from .store import load_graph

    payload = load_graph()
    payload["memories"] = list_memories()
    payload["timeline"] = _collection_timeline()
    return payload


@app.post("/seed")
def seed() -> dict:
    return {"memories": seed_samples()}


def seed_samples() -> list[dict]:
    existing = list_memories()
    if any(item.get("sample") for item in existing):
        return existing
    made = []
    specs = [
        (
            record_detail,
            "Painted reference, closer view",
            "A second painted view used to propose — not assert — that a record player may be the same kind of object. No capture date is stored.",
        ),
        (
            living_room,
            "Painted reference interior",
            "Painted in this repository as a demonstration photograph. It is not a historical picture and it has no camera timestamp. Vision output is from local models on these pixels, not a live Meta API call.",
        ),
    ]
    for painter, title, note in specs:
        rgb, _truth = painter()
        consent = {
            "rights_confirmed": True,
            "external_models": False,
            "use_capture_time": False,
            "accepted_at": utc_now(),
            "note": "Seeded demonstration image.",
        }
        memory, images = build_memory(
            rgb,
            consent=consent,
            capture_time=None,
            capture_time_reliability="unknown",
            sample=True,
            sample_note=note,
            title=title,
        )
        save_memory(memory, images)
        propose_for(memory)
        update_memory(memory)
        made.append(memory["id"])
    return list_memories()


def _memory_or_404(memory_id: str) -> dict:
    try:
        return load_memory(memory_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Memory not found.") from exc


def _collection_timeline() -> list[dict]:
    dated = []
    for summary in list_memories():
        if summary.get("capture_time") and summary.get("capture_time_reliability") in {"exif", "user_asserted"}:
            dated.append(
                {
                    "memory_id": summary["id"],
                    "title": summary["title"],
                    "at": summary["capture_time"],
                    "reliability": summary["capture_time_reliability"],
                }
            )
    dated.sort(key=lambda item: item["at"])
    if len(dated) < 2:
        return []
    return dated


@app.on_event("startup")
def _startup() -> None:
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    if os.environ.get("CHRONOSPACE_SKIP_SEED") == "1":
        return
    seed_samples()
