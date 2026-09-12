# -*- coding: utf-8 -*-
"""统计 Python 文件的代码行 / 注释行比例（供 comment-check 技能使用）。

用法：python comment_ratio.py <文件或目录> [<文件或目录> ...]
- 给目录就递归找里面的 .py 文件（自动跳过 .git/.claude/__pycache__ 等目录）
- 只统计，不修改任何代码
"""
import io
import sys
import tokenize
from pathlib import Path

# 扫描时跳过的目录
SKIP_DIRS = {".git", ".claude", "__pycache__", "venv", ".venv", "node_modules", "site-packages"}

# 目标：10 行里约 7 行代码、3 行注释 -> 注释占比 30%
TARGET_RATIO = 0.30
WARN_RATIO = 0.15  # 低于这个算严重缺注释


def _docstring_lines(source):
    """找出 docstring（模块/函数/类开头的三引号字符串）占用的行号集合（1 起）。"""
    doc = set()
    prev = None
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.STRING:
                # 字符串是语句开头（文件头、缩进后、换行后）=> 是 docstring
                if prev is None or prev.type in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL):
                    for ln in range(tok.start[0], tok.end[0] + 1):
                        doc.add(ln)
            prev = tok
    except (tokenize.TokenError, IndentationError):
        pass  # 解析不了就跳过 docstring 统计，不影响整体
    return doc


def analyze(path):
    """统计单个文件的各类行数，返回字典。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    lines = source.splitlines()
    doc_lines = _docstring_lines(source)

    blank = comment = doc_count = code = 0
    for i, raw in enumerate(lines, start=1):
        s = raw.strip()
        if not s:
            blank += 1
        elif s.startswith("#"):
            comment += 1
        elif i in doc_lines:
            doc_count += 1
        else:
            code += 1

    comment_total = comment + doc_count
    code_total = comment_total + code
    ratio = round(comment_total / code_total, 2) if code_total else 0
    return {
        "path": str(path),
        "total": len(lines),
        "blank": blank,
        "code": code,
        "comment": comment,
        "docstring": doc_count,
        "comment_total": comment_total,
        "ratio": ratio,
    }


def _level(ratio):
    if ratio >= TARGET_RATIO:
        return "达标"
    if ratio >= WARN_RATIO:
        return "欠注释"
    return "严重缺注释"


def collect(paths):
    """把传入的文件/目录展开成 .py 文件列表。"""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if not any(part in SKIP_DIRS for part in f.parts):
                    files.append(f)
        elif p.is_file() and p.suffix == ".py":
            files.append(p)
    return files


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python comment_ratio.py <文件或目录> [...]")
        sys.exit(1)

    files = collect(args)
    if not files:
        print("没有找到 .py 文件")
        return

    print(f"comment-ratio 统计结果  (目标注释占比 {TARGET_RATIO:.0%})")
    print("=" * 60)
    summary = []
    for f in files:
        r = analyze(f)
        level = _level(r["ratio"])
        summary.append(level)
        print(f"\n文件: {r['path']}")
        print(f"  总行数: {r['total']}  (空行 {r['blank']})")
        print(f"  代码行: {r['code']}   注释行: {r['comment']}   文档行: {r['docstring']}")
        print(f"  注释占比: {r['ratio']:.0%}  -> {level}")

    print("\n" + "=" * 60)
    print(f"汇总: 共 {len(files)} 个文件, "
          f"达标 {summary.count('达标')} 个, "
          f"欠注释 {summary.count('欠注释')} 个, "
          f"严重缺注释 {summary.count('严重缺注释')} 个")


if __name__ == "__main__":
    main()
