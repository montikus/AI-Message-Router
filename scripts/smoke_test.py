"""Live end-to-end acceptance test: API -> real Ollama -> SMTP -> Mailpit.

Run: docker compose exec api python scripts/smoke_test.py
Only creates test messages; never clears the inbox.
"""

import argparse
import json

# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
import time
from email import policy
from email.parser import BytesParser

import httpx

CASES = [
    ("Nie działa mi komputer", "help-desk@example.com"),
    ("Chciałbym zgłosić urlop na jutro", "kadry@example.com"),
    ("Chcę rozpocząć rekrutację nowego pracownika do zespołu", "human-resources@example.com"),
    ("Awaria serwera bazy danych, wszystkie działy firmy utraciły dostęp", "it@example.com"),
    ("Jaka jest pogoda na Marsie?", "other@example.com"),
    ("Нужна справка о зарплате за прошлый месяц", "kadry@example.com"),
    ("I forgot my laptop password and cannot log in", "help-desk@example.com"),
]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(api_url: str, mailpit_url: str) -> list[dict]:
    results = []
    with httpx.Client(timeout=420, trust_env=False) as client:
        client.get(f"{api_url}/health/ready").raise_for_status()
        client.get(f"{api_url}/api/v1/docs").raise_for_status()
        schema = client.get(f"{api_url}/api/v1/openapi.json")
        schema.raise_for_status()
        check("/api/v1/messages" in schema.json()["paths"], "Endpoint missing from OpenAPI")
        for text, expected in CASES:
            start = time.monotonic()
            response = client.post(
                f"{api_url}/api/v1/messages",
                json={"email": "acceptance.test@example.com", "message": text},
            )
            check(
                response.status_code == 201, f"API failed: {response.status_code} {response.text}"
            )
            result = response.json()
            check(result["recipient"] == expected, f"Wrong classification: {text!r}: {result}")

            # Search by this request's unique subject; old inbox messages cannot pass the test.
            found = []
            for _ in range(20):
                search = client.get(
                    f"{mailpit_url}/api/v1/search",
                    params={"query": f"subject:{result['request_id']}"},
                )
                search.raise_for_status()
                found = search.json()["messages"]
                if found:
                    break
                time.sleep(0.5)
            check(len(found) == 1, f"Expected exactly one captured email, got {len(found)}")
            raw = client.get(f"{mailpit_url}/api/v1/message/{found[0]['ID']}/raw")
            raw.raise_for_status()
            email = BytesParser(policy=policy.default).parsebytes(raw.content)
            check(str(email["To"]) == expected, "Wrong To header")
            check(str(email["Reply-To"]) == "acceptance.test@example.com", "Wrong Reply-To")
            check(str(email["Message-ID"]) == result["message_id"], "Wrong Message-ID")
            check(str(email["X-Request-ID"]) == result["request_id"], "Wrong request ID")
            check(email.get_content().replace("\r\n", "\n") == text + "\n", "Body was modified")
            results.append(
                {
                    "message": text,
                    "recipient": expected,
                    "reply_to": str(email["Reply-To"]),
                    "request_id": result["request_id"],
                    "seconds": round(time.monotonic() - start, 2),
                    "status": "passed",
                }
            )
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--mailpit-url", default="http://mailpit:8025")
    args = parser.parse_args()
    passed = run(args.api_url.rstrip("/"), args.mailpit_url.rstrip("/"))
    print(f"PASS: {len(passed)} live routes, original bodies and Reply-To headers verified.")
