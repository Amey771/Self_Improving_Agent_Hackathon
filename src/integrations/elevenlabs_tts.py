import requests
import re
from datetime import datetime
from pathlib import Path
from src.config import Settings

class ElevenLabsTTS:
    MODEL_OPTIONS = [
        "eleven_multilingual_v2",
        "eleven_turbo_v2_5",
        "eleven_turbo_v2",
        "eleven_monolingual_v1",
    ]

    def __init__(self):
        if not Settings.ELEVENLABS_API_KEY:
            raise RuntimeError("ELEVENLABS_API_KEY not set")

        self.api_key = Settings.ELEVENLABS_API_KEY
        self.voice_id = Settings.ELEVENLABS_VOICE_ID or self._get_first_user_voice_id()
        self.default_model_id = Settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"
        self.default_stability = Settings.ELEVENLABS_STABILITY
        self.default_similarity_boost = Settings.ELEVENLABS_SIMILARITY_BOOST
        self.default_style = Settings.ELEVENLABS_STYLE
        self.default_speaker_boost = Settings.ELEVENLABS_USE_SPEAKER_BOOST

    def _get_first_user_voice_id(self) -> str:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": self.api_key}
        r = requests.get(url, headers=headers, timeout=20)

        if r.status_code != 200:
            raise RuntimeError(f"Unable to fetch voices: {r.status_code} {r.text[:200]}")

        data = r.json()
        voices = data.get("voices", [])
        if not voices:
            raise RuntimeError("No voices found in your ElevenLabs account. Create one in Voices -> Add Voice.")
        return voices[0]["voice_id"]

    def _normalize_text(self, text: str) -> str:
        cleaned = text
        replacements = {
            "->": " to ",
            "_": " ",
            "|": " ",
        }
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def synthesize_to_file(
        self,
        text: str,
        out_dir: str = "data/runs",
        model_id: str | None = None,
        stability: float | None = None,
        similarity_boost: float | None = None,
        style: float | None = None,
        use_speaker_boost: bool | None = None,
    ) -> str:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        filename = f"voice_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp3"
        out_path = str(Path(out_dir) / filename)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": self._normalize_text(text),
            "model_id": model_id or self.default_model_id,
            "voice_settings": {
                "stability": max(0.0, min(1.0, stability if stability is not None else self.default_stability)),
                "similarity_boost": max(0.0, min(1.0, similarity_boost if similarity_boost is not None else self.default_similarity_boost)),
                "style": max(0.0, min(1.0, style if style is not None else self.default_style)),
                "use_speaker_boost": self.default_speaker_boost if use_speaker_boost is None else bool(use_speaker_boost),
            },
        }

        r = requests.post(url, headers=headers, json=payload, timeout=45)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")

        with open(out_path, "wb") as f:
            f.write(r.content)

        return out_path
