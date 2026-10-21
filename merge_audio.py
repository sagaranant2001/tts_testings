import os
import re
import wave
from collections import defaultdict

INPUT_DIR = "output"
FINAL_DIR = "final"

PAUSE_SPEAKER_CHANGE = 0.5   # seconds of silence when the speaker changes
PAUSE_SAME_SPEAKER = 0.25    # seconds of silence between two turns by the same speaker

os.makedirs(FINAL_DIR, exist_ok=True)

# matches: <call_id>_<turn number>_<speaker>.wav
PATTERN = re.compile(r"^(.*)_(\d+)_(agent|customer)\.wav$")


def group_files():
    calls = defaultdict(list)
    for name in os.listdir(INPUT_DIR):
        m = PATTERN.match(name)
        if m:
            call_id, turn, speaker = m.group(1), int(m.group(2)), m.group(3)
            calls[call_id].append((turn, speaker, os.path.join(INPUT_DIR, name)))
    for call_id in calls:
        calls[call_id].sort()  # sort by turn number
    return calls


def silence(seconds, params):
    n_frames = int(params.framerate * seconds)
    return b"\x00" * (n_frames * params.nchannels * params.sampwidth)


def merge_call(call_id, items):
    out_path = os.path.join(FINAL_DIR, f"{call_id}_full.wav")
    out = None
    prev_speaker = None
    total_seconds = 0.0

    for turn, speaker, path in items:
        with wave.open(path, "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())

        if out is None:
            out = wave.open(out_path, "wb")
            out.setnchannels(params.nchannels)
            out.setsampwidth(params.sampwidth)
            out.setframerate(params.framerate)
            base = params
        elif (params.framerate, params.nchannels, params.sampwidth) != \
             (base.framerate, base.nchannels, base.sampwidth):
            print(f"SKIPPED {path}: audio format differs from the first clip")
            continue

        if prev_speaker is not None:
            gap = PAUSE_SPEAKER_CHANGE if speaker != prev_speaker else PAUSE_SAME_SPEAKER
            out.writeframes(silence(gap, base))
            total_seconds += gap

        out.writeframes(frames)
        total_seconds += len(frames) / (base.framerate * base.nchannels * base.sampwidth)
        prev_speaker = speaker

    if out:
        out.close()
        print(f"OK  {out_path}  ({len(items)} turns, {total_seconds:.1f}s)")


def main():
    calls = group_files()
    if not calls:
        raise SystemExit("No matching .wav files found in the output folder.")
    for call_id, items in calls.items():
        merge_call(call_id, items)


if __name__ == "__main__":
    main()