"""Export each slide of a slides.html (slide chosen by URL hash #1..#N) to PNG with headless Chrome.

Usage: python export_slides.py <slides.html> <count> [width] [height]
"""
import pathlib
import subprocess
import sys

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
src = pathlib.Path(sys.argv[1]).resolve()
count = int(sys.argv[2])
w = sys.argv[3] if len(sys.argv) > 3 else "1080"
h = sys.argv[4] if len(sys.argv) > 4 else "1350"
for i in range(1, count + 1):
    out = src.parent / f"slide-{i:02d}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
         "--virtual-time-budget=5000", f"--screenshot={out}", src.as_uri() + f"#{i}"],
        capture_output=True, timeout=120,
    )
    print(out.name, out.exists() and out.stat().st_size)
