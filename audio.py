from __future__ import annotations


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
