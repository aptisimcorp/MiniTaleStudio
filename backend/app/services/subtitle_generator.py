import os

from app.models import Scene


def _format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def generate_subtitles(scenes: list[Scene], total_duration: float, work_dir: str) -> str:
    srt_dir = os.path.join(work_dir, "subtitles")
    os.makedirs(srt_dir, exist_ok=True)
    output_path = os.path.join(srt_dir, "story.srt")

    # Distribute duration proportionally by word count
    total_words = sum(len(s.text.split()) for s in scenes)
    if total_words == 0:
        total_words = 1

    current_time = 0.0
    srt_entries = []

    for i, scene in enumerate(scenes):
        words = len(scene.text.split())
        scene_duration = (words / total_words) * total_duration
        scene.duration_seconds = scene_duration

        # Split scene text into subtitle chunks (~8-10 words each)
        words_list = scene.text.split()
        chunk_size = 8
        chunks = [
            " ".join(words_list[j : j + chunk_size])
            for j in range(0, len(words_list), chunk_size)
        ]
        if not chunks:
            chunks = [scene.text]

        chunk_duration = scene_duration / len(chunks) if chunks else scene_duration

        for chunk in chunks:
            start = current_time
            end = current_time + chunk_duration
            idx = len(srt_entries) + 1

            srt_entries.append(
                f"{idx}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{chunk}\n"
            )
            current_time = end

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))

    return output_path
