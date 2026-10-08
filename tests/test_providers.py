import json

import httpx
import pytest
from jarvis.config import Settings
from jarvis.contracts import ToolError
from jarvis.providers import Provider


@pytest.mark.parametrize(
    "status,code",
    [(401, "authentication"), (403, "provider_permission"), (404, "model_not_found"), (429, "quota")],
)
async def test_provider_diagnosis_is_sanitized(status, code):
    def handler(request):
        return httpx.Response(
            status,
            json={"error": {"code": "upstream", "message": "bad secret-value sk-test123"}},
            headers={"x-request-id": "r1"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    p = Provider(Settings(api_key="secret-value"), client)
    with pytest.raises(ToolError) as e:
        await p.diagnose()
    assert e.value.result.error_code == code
    assert "secret-value" not in e.value.result.model_dump_json()
    assert "sk-test123" not in e.value.result.model_dump_json()
    assert e.value.result.technical_details_redacted["model"] == "gpt-6-astra"
    await p.close()


async def test_streaming_model_usage_and_function_contract():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        events = [
            {"type": "response.output_text.delta", "delta": "Hola"},
            {
                "type": "response.completed",
                "response": {
                    "model": "gpt-6-astra",
                    "usage": {"total_tokens": 19},
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Hola"}],
                        }
                    ],
                },
            },
        ]
        return httpx.Response(
            200,
            content="".join(f"data: {json.dumps(e)}\n\n" for e in events),
            headers={"content-type": "text/event-stream"},
        )

    p = Provider(Settings(api_key="test"), httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    deltas = []

    async def delta(text):
        deltas.append(text)

    result = await p.respond([{"role": "user", "content": "Hola"}], [], delta)
    assert deltas == ["Hola"] and result["text"] == "Hola"
    assert result["usage"]["total_tokens"] == 19
    assert requests[0]["model"] == "gpt-6-astra" and requests[0]["store"] is False
    await p.close()
