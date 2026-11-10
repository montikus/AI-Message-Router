import json

import httpx

# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
import pytest

from app import bootstrap
from app.config import Settings
from app.errors import InvalidToolCall


def setup_initializer(monkeypatch, handler):
    client = httpx.Client(base_url="http://ollama:11434", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(bootstrap.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(bootstrap, "Settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(bootstrap.time, "sleep", lambda seconds: None)


def valid_warmup():
    return httpx.Response(
        200,
        json={
            "done": True,
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "send_email",
                            "arguments": {"recipient": "kadry@example.com"},
                        }
                    }
                ],
            },
        },
    )


@pytest.mark.parametrize("cached", [False, True])
def test_bootstrap_downloads_only_if_missing_and_checks_tool_call(monkeypatch, cached):
    paths = []

    def ollama(request):
        paths.append(request.url.path)
        if request.url.path == "/api/show":
            if not cached and paths.count("/api/show") == 1:
                return httpx.Response(404, json={"error": "missing model"})
            return httpx.Response(200, json={"capabilities": ["tools"]})
        if request.url.path == "/api/pull":
            assert json.loads(request.content)["stream"] is True
            return httpx.Response(200, text='{"status":"pulling"}\n{"status":"success"}\n')
        if request.url.path == "/api/chat":
            return valid_warmup()
        pytest.fail(f"Unexpected request: {request.url}")

    setup_initializer(monkeypatch, ollama)
    bootstrap.initialize()
    assert paths.count("/api/pull") == (0 if cached else 1)
    assert paths[-1] == "/api/chat"


def test_bootstrap_does_not_succeed_on_partial_download(monkeypatch):
    paths = []

    def ollama(request):
        paths.append(request.url.path)
        if request.url.path == "/api/show":
            return httpx.Response(404)
        return httpx.Response(200, text='{"status":"pulling"}\n')

    setup_initializer(monkeypatch, ollama)
    with pytest.raises(RuntimeError, match="did not complete"):
        bootstrap.initialize()
    assert paths.count("/api/pull") == 3
    assert "/api/chat" not in paths


def test_bootstrap_rejects_model_without_tools(monkeypatch):
    setup_initializer(
        monkeypatch, lambda request: httpx.Response(200, json={"capabilities": ["completion"]})
    )
    with pytest.raises(RuntimeError, match="does not support tools"):
        bootstrap.initialize()


def test_bootstrap_fails_when_real_tool_call_cannot_be_generated(monkeypatch):
    def ollama(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["tools"]})
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": "No tool call"}}
        )

    setup_initializer(monkeypatch, ollama)
    with pytest.raises(InvalidToolCall):
        bootstrap.initialize()
