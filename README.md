# Hindi Reel Pipeline

Turn a Hinglish script + voice lines into a finished 1080×1920 Instagram reel: animated scenes, word captions, SFX, an original synthesised music bed, loudness at −14 LUFS, and a file under 10 MB. Free and local.

Built by **Aman Shakya** (Scalvya Digital) on top of [HyperFrames](https://www.npmjs.com/package/hyperframes) (HTML → video).

## Pipeline
1. **Script**: 5–7 scenes (hook, beats, payoff, CTA keyword) → `script.md`.
2. **Voice**: one file per line (any TTS, or `tools/tts_indic.py` for free Indic TTS). `tools/collect_voice.ps1 <reel-dir>` moves downloads into `vo-lumi/scene-NN.wav`.
3. **Build**:
   - Narrator format: write `spec.json`, then `python -X utf8 tools/reel_builder.py <reel-dir> --render`.
   - Custom formats: a `build.py` using `tools/reel_kit.py` (`Reel(...)` trims voice, times scenes, captions, SFX, music, render).
4. **Check**: `npx hyperframes check` and `npx hyperframes snapshot`, fix overlaps before rendering.
5. **Render**: output `reel.mp4`, loudnorm −14 LUFS, re-encoded under 10 MB.

`template/make_music.py` makes a royalty-free background loop with numpy, so there are no music copyright problems.
`tools/export_slides.py` exports carousel HTML slides to PNG with headless Chrome.

## Rules that save time
- GSAP timelines must be deterministic (no `Math.random`). Register as `window.__timelines["main"]`.
- Keep all text inside the centre 3:4 band so the grid crop never cuts it.
- Don't name a JS variable `top` in slide HTML.

## Requirements
Python 3 + numpy, Node.js (for `npx hyperframes`), ffmpeg, Google Chrome.

## License
MIT (this repo's code). HyperFrames has its own license.
