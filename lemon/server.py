"""Authenticated, same-origin loopback API. No general file or code execution endpoints."""

import secrets
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .gimp import EditorError, GimpAdapter
from .raw import MAX_UPLOAD_BYTES, RAW_EXTENSIONS
from .store import Controller
from .vision import VisionPlanner


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ConsentBody(StrictBody):
    granted: bool


class PlanBody(StrictBody):
    planner: str = "local"
    instruction: str = Field(default="", max_length=500)
    strength: float = Field(default=0.55, ge=0.05, le=1, allow_inf_nan=False)


class RunBody(StrictBody):
    plan_id: str
    plan_hash: str
    step_index: int = Field(ge=0, le=2)
    request_id: str


class RetouchBody(StrictBody):
    node_id: str
    kind: str
    region: list[float] = Field(min_length=4, max_length=4)
    amount: float = Field(ge=0.05, le=0.8, allow_inf_nan=False)


class AcceptRetouchBody(StrictBody):
    candidate_id: str


class ExportBody(StrictBody):
    node_id: str
    format: str = "png"
    long_edge: int | None = Field(default=None, ge=64, le=20000)
    quality: int = Field(default=90, ge=1, le=100)
    compression: int = Field(default=6, ge=0, le=9)


class VersionBody(StrictBody):
    node_id: str


def create_app(data_dir, token=None, port=8765, adapter=None):
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    adapter = adapter or GimpAdapter(data_dir / "runtime")
    vision = VisionPlanner()
    controller = Controller(data_dir / "projects", adapter, vision)
    token = token or secrets.token_urlsafe(32)
    host = f"127.0.0.1:{port}"
    origin = "http://" + host
    app = FastAPI(title="Lemon", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.controller, app.state.token = controller, token

    @app.middleware("http")
    async def protect(request: Request, call_next):
        if request.headers.get("host") != host:
            return JSONResponse({"detail": "Invalid Host."}, 403)
        provided_origin = request.headers.get("origin")
        if provided_origin is not None and provided_origin != origin:
            return JSONResponse({"detail": "Invalid Origin."}, 403)
        if request.method not in {"GET", "HEAD"} and provided_origin != origin:
            return JSONResponse({"detail": "Same-origin requests are required."}, 403)
        if request.headers.get("sec-fetch-site") in {"cross-site"}:
            return JSONResponse({"detail": "Cross-site requests are forbidden."}, 403)
        if request.url.path.startswith("/api/"):
            credential = request.cookies.get("lemon_session", "")
            if request.url.path == "/api/session":
                credential = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not secrets.compare_digest(credential, token):
                return JSONResponse(
                    {"detail": "Open Lemon using the private launch URL from your terminal."}, 401
                )
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid content length."}, 400)
        if content_length > 2 * MAX_UPLOAD_BYTES + 1024 * 1024:
            return JSONResponse({"detail": "Upload is too large."}, 413)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)}, 400)

    @app.exception_handler(EditorError)
    async def editor_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 503)

    @app.post("/api/session")
    def session():
        response = JSONResponse({"ok": True})
        response.set_cookie("lemon_session", token, httponly=True, samesite="strict", path="/", max_age=86400)
        return response

    @app.get("/api/status")
    def status():
        return {
            "gimp_available": bool(adapter.executable),
            "environment": adapter.environment,
            "planner": "Local reference analysis",
            "cloud_ai": "Configured; permission required" if vision.available else "Not connected",
            "vision_available": vision.available,
            "vision_model": vision.model,
            "privacy": "Photos stay on this computer",
        }

    @app.post("/api/editor/check")
    def check():
        return adapter.discover()

    @app.get("/api/projects")
    def projects():
        return controller.list_projects()

    @app.post("/api/projects")
    async def create(
        name: str = Form(...), source: UploadFile = File(...), reference: UploadFile = File(...)
    ):
        with tempfile.TemporaryDirectory(dir=data_dir, prefix="import-") as directory:
            paths = []
            try:
                for index, upload in enumerate([source, reference]):
                    suffix = Path(upload.filename or "").suffix.lower()
                    path = Path(directory) / (str(index) + (suffix if suffix in RAW_EXTENSIONS else ""))
                    count = 0
                    with path.open("wb") as output:
                        while chunk := await upload.read(1024 * 1024):
                            count += len(chunk)
                            if count > MAX_UPLOAD_BYTES:
                                raise ValueError("Each upload must be smaller than 128 MB.")
                            output.write(chunk)
                    paths.append(path)
                return await run_in_threadpool(controller.create, name, *paths)
            finally:
                await source.close()
                await reference.close()

    @app.get("/api/projects/{project_id}")
    def history(project_id: str):
        return controller.history(project_id)

    @app.post("/api/projects/{project_id}/consent")
    def consent(project_id: str, body: ConsentBody):
        return controller.consent(project_id, body.granted)

    @app.post("/api/projects/{project_id}/plans")
    def plan(project_id: str, body: PlanBody):
        return controller.plan(project_id, body.strength, body.planner, body.instruction)

    @app.post("/api/projects/{project_id}/run")
    def run(project_id: str, body: RunBody):
        return controller.run_step(project_id, **body.model_dump())

    @app.post("/api/projects/{project_id}/restore")
    def restore(project_id: str, body: VersionBody):
        return controller.restore(project_id, body.node_id)

    @app.post("/api/projects/{project_id}/retouches")
    def retouch(project_id: str, body: RetouchBody):
        return controller.retouch_preview(project_id, **body.model_dump())

    @app.post("/api/projects/{project_id}/retouches/accept")
    def accept_retouch(project_id: str, body: AcceptRetouchBody):
        return controller.accept_retouch(project_id, body.candidate_id)

    @app.post("/api/projects/{project_id}/exports")
    def export(project_id: str, body: ExportBody):
        return controller.export(project_id, **body.model_dump())

    @app.get("/api/projects/{project_id}/assets/{role}")
    def asset(project_id: str, role: str, asset_id: str | None = None):
        path = controller.asset(project_id, role, asset_id)
        return FileResponse(path, filename=("lemon" + path.suffix) if role == "export" else None)

    static = Path(__file__).parent / "static"

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app
