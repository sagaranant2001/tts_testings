# Transcript to Call Audio (TTS Test)

Converts call-center style dialogues (agent and customer) into synthetic speech
using the [Smallest AI Waves TTS API](https://smallest.ai). Each turn of a
conversation is rendered as its own WAV file with a different voice per speaker,
and every request is logged to a CSV for latency and character-usage tracking.

## Features

- Reads dialogues from a simple `dialogues.json` file
- One voice per speaker (agent and customer)
- Saves each turn as a separate WAV: `output/<call_id>_<turn>_<speaker>.wav`
- Retries on network errors (timeouts, dropped connections) with backoff
- Warns when a turn exceeds the recommended ~250 characters
- Writes `results.csv` with call ID, turn, speaker, voice, model, characters, latency and file path
- Prints total characters sent (useful for tracking API credit usage)

## Project Structure

```
tts-test/
├── tts_test.py        # main script
├── dialogues.json     # input dialogues
├── .env               # API key (not committed)
├── requirements.txt
├── output/            # generated WAV files
└── results.csv        # per-turn log
```

## Requirements

- Python 3.9+
- A Smallest AI API key

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

`requirements.txt`:

```
requests
python-dotenv
```

Create a `.env` file in the project root:

```
SMALLEST_API_KEY=your_api_key_here
```

## Input Format

`dialogues.json` is a list of calls. Each call has an `id` and an ordered list of `turns`:

```json
[
  {
    "id": "call01",
    "turns": [
      { "speaker": "agent",    "text": "Hello, thank you for calling. How can I help you today?" },
      { "speaker": "customer", "text": "Hi, I bought your eye drops and they sting when I use them." }
    ]
  }
]
```

Speaker labels must match the keys in `VOICE_MAP`.

## Configuration

Edit these values at the top of the script:

| Setting | Description | Default |
|---------|-------------|---------|
| `MODEL` | `lightning_v3.1_pro` (premium voices) or `lightning_v3.1` (standard voices) | `lightning_v3.1_pro` |
| `VOICE_MAP` | Speaker to voice ID mapping | `agent: kaitlyn`, `customer: zoe` |
| `SAMPLE_RATE` | 8000, 16000, 24000 or 44100 Hz | `24000` |
| `OUTPUT_DIR` | Folder for generated audio | `output` |

> Pro models must be used with Pro voices, and standard models with standard voices.

## Usage

```bash
python tts_test.py
```

Sample output:

```
OK  output/call01_01_agent.wav  (1.42s)
OK  output/call01_02_customer.wav  (1.18s)

Done. Total characters sent: 312
```

## Output

- `output/` contains one WAV file per turn, named `<call_id>_<turn>_<speaker>.wav`
- `results.csv` columns: `call_id, turn, speaker, voice, model, chars, latency_s, file`

## Known Limitations

- Turns are generated as separate files and are not yet merged into a single call recording
- Only network errors are retried, not HTTP errors such as 429 or 503
- Turns longer than ~250 characters are warned about but not split

## Roadmap

- [ ] Stitch turns into one WAV per call with short silences between speakers
- [ ] Retry on rate-limit and server errors (429, 500, 502, 503)
- [ ] Split long turns at sentence boundaries
- [ ] Optional stereo output (agent on the left channel, customer on the right)

## Security

Never commit your `.env` file. Add this to `.gitignore`:

```
.env
venv/
output/
results.csv
__pycache__/
```

## License

MIT (or your preferred license)
