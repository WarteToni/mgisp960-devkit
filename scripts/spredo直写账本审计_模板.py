# ══════════════════════════════════════════════════════════════════
# 【模板】spredo 直写账本审计器 —— mock spredo 直接执行脚本，零漂移
# 用法：改 CONFIG① 脚本路径与名称 ② 初始装载 build_state ③ 换台/弹窗钩子
#       ④ 珠源井集合 ⑤ 关键终态断言，python3 运行。
# 适用：spredo 直写交付项目（工作流 A），与 wfp 版账本模板二选一：
#       交付 .py → 用本工具（无 wfp 依赖）；交付 .wfp → 用 wfp 版模板。
# 方法论：references/13 §十（净积累/液体身份/五类审计），并扩展 Z 锚审计
#       （每条 aspirate 的没入深度 = 吸前液面 − Z，≥0.5mm）。
# 示例值来源：rRNA 去除+RNA 建库双段项目（2026-09，两段全绿验证），
# 复用必须全部换成新项目值。
# 依赖：仅标准库。审计输出：过抽/板冲突警告 + 关键终态断言 + 各板终态。
# ══════════════════════════════════════════════════════════════════
# -*- coding: utf-8 -*-
"""全流程液量账本审计器（13 §十）：mock spredo 直接执行脚本骨架，
逐孔累计体积+液体身份，输出五类审计。方法论同 scripts/账本_全流程液量模拟_模板，
但直接消费 spredo .py（本项目交付物），零漂移。

语义约定：
- 96 头操作（不写 Tips）= 整板 1:1（每通道吸/打 AspirateVolume/DispenseVolume）
- 8 头操作（Tips:8）= 每通道体积语义；源井消耗 = 8×体积；目标列 8 孔各 +体积
- 戳膜假吸（BottomOffsetOfZ==20）不计体积（13 §七.4b）
- 排空(empty) = 枪头内容物全部进目标（13 §八净积累）
- 孔地址 = f'{列}{行}'（如 '5A'）；板位键 = 'POS9' → '9'
"""
import json, sys

DEEP_TABLE = [(10,1),(20,1.4),(30,1.7),(40,2),(50,2.4),(60,2.6),(70,2.7),(80,2.9),(90,3.1),
              (100,3.3),(150,4.3),(200,5.2),(250,6.2),(300,7.1),(350,8.1),(400,9),(450,10),
              (500,10.9),(600,12.8),(700,14.7),(800,16.6),(900,18.5),(1000,20.4)]
PCR_TABLE  = [(10,2),(20,3.3),(30,4.4),(40,5.2),(50,6),(60,6.7),(70,7.3),(80,7.9),(90,8.5),
              (100,9),(150,11.2)]
ROWS = 'ABCDEFGH'
ALL_WELLS = [f'{c}{r}' for c in range(1, 13) for r in ROWS]

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

def mtag(cur, new):
    if not cur: return new
    parts = cur.split('+')
    for p in new.split('+'):
        if p not in parts: parts.append(p)
    return '+'.join(parts)

def poskey(pos):
    return str(pos).replace('POS', '').replace('Pos', '')

def wellkey(d):
    if 'Well' in d:
        return str(d['Well'])
    return f"{int(float(d['Col']))}{ROWS[int(float(d['Row'])) - 1]}"

class Plate:
    def __init__(self, ptype, name):
        self.ptype = ptype; self.name = name
        self.wells = {}; self.floor = {}; self.tags = {}
    def fill(self, keys, v):
        for k in keys: self.wells[k] = self.wells.get(k, 0) + v
    def eff(self, k):
        return max(self.wells.get(k, 0), self.floor.get(k, 0))

class Engine:
    def __init__(self, name, build_state, on_dialog, bead_src, checkpoints):
        self.name = name
        self.state = build_state()
        self.on_dialog = on_dialog
        self.bead_src = bead_src
        self.checkpoints = checkpoints
        self.log = []; self.warn = []
        self.tip = 0.0; self.tip96 = 0.0
        self.tip_liq = ''; self.tip96_liq = ''
        self.last8 = None; self.last96 = None
        self.tips_used = {}

    def plate(self, pos):
        k = poskey(pos)
        pl = self.state.get(k)
        if pl is None:
            self.warn.append(f'@{len(self.log)} P{k} 无板（装载定义漏板）')
            pl = self.state[k] = Plate('deep', f'P{k}临时')
        return pl

    def aspirate(self, d):
        pos = poskey(d['Module']); tips = int(d.get('Tips', 96)); v = float(d['AspirateVolume'])
        if float(d.get('BottomOffsetOfZ', 0)) == 20:   # 戳膜假吸
            return
        pl = self.plate(pos)
        if tips == 96:
            lv = level(pl.eff('1A') + v, pl.ptype)
            for k in ALL_WELLS:
                w0 = pl.wells.get(k, 0)
                pl.wells[k] = w0 - v
                if pl.wells[k] < pl.floor.get(k, 0) - 1e-9:
                    self.warn.append(f'@{len(self.log)} 过抽 P{pos} {k}: {w0:.1f}-{v}')
            self.tip96 = v; self.tip96_liq = pl.tags.get('1A', self.tip96_liq or '液')
            self.last96 = pos
            self.log.append(dict(kind='A', pos=pos, tips=96, vol=v, lv=round(lv, 2), z=float(d.get('BottomOffsetOfZ', 0))))
        else:
            wk = wellkey(d)
            w0 = pl.wells.get(wk, 0)
            pl.wells[wk] = w0 - 8 * v
            lv = level(pl.eff(wk) + 8 * v, pl.ptype)
            if pl.wells[wk] < pl.floor.get(wk, 0) - 1e-9:
                self.warn.append(f'@{len(self.log)} 过抽 P{pos} {wk}: {w0:.1f}-{8 * v} (8×{v})')
            self.tip = 8 * v; self.tip_liq = pl.tags.get(wk, self.tip_liq or '液')
            self.last8 = (pos, wk)
            self.log.append(dict(kind='A', pos=pos, tips=8, vol=v, lv=round(lv, 2), z=float(d.get('BottomOffsetOfZ', 0))))

    def dispense(self, d):
        pos = poskey(d['Module']); tips = int(d.get('Tips', 96)); v = float(d['DispenseVolume'])
        pl = self.plate(pos)
        if tips == 96:
            dv = min(v, self.tip96)
            pl.fill(ALL_WELLS, dv)
            for k in ALL_WELLS:
                pl.tags[k] = mtag(pl.tags.get(k), self.tip96_liq)
            self.tip96 -= dv
            self.log.append(dict(kind='D', pos=pos, vol=round(dv, 1),
                                 lv=round(level(pl.eff('1A'), pl.ptype), 2),
                                 well=round(pl.wells.get('1A', 0), 1)))
        else:
            wk = wellkey(d)
            keys = [wk] if 'Well' in d else [f"{wk[:-1]}{r}" for r in ROWS]
            dv = min(v, self.tip / len(keys))
            pl.fill(keys, dv)
            for k in keys:
                pl.tags[k] = mtag(pl.tags.get(k), self.tip_liq)
            self.tip -= dv * len(keys)
            self.log.append(dict(kind='D', pos=pos, vol=round(dv, 1),
                                 lv=round(level(pl.eff(keys[0]), pl.ptype), 2),
                                 well=round(pl.wells.get(keys[0], 0), 1)))

    def empty(self, d):
        pos = poskey(d['Module']); tips = int(d.get('Tips', 96))
        pl = self.plate(pos)
        if tips == 96:
            dv = self.tip96; src = self.last96
            pl.fill(ALL_WELLS, dv)
            for k in ALL_WELLS:
                pl.tags[k] = mtag(pl.tags.get(k), self.tip96_liq)
                if src and (src, k) in self.bead_src and dv > 0:
                    pl.floor[k] = max(pl.floor.get(k, 0), 0.55 * dv)
            self.log.append(dict(kind='E', pos=pos, vol=round(dv, 1),
                                 lv=round(level(pl.eff('1A'), pl.ptype), 2),
                                 well=round(pl.wells.get('1A', 0), 1)))
            self.tip96 = 0.0; self.last96 = None
        else:
            wk = wellkey(d)
            keys = [wk] if 'Well' in d else [f"{wk[:-1]}{r}" for r in ROWS]
            dv = self.tip / len(keys); src = self.last8
            pl.fill(keys, dv)
            for k in keys:
                pl.tags[k] = mtag(pl.tags.get(k), self.tip_liq)
                if src and (src[0], src[1]) in self.bead_src and dv > 0:
                    pl.floor[k] = max(pl.floor.get(k, 0), 0.55 * dv)
            self.log.append(dict(kind='E', pos=pos, vol=round(dv, 1),
                                 lv=round(level(pl.eff(keys[0]), pl.ptype), 2),
                                 well=round(pl.wells.get(keys[0], 0), 1)))
            self.tip = 0.0; self.last8 = None

    def mix(self, d):
        pos = poskey(d['Module']); pl = self.plate(pos)
        wk = wellkey(d) if int(d.get('Tips', 96)) == 8 else '1A'
        self.log.append(dict(kind='M', pos=pos, vol=d.get('MixLoopVolume'),
                             lv=round(level(pl.eff(wk), pl.ptype), 2),
                             well=round(pl.wells.get(wk, 0), 1)))

    def mvkit(self, src, dst):
        s, t = poskey(src), poskey(dst)
        if s in self.state:
            if t in self.state:
                self.warn.append(f'@{len(self.log)} mvkit {s}->{t}: 目标位有板（loose_check 必炸）')
            self.state[t] = self.state.pop(s)
        else:
            self.warn.append(f'@{len(self.log)} mvkit {s}->{t}: 源位无板')

    def dialog(self, msg):
        self.log.append(dict(kind='DLG', msg=msg[:30]))
        self.on_dialog(msg, self.state)

    def load_tips(self, d):
        k = poskey(d['Module'])
        self.tips_used[k] = self.tips_used.get(k, 0) + 1

    def finish(self):
        print(f'\n══════ {self.name} 账本 ══════')
        print('枪头取用: ' + ', '.join(f'{k}×{v}' for k, v in sorted(self.tips_used.items(),
                                                        key=lambda x: (len(x[0]), x[0]))))
        if self.warn:
            print(f'⚠ 警告 {len(self.warn)} 条（按类去重）:')
            seen = {}
            for w in self.warn:
                seen.setdefault(w.split(':')[0], []).append(w)
            for key, ws in sorted(seen.items()):
                print(f'  [{key}] ×{len(ws)}  例: {ws[0]}')
        else:
            print('✓ 无过抽 / 无板冲突')
        print('—— 关键终态断言 ——')
        for desc, fn in self.checkpoints:
            try:
                r = fn(self.state)
                print(f'  {"✓" if r is not False else "✗"} {desc}: {r}')
            except Exception as ex:
                print(f'  ✗ {desc}: 异常 {ex}')
        print('—— 各板终态（1A 井）——')
        for pos in sorted(self.state, key=lambda x: (len(x), x)):
            pl = self.state[pos]
            print(f'  P{pos:>2} {pl.ptype:4} {pl.name}: {round(pl.wells.get("1A", 0), 1)}µL '
                  f'泥底{round(pl.floor.get("1A", 0), 1)} [{pl.tags.get("1A", "")}]')
        return not self.warn

# ══════════════ CONFIG · 段一 RrnDepletion ══════════════
def build_rrn():
    s = {}
    def plate(pos, ptype, name):
        s[pos] = Plate(ptype, name); return s[pos]
    p9 = plate('9', 'pcr', '样本反应板'); p9.fill(ALL_WELLS, 18)
    for k in ALL_WELLS: p9.tags[k] = 'totalRNA'
    p10 = plate('10', 'pcr', '水板'); p10.fill(ALL_WELLS, 15)
    for k in ALL_WELLS: p10.tags[k] = 'NF水'
    p11 = plate('11', 'deep', '磁珠源板')
    for c in range(1, 13): p11.wells[f'{c}A'] = 700; p11.tags[f'{c}A'] = 'RNACleanXP'
    plate('13', 'pcr', 'HB分装板(空)'); plate('14', 'pcr', 'PM分装板(空)')
    plate('16', 'pcr', 'RH分装板(空)'); plate('17', 'pcr', 'DI分装板(空)')
    plate('18', 'pcr', '产物板(空)'); plate('20', 'deep', '纯化磁珠板(空)')
    plate('23', 'deep', '废液板(空)')
    p21 = plate('21', 'deep', '酶试剂区板')
    for wk, v, tag in (('1A',560,'HB'), ('2A',600,'PM'), ('3A',340,'RHB'), ('4A',230,'RHE'),
                       ('5A',0,'RHbulk'), ('6A',830,'DIB'), ('7A',830,'DIB'), ('8A',510,'DIE'),
                       ('9A',0,'DIbulk'), ('10A',0,'DIbulk')):
        p21.wells[wk] = v; p21.tags[wk] = tag
    p22 = plate('22', 'deep', '乙醇板'); p22.fill(ALL_WELLS, 550)
    for k in ALL_WELLS: p22.tags[k] = '80%乙醇'
    return s

def dlg_rrn(msg, state):
    pass

BEAD_RRN = {('11', f'{c}A') for c in range(1, 13)}

def ck_rrn():
    def p18(st):
        v = st['18'].wells.get('1A', 0)
        return f'{v:.1f}µL/孔' if abs(v - 10) < 1 else False
    def p9(st):
        v = st['9'].wells.get('1A', 0)
        return f'余{v:.1f}' if -0.5 < v < 6 else False
    def waste_rrn(st):
        v = st['23'].wells.get('1A', 0)
        return f'废液 {v:.1f}/孔' if 400 < v < 700 else False
    def p16(st):
        v = st['16'].wells.get('1A', 0)
        return f'余{v:.1f}' if -0.5 < v < 2 else False
    def eth(st):
        v = st['22'].wells.get('1A', 0)
        return f'余{v:.1f}' if v >= 0 else False
    return [('产物板=10µL/孔', p18), ('反应板抽净', p9), ('RH分装余(死体积)', p16), ('乙醇井未透支', eth), ('废液量合理', waste_rrn)]

# ══════════════ CONFIG · 段二 RnaLibPrep ══════════════
def build_lib():
    s = {}
    def plate(pos, ptype, name):
        s[pos] = Plate(ptype, name); return s[pos]
    p9 = plate('9', 'pcr', '输入反应板P'); p9.fill(ALL_WELLS, 10)
    for k in ALL_WELLS: p9.tags[k] = '去rRNA RNA'
    plate('13', 'deep', '纯化A板(空)')
    p14 = plate('14', 'deep', '乙醇板'); p14.fill(ALL_WELLS, 550)
    for k in ALL_WELLS: p14.tags[k] = '80%乙醇'
    plate('16', 'pcr', 'RT分装板(空)')
    p17 = plate('17', 'deep', 'TE板'); p17.fill(ALL_WELLS, 140)
    for k in ALL_WELLS: p17.tags[k] = 'TE'
    plate('18', 'deep', '废液1(空)')
    plate('20', 'pcr', 'SS分装板(空)')
    p21 = plate('21', 'deep', '酶试剂区板')
    for wk, v, tag in (('1A',450,'FragBuf'), ('2A',670,'RT-B'), ('3A',140,'RT-E'),
                       ('4A',0,'RTbulk'), ('5A',1070,'SS-B'), ('6A',1070,'SS-B'),
                       ('4C',1070,'SS-B'), ('7A',430,'SS-E'),
                       ('8A',0,'SSbulk'), ('9A',0,'SSbulk'), ('10A',0,'SSbulk'),
                       ('11A',910,'ERAT-B'), ('12A',330,'ERAT-E'), ('1B',0,'ERATbulk'),
                       ('2B',890,'LIG-B'), ('3B',890,'LIG-B'), ('6C',890,'LIG-B'), ('4B',190,'LIG-E'),
                       ('5B',0,'LIGbulk'), ('6B',0,'LIGbulk'), ('7B',0,'LIGbulk'),
                       ('8B',480,'Primer'), ('9B',900,'PCR-E'), ('10B',900,'PCR-E'),
                       ('2C',900,'PCR-E'),
                       ('11B',0,'PCRbulk'), ('12B',0,'PCRbulk'), ('1C',0,'PCRbulk')):
        p21.wells[wk] = v; p21.tags[wk] = tag
    for c in range(1, 13):                                  # 磁珠源井（POS21 D/E 行，6℃）
        p21.wells[f'{c}D'] = 700; p21.tags[f'{c}D'] = 'DNA Clean Beads'
    for c in ('1E', '2E', '3E'):
        p21.wells[c] = 1200; p21.tags[c] = 'DNA Clean Beads'   # 32.5µL：每井 4 列
    p21.wells['4E'] = 1100; p21.tags['4E'] = 'DNA Clean Beads'  # 10µL：每井 12 列
    for c in ('5E', '6E', '7E', '8E', '9E', '10E'):
        p21.wells[c] = 1100; p21.tags[c] = 'DNA Clean Beads'   # 60µL：每井 2 列
    p22 = plate('22', 'pcr', 'Adapter板'); p22.fill(ALL_WELLS, 10)
    for k in ALL_WELLS: p22.tags[k] = 'Adapter原液'
    return s

def dlg_lib(msg, state):
    def refill_eth(state):
        for k in ALL_WELLS: state['14'].wells[k] = 550
    if '换台②' in msg:
        state['16'] = Plate('pcr', 'ERAT分装板(空)')
        state['20'] = Plate('pcr', 'LIG分装板(空)')
        state['23'] = Plate('deep', '分选1板(空)')
        refill_eth(state)
    elif '快速更换枪头盒' in msg:
        pass
    elif '换台③' in msg:
        state['13'] = Plate('deep', 'PCR纯化板(空)')
        state['16'] = Plate('deep', '分选2板(空)')
        state['12'] = Plate('pcr', 'PCRMix分装板(空)')
        state['10'] = Plate('pcr', '反应板S(空)')
        state['18'] = Plate('deep', '废液2(空)')
        state.pop('20', None)
        refill_eth(state)
    elif '换台④' in msg:
        state.pop('9', None); state.pop('22', None); state.pop('23', None)
        state['20'] = Plate('pcr', '产物板T(空)')
        refill_eth(state)

BEAD_LIB = ({('21', f'{c}D') for c in range(1, 13)}
            | {('21', c) for c in ('1E', '2E', '3E', '4E', '5E', '6E', '7E', '8E', '9E', '10E')})

def ck_lib():
    def s50(st):
        v = st['11'].wells.get('1A', 0)
        return f'S抽净({v:.1f})' if -0.5 < v < 3 else False
    def t30(st):
        v = st['20'].wells.get('1A', 0)
        return f'{v:.1f}' if abs(v - 30) < 1.5 else False
    def pf(st):
        v = st['9'].wells.get('1A', 0) if '9' in st else 0
        return f'余{v:.1f}' if -0.5 < v < 4 else False
    def te(st):
        v = st['17'].wells.get('1A', 0)
        return f'余{v:.1f}' if v > 5 else False
    def eth(st):
        v = st['14'].wells.get('1A', 0)
        return f'余{v:.1f}' if v >= 0 else False
    return [('S板=50µL', s50), ('T板=30µL', t30), ('P板抽净', pf), ('TE板未吸空', te), ('乙醇井未透支', eth)]

# ══════════════ mock spredo & 执行 ══════════════
class _Wait:
    def Wait(self): pass

def run_script(path, eng):
    import types
    mock = types.ModuleType('spredo')
    mock.init = lambda x: None
    mock.binding_map = lambda m: None
    mock.update_feature = lambda feats: eng.log.append(dict(kind='DESK', n=len(feats)))
    mock.shake = types.SimpleNamespace(binding=lambda x: None)
    mock.home = lambda: None
    mock.dely = lambda s2: eng.log.append(dict(kind='DELY', s=s2))
    mock.dialog = lambda m: eng.dialog(m)
    mock.report = lambda **kw: eng.log.append(dict(kind='R', **kw))
    mock.require2 = lambda opts, extra: types.SimpleNamespace(Item1=['200 ng→14 cycles'])
    mock.load_tips = lambda d: eng.load_tips(d)
    mock.unload_tips = lambda d: (setattr(eng, 'tip', 0.0), setattr(eng, 'tip96', 0.0))
    mock.aspirate = lambda d: eng.aspirate(d)
    mock.dispense = lambda d: eng.dispense(d)
    mock.empty = lambda d: eng.empty(d)
    mock.mix = lambda d: eng.mix(d)
    mock.mvkit = lambda a, b: eng.mvkit(a, b)
    mock.pcr_open_door = lambda: None
    mock.pcr_close_door = lambda: None
    mock.pcr_run_methods = lambda method='': eng.log.append(dict(kind='PCR', m=method))
    mock.pcr_stop_heating = lambda: None
    mock.temp_set = lambda t: None
    mock.temp_sleep = lambda: None
    mock.shake_on = lambda *a: None
    mock.shake_off = lambda: None
    mock.parallel_block = lambda fn: (fn(), _Wait())[1]
    g = {'Spx96': object(), '__name__': '__main__'}
    sys.modules['spredo'] = mock
    exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), g)

if __name__ == '__main__':
    here = '.'   # ← 改成你的 spredo 脚本所在目录
    results = {}
    for name, path, eng in (
            ('RrnDepletion', f'{here}/RrnDepletion.py',
             Engine('RrnDepletion', build_rrn, dlg_rrn, BEAD_RRN, ck_rrn())),
            ('RnaLibPrep', f'{here}/RnaLibPrep.py',
             Engine('RnaLibPrep', build_lib, dlg_lib, BEAD_LIB, ck_lib()))):
        try:
            run_script(path, eng)
            ok = eng.finish()
            results[name] = {'ok': ok, 'warn': eng.warn, 'log': eng.log}
        except Exception:
            import traceback
            print(f'\n══════ {name} 执行失败 ══════')
            traceback.print_exc()
            results[name] = {'ok': False}
    json.dump(results, open('/tmp/ledger_rrn_lib.json', 'w', encoding='utf-8'),
              ensure_ascii=False, default=str)
    print('\n明细已存 /tmp/ledger_rrn_lib.json')
