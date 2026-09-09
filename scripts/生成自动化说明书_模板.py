# ══════════════════════════════════════════════════════════════════
# 【模板】自动化说明书生成器 —— 克隆母版 + 定点替换 + 去标签化断言
# 用法：改 CONFIG① 母版/输出/项目名 + CONFIG② 替换表 + CONFIG③ 品牌词清单，
#       python3 生成自动化说明书_模板.py 运行。
# 纪律：① 唯一前缀独立条目（替换顺序敏感，长句先） ② 每处替换后计数断言
#       ③ 旧标识清零断言 ④ 品牌词清零断言（去标签化，交付红线）
# 前置三问（见 references/06）：项目名已问用户？设计文稿有无？母版已确认？
# ══════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""
自动化说明书生成器模板（通用去标签化版）：
读母版 HTML → 按替换表定点替换 → 去标签化断言 → 写新 HTML。

母版 = 用户确认过的已验证同类说明书 HTML（旧说明书只是风格参考，用前先问）。
无母版时按 16 页标准结构从零排版（见 references/06 方法 B），本脚本不适用。
生成 HTML 后转 A4 PDF：headless Chrome（命令在文件末尾注释）。
"""
import sys

# ── CONFIG① 母版 / 输出 / 项目名（复用必改；项目名必须已问用户拍板）──
MASTER_HTML = ""   # 母版 HTML 路径（用户确认过的已验证说明书）
OUT_HTML = ""      # 输出路径，如 "自动化说明书.html"
PROJECT_NAME = ""  # 用户拍板的项目名（不要自拟带公司/品牌字样的名字）
if not MASTER_HTML or not OUT_HTML or not PROJECT_NAME:
    sys.exit("【模板提示】请先改 MASTER_HTML / OUT_HTML / PROJECT_NAME（项目名先问用户）")

# ── CONFIG② 替换表 (旧文本, 新文本)：从新项目的脚本/台面/弹窗逐项提炼 ──
# 原则：唯一前缀定位（长句先替换，防部分改写导致后续失配）；约 40 处量级。
# 参考示例（一步法母版 → 新项目）：
#   ("rna-mgisc960-onestep-manual", "新脚本名"),
#   ("一步法说明书 V3", f"{PROJECT_NAME} 自动化说明书"),
REPLACEMENTS: list[tuple[str, str]] = []
if not REPLACEMENTS:
    sys.exit("【模板提示】请先填 REPLACEMENTS 替换表（旧标识→新内容）")

# ── CONFIG③ 品牌词清单（去标签化红线）：交付物中不得出现的公司/品牌名 ──
# 来源 = 母版里出现过的厂商名、品牌词、旧项目公司字样；跑前必须补齐。
# 图片里的 logo 无法文本检索：人工核对封面/页眉/页脚内嵌图（删图或换中性占位）。
BRAND_WORDS: list[str] = []
if not BRAND_WORDS:
    sys.exit("【模板提示】请先填 BRAND_WORDS 品牌词清单（去标签化断言用）")


def replace_with_assert(html: str, old: str, new: str) -> str:
    """单处定点替换 + 计数断言（防漏替换）。"""
    n = html.count(old)
    assert n > 0, f"替换失配（检查顺序/唯一前缀）: {old[:50]!r}"
    html = html.replace(old, new)
    assert html.count(new) >= n, f"替换后计数异常: {new[:50]!r}"
    return html


def assert_no_brand(html: str) -> None:
    """去标签化断言：任何品牌词残留即失败（交付红线）。"""
    for word in BRAND_WORDS:
        n = html.count(word)
        assert n == 0, f"[去标签化失败] 品牌词 {word!r} 残留 {n} 次"


def main() -> None:
    html = open(MASTER_HTML, encoding="utf-8").read()
    for old, new in REPLACEMENTS:
        html = replace_with_assert(html, old, new)
    # 旧标识清零：如需额外断言旧版本号/旧 URL 出现 0 次，在此追加
    assert_no_brand(html)
    open(OUT_HTML, "w", encoding="utf-8").write(html)
    print(f"已生成 {OUT_HTML}（项目：{PROJECT_NAME}）；替换 {len(REPLACEMENTS)} 处，去标签化断言通过")
    print("下一步：headless Chrome 转 A4 PDF（见文件末尾命令）")


if __name__ == "__main__":
    main()

# PDF 转换（macOS 示例，关页眉页脚）：
# "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#   --headless --disable-gpu --no-pdf-header-footer \
#   --print-to-pdf="自动化说明书-A4.pdf" "file://$(pwd)/自动化说明书.html"
