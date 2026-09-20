"""把财报 PDF 转成带页码标记的纯文本，供下游检索与页码级溯源。

用法:
    python pdf_to_text.py -o <输出目录> <pdf> [<pdf> ...]

输出 <输出目录>/<pdf 主名>.txt，每页开头一行 `[[page N]]`。
页码是该 PDF 的物理页序号，与 PDF 阅读器显示的页码一致。
"""

import sys
from pathlib import Path

import pdfplumber


def convert(pdf_path, out_dir):
    src = Path(pdf_path)
    out = Path(out_dir) / (src.stem + ".txt")
    parts = []
    with pdfplumber.open(src) as pdf:
        n = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(f"\n[[page {page.page_number}]]\n{text}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    size = out.stat().st_size
    print(f"{src.name}  {n} 页 -> {out}  ({size / 1024:.0f} KB)")
    return out


if __name__ == "__main__":
    if "-o" not in sys.argv or len(sys.argv) < 4:
        sys.exit(__doc__)
    i = sys.argv.index("-o")
    out_dir = sys.argv[i + 1]
    pdfs = [a for j, a in enumerate(sys.argv[1:], start=1)
            if a != "-o" and j != i + 1]
    for p in pdfs:
        try:
            convert(p, out_dir)
        except Exception as e:
            print(f"!! {p} 失败: {type(e).__name__}: {e}")
