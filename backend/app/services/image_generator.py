import os
import requests
from openai import OpenAI, BadRequestError
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.models import ImageStyle, Scene


# Strict style instructions for DALL-E  -  each style is heavily described
# so the model cannot deviate from the requested aesthetic.
STYLE_MODIFIERS = {
    ImageStyle.LEGO: (
        "Rendered entirely as LEGO bricks and minifigures. "
        "Plastic toy aesthetic, ABS plastic texture, stud details on every surface, "
        "bright primary colors, miniature LEGO world, toy photography style"
    ),
    ImageStyle.COMIC_BOOK: (
        "Classic comic book art style with bold black ink outlines, "
        "Ben-Day dots halftone pattern, speech bubble aesthetic, "
        "dramatic panel composition, vivid saturated colors, Marvel/DC comic look"
    ),
    ImageStyle.DISNEY_TOON: (
        "Walt Disney classic animation style, smooth cel-shaded characters, "
        "big expressive eyes, rounded soft features, warm magical color palette, "
        "fairy-tale atmosphere, Disney Renaissance aesthetic"
    ),
    ImageStyle.STUDIO_GHIBLI: (
        "Studio Ghibli animation style by Hayao Miyazaki, hand-painted backgrounds, "
        "soft pastel watercolor skies, lush detailed nature, whimsical atmosphere, "
        "gentle lighting, nostalgic Japanese animation aesthetic"
    ),
    ImageStyle.PIXELATED: (
        "Retro pixel art style, 16-bit video game aesthetic, "
        "visible square pixels, limited color palette, dithering effects, "
        "nostalgic retro gaming look, crisp pixel edges"
    ),
    ImageStyle.CREEPY_TOON: (
        "Dark creepy cartoon style, Tim Burton inspired aesthetic, "
        "exaggerated angular features, gothic color palette of blacks and purples, "
        "eerie shadows, unsettling whimsical atmosphere, Coraline-like look"
    ),
    ImageStyle.CHILDRENS_BOOK: (
        "Charming children's book illustration, soft watercolor and crayon textures, "
        "gentle rounded shapes, warm friendly color palette, "
        "storybook page aesthetic, innocent and whimsical feel"
    ),
    ImageStyle.PHOTO_REALISM: (
        "Photorealistic image, ultra high detail, natural lighting, "
        "shot on Canon EOS R5, 85mm lens, shallow depth of field, "
        "8K resolution quality, lifelike textures and materials"
    ),
    ImageStyle.MINECRAFT: (
        "Minecraft game world style, everything built from cubic voxel blocks, "
        "blocky characters and terrain, Minecraft texture pack aesthetic, "
        "square sun, pixelated trees, recognizable Minecraft look"
    ),
    ImageStyle.WATERCOLOR: (
        "Traditional watercolor painting, soft wet-on-wet blending, "
        "visible brush strokes and paint bleeding, textured watercolor paper, "
        "translucent color washes, impressionistic fine art aesthetic"
    ),
    ImageStyle.EXPRESSIONISM: (
        "German Expressionism art style, bold distorted forms, "
        "intense emotional color contrasts, angular exaggerated shapes, "
        "thick impasto brush strokes, Edvard Munch and Kirchner inspired"
    ),
    ImageStyle.CHARCOAL: (
        "Charcoal drawing on textured paper, dramatic chiaroscuro lighting, "
        "smudged graphite shading, black and white with gray tones, "
        "raw sketchy line work, fine art charcoal illustration"
    ),
    ImageStyle.GTAV: (
        "Grand Theft Auto V loading screen art style, "
        "stylized semi-realistic illustration, bold outlines with cel shading, "
        "saturated pop colors, urban gritty aesthetic, Rockstar Games art look"
    ),
    ImageStyle.ANIME: (
        "Japanese anime art style, sharp clean line art, "
        "large detailed eyes, vibrant hair colors, dynamic action poses, "
        "cel-shaded coloring, modern anime aesthetic like Demon Slayer"
    ),
    ImageStyle.FILM_NOIR: (
        "Classic film noir cinematic style, high contrast black and white, "
        "dramatic venetian blind shadow patterns, moody atmospheric lighting, "
        "1940s detective movie aesthetic, rain-slicked streets"
    ),
    ImageStyle.THREE_D_TOON: (
        "3D cartoon render style like Pixar or Illumination Studios, "
        "smooth subsurface scattering on skin, glossy plastic-like materials, "
        "exaggerated proportions, vibrant 3D animated movie look"
    ),
}

# Safety prefix injected into every prompt to reduce content-filter rejections
SAFETY_PREFIX = (
    "Safe-for-work digital illustration suitable for all ages. "
    "No violence, blood, weapons, gore, nudity, or suggestive content. "
    "Family-friendly, non-threatening imagery only. "
)

# Words / phrases that commonly trigger OpenAI content filters
_TRIGGER_WORDS = [
    # violence / gore
    "blood", "bloody", "gore", "gory", "murder", "murdered", "murderer",
    "kill", "killed", "killing", "killer", "death", "dead body", "corpse",
    "weapon", "gun", "pistol", "rifle", "shotgun", "bullet",
    "knife", "blade", "sword", "dagger", "axe",
    "stab", "stabbed", "stabbing", "slash", "slashed",
    "strangle", "strangled", "strangling", "choke", "choked",
    "violent", "violence", "attack", "attacked", "assault",
    "horror", "terrifying", "terrified", "horrifying", "gruesome",
    "disturbing", "torture", "tortured", "scream", "screaming",
    "wound", "wounded", "bleed", "bleeding", "bruise", "scar",
    "dismember", "decapitate", "mutilate", "butcher",
    "poison", "poisoned", "suffocate", "suffocated",
    "fight", "fighting", "punch", "punched", "beaten",
    # sexual / explicit
    "explicit", "nude", "naked", "sexy", "seductive", "sensual",
    "erotic", "provocative", "intimate", "undressed", "lingerie",
    # horror-adjacent atmosphere
    "demonic", "demon", "satan", "satanic", "devil", "possessed",
    "evil spirit", "dark ritual", "sacrifice", "sacrificial",
    "haunted", "ghost", "phantom", "apparition",
    "cemetery", "graveyard", "tombstone",
    # threatening imagery
    "kidnap", "kidnapped", "hostage", "captive",
    "stalker", "stalking", "prey", "predator",
    "threatening", "menacing", "sinister",
]


# Path to bundled fonts directory (backend/fonts/)
_BUNDLED_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "fonts",
)


def _get_devanagari_font(size: int):
    """Find a font that supports Devanagari (Hindi) text."""
    candidates = []
    # Bundled fonts first (most reliable)
    if os.path.isdir(_BUNDLED_FONTS_DIR):
        for name in sorted(os.listdir(_BUNDLED_FONTS_DIR)):
            if name.lower().endswith((".ttf", ".otf")):
                candidates.append(os.path.join(_BUNDLED_FONTS_DIR, name))
    # System fonts
    candidates += [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _create_placeholder_image(image_path: str, text: str) -> str:
    """Generate a dark gradient placeholder when DALL-E refuses the prompt."""
    img = Image.new("RGB", (1024, 1792), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    font = _get_devanagari_font(32)
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > 30:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    y = 800
    for ln in lines[:6]:
        draw.text((80, y), ln, fill=(148, 163, 184), font=font)
        y += 44
    img.save(image_path, "PNG")
    return image_path


def _sanitize_prompt(prompt: str) -> str:
    """Strip potentially triggering words and re-frame for safety."""
    sanitized = prompt
    for word in _TRIGGER_WORDS:
        # Case-insensitive replacement with a neutral phrase
        for variant in (word, word.capitalize(), word.upper()):
            sanitized = sanitized.replace(variant, "mysterious scene")
    return SAFETY_PREFIX + sanitized


def _build_safe_fallback_prompt(scene: Scene, style_mod: str) -> str:
    """Build a heavily sanitized last-resort prompt focusing only on setting and mood.

    Strips the original image_prompt entirely and generates from the
    narration text, keeping only safe visual elements.
    """
    # Take only the first 200 chars of scene text, sanitized
    safe_text = scene.text[:200]
    for word in _TRIGGER_WORDS:
        for variant in (word, word.capitalize(), word.upper()):
            safe_text = safe_text.replace(variant, "")

    return (
        f"{SAFETY_PREFIX}"
        f"STRICT ART STYLE: {style_mod}. "
        f"VERTICAL PORTRAIT 9:16 composition, tall narrow frame. "
        f"A calm, atmospheric scene inspired by this narration: \"{safe_text.strip()}\". "
        f"Focus on the setting, environment, and mood. "
        f"Show landscape, architecture, or nature. "
        f"Soft cinematic lighting, peaceful composition. "
        f"Do NOT depict any violence, conflict, or distress."
    )


def generate_scene_image(
    scene: Scene,
    image_style: ImageStyle,
    work_dir: str,
    character_descriptions: str = "",
) -> str:
    client = OpenAI(api_key=settings.openai_api_key)

    style_mod = STYLE_MODIFIERS.get(image_style, STYLE_MODIFIERS[ImageStyle.PHOTO_REALISM])

    base_prompt = (
        "This image MUST be composed for a smartphone screen in portrait orientation.\n\n"
        "Aspect ratio: 9:16 vertical.\n\n"
        "Camera orientation:\n"
        "A phone camera held upright capturing a tall vertical frame.\n\n"
        "Composition rules:\n"
        "- portrait photography framing\n"
        "- vertical cinematic composition\n"
        "- subject arranged from top to bottom\n"
        "- tall narrow frame\n"
        "- character centered in vertical space\n"
        "- sky/background at top\n"
        "- ground/environment at bottom\n\n"
        f"STRICT ART STYLE:\n{style_mod}\n\n"
        f"CHARACTER DESIGN (must stay consistent):\n{character_descriptions}\n\n"
        f"SCENE DESCRIPTION:\n{scene.image_prompt}\n\n"
        "CINEMATIC DETAILS:\n"
        "beautiful lighting, depth, atmospheric perspective, high detail\n\n"
        "NEGATIVE COMPOSITION RULES:\n"
        "do NOT create landscape image\n"
        "do NOT create horizontal frame\n"
        "do NOT create widescreen composition\n"
        "do NOT create square image\n"
        "do NOT create panoramic shot\n\n"
        "FINAL OUTPUT FORMAT:\n"
        "Designed for TikTok, Instagram Reels, and YouTube Shorts vertical video frame.\n\n"
        "Portrait orientation. 9:16 vertical composition. Tall mobile screen layout."
    )

    image_path = os.path.join(work_dir, f"scene_{scene.index:03d}.png")

    prompts_to_try = [
        SAFETY_PREFIX + base_prompt,                          # Attempt 1: original + safety prefix
        _sanitize_prompt(base_prompt),                        # Attempt 2: word-level sanitized
        _build_safe_fallback_prompt(scene, style_mod),        # Attempt 3: environment-only fallback
    ]

    for attempt, prompt in enumerate(prompts_to_try):
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt[:4000],
                size="1024x1792",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            img_data = requests.get(image_url, timeout=120).content
            with open(image_path, "wb") as f:
                f.write(img_data)

            # Log raw dimensions before enforcement
            raw_img = Image.open(image_path)
            rw, rh = raw_img.size
            raw_img.close()
            if rw > rh:
                print(f"[ImageGen] Scene {scene.index} DALL-E returned LANDSCAPE ({rw}x{rh}), will crop to portrait")
            elif rw == rh:
                print(f"[ImageGen] Scene {scene.index} DALL-E returned SQUARE ({rw}x{rh}), will crop to portrait")

            # Verify and enforce exact 9:16 portrait orientation
            _enforce_portrait_orientation(image_path)

            if attempt > 0:
                print(f"[ImageGen] Scene {scene.index} succeeded on attempt {attempt+1}")
            return image_path

        except BadRequestError as e:
            if "content_policy_violation" in str(e):
                label = ["original+prefix", "sanitized", "safe-fallback"][attempt]
                print(f"[ImageGen] Scene {scene.index} attempt {attempt+1} ({label}) blocked by content filter, retrying...")
                continue
            raise

    print(f"[ImageGen] Scene {scene.index} - all 3 prompts blocked, using placeholder image")
    return _create_placeholder_image(image_path, scene.text[:120])


def _enforce_portrait_orientation(image_path: str, target_w: int = 1024, target_h: int = 1792):
    """Ensure image is strictly portrait 9:16.

    If DALL-E returns a landscape or square image, smart-crop to portrait
    (center-crop the width) then resize. Never rotate -- that makes content sideways.
    """
    img = Image.open(image_path)
    w, h = img.size

    if w == target_w and h == target_h:
        return

    # Log if DALL-E ignored our portrait request
    if w > h:
        print(f"[ImageGen] WARNING: DALL-E returned landscape ({w}x{h}), cropping to portrait")
    elif w == h:
        print(f"[ImageGen] WARNING: DALL-E returned square ({w}x{h}), cropping to portrait")

    # Center-crop to target aspect ratio then resize
    target_ratio = target_w / target_h
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Too wide -- crop sides (center-crop horizontally)
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif current_ratio < target_ratio:
        # Too tall -- crop top/bottom (center-crop vertically)
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)
    img.save(image_path, "PNG")


def generate_all_images(
    scenes: list[Scene],
    image_style: ImageStyle,
    work_dir: str,
    character_descriptions: str = "",
) -> list[Scene]:
    images_dir = os.path.join(work_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    for scene in scenes:
        path = generate_scene_image(scene, image_style, images_dir, character_descriptions)
        scene.image_path = path

    return scenes
