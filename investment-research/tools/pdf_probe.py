"""探测财报 PDF：页数、文本层是否可读、关键词落在哪几页。

用法:
    python pdf_probe.py <pdf> [<pdf> ...]
"""

import re
import sys
from pathlib import Path

import pdfplumber

KEYWORDS = [
    "主要会计数据", "合并资产负债表", "合并利润表", "合并现金流量表",
    "分行业", "分部", "前五名客户", "前五名供应商",
    "折旧", "摊销", "有息负债", "短期借款", "长期借款",
    "股本变动", "股份变动", "研发投入", "商誉",
]


def probe(path):
    p = Path(path)
    print("=" * 70)
    print(f"{p.name}   ({p.stat().st_size / 1024 / 1024:.1f} MB)")
    with pdfplumber.open(p) as pdf:
        n = len(pdf.pages)
        print(f"页数: {n}")

        # 抽前三页看有没有文本层
        sample = ""
        for i in range(min(3, n)):
            sample += (pdf.pages[i].extract_text() or "")
        cn = len(re.findall(r"[一-鿿]", sample))
        repl = sample.count("�")
        total = len(sample)
        print(f"前 3 页抽到 {total} 字符，其中汉字 {cn}，替换符 {repl}")
        if total < 50:
            print(">>> 警告: 几乎抽不到文字，可能是扫描件，需要 OCR")
        elif cn < total * 0.1:
            print(">>> 警告: 汉字占比过低，可能乱码或需 OCR")
        else:
            head = re.sub(r"\s+", " ", sample)[:100]
            print(f"样本文本: {head}")

        # 关键词定位
        if total >= 50:
            hits = {}
            for page in pdf.pages:
                # 只对前 260 页扫描，年报正文一般在此范围内
                if page.page_number > 260:
                    break
                t = page.extract_text() or ""
                for kw in KEYWORDS:
                    if kw in t:
                        hits.setdefault(kw, []).append(page.page_number)
            print("关键词落点:")
            for kw in KEYWORDS:
                pages = hits.get(kw, [])
                if pages:
                    shown = pages[:8]
                    more = f" ...(共{len(pages)}页)" if len(pages) > 8 else ""
                    print(f"  {kw:12s} -> {shown}{more}")
                else:
                    print(f"  {kw:12s} -> 未命中")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for arg in sys.argv[1:]:
        try:
            probe(arg)
        except Exception as e:
            print(f"!! {arg} 处理失败: {type(e).__name__}: {e}")
