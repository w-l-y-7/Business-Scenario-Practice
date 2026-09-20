"""生成试排用的样图。

只为验证「Markdown 里的 ![](figures/xxx.png) 能不能排进 PDF」这一件事，
图上的数字全是编的，**不是任何真实公司的数据**，不得引用进研报。

用法：python tools/pdf/make_smoke_figure.py
输出：figures/试排样图.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "试排样图.png"

fig, ax = plt.subplots(figsize=(8, 3.6), dpi=200)
labels = ["2023", "2024", "2025"]
values = [1.0, 1.6, 2.5]
bars = ax.bar(labels, values, color=["#9db8d2", "#5b8cb8", "#2d5f8a"], width=0.55)
ax.bar_label(bars, fmt="%.1f", padding=3)
ax.set_title("试排样图 —— 数字均为编造，不得引用", fontsize=11)
ax.set_ylabel("任意单位")
ax.spines[["top", "right"]].set_visible(False)
ax.set_ylim(0, max(values) * 1.2)

fig.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT)
print(f"已生成：{OUT}")
