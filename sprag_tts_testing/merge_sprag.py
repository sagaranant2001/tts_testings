import sys
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

DIALOGUES_FILE = ROOT / "dialogues.json"
if len(sys.argv) > 1:
    DIALOGUES_FILE = Path(sys.argv[1])
    if not DIALOGUES_FILE.exists():
        DIALOGUES_FILE = ROOT / sys.argv[1]

INPUT_DIR = SCRIPT_DIR / "output_sprag"
FINAL_DIR = SCRIPT_DIR / "final_sprag"
FINAL_DIR.mkdir(exist_ok=True)

PAUSE_SPEAKER_CHANGE = 0.4   # seconds of silence when the speaker changes
PAUSE_SAME_SPEAKER = 0.2     # seconds when the same speaker continues
EDGE_SILENCE = 0.3           # seconds at the start and end
NOISE_LEVEL = 0.0            # 0 = off. Try 0.01 to 0.03 for room noise

with open(DIALOGUES_FILE, encoding="utf-8") as f:
    DIALOGUES = json.load(f)


def read_clip(path):
    """Any WAV -> mono float32 samples in -1..1, plus its sample rate."""
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    return data.mean(axis=1), rate


def resample(x, from_rate, to_rate):
    if from_rate == to_rate:
        return x
    n = int(len(x) * to_rate / from_rate)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def merge_call(call):
    placed = []          # (start_sample, samples)
    rate = None
    prev_end = 0
    prev_speaker = None

    for i, turn in enumerate(call["turns"], start=1):
        speaker = turn["speaker"]
        path = INPUT_DIR / f"{call['id']}_{i:02d}_{speaker}.wav"
        if not path.exists():
            print(f"MISSING {path.name}, skipped")
            continue

        try:
            samples, clip_rate = read_clip(path)
        except Exception as e:
            print(f"UNREADABLE {path.name}: {e}")
            continue

        if rate is None:
            rate = clip_rate
        samples = resample(samples, clip_rate, rate)

        if prev_speaker is None:
            start = int(EDGE_SILENCE * rate)
        elif turn.get("overlap", 0) > 0:
            start = max(0, prev_end - int(turn["overlap"] * rate))
        else:
            default_gap = PAUSE_SPEAKER_CHANGE if speaker != prev_speaker else PAUSE_SAME_SPEAKER
            start = prev_end + int(turn.get("pause_before", default_gap) * rate)

        placed.append((start, samples))
        prev_end = max(prev_end, start + len(samples))
        prev_speaker = speaker

    if not placed:
        print(f"{call['id']}: nothing to merge")
        return

    total = prev_end + int(EDGE_SILENCE * rate)
    timeline = np.zeros(total, dtype=np.float32)
    for start, samples in placed:
        timeline[start:start + len(samples)] += samples

    if NOISE_LEVEL > 0:
        noise = np.random.normal(0, 1, total)
        noise = np.convolve(noise, np.ones(8) / 8, mode="same")   # softer, room-like
        timeline += (noise / noise.std() * NOISE_LEVEL).astype(np.float32)

    peak = float(np.abs(timeline).max())
    if peak > 0.99:                       # avoid clipping after overlaps or noise
        timeline *= 0.99 / peak

    out_path = FINAL_DIR / f"{call['id']}_full.wav"
    sf.write(str(out_path), timeline, rate, subtype="PCM_16")
    print(f"OK  {out_path}  ({len(placed)} turns, {total / rate:.1f}s, {rate} Hz)")


def main():
    for call in DIALOGUES:
        merge_call(call)


if __name__ == "__main__":
    main()