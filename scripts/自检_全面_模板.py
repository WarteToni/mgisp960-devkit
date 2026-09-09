# ══════════════════════════════════════════════════════════════════
# 【模板】交付前全面自检 —— 板流/容量/枪头/硬件/语法/弹窗/并发/参数规则
# 用法：改 CONFIG①~⑤ 后 python3 自检_全面_模板.py
# 输出：🔴 错误（有则禁止交付）/ 🟡 警告（人工复核）/ ℹ️ 提示；退出码 1=有错误
# 检查项来源：SKILL.md 红线速记、01 硬件规则、02 语法规范、08 踩坑实录、
#             13 液体操作经验铁律。模板引擎通用；台面/废液/装液量按项目配置。
# ══════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""
交付前全面自检（替代旧的板流模拟+参数一致性两个工具）：

 A 板流模拟      —— mvkit 源有板/目标空；液体操作时板位必须有板
 B 枪头台账      —— 仅 POS5 可 8 头取枪头；POS5 列唯一且 ≤12 列；96 头盒限 POS1-4/6-8
 C 容量核算      —— 废液分板累计 < 容量×余量；装液板消耗 ≤ 装液量
 D 换台一致性    —— 弹窗三栏（取出/保留/放入）与换台后 pos_type_map 逐项互证（踩坑#6）
 E 声明合法性    —— POS1-8 不放板；振荡位 [..,"shake"] 格式；feature 7 字段/'Pos1'/4 种标记
 F 语法红线      —— initialize/pcr_stop/多参 dialog/位置参 report 等 WD 残留与禁用 API（08#5）
 G 成对规则      —— update_feature 后必有 binding_map；换台后重新绑定（红线6）；
                    shake_on 需 shake.binding；首尾 home()
 H PCR 方法核对  —— pcr_run_methods 方法名 ⊆ XML 实际方法（04：改名必须两头同步）
 I 并发模型      —— 两个"手臂分支"（含液体操作的 parallel 函数）时间区间不得重叠；
                    手臂分支运行期间主流程不得再有液体操作（臂×1，01/05§五）；
                    模块分支（PCR/温控/振荡）与手臂并行是合法形态，不告警
 J 参数规则      —— 公式 Z 提示人工复核（负 Z 官方允许，不报错）
 K 枪头量程      —— 吸液+前吸+后吸 两档：>165 警告（带滤芯保证量程）、
                    >200 报错（不带滤芯硬上限）；排液体积 ≤ 当前枪头液量
                    （官方：≤ 上一步吸液体积，报错）；mix 末排 ≤ 枪头液量

口径说明：容量/废液按"每次调用=每孔一次"累计（与装液量同口径）；
公式体积（含循环变量）按最大值估计；解析不了的项跳过并提示，不误报。
"""
import ast
import re
import sys

# ── CONFIG① 待自检脚本路径（复用必改）──
SRC = ""
if not SRC:
    sys.exit("【模板提示】请先改 SRC 指向待自检的 spredo 脚本")

# ── CONFIG② PCR XML 路径（可选；留空则跳过 H 项核对）──
XML_PATH = ""

# ── CONFIG③ 装液量板位（μL/孔；消耗按每次调用累计，同口径）──
# 参考示例（一步法）: {'POS22': 230, 'POS12': 1000}
LIQ_STOCK: dict[str, float] = {}

# ── CONFIG④ 废液板位与单孔容量（μL）──
# 参考示例（一步法）: {'POS23': 1300, 'POS18': 1300}
WASTE_POS: dict[str, float] = {}
WASTE_MARGIN = 0.8          # 超过 容量×0.8 警告，超过容量报错（05§三：留 20% 余量）

# ── CONFIG⑤ 换台弹窗识别词（dialog 文本含该词即按换台处理）──
SWAP_MARK = "换台"

# ── CONFIG⑥ 枪头量程 μL（官方课程6：带滤芯 2-165 / 不带滤芯 2-200）──
# 两档判级：>TIP_CAPACITY 警告（超带滤芯保证量程）；>TIP_HARD 报错（硬上限）
TIP_CAPACITY = 165
TIP_HARD = 200

errors: list[str] = []
warns: list[str] = []
infos: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warns.append(msg)


def info(msg: str) -> None:
    infos.append(msg)


# ══════════════ 字符串感知的行处理与语句切分 ══════════════
def desquote(line: str, tri: str | None) -> tuple[str, str | None]:
    """去掉字符串字面量与注释（保留括号计数所需结构），跨行三引号状态传递。"""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        if tri:
            if line[i:i + 3] == tri:
                tri = None
                i += 3
            else:
                i += 1
            continue
        if line[i:i + 3] in ('"""', "'''"):
            tri = line[i:i + 3]
            out.append(" ")
            i += 3
            continue
        c = line[i]
        if c == "#":
            break
        if c in ("'", '"'):
            q = c
            i += 1
            while i < n:
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == q:
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        out.append(c)
        i += 1
    return "".join(out), tri


def read_statements(path: str) -> tuple[list[tuple[int, str]], list[str]]:
    """按 ()/{}/[] 平衡切逻辑语句（字符串感知）。返回 (行号,语句) 列表与原始行列表。"""
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    stmts: list[tuple[int, str]] = []
    buf, start = "", 0
    dp = db = dk = 0
    tri: str | None = None
    for i, raw in enumerate(lines, 1):
        clean, tri = desquote(raw.rstrip("\n"), tri)
        if not buf and not clean.strip():
            continue
        if not buf:
            start = i
        buf += raw.rstrip("\n") + "\n"
        dp += clean.count("(") - clean.count(")")
        db += clean.count("{") - clean.count("}")
        dk += clean.count("[") - clean.count("]")
        if dp <= 0 and db <= 0 and dk <= 0:
            stmts.append((start, buf))
            buf, dp, db, dk = "", 0, 0, 0
    if buf.strip():
        stmts.append((start, buf))
    return stmts, lines


def parse_dict_arg(stmt: str) -> dict:
    m = re.search(r"\{(.*)\}", stmt, re.S)
    if not m:
        return {}
    return dict(re.findall(r"['\"](\w+)['\"]\s*:\s*([^,}]+)", m.group(1)))


def vol_of(d: dict, key: str):
    v = (d.get(key) or "").strip().strip("'\"()")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        expr = v
        for var, mx in (("x", 12), ("i", 12), ("z", 12), ("y", 12), ("c", 11), ("j", 5)):
            expr = re.sub(rf"\b{var}\b", str(mx), expr)
        try:
            return float(eval(expr, {}))  # noqa: S307 模板自检，输入为本地脚本
        except Exception:
            return None


def literal_of(stmt: str, opener: str):
    idx = stmt.find(opener)
    if idx < 0:
        return None
    text = stmt[idx:]
    depth = 0
    for cut in range(len(text)):
        c = text[cut]
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:
                try:
                    return ast.literal_eval(text[: cut + 1])
                except Exception:
                    return None
    return None


# ══════════════ 台面状态机 ══════════════
def norm_state(v):
    if v == "useless":
        return ("useless", "", False)
    if v is None:
        return ("empty", "", False)
    if isinstance(v, list):
        kit = v[0] if v and v[0] else ""
        return (("plate" if kit else "empty"), str(kit), "shake" in v)
    return ("plate", str(v), False)


def check_tip_positions(deck: dict, ln: int, tag: str) -> None:
    for p in (f"POS{n}" for n in range(1, 9)):
        st = deck.get(p)
        if st and st[0] == "plate":
            err(f"L{ln} [E] {tag}{p} 是枪头位却声明了板（红线2：POS1-8 不放板）")


stmts, raw_lines = read_statements(SRC)
text_all = "".join(s for _, s in stmts)

# def 函数体行区间（并发检查用）
def_ranges: list[tuple[str, int, int]] = []
for i, rl in enumerate(raw_lines, 1):
    m = re.match(r"def\s+(\w+)\s*\(", rl)
    if m:
        j = i
        while j < len(raw_lines):
            nxt = raw_lines[j]
            if nxt.strip() and not nxt.startswith((" ", "\t")):
                break
            j += 1
        def_ranges.append((m.group(1), i, j))


def in_def(ln: int) -> bool:
    return any(a <= ln <= b for _, a, b in def_ranges)


def def_ops(fn: str) -> int:
    for name, a, b in def_ranges:
        if name == fn:
            return sum(1 for rl in raw_lines[a:b] if LIQ_RE.search(rl))
    return 0


LIQ_RE = re.compile(r"\b(?:a_)?(aspirate|dispense|empty|mix|mvkit)\s*\(")

# ── 列表赋值映射（update_feature(SWAP1_POS) 这类按名引用）──
assign_map: dict[str, list] = {}
for ln, s in stmts:
    m = re.match(r"\s*(\w+)\s*=\s*\[", s)
    if m:
        lit = literal_of(s, "[")
        if isinstance(lit, list):
            assign_map[m.group(1)] = lit

deck: dict[str, tuple] = {}
for ln, s in stmts:
    t = s.strip()
    if t.startswith("pos_type_map"):
        lit = literal_of(s, "{")
        if isinstance(lit, dict):
            deck = {k: norm_state(v) for k, v in lit.items()}
            check_tip_positions(deck, ln, "初始台面 ")
            for k, v in lit.items():
                if isinstance(v, str) and "shake" in v:
                    err(f"L{ln} [E] {k} 振荡位应为 [..,\"shake\"] 列表格式（08#3）")
            break

tip_content = 0.0
waste_acc: dict[str, float] = {p: 0.0 for p in WASTE_POS}
liq_used: dict[str, float] = {p: 0.0 for p in LIQ_STOCK}
pos5_cols: list[int] = []
pcr_methods_used: list[tuple[int, str]] = []
swap_expect: tuple[set, set, set] | None = None
pending_update_feature: list[int] = []
parallel_submit: list[tuple[int, str, str]] = []   # (行号, 变量名, 函数名)
waits: dict[str, int] = {}                         # 变量名 → Wait 行号


def parse_pos_tokens(seg: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"Pos\s*(\d+)\s*[-–~]\s*(?:Pos\s*)?(\d+)", seg):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b <= 24:
            out |= {f"POS{n}" for n in range(a, b + 1)}
    for m in re.finditer(r"Pos\s*(\d+)", seg):
        out.add(f"POS{int(m.group(1))}")
    return out


def split_dialog_sections(txt: str):
    take = re.search(r"【取出[^】]*】(.*?)(?=【|确认|$)", txt, re.S)
    keep = re.search(r"【保留[^】]*】(.*?)(?=【|确认|$)", txt, re.S)
    load = re.search(r"【放入[^】]*】(.*?)(?=【|确认|$)", txt, re.S)
    return (parse_pos_tokens(take.group(1)) if take else set(),
            parse_pos_tokens(keep.group(1)) if keep else set(),
            parse_pos_tokens(load.group(1)) if load else set())


for ln, s in stmts:
    t = s.strip()

    # ── A 搬板 ──
    m = re.match(r"mvkit\(\s*['\"](POS\d+)['\"]\s*,\s*['\"](POS\d+)['\"]", t)
    if m:
        a, b = m.group(1), m.group(2)
        sa, sb = deck.get(a), deck.get(b)
        if not sa or sa[0] != "plate":
            err(f"L{ln} [A] mvkit({a},{b})：源位 {a} 当时无板（软件会拒：源位必须有板）")
        elif sb and sb[0] != "empty":
            err(f"L{ln} [A] mvkit({a},{b})：目标位 {b} 当时非空（loose_check 会拒）")
        else:
            if b in ("POS9", "POS10", "POS11") and "PCR" not in sa[1]:
                warn(f"L{ln} [A] mvkit 到 PCR 位 {b} 的板 {sa[1]!r} 不像 PCR 板，人工确认")
            deck[b] = sa
            deck[a] = ("empty", "", sa[2])
        continue

    # ── B 枪头 ──
    if t.startswith("load_tips"):
        tip_content = 0.0    # 换新枪头，液量清零
        d = parse_dict_arg(s)
        mod = d.get("Module", "").strip("'\"")
        tips = (d.get("Tips") or "96").strip()
        try:
            tips_n = int(tips)
        except ValueError:
            tips_n = 96
        if tips_n == 8:
            if mod != "POS5":
                err(f"L{ln} [B] 8 头取枪头只能在 POS5（红线2），实际 {mod}")
            else:
                well = d.get("Well", "").strip("'\"")
                colm = d.get("Col", "").strip()
                col = None
                cm = re.match(r"(\d+)", well)
                if well and cm:
                    col = int(cm.group(1))
                elif colm.isdigit():
                    col = int(colm)
                if col:
                    if col in pos5_cols:
                        err(f"L{ln} [B] POS5 第 {col} 列重复取用（每列只能用一次）")
                    pos5_cols.append(col)
                    if len(pos5_cols) > 12:
                        err(f"L{ln} [B] POS5 八头盒已超过 12 列（用了 {len(pos5_cols)} 列）")
        else:
            if mod not in {f"POS{n}" for n in (1, 2, 3, 4, 6, 7, 8)}:
                warn(f"L{ln} [B] 96 头盒通常取自 POS1-4/6-8，实际 {mod}，人工确认")
        continue

    if t.startswith("unload_tips"):
        tip_content = 0.0
        continue

    # ── A/C/J 液体操作 ──
    lm = re.match(r"(?:a_)?(aspirate|dispense|empty|mix)\(", t)
    if lm:
        op = lm.group(1)
        d = parse_dict_arg(s)
        mod = d.get("Module", "").strip("'\"")
        st = deck.get(mod)
        if st is None:
            warn(f"L{ln} [A] {op} 的板位 {mod} 未在台面声明中出现，人工确认")
        elif st[0] != "plate":
            err(f"L{ln} [A] {op} 时 {mod} 无板（磁架/空位空吸=事故）")
        zraw = (d.get("BottomOffsetOfZ") or "").strip().strip("'\"")
        if zraw:
            try:
                float(zraw)   # 负 Z 官方允许（课程6：可为负无限制），不报错
            except ValueError:
                if re.search(r"[a-wyz]", zraw):
                    info(f"L{ln} [J] {op}@{mod} Z 为公式 {zraw!r}（液面跟踪，人工复核推导依据，见 11）")
        if op == "aspirate":
            v = vol_of(d, "AspirateVolume")
            pre = vol_of(d, "PreAirVolume") or 0
            post = vol_of(d, "PostAirVolume") or 0
            if v is not None:
                total = v + pre + post
                if total > TIP_HARD:
                    err(f"L{ln} [K] {op}@{mod} 枪头总量=吸{v:g}+前吸{pre:g}+后吸{post:g}"
                        f"={total:g}μL > 硬上限 {TIP_HARD:g}μL（不带滤芯量程，CONFIG⑥）")
                elif total > TIP_CAPACITY:
                    warn(f"L{ln} [K] {op}@{mod} 枪头总量 {total:g}μL > 带滤芯保证量程"
                         f" {TIP_CAPACITY:g}μL（产线有实机通过先例；确认枪头型号/精度要求）")
                tip_content += v
                if mod in liq_used:
                    liq_used[mod] += v
        elif op == "dispense":
            v = vol_of(d, "DispenseVolume")
            if v is not None:
                if v > tip_content + 1e-6:
                    err(f"L{ln} [K] {op}@{mod} 排液 {v:g}μL > 当前枪头液量 {tip_content:g}μL"
                        f"（官方：DispenseVolume 必须 ≤ 上一步吸液体积）")
                tip_content = max(0.0, tip_content - v)
        elif op == "mix":
            mv = vol_of(d, "MixLoopVolume") or 0
            mpre = vol_of(d, "PreAirVolume") or 0
            if mv + mpre > TIP_HARD:
                err(f"L{ln} [K] {op}@{mod} mix 体积{mv:g}+前吸{mpre:g}={mv + mpre:g}μL"
                    f" > 硬上限 {TIP_HARD:g}μL")
            elif mv + mpre > TIP_CAPACITY:
                warn(f"L{ln} [K] {op}@{mod} mix 体积+前吸 {mv + mpre:g}μL > 带滤芯保证量程"
                     f" {TIP_CAPACITY:g}μL（确认枪头型号/精度要求）")
            da = vol_of(d, "DispenseVolumeAfterSubmixLoop")
            if da and tip_content > 0.5 and da > tip_content + 1e-6:
                err(f"L{ln} [K] {op}@{mod} 末排 {da:g}μL > 枪头液量 {tip_content:g}μL")
            if da:
                tip_content = max(0.0, tip_content - da)
        elif op == "empty":
            if mod in waste_acc and tip_content > 0:
                waste_acc[mod] += tip_content
            tip_content = 0.0
        continue

    # ── D 换台弹窗 ──
    if t.startswith("dialog("):
        body = s[s.index("("):]
        if SWAP_MARK in body:
            swap_expect = split_dialog_sections(body)
            if not any(swap_expect):
                warn(f"L{ln} [D] 换台弹窗未解析出【取出/保留/放入】板位，人工核对")
        depth, args, started = 0, 1, False
        for ch in body:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                if depth <= 1 and started:
                    break
                depth -= 1
            elif ch == "," and depth == 1:
                args += 1
        if args > 1:
            err(f"L{ln} [F] dialog 为 {args} 参数（spredo 应单参；4 参是 WD 语法，08#5）")
        continue

    # ── E/G 台面更新 ──
    if t.startswith("update_feature"):
        pending_update_feature.append(ln)
        mname = re.match(r"update_feature\s*\(\s*(\w+)\s*\)", t)
        lit = None
        if mname and mname.group(1) in assign_map:
            lit = assign_map[mname.group(1)]
        else:
            lit = literal_of(s, "[")
        if isinstance(lit, list):
            for tup in lit:
                if not isinstance(tup, (tuple, list)) or len(tup) != 7:
                    err(f"L{ln} [E] feature 元组应为 7 字段：{str(tup)[:60]}")
                    continue
                if not re.match(r"Pos\d+$", str(tup[0])):
                    err(f"L{ln} [E] feature 首字段应为 'Pos1' 形态（大写P小写os）：{tup[0]!r}")
                if tup[6] not in ("", "PCR", "MagRack", "Shaker", "Temp_Module"):
                    err(f"L{ln} [E] 非法标记 {tup[6]!r}（合法仅 4 种+空，02§一）")
        continue

    if re.match(r"pos_type_map\s*=", t):
        lit = literal_of(s, "{")
        if isinstance(lit, dict):
            new_deck = {k: norm_state(v) for k, v in lit.items()}
            if swap_expect:
                take, keep, load = swap_expect
                for p in sorted(take):
                    # 取出后又放入 = 换板（如废液板→乙醇板），不算矛盾
                    if p in load:
                        continue
                    if p in new_deck and new_deck[p][0] == "plate":
                        warn(f"L{ln} [D] 弹窗说【取出】{p}，但新台面仍有板 {new_deck[p][1]!r}"
                             f"（踩坑#6：弹窗与逻辑必须互证）")
                for p in sorted(keep):
                    # 枪头位（useless）保留的是枪头盒不是板，不校验；只拦"该留板却是空位"
                    if p in new_deck and new_deck[p][0] == "empty":
                        warn(f"L{ln} [D] 弹窗说【保留】{p}，但新台面该位是空位")
                for p in sorted(load):
                    # 枪头位放的是枪头盒不是板，不校验
                    if p in new_deck and new_deck[p][0] == "empty":
                        warn(f"L{ln} [D] 弹窗说【放入】{p}，但新台面该位是空位")
                swap_expect = None
            deck = new_deck
            check_tip_positions(deck, ln, "换台后台面 ")
        continue

    # ── H/I 收集 ──
    mm = re.search(r"pcr_run_methods\(\s*method\s*=\s*['\"]([^'\"]+)['\"]", t)
    if mm:
        pcr_methods_used.append((ln, mm.group(1)))
        continue
    pm = re.match(r"(\w+)\s*=\s*parallel_block\s*\(\s*(\w+)\s*\)", t)
    if pm:
        parallel_submit.append((ln, pm.group(1), pm.group(2)))
        continue
    wm = re.match(r"(\w+)\s*\.\s*Wait\s*\(", t)
    if wm:
        waits.setdefault(wm.group(1), ln)
        continue

# ══════════════ F 语法红线（全文扫描） ══════════════
if re.search(r"\binitialize\s*\(", text_all):
    err("[F] 出现 initialize()（spredo 直写版应用 init(spx96)，08#5）")
for m in re.finditer(r"\bpcr_stop\s*\(", text_all):
    if not text_all[m.end():m.end() + 8].startswith("heating"):
        err("[F] pcr_stop 不存在，应为 pcr_stop_heating（08#5）")
for m in re.finditer(r"\breport\s*\(", text_all):
    seg = text_all[m.end():m.end() + 40]
    if "=" not in seg.split(")")[0]:
        warn(f"[F] report 疑似位置参数（spredo 应关键字参数 phase=/step=，08#5）：{seg[:30]!r}")
if re.search(r"\bshake_(on|off)\s*\(", text_all) and "shake.binding" not in text_all:
    err("[G] 用了 shake_on/shake_off 但 HEAD 缺 shake.binding(spx96)（08#5）")
home_n = len(re.findall(r"\bhome\s*\(\s*\)", text_all))
if home_n < 2:
    warn(f"[G] home() 仅 {home_n} 次（建议开头结尾各一次，08#5）")
if re.search(r"\blog\s*\(", text_all):
    warn("[F] 使用了 log()（控制软件环境未验证，02§四：谨慎起见不用）")

# ══════════════ G update_feature 后必须 binding_map ══════════════
bind_lines = [ln for ln, s in stmts if s.strip().startswith("binding_map")]
for ln_uf in pending_update_feature:
    if not any(ln_uf < lb <= ln_uf + 40 for lb in bind_lines):
        err(f"L{ln_uf} [G] update_feature 后未找到 binding_map（红线6：换台必须重新绑定）")

# ══════════════ I 并发模型 ══════════════
arm_intervals: list[tuple[int, int, str]] = []
for ln_sub, var, fn in parallel_submit:
    n_ops = def_ops(fn)
    if n_ops == 0:
        continue  # 模块分支（PCR/温控/振荡）：与手臂并行合法
    ln_wait = waits.get(var)
    if not ln_wait:
        warn(f"L{ln_sub} [I] parallel_block({fn}) 未见 {var}.Wait()，人工确认")
        continue
    arm_intervals.append((ln_sub, ln_wait, fn))
    # 手臂分支区间内，主流程（def 之外）不应有液体操作
    main_ops = [ln2 for ln2, s2 in stmts
                if ln_sub < ln2 < ln_wait and LIQ_RE.search(s2) and not in_def(ln2)]
    if main_ops:
        warn(f"L{ln_sub} [I] 手臂分支 {fn} 运行期间（至 L{ln_wait}），主流程还有 "
             f"{len(main_ops)} 处液体操作（如 L{main_ops[0]}）——机械臂×1，任何时刻最多 1 个"
             f"手臂分支（01/05§五），人工确认")
for i in range(len(arm_intervals)):
    for j in range(i + 1, len(arm_intervals)):
        a1, a2, fa = arm_intervals[i]
        b1, b2, fb = arm_intervals[j]
        if a1 < b2 and b1 < a2:
            warn(f"[I] 两个手臂分支 {fa}(L{a1}-{a2}) 与 {fb}(L{b1}-{b2}) 时间区间重叠"
                 f"——双臂并行=未定义行为（01/05§五），人工确认")

# ══════════════ C/H 结尾核算 ══════════════
for p, cap in WASTE_POS.items():
    acc = waste_acc.get(p, 0.0)
    if acc > cap:
        err(f"[C] 废液板 {p} 累计 {acc:.0f}μL > 容量 {cap:.0f}μL（深孔板 1300μL/孔，05§三）")
    elif acc > cap * WASTE_MARGIN:
        warn(f"[C] 废液板 {p} 累计 {acc:.0f}μL > {WASTE_MARGIN:.0%} 容量"
             f"（{cap * WASTE_MARGIN:.0f}μL），建议分流或手工复核（粗算可能虚高）")
for p, stock in LIQ_STOCK.items():
    used = liq_used.get(p, 0.0)
    if used > stock:
        err(f"[C] {p} 消耗 {used:.0f}μL > 装液量 {stock:.0f}μL/孔——中途会吸空")
    elif used > stock * 0.9:
        warn(f"[C] {p} 消耗 {used:.0f}μL 达装液量 {stock:.0f}μL 的 {used / stock:.0%}，余量偏紧")
if pos5_cols:
    info(f"[B] POS5 八头盒用列：{sorted(pos5_cols)}（共 {len(pos5_cols)}/12 列）")

if XML_PATH:
    try:
        xml = open(XML_PATH, encoding="utf-8").read()
        defined = set(re.findall(r"methodName=\"([^\"]+)\"", xml))
        for ln, name in pcr_methods_used:
            if name not in defined:
                err(f"L{ln} [H] PCR 方法 {name!r} 不在 XML 中（04：方法名两头必须同步）")
        info(f"[H] 脚本引用 {len(set(n for _, n in pcr_methods_used))} 个方法，XML 定义 {len(defined)} 个")
    except OSError:
        warn(f"[H] XML 文件不可读：{XML_PATH}，跳过方法名核对")

# ══════════════ 报告 ══════════════
print("=" * 70)
print(f"全面自检：{SRC}")
print("=" * 70)
for tag, lst in (("🔴 错误（禁止交付）", errors), ("🟡 警告（人工复核）", warns), ("ℹ️ 提示", infos)):
    print(f"\n{tag}：{len(lst)} 条")
    for x in lst:
        print("  -", x)
print("\n" + "=" * 70)
if errors:
    print(f"✗ 未通过：{len(errors)} 个错误必须修复后重检")
    sys.exit(1)
print(f"✓ 通过（{len(warns)} 条警告需人工复核）")
