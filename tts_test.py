import os
import csv
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SMALLEST_API_KEY")

URL = "https://api.smallest.ai/waves/v1/lightning-v3.1/get_speech"
VOICES_URL = "https://api.smallest.ai/waves/v1/lightning-v3.1/get_voices"

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_RATE = 24000
MODEL = "lightning_v3.1"
LANGUAGE = "en"
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5

VOICE_MAP = {
    "agent": "magnus",      # male, "Customer support agent"
    "customer": "chloe",    # female, "Customer support agent"
}

with open("dialogues.json", encoding="utf-8") as f:
    DIALOGUES = json.load(f)


def error_detail(response):
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def validate_voices(voices):
    response = requests.get(VOICES_URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
    response.raise_for_status()
    catalog = {v["voiceId"] for v in response.json()["voices"]}
    invalid = {v for v in voices.values() if v not in catalog}
    if invalid:
        raise SystemExit(
            f"Invalid voice id(s): {', '.join(sorted(invalid))}. "
            f"List valid ids with: GET {VOICES_URL}"
        )


def tts(text, voice_id, sample_rate, out_file):
    payload = {
        "text": text,
        "voice_id": voice_id,
        "model": MODEL,
        "sample_rate": sample_rate,
        "speed": 1.0,
        "language": LANGUAGE,
        "output_format": "wav",
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "audio/wav",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.time()
        try:
            r = requests.post(URL, headers=headers, json=payload, timeout=(10, 120))
            latency = time.time() - t0
            if r.status_code != 200:
                print(f"FAILED {voice_id}: {r.status_code} {r.reason} {error_detail(r)}")
                if r.status_code < 500 and r.status_code != 429:
                    return None, latency
            else:
                with open(out_file, "wb") as f:
                    f.write(r.content)
                return len(text), latency
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            latency = time.time() - t0
            print(f"RETRY {attempt}/{MAX_RETRIES} {voice_id}: {type(e).__name__}: {e}")
            if attempt == MAX_RETRIES:
                print(f"FAILED {voice_id}: giving up after {MAX_RETRIES} attempts")
                return None, latency
        time.sleep(RETRY_BACKOFF * attempt)

    return None, 0.0


def main():
    if not API_KEY:
        raise SystemExit("API key missing. Check your .env file.")

    validate_voices(VOICE_MAP)

    with open("results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["call_id", "turn", "speaker", "voice", "chars", "latency_s", "file"])

        for call in DIALOGUES:
            for i, turn in enumerate(call["turns"], start=1):
                speaker = turn["speaker"]
                voice = VOICE_MAP[speaker]
                out = os.path.join(OUTPUT_DIR, f"{call['id']}_{i:02d}_{speaker}.wav")

                chars, latency = tts(turn["text"], voice, SAMPLE_RATE, out)
                if chars:
                    writer.writerow([call["id"], i, speaker, voice, chars, f"{latency:.2f}", out])
                    print(f"OK  {out}  ({latency:.2f}s)")


if __name__ == "__main__":
    main()
