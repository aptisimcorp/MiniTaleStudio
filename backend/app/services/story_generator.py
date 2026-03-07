import json
from openai import OpenAI

from app.config import settings
from app.models import (
    ConfigurationCreate,
    DurationRange,
    Language,
    Scene,
    StoryResult,
)

# Word-count targets per duration range
WORD_TARGETS = {
    DurationRange.SHORT: (150, 180),
    DurationRange.MEDIUM: (200, 240),
    DurationRange.LONG: (260, 350),
}

SCENE_COUNTS = {
    DurationRange.SHORT: (6, 8),
    DurationRange.MEDIUM: (8, 10),
    DurationRange.LONG: (10, 12),
}


def generate_story(config: ConfigurationCreate) -> StoryResult:
    client = OpenAI(api_key=settings.openai_api_key)

    min_words, max_words = WORD_TARGETS[config.duration]
    min_scenes, max_scenes = SCENE_COUNTS[config.duration]
    category = config.custom_category if config.category.value == "custom" and config.custom_category else config.category.value
    lang = "Hindi" if config.language == Language.HINDI else "English"

    system_prompt = (
        "You are a master storyteller who creates gripping short stories for vertical video platforms "
        "(YouTube Shorts, Instagram Reels, TikTok). "
        "Your stories follow this structure: Hook -> Setup -> Rising tension -> Climax -> Twist ending. "
        "CRITICAL: You must define consistent character appearances upfront and reference them in every scene."
    )

    user_prompt = f"""Create a {category} short story in {lang}.

Requirements:
- Word count: {min_words}-{max_words} words
- Split the story into exactly {min_scenes} to {max_scenes} scenes
- Each scene should be 1-3 sentences that paint a vivid visual picture
- Start with a compelling hook
- End with an unexpected twist

CHARACTER CONSISTENCY RULES:
- Define 1-3 main characters with FIXED visual descriptions
- Each character must have: name, gender, approximate age, hair color/style, clothing, and one distinguishing feature
- These EXACT descriptions must be repeated in EVERY image_prompt where that character appears
- Never change a character's appearance between scenes

IMAGE PROMPT RULES:
- Every image_prompt MUST start with "VERTICAL PORTRAIT 9:16 composition, tall narrow frame, "
- Always describe the camera angle (close-up, medium shot, wide shot from below, etc.)
- Include the full character description from the characters list for any character in the scene
- Describe the setting, mood, and lighting
- NEVER describe a wide/landscape/horizontal composition

Return your response as valid JSON with this exact structure:
{{
  "title": "Story Title",
  "characters": [
    {{
      "name": "Character Name",
      "description": "Gender, age ~X, [hair], [clothing], [distinguishing feature] - EXACT visual description"
    }}
  ],
  "scenes": [
    {{
      "index": 1,
      "text": "Scene narration text...",
      "image_prompt": "VERTICAL PORTRAIT 9:16 composition, tall narrow frame, [camera angle], [full character description from characters list], [setting], [mood/lighting]"
    }}
  ]
}}

IMPORTANT: image_prompt must be safe for AI image generation - describe mood and atmosphere instead of violence, weapons, or graphic content. Use metaphorical and artistic descriptions.
Return ONLY the JSON, no extra text."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    data = json.loads(raw)

    # Extract character descriptions for image consistency
    characters = data.get("characters", [])
    character_block = ""
    if characters:
        char_lines = []
        for c in characters:
            char_lines.append(f"{c['name']}: {c['description']}")
        character_block = "RECURRING CHARACTERS (use these exact descriptions): " + "; ".join(char_lines) + ". "

    scenes = [
        Scene(
            index=s["index"],
            text=s["text"],
            image_prompt=s["image_prompt"],
        )
        for s in data["scenes"]
    ]

    full_text = " ".join(s.text for s in scenes)
    word_count = len(full_text.split())

    return StoryResult(
        title=data.get("title", "Untitled"),
        full_text=full_text,
        scenes=scenes,
        language=lang,
        word_count=word_count,
        character_descriptions=character_block,
    )
