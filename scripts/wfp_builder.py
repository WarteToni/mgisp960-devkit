#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wfp 直接构建器 —— 从操作序列直接生成 WDesigner 工程（不经 spredo/AST/转换器）。

定位（2026-09-10 用户需求）：WD 交付路线 = 直接生成。spredo转wfp_生成器 保留为
"已有 spredo 脚本转 wfp"的兼容路径；新项目 wfp 一律用本构建器。

用法骨架：
    from wfp_builder import Wfp, seq
    w = Wfp("工程名", deck_main=[24位7元组], deck_swap=[同], sw="1.9.0.395")
    r = w.root()
    r.initialize()
    with r.block("开机确认·设温") as b:
        b.dialog("..."); b.temp_set(6)
    with r.parallel("并行:预热+准备") as par:
        par.branch("PCR 预热", lambda b: (b.pcr_open_door(), b.pcr_run("START")))
        par.branch("主流程", lambda b: b.report("试剂预混", "1/8"))
    with r.block("阶段名") as b:
        for col in range(4):
            b.load_tips("POS5", col + 1, tips=8)
            b.aspirate("POS21", 4, volume=12, z="2.0", tips=8, rate=20, pre=2)
            b.dispense("POS21", 3, volume=12, z="3.5", tips=8, rate=20)
            b.unload_tips()
    b.dely(180); b.pcr_stop_heating()
    w.save("out.wfp")

惯例依据：references/09 §八（Reference-first 产线惯例）。
模板：<skill>/scripts/最小骨架模板.wfp（只借类型名记录与头部骨架）。
版本：默认 1.9.0.395（现场实机实证；低版本软件打不开高版本串文件）。
"""
import json, os, struct

_SW_DEFAULT = "1.9.0.395"
_BASE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA = {k: v for k, v in json.load(
    open(os.path.join(_BASE, "wfp活动schema.json"), encoding="utf-8")).items()}

CORE = "Common.WorkflowDesigner.Spx.Core, Version={sw}, Culture=neutral, PublicKeyToken=null"
ASM = "Lib.MGISP_960.VisualDesigner.Spx, Version={sw}, Culture=neutral, PublicKeyToken=null"

MARK2TYPE = {'PCR': None, 'MagRack': 6, 'Shaker': 8, 'Temp_Module': 9}


def _R(s):
    b = s.encode('utf-8') if isinstance(s, str) else s
    return struct.pack('>I', len(b)) + b


def _J(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))


def _act(name, disp, sw, **kw):
    """按 schema 白名单构造活动 dict（多余字段剔除、类型串权威化）。"""
    sch = _SCHEMA[name]
    a = {"ActivityType": sch["type"].replace("{sw}", sw).replace("1.9.0.395", sw),
         "ActivityName": name, "DisplayName": disp or name, "IsEnabled": True}
    for f in sch["fields"]:
        if f in kw:
            a[f] = kw[f]
    for k, v in kw.items():
        if k in sch["fields"]:
            a[k] = v
    a.setdefault("ActivityName", name)
    if "IsEnabled" in sch["fields"]:
        a.setdefault("IsEnabled", True)
    return a


def _liq(name, module, col, row, tips, sw, disp=None, **kw):
    """液体类活动通用构造。volume/rate/z/pre/post/dely/touch 按生成器键名映射。"""
    keymap = {'volume': ('AspirateVolume', 'DispenseVolume'),
              'rate': ('AspirateRateOfP', 'DispenseRateOfP'),
              'z': 'BottomOffsetOfZ', 'pre': 'PreAirVolume', 'post': 'PostAirVolume',
              'dely': 'DelySeconds'}
    o = {"Position": str(module).replace('POS', '').replace('Pos', ''),
         "Col": str(col), "Row": str(row), "WellType": 0, "Tips": int(tips)}
    for k, v in kw.items():
        if k in ('volume', 'rate', 'z', 'pre', 'post', 'dely'):
            if v is None:
                continue
            keys = keymap[k]
            keys = keys if isinstance(keys, tuple) else (keys, keys)
            o[keys[0] if name == 'Aspirate' else keys[-1]] = str(v)
        elif k == 'mixloops':
            o['SubMixLoopCounts'] = str(v)
        elif k == 'mixvol':
            o['MixLoopVolume'] = str(v)
        elif k == 'mixrate':
            o['MixLoopAspirateRate'] = o['MixLoopDispenseRate'] = str(v)
        elif k == 'mixzin':
            o['MixOffsetOfZInLoop'] = str(v)
        elif k == 'mixzafter':
            o['MixOffsetOfZAfterLoop'] = str(v)
        elif k == 'mixdely':
            o['SubMixLoopCompletedDely'] = str(v)
        elif k == 'touch':
            o['IfTipTouch'] = True; o['TipTouchHeight'] = str(v)
        else:
            o[k] = str(v) if isinstance(v, (int, float)) else v
    if name == 'Dispense':
        o['IsEmpty'] = bool(disp); o['EmptyForDispense'] = False
    if 'IfTipTouch' not in o:
        o['IfTipTouch'] = False
    return _act(name, kw.get('disp_name') or name, sw, **o)


class Seq:
    """活动序列容器：root / Block / Parallel.branch / Loop.Body 共用。
    子序列用 Seq(sw, items=父列表) 共享同一列表——全部方法在子序列可用。"""

    def __init__(self, sw, items=None):
        self.sw = sw
        self.items = items if items is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _add(self, a):
        self.items.append(a)
        return a

    # ── 流程控制 ──
    def initialize(self):
        return self._add(_act('Initialize', 'Initialize', self.sw, Comment='初始化'))

    def block(self, disp):
        b = self._add(_act('Block', disp, self.sw, Comment=None))
        b['Activities'] = []
        return Seq(self.sw, items=b['Activities'])

    def parallel(self, disp, branches=None):
        """两用：branches=[(label, fn)] 直接组装；或不传，用 with + par.branch()。"""
        p = _act('Parallel', disp, self.sw)
        p['Branches'] = []

        def assemble(label, fn):
            s = Seq(self.sw)
            fn(s)
            br = _act('Block', label, self.sw, Comment=None)
            br['Activities'] = s.items
            p['Branches'].append(br)

        if branches:
            for label, fn in branches:
                assemble(label, fn)
        self._add(p)
        return ParallelCtx(p, self.sw, assemble)

    def loop(self, var, count, disp=None):
        l = _act('Loop', disp or f'循环·{var}×{count}', self.sw,
                 VariableName=var, LoopCount=str(count), LoopType=1)
        l['Body'] = []
        self._add(l)
        return Seq(self.sw, items=l['Body'])

    # ── 指令 ──
    def dialog(self, msg):
        return self._add(_act('Dialog', '弹窗·人工确认', self.sw, Comment=msg))

    def report(self, phase, step):
        return self._add(_act('Report', f'进度·{phase} {step}', self.sw,
                              Phase=phase, Step=step))

    def load_tips(self, module, col, row=1, tips=96):
        return self._add(_liq('LoadTips', module, col, row, tips, self.sw,
                              disp_name=f'取枪头·P{str(module).replace("POS", "")}' + ('（8头）' if tips == 8 else '')))

    def unload_tips(self, module='POS24', well='1A'):
        return self._add(_act('UnloadTips', '丢枪头', self.sw, Position='24', Well=well))

    def aspirate(self, module, col, volume, z, tips=96, rate=20, pre=5, post=0,
                 dely=0.5, row=1, disp_name=None, **kw):
        return self._add(_liq('Aspirate', module, col, row, tips, self.sw,
                              volume=volume, rate=rate, z=z, pre=pre, post=post,
                              dely=dely, disp_name=disp_name, **kw))

    def dispense(self, module, col, volume=None, z=None, tips=96, rate=20,
                 dely=0.5, row=1, empty=False, touch=None, disp_name=None, **kw):
        kw2 = dict(volume=volume, rate=rate, z=z, dely=dely, touch=touch,
                   disp_name=disp_name)
        return self._add(_liq('Dispense', module, col, row, tips, self.sw,
                              disp=empty, **{k: v for k, v in kw2.items() if v is not None or k in ('z', 'volume')}))

    def mix(self, module, col, loops, mixvol, z=1.0, zin=1.0, zafter=5.0,
            rate=20, tips=8, dely=0, row=1, disp_name=None, **kw):
        return self._add(_liq('Mix', module, col, row, tips, self.sw,
                              mixloops=loops, mixvol=mixvol, z=z, mixrate=rate,
                              mixzin=zin, mixzafter=zafter, mixdely=dely,
                              disp_name=disp_name))

    def mvkit(self, src, dst):
        return self._add(_act('MvKit', f'移板 {src}→{dst}', self.sw,
                              Source=src, Destination=dst))

    def dely(self, seconds):
        return self._add(_act('Delay', f'静置·{seconds}s', self.sw, Duration=str(seconds)))

    def pcr_run(self, method):
        return self._add(_act('PcrRun', f'PCR程序·{method}', self.sw,
                              Method={"Text": method, "IsUseVariable": False,
                                      "VariableName": None, "DisplayName": method},
                              PCRType=0))

    def pcr_open_door(self):
        return self._add(_act('PcrOpenDoor', '', self.sw, PCRType=0))

    def pcr_close_door(self):
        return self._add(_act('PcrCloseDoor', '', self.sw, PCRType=0))

    def pcr_stop_heating(self):
        return self._add(_act('PcrStop', 'PCR停止加热', self.sw, PCRType=0))

    def temp_set(self, t):
        return self._add(_act('TempSet', f'温控模块 {t}℃', self.sw, TempType=0, Target=str(t)))

    def shake_on(self, rpm, direction):
        return self._add(_act('ShakeOn', 'Shake On', self.sw, Rate=str(rpm), Direct=int(direction)))

    def shake_off(self):
        return self._add(_act('ShakeOff', 'Shake Off', self.sw))


class ParallelCtx:
    """with r.parallel(...) as par: par.branch(label, fn) 收集分支。"""

    def __init__(self, p, sw, assemble):
        self._p, self.sw, self._assemble = p, sw, assemble

    def branch(self, label, fn):
        self._assemble(label, fn)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Wfp:
    """工程级：台面（24 位 7 元组）+ 流程根 → 记录流写出。"""

    def __init__(self, proj, deck_main, deck_swap, sw=_SW_DEFAULT, template=None):
        self.proj = proj
        self.sw = sw
        self.deck_main = deck_main
        self.deck_swap = deck_swap
        self.template = template or os.path.join(_BASE, "最小骨架模板.wfp")
        self._root = Seq(sw)

    def root(self):
        return self._root

    def _deck_json(self, tuples, name, is_main):
        posinfos = []
        for slot, kit, c1, c2, cover, replace, mark in tuples:
            n = int(slot.replace('Pos', '').replace('POS', ''))
            pt = MARK2TYPE.get(mark, 0)
            if mark == 'PCR':
                pt = 4 if kit else 3
            if n == 5:
                pt = 1
            if n == 24:
                pt = 10
            posinfos.append({
                "Name": f"POS{n}", "KitName": kit, "PosType": pt,
                "Available": (pt != 3), "CoverName": None,
                "Comment1": c1, "Comment2": c2, "Comment3": c1, "Comment4": c2,
                "HaveCoverPlate": False, "IsNeedReplace": True,
                "IsAllowGripperAction": (n > 4), "Version": 1})
        return {"Name": name, "IsMainDeck": is_main,
                "DeviceConfigName": "2" if is_main else None, "PosInfos": posinfos}

    def save(self, out):
        sw = self.sw
        root = self._root
        workflow = {
            "ActivityType": f"Common.WorkflowDesigner.Spx.Core.GlobalSequence, {CORE.format(sw=sw)}",
            "ActivityName": "GlobalSequence", "DisplayName": "Workflow",
            "GlobalVariables": [],
            "Activities": root.items}
        workflow.pop('IsEnabled', None)
        main = self._deck_json(self.deck_main, '\\MainDeck/', True)
        desk2 = self._deck_json(self.deck_swap, 'DESK 2', False)

        # 模板借字节锚点：Release / 模块类型名记录 / 头部（'2'+时间戳）
        tpl = open(self.template, 'rb').read()
        name_len = struct.unpack('>I', tpl[14:18])[0]
        head0 = 14 + 4 + name_len
        assert tpl[head0+4:head0+5] == b'2', "模板头部布局异常（确认是 .wfp 工程）"
        hdr = tpl[head0:head0+21] + struct.pack('>I', 3)

        def recs_from_tpl():
            out, i = [], 0
            while i < len(tpl) - 4:
                n = struct.unpack('>I', tpl[i:i+4])[0]
                if 2 <= n <= 500000 and i+4+n <= len(tpl):
                    try:
                        t = tpl[i+4:i+4+n].decode('utf-8')
                        if sum(1 for c in t if c.isprintable())/len(t) > 0.92:
                            out.append(tpl[i:i+4+n]); i += 4+n; continue
                    except UnicodeDecodeError:
                        pass
                i += 1
            return out
        T = recs_from_tpl()
        ff = bytes([0xFF] * 4)
        blob = b''.join([
            T[0], _R(self.proj), hdr,
            T[2], T[3], ff, _R(_J(main)),
            T[5], T[6], ff, _R(_J(workflow)),
            T[8], _R('DESK 2'), ff, _R(_J(desk2)),
        ])
        if self.sw != '1.9.0.395':
            blob = blob.replace(b'1.9.0.395', self.sw.encode())
        open(out, 'wb').write(blob)
        print(f"✓ builder 生成 {out}（{len(blob)}B）| 根下 {len(root.items)} 活动 | "
              f"台面 MainDeck {len(main['PosInfos'])}位 + DESK2 {len(desk2['PosInfos'])}位 | sw={sw}")
        return out
