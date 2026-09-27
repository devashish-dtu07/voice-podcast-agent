from __future__ import annotations
import os
import streamlit as st
from core.llm import client
from core.agents import validate_text, create_podcast
from core.audio import synthesize

APP_VERSION = "1.0"
st.set_page_config(page_title="Voice & Podcast AI", page_icon="🎙️", layout="wide")

st.markdown('''<style>
.block-container{max-width:1100px;padding-top:1.5rem}
.smallmuted{color:#6b7280;font-size:.9rem}
.resultbox{border:1px solid #e5e7eb;border-radius:14px;padding:1rem 1.1rem;background:white}
</style>''', unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

api_key = secret("OPENAI_API_KEY", "")
MODEL_TEXT = secret("MODEL_TEXT", "gpt-5.6-luna")
MODEL_TTS = secret("MODEL_TTS", "gpt-4o-mini-tts")
VOICE = secret("TTS_VOICE", "marin")

if not api_key:
    st.error("OPENAI_API_KEY is missing. Add it in Streamlit → App settings → Secrets.")
    st.stop()

c = client(api_key)
SPEEDS = [0.5, 0.75, 0.9, 1.0, 1.2, 1.5]

DEFAULTS = {
    "vo_audio": None, "vo_text": "", "vo_speed_applied": None,
    "pod_title": "", "pod_script": "", "pod_source": "", "pod_audio": None,
    "pod_speed_applied": None, "pod_length_applied": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title("🎙️ Voice & Podcast AI")
st.caption("Paste text → either hear it exactly as written, or turn it into a concise revision-friendly podcast.")

voice_tab, podcast_tab = st.tabs(["🔊 Voice Over", "🎧 Podcast"])

with voice_tab:
    st.subheader("Voice Over")
    st.write("Paste text and the app will read it **as written**, without summarising or rewriting it.")
    vo_text = st.text_area("Text to read", height=300, key="voice_input", placeholder="Paste your text here...")
    a, b = st.columns([1, 2])
    with a:
        vo_speed = st.select_slider("Playback speed", options=SPEEDS, value=1.0, format_func=lambda x: f"{x:g}×", key="voice_speed")
    with b:
        st.caption("The selected speed is applied when the audio is generated. Change it anytime to regenerate the same text at a new pace.")

    if st.button("▶ Generate Voice", type="primary", use_container_width=True, key="generate_voice"):
        try:
            with st.spinner("Checking the text…"):
                check = validate_text(c, MODEL_TEXT, vo_text, "voiceover")
            if not check["valid"]:
                st.error(check["message"])
                st.session_state.vo_audio = None
            else:
                with st.spinner("Generating voice…"):
                    st.session_state.vo_audio = synthesize(c, vo_text.strip(), VOICE, MODEL_TTS, vo_speed, "voiceover")
                st.session_state.vo_text = vo_text
                st.session_state.vo_speed_applied = vo_speed
        except Exception as e:
            st.error(f"Voice generation failed: {e}")

    # Live speed change: regenerate only when we already have audio for exactly this text.
    if (st.session_state.vo_audio is not None and st.session_state.vo_text == vo_text and
        st.session_state.vo_speed_applied is not None and float(st.session_state.vo_speed_applied) != float(vo_speed)):
        try:
            with st.spinner("Updating playback speed…"):
                st.session_state.vo_audio = synthesize(c, vo_text.strip(), VOICE, MODEL_TTS, vo_speed, "voiceover")
            st.session_state.vo_speed_applied = vo_speed
        except Exception as e:
            st.error(f"Could not update speed: {e}")

    if st.session_state.vo_audio is not None and st.session_state.vo_text == vo_text:
        st.audio(st.session_state.vo_audio, format="audio/mp3")
        st.download_button("Download MP3", st.session_state.vo_audio, file_name="voice_over.mp3", mime="audio/mpeg", key="download_vo")

with podcast_tab:
    st.subheader("Podcast")
    st.write("Paste material and the app will **condense it into a natural spoken script**, show you the script, then generate the podcast audio.")
    pod_text = st.text_area("Source material", height=300, key="podcast_input", placeholder="Paste notes, readings, an article, or revision material here...")
    c1, c2 = st.columns(2)
    with c1:
        pod_length = st.radio("Podcast detail", ["Brief", "Standard", "Detailed"], horizontal=True, index=1)
    with c2:
        pod_speed = st.select_slider("Playback speed", options=SPEEDS, value=1.0, format_func=lambda x: f"{x:g}×", key="pod_speed")

    if st.button("✨ Create Podcast", type="primary", use_container_width=True, key="create_podcast"):
        try:
            with st.spinner("Checking the source material…"):
                check = validate_text(c, MODEL_TEXT, pod_text, "podcast")
            if not check["valid"]:
                st.error(check["message"])
                st.session_state.pod_audio = None
                st.session_state.pod_title = ""
                st.session_state.pod_script = ""
            else:
                with st.spinner("Condensing and rewriting for listening…"):
                    result = create_podcast(c, MODEL_TEXT, pod_text.strip(), pod_length)
                st.session_state.pod_title = result["title"]
                st.session_state.pod_script = result["script"]
                st.session_state.pod_source = pod_text
                st.session_state.pod_length_applied = pod_length
                # Script appears in this same rerun before the audio player below; TTS follows generation.
                with st.spinner("Generating podcast audio…"):
                    st.session_state.pod_audio = synthesize(c, result["script"], VOICE, MODEL_TTS, pod_speed, "podcast")
                st.session_state.pod_speed_applied = pod_speed
        except Exception as e:
            st.error(f"Podcast generation failed: {e}")

    current_podcast = bool(st.session_state.pod_script) and st.session_state.pod_source == pod_text
    if current_podcast:
        st.divider()
        st.markdown(f"## {st.session_state.pod_title}")
        st.caption(f"{st.session_state.pod_length_applied} version")
        st.text_area("Podcast script", value=st.session_state.pod_script, height=360, disabled=True, key="pod_script_display")

        if (st.session_state.pod_audio is not None and st.session_state.pod_speed_applied is not None and
            float(st.session_state.pod_speed_applied) != float(pod_speed)):
            try:
                with st.spinner("Updating playback speed…"):
                    st.session_state.pod_audio = synthesize(c, st.session_state.pod_script, VOICE, MODEL_TTS, pod_speed, "podcast")
                st.session_state.pod_speed_applied = pod_speed
            except Exception as e:
                st.error(f"Could not update speed: {e}")

        if st.session_state.pod_audio is not None:
            st.audio(st.session_state.pod_audio, format="audio/mp3")
            safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in st.session_state.pod_title)[:60] or "podcast"
            st.download_button("Download Podcast MP3", st.session_state.pod_audio, file_name=f"{safe_name}.mp3", mime="audio/mpeg", key="download_pod")

        if st.button("🔄 Regenerate Podcast", use_container_width=True):
            try:
                with st.spinner("Creating a fresh version…"):
                    result = create_podcast(c, MODEL_TEXT, pod_text.strip(), pod_length)
                    st.session_state.pod_title = result["title"]
                    st.session_state.pod_script = result["script"]
                    st.session_state.pod_length_applied = pod_length
                    st.session_state.pod_audio = synthesize(c, result["script"], VOICE, MODEL_TTS, pod_speed, "podcast")
                    st.session_state.pod_speed_applied = pod_speed
                st.rerun()
            except Exception as e:
                st.error(f"Regeneration failed: {e}")

st.divider()
st.caption(f"Voice & Podcast AI v{APP_VERSION} · OpenAI text + TTS")
