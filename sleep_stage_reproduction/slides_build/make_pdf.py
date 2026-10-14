from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


BUILD = Path(r"C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction\slides_build")
PNG_DIR = BUILD / "output"
PDF_PATH = PNG_DIR / "pdf" / "sleep_stage_classification_3slides.pdf"
PAGE_W, PAGE_H = 960, 540


def main() -> None:
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    pdf.setTitle("Sleep Stage Classification - 3-slide research proposal")
    pdf.setAuthor("Codex")
    for index in range(1, 4):
        image_path = PNG_DIR / f"slide-{index:02d}.png"
        pdf.drawImage(ImageReader(str(image_path)), 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")
        pdf.showPage()
    pdf.save()
    print(PDF_PATH)


if __name__ == "__main__":
    main()
