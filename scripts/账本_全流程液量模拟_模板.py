#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全流程液量账本（模板）：模拟 wfp 活动树执行，逐孔累计体积与液体身份，
输出每个液体操作时刻的液面。方法论：references/13 §十。

五类审计：① 排空贴液面（排空 Z=打完后液面−0.4，13 §七.4）② 吸液没入深度
（Z=0 仅磁吸类，13 铁律 4）③ 混匀双约束（13 §三）④ 反应体系终态 vs 说明书
（净积累，13 §八）⑤ 试剂装载五问：装载/每孔用量/剩余/说明书量/mix 配比（13 §六）。

液面模型：实测液面对照表（references/11 §一）分段线性插值
（数据固化 references/11 §一；禁止自行几何推导——用户指令 2026-09-06）。

模板约定：先改 CONFIG 再运行。示例值来自 RNA 一步法项目 V2.9（2026-09），
复用必须全部换成新项目值。本模板**只读不写** wfp；要改写 wfp 先走
references/09 §七往返字节级一致验证。依赖：仅标准库。
"""
import json, struct

# ════════════════ CONFIG（全部按新项目替换） ════════════════

# ① 程序清单：(wfp 路径, 展示名——build_state/on_dialog 按它分发)
WFPS = [
    ("/path/to/oligodT capture.wfp", "捕获"),
    ("/path/to/Library Prep.wfp", "建库"),
]

ALL = range(1, 13)  # 12 列×8 头；不满 96 样本时按实际列改

# ② 初始台面装载（每段程序开始前的物理真实状态：板型别/每井µL/液体身份种子）
def build_state(name):
    s = {}
    if name == "捕获":
        s['11'] = Plate('pcr', '样本板'); s['11'].fill(ALL, 50)
        for c in ALL: s['11'].tags[c] = 'totalRNA样本'
        s['12'] = Plate('pcr', '收集板(空)')
        s['13'] = Plate('pcr', 'oligo珠板'); s['13'].fill(ALL, 10)
        for c in ALL: s['13'].floor[c] = 5.5; s['13'].tags[c] = 'oligo珠保存液'
        s['17'] = Plate('deep', 'BindingBuffer'); s['17'].fill(ALL, 120)
        s['18'] = Plate('deep', 'WashBuffer'); s['18'].fill(ALL, 340)
        s['22'] = Plate('deep', 'NF水'); s['22'].fill(ALL, 85)
        s['23'] = Plate('deep', '废液板')
        for pos, tag in (('17', 'BindingBuffer'), ('18', 'WashBuffer'), ('22', 'NF水')):
            for c in ALL: s[pos].tags[c] = tag
    else:  # 建库（示例起点=捕获实收 17µL/孔；空板只给型别+名）
        s['11'] = Plate('pcr', '反应板(空)')
        s['12'] = Plate('pcr', 'mRNA板'); s['12'].fill(ALL, 17)
        for c in ALL: s['12'].tags[c] = 'mRNA'
        for pos, nm in (('13', '二链Mix中转'), ('14', 'Adapter中转'),
                        ('15', '连接Mix中转'), ('16', '一链Mix中转')):
            s[pos] = Plate('pcr', nm + '(空)')
        for pos, nm in (('17', '磁珠板·纯化1'), ('18', '磁珠板·片选1'), ('22', '磁珠板·片选2')):
            s[pos] = Plate('deep', nm + '(空)')
        s['21'] = Plate('deep', '试剂板')  # 逐列不同试剂：起点µL+身份
        C21 = {1: ('FragBuffer', 45), 2: ('一链Buffer', 120), 3: ('一链Enzyme井', 36),
               4: ('二链Buffer', 400), 5: ('二链Enzyme井', 80), 6: ('连接Buffer', 546),
               7: ('连接Enzyme井', 78), 8: ('Adapter', 85), 9: ('PCRmix', 320),
               10: ('磁珠源', 700), 11: ('磁珠源', 1000), 12: ('磁珠源', 630)}
        for col, (tag, v) in C21.items():
            s['21'].wells[col] = v; s['21'].tags[col] = tag
        s['23'] = Plate('deep', '废液板')
    return s

# ③ 台面重置钩子（示例：换入 NF水/引物/乙醇/PCR 板）
def on_update_deck(state, log):
    s = state
    s['12'] = Plate('deep', 'NF水'); s['12'].fill(ALL, 180)
    for c in ALL: s['12'].tags[c] = 'NF水'
    s['13'] = Plate('pcr', 'PCR引物板'); s['13'].fill(ALL, 6)
    for c in ALL: s['13'].tags[c] = 'PCR引物'
    s['14'] = Plate('deep', '80%乙醇整板'); s['14'].fill(ALL, 1000)
    for c in ALL: s['14'].tags[c] = '80%乙醇'
    s['15'] = Plate('pcr', 'PCR反应板(空)')
    s['16'] = Plate('deep', 'PCR纯化磁珠板(空)')

def on_dialog(msg, state, log):
    """弹窗触发的人工换板（示例：'废液'弹窗=换 P23 废液板+P13 承接板）。"""
    if '废液' in msg:
        state['23'] = Plate('deep', '废液板(新)')
        state['13'] = Plate('pcr', '新PCR板(文库承接)')

# ④ 珠悬液源井 {(板位, 列)}：吸入后 0.55×吸入量记为目标孔泥底（仅液面估算）
BEAD_SRC = {('21', 10), ('21', 11), ('21', 12)}

# ════════════════ 引擎（通用，勿动） ════════════════

# 实测表（references/11 §一，禁止几何推导）
DEEP_TABLE = [(10,1),(20,1.4),(30,1.7),(40,2),(50,2.4),(60,2.6),(70,2.7),(80,2.9),(90,3.1),
              (100,3.3),(150,4.3),(200,5.2),(250,6.2),(300,7.1),(350,8.1),(400,9),(450,10),
              (500,10.9),(600,12.8),(700,14.7),(800,16.6),(900,18.5),(1000,20.4)]
PCR_TABLE  = [(10,2),(20,3.3),(30,4.4),(40,5.2),(50,6),(60,6.7),(70,7.3),(80,7.9),(90,8.5),
              (100,9),(150,11.2)]

def _interp(v, table):
    if v <= 0: return 0.0
    if v <= table[0][0]:
        v0, h0 = table[0]; return v * h0 / v0
    for (v0, h0), (v1, h1) in zip(table, table[1:]):
        if v <= v1: return h0 + (v - v0) * (h1 - h0) / (v1 - v0)
    slope = (table[-1][1] - table[-2][1]) / (table[-1][0] - table[-2][0])
    v0, h0 = table[-1]; return h0 + (v - v0) * slope

def level(v, ptype):
    return _interp(v, PCR_TABLE if ptype == 'pcr' else DEEP_TABLE)

class Plate:
    def __init__(self, ptype, name):
        self.ptype = ptype; self.name = name
        self.wells = {}   # col -> µL/孔（真实账目）
        self.floor = {}   # col -> 磁珠泥底µL（仅液面估算）
        self.tags = {}    # col -> 液体身份（随板移动）
    def fill(self, cols, v):
        for c in cols: self.wells[c] = self.wells.get(c, 0) + v
    def sub(self, cols, v):
        """真实账目不钳制（可为负=吸及珠泥=携带）。返回是否携带。"""
        hit = False
        for c in cols:
            w0 = self.wells.get(c, 0)
            self.wells[c] = w0 - v
            if w0 - v < self.floor.get(c, 0): hit = True
        return hit
    def eff(self, c):
        return max(self.wells.get(c, 0), self.floor.get(c, 0))

def mtag(cur, new):
    """液体身份有序去重合并；重复注入同名液体不改变标签。"""
    if not cur: return new
    parts = cur.split('+')
    for p_ in new.split('+'):
        if p_ not in parts: parts.append(p_)
    return '+'.join(parts)

def parse(path):
    """wfp 解析器（格式见 references/09 §三/§六；只读）。板位缺失直接 KeyError
    = 装载定义漏板，属模板断言。"""
    d = open(path, 'rb').read()
    i = 0
    def rd_str():
        nonlocal i
        n = struct.unpack('>I', d[i:i+4])[0]
        s = d[i+4:i+4+n].decode('utf-8'); i += 4 + n
        return s
    release = rd_str(); proj = rd_str()
    i += 21
    n_modules = struct.unpack('>I', d[i:i+4])[0]; i += 4
    modules = []
    for _ in range(n_modules):
        type_name = rd_str(); mod_name = rd_str()
        ff = d[i:i+4]; i += 4
        modules.append({'type': type_name, 'name': mod_name, 'ff': ff.hex(), 'json': rd_str()})
    return {'release': release, 'proj': proj, 'n_modules': n_modules,
            'modules': modules, 'end': len(d) - i}

def ev(expr, env):
    return float(eval(str(expr), {'__builtins__': {}}, dict(env)))

def run(path, state, log, wf=None):
    if wf is None:
        p = parse(path)
        wf = json.loads([m for m in p['modules'] if m['name'] == 'WorkflowModuleModel'][0]['json'])
    tip = [0.0]; last_asp = [{}]; tip_liq = ['']
    def typ(a): return a['ActivityType'].split(',')[0].split('.')[-1]
    def cols_of(a, env):
        c = a.get('Col', '1')
        if isinstance(c, str) and any(op in c for op in '+-*'):
            return [int(round(ev(c, env)))]
        return [int(float(c))]
    def walk(a, env):
        if not isinstance(a, dict): return
        t = typ(a) if 'ActivityType' in a else None
        if t == 'Loop':
            var, n = a.get('VariableName'), int(float(a.get('LoopCount', '1')))
            for k in range(n):
                for c in a.get('Body') or []: walk(c, {**env, var: k})
            return
        if t in ('Block', 'Parallel', 'GlobalSequence'):
            for k in ('Branches', 'Activities', 'Body'):
                for c in a.get(k) or []: walk(c, env)
            return
        pos = str(a.get('Position', ''))
        if t == 'Aspirate':
            cols = cols_of(a, env); v = float(a.get('AspirateVolume', 0)); plate = state[pos]
            lv_before = level(plate.eff(cols[0]), plate.ptype)
            carried = plate.sub(ALL if int(a.get('Tips', 96)) == 96 else cols, v)
            log.append(dict(kind='A', pos=pos, col=a.get('Col'), vol=v, act=a,
                            z=str(a.get('BottomOffsetOfZ', '')), env=dict(env), carried=carried,
                            bead_src=(pos, cols[0]) in BEAD_SRC,
                            floor_carry=plate.floor.get(cols[0], 0) if carried else 0,
                            lv=round(lv_before, 2), ptype=plate.ptype,
                            well_v=round(plate.wells.get(cols[0], 0), 1),
                            tips=int(a.get('Tips', 96)), liq=plate.tags.get(cols[0])))
            tip[0] += v; tip_liq[0] = plate.tags.get(cols[0]) or tip_liq[0]; last_asp[0] = log[-1]
        elif t == 'Dispense':
            cols = cols_of(a, env); plate = state[pos]
            tips_all = int(a.get('Tips', 96)) == 96
            if a.get('IsEmpty'):
                dv = tip[0]
                plate.fill(ALL if tips_all else cols, dv)
                for c in cols:  # 珠源→泥底 0.55×；携带→泥底继承
                    if last_asp[0].get('bead_src'):
                        plate.floor[c] = max(plate.floor.get(c, 0), round(0.55 * last_asp[0]['vol'], 1))
                    elif last_asp[0].get('carried'):
                        plate.floor[c] = max(plate.floor.get(c, 0), last_asp[0].get('floor_carry', 0))
                for c in cols: plate.tags[c] = mtag(plate.tags.get(c), tip_liq[0] or '液体')
                log.append(dict(kind='E', pos=pos, col=a.get('Col'), vol=round(dv, 1), act=a,
                                z=str(a.get('BottomOffsetOfZ', '')),
                                lv=round(level(plate.eff(cols[0]), plate.ptype), 2),
                                ptype=plate.ptype, well_v=round(plate.wells.get(cols[0], 0), 1),
                                tips=int(a.get('Tips', 96)), env=dict(env),
                                liq=tip_liq[0] or '液体', tag=plate.tags.get(cols[0])))
                tip[0] = 0.0
            else:
                dv = float(a.get('DispenseVolume', 0))
                plate.fill(ALL if tips_all else cols, dv); tip[0] -= dv
                for c in cols: plate.tags[c] = mtag(plate.tags.get(c), tip_liq[0] or '液体')
                log.append(dict(kind='D', pos=pos, col=a.get('Col'), vol=dv, act=a,
                                z=str(a.get('BottomOffsetOfZ', '')),
                                lv=round(level(plate.eff(cols[0]), plate.ptype), 2),
                                ptype=plate.ptype, well_v=round(plate.wells.get(cols[0], 0), 1),
                                tips=int(a.get('Tips', 96))))
        elif t == 'MvKit':
            src, dst = str(a.get('Source')), str(a.get('Destination'))
            if src in state: state[dst] = state.pop(src)
            else: log.append(dict(kind='MV-ERR', pos=f'{src}->{dst}', detail='源位无板'))
        elif t == 'UpdateDeck':
            on_update_deck(state, log); log.append(dict(kind='DESK2', pos='', detail='换台重置'))
        elif t == 'Dialog':
            on_dialog(str(a.get('Message', '')), state, log)
            log.append(dict(kind='DIALOG', pos='', detail=str(a.get('Message', ''))[:40]))
        elif t == 'Mix':
            cols = cols_of(a, env); plate = state[pos]
            log.append(dict(kind='M', pos=pos, col=a.get('Col'), act=a,
                            lv=round(level(plate.eff(cols[0]), plate.ptype), 2),
                            well_v=round(plate.wells.get(cols[0], 0), 1), tag=plate.tags.get(cols[0]),
                            ptype=plate.ptype, mv=a.get('MixLoopVolume', ''), n=a.get('SubMixLoopCounts', ''),
                            zi=a.get('MixOffsetOfZInLoop', ''), za=a.get('MixOffsetOfZAfterLoop', ''),
                            z0=a.get('BottomOffsetOfZ', ''), ra=a.get('MixLoopAspirateRate', ''),
                            rd=a.get('MixLoopDispenseRate', ''), env=dict(env)))
        elif t == 'Report':
            log.append(dict(kind='R', phase=str(a.get('Phase', '')), step=str(a.get('Step', ''))))
        elif t in ('LoadTips', 'UnloadTips'):
            if tip[0] > 0.01:
                log.append(dict(kind='WARN', pos=pos,
                                detail=f'带液{tip[0]:.1f}µL{"取" if t == "LoadTips" else "丢"}头'))
            tip[0] = 0.0
    walk(wf, {})
    return state

if __name__ == '__main__':
    out = {}
    for path, name in WFPS:
        p = parse(path)
        assert p['end'] == 0, f'{path}: 尾部 {p["end"]}B 多余字节（文件损坏或格式更新）'
        wf = json.loads([m for m in p['modules'] if m['name'] == 'WorkflowModuleModel'][0]['json'])
        log = []
        st = run(path, build_state(name), log, wf=wf)
        out[name] = [{k: v for k, v in r.items() if k != 'act'} for r in log]
        print(f'=== {name} 账本（{len(log)} 条）===')
        for r in log:
            if r['kind'] in ('D', 'E'):
                print(f"  {r['kind']} P{r['pos']} +{r['vol']:<5} → 累计{r['well_v']:>7}µL "
                      f"液面{r['lv']:>5}mm [{r.get('tag') or r.get('liq', '')}]")
        print('  各板终态：')
        for pos in sorted(st, key=int):
            pl = st[pos]
            print(f"    P{pos:>2} {pl.ptype:4} {pl.name}: "
                  f"C1={round(pl.wells.get(1, 0), 1)} C12={round(pl.wells.get(12, 0), 1)}µL {pl.tags.get(1, '')}")
    json.dump(out, open('/tmp/ledger.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n明细已存 /tmp/ledger.json（每步 env/液面/身份——五类审计消费，13 §十）')
