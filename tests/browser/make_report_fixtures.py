"""Public synthetic documents for the renderer gate, never patient records."""
import argparse
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def main(folder):
    folder.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    pdfmetrics.registerFont(TTFont('ReviewFont', str(root / 'src/sehatraasta/web/static/fonts/PublicSans.ttf')))
    for name, count, font in [('three-pages.pdf', 3, 'Courier'), ('embedded-font.pdf', 2, 'ReviewFont'), ('too-many.pdf', 61, 'Courier')]:
        document = canvas.Canvas(str(folder / name), pagesize=(400, 500), invariant=1)
        for number in range(1, count + 1):
            document.setFont(font, 20)
            document.drawString(30, 450, 'Fictional document page ' + str(number))
            document.setFont(font, 12)
            document.drawString(30, 420, 'Renderer test only. No patient data.')
            document.showPage()
        document.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    main(parser.parse_args().folder)
