import os
from openai import OpenAI

from app.config import settings
from app.models import Language


# Map of language ? recommended voice
VOICE_MAP = {
    Language.ENGLISH: "alloy",
    Language.HINDI: "shimmer",
}


def generate_narration(
    text: str,
    language: Language,
    voice_type: str | None,
    work_dir: str,
) -> str:
    client = OpenAI(api_key=settings.openai_api_key)

    voice = voice_type or VOICE_MAP.get(language, "alloy")
    audio_dir = os.path.join(work_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    output_path = os.path.join(audio_dir, "narration.mp3")

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )

    response.stream_to_file(output_path)
    return output_path
