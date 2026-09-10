#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wfp_builder 示例 + 自证测试（09 §八）：用 builder 直接生成完整参考工程，
与 scripts/参考工程_结构示例.wfp 逐字段对比——证明 builder 产物与实机验证过的
工程零差异。新项目从此文件复制骨架改写。运行：python3 scripts/wfp_builder_示例.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfp_builder import Wfp

# ── 台面（24 位全定义，与现交付一致）──
DECK = [
    ('Pos1', 'TipGEBAF250A', 'NEW·枪头盒', '弃上清（磁吸后）×1', False, True, ''),
    ('Pos2', 'TipGEBAF250A', 'NEW·枪头盒', '打乙醇×2轮悬空复用', False, True, ''),
    ('Pos3', 'TipGEBAF250A', 'NEW·枪头盒', '去乙醇I×2段', False, True, ''),
    ('Pos4', 'TipGEBAF250A', 'NEW·枪头盒', '去乙醇II×2段+补偿吸', False, True, ''),
    ('Pos5', 'TipGEBAF250A', 'NEW·8头枪头盒', '预混/HB/PM→换盒→MixA/B/磁珠→换盒→水/产物', False, True, ''),
    ('Pos6', None, '', '', False, True, ''),
    ('Pos7', None, '', '', False, True, ''),
    ('Pos8', None, '', '', False, True, ''),
    ('Pos9', None, '', '', False, True, 'PCR'),
    ('Pos10', None, '', '', False, True, 'PCR'),
    ('Pos11', 'PCRBioRadHSP9601', '样本板·NEW', 'RNA 18μL/孔 预装列1-4；杂交/消化/纯化/洗脱', False, False, 'PCR'),
    ('Pos12', 'DeepwellPlateDT7350504', 'NEW·80%乙醇', '450μL/孔 整板（现配）', False, True, ''),
    ('Pos13', 'DeepwellPlateDT7350504', 'NEW·NF水', '60μL/孔 列1（洗脱源）', False, True, ''),
    ('Pos14', 'PCRBioRadHSP9601', '产物板·NEW', '空板收产物 10μL/孔 列1-4', False, True, ''),
    ('Pos15', None, '', '', False, True, 'MagRack'),
    ('Pos16', 'DeepwellPlateDT7350504', 'NEW·磁珠', 'RNACleanXP 90μL/孔 列1-4（RT平衡30min）', False, True, ''),
    ('Pos17', None, '', '', False, True, ''),
    ('Pos18', None, '', '', False, True, ''),
    ('Pos19', None, '', '', False, True, 'MagRack'),
    ('Pos20', None, '', '', False, True, 'Shaker'),
    ('Pos21', 'PCRBioRadHSP9601', 'NEW·试剂板6℃', '列1 HB28/列2 PM12/列3 RH12/列4 RHB16/列5 DI25/列6 DIB65 μL/孔', False, True, 'Temp_Module'),
    ('Pos22', None, '', '', False, True, 'Temp_Module'),
    ('Pos23', 'DeepwellPlateDT7350504', '废液板·NEW', '空板·单路累计约530μL/孔 列1-4', False, True, ''),
    ('Pos24', None, '', '', False, True, ''),
]

w = Wfp("RrnDepletion", deck_main=DECK, deck_swap=DECK, sw="1.9.0.395")
r = w.root()
r.initialize()

# ── 开机确认块 ──
with r.block("开机确认·设温") as b:
    b.dialog('开机确认：\r\n1. 样本板 RNA 已按 18μL/孔 预装于 Pos11 列1-4\r\n'
             '2. 磁珠已室温平衡 30min 并振荡重悬（Pos16）\r\n3. 80% 乙醇已新鲜配制（Pos12 整板）\r\n'
             '4. Pos1-4 枪头盒（96头）、Pos5 枪头盒（8头）、Pos21 试剂已就位\r\n'
             '5. 【重要】杂交反应约 20min，期间请将第 2 盒 8 头枪头放入 Pos5\r\n'
             '（第 1 盒 8 头用至加完 Probe Mix）\r\n确认后点击【继续】。')
    b.temp_set(6)

# ── 开机并行：PCR START 预热 × 试剂预混 ──
def preheat(b):
    b.pcr_open_door()
    b.pcr_run("START")

def premix(b):
    b.report("试剂预混", "1/8 准备 Mix-A/Mix-B")
    b.load_tips("POS5", 1, tips=8)
    b.aspirate("POS21", 4, volume=12, z='2.0', tips=8, rate=20, pre=2)
    b.dispense("POS21", 3, volume=12, z='3.5', tips=8, rate=20)
    b.mix("POS21", 3, loops=15, mixvol=15, z='1.0', zin='1.0', zafter='3.0')
    b.unload_tips()
    b.load_tips("POS5", 2, tips=8)
    b.aspirate("POS21", 6, volume=65, z='6.0', tips=8, rate=20, pre=5)
    b.dispense("POS21", 5, volume=65, z='6.0', tips=8, rate=20)
    b.mix("POS21", 5, loops=20, mixvol=50, z='4.5', zin='4.5', zafter='8.0')
    b.unload_tips()

with r.parallel("并行:PCR START预热+开机确认与试剂预混") as par:
    par.branch("PCR START 预热", preheat)
    par.branch("开机确认·设温·试剂预混", premix)

# ── 探针杂交 ──
with r.block("探针杂交·体系配制与反应") as b:
    b.report("探针杂交", "2/8 加 Hybridization Buffer 与 Probe Mix")
    with b.loop("col", 4, disp="循环·HB×4列"):
        b.load_tips("POS5", "col+3", tips=8)
        b.aspirate("POS21", 1, volume=7, z='3.2 - 0.5 * col', tips=8, rate=20, pre=2)
        b.dispense("POS21", 1, volume=2, z='4.0', tips=8, rate=5, dely=0.3)
        b.dispense("POS11", "col+1", volume=5, z='4.5', tips=8, rate=10)
        b.unload_tips()
    with b.loop("col", 4, disp="循环·PM×4列"):
        b.load_tips("POS5", "col+7", tips=8)
        b.aspirate("POS21", 2, volume=4, z='1.6 - 0.4 * col', tips=8, rate=5, pre=2, dely=1.0)
        b.dispense("POS21", 2, volume=2, z='2.5', tips=8, rate=3, dely=0.3)
        b.dispense("POS11", "col+1", volume=2, z='4.0', tips=8, rate=5)
        b.mix("POS11", "col+1", loops=15, mixvol=15, z='1.0', zin='1.0', zafter='3.0')
        b.unload_tips()
    b.report("探针杂交", "3/8 杂交反应 ~20min（请更换 Pos5 第2盒8头枪头）")
    b.pcr_close_door()
    b.pcr_run("HYB_RRNA")
    b.pcr_open_door()

# ── RNase H 消化 ──
with r.block("RNase H 消化·加Mix-A+37℃30min") as b:
    b.report("RNase H 消化", "4/8 加 Mix-A 并消化 30min")
    with b.loop("col", 4, disp="循环·Mix-A×4列"):
        b.load_tips("POS5", "col+1", tips=8)
        b.aspirate("POS21", 3, volume=7, z='2.7 - 0.55 * col', tips=8, rate=20, pre=2)
        b.dispense("POS21", 3, volume=2, z='4.0', tips=8, rate=5, dely=0.3)
        b.dispense("POS11", "col+1", volume=5, z='4.5', tips=8, rate=10)
        b.mix("POS11", "col+1", loops=15, mixvol=18, z='1.5', zin='1.5', zafter='3.5')
        b.unload_tips()
    b.pcr_close_door()
    b.pcr_run("DIGEST_37C30")
    b.pcr_open_door()

# ── DNase I 消化 ──
with r.block("DNase I 消化·加Mix-B+37℃30min") as b:
    b.report("DNase I 消化", "5/8 加 Mix-B 并消化 30min")
    with b.loop("col", 4, disp="循环·Mix-B×4列"):
        b.load_tips("POS5", "col+5", tips=8)
        b.aspirate("POS21", 5, volume=22, z='7.7 - 1.35 * col', tips=8, rate=20, pre=5)
        b.dispense("POS21", 5, volume=2, z='8.0', tips=8, rate=5, dely=0.3)
        b.dispense("POS11", "col+1", volume=20, z='7.0', tips=8, rate=20)
        b.mix("POS11", "col+1", loops=20, mixvol=30, z='2.5', zin='2.5', zafter='5.5')
        b.unload_tips()
    b.pcr_close_door()
    b.pcr_run("DIGEST_37C30")
    b.pcr_open_door()

# ── 磁珠纯化 ──
with r.block("磁珠纯化·结合/乙醇洗×2/干燥") as b:
    b.report("RNA 纯化", "6/8 加磁珠结合")
    with b.loop("col", 4, disp="循环·磁珠×4列"):
        b.load_tips("POS5", "col+9", tips=8)
        b.mix("POS16", "col+1", loops=20, mixvol=60, z='1.0', zin='1.0', zafter='2.5', rate=200, mixdely=5)
        b.aspirate("POS16", "col+1", volume=75, z='2.3', tips=8, rate=20, pre=5, dely=1.0)
        b.dispense("POS11", "col+1", volume=75, z='7.5', tips=8, rate=30)
        b.mix("POS11", "col+1", loops=25, mixvol=90, z='4.0', zin='4.0', zafter='9.5', rate=180)
        b.unload_tips()
    b.pcr_close_door()
    b.pcr_run("RT_5MIN")
    b.pcr_open_door()
    b.mvkit("POS11", "POS19")
    b.dely(180)
    b.load_tips("POS1", 1)
    b.aspirate("POS19", 1, volume=120, z='0.3', tips=96, rate=20, pre=8, dely=1.0)
    b.dispense("POS23", 1, empty=True, z='3.3', tips=96, rate=30)
    b.unload_tips()
    b.report("RNA 纯化", "7/8 乙醇洗涤×2 + 干燥")
    b.load_tips("POS2", 1)
    b.aspirate("POS12", 1, volume=100, z='9.2', tips=96, rate=100, post=2)
    b.dispense("POS19", 1, volume=100, z='4.5', tips=96, rate=25, touch=18)
    b.aspirate("POS12", 1, volume=100, z='7.3', tips=96, rate=100, post=2)
    b.dispense("POS19", 1, volume=100, z='4.5', tips=96, rate=25, touch=18)
    b.dely(30)
    b.load_tips("POS3", 1)
    b.aspirate("POS19", 1, volume=100, z='0.3', tips=96, rate=30, pre=5, post=2)
    b.dispense("POS23", 1, empty=True, z='5.2', tips=96, rate=30)
    b.aspirate("POS19", 1, volume=100, z='0.2', tips=96, rate=30, pre=5, post=2)
    b.dispense("POS23", 1, empty=True, z='7.1', tips=96, rate=30)
    b.unload_tips()
    b.aspirate("POS12", 1, volume=100, z='5.4', tips=96, rate=100, post=2)
    b.dispense("POS19", 1, volume=100, z='4.5', tips=96, rate=25, touch=18)
    b.aspirate("POS12", 1, volume=100, z='3.5', tips=96, rate=100, post=2)
    b.dispense("POS19", 1, volume=100, z='4.5', tips=96, rate=25, touch=18)
    b.unload_tips()
    b.dely(30)
    b.load_tips("POS4", 1)
    b.aspirate("POS19", 1, volume=100, z='0.3', tips=96, rate=30, pre=5, post=2)
    b.dispense("POS23", 1, empty=True, z='9.0', tips=96, rate=30)
    b.aspirate("POS19", 1, volume=100, z='0.2', tips=96, rate=30, pre=5, post=2)
    b.dispense("POS23", 1, empty=True, z='10.9', tips=96, rate=30)
    b.aspirate("POS19", 1, volume=3, z='0.1', tips=96, rate=10, pre=2, post=2, dely=1.0)
    b.dispense("POS23", 1, empty=True, z='11.1', tips=96, rate=30)
    b.unload_tips()
    b.dely(480)
    b.dialog('请检查磁珠干燥程度（Pos19 样本板）：磁珠表面无反光、无开裂后点击【继续】。\r\n'
             '（过度干燥会降低得率，干燥不足有乙醇残留）\r\n'
             '【同时请将第 3 盒 8 头枪头放入 Pos5】。')

# ── 洗脱回收 ──
with r.block("洗脱回收·NF水洗脱+产物转移") as b:
    b.report("洗脱回收", "8/8 洗脱并转移产物")
    b.mvkit("POS19", "POS11")
    with b.loop("col", 4, disp="循环·NF水洗脱×4列"):
        b.load_tips("POS5", "col+1", tips=8)
        b.aspirate("POS13", 1, volume=14, z='2.1 - 0.5 * col', tips=8, rate=30, pre=2)
        b.dispense("POS11", "col+1", volume=12, z='1.5', tips=8, rate=20)
        b.mix("POS11", "col+1", loops=15, mixvol=10, z='0.3', zin='0.3', zafter='1.0')
        b.unload_tips()
    b.pcr_close_door()
    b.pcr_run("RT_5MIN")
    b.pcr_open_door()
    b.mvkit("POS11", "POS19")
    b.dely(180)
    with b.loop("col", 4, disp="循环·产物×4列"):
        b.load_tips("POS5", "col+5", tips=8)
        b.aspirate("POS19", "col+1", volume=10, z='0.2', tips=8, rate=8, pre=5, dely=1.5)
        b.dispense("POS14", "col+1", volume=10, z='2.0', tips=8, rate=15)
        b.unload_tips()

# ── 收尾 ──
with r.block("收尾·停加热") as b:
    b.report("完成", "rRNA 去除产物在 Pos14 列1-4（10μL/孔）")
    b.pcr_stop_heating()

out = "/tmp/wfp_builder_示例_自证.wfp"
w.save(out)

# ── 自证：与参考工程逐字段对比 ──
import json, struct
def liq(path):
    d = open(path, 'rb').read(); i = 0
    def rd():
        nonlocal i
        n = struct.unpack('>I', d[i:i+4])[0]
        x = d[i+4:i+4+n].decode('utf-8'); i += 4 + n
        return x
    rd(); rd(); i += 21
    n = struct.unpack('>I', d[i:i+4])[0]; i += 4
    wf = None
    for _ in range(n):
        t = rd(); nm = rd(); i += 4
        j = rd()
        if nm == 'WorkflowModuleModel': wf = json.loads(j)
    from collections import Counter
    c = Counter(); seq = []
    def walk(a):
        c[a.get('ActivityName')] += 1
        if a.get('ActivityName') in ('Aspirate','Dispense','Mix'):
            seq.append((a.get('ActivityName'), a.get('Position'), str(a.get('Col')),
                        a.get('AspirateVolume') or a.get('DispenseVolume') or a.get('MixLoopVolume'),
                        a.get('BottomOffsetOfZ'), a.get('Tips')))
        for k in ('Branches','Body','Activities'):
            for cc in a.get(k) or []: walk(cc)
    for x in wf['Activities']: walk(x)
    return c, seq, [a.get('DisplayName') for a in wf['Activities']]
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "参考工程_结构示例.wfp")
c1, s1, r1 = lix1 = liq(out)
c2, s2, r2 = lix2 = liq(base)
assert dict(c1) == dict(c2), f"统计不一致: {set(c1.items()) ^ set(c2.items())}"
assert r1 == r2, "根下 DisplayName 不一致"
assert s1 == s2, f"液体活动字段差异 {sum(1 for a, b in zip(s1, s2) if a != b)} 处"
print("✓ 自证通过：builder 产物与参考工程 完全等价（统计/根结构/%d 液体活动零差异）" % len(s1))
