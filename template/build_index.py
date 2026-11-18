"""Build video/index.html: scene hosts, voiceover, music, narrator character and synced captions.

Reads vo/timings.json (word timings from make_vo.py) and the mp3 durations.
"""
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
VID = HERE / "video"
GAP = 0.3
VO_LEAD = 0.1

# caption chunks per scene: (start second inside the voiceover clip, text, optional highlighted word)
CAPS = [
    [(0.0, "Ads pe paisa"), (0.75, "ja raha hai"), (1.5, "aur leads?"), (2.59, "ZERO!"), (3.8, "Yaar,"), (4.2, "galti ads ki"), (5.0, "hai hi nahi")],
    [(0.0, "Pehli wajah"), (1.27, "Customer ne ad pe"), (2.2, "click kiya"), (3.34, "aur pahunch gaya"), (3.95, "homepage pe"), (5.03, "Offer wala page"), (5.8, "kahan hai bhai?")],
    [(0.0, "Doosri wajah"), (1.45, "Offer hi"), (1.95, "saaf nahi hai"), (3.24, "Kya milega?"), (4.53, "Kitne me?"), (5.82, "Kab tak?")],
    [(0.0, "Teesri wajah"), (1.21, "Lead aayi"), (2.0, "aur reply gaya"), (3.2, "do ghante baad"), (4.66, "Paanch minute me"), (5.6, "jawab nahi"), (6.61, "to lead"), (7.54, "thandi")],
    [(0.0, "Dekho,"), (0.45, "ads sirf traffic"), (1.5, "laate hain"), (2.58, "Bechta hai"), (3.15, "SYSTEM")],
    [(0.3, "Ye reel"), (0.75, "us dost ko bhejo"), (1.8, "jo ads chala"), (2.5, "raha hai")],
]
EXTRA_END = [0, 0, 0, 0, 0, 1.9]  # hold on the last scene for the CTA


def dur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip())


timings = json.loads((HERE / "vo" / "timings.json").read_text(encoding="utf-8"))
durs = [dur(HERE / "vo" / f"scene-{i:02d}.mp3") for i in range(1, 7)]
starts, slots, t = [], [], 0.0
for i, d in enumerate(durs):
    slot = round(d + GAP + EXTRA_END[i], 2)
    starts.append(round(t, 2))
    slots.append(slot)
    t += slot
TOTAL = round(t, 2)

hosts, audios, caps, mouth = [], [], [], []
for i in range(6):
    n = i + 1
    hosts.append(
        f'      <div id="s{n}" data-composition-id="s{n}" data-composition-src="compositions/s{n}.html" data-start="{starts[i]}" data-duration="{slots[i]}" data-track-index="1" data-track-kind="graphics" data-width="1080" data-height="1920"></div>'
    )
    vo0 = round(starts[i] + VO_LEAD, 2)
    audios.append(f'      <audio id="vo{n}" class="clip" src="assets/scene-{n:02d}.mp3" data-start="{vo0}" data-duration="{durs[i]:.2f}" data-track-index="{2 + i}" data-volume="1"></audio>')
    chunks = CAPS[i]
    for k, (cs, text) in enumerate(chunks):
        ce = chunks[k + 1][0] if k + 1 < len(chunks) else durs[i]
        caps.append(f'        <div id="cap{n}-{k}" class="clip cap" data-start="{vo0 + cs:.2f}" data-duration="{max(0.2, ce - cs):.2f}" data-track-index="9"><span>{text}</span></div>')
    for off, _w in timings[i]:
        mouth.append(round(vo0 + off, 2))

html = (HERE / "index.template.html").read_text(encoding="utf-8")
html = (
    html.replace("{{TOTAL}}", str(TOTAL))
    .replace("<!--HOSTS-->", "\n".join(hosts))
    .replace("<!--AUDIO-->", "\n".join(audios))
    .replace("<!--CAPS-->", "\n".join(caps))
    .replace("/*MOUTH*/", json.dumps(mouth))
    .replace("/*SCENES*/", json.dumps(starts))
)
(VID / "index.html").write_text(html, encoding="utf-8")
print("total", TOTAL, "starts", starts, "slots", slots)
