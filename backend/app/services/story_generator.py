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


def generate_story(config: ConfigurationCreate, character_prompt_block: str = "") -> StoryResult:
    client = OpenAI(api_key=settings.openai_api_key)

    min_words, max_words = WORD_TARGETS[config.duration]
    min_scenes, max_scenes = SCENE_COUNTS[config.duration]
    category = config.custom_category if config.category.value == "custom" and config.custom_category else config.category.value
    lang = "Hindi" if config.language == Language.HINDI else "English"

    # Determine if we need video_prompt (for Grok pipeline)
    use_video_prompts = config.ai_service.value == "grok" if hasattr(config, 'ai_service') else False

    system_prompt = (
        "You are a master storyteller who creates gripping short stories for vertical video platforms "
        "(YouTube Shorts, Instagram Reels, TikTok). "
        "Your stories follow this structure: Hook -> Setup -> Rising tension -> Climax -> Twist ending. "
        "CRITICAL: You must define consistent character appearances upfront and reference them in every scene."
    )

    # Insert character block if provided (from character_service)
    character_section = ""
    if character_prompt_block:
        character_section = f"""
{character_prompt_block}

"""

    video_prompt_instruction = ""
    video_prompt_json = ""
    if use_video_prompts:
        video_prompt_instruction = """
VIDEO PROMPT RULES (for animated video generation):
- Each scene MUST include a 'video_prompt' field
- video_prompt is a SELF-CONTAINED visual description used to generate an animated video clip
- CRITICAL: Every video_prompt MUST repeat the FULL physical appearance of EVERY character present in that scene
  (name, gender, age, hair color/style, clothing, skin tone, body build, distinguishing features)
- Describe the motion, action, body language, and facial expressions of each character
- Describe camera movement (slow zoom in, tracking shot, static wide shot, etc.)
- Describe the environment, lighting, time of day, weather, colors
- video_prompt should be 3-5 detailed sentences
- NEVER refer to characters by name only -- always include their full visual description
- Example: Instead of "Aanya walks into the room" write "A confident woman in her late 20s with long wavy dark hair, expressive brown eyes, wearing a fitted olive jacket and dark jeans, walks purposefully into a dimly lit room with cracked walls and flickering fluorescent lights"
"""
        video_prompt_json = ',\n      "video_prompt": "Self-contained cinematic description with FULL character appearances, actions, camera angle, setting, lighting"'

    user_prompt = f"""Create a {category} short story in {lang}.
{character_section}
Requirements:
- Word count: {min_words}-{max_words} words
- Split the story into exactly {min_scenes} to {max_scenes} scenes
- Each scene should be 1-3 sentences that paint a vivid visual picture
- Start with a compelling hook
- End with an unexpected twist

CHARACTER CONSISTENCY RULES:
- Define 1-3 main characters with FIXED visual descriptions
- Each character must have: name, gender, approximate age, ethnicity/skin tone, hair color/style, body build, clothing, and one distinguishing feature
- These EXACT descriptions must be repeated WORD FOR WORD in EVERY image_prompt AND video_prompt where that character appears
- Never change a character's appearance between scenes
- A reader of any single scene prompt should be able to perfectly visualize each character without seeing other scenes

IMAGE PROMPT RULES:
- Every image_prompt MUST start with "VERTICAL PORTRAIT 9:16 composition, tall narrow frame, "
- Always describe the camera angle (close-up, medium shot, wide shot from below, etc.)
- Include the full character description from the characters list for any character in the scene
- Describe the setting, mood, and lighting
- NEVER describe a wide/landscape/horizontal composition
{video_prompt_instruction}
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
      "image_prompt": "VERTICAL PORTRAIT 9:16 composition, tall narrow frame, [camera angle], [full character description from characters list], [setting], [mood/lighting]"{video_prompt_json}
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
            video_prompt=s.get("video_prompt"),
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
