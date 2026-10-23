"""仅在解析镜像中生成无业务数据的 RAG 导入验收样本。"""

import argparse
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    clean_pdf = canvas.Canvas(str(root / "native-policy.pdf"), pagesize=A4, invariant=1)
    clean_pdf.drawString(72, 760, "Return policy: SKU-AX1 may be returned within 30 days.")
    clean_pdf.drawString(72, 740, "Do not promise a refund before the order is verified.")
    clean_pdf.save()

    office = Document()
    office.add_heading("Warehouse handling policy", level=1)
    office.add_paragraph("SKU-AX1 ships only after payment confirmation.")
    office.save(root / "warehouse-policy.docx")

    image = Image.new("RGB", (1300, 260), "white")
    drawing = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    drawing.text((30, 75), "SKU-AX1 NO REFUND BEFORE REVIEW", fill="black", font=font)
    image.save(root / "scanned-policy.png")

    mixed_pdf = canvas.Canvas(str(root / "mixed-native-scan.pdf"), pagesize=A4, invariant=1)
    mixed_pdf.drawString(72, 760, "Order policy: verify the order before refund.")
    mixed_pdf.showPage()
    mixed_pdf.drawImage(str(root / "scanned-policy.png"), 72, 590, width=450, height=90)
    mixed_pdf.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    generate(parser.parse_args().output)
