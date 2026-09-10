#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wfp 后处理（模板）：对"生成器直出"的 wfp 做产线惯例对齐——
① 阶段 Block 分组（按 Report phase 边界切，对齐产线工程"根下极简"结构）
② 全活动语义 DisplayName（WDesigner 画布可读性核心）
③ Parallel 分支中文名
④ 版本串归一（--sw，默认与现场实机一致；等长字节替换，不动长度前缀）

方法论：references/09 §十一（产线惯例对齐 Reference-first）。
直改规范：本工具只处理"本目录刚生成的" wfp（09 §七：新生成文件直改
无需往返基线，但写出必须用同款记录流格式，4B 大端长度 + UTF-8）。

用法：先改 CONFIG①~⑤，再 python3 wfp后处理_模板.py <in.wfp> <out.wfp>
CONFIG 示例值全部为假名（HEBI/WashX 等），复用必须换成新项目真值——
去标签化红线：任何 CONFIG 里不得出现真实项目/公司名。
"""
import json, struct, sys

IN, OUT = sys.argv[1], sys.argv[2]

# ── CONFIG① 版本串归一（留空 = 不动）──
# 取"现场现役工程"类型串的版本号（S0 实证：低版本软件打不开高版本串文件；
# 395 文件在 398 软件上可开，反向不可）。等长数字串才可替换。
SW_FROM, SW_TO = "1.9.0.398", "1.9.0.395"

# ── CONFIG② 阶段 Block 命名（Report phase → Block DisplayName）──
BLOCK_NAME = {
    "预混": "试剂预混·MixP/MixQ",
    "杂交": "探针杂交·体系配制与反应",
    "消化1": "酶消化1·加Mix+37℃30min",
    "纯化": "磁珠纯化·结合/乙醇洗×2/干燥",
    "洗脱": "洗脱回收·洗脱+产物转移",
    "完成": "收尾·停加热",
}

# ── CONFIG③ 试剂映射：(板位, 列) → 试剂名；列 None = 该板位任意列 ──
REAGENT = {
    ("21", "1"): "BufferP", ("21", "2"): "EnzQ", ("21", "3"): "Mix-A",
    ("12", None): "80%乙醇", ("13", None): "NF水", ("16", None): "磁珠",
}

# ── CONFIG④ Loop 上下文（按脚本中 Loop 出现顺序 → 语义名）──
LOOP_CTX = ["BufferP", "EnzQ", "Mix-A", "Mix-B", "磁珠", "NF水洗脱", "产物"]

# ── CONFIG⑤ 并行分支与开机块名 ──
PARALLEL_NAME = "并行:PCR预热+开机准备"
BRANCH_NAMES = ["PCR 预热", "开机确认·预混"]
HEAD_BLOCK_FALLBACK = "开机确认·设温"     # Parallel 之前的"主流程"块名

# ════════════════ 引擎（通用，勿动） ════════════════

def read_records(path):
    d = open(path, 'rb').read()
    i = 0
    recs = []
    def rd():
        nonlocal i
        n = struct.unpack('>I', d[i:i+4])[0]
        s = d[i+4:i+4+n].decode('utf-8'); i += 4 + n
        return s
    recs.append(rd()); recs.append(rd())           # Release V1、工程名（字符串记录）
    recs.append(('RAW21', d[i:i+21])); i += 21     # 配置号'2'+时间戳16B，原样字节
    n_mod = struct.unpack('>I', d[i:i+4])[0]; i += 4
    recs.append(('MODCOUNT', n_mod))
    for _ in range(n_mod):
        t = rd(); nm = rd()
        ff = d[i:i+4]; i += 4
        j = rd()
        recs.append(('MOD', t, nm, ff, j))
    assert i == len(d), f'尾余 {len(d)-i}B（文件结构异常，禁止直改）'
    return recs

def write_records(path, recs):
    """⚠ 历史踩坑：字符串记录必须整串写出。曾误写 r[1]（字符索引），
    把 'Release V1' 写成 'e'——文件头损坏、WDesigner 报打不开。"""
    out = bytearray()
    def wr(s):
        b = s.encode('utf-8')
        out.extend(struct.pack('>I', len(b))); out.extend(b)
    for r in recs:
        if r[0] == 'RAW21':
            out.extend(r[1])
        elif r[0] == 'MODCOUNT':
            out.extend(struct.pack('>I', r[1]))
        elif r[0] == 'MOD':
            _, t, nm, ff, j = r
            wr(t); wr(nm); out.extend(ff); wr(j)
        else:  # 字符串记录：r 本身就是完整字符串
            wr(r if isinstance(r, str) else ''.join(r))
    open(path, 'wb').write(bytes(out))

def name_liq(a, ctx):
    t = a['ActivityName']; pos = str(a.get('Position', '')); col = str(a.get('Col', '1'))
    reagent = REAGENT.get((pos, col)) or REAGENT.get((pos, None)) or ''
    v = a.get('AspirateVolume') or a.get('DispenseVolume')
    if t == 'Aspirate':
        if pos == '19':  # 磁吸位：按体积档区分动作语义（换项目重写此段）
            vv = float(v or 0)
            if vv >= 100: return f'磁吸去废液·{v}µL'
            if vv <= 5: return f'低量补偿吸·{v}µL'
            return f'磁吸回收·{v}µL'
        return f'试剂源吸取·{reagent or pos} {v}µL'
    if t == 'Dispense':
        if a.get('IsEmpty'):
            return '排空入废液' if pos == '23' else '排空并孔'
        if pos == '21' and float(v or 0) <= 2: return f'回打平衡·{v}µL'
        if pos == '11' and ctx: return f'加样·{ctx} {v}µL'
        return f'打液·{reagent or pos} {v}µL'
    if t == 'Mix':
        return (f'混匀{a.get("MixLoopVolume")}µL×{a.get("SubMixLoopCounts")}'
                f'·Z{a.get("MixOffsetOfZInLoop")}↔{a.get("MixOffsetOfZAfterLoop")}')
    return None

def rename(a, ctx='主流程', loop_i=None):
    t = a.get('ActivityName')
    if t in ('Aspirate', 'Dispense', 'Mix'):
        nm = name_liq(a, ctx)
        if nm: a['DisplayName'] = nm
    elif t == 'Loop':
        ctx2 = LOOP_CTX[loop_i] if loop_i is not None and loop_i < len(LOOP_CTX) else ctx
        a['DisplayName'] = f'循环·{ctx2}×{a.get("LoopCount")}列'
        for c in a.get('Body') or []: rename(c, ctx2, None)
    elif t == 'Delay':
        a['DisplayName'] = f'静置·{a.get("Duration")}s'
    elif t == 'MvKit':
        a['DisplayName'] = f'移板 {a.get("Source")}→{a.get("Destination")}'
    elif t == 'PcrRun':
        a['DisplayName'] = f'PCR程序·{(a.get("Method") or {}).get("Text", "")}'
    elif t == 'PcrStop':
        a['DisplayName'] = 'PCR停止加热'
    elif t == 'LoadTips':
        a['DisplayName'] = f'取枪头·P{a.get("Position")}' + ('（8头）' if str(a.get('Tips')) == '8' else '')
    elif t == 'UnloadTips':
        a['DisplayName'] = '丢枪头'
    elif t == 'Report':
        a['DisplayName'] = f'进度·{a.get("Phase","")} {a.get("Step","")}'
    elif t == 'Dialog':
        a['DisplayName'] = '弹窗·人工确认'
    elif t == 'TempSet':
        a['DisplayName'] = f'温控模块 {a.get("Target")}℃'
    elif t == 'Block':
        a.setdefault('Comment', None)
        for c in a.get('Activities') or []: rename(c, ctx, loop_i)
    # Initialize/PcrOpenDoor/PcrCloseDoor/GlobalSequence 保留默认名

def main():
    recs = read_records(IN)
    for idx, r in enumerate(recs):
        if r[0] != 'MOD' or r[2] != 'WorkflowModuleModel':
            continue
        wf = json.loads(r[4])
        root = wf['Activities']
        # ① 阶段 Block 分组：最后一个 Parallel 之后的平铺活动按 Report(phase) 切块
        cut = 0
        for i, a in enumerate(root):
            if a.get('ActivityName') == 'Parallel':
                cut = i + 1
        head, tail = root[:cut], root[cut:]
        blocks, cur, cur_phase = [], [], None
        for a in tail:
            if a.get('ActivityName') == 'Report':
                ph = a.get('Phase', '')
                if ph != cur_phase and cur:
                    blocks.append((cur_phase, cur)); cur = []
                cur_phase = ph
            cur.append(a)
        if cur: blocks.append((cur_phase, cur))
        grouped = []
        for ph, acts in blocks:
            grouped.append({
                'ActivityType': f'Common.WorkflowDesigner.Spx.Core.Block, Common.WorkflowDesigner.Spx, Version={SW_TO or "1.9.0.395"}, Culture=neutral, PublicKeyToken=null',
                'ActivityName': 'Block', 'DisplayName': BLOCK_NAME.get(ph or '', f'阶段·{ph}'),
                'IsEnabled': True, 'Comment': None, 'Activities': acts})
        wf['Activities'] = head + grouped
        # ② 语义命名（Loop 序号跨块全局计数）
        loop_counter = [0]
        def rename_root(a):
            if a.get('ActivityName') == 'Loop':
                rename(a, '主流程', loop_counter[0]); loop_counter[0] += 1
            elif a.get('ActivityName') == 'Block':
                for c in a.get('Activities') or []: rename_root(c)
            elif a.get('ActivityName') == 'Parallel':
                a['DisplayName'] = PARALLEL_NAME
                brs = a.get('Branches') or []
                for bi, br in enumerate(brs):
                    if bi < len(BRANCH_NAMES): br['DisplayName'] = BRANCH_NAMES[bi]
                    for c in br.get('Activities') or []: rename(c, '并行分支')
            else:
                rename(a)
        for a in wf['Activities']:
            rename_root(a)
        # Parallel 之前的"主流程"回退块名
        for a in wf['Activities']:
            if a.get('ActivityName') == 'Block' and a.get('DisplayName') == '主流程':
                a['DisplayName'] = HEAD_BLOCK_FALLBACK
                a.setdefault('Comment', None)
        recs[idx] = ('MOD', r[1], r[2], r[3], json.dumps(wf, ensure_ascii=False, separators=(',', ':')))
    # ③ 版本串归一（写出前对全部记录做等长替换；不动 RAW21 字节段）
    if SW_FROM and SW_TO and SW_FROM != SW_TO:
        assert len(SW_FROM) == len(SW_TO), '版本串必须等长才能字节替换'
        norm = []
        for r in recs:
            if r[0] == 'MOD':
                t, nm, ff, j = r[1], r[2], r[3], r[4]
                t = t.replace(SW_FROM, SW_TO); j = j.replace(SW_FROM, SW_TO)
                norm.append(('MOD', t, nm, ff, j))
            elif r[0] == 'RAW21':
                norm.append(r)  # 头部字节段原样
            else:
                norm.append(r.replace(SW_FROM, SW_TO) if isinstance(r, str) else r)
        recs = norm
    write_records(OUT, recs)
    print(f'post 完成 → {OUT}（版本串 {SW_FROM or "未改"}→{SW_TO or "未改"}，Block 分组+语义命名）')

if __name__ == '__main__':
    main()
