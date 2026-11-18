"""Free Hindi voiceover through AI4Bharat's public Indic Parler-TTS demo (Hugging Face Space).

No account or API key. Uses only the Python standard library.

Usage: python tts_indic.py <text-file> <out.wav> ["voice description"]
"""
import json
import pathlib
import sys
import time
import urllib.request

BASE = "https://ai4bharat-indic-parler-tts.hf.space"
DEFAULT_DESC = (
    "Rohit speaks at a fast pace in an energetic, expressive and friendly conversational tone, "
    "like an enthusiastic Indian content creator explaining something to a friend. "
    "The recording is very high quality, with the voice very close up and no background noise."
)


def call(text, desc, tries=4):
    body = json.dumps({"data": [text, desc]}).encode("utf-8")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(BASE + "/gradio_api/call/generate_finetuned", data=body, headers={"Content-Type": "application/json"})
            event_id = json.loads(urllib.request.urlopen(req, timeout=60).read())["event_id"]
            with urllib.request.urlopen(BASE + "/gradio_api/call/generate_finetuned/" + event_id, timeout=600) as stream:
                event = None
                for raw in stream:
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                        if event == "complete":
                            return json.loads(data)[0]
                        if event == "error":
                            raise RuntimeError("space error: " + data[:300])
        except Exception as e:  # queue full, GPU quota, cold start
            print("retry", attempt, type(e).__name__, str(e)[:200])
            time.sleep(15)
    raise SystemExit("generation failed")


def main():
    text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    out = pathlib.Path(sys.argv[2])
    desc = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_DESC
    result = call(text, desc)
    url = BASE + "/gradio_api/file=" + result["path"]  # the "url" field the Space returns is malformed
    out.write_bytes(urllib.request.urlopen(url, timeout=120).read())
    print("saved", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
