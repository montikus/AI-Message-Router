# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import Department


def tool_response(recipient="help-desk@example.com", name="send_email", extra=None):
    arguments = {"recipient": recipient, **(extra or {})}
    return {
        "done": True,
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        },
    }


def make_app(smtp_server, handler):
    _, port = smtp_server
    return create_app(
        Settings(smtp_host="127.0.0.1", smtp_port=port, _env_file=None),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize("department", list(Department))
def test_native_tool_dispatch_delivers_original_email(smtp_server, department):
    inbox, _ = smtp_server
    calls = []

    def ollama(request):
        calls.append(json.loads(request.content))
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json=tool_response(department.value))

    original = "  Nie działa mi komputer.\nZażółć gęślą jaźń. Тест.  "
    with TestClient(make_app(smtp_server, ollama)) as client:
        response = client.post(
            "/api/v1/messages", json={"email": "jan.nowak@example.com", "message": original}
        )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["recipient"] == department.value
    assert result["status"] == "sent"
    assert len(inbox.messages) == 1
    message = inbox.messages[0]
    assert str(message["To"]) == department.value
    assert str(message["Reply-To"]) == "jan.nowak@example.com"
    assert str(message["From"]) == "router@example.com"
    assert str(message["Message-ID"]) == result["message_id"]
    assert str(message["X-Request-ID"]) == result["request_id"]
    assert message.get_content().replace("\r\n", "\n") == original + "\n"
    assert inbox.envelopes[0].rcpt_tos == [department.value]
    assert len(calls) == 1  # No extra model call after SMTP acceptance.
    assert calls[0]["tools"][0]["function"]["name"] == "send_email"
    assert calls[0]["stream"] is False
    assert "jan.nowak@example.com" not in json.dumps(calls[0]["messages"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "bad", "message": "Test"},
        {"email": "a@example.com\r\nBcc: b@example.com", "message": "Test"},
        {"email": "a@example.com", "message": ""},
        {"email": "a@example.com", "message": " \n\t"},
        {"email": "a@example.com", "message": "x" * 4001},
        {"email": "a@example.com", "message": 123},
        {"email": "a@example.com", "message": "Test", "recipient": "evil@example.net"},
    ],
)
def test_validation_never_calls_model_or_smtp(smtp_server, payload):
    def unexpected(request):
        pytest.fail("Invalid input must not reach Ollama")

    with TestClient(make_app(smtp_server, unexpected)) as client:
        assert client.post("/api/v1/messages", json=payload).status_code == 422
    assert not smtp_server[0].messages


@pytest.mark.parametrize(
    "invalid",
    [
        tool_response("evil@example.net"),
        tool_response(name="execute_shell"),
        tool_response(extra={"reply_to": "evil@example.net"}),
        {"done": True, "message": {"role": "assistant", "content": "Sent!"}},
        {"done": True, "message": {"role": "assistant", "tool_calls": [None]}},
        {"done": False, "message": tool_response()["message"]},
        {"done": True, "message": []},
        [],
        {
            "done": True,
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "send_email",
                            "arguments": '{"recipient":"it@example.com"}',
                        }
                    }
                ],
            },
        },
        {
            "done": True,
            "message": {
                "role": "assistant",
                "tool_calls": tool_response()["message"]["tool_calls"] * 2,
            },
        },
    ],
)
def test_invalid_model_responses_never_send_email(smtp_server, invalid):
    calls = []

    def ollama(request):
        calls.append(request)
        return httpx.Response(200, json=invalid)

    with TestClient(make_app(smtp_server, ollama)) as client:
        result = client.post("/api/v1/messages", json={"email": "a@example.com", "message": "Test"})
    assert result.status_code == 502
    assert len(calls) == 2
    assert not smtp_server[0].messages


def test_repair_before_dispatch_sends_only_once(smtp_server):
    responses = iter([tool_response("not-allowed@example.net"), tool_response("other@example.com")])
    with TestClient(
        make_app(smtp_server, lambda request: httpx.Response(200, json=next(responses)))
    ) as client:
        result = client.post(
            "/api/v1/messages", json={"email": "a@example.com", "message": "Nieznany temat"}
        )
    assert result.status_code == 201
    assert result.json()["recipient"] == "other@example.com"
    assert len(smtp_server[0].messages) == 1


@pytest.mark.parametrize(
    "failure, expected", [("timeout", 504), ("connection", 503), ("http", 503)]
)
def test_model_failures_do_not_send(smtp_server, failure, expected):
    def ollama(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("Timeout", request=request)
        if failure == "connection":
            raise httpx.ConnectError("Offline", request=request)
        return httpx.Response(500, json={"error": "Internal model failure"})

    with TestClient(make_app(smtp_server, ollama)) as client:
        result = client.post("/api/v1/messages", json={"email": "a@example.com", "message": "Test"})
    assert result.status_code == expected
    assert not smtp_server[0].messages


def test_smtp_failure_is_not_reported_as_success(smtp_server):
    inbox, _ = smtp_server
    inbox.reject = True
    calls = []

    def ollama(request):
        calls.append(request)
        return httpx.Response(200, json=tool_response())

    with TestClient(make_app(smtp_server, ollama)) as client:
        result = client.post("/api/v1/messages", json={"email": "a@example.com", "message": "Test"})
    assert result.status_code == 502
    assert "SMTP" in result.json()["detail"]
    assert len(calls) == 1
    assert not inbox.messages


def test_docs_and_readiness(smtp_server):
    def ollama(request):
        assert request.url.path == "/api/show"
        return httpx.Response(200, json={"capabilities": ["completion", "tools"]})

    with TestClient(make_app(smtp_server, ollama)) as client:
        assert client.get("/api/v1/docs").status_code == 200
        schema = client.get("/api/v1/openapi.json").json()
        assert "/api/v1/messages" in schema["paths"]
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize("capabilities", [[], ["completion"]])
def test_readiness_requires_tool_capable_model(smtp_server, capabilities):
    with TestClient(
        make_app(
            smtp_server, lambda request: httpx.Response(200, json={"capabilities": capabilities})
        )
    ) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200


def test_busy_router_rejects_before_dispatch(smtp_server):
    def unexpected(request):
        pytest.fail("Busy router must not call Ollama")

    app = make_app(smtp_server, unexpected)
    with TestClient(app) as client:
        for _ in range(2):
            assert app.state.capacity.acquire(blocking=False)
        response = client.post(
            "/api/v1/messages", json={"email": "a@example.com", "message": "Test"}
        )
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "10"
        for _ in range(2):
            app.state.capacity.release()
    assert not smtp_server[0].messages
