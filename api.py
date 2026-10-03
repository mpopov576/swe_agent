import json
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

from main import main as run_agent


ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "api-jobs"

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def read_job(job_id):
    path = JOBS / str(job_id) / "status.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")

    return json.loads(path.read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(app):
    key = os.environ.get("SWE_API_KEY", "")
    if len(key) < 24:
        raise RuntimeError("Set SWE_API_KEY to at least 24 characters")

    JOBS.mkdir(exist_ok=True)

    # A previous server shutdown may have interrupted a job.
    for path in JOBS.glob("*/status.json"):
        job = json.loads(path.read_text(encoding="utf-8"))
        if job["status"] in ("queued", "running"):
            job["status"] = "interrupted"
            write_json(path, job)

    app.state.api_key = key
    app.state.busy = threading.Lock()
    app.state.executor = ThreadPoolExecutor(max_workers=1)

    try:
        yield
    finally:
        # Allow an active job to finish during normal shutdown.
        app.state.executor.shutdown(wait=True)


app = FastAPI(
    title="Repository Repair API",
    version="0.1.0",
    lifespan=lifespan,
)


def authenticate(key: str | None = Depends(api_key_header)):
    if key is None or not secrets.compare_digest(
        key.encode("utf-8"),
        app.state.api_key.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid API key")


class JobRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=2000)
    issue_text: str = Field(min_length=1, max_length=8000)

    @field_validator("repo_url", "issue_text")
    @classmethod
    def reject_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value


def execute_job(job, request):
    directory = JOBS / job["job_id"]
    started = time.perf_counter()

    try:
        job["status"] = "running"
        write_json(directory / "status.json", job)

        backend = os.environ.get(
            "SWE_LLM_BACKEND",
            "ollama",
        ).strip().lower()

        default_model = (
            "qwen.qwen3-coder-30b-a3b-v1:0"
            if backend == "bedrock"
            else "qwen3:14b"
        )

        result = run_agent(
            repo_url=request.repo_url,
            issue_text=request.issue_text,
            agent_model=os.environ.get(
                "SWE_AGENT_MODEL",
                default_model,
            ),
            judge_model=os.environ.get(
                "SWE_JUDGE_MODEL",
                default_model,
            ),
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            total_seconds=900,
            request_timeout=300,
            # Save the candidate without prompting or committing.
            approval_callback=lambda diff, verdict: False,
        )

        write_json(directory / "result.json", result)

        patch = (result.get("diff") or {}).get("git_diff", "")
        patch_available = bool(
            result.get("patch_complete") and patch.strip()
        )

        if patch_available:
            (directory / "patch.diff").write_bytes(patch.encode("utf-8"))

        job.update(
            status="finished",
            agent_status=result.get("status"),
            judge_result=(result.get("verdict") or {}).get("result"),
            patch_available=patch_available,
        )

    except Exception as error:
        job.update(
            status="error",
            error=f"{type(error).__name__}: {error}"[:2000],
        )

    finally:
        job["duration_seconds"] = round(
            time.perf_counter() - started, 2
        )
        try:
            write_json(directory / "status.json", job)
        finally:
            app.state.busy.release()


@app.get("/health")
def health():
    # Liveness only; does not test Docker or Ollama.
    return {"status": "ok"}


@app.post(
    "/jobs",
    status_code=202,
    dependencies=[Depends(authenticate)],
)
def submit_job(request: JobRequest):
    if not app.state.busy.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A job is already running. Try again after it finishes.",
        )

    job_id = str(uuid4())
    directory = JOBS / job_id
    job = {
        "job_id": job_id,
        "status": "queued",
        "agent_status": None,
        "judge_result": None,
        "patch_available": False,
        "duration_seconds": None,
        "error": None,
    }

    try:
        directory.mkdir()
        write_json(directory / "request.json", request.model_dump())
        write_json(directory / "status.json", job)
        app.state.executor.submit(execute_job, job, request)
    except Exception:
        app.state.busy.release()
        raise

    return {
        "job_id": job_id,
        "status_url": f"/jobs/{job_id}",
        "result_url": f"/jobs/{job_id}/result",
        "patch_url": f"/jobs/{job_id}/patch",
    }


@app.get("/jobs/{job_id}", dependencies=[Depends(authenticate)])
def job_status(job_id: UUID):
    return read_job(job_id)


@app.get("/jobs/{job_id}/result", dependencies=[Depends(authenticate)])
def job_result(job_id: UUID):
    job = read_job(job_id)
    if job["status"] != "finished":
        raise HTTPException(
            status_code=409,
            detail="No completed agent result is available",
        )

    return FileResponse(
        JOBS / str(job_id) / "result.json",
        media_type="application/json",
        filename="result.json",
    )


@app.get("/jobs/{job_id}/patch", dependencies=[Depends(authenticate)])
def job_patch(job_id: UUID):
    job = read_job(job_id)
    if not job.get("patch_available"):
        raise HTTPException(
            status_code=409,
            detail="No complete nonempty patch is available",
        )

    return FileResponse(
        JOBS / str(job_id) / "patch.diff",
        media_type="text/plain",
        filename="patch.diff",
    )