import requests
from datetime import datetime
from pathlib import Path
from src.config import Settings

class ElevenLabsTTS:
    def __init__(self):
        if not Settings.ELEVENLABS_API_KEY:
            raise RuntimeError("ELEVENLABS_API_KEY not set")

        self.api_key = Settings.ELEVENLABS_API_KEY
        self.voice_id = Settings.ELEVENLABS_VOICE_ID or self._get_first_user_voice_id()

    def _get_first_user_voice_id(self) -> str:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": self.api_key}
        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            raise RuntimeError(f"Unable to fetch voices: {r.status_code} {r.text[:200]}")

        data = r.json()
        voices = data.get("voices", [])
        if not voices:
            raise RuntimeError("No voices found in your ElevenLabs account. Create one in Voices -> Add Voice.")
        return voices[0]["voice_id"]

    def synthesize_to_file(self, text: str, out_dir: str = "data/runs") -> str:
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
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
        }

        r = requests.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")

        with open(out_path, "wb") as f:
            f.write(r.content)

        return out_path