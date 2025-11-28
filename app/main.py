# app/main.py
import os
import uuid
import hashlib

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
import redis

from .celery_app import celery

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB_HASH = int(os.getenv("REDIS_DB_HASH", "2"))  # for hash->job mapping

PDF_OUTPUT_DIR = os.getenv("PDF_OUTPUT_DIR", "/data/pdfs")

# Redis used only for hash->job_id mapping (dedupe)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_HASH, decode_responses=True)

app = FastAPI(title="HTML → PDF Service (FastAPI + Celery)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def pdf_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def map_celery_state(state: str) -> str:
    """
    Map Celery states to simpler API states.
    """
    if state in ("PENDING", "RECEIVED", "RETRY"):
        return "PENDING"
    if state in ("STARTED",):
        return "RUNNING"
    if state == "SUCCESS":
        return "DONE"
    if state == "FAILURE":
        return "FAILED"
    return state or "UNKNOWN"


@app.post("/generate")
async def generate(request: Request):
    """
    Accept raw HTML (body = <html>...</html>).
    - Compute hash
    - If hash seen before -> return existing job_id + status
    - Else -> create job_id, enqueue Celery task, save hash->job_id
    """
    body = await request.body()
    if not body.strip():
        raise HTTPException(status_code=400, detail="Empty HTML body")

    h = pdf_hash(body)
    hash_key = f"pdf_hash:{h}"

    # existing_job_id = r.get(hash_key)
    # if existing_job_id:
    #     # Check Celery state
    #     res = AsyncResult(existing_job_id, app=celery)
    #     status = map_celery_state(res.state)
    #     return {
    #         "status": status,
    #         "job_id": existing_job_id,
    #         "cached": True,
    #     }

    # New job
    html = body.decode("utf-8")
    job_id = str(uuid.uuid4())

    # Enqueue Celery task with our custom job_id
    task = celery.send_task("generate_pdf", args=[html, job_id], task_id=job_id)

    # Store hash -> job_id
    r.set(hash_key, job_id)

    return {
        "status": "QUEUED",
        "job_id": job_id,
        "cached": False,
    }


@app.get("/status/{job_id}")
async def status(job_id: str):
    res = AsyncResult(job_id, app=celery)
    state = res.state
    api_status = map_celery_state(state)

    if state == "FAILURE":
        # res.info is the exception, may contain message
        err = str(res.info)
        return {"status": api_status, "job_id": job_id, "error": err}

    return {"status": api_status, "job_id": job_id}


@app.get("/download/{job_id}")
async def download(job_id: str):
    res = AsyncResult(job_id, app=celery)
    if res.state != "SUCCESS":
        raise HTTPException(status_code=409, detail=f"Job not ready (state={res.state})")

    result = res.result or {}
    pdf_path = result.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF path missing in task result")

    # (Optionally) verify file exists
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF file missing on server")

    filename = os.path.basename(pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@app.get("/")
async def health():
    # quick health check
    try:
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "redis_error", "detail": str(e)})


