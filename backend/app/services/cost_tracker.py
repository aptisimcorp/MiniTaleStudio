"""Video generation cost tracker.

Tracks costs per pipeline step and stores the total in Cosmos DB.
"""

from dataclasses import dataclass, field


# OpenAI pricing estimates (USD)
OPENAI_GPT4O_INPUT_PER_1K = 0.0025
OPENAI_GPT4O_OUTPUT_PER_1K = 0.01
OPENAI_DALLE3_PER_IMAGE = 0.04
OPENAI_TTS1_PER_1K_CHARS = 0.015

# Grok pricing estimates (USD)
GROK_VIDEO_PER_CLIP = 0.10


@dataclass
class VideoCostTracker:
    """Accumulates costs for a single video generation run."""

    story_generation_cost: float = 0.0
    image_generation_cost: float = 0.0
    video_generation_cost: float = 0.0
    tts_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return (
            self.story_generation_cost
            + self.image_generation_cost
            + self.video_generation_cost
            + self.tts_cost
        )

    def add_openai_story_cost(self, input_tokens: int, output_tokens: int):
        """Track cost for GPT-4o story generation."""
        self.story_generation_cost += (
            (input_tokens / 1000) * OPENAI_GPT4O_INPUT_PER_1K
            + (output_tokens / 1000) * OPENAI_GPT4O_OUTPUT_PER_1K
        )

    def add_openai_image_cost(self, count: int = 1):
        """Track cost for DALL-E 3 image generation."""
        self.image_generation_cost += OPENAI_DALLE3_PER_IMAGE * count

    def add_grok_video_cost(self, clip_count: int = 1):
        """Track cost for Grok video clip generation."""
        self.video_generation_cost += GROK_VIDEO_PER_CLIP * clip_count

    def add_tts_cost(self, char_count: int):
        """Track cost for OpenAI TTS."""
        self.tts_cost += (char_count / 1000) * OPENAI_TTS1_PER_1K_CHARS

    def to_dict(self) -> dict:
        return {
            "story_generation_cost": round(self.story_generation_cost, 4),
            "image_generation_cost": round(self.image_generation_cost, 4),
            "video_generation_cost": round(self.video_generation_cost, 4),
            "tts_cost": round(self.tts_cost, 4),
            "total_cost": round(self.total_cost, 4),
        }
