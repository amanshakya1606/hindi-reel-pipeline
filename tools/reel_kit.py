"""Shared helpers for hand-built Your Brand reels (voice timing, captions, SFX, render).

A reel script defines CSS, body HTML and a GSAP timeline; this module handles the rest.
Voice files: <reel>/vo-lumi/scene-NN.wav (Google AI Studio, Lumi).
"""
import html
import json
import math
import pathlib
import random
import shutil
import sys
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reel_builder as rb  # noqa: E402

SR = 44100
_r = random.Random(5)

CAP_CSS = """
.cap{position:absolute;inset:0;z-index:40}
.cap span{position:absolute;left:50%;top:1420px;transform:translateX(-50%);white-space:nowrap;padding:14px 30px 12px;background:#17171A;color:#fff;border-radius:20px;font-weight:700;font-size:44px;box-shadow:0 8px 0 #F2B705}
"""


def tone(freqs, length, decay=6.0, attack=0.004):
    t = np.arange(int(SR * length)) / SR
    env = np.minimum(1, t / attack) * np.exp(-t * decay)
    return sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs) * env


def noise(n):
    return np.array([_r.gauss(0, 1) for _ in range(n)])


def sfx_bank():
    fx = {}
    t = np.arange(int(SR * 0.16)) / SR
    fx["pop"] = np.sin(2 * np.pi * np.cumsum(500 + 900 * t / 0.16) / SR) * np.exp(-t * 22) * 0.5
    n = int(SR * 0.4)
    fx["whoosh"] = noise(n) * np.sin(np.linspace(0, math.pi, n)) * 0.15
    fx["ding"] = tone([1318.5, 2637], 0.7, 6) * 0.5
    fx["bell"] = (tone([880, 1320, 2200], 1.4, 2.2) * 0.6)
    t = np.arange(int(SR * 0.25)) / SR
    fx["thud"] = tone([70, 110], 0.25, 12) * 0.9 + noise(len(t)) * np.exp(-t * 50) * 0.2
    fx["coin"] = np.concatenate([tone([988], 0.08, 20), tone([1319], 0.35, 8)]) * 0.45
    t = np.arange(int(SR * 0.6)) / SR
    fx["fall"] = np.sin(2 * np.pi * np.cumsum(900 - 700 * t / 0.6) / SR) * np.exp(-t * 4) * 0.3
    fx["cheer"] = sum(tone([f], 0.9, 3) for f in (523, 659, 784, 1046)) / 4 * 0.7
    fx["tick"] = tone([2000], 0.05, 80) * 0.5
    return fx


def write_wav(path, sig):
    sig = np.clip(sig, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((sig * 32767).astype("<i2").tobytes())


class Reel:
    def __init__(self, here, n_scenes, holds, lead=0.15):
        self.here = pathlib.Path(here)
        self.vid = self.here / "video"
        (self.vid / "assets").mkdir(parents=True, exist_ok=True)
        (self.here / "vo").mkdir(exist_ok=True)
        for f in ["hyperframes.json", "package.json", "meta.json"]:
            if not (self.vid / f).exists():
                shutil.copy(rb.BASE / "video" / f, self.vid / f)
        self.durs, self.segs = [], []
        for i in range(1, n_scenes + 1):
            raw, mp3 = self.here / "vo-lumi" / f"scene-{i:02d}.wav", self.here / "vo" / f"scene-{i:02d}.mp3"
            rb.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse",
                    "-ar", "44100", "-b:a", "160k", str(mp3)])
            shutil.copy(mp3, self.vid / "assets" / mp3.name)
            d = rb.dur(mp3)
            self.durs.append(d)
            self.segs.append(rb.voiced(d, rb.silences(mp3)))
        self.S, t = [], lead
        for i, d in enumerate(self.durs):
            self.S.append(round(t, 2))
            t += d + holds[i]
        self.total = round(t, 2)
        self.V = [round(s + 0.1, 2) for s in self.S]
        self.fx = sfx_bank()
        self.mix = np.zeros(int(SR * (self.total + 1)))

    def P(self, i, f):
        return round(self.V[i] + rb.pos(self.segs[i], f), 2)

    def put(self, name, at, g=1.0):
        s = self.fx[name]
        i = int(at * SR)
        if i >= len(self.mix):
            return
        self.mix[i:i + len(s)] += s[: len(self.mix) - i] * g

    def captions(self, caps):
        out = []
        for i, chunks in enumerate(caps):
            w = [len(c) for c in chunks]
            tot, acc, st = sum(w), 0, []
            for x in w:
                st.append(rb.pos(self.segs[i], acc / tot))
                acc += x
            for j, c in enumerate(chunks):
                ce = st[j + 1] if j + 1 < len(st) else self.durs[i]
                out.append(f'<div class="clip cap" data-start="{self.V[i] + st[j]:.2f}" data-duration="{max(.3, ce - st[j]):.2f}" data-track-index="9"><span>{html.escape(c)}</span></div>')
        return "\n".join(out)

    def audio_tags(self, music_vol=0.13):
        a = [f'<audio id="vo{i + 1}" class="clip" src="assets/scene-{i + 1:02d}.mp3" data-start="{self.V[i]}" data-duration="{self.durs[i]:.2f}" data-track-index="{2 + i}" data-volume="1"></audio>' for i in range(len(self.durs))]
        a.append(f'<audio id="mus" class="clip" src="assets/music.wav" data-start="0" data-duration="{self.total}" data-track-index="20" data-volume="{music_vol}"></audio>')
        a.append(f'<audio id="sfx" class="clip" src="assets/sfx.wav" data-start="0" data-duration="{self.total}" data-track-index="21" data-volume="0.9"></audio>')
        return "\n".join(a)

    def write(self, css, body, js, T):
        write_wav(self.vid / "assets" / "sfx.wav", self.mix * 0.8)
        r = rb.run([sys.executable, str(rb.BASE / "make_music.py"), str(self.total), str(self.vid / "assets" / "music.wav")])
        if r.returncode:
            print(r.stderr[-500:])
        page = f"""<!doctype html>
<html lang="hi"><head><meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<style>{css}{CAP_CSS}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{self.total}" data-width="1080" data-height="1920">
{body}
</div>
<script>const T = {json.dumps(T)};
{js}</script></body></html>"""
        (self.vid / "index.html").write_text(page, encoding="utf-8")
        print("built total", self.total, "starts", self.S)

    def render(self):
        raw = self.here / "reel-raw.mp4"
        r = rb.run(["npx", "hyperframes", "render", "--output", str(raw)], cwd=self.vid, shell=True, timeout=1500)
        if not raw.exists():
            print(r.stdout[-1500:], r.stderr[-1500:])
            raise SystemExit("render failed")
        # loudness-normalise and keep under ~8 MB for upload
        rb.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "libx264", "-crf", "23", "-preset", "slow", "-pix_fmt", "yuv420p",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(self.here / "reel.mp4")])
        raw.unlink()
        print("rendered", rb.dur(self.here / "reel.mp4"), (self.here / "reel.mp4").stat().st_size)
