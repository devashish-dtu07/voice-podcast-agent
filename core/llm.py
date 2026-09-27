from __future__ import annotations
import json, re, time
from typing import Any, Dict
from openai import OpenAI


def client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def _text(resp) -> str:
    if getattr(resp, "output_text", None):
        return resp.output_text
    try:
        return "".join(c.text for o in resp.output for c in o.content if getattr(c, "type", "") == "output_text")
    except Exception:
        return str(resp)


def call_text(c: OpenAI, model: str, system: str, user: str, reasoning: str="low", retries: int=2) -> str:
    last = None
    for i in range(retries + 1):
        try:
            kwargs = dict(model=model, input=[{"role":"system","content":system},{"role":"user","content":user}])
            if reasoning and "gpt-5" in model:
                kwargs["reasoning"] = {"effort": reasoning}
            r = c.responses.create(**kwargs)
            return _text(r).strip()
        except Exception as e:
            last = e
            if i < retries:
                time.sleep(1.2 * (i + 1))
    raise last


def parse_json_loose(text: str, fallback: Dict[str, Any] | None=None) -> Dict[str, Any]:
    fallback = fallback or {}
    if not text:
        return dict(fallback)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return dict(fallback)
