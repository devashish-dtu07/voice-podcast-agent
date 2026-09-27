from __future__ import annotations
from .llm import call_text, parse_json_loose


def validate_text(c, model: str, text: str, mode: str) -> dict:
    # Cheap local guards first, before an API validation call.
    stripped = (text or "").strip()
    if not stripped:
        return {"valid": False, "message": "Please paste some text first."}
    if len(stripped) < 3:
        return {"valid": False, "message": "The pasted text is too short to process."}

    requirement = (
        "For VOICE OVER, accept any understandable text that a person could reasonably want read aloud, "
        "including short sentences, formulas, bullet points, fragmented notes, acronyms, headings, and study notes."
        if mode == "voiceover" else
        "For PODCAST, the text must contain enough understandable semantic information to condense or explain. "
        "Short but meaningful material can pass, but a lone formula/title or content with almost nothing to develop should fail."
    )
    system = f'''You are a conservative input-quality validator. Decide whether pasted text is meaningful enough for the requested mode.
{requirement}
Reject random keyboard smashing, gibberish, meaningless repeated tokens, mostly-symbol noise, or text with no interpretable content.
Do NOT reject text merely because grammar is poor, formatting is messy, it contains abbreviations, formulas, lists, copied notes, or sentence fragments.
Return ONLY JSON: {{"valid":true|false,"message":"brief user-facing reason"}}.'''
    # Validation doesn't need the whole huge document to detect gibberish; sample front/middle/end.
    if len(stripped) > 12000:
        mid = len(stripped)//2
        sample = stripped[:4500] + "\n...[middle sample]...\n" + stripped[mid-1500:mid+1500] + "\n...[end sample]...\n" + stripped[-4500:]
    else:
        sample = stripped
    raw = call_text(c, model, system, f"MODE: {mode}\n\nTEXT:\n{sample}", "low")
    out = parse_json_loose(raw, {"valid": False, "message": "I couldn't verify that the pasted text is usable. Please check it and try again."})
    valid = bool(out.get("valid"))
    msg = str(out.get("message") or ("Text looks usable." if valid else "The pasted text doesn't appear to contain coherent content. Please check it and try again."))
    return {"valid": valid, "message": msg}


LENGTH_GUIDE = {
    "Brief": "Keep roughly 30-40% of the source's informational detail. Prioritize core concepts, definitions, logic and conclusions.",
    "Standard": "Keep roughly 50-65% of the source's informational detail. Preserve important examples and distinctions when useful.",
    "Detailed": "Keep roughly 70-85% of the source's informational detail. Condense repetition and written clutter, but retain most substantive points.",
}


def create_podcast(c, model: str, text: str, length: str="Standard") -> dict:
    system = f'''Turn study/reference text into a concise educational podcast script for one narrator.
{LENGTH_GUIDE.get(length, LENGTH_GUIDE['Standard'])}

Rules:
- Preserve the source's meaning. Do not invent facts that are not supported by the pasted text.
- Make it natural to LISTEN to: clear transitions, spoken-language sentences, and explanations that flow.
- Remove repetition, administrative clutter, citations/URLs that are not useful when spoken, and awkward written formatting.
- Keep important numbers, formulas, frameworks, definitions, caveats, comparisons and examples when they matter.
- Do not use fake dialogue, two-host banter, sound-effect directions, or cheesy podcast filler.
- Do not start with generic lines like "Welcome back listeners" or "In today's exciting episode".
- A short orientation sentence is fine when it helps comprehension.
- Produce a specific, useful title.
- The script itself must be suitable for direct text-to-speech.
Return ONLY valid JSON: {{"title":"...","script":"..."}}.'''
    raw = call_text(c, model, system, f"SOURCE TEXT:\n{text}", "low")
    out = parse_json_loose(raw, {})
    title = str(out.get("title") or "Podcast Summary").strip()
    script = str(out.get("script") or "").strip()
    if not script:
        raise ValueError("The podcast script could not be generated. Please try again.")
    return {"title": title, "script": script}
