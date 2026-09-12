# -*- coding: utf-8 -*-
"""安全审计扫描脚本（供 security-audit 技能使用）。

用法：python security_scan.py <文件或目录> [<文件或目录> ...]
- 给目录就递归找里面的代码/配置文件（自动跳过 .git/.claude/__pycache__ 等目录）
- 只扫描并列出「可疑点」，不修改任何代码
- 扫描结果是怀疑清单：每个点都还要再读一遍原代码确认是不是真问题
"""
import re
import sys
from pathlib import Path

# 扫描时跳过的目录
SKIP_DIRS = {".git", ".claude", "__pycache__", "venv", ".venv", "node_modules", "site-packages", "dist", "build", ".idea", ".vscode"}

# 代码文件扩展名
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".sh", ".bat", ".ps1", ".swift", ".kt", ".rs", ".sql"}
# 配置文件扩展名
CONFIG_EXTS = {".env", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml", ".json", ".xml", ".properties"}
ALL_EXTS = CODE_EXTS | CONFIG_EXTS | {".pem", ".key"}

# 1) 等号/冒号右边直接给了一个带引号的字符串值 -> 疑似硬编码密钥
SECRET_ASSIGN_RE = re.compile(
    r"""(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|apikey|token|auth[_-]?token|access[_-]?key|secret[_-]?key|client[_-]?secret|private[_-]?key|db[_-]?password|mysql[_-]?password|redis[_-]?password)\b\s*[:=]\s*['"]([^'"]{4,})['"]"""
)
# 2) 配置文件里不带引号的明文值，如 password=123456
CONFIG_SECRET_RE = re.compile(
    r"""(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|apikey|token|secret[_-]?key|access[_-]?key|client[_-]?secret|db[_-]?password)\b\s*[:=]\s*([^\s'";#]+)"""
)
# 3) AWS 访问密钥（AKIA 开头）
AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
# 4) 私钥块
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")
# 5) 连接串里带账号密码，如 mysql://root:secret@host
URL_CRED_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")

# SQL 注入相关
SQL_KEYWORD_RE = re.compile(r"(?<![\w.])\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", re.I)
FSTRING_SQL_RE = re.compile(r"[fF](?:'{3}|\"\"\"|'|\")")
CONCAT_SQL_RE = re.compile(r"('|\")\s*\+|\+\s*('|\")")
FORMAT_SQL_RE = re.compile(r"\.format\s*\(")
PERCENT_SQL_RE = re.compile(r"%\s*(?:\(|\w)")

# 内网/本机 IP
IP_PRIVATE_RE = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|127\.0\.0\.1)\b")

# (正则, 级别, 说明)  危险函数/危险写法
DANGER_FUNCS = [
    (re.compile(r"\beval\s*\("), "高危", "eval(): 把字符串当代码执行，用户能影响输入时等于把代码控制权交出去"),
    (re.compile(r"\bexec\s*\("), "高危", "exec(): 把字符串当代码执行，和 eval 一样危险"),
    (re.compile(r"\bos\.system\s*\("), "高危", "os.system(): 直接把字符串交给系统命令执行，最容易命令注入"),
    (re.compile(r"\bshell\s*=\s*True"), "高危", "shell=True: 让命令走 shell 解析，参数里带特殊字符可能被当成命令执行"),
    (re.compile(r"\bpickle\.(?:load|loads)\s*\("), "高危", "pickle 反序列化：来历不明的数据反序列化时会被植入恶意代码"),
    (re.compile(r"(?i)\bverify\s*=\s*False\b"), "中危", "verify=False: 关闭了 HTTPS 证书校验，中间人可以冒充服务器"),
    (re.compile(r"(?i)\b(?:hashlib\.)?md5\s*\("), "中危", "MD5 哈希：有严重碰撞缺陷，密码/签名场景不能用"),
    (re.compile(r"(?i)\b(?:hashlib\.)?sha1\s*\("), "中危", "SHA1 哈希：有碰撞风险，密码/签名场景不要用"),
    (re.compile(r"\b(?:subprocess\.)?(?:run|call|Popen|check_output|check_call)\s*\(\s*['\"]"), "中危", "命令执行传了字符串：应传参数列表（如 ['git', 'pull']），否则可能被 shell 误解"),
    (re.compile(r"^\s*assert\s+"), "提示", "assert: 用 python -O 跑时会被整体禁用，不能当安全校验用"),
    (re.compile(r"\brandom\."), "提示", "random 模块：只适合游戏/抽签；生成密码、token 要改用 secrets"),
    (re.compile(r"(?i)\bdebug\s*=\s*True\b"), "提示", "debug=True 没关：正式上线前记得关掉，否则可能把内部错误信息暴露给用户"),
]


def _looks_like_placeholder(val):
    """值看着像占位符（your_password、example 之类）就跳过，避免误报。"""
    v = val.lower()
    for w in ("your", "example", "sample", "changeme", "placeholder", "here", "todo", "xxx"):
        if w in v:
            return True
    return "<" in val or ">" in val


def scan_file(path):
    """扫描单个文件，返回 (可疑点列表, 参数化查询处数, 是否读不了)。"""
    findings = []  # (行号, 级别, 说明)
    param_safe = 0
    name = path.name.lower()
    is_env = name == ".env" or name.endswith(".env")
    is_config = path.suffix.lower() in CONFIG_EXTS or is_env
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return findings, param_safe, True

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")

        # 硬编码密码/密钥（带引号）
        m = SECRET_ASSIGN_RE.search(line)
        if m and not _looks_like_placeholder(m.group(1)):
            snippet = m.group(0)[:50]
            if is_env:
                findings.append((i, "提示", f"{snippet}…（.env 放密钥本身正常，但要确认它已加进 .gitignore 且没被提交进 git）"))
            elif is_config:
                findings.append((i, "中危", f"{snippet}…（配置文件里写了明文密钥，应从配置里移走，改用环境变量）"))
            else:
                findings.append((i, "高危", f"{snippet}…（代码里硬编码了敏感值，密钥不该写在源码里，应移到环境变量）"))

        # 配置文件里不带引号的明文值
        if is_config and not is_env:
            m = CONFIG_SECRET_RE.search(line)
            if m and not _looks_like_placeholder(m.group(1)):
                findings.append((i, "中危", f"配置文件明文敏感值: {m.group(0).strip()[:60]}"))

        # AWS 密钥 / 私钥 / 带密码的连接串
        if AWS_KEY_RE.search(line):
            findings.append((i, "高危", "疑似 AWS 访问密钥（AKIA 开头），泄露=云账号可能被黑"))
        if PRIVATE_KEY_RE.search(line):
            findings.append((i, "高危", "私钥泄露：私钥绝不能提交进代码/仓库"))
        if URL_CRED_RE.search(line):
            findings.append((i, "高危", "连接串里带着账号密码（user:pass@），会泄露账号"))

        # SQL 注入风险
        if SQL_KEYWORD_RE.search(line):
            if "?" in line:
                param_safe += 1
            signals = []
            if FSTRING_SQL_RE.search(line) and "{" in line:
                signals.append("f-string 直接拼 SQL")
            if CONCAT_SQL_RE.search(line):
                signals.append("字符串 + 拼接 SQL")
            if FORMAT_SQL_RE.search(line):
                signals.append(".format() 拼 SQL")
            if PERCENT_SQL_RE.search(line):
                signals.append("% 格式化拼 SQL")
            if signals:
                findings.append((i, "高危", f"SQL 疑似注入风险：{'、'.join(signals)}。SQL 应改用 ? 参数占位传参，不要把变量直接拼进字符串"))

        # 危险函数/危险写法
        for pat, sev, msg in DANGER_FUNCS:
            if pat.search(line):
                findings.append((i, sev, msg))

        # 内网/本机 IP
        if IP_PRIVATE_RE.search(line):
            findings.append((i, "提示", "硬编码内网/本机 IP：确认是不是调试残留，正式环境一般从配置读"))

    return findings, param_safe, False


def collect(paths):
    """把传入的文件/目录展开成可扫描的文件列表。"""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if not f.is_file():
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.suffix.lower() in ALL_EXTS or f.name.lower() == ".env":
                    files.append(f)
        elif p.is_file():
            if p.suffix.lower() in ALL_EXTS or p.name.lower() == ".env":
                files.append(p)
    return files


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python security_scan.py <文件或目录> [...]")
        sys.exit(1)

    files = collect(args)
    if not files:
        print("没有找到可扫描的代码/配置文件")
        return

    print("security-scan 扫描结果（可疑点，需再读原代码确认）")
    print("=" * 70)
    high = mid = info = 0
    scanned = 0
    for f in files:
        findings, param_safe, unreadable = scan_file(f)
        if unreadable:
            continue
        scanned += 1
        print(f"\n文件: {f}")
        if param_safe:
            print(f"  [好习惯] {param_safe} 处 SQL 用了 ? 参数占位符（安全写法）")
        if not findings:
            print("  没发现明显可疑点")
            continue
        for ln, sev, msg in findings:
            print(f"  [{sev}] 第 {ln} 行: {msg}")
            if sev == "高危":
                high += 1
            elif sev == "中危":
                mid += 1
            else:
                info += 1

    print("\n" + "=" * 70)
    print(f"汇总: 扫描 {scanned} 个文件，高危 {high} 处，中危 {mid} 处，提示 {info} 处")


if __name__ == "__main__":
    main()
