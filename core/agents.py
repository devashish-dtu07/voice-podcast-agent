from __future__ import annotations
from .llm import call_text, parse_json_loose

# Conservative character budgets. The API/model in this deployment is enforcing
# a 2,000-token input ceiling, so prompts + source must stay comfortably below it.
VALIDATION_SAMPLE_CHARS = 4500
PODCAST_CHUNK_CHARS = 4200


def _split_text(text: str, max_chars: int = PODCAST_CHUNK_CHARS) -> list[str]:
    """Split on paragraph/sentence boundaries where possible, with a hard fallback."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks, current = [], ""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    for p in paragraphs:
        # Hard-split an unusually large paragraph.
        while len(p) > max_chars:
            room = max_chars - len(current) - (1 if current else 0)
            if room > 300:
                piece = p[:room]
                cut = max(piece.rfind(". "), piece.rfind("; "), piece.rfind(", "), piece.rfind(" "))
                if cut > int(room * 0.6):
                    piece = piece[:cut + 1]
                current = (current + "\n" + piece).strip()
                chunks.append(current)
                current = ""
                p = p[len(piece):].strip()
            else:
                if current:
                    chunks.append(current)
                    current = ""
                piece = p[:max_chars]
                cut = max(piece.rfind(". "), piece.rfind("; "), piece.rfind(", "), piece.rfind(" "))
                if cut > int(max_chars * 0.6):
                    piece = piece[:cut + 1]
                chunks.append(piece.strip())
                p = p[len(piece):].strip()

        candidate = (current + "\n" + p).strip() if current else p
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def validate_text(c, model: str, text: str, mode: str) -> dict:
    stripped = (text or "").strip()
    if not stripped:
        return {"valid": False, "message": "Please paste some text or upload a readable PDF first."}
    if len(stripped) < 3:
        return {"valid": False, "message": "The text is too short to process."}

    requirement = (
        "For VOICE OVER, accept any understandable text that a person could reasonably want read aloud, "
        "including short sentences, formulas, bullet points, fragmented notes, acronyms, headings, and study notes."
        if mode == "voiceover" else
        "For PODCAST, the text must contain enough understandable semantic information to condense or explain. "
        "Short but meaningful material can pass, but a lone formula/title or content with almost nothing to develop should fail."
    )
    system = f'''You are a conservative input-quality validator. Decide whether text is meaningful enough for the requested mode.
{requirement}
Reject random keyboard smashing, gibberish, meaningless repeated tokens, mostly-symbol noise, or text with no interpretable content.
Do NOT reject text merely because grammar is poor, formatting is messy, it contains abbreviations, formulas, lists, copied notes, or sentence fragments.
Return ONLY JSON: {{"valid":true|false,"message":"brief user-facing reason"}}.'''

    # Keep validation itself safely below the API's 2k-token input ceiling.
    if len(stripped) > VALIDATION_SAMPLE_CHARS:
        third = VALIDATION_SAMPLE_CHARS // 3
        mid = len(stripped) // 2
        sample = (
            stripped[:third] + "\n...[middle]...\n" +
            stripped[mid-third//2:mid+third//2] + "\n...[end]...\n" +
            stripped[-third:]
        )
    else:
        sample = stripped

    raw = call_text(c, model, system, f"MODE: {mode}\n\nTEXT:\n{sample}", "low")
    out = parse_json_loose(raw, {"valid": False, "message": "I couldn't verify that the text is usable. Please check it and try again."})
    valid = bool(out.get("valid"))
    msg = str(out.get("message") or ("Text looks usable." if valid else "The text doesn't appear to contain coherent content. Please check it and try again."))
    return {"valid": valid, "message": msg}


LENGTH_GUIDE = {
    "Brief": "Keep only the core concepts, definitions, logic and conclusions. Be aggressively concise.",
    "Standard": "Keep the important concepts, distinctions, examples, numbers and conclusions while removing repetition.",
    "Detailed": "Retain most substantive concepts, definitions, examples, numbers, caveats and distinctions while removing repetition and written clutter.",
}


def _condense_chunk(c, model: str, chunk: str, length: str, idx: int, total: int) -> str:
    system = f'''You are preparing source notes for an educational podcast. This is section {idx} of {total}.
{LENGTH_GUIDE.get(length, LENGTH_GUIDE['Standard'])}
Extract and condense ONLY information supported by this section. Preserve important terminology, numbers, formulas, frameworks, examples, caveats and causal logic. Remove repetition, citations/URLs and formatting clutter. Do not add an intro/outro and do not invent facts. Return plain text notes only.'''
    return call_text(c, model, system, f"SECTION {idx}/{total}:\n{chunk}", "low").strip()


def _final_podcast(c, model: str, notes: str, length: str) -> dict:
    system = f'''Turn condensed study/reference notes into a concise educational podcast script for one narrator.
{LENGTH_GUIDE.get(length, LENGTH_GUIDE['Standard'])}

Rules:
- Preserve the supplied notes' meaning. Do not invent facts.
- Make it natural to LISTEN to: clear transitions, spoken-language sentences, and explanations that flow.
- Remove repetition and awkward written formatting.
- Keep important numbers, formulas, frameworks, definitions, caveats, comparisons and examples when they matter.
- Do not use fake dialogue, two-host banter, sound-effect directions, or cheesy podcast filler.
- Do not start with generic lines like "Welcome back listeners" or "In today's exciting episode".
- Produce a specific, useful title.
- Keep the script concise enough for reliable text-to-speech; prioritize substance over filler.
Return ONLY valid JSON: {{"title":"...","script":"..."}}.'''
    raw = call_text(c, model, system, f"CONDENSED SOURCE NOTES:\n{notes}", "low")
    out = parse_json_loose(raw, {})
    title = str(out.get("title") or "Podcast Summary").strip()
    script = str(out.get("script") or "").strip()
    if not script:
        raise ValueError("The podcast script could not be generated. Please try again.")
    return {"title": title, "script": script}


def create_podcast(c, model: str, text: str, length: str="Standard") -> dict:
    chunks = _split_text(text, PODCAST_CHUNK_CHARS)
    if not chunks:
        raise ValueError("No usable source text was found.")

    # Short source: one direct final call.
    if len(chunks) == 1:
        notes = _condense_chunk(c, model, chunks[0], length, 1, 1)
        return _final_podcast(c, model, notes, length)

    # Long source: map each safe chunk to compact notes.
    summaries = [_condense_chunk(c, model, ch, length, i, len(chunks)) for i, ch in enumerate(chunks, 1)]

    # Reduce recursively if the combined summaries are still too large for one call.
    combined = "\n\n".join(f"Section {i}: {s}" for i, s in enumerate(summaries, 1))
    while len(combined) > PODCAST_CHUNK_CHARS:
        reduce_chunks = _split_text(combined, PODCAST_CHUNK_CHARS)
        reduced = []
        for i, ch in enumerate(reduce_chunks, 1):
            reduced.append(_condense_chunk(c, model, ch, "Brief", i, len(reduce_chunks)))
        new_combined = "\n\n".join(reduced)
        if len(new_combined) >= len(combined):
            # Safety valve: hard cap after semantic reduction rather than loop forever.
            combined = new_combined[:PODCAST_CHUNK_CHARS]
            break
        combined = new_combined

    return _final_podcast(c, model, combined, length)
