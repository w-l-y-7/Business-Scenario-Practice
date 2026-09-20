"""试排检查：导出的 PDF 有没有排版事故。

查五件事（前四项对应 output-format.md §1.3）：

    1. 页数 —— 正文 ≤ 10 页、附录 ≤ 10 页
    2. 溢出 —— 最宽的那张表、最大的那张图有没有冲出页边距
    3. 页码 —— 正文每一页有没有页码（封面封底不计页码，跳过）
    4. 内容 —— 附录表头、来源标注、占位标记在不在
    5. 图片 —— 有没有图被排到版心外

用法：

    python tools/pdf/check_layout.py path/to/试排.pdf --margin 17 --body-pages 3

封面封底默认各占 1 页（首尾），可用 --cover-pages / --back-cover-pages 调整。
"""

from __future__ import annotations

import argparse

import pdfplumber

MM_TO_PT = 72.0 / 25.4
TOLERANCE_PT = 2.0  # 抗锯齿与字距引起的轻微越界不算问题


def analyse(path, margin_mm, body_pages, cover_pages, back_cover_pages):
    margin_pt = margin_mm * MM_TO_PT
    problems = []
    notes = []

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        notes.append(f"总页数：{page_count}")

        # 封面封底豁免页码检查。页数太少时不豁免，免得整份文档一页都不用查。
        exempt = set()
        if page_count >= 3:
            exempt |= set(range(1, cover_pages + 1))
            if back_cover_pages:
                exempt |= set(range(page_count - back_cover_pages + 1, page_count + 1))
        if exempt:
            notes.append(f"封面封底（不计页码）：{sorted(exempt)}")

        body_count = page_count - len(exempt)
        if body_pages:
            body_count = body_pages
        if body_count > 10:
            problems.append(f"页数：正文连同附录 {body_count} 页，超过 10 页上限")
        if page_count > 22:
            problems.append(f"页数：共 {page_count} 页，正文加附录不得超过 20 页")

        for index, page in enumerate(pdf.pages, start=1):
            left = margin_pt
            right = page.width - margin_pt
            top = margin_pt

            words = page.extract_words()
            images = page.images

            if not words and not images:
                problems.append(f"第 {index} 页：一个字都没提取到 —— 可能是空白页或字体没嵌进去")
                continue

            over_right = [w for w in words if w["x1"] > right + TOLERANCE_PT]
            over_left = [w for w in words if w["x0"] < left - TOLERANCE_PT]

            if over_right:
                sample = over_right[0]["text"][:20]
                problems.append(
                    f"第 {index} 页：{len(over_right)} 处文字越过右边距（最远 "
                    f"{max(w['x1'] for w in over_right) - right:.1f} pt），如「{sample}」"
                    " —— 多半是表格太宽或长来源没断行"
                )
            if over_left:
                sample = over_left[0]["text"][:20]
                problems.append(
                    f"第 {index} 页：{len(over_left)} 处文字越过左边距，如「{sample}」"
                )

            # 图片：横竖都不能出界。图片没被 \setkeys{Gin} 约束住时会在这里露出来。
            for img in images:
                if img["x1"] > right + TOLERANCE_PT:
                    problems.append(
                        f"第 {index} 页：有图越过右边距 "
                        f"{img['x1'] - right:.1f} pt —— 检查图是不是没被限宽"
                    )
                elif img["x0"] < left - TOLERANCE_PT:
                    problems.append(
                        f"第 {index} 页：有图越过左边距 {left - img['x0']:.1f} pt"
                    )
                if img["top"] < top - TOLERANCE_PT:
                    problems.append(
                        f"第 {index} 页：有图越过上边距 {top - img['top']:.1f} pt"
                    )

            # 页码：页脚区域（下边距以内）应当有内容
            if index not in exempt:
                footer = [w for w in words if w["top"] > page.height - margin_pt]
                if not any(w["text"].strip().isdigit() for w in footer):
                    problems.append(f"第 {index} 页：页脚没找到页码")

            if page.width > page.height:
                problems.append(f"第 {index} 页：页面是横向的，应为 A4 纵向")

    return page_count, problems, notes


def check_keywords(path, keywords):
    """检查关键内容在不在（附录表头、来源标注、占位标记）。"""
    problems = []
    with pdfplumber.open(path) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    for label, keyword in keywords:
        if keyword not in text:
            problems.append(f"内容：没找到{label}「{keyword}」")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="试排检查")
    parser.add_argument("pdf")
    parser.add_argument("--margin", type=float, default=17.0, help="页边距（mm）")
    parser.add_argument("--body-pages", type=int, default=0, help="正文页数（用于页数上限判断）")
    parser.add_argument("--cover-pages", type=int, default=1, help="开头不计页码的页数（封面）")
    parser.add_argument("--back-cover-pages", type=int, default=1, help="末尾不计页码的页数（封底）")
    args = parser.parse_args(argv)

    page_count, problems, notes = analyse(
        args.pdf, args.margin, args.body_pages, args.cover_pages, args.back_cover_pages
    )
    problems += check_keywords(args.pdf, [
        ("附录表头", "Appendix"),
        ("来源标注", "Source"),
        ("占位标记", "待填"),
    ])

    for note in notes:
        print(f"  {note}")
    if problems:
        print("试排检查未通过：")
        for item in problems:
            print(f"  - {item}")
        return 1

    print("试排检查五项全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
