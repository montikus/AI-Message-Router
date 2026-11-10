import logging
import smtplib
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agent import RoutingAgent
from app.config import Settings
from app.errors import RouterError
from app.mailer import EmailTool
from app.schemas import ErrorResponse, MessageRequest, MessageResponse

logger = logging.getLogger(__name__)


# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
def create_app(
    settings: Settings | None = None, transport: httpx.BaseTransport | None = None
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with httpx.Client(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(settings.ollama_timeout, connect=10),
            transport=transport,
            trust_env=False,
        ) as client:
            application.state.ollama = client
            application.state.email_tool = EmailTool(settings)
            application.state.agent = RoutingAgent(settings, client, application.state.email_tool)
            application.state.capacity = BoundedSemaphore(settings.max_concurrent_requests)
            yield

    application = FastAPI(
        title="AI Message Router",
        description="Local Ollama agent routes requests by calling its send_email tool.",
        version="1.0.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    @application.exception_handler(RouterError)
    async def router_error_handler(request: Request, exc: RouterError) -> JSONResponse:
        logger.warning("routing_failed error=%s", type(exc).__name__)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.post(
        "/api/v1/messages",
        response_model=MessageResponse,
        status_code=201,
        tags=["Messages"],
        responses={
            502: {"model": ErrorResponse, "description": "Invalid tool call or SMTP failure"},
            503: {"model": ErrorResponse, "description": "Ollama unavailable or router busy"},
            504: {"model": ErrorResponse, "description": "Ollama timeout before email dispatch"},
        },
    )
    def route_message(payload: MessageRequest, request: Request):
        """Return 201 only after the SMTP server accepts the message."""
        capacity = request.app.state.capacity
        if not capacity.acquire(blocking=False):
            return JSONResponse(
                status_code=503,
                content={"detail": "Router is busy; retry later."},
                headers={"Retry-After": "10"},
            )
        try:
            return request.app.state.agent.run(payload, uuid4())
        finally:
            capacity.release()

    @application.get("/health/live", tags=["Health"])
    def live():
        return {"status": "alive"}

    @application.get("/health/ready", tags=["Health"], responses={503: {"model": ErrorResponse}})
    def ready(request: Request):
        try:
            result = request.app.state.ollama.post(
                "/api/show", json={"model": settings.ollama_model}, timeout=5
            )
            result.raise_for_status()
            if "tools" not in result.json().get("capabilities", []):
                raise ValueError("Model does not support tool calling")
            request.app.state.email_tool.check_connection()
        except (httpx.HTTPError, ValueError, AttributeError, OSError, smtplib.SMTPException):
            return JSONResponse(status_code=503, content={"detail": "Dependencies are not ready."})
        return {"status": "ready", "model": settings.ollama_model}

    return application


app = create_app()
