# Voice & Podcast AI v1.0

A Streamlit app with two OpenAI-powered modes:

- **Voice Over:** validates pasted text and reads it as written.
- **Podcast:** validates pasted material, creates a title + condensed spoken script, displays the script, and generates audio.

Both modes support 0.5x, 0.75x, 0.9x, 1x, 1.2x and 1.5x TTS speeds.

## Streamlit Community Cloud

1. Create a new GitHub repository and upload this folder, preserving the `core/` directory.
2. In Streamlit Community Cloud, create a new app using `streamlit_app.py` as the entrypoint.
3. In **App settings → Secrets**, add:

```toml
OPENAI_API_KEY = "sk-..."

# Optional overrides
MODEL_TEXT = "gpt-5.6-luna"
MODEL_TTS = "gpt-4o-mini-tts"
TTS_VOICE = "marin"
```

4. Deploy/reboot the app.

## Notes

- The app performs a semantic validation step before TTS/podcast generation, so obvious gibberish is rejected.
- Voice Over does not intentionally rewrite the input; the original pasted text is sent to TTS.
- Podcast mode is designed for learning/revision, not entertainment-style filler.
- Streamlit session state is ephemeral; generated audio is available during the current session and can be downloaded.
