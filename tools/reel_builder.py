"""Build a Your Brand animated reel (HyperFrames project) from a spec + per-scene voice files.

Folder layout for one reel (e.g. content/2026-11-19-whatsapp/):
  spec.json          scenes (see below)
  vo-lumi/scene-NN.wav   raw voice from Google AI Studio (Lumi), one per scene
Output:
  vo/scene-NN.mp3, video/ (HyperFrames project), reel.mp4 after render

Usage:
  python tools/reel_builder.py content/<reel-dir>            # build project
  python tools/reel_builder.py content/<reel-dir> --render   # build + render + loudnorm

spec.json:
{ "scenes": [ {"type":"hook","kicker":"..","title":"Text with **highlight**","sub":"..","caps":["..",".."]},
              {"type":"point","num":"01","kicker":"..","title":"..","chips":["..",".."],"caps":[..]},
              {"type":"compare","left":{"label":"..","title":"..","items":[..]},"right":{...},"caps":[..]},
              {"type":"statement","a":"..","b":"..","caps":[..]},
              {"type":"cta","title":"..","sub":"..","btn":"..","caps":[..]} ] }
"""
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "template"  # source of narrator template + project scaffold
GAP, VO_LEAD, END_HOLD = 0.3, 0.1, 1.9


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def silences(p):
    err = run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "silencedetect=noise=-38dB:d=0.22", "-f", "null", "-"]).stderr
    out, cur = [], None
    for kind, v in re.findall(r"silence_(start|end): ([0-9.]+)", err):
        if kind == "start":
            cur = float(v)
        elif cur is not None:
            out.append((cur, float(v)))
            cur = None
    return out


def voiced(d, sil):
    segs, t = [], 0.0
    for a, b in sorted(sil):
        if a > t + 0.05:
            segs.append((t, a))
        t = max(t, b)
    if d > t + 0.05:
        segs.append((t, d))
    return segs or [(0, d)]


def pos(segs, frac):
    total = sum(b - a for a, b in segs)
    want = frac * total
    for a, b in segs:
        if want <= (b - a):
            return a + want
        want -= (b - a)
    return segs[-1][1]


def hl(text):
    t = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="mk"><i class="mki"></i><b>\1</b></span>', t)


SCENE_CSS = """
    #root { position: absolute; inset: 0; }
    .chips { margin-top: 44px; display: flex; flex-direction: column; gap: 22px; }
    .chip { display: flex; align-items: center; gap: 26px; padding: 26px 34px; font-weight: 700; font-size: 54px; line-height: 1.12; background: #fff; border-radius: 32px; box-shadow: 0 14px 40px rgba(23,23,26,.08); }
    .chip span { flex: none; width: 74px; height: 74px; border-radius: 50%; background: var(--gold); display: flex; align-items: center; justify-content: center; font-size: 40px; font-weight: 800; }
    .hk-kicker { font-weight: 700; font-size: 40px; letter-spacing: .08em; text-transform: uppercase; color: var(--gold-text); }
    .hk-title { margin-top: 18px; font-weight: 800; font-size: 118px; line-height: 1.03; letter-spacing: -.03em; }
    .hk-sub { margin-top: 36px; font-weight: 600; font-size: 54px; line-height: 1.22; color: var(--muted); }
    .cmp { margin-top: 10px; display: flex; gap: 26px; }
    .cmp .c { flex: 1; padding: 34px 30px; border-radius: 34px; background: #fff; box-shadow: 0 14px 40px rgba(23,23,26,.08); }
    .cmp .c.on { background: var(--gold); }
    .cmp .lab { font-weight: 700; font-size: 34px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
    .cmp .c.on .lab { color: var(--ink); }
    .cmp .t { margin-top: 10px; font-weight: 800; font-size: 60px; line-height: 1.08; }
    .cmp ul { list-style: none; margin-top: 22px; display: flex; flex-direction: column; gap: 12px; }
    .cmp li { font-weight: 600; font-size: 40px; line-height: 1.15; }
    .st-a { margin-top: 40px; font-weight: 700; font-size: 80px; line-height: 1.12; color: var(--muted); }
    .st-b { margin-top: 40px; font-weight: 800; font-size: 120px; line-height: 1.04; letter-spacing: -.03em; }
    .cta-ic { width: 190px; height: 190px; }
    .cta-t { margin-top: 30px; font-weight: 800; font-size: 104px; line-height: 1.05; letter-spacing: -.03em; }
    .cta-s { margin-top: 24px; font-weight: 600; font-size: 56px; line-height: 1.2; color: var(--muted); }
    .cta-b { display: inline-block; margin-top: 60px; padding: 28px 44px; background: var(--gold); border-radius: 999px; font-weight: 800; font-size: 44px; }
    .cta-h { margin-top: 28px; font-weight: 700; font-size: 44px; }
"""


def scene_html(i, sc, d):
    sid = f"s{i}"
    els, tw = [], []  # markup, (selector, start, kind)
    if sc["type"] == "hook":
        els.append(f'<div class="hk-kicker" id="{sid}-k">{html.escape(sc.get("kicker", ""))}</div>')
        els.append(f'<div class="hk-title" id="{sid}-t">{hl(sc["title"])}</div>')
        if sc.get("sub"):
            els.append(f'<div class="hk-sub" id="{sid}-s">{hl(sc["sub"])}</div>')
        tw += [(f"#{sid}-k", 0.0, "up"), (f"#{sid}-t", 0.12, "pop"), (f"#{sid}-s", d * 0.3, "up")]
    elif sc["type"] == "point":
        els.append(f'<div class="num" id="{sid}-n">{html.escape(sc["num"])}</div>')
        els.append(f'<div class="kicker" id="{sid}-k">{html.escape(sc.get("kicker", ""))}</div>')
        els.append(f'<div class="h" id="{sid}-t">{hl(sc["title"])}</div>')
        chips = sc.get("chips", [])
        if chips:
            els.append('<div class="chips">' + "".join(
                f'<div class="chip" id="{sid}-c{j}"><span>✓</span>{html.escape(c)}</div>' for j, c in enumerate(chips)) + "</div>")
        tw += [(f"#{sid}-n", 0.05, "spin"), (f"#{sid}-k", 0.2, "left"), (f"#{sid}-t", 0.45, "up")]
        for j in range(len(chips)):
            tw.append((f"#{sid}-c{j}", d * (0.22 + 0.42 * j / max(1, len(chips))), "right"))
    elif sc["type"] == "compare":
        def card(side, cls):
            items = "".join(f"<li>• {html.escape(x)}</li>" for x in side.get("items", []))
            return f'<div class="c {cls}" id="{sid}-{cls or "l"}"><div class="lab">{html.escape(side["label"])}</div><div class="t">{hl(side["title"])}</div><ul>{items}</ul></div>'
        if sc.get("title"):
            els.append(f'<div class="h" id="{sid}-t" style="margin-bottom:40px">{hl(sc["title"])}</div>')
            tw.append((f"#{sid}-t", 0.05, "up"))
        els.append('<div class="cmp">' + card(sc["left"], "") + card(sc["right"], "on") + "</div>")
        tw += [(f"#{sid}-l", 0.2, "up"), (f"#{sid}-on", d * 0.5, "pop")]
    elif sc["type"] == "statement":
        els.append(f'<div class="st-a" id="{sid}-a">{hl(sc["a"])}</div>')
        els.append(f'<div class="st-b" id="{sid}-b">{hl(sc["b"])}</div>')
        tw += [(f"#{sid}-a", 0.15, "up"), (f"#{sid}-b", d * 0.5, "pop")]
    elif sc["type"] == "cta":
        els.append(f'<svg class="cta-ic" id="{sid}-i" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="#f2b705"/><path d="M24 49 L76 27 L62 76 L50 57 Z M50 57 L76 27" fill="none" stroke="#17171a" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/></svg>')
        els.append(f'<div class="cta-t" id="{sid}-t">{hl(sc["title"])}</div>')
        if sc.get("sub"):
            els.append(f'<div class="cta-s" id="{sid}-s">{hl(sc["sub"])}</div>')
        els.append(f'<div class="cta-b" id="{sid}-b">{html.escape(sc.get("btn", "Book Your Free Strategy Call"))}</div>')
        els.append(f'<div class="cta-h" id="{sid}-h">@yourbrand</div>')
        tw += [(f"#{sid}-i", 0.05, "fly"), (f"#{sid}-t", 0.3, "up"), (f"#{sid}-s", 1.2, "up"), (f"#{sid}-b", 1.6, "pop"), (f"#{sid}-h", 1.8, "up")]
    present = {re.search(r'id="([^"]+)"', e).group(1) for e in re.findall(r'id="[^"]+"', "".join(els))}
    js = [f'const tl = gsap.timeline({{ paused: true }});']
    for sel, t, kind in tw:
        if sel[1:] not in present:
            continue
        t = round(max(0.0, min(t, d - 0.6)), 2)
        fr, to = {
            "up": ("{ opacity: 0, y: 46 }", "{ opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }"),
            "left": ("{ opacity: 0, x: -40 }", "{ opacity: 1, x: 0, duration: 0.3 }"),
            "right": ("{ opacity: 0, x: 120 }", "{ opacity: 1, x: 0, duration: 0.32, ease: 'power3.out' }"),
            "pop": ("{ opacity: 0, scale: 0.86, transformOrigin: '0% 50%' }", "{ opacity: 1, scale: 1, duration: 0.42, ease: 'back.out(1.8)' }"),
            "spin": ("{ scale: 0, rotation: -20 }", "{ scale: 1, rotation: 0, duration: 0.4, ease: 'back.out(2)' }"),
            "fly": ("{ x: -260, y: 120, opacity: 0, rotation: -25 }", "{ x: 0, y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: 'power3.out' }"),
        }[kind]
        js.append(f'tl.fromTo("{sel}", {fr}, {to}, {t});')
    js.append(f'tl.fromTo("#{sid} .mki", {{ scaleX: 0, transformOrigin: "0% 50%" }}, {{ scaleX: 1, duration: 0.4, ease: "power2.out", stagger: 0.25 }}, {round(min(d * 0.35, d - 0.8), 2)});')
    if sc["type"] != "cta":
        js.append(f'tl.fromTo("#{sid}-wrap", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.2 }}, {round(d - 0.25, 2)});')
    js.append(f'window.__timelines["{sid}"] = tl;')
    return f"""<template>
  <style>{SCENE_CSS}</style>
  <div id="root" data-composition-id="{sid}" data-width="1080" data-height="1920">
    <div class="wrap" id="{sid}-wrap">
      {chr(10).join('      ' + e for e in els).strip()}
    </div>
  </div>
  <script>
    {chr(10).join('    ' + l for l in js).strip()}
  </script>
</template>
"""


def main():
    rd = (ROOT / sys.argv[1]).resolve() if not pathlib.Path(sys.argv[1]).is_absolute() else pathlib.Path(sys.argv[1])
    spec = json.loads((rd / "spec.json").read_text(encoding="utf-8"))
    scenes = spec["scenes"]
    n = len(scenes)
    (rd / "vo").mkdir(exist_ok=True)
    vid = rd / "video"
    (vid / "compositions").mkdir(parents=True, exist_ok=True)
    (vid / "assets").mkdir(exist_ok=True)
    for f in ["hyperframes.json", "package.json", "meta.json"]:
        if (BASE / "video" / f).exists() and not (vid / f).exists():
            shutil.copy(BASE / "video" / f, vid / f)

    durs, segs = [], []
    for i in range(1, n + 1):
        raw = rd / "vo-lumi" / f"scene-{i:02d}.wav"
        mp3 = rd / "vo" / f"scene-{i:02d}.mp3"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
             "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse",
             "-ar", "44100", "-b:a", "160k", str(mp3)])
        shutil.copy(mp3, vid / "assets" / mp3.name)
        d = dur(mp3)
        durs.append(d)
        segs.append(voiced(d, silences(mp3)))

    starts, slots, t = [], [], 0.0
    for i, d in enumerate(durs):
        slot = round(d + GAP + (END_HOLD if i == n - 1 else 0), 2)
        starts.append(round(t, 2))
        slots.append(slot)
        t += slot
    total = round(t, 2)

    hosts, audios, caps, mouth = [], [], [], []
    for i, sc in enumerate(scenes):
        k = i + 1
        (vid / "compositions" / f"s{k}.html").write_text(scene_html(k, sc, slots[i]), encoding="utf-8")
        hosts.append(f'      <div id="s{k}" data-composition-id="s{k}" data-composition-src="compositions/s{k}.html" data-start="{starts[i]}" data-duration="{slots[i]}" data-track-index="1" data-track-kind="graphics" data-width="1080" data-height="1920"></div>')
        vo0 = round(starts[i] + VO_LEAD, 2)
        audios.append(f'      <audio id="vo{k}" class="clip" src="assets/scene-{k:02d}.mp3" data-start="{vo0}" data-duration="{durs[i]:.2f}" data-track-index="{1 + k}" data-volume="1"></audio>')
        chunks = sc.get("caps", [])
        weights = [max(1, len(c)) for c in chunks]
        tot = sum(weights)
        acc = 0
        cstarts = []
        for w in weights:
            cstarts.append(round(pos(segs[i], acc / tot), 2) if tot else 0)
            acc += w
        for j, c in enumerate(chunks):
            ce = cstarts[j + 1] if j + 1 < len(cstarts) else durs[i]
            caps.append(f'        <div id="cap{k}-{j}" class="clip cap" data-start="{vo0 + cstarts[j]:.2f}" data-duration="{max(0.25, ce - cstarts[j]):.2f}" data-track-index="9"><span>{html.escape(c)}</span></div>')
        x = 0.0
        while x < durs[i] - 0.1:
            if any(a <= x < b for a, b in segs[i]):
                mouth.append(round(vo0 + x, 2))
            x += 0.19

    tpl = (BASE / "index.template.html").read_text(encoding="utf-8")
    page = (tpl.replace("{{TOTAL}}", str(total)).replace("<!--HOSTS-->", "\n".join(hosts))
            .replace("<!--AUDIO-->", "\n".join(audios)).replace("<!--CAPS-->", "\n".join(caps))
            .replace("/*MOUTH*/", json.dumps(mouth)).replace("/*SCENES*/", json.dumps(starts)))
    (vid / "index.html").write_text(page, encoding="utf-8")
    r = run([sys.executable, str(BASE / "make_music.py"), str(total), str(vid / "assets" / "music.wav")])
    if r.returncode:
        print(r.stderr[-800:])
    print("built", rd.name, "total", total, "scenes", slots)

    if "--render" in sys.argv:
        raw = rd / "reel-raw.mp4"
        r = run(["npx", "hyperframes", "render", "--output", str(raw)], cwd=vid, shell=True, timeout=1200)
        if not raw.exists():
            print(r.stdout[-1500:], r.stderr[-1500:])
            raise SystemExit("render failed")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", str(rd / "reel.mp4")])
        raw.unlink()
        print("rendered", rd / "reel.mp4", dur(rd / "reel.mp4"))


if __name__ == "__main__":
    main()
