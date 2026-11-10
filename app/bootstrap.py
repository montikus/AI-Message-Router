"""One-shot Compose initializer: download, validate and warm the local model."""

import json
import logging
import time

import httpx

from app.agent import RoutingAgent
from app.config import Settings
from app.mailer import EmailTool

# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
from app.schemas import MessageRequest

logger = logging.getLogger(__name__)


def initialize() -> None:
    settings = Settings()
    with httpx.Client(
        base_url=settings.ollama_base_url,
        timeout=httpx.Timeout(900, connect=10),
        trust_env=False,
    ) as client:
        for attempt in range(1, 4):
            try:
                shown = client.post("/api/show", json={"model": settings.ollama_model})
                if shown.status_code == 404:
                    last_status = None
                    completed = False
                    with client.stream(
                        "POST", "/api/pull", json={"model": settings.ollama_model, "stream": True}
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if not line:
                                continue
                            event = json.loads(line)
                            if event.get("error"):
                                raise RuntimeError(event["error"])
                            status = event.get("status")
                            if status != last_status:
                                logger.info("Model download: %s", status)
                                last_status = status
                            completed = completed or status == "success"
                    if not completed:
                        raise RuntimeError("Model download did not complete")
                    shown = client.post("/api/show", json={"model": settings.ollama_model})
                shown.raise_for_status()
                if "tools" not in shown.json().get("capabilities", []):
                    raise RuntimeError("Configured model does not support tools")
                break
            except (httpx.HTTPError, RuntimeError):
                if attempt == 3:
                    raise
                logger.warning("Model initialization attempt %s failed; retrying", attempt)
                time.sleep(5)

        logger.info("Warming model and checking native tool calling (no email is sent)")
        agent = RoutingAgent(settings, client, EmailTool(settings))
        agent.select_call(
            MessageRequest(email="startup@example.com", message="Wniosek o urlop jutro")
        )
        logger.info("Model %s is ready", settings.ollama_model)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    initialize()
