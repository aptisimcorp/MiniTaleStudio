import os
import sys
from datetime import datetime

# Pillow 10+ removed ANTIALIAS; moviepy 1.0.3 still references it
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from app.config import settings
from app.models import Scene, SubtitleStyle

# Subtitle style presets (Pillow-based rendering)
SUBTITLE_STYLES = {
    SubtitleStyle.DEFAULT: {
        "fontsize": 42,
        "color": (255, 255, 255),
        "stroke_color": (0, 0, 0),
        "stroke_width": 3,
    },
    SubtitleStyle.BOLD: {
        "fontsize": 50,
        "color": (255, 255, 0),
        "stroke_color": (0, 0, 0),
        "stroke_width": 4,
    },
    SubtitleStyle.MINIMAL: {
        "fontsize": 38,
        "color": (255, 255, 255),
        "stroke_color": None,
        "stroke_width": 0,
    },
}

# Try to find a font that supports Hindi (Devanagari) and Latin scripts
def _get_font(size: int):
    # Build list of candidate paths: prefer Unicode-capable fonts first
    candidates = []
    if sys.platform == "win32":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        # Nirmala UI: ships with Windows, supports Devanagari + Latin
        candidates += [
            os.path.join(fonts_dir, "Nirmala.ttf"),
            os.path.join(fonts_dir, "NirmalaB.ttf"),
            os.path.join(fonts_dir, "arial.ttf"),
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    # Generic names as fallback (Pillow searches system font dirs)
    candidates += ["NirmalaUI", "Nirmala.ttf", "arial.ttf", "DejaVuSans.ttf"]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _render_subtitle_frame(text: str, width: int, height: int, style: dict) -> np.ndarray:
    """Render a subtitle text into a transparent RGBA numpy array using Pillow."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _get_font(style["fontsize"])

    # Word-wrap the text
    max_width = width - 80
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Calculate total text height
    line_height = style["fontsize"] + 8
    total_text_height = len(lines) * line_height

    # Position at bottom of frame
    y_start = height - total_text_height - 60

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = y_start + i * line_height

        # Draw stroke/outline
        if style.get("stroke_color") and style.get("stroke_width", 0) > 0:
            sw = style["stroke_width"]
            sc = style["stroke_color"]
            for dx in range(-sw, sw + 1):
                for dy in range(-sw, sw + 1):
                    if dx * dx + dy * dy <= sw * sw:
                        draw.text((x + dx, y + dy), line, font=font, fill=sc + (255,))

        # Draw text
        draw.text((x, y), line, font=font, fill=style["color"] + (255,))

    return np.array(img)


def _parse_srt(srt_path: str) -> list[dict]:
    entries = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    blocks = content.split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        time_line = lines[1]
        text = " ".join(lines[2:])
        parts = time_line.split(" --> ")
        start = _srt_time_to_seconds(parts[0].strip())
        end = _srt_time_to_seconds(parts[1].strip())
        entries.append({"start": start, "end": end, "text": text})

    return entries


def _srt_time_to_seconds(t: str) -> float:
    parts = t.replace(",", ".").split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def assemble_video(
    scenes: list[Scene],
    narration_path: str,
    subtitle_path: str,
    subtitle_style: SubtitleStyle,
    work_dir: str,
    watermark_path: str = None,
    splash_start_path: str = None,
    splash_end_path: str = None,
) -> str:
    width = settings.default_width
    height = settings.default_height
    fps = settings.default_fps

    # Load narration to get total duration
    narration = AudioFileClip(narration_path)
    total_duration = narration.duration

    # Calculate per-scene duration proportionally
    total_words = sum(len(s.text.split()) for s in scenes)
    if total_words == 0:
        total_words = 1

    scene_clips = []
    for scene in scenes:
        word_count = len(scene.text.split())
        scene_dur = (word_count / total_words) * total_duration

        if scene.image_path and os.path.exists(scene.image_path):
            clip = (
                ImageClip(scene.image_path)
                .set_duration(scene_dur)
                .resize((width, height))
            )
        else:
            clip = (
                ImageClip(np.zeros((height, width, 3), dtype="uint8"))
                .set_duration(scene_dur)
            )
        scene_clips.append(clip)

    video = concatenate_videoclips(scene_clips, method="compose")
    video = video.set_audio(narration)

    # Overlay subtitles using Pillow-rendered frames (no ImageMagick needed)
    style = SUBTITLE_STYLES.get(subtitle_style, SUBTITLE_STYLES[SubtitleStyle.DEFAULT])
    srt_entries = _parse_srt(subtitle_path)

    overlay_clips = []
    for entry in srt_entries:
        try:
            frame = _render_subtitle_frame(entry["text"], width, height, style)
            sub_clip = (
                ImageClip(frame, ismask=False, transparent=True)
                .set_start(entry["start"])
                .set_duration(entry["end"] - entry["start"])
                .set_position((0, 0))
            )
            overlay_clips.append(sub_clip)
        except Exception as e:
            print(f"[Subtitles] Skipping entry: {e}")
            continue

    # Watermark overlay (top-left, semi-transparent, for entire video duration)
    if watermark_path and os.path.exists(watermark_path):
        try:
            wm_img = Image.open(watermark_path).convert("RGBA")
            # Scale watermark to ~15% of video width, maintain aspect ratio
            wm_target_w = int(width * 0.15)
            wm_ratio = wm_target_w / wm_img.width
            wm_target_h = int(wm_img.height * wm_ratio)
            wm_img = wm_img.resize((wm_target_w, wm_target_h), Image.LANCZOS)
            # Set semi-transparency
            alpha = wm_img.split()[3]
            alpha = alpha.point(lambda p: int(p * 0.7))
            wm_img.putalpha(alpha)
            wm_array = np.array(wm_img)
            wm_clip = (
                ImageClip(wm_array, ismask=False, transparent=True)
                .set_duration(video.duration)
                .set_position((30, 30))
            )
            overlay_clips.append(wm_clip)
            print(f"[VideoAssembler] Watermark added: {wm_target_w}x{wm_target_h}")
        except Exception as e:
            print(f"[VideoAssembler] Watermark failed: {e}")

    final = CompositeVideoClip([video] + overlay_clips, size=(width, height))

    # Prepend splash start screen (3 seconds, static image)
    clips_to_concat = []
    if splash_start_path and os.path.exists(splash_start_path):
        try:
            splash_start = (
                ImageClip(splash_start_path)
                .set_duration(3)
                .resize((width, height))
            )
            clips_to_concat.append(splash_start)
            print("[VideoAssembler] Splash start screen added (3s)")
        except Exception as e:
            print(f"[VideoAssembler] Splash start failed: {e}")

    clips_to_concat.append(final)

    # Append splash end screen (3 seconds, static image)
    if splash_end_path and os.path.exists(splash_end_path):
        try:
            splash_end = (
                ImageClip(splash_end_path)
                .set_duration(3)
                .resize((width, height))
            )
            clips_to_concat.append(splash_end)
            print("[VideoAssembler] Splash end screen added (3s)")
        except Exception as e:
            print(f"[VideoAssembler] Splash end failed: {e}")

    if len(clips_to_concat) > 1:
        final = concatenate_videoclips(clips_to_concat, method="compose")

    # Output path
    videos_dir = os.path.join(settings.output_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(videos_dir, f"story_{timestamp}.mp4")

    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
    )

    # Cleanup
    narration.close()
    final.close()
    for clip in scene_clips:
        clip.close()

    return output_path
