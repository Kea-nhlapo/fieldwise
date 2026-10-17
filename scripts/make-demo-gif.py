"""Build docs/media/demo.gif and README stills from the screenshots record-demo.cjs saves.

    node scripts/record-demo.cjs http://127.0.0.1:8767     # writes artifacts/demo-backup/*.png
    .venv/Scripts/python.exe scripts/make-demo-gif.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'artifacts' / 'demo-backup'
OUT = ROOT / 'docs' / 'media'

FRAMES = [
    ('01-start-next-visit.png', '1  Fieldwise ranks eight farms from live weather, soil and map data'),
    ('03-who-to-ask.png', '2  It picks the farmers whose answer would change today’s visits'),
    ('05-ussd-screen.png', '3  The farmer answers on a basic phone over USSD, after giving consent'),
    ('07-ussd-screen.png', '3  The farmer answers on a basic phone over USSD, after giving consent'),
    ('09-answer-changed-score.png', '4  One answer moves the farm from rank 4 to rank 1 (+55 points)'),
    ('10-model-learned.png', '5  Felix taps what he found; the model learns from each visit'),
    ('13-impact.png', '6  Every impact number comes from a logged, de-identified event'),
    ('16-simulation-chart.png', '7  200 simulated seasons, with an experienced-officer baseline and no-signal controls'),
]
WIDTH, BAR = 1000, 54
FOREST, LIME, WHITE = (18, 51, 41), (212, 240, 122), (243, 247, 234)


def font(size, bold=False):
    for name in (('seguisb.ttf', 'segoeuib.ttf') if bold else ('segoeui.ttf',)) + ('arial.ttf',):
        try:
            return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(name, caption):
    shot = Image.open(SRC / name).convert('RGB')
    shot = shot.resize((WIDTH, round(shot.height * WIDTH / shot.width)), Image.LANCZOS)
    canvas = Image.new('RGB', (WIDTH, shot.height + BAR), FOREST)
    canvas.paste(shot, (0, 0))
    draw = ImageDraw.Draw(canvas)
    number, text = caption.split('  ', 1)
    draw.ellipse((18, shot.height + 13, 46, shot.height + 41), fill=LIME)
    draw.text((32, shot.height + 27), number, fill=FOREST, font=font(17, bold=True), anchor='mm')
    draw.text((60, shot.height + 27), text, fill=WHITE, font=font(19), anchor='lm')
    return canvas


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [frame(n, c).quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for n, c in FRAMES]
    durations = [2600, 2600, 1300, 1300, 3200, 2600, 2600, 3400]
    frames[0].save(OUT / 'demo.gif', save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    for name, still in (('17-map.png', 'farm-map.jpg'), ('15-simulation.png', 'simulation.jpg'), ('01-start-next-visit.png', 'workspace.jpg')):
        img = Image.open(SRC / name).convert('RGB')
        img.resize((1200, round(img.height * 1200 / img.width)), Image.LANCZOS).save(OUT / still, quality=84, optimize=True, progressive=True)
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
