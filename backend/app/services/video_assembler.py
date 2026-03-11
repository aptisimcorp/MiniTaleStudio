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
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    afx,
)

from app.config import settings
from app.models import Scene, SubtitleStyle

# Background music volume relative to narration (0.0 - 1.0)
_MUSIC_VOLUME = 0.15

# Music directory -- pre-uploaded tracks in backend/app/workers/audio/
_MUSIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workers", "audio",
)

# Map each story category to the best-matching audio file.
# Multiple categories can share the same file.
_CATEGORY_MUSIC_MAP = {
    "horror":   "horror.wav",
    "crime":    "darkcrime.wav",
    "thriller": "strangemovements.wav",
    "mystery":  "nightthunder.wav",
    "funny":    "happy.wav",
    "history":  "nature.wav",
    "adult":    "windblowing.wav",
    "custom":   "nature.wav",
}

# Subtitle style presets (Pillow-based rendering)
SUBTITLE_STYLES = {
    SubtitleStyle.DEFAULT: {
        "fontsize": 42,
        "color": (255, 255, 255),
        "stroke_color": (0, 0, 0),
        "stroke_width": 3,
        "shadow_color": (0, 0, 0),
        "shadow_offset": (3, 3),
    },
    SubtitleStyle.BOLD: {
        "fontsize": 50,
        "color": (255, 255, 0),
        "stroke_color": (0, 0, 0),
        "stroke_width": 4,
        "shadow_color": (0, 0, 0),
        "shadow_offset": (4, 4),
    },
    SubtitleStyle.MINIMAL: {
        "fontsize": 38,
        "color": (255, 255, 255),
        "stroke_color": None,
        "stroke_width": 0,
        "shadow_color": (0, 0, 0),
        "shadow_offset": (2, 2),
    },
}

# Try to find a font that supports Hindi (Devanagari) and Latin scripts
_BUNDLED_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fonts")

def _get_font(size: int):
    """Return a TrueType font that supports Devanagari + Latin scripts."""
    # Build list of candidate paths: prefer Unicode-capable fonts first
    candidates = []

    # 1) Bundled fonts in backend/fonts/ (most reliable on any platform)
    if os.path.isdir(_BUNDLED_FONTS_DIR):
        for name in sorted(os.listdir(_BUNDLED_FONTS_DIR)):
            if name.lower().endswith((".ttf", ".otf")):
                candidates.append(os.path.join(_BUNDLED_FONTS_DIR, name))

    # 2) Platform-specific system fonts
    if sys.platform == "win32":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        candidates += [
            os.path.join(fonts_dir, "Nirmala.ttf"),
            os.path.join(fonts_dir, "NirmalaB.ttf"),
            os.path.join(fonts_dir, "arial.ttf"),
        ]
    else:
        # Linux: Noto fonts installed via apt (fonts-noto package)
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari[wdth,wght].ttf",
        ]
        # Search recursively for any Noto Devanagari font
        for search_dir in ["/usr/share/fonts", "/usr/local/share/fonts"]:
            if os.path.isdir(search_dir):
                for root, dirs, files in os.walk(search_dir):
                    for f in files:
                        if "devanagari" in f.lower() and f.endswith((".ttf", ".otf")):
                            candidates.append(os.path.join(root, f))
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]

    # 3) Generic names as fallback (Pillow searches system font dirs)
    candidates += ["NotoSansDevanagari-Regular.ttf", "NirmalaUI", "Nirmala.ttf", "arial.ttf", "DejaVuSans.ttf"]

    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            # Quick check: can it render a Devanagari character?
            try:
                bbox = font.getbbox("\u0905")  # ?
                if bbox and (bbox[2] - bbox[0]) > 0:
                    return font
            except Exception:
                pass
            # If Devanagari check fails, still usable for Latin -- keep searching
            # but remember this as a fallback
            if not hasattr(_get_font, "_latin_fallback"):
                _get_font._latin_fallback = font
        except (IOError, OSError):
            continue

    # Return best available: Latin fallback or Pillow default
    if hasattr(_get_font, "_latin_fallback"):
        print("[VideoAssembler] WARNING: No Devanagari font found, Hindi subtitles may show as blocks")
        return _get_font._latin_fallback
    print("[VideoAssembler] WARNING: No TrueType fonts found at all, using Pillow default")
    return ImageFont.load_default()


def _render_subtitle_frame(text: str, width: int, height: int, style: dict) -> np.ndarray:
    """Render a subtitle text into a transparent RGBA numpy array using Pillow.

    Text is centered both horizontally and vertically on the screen,
    with a drop shadow for readability on any background.
    """
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

    # Position at vertical center of the frame
    y_start = (height - total_text_height) // 2

    shadow_color = style.get("shadow_color", (0, 0, 0))
    shadow_offset = style.get("shadow_offset", (3, 3))

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = y_start + i * line_height

        # Draw drop shadow
        if shadow_color and shadow_offset:
            sx, sy = shadow_offset
            draw.text(
                (x + sx, y + sy), line, font=font,
                fill=shadow_color + (160,),
            )

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


def _get_music_path(category: str) -> str | None:
    """Find the best-matching background music file for the given category."""
    # Look up the mapped filename for this category
    filename = _CATEGORY_MUSIC_MAP.get(category.lower())
    if filename:
        path = os.path.join(_MUSIC_DIR, filename)
        if os.path.exists(path):
            return path

    # Fallback: try any file in the directory (first .wav, then .mp3)
    if os.path.isdir(_MUSIC_DIR):
        for f in sorted(os.listdir(_MUSIC_DIR)):
            if f.lower().endswith((".wav", ".mp3")):
                print(f"[VideoAssembler] No mapping for '{category}', falling back to {f}")
                return os.path.join(_MUSIC_DIR, f)

    print(f"[VideoAssembler] WARNING: No music files found in {_MUSIC_DIR}")
    return None


def assemble_video(
    scenes: list[Scene],
    narration_path: str,
    subtitle_path: str,
    subtitle_style: SubtitleStyle,
    work_dir: str,
    watermark_path: str = None,
    splash_start_path: str = None,
    splash_end_path: str = None,
    background_music: bool = False,
    category: str = "default",
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

    # Mix background music with narration if enabled
    if background_music:
        music_path = _get_music_path(category)
        if music_path:
            try:
                music = AudioFileClip(music_path)
                # Loop music to match narration duration
                if music.duration < total_duration:
                    loops_needed = int(total_duration / music.duration) + 1
                    music = concatenate_videoclips(
                        [music.to_soundarray for _ in range(loops_needed)]
                    ) if False else music.fx(afx.audio_loop, duration=total_duration)
                else:
                    music = music.subclip(0, total_duration)
                # Lower music volume so narration stays clear
                music = music.volumex(_MUSIC_VOLUME)
                # Mix narration + music
                mixed_audio = CompositeAudioClip([narration, music])
                video = video.set_audio(mixed_audio)
                print(f"[VideoAssembler] Background music added: {os.path.basename(music_path)} (vol={_MUSIC_VOLUME})")
            except Exception as e:
                print(f"[VideoAssembler] Background music failed, using narration only: {e}")
                video = video.set_audio(narration)
        else:
            print(f"[VideoAssembler] No music file found for category '{category}', skipping")
            video = video.set_audio(narration)
    else:
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

    # Cleanup -- close ALL clips to release memory
    try:
        final.close()
    except Exception:
        pass
    for clip in scene_clips:
        try:
            clip.close()
        except Exception:
            pass
    for clip in overlay_clips:
        try:
            clip.close()
        except Exception:
            pass
    try:
        narration.close()
    except Exception:
        pass
    try:
        video.close()
    except Exception:
        pass
    import gc
    gc.collect()

    return output_path


def assemble_video_from_clips(
    scenes: list[Scene],
    narration_path: str,
    subtitle_path: str,
    subtitle_style: SubtitleStyle,
    work_dir: str,
    watermark_path: str = None,
    splash_start_path: str = None,
    splash_end_path: str = None,
    background_music: bool = False,
    category: str = "default",
) -> str:
    """Assemble final video from Grok-generated video clips (MP4s) instead of images.

    This function merges individual scene video clips, adds narration,
    subtitles, background music, watermark, and splash screens.
    """
    width = settings.default_width
    height = settings.default_height
    fps = settings.default_fps

    # Load narration to get total duration
    narration = AudioFileClip(narration_path)
    total_duration = narration.duration

    # Load scene video clips
    scene_clips = []
    clip_objects = []  # track for cleanup
    total_clip_duration = 0

    for scene in scenes:
        if scene.video_clip_path and os.path.exists(scene.video_clip_path):
            clip = VideoFileClip(scene.video_clip_path).resize((width, height))
            clip_objects.append(clip)
            total_clip_duration += clip.duration
            scene_clips.append(clip)
        else:
            # Fallback: use image if video clip is missing
            if scene.image_path and os.path.exists(scene.image_path):
                word_count = len(scene.text.split())
                total_words = sum(len(s.text.split()) for s in scenes) or 1
                scene_dur = (word_count / total_words) * total_duration
                clip = (
                    ImageClip(scene.image_path)
                    .set_duration(scene_dur)
                    .resize((width, height))
                )
                clip_objects.append(clip)
                scene_clips.append(clip)
                print(f"[VideoAssembler] Scene {scene.index}: Fallback to image (no video clip)")
            else:
                print(f"[VideoAssembler] Scene {scene.index}: No video clip or image, skipping")

    if not scene_clips:
        raise RuntimeError("No scene clips available for video assembly")

    video = concatenate_videoclips(scene_clips, method="compose")

    # Speed-adjust video to match narration duration if needed
    if abs(video.duration - total_duration) > 1.0:
        speed_factor = video.duration / total_duration
        video = video.fx(lambda c: c.speedx(speed_factor))
        print(f"[VideoAssembler] Speed-adjusted clips: {speed_factor:.2f}x to match narration")

    # Mix audio (same logic as image-based assembly)
    if background_music:
        music_path = _get_music_path(category)
        if music_path:
            try:
                music = AudioFileClip(music_path)
                if music.duration < total_duration:
                    music = music.fx(afx.audio_loop, duration=total_duration)
                else:
                    music = music.subclip(0, total_duration)
                music = music.volumex(_MUSIC_VOLUME)
                mixed_audio = CompositeAudioClip([narration, music])
                video = video.set_audio(mixed_audio)
                print(f"[VideoAssembler] Background music added: {os.path.basename(music_path)}")
            except Exception as e:
                print(f"[VideoAssembler] Background music failed: {e}")
                video = video.set_audio(narration)
        else:
            video = video.set_audio(narration)
    else:
        video = video.set_audio(narration)

    # Subtitles overlay
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

    # Watermark
    if watermark_path and os.path.exists(watermark_path):
        try:
            wm_img = Image.open(watermark_path).convert("RGBA")
            wm_target_w = int(width * 0.15)
            wm_ratio = wm_target_w / wm_img.width
            wm_target_h = int(wm_img.height * wm_ratio)
            wm_img = wm_img.resize((wm_target_w, wm_target_h), Image.LANCZOS)
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
        except Exception as e:
            print(f"[VideoAssembler] Watermark failed: {e}")

    final = CompositeVideoClip([video] + overlay_clips, size=(width, height))

    # Splash screens
    clips_to_concat = []
    if splash_start_path and os.path.exists(splash_start_path):
        try:
            splash_start = ImageClip(splash_start_path).set_duration(3).resize((width, height))
            clips_to_concat.append(splash_start)
        except Exception:
            pass

    clips_to_concat.append(final)

    if splash_end_path and os.path.exists(splash_end_path):
        try:
            splash_end = ImageClip(splash_end_path).set_duration(3).resize((width, height))
            clips_to_concat.append(splash_end)
        except Exception:
            pass

    if len(clips_to_concat) > 1:
        final = concatenate_videoclips(clips_to_concat, method="compose")

    # Output
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

    # Cleanup -- close ALL clips to release memory
    try:
        final.close()
    except Exception:
        pass
    for clip in clip_objects:
        try:
            clip.close()
        except Exception:
            pass
    for clip in overlay_clips:
        try:
            clip.close()
        except Exception:
            pass
    try:
        narration.close()
    except Exception:
        pass
    try:
        video.close()
    except Exception:
        pass
    import gc
    gc.collect()

    print(f"[VideoAssembler] Grok clip assembly complete: {output_path}")
    return output_path
