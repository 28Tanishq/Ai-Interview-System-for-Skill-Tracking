"""Speech helpers: speech-to-text (free Google Web Speech via SpeechRecognition) and text-to-speech (gTTS)."""
import io


def transcribe_audio(wav_bytes: bytes, language: str = "en-US") -> tuple[str, str | None]:
    """Convert WAV bytes to text. Returns (text, error_message_or_None).

    Uses the free Google Web Speech endpoint bundled with SpeechRecognition
    (no API key needed, requires internet, suited to short clips).
    """
    try:
        import speech_recognition as sr
    except ImportError:
        return "", "SpeechRecognition is not installed. Run: pip install SpeechRecognition"

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language=language), None
    except sr.UnknownValueError:
        return "", "Could not understand the audio. Please speak clearly and try again, or type your answer."
    except sr.RequestError as e:
        return "", f"Speech service unavailable ({e}). Check your internet connection or type your answer."
    except Exception as e:
        return "", f"Audio processing failed: {e}"


def text_to_speech(text: str, lang: str = "en") -> bytes | None:
    """Read a question aloud with gTTS (free, needs internet). Returns MP3 bytes or None."""
    try:
        from gtts import gTTS

        buf = io.BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None


def transcribe_media(audio_bytes: bytes, language: str = "en-US") -> tuple[str, str | None]:
    """Fallback when the browser has no live speech recognition (e.g. Firefox).

    Converts WebM/MP4 audio to WAV with ffmpeg (must be installed) and uses the free Google Web Speech endpoint.
    """
    import shutil
    import subprocess
    import tempfile

    if not audio_bytes:
        return "", "No audio received."
    if not shutil.which("ffmpeg"):
        return "", "ffmpeg is not installed, so the recording could not be transcribed on the server."
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = f"{tmp}/in.bin", f"{tmp}/out.wav"
        with open(src, "wb") as f:
            f.write(audio_bytes)
        try:
            subprocess.run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", dst], check=True,
                           capture_output=True, timeout=60)
            with open(dst, "rb") as f:
                return transcribe_audio(f.read(), language)
        except Exception as e:  # noqa: BLE001
            return "", f"Audio conversion failed: {e}"
