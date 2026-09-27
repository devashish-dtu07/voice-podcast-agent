from __future__ import annotations
import re

# TTS is also subject to an input ceiling. Keep each request comfortably below it.
TTS_CHUNK_CHARS = 4800


def _split_for_tts(text: str, max_chars: int = TTS_CHUNK_CHARS) -> list[str]:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if not s:
            continue
        while len(s) > max_chars:
            if current:
                chunks.append(current.strip()); current = ""
            piece = s[:max_chars]
            cut = piece.rfind(" ")
            if cut > int(max_chars * 0.7):
                piece = piece[:cut]
            chunks.append(piece.strip())
            s = s[len(piece):].strip()
        candidate = (current + " " + s).strip() if current else s
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = s
    if current:
        chunks.append(current.strip())
    return chunks


def _one_tts(c, text: str, voice: str, model: str, speed: float, instructions: str) -> bytes:
    try:
        r = c.audio.speech.create(
            model=model, voice=voice, input=text, instructions=instructions,
            response_format="mp3", speed=float(speed)
        )
    except TypeError:
        r = c.audio.speech.create(model=model, voice=voice, input=text, response_format="mp3", speed=float(speed))
    if hasattr(r, "read"):
        return r.read()
    if hasattr(r, "content"):
        return r.content
    return bytes(r)


def synthesize(c, text: str, voice: str="marin", model: str="gpt-4o-mini-tts", speed: float=1.0, mode: str="voiceover") -> bytes:
    if mode == "podcast":
        instructions = (
            "Natural educational podcast narrator. Clear, warm, conversational and focused. "
            "Sound like a knowledgeable person explaining revision material aloud. Avoid theatrical delivery, "
            "radio-host hype, exaggerated enthusiasm, or unnecessary dramatic pauses."
        )
    else:
        instructions = (
            "Clear neutral narrator. Read the supplied text faithfully and exactly as written. "
            "Do not paraphrase, omit, add, explain, or editorialize. Natural pronunciation and clean pauses only."
        )

    chunks = _split_for_tts(text)
    if not chunks:
        raise ValueError("No text was available for speech generation.")
    # MP3 is frame-based; concatenated MP3 responses are playable as one continuous stream
    # in modern browser audio players while keeping every API request under the input ceiling.
    return b"".join(_one_tts(c, ch, voice, model, speed, instructions) for ch in chunks)
