"""Generate simple ambient background music loops for each story category.

Each track is a 30-second WAV file with a low-volume ambient tone that
loops well under narration. These are intentionally subtle - just enough
to add atmosphere without drowning out the voice.

Run once:  python assets/music/generate_tracks.py
"""
import math
import struct
import wave
import os

SAMPLE_RATE = 44100
DURATION = 30  # seconds
AMPLITUDE = 2000  # low volume (max is 32767)

# Category -> (base_freq_hz, secondary_freq_hz, beat_freq_hz)
# Designed to evoke different moods
CATEGORY_TONES = {
    "horror":   (65.0,  82.0,  0.5),   # deep, ominous drone
    "thriller": (80.0,  100.0, 0.8),   # tense, pulsing
    "mystery":  (110.0, 138.6, 0.3),   # ethereal, floating
    "crime":    (73.4,  92.5,  0.6),   # dark, urban
    "funny":    (196.0, 246.9, 1.5),   # light, bouncy
    "history":  (130.8, 164.8, 0.4),   # grand, slow
    "adult":    (98.0,  123.5, 0.7),   # smooth, jazzy
    "custom":   (110.0, 146.8, 0.5),   # neutral ambient
}


def generate_track(filename: str, base_freq: float, sec_freq: float, beat_freq: float):
    """Generate a simple ambient WAV track."""
    n_samples = SAMPLE_RATE * DURATION
    samples = []

    for i in range(n_samples):
        t = i / SAMPLE_RATE
        # Fade in/out over first/last 2 seconds for smooth looping
        fade = 1.0
        if t < 2.0:
            fade = t / 2.0
        elif t > DURATION - 2.0:
            fade = (DURATION - t) / 2.0

        # Mix two sine waves with a slow amplitude modulation (beat)
        beat = 0.5 + 0.5 * math.sin(2 * math.pi * beat_freq * t)
        val = (
            0.6 * math.sin(2 * math.pi * base_freq * t)
            + 0.4 * math.sin(2 * math.pi * sec_freq * t)
        ) * beat * fade * AMPLITUDE

        samples.append(int(max(-32767, min(32767, val))))

    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    size_kb = os.path.getsize(filename) / 1024
    print(f"  Created: {filename} ({size_kb:.0f} KB)")


def main():
    music_dir = os.path.dirname(os.path.abspath(__file__))

    print("Generating background music tracks...")
    for category, (base, sec, beat) in CATEGORY_TONES.items():
        filepath = os.path.join(music_dir, f"{category}.wav")
        generate_track(filepath, base, sec, beat)

    # Also create a "default" track (copy of custom)
    default_path = os.path.join(music_dir, "default.wav")
    base, sec, beat = CATEGORY_TONES["custom"]
    generate_track(default_path, base, sec, beat)

    print(f"\nDone! {len(CATEGORY_TONES) + 1} tracks generated in {music_dir}")


if __name__ == "__main__":
    main()
