"""Synthesise an original, royalty-free background bed (light upbeat pluck loop) as a WAV.

Usage: python make_music.py <seconds> <out.wav>
"""
import random
import sys
import wave

import numpy as np

SR = 44100
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
OUT = sys.argv[2] if len(sys.argv) > 2 else "music.wav"
BPM = 104
BEAT = 60 / BPM
_r = random.Random(7)


def noise(k):
    return np.array([_r.gauss(0, 1) for _ in range(k)])

n = int(SR * DUR)
mix = np.zeros(n)


def add(sig, t0, gain=1.0):
    i = int(t0 * SR)
    if i >= n:
        return
    j = min(n, i + len(sig))
    mix[i:j] += sig[: j - i] * gain


def pluck(freq, length=0.5):
    t = np.arange(int(SR * length)) / SR
    env = np.exp(-t * 9)
    return (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.12 * np.sin(6 * np.pi * freq * t)) * env


def bass(freq, length):
    t = np.arange(int(SR * length)) / SR
    env = np.minimum(1, t * 60) * np.exp(-t * 2.2)
    return np.sin(2 * np.pi * freq * t) * env


def kick():
    t = np.arange(int(SR * 0.22)) / SR
    f = 110 * np.exp(-t * 28) + 46
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)


def hat():
    t = np.arange(int(SR * 0.05)) / SR
    nz = np.diff(noise(len(t)), prepend=0)  # crude high-pass
    return nz * np.exp(-t * 90)


def clap():
    t = np.arange(int(SR * 0.12)) / SR
    return noise(len(t)) * np.exp(-t * 38)


def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


# C  Am  F  G  (one bar each), arpeggio pattern in eighth notes
CHORDS = [(48, [60, 64, 67, 72]), (45, [57, 60, 64, 69]), (41, [53, 57, 60, 65]), (43, [55, 59, 62, 67])]
PATTERN = [0, 2, 1, 3, 2, 1, 3, 2]
bars = int(DUR / (4 * BEAT)) + 1
for b in range(bars):
    root, notes = CHORDS[b % 4]
    t_bar = b * 4 * BEAT
    add(bass(hz(root - 12), 4 * BEAT * 0.95), t_bar, 0.5)
    add(bass(hz(root - 12), BEAT), t_bar + 2.5 * BEAT, 0.3)
    for k, idx in enumerate(PATTERN):
        add(pluck(hz(notes[idx]), 0.45), t_bar + k * BEAT / 2, 0.22 if k % 2 == 0 else 0.15)
    for beat in range(4):
        add(kick(), t_bar + beat * BEAT, 0.55)
        add(hat(), t_bar + beat * BEAT + BEAT / 2, 0.10)
        if beat in (1, 3):
            add(clap(), t_bar + beat * BEAT, 0.10)

fade = int(SR * 0.6)
mix[:fade] *= np.linspace(0, 1, fade)
mix[-int(SR * 1.5):] *= np.linspace(1, 0, int(SR * 1.5))
mix = mix / np.max(np.abs(mix)) * 0.8
with wave.open(OUT, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
