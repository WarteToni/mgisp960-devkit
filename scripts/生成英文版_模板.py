# ══════════════════════════════════════════════════════════════════
# 【模板】英文版脚本生成器 —— zh-cn → en-us
# 用法：改 CONFIG① CN/EN 文件名 + CONFIG② 三块映射内容，python3 运行。
# 纪律：① 长串优先替换(防词序污染) ② 跑完必须 AST 等价验证通过才可用。
# ══════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""
英文版脚本生成器模板：对中文版做【纯字符串映射替换】，不改任何逻辑/参数/板位。
三块映射内容（docstring 头/弹窗/短语表）= 参考项目（一步法）完整示例，
新项目必须从新脚本的中文串重新提炼；不可动的是骨架方法本身。
验证：AST 等价检查（所有字符串字面量置空后两版语法树必须完全一致）。
"""
import ast, re, sys

# ── CONFIG① 中文源脚本 → 英文版输出路径（复用必改）──
CN = ""   # 参考示例: "某项目_中文直写版.py"
EN = ""   # 参考示例: "某项目_EN_英文版.py"
if not CN or not EN:
    sys.exit("【模板提示】请先改 CN/EN 文件名")

src = open(CN, encoding="utf-8").read()

# ── CONFIG②-a 头部 docstring 整段替换（以下 DOC_EN 为参考项目示例）──
DOC_CN_HEAD = 'Non Strand Specific RNA Library Preparation Kit V3（Python 直写版）'
DOC_EN = '''================================================================================
Non Strand Specific RNA Library Preparation Kit V3 (pure-Python spredo)
MGISP-960 One-Step program - single deck swap - oligo(dT) capture + library prep
Syntax: pure-Python spredo (no WDesigner GUI) - 2026-08-28 - V1.0 aliquot-plate edition
--------------------------------------------------------------------------------
[Design principles]
- All liquid steps inherited from V2.2: aliquot plates + 96-ch transfer
  (production-proven anti-contamination pattern); aspirate/dispense rates,
  air gaps, Z-heights and mix parameters copied verbatim.
- Single deck swap: full load-in at start (capture + aliquot plates + library
  reagents); swap only during the 15-min ligation window.
[Deck layout]
- 4 aliquot plates at POS14 (1st-strand Mix) / POS16 (2nd-strand Mix) /
  POS19 (Adapter) / POS20 (LigMix). POS19/20 are MagRack/Shaker slots used
  as plain plate positions during the enzymatic stage (same precedent as
  V2.2 placing the LigMix plate on MagRack POS15); after deck swap they
  resume MagRack/Shaker duty for purification.
- Transfer tips: POS6 leftover box (frag mix + 1st-strand transfer, V2.2
  pattern), POS7 new (2nd-strand), POS8 new (ligation assembly).
- Single-plate design: mRNA collection plate (POS12) moves into PCR slot
  POS11 and becomes the reaction plate.
- Primer pre-load: PCR primers preloaded into the PCR reaction plate at
  start-up (placed at POS15 after swap) - no primer transfer needed.
- Water plate spans the whole run at POS22 (230 uL); reagent plate POS21
  chilled to 6 C from start-up.
- Waste routing (no waste swap): POS23 = capture + purif-1 waste (~983 uL);
  POS18 size-select-1 plate = size-select-2 + PCR-purif waste (~915 uL).
[Tips] start-up 8 boxes (7x 96-ch + 1x 8-ch) + swap 7 boxes = 15 total.
[PCR cycles] prompt at start-up (dialog-based selection), maps to PCR_10C..16C.
[Hardware] Config-2: POS5 = only 8-ch tip pick-up; POS15/19 = MagRack;
POS20 = Shaker; POS21/22 = temp modules; POS9-11 = PCR; POS24 = waste.
================================================================================'''

first = src.index('"""')                      # docstring 开始
second = src.index('"""', first + 3)          # docstring 结束
src = src[:first + 3] + "\n" + DOC_EN + "\n" + src[second:]

# ── CONFIG②-b dialog 弹窗整段替换（参考项目示例）──────────────
DIALOG_SWAP_CN = "请执行全程唯一一次换台：\\r\\n【取出丢弃】Pos1-Pos4、Pos6-Pos8 吸头盒7盒（Pos5 八头盒保留原位勿动）；Pos12 捕获废板、Pos13 磁珠废板、Pos14 一链Mix废板、Pos16 二链Mix废板、Pos19 Adapter废板、Pos20 LigMix废板、Pos17 Binding 板、Pos18 Wash 板。\\r\\n【保留】Pos5 八头吸头盒（尚有余列）；Pos11 反应板（连接产物，勿动）；Pos21 建库试剂板；Pos22 NF Water 板；Pos23 废液板。\\r\\n【放入】吸头7盒：Pos1-Pos4、Pos6-Pos8；深孔板：Pos12 80%乙醇、Pos14 分选2板、Pos16 PCR纯化磁珠板、Pos17 纯化1板、Pos18 分选1板；PCR板：Pos13 文库收集板（空置）、Pos15 PCR反应板（扩增引物已预装6μL/孔）。\\r\\n确认无误后关闭门窗，点击【继续】。"
DIALOG_SWAP_EN = ("Please perform the ONLY deck swap of the run:\\r\\n"
 "[REMOVE & DISCARD] Tip boxes x7: Pos 1-4, Pos 6-8 (KEEP the Pos 5 8-channel box in place); "
 "Pos 12 capture waste, Pos 13 bead waste, Pos 14 1st-strand Mix waste, Pos 16 2nd-strand Mix waste, "
 "Pos 19 Adapter waste, Pos 20 LigMix waste, Pos 17 Binding plate, Pos 18 Wash plate.\\r\\n"
 "[KEEP] Pos 5 8-channel tip box (columns remaining); Pos 11 reaction plate (ligation product, DO NOT MOVE); "
 "Pos 21 reagent plate; Pos 22 NF Water plate; Pos 23 waste plate.\\r\\n"
 "[LOAD] Tips x7: Pos 1-4, Pos 6-8; Deep-well plates: Pos 12 80% ethanol, Pos 14 size-select-2, "
 "Pos 16 PCR-purif beads, Pos 17 purification-1, Pos 18 size-select-1; PCR plates: Pos 13 library collection (empty), "
 "Pos 15 PCR reaction plate (primers preloaded 6 uL/well).\\r\\n"
 "Close the doors and press [Continue].")
DIALOG_END_CN = "实验已完成，请取出POS13的PCR文库封膜后置于-20℃进行保存，并清理台面（含Pos15/Pos16/Pos17/Pos18废板与Pos23废液板）。"
DIALOG_END_EN = ("Run complete. Remove the PCR library plate at POS13, seal it and store at -20 C. "
 "Clean the deck (waste plates at Pos 15/16/17/18 and waste plate at Pos 23).")
src = src.replace(DIALOG_SWAP_CN, DIALOG_SWAP_EN)
src = src.replace(DIALOG_END_CN, DIALOG_END_EN)

# ── CONFIG②-c 台面 feature 字段 + report 阶段名 + 分段注释短语映射（参考项目示例）──
PHRASES = [
    # first_feature / SWAP1_POS 描述字段
    ("去上清专用", "Supernatant removal"),
    ("NF Water 加水", "NF Water"),
    ("8头单列·全程12列", "8-ch · 12 cols total"),
    ("mRNA取样+混匀/一链转", "mRNA transfer / 1st-strand"),
    ("二链转板(新盒)", "2nd-strand transfer (new)"),
    ("连接组装(新盒)", "Ligation assembly (new)"),
    ("mRNA收集→反应板", "mRNA collect -> reaction"),
    ("一链Mix分装板", "1st-strand Mix aliquot plate"),
    ("二链Mix分装板", "2nd-strand Mix aliquot plate"),
    ("Adapter分装板", "Adapter aliquot plate"),
    ("LigMix分装板", "LigMix aliquot plate"),
    ("建库试剂", "library reagents"),
    ("12列装液·6℃", "12 cols loaded · 6 C"),
    ("230μL/孔·跨全程", "230 uL/well · whole run"),
    ("230μL/孔·跨程", "230 uL/well · whole run"),
    ("纯化1主链", "Purif-1 main line"),
    ("80%乙醇加样", "80% EtOH loading"),
    ("洗脱/产物转移", "Elution / product transfer"),
    ("分选废液", "Size-select waste"),
    ("高板位·保留余列", "High slot · keep remaining cols"),
    ("PCR主链", "PCR main line"),
    ("PCR纯化废液", "PCR-purif waste"),
    ("分选2洗脱加水", "SS-2 elution water"),
    ("连接产物", "Ligation product"),
    ("反应板·勿动", "reaction · do not move"),
    ("80%乙醇", "80% EtOH"),
    ("文库收集板·空置", "Library collection · empty"),
    ("分选2板", "Size-select-2 plate"),
    ("PCR反应板·引物已预装", "PCR plate · primers preloaded"),
    ("PCR纯化磁珠板", "PCR-purif beads plate"),
    ("纯化1板", "Purification-1 plate"),
    ("分选1板+废液承接", "Size-select-1 + waste"),
    ("磁力架(已恢复)", "MagRack (restored)"),
    ("振荡器(已恢复)", "Shaker (restored)"),
    ("第一废液", "Waste #1"),
    ("废料袋", "Waste bag"),
    ("50μL/孔", "50 uL/well"),
    ("10μL/孔", "10 uL/well"),
    ("6μL/孔", "6 uL/well"),
    ("110μL/孔", "110 uL/well"),
    ("330μL/孔", "330 uL/well"),
    ("1000μL/孔", "1000 uL/well"),
    # report phase
    ("oligo dT 磁珠准备", "oligo dT bead preparation"),
    ("oligo dT 磁珠捕获", "oligo dT capture"),
    ("RNA片段化", "RNA fragmentation"),
    ("反转录", "Reverse transcription"),
    ("二链合成", "Second-strand synthesis"),
    ("接头连接", "Adapter ligation"),
    ("磁珠分装", "Bead dispensing"),
    ("连接产物纯化", "Ligation-product purification"),
    ("双选", "Double size selection"),
    ("PCR反应", "PCR reaction"),
    ("PCR纯化", "PCR purification"),
    # report step
    ("1/7 磁珠预处理", "1/7 Bead conditioning"),
    ("2/7 poly(A)+RNA结合", "2/7 poly(A)+RNA binding"),
    ("3/7 清洗", "3/7 Wash"),
    ("4/7 洗脱", "4/7 Elution"),
    ("5/7 再结合", "5/7 Re-binding"),
    ("6/7 再清洗", "6/7 Re-wash"),
    ("7/7 终洗脱", "7/7 Final elution"),
    ("1/3分配打断试剂", "1/3 Dispense frag reagent"),
    ("2/3混匀打断反应", "2/3 Mix frag reaction"),
    ("(3/3)进行片段化反应", "3/3 Fragmentation incubation"),
    ("1/4配制反应液", "1/4 Prepare reaction mix"),
    ("2/4分装反应液", "2/4 Dispense reaction mix"),
    ("3/4混匀反应液", "3/4 Mix reaction"),
    ("3/4混匀反应体系", "3/4 Mix reaction system"),
    ("4/4 进行二链合成反应", "4/4 Second-strand synthesis"),
    ("1/3配制反应液", "1/3 Prepare reaction mix"),
    ("2/3混匀反应体系", "2/3 Mix reaction system"),
    ("3/3进行连接反应", "3/3 Ligation incubation"),
    ("预分装纯化磁珠", "Pre-dispense purification beads"),
    ("1/5 第一轮纯化", "1/5 Round-1 purification"),
    ("2/5 乙醇洗涤", "2/5 Ethanol wash"),
    ("3/5 DNA洗脱", "3/5 DNA elution"),
    ("1/3 第一轮片选", "1/3 Round-1 selection"),
    ("2/3 第二轮片选", "2/3 Round-2 selection"),
    ("3/3 去废液·乙醇洗涤·洗脱", "3/3 Remove waste · wash · elute"),
    ("1/3 配制PCR体系", "1/3 Prepare PCR mix"),
    ("2/3 PCR反应", "2/3 PCR amplification"),
    ("1/4 DNA与磁珠结合", "1/4 DNA-bead binding"),
    ("2/4 移除废液", "2/4 Remove supernatant"),
    ("3/4 乙醇洗涤", "3/4 Ethanol wash"),
    ("4/4 洗脱并收取文库", "4/4 Elute & collect library"),
    # 主要行内/分段注释（可选翻译，便于英文环境维护）
    ("阶段一 · oligo(dT) 磁珠捕获（液体参数逐条照搬 V2.2 捕获）", "Stage 1 - oligo(dT) bead capture (params copied from V2.2 capture)"),
    ("阶段二 · 建库酶连段（分装板+96头转板，参数照搬 V2.2）", "Stage 2 - Library enzymatic stage (aliquot plates + 96-ch transfer, params from V2.2)"),
    ("衔接 · 单板化：mRNA 板进驻 PCR 位变反应板；捕获废板泊 Pos12", "Transition - single-plate: mRNA plate moves to PCR slot as reaction plate; capture waste parked at Pos12"),
    ("阶段四 · PCR 扩增（引物预装 PCR 反应板）+ PCR 纯化 + 文库收取", "Stage 4 - PCR amplification (preloaded primer plate) + PCR purification + library collection"),
    ("阶段三 · 纯化段（液体参数照搬 V2.2；废液分流见上）", "Stage 3 - Purification (params from V2.2; waste routing above)"),
    ("开机询问：PCR 扩增循环数（弹窗选择）", "Start-up prompt: PCR cycle number (dialog selection)"),
    ("开机即冷藏建库试剂板（与捕获启动并行；等效 V2.2 建库开场 temp_a(6)）", "Chill library reagent plate from start-up (parallel to capture start; equals V2.2 temp_a(6))"),
    ("不要修改HEAD", "Do not modify the HEAD section"),
    ("初始台面（7 字段：板位, 耗材, 功能描述, 特性描述, 有盖板, 需更换, 标记）", "Initial deck (7 fields: slot, labware, name, feature, covered, replace, marker)"),
    ("标记合法集合：'PCR' / 'MagRack' / 'Shaker' / 'Temp_Module'", "Valid markers: 'PCR' / 'MagRack' / 'Shaker' / 'Temp_Module'"),
    ("POS19/20 分装板：酶连段只作放板用，换台①后恢复磁架/振荡功能", "POS19/20 aliquot plates: plain plate slots in enzymatic stage; MagRack/Shaker duty after deck swap"),
    ("pos and kit type mapping table —— 初始台面（开机一次摆满）", "pos and kit type mapping table - initial deck (full load at start-up)"),
    ("three write methods:empty-None; kit-\"kit\"; cannot grasp/loose-\"useless\"; shake-([\"kit\",\"shake\"])", "three write methods: empty-None; kit-\"kit\"; cannot grasp/loose-\"useless\"; shake-([\"kit\",\"shake\"])"),
    ("磁珠预分装：纯化1→Pos17  分选1→Pos18  分选2→Pos14", "Bead pre-dispense: purif-1 -> Pos17, size-select-1 -> Pos18, size-select-2 -> Pos14"),
    ("连接产物纯化（0.5×）", "Ligation-product purification (0.5x)"),
    ("双片段选择", "Double size selection"),
    ("片段化：Frag 直打反应板（V2.2 本就直加，无需分装板）", "Fragmentation: Frag dispensed directly (V2.2 direct-add, no aliquot plate)"),
    ("打断PCR期间并行：配制一链 mix 并分装到 POS14（一链Mix分装板）", "Parallel during frag PCR: prepare 1st-strand mix and dispense to POS14"),
    ("引物已预装在 Pos15，直接转 DNA 并混匀", "Primers preloaded at Pos15; transfer DNA directly and mix"),
    ("控制软件spredo无temp_sleep_a(官方语料变体)，等价API为temp_sleep；同理log()亦未验证，勿启用", "This spredo build has no temp_sleep_a (corpus variant); equivalent is temp_sleep; log() unverified too - keep disabled"),
    ("模拟模式可能无此函数，注释掉", "may not exist in simulation mode - disabled"),
]
# 长串优先替换，避免短词组先命中污染长串（如"二链合成"吃掉"4/4 进行二链合成反应"）
for cn, en in sorted(PHRASES, key=lambda x: -len(x[0])):
    src = src.replace(cn, en)

open(EN, "w", encoding="utf-8").write(src)

# ── 4. AST 等价验证：字符串全置空后语法树必须一致 ────────────
def skeleton(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.dump(tree)

if skeleton(CN) == skeleton(EN):
    print("✓ AST 等价验证通过：英文版与中文版除字符串外零差异")
else:
    print("✗ AST 不一致！"); sys.exit(1)

leftover = [l for l in src.splitlines() if re.search(r"[一-鿿]", l) and not l.strip().startswith("#")]
print(f"剩余含中文的非注释行: {len(leftover)}")
for l in leftover[:10]: print("  ", l.strip()[:80])
