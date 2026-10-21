import os
import sys
import csv
import json
import time
import random
from pathlib import Path

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
load_dotenv(ROOT / ".env")
load_dotenv()

API_KEY = os.getenv("SPRAG_API_KEY") or os.getenv("SPRAG_AI_KEY")
if not API_KEY:
    raise SystemExit("SPRAG_API_KEY missing. Check your .env file.")

URL = "https://api.sprag.ai/v1/audio/speech"
MODEL = "chorus"
RESPONSE_FORMAT = "wav"      # wav so merge_audio.py can join the clips
REQUEST_GAP = 1.1            # docs: 60 requests per 60 seconds per organization

# Change these to voices from GET https://api.sprag.ai/v1/audio/voices?model=chorus
AGENT_VOICE = "dominic"
CUSTOMER_VOICES = {
    "female": ["marin", "serena"],
    "male": ["wade"],
}

# Emotion = style guidance sent in the "instructions" field
EMOTION_INSTRUCTIONS = {
    "neutral": "",
    "warm": "Speak in a warm, friendly, professional tone.",
    "gentle": "Speak gently and softly, with sympathy and care.",
    "sad": "Speak quietly and slowly, in a sad, subdued voice.",
    "tearful": "Speak in a tearful voice, with a slight tremble, slowly.",
    "crying": "Speak while crying, with a shaky voice, pausing to catch your breath.",
    "urgent": "Speak quickly and urgently.",
}

DIALOGUES_FILE = ROOT / "dialogues.json"
if len(sys.argv) > 1:
    DIALOGUES_FILE = Path(sys.argv[1])
    if not DIALOGUES_FILE.exists():
        DIALOGUES_FILE = ROOT / sys.argv[1]

OUTPUT_DIR = SCRIPT_DIR / "output_sprag"
OUTPUT_DIR.mkdir(exist_ok=True)

with open(DIALOGUES_FILE, encoding="utf-8") as f:
    DIALOGUES = json.load(f)


def pick_voice(call, speaker):
    if speaker == "agent":
        return call.get("sprag_agent_voice", AGENT_VOICE)
    if call.get("sprag_customer_voice"):
        return call["sprag_customer_voice"]
    pool = CUSTOMER_VOICES.get(call.get("customer_gender")) or \
        [v for voices in CUSTOMER_VOICES.values() for v in voices]
    return random.Random(call["id"]).choice(pool)


def error_detail(response):
    detail = response.text
    try:
        detail = response.json()["error"]["message"]
    except Exception:
        pass
    return f"HTTP {response.status_code} {response.reason} - {detail}"


def tts(text, voice, instructions, out_file, speed=None, retries=3):
    payload = {
        "model": MODEL,
        "input": text,
        "voice": voice,
        "response_format": RESPONSE_FORMAT,
    }
    if instructions:
        payload["instructions"] = instructions
    if speed:
        payload["speed"] = speed

    used_instructions = bool(instructions)

    for attempt in range(1, retries + 1):
        t0 = time.time()
        try:
            response = requests.post(
                URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json=payload,
                timeout=120,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"Attempt {attempt}/{retries} failed: {type(e).__name__}")
            time.sleep(2 * attempt)
            continue

        latency = time.time() - t0

        if response.ok:
            out_file.write_bytes(response.content)
            return len(text), latency, used_instructions

        if response.status_code in (429, 503):
            wait = float(response.headers.get("Retry-After", 5 * attempt))
            print(f"{response.status_code}, waiting {wait:.0f}s")
            time.sleep(wait)
            continue

        if response.status_code == 400 and "instructions" in payload:
            print(f"Instructions rejected ({error_detail(response)}). Retrying without them.")
            payload.pop("instructions")
            used_instructions = False
            continue

        print(f"FAILED {voice}: {error_detail(response)}")
        return None, latency, used_instructions

    print(f"GAVE UP on {out_file.name}")
    return None, 0, used_instructions


def main():
    total_chars = 0
    results_file = SCRIPT_DIR / "results_sprag.csv"

    with open(results_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["call_id", "turn", "speaker", "voice", "emotion",
                         "instructions_used", "chars", "latency_s", "file"])

        for call in DIALOGUES:
            print(f"\n{call['id']}: agent={pick_voice(call, 'agent')}, "
                  f"customer={pick_voice(call, 'customer')}")

            for i, turn in enumerate(call["turns"], start=1):
                speaker = turn["speaker"]
                voice = pick_voice(call, speaker)
                emotion = turn.get("emotion", "neutral")
                instructions = turn.get("instructions", EMOTION_INSTRUCTIONS.get(emotion, ""))
                text = turn.get("tts_text", turn["text"])
                out = OUTPUT_DIR / f"{call['id']}_{i:02d}_{speaker}.wav"

                chars, latency, used = tts(text, voice, instructions, out, speed=turn.get("speed"))
                if chars:
                    total_chars += chars
                    writer.writerow([call["id"], i, speaker, voice, emotion,
                                     used, chars, f"{latency:.2f}", out])
                    print(f"OK  {out.name}  [{emotion}, instructions={used}]  ({latency:.2f}s)")
                time.sleep(REQUEST_GAP)

    print(f"\nDone. Total characters sent: {total_chars}")
    print(f"Results: {results_file}")


if __name__ == "__main__":
    main()