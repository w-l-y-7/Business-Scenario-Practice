"""从带页码标记的财报文本里摘出关键章节，生成紧凑的「财务摘录」。

用法:
    python extract_key_sections.py <文本目录> <输出目录> [--index]

每份财报只有几十页与本次分析相关，全量读会淹掉重点。本脚本按关键词
定位页码，把命中页及其后若干页摘出来，保留 [[page N]] 标记以便溯源。

--index 只输出关键词→页码的索引，不落摘录。
"""

import re
import sys
from pathlib import Path

# 每个主题: (关键词列表, 关键词命中后额外多摘几页)
TOPICS = {
    "01-主要会计数据": (["主要会计数据和财务指标", "主要会计数据"], 2),
    "02-合并资产负债表": (["合并资产负债表"], 2),
    "03-合并利润表": (["合并利润表"], 2),
    "04-合并现金流量表": (["合并现金流量表"], 2),
    "05-现金流量表补充资料": (["现金流量表补充资料", "将净利润调节为经营活动现金流量"], 2),
    "06-借款与有息负债": (["短期借款", "长期借款", "一年内到期的非流动负债"], 1),
    "07-股份变动": (["股份变动情况", "股本变动"], 2),
    "08-分部报告": (["分部报告", "分产品", "分行业"], 1),
    "09-客户与供应商集中度": (["前五名客户", "前五大客户", "前五名供应商"], 1),
    "10-研发投入": (["研发投入"], 1),
    "11-商誉与受限资产": (["商誉", "所有权或使用权受到限制的资产"], 1),
    "12-管理层讨论与分析": (["管理层讨论与分析", "经营情况讨论与分析"], 1),
}

PAGE_RE = re.compile(r"\[\[page (\d+)\]\]")


def split_pages(text):
    """把整份文本切成 {页码: 正文}。"""
    parts = PAGE_RE.split(text)
    # split 结果: ['前导', '1', '正文1', '2', '正文2', ...]
    pages = {}
    for i in range(1, len(parts) - 1, 2):
        pages[int(parts[i])] = parts[i + 1]
    return pages


def build(pages):
    """返回 {主题: 页码列表}。"""
    hits = {}
    for topic, (keywords, tail) in TOPICS.items():
        want = set()
        for kw in keywords:
            for num, body in pages.items():
                if kw in body:
                    want.update(range(num, num + 1 + tail))
        if want:
            hits[topic] = sorted(want)
    return hits


def render(pages, hits):
    out = []
    for topic in sorted(hits):
        nums = [n for n in hits[topic] if n in pages]
        if not nums:
            continue
        shown = ",".join(str(n) for n in nums)
        out.append(f"\n{'=' * 60}\n## {topic}   (p{shown})\n{'=' * 60}")
        for n in nums:
            out.append(f"\n[[page {n}]]\n{pages[n]}")
    return "".join(out)


def main(text_dir, out_dir, index_only=False):
    text_dir, out_dir = Path(text_dir), Path(out_dir)
    files = sorted(text_dir.glob("*.txt"))
    if not files:
        sys.exit(f"没找到文本文件: {text_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        pages = split_pages(f.read_text(encoding="utf-8"))
        hits = build(pages)
        if index_only:
            print(f"\n=== {f.name}  ({len(pages)} 页) ===")
            for topic in sorted(hits):
                print(f"  {topic:24s} -> p{hits[topic][:12]}")
            continue
        body = render(pages, hits)
        dest = out_dir / (f.stem + "-摘录.md")
        dest.write_text(body, encoding="utf-8")
        print(f"{f.name} -> {dest.name}  ({len(body) / 1024:.0f} KB)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    main(args[0], args[1], index_only="--index" in sys.argv)
