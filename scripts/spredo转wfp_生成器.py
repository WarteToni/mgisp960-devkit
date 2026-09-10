# -*- coding: utf-8 -*-
"""
spredo 脚本 → WDesigner .wfp 工程生成器（通用版）
用法：python3 spredo转wfp_生成器.py <spredo脚本.py> <模板.wfp> <输出.wfp> [工程名] [固定PCR方法名]
示例：python3 spredo转wfp_生成器.py RNA_Library.py 模板.wfp out/MyProject.wfp MyProject PCR_14C
输入/输出全部命令行传入，无硬编码路径；<模板.wfp> 用任意一个与目标软件版本
匹配的已有单换台 .wfp 工程即可（只借用其字节骨架与类型名记录）。
已知限制（首版）：
  - 源脚本须为"单换台"结构：first_feature() 开机台面 + 顶层 SWAP1_POS 变量
  - require2 循环数选择不转换，PCR 调用统一替换为固定方法名（第5参数）
"""
import ast, json, os, struct, sys

USAGE = ("用法: python3 spredo转wfp_生成器.py <spredo脚本.py> <模板.wfp> <输出.wfp> "
         "[工程名] [固定PCR方法名] [--sw 1.9.0.398]")
if len(sys.argv) < 4:
    print(USAGE)
    sys.exit(1)
_args = list(sys.argv[1:])
SW = "1.9.0.398"                                              # 现场软件 1.9.0.395 时用 --sw 切换
if "--sw" in _args:
    _i = _args.index("--sw"); SW = _args[_i + 1]; del _args[_i:_i + 2]
SRC, TPL, OUT = _args[0], _args[1], _args[2]
PROJ_NAME = _args[3] if len(_args) > 3 else os.path.splitext(os.path.basename(OUT))[0]
FIXED_PCR = _args[4] if len(_args) > 4 else "PCR_14C"   # require2 替代：固定循环方法

ASM = f"Lib.MGISP_960.VisualDesigner.Spx, Version={SW}, Culture=neutral, PublicKeyToken=null"
CORE = f"Common.WorkflowDesigner.Spx, Version={SW}, Culture=neutral, PublicKeyToken=null"
def A(name): return f"Lib.MGISP_960.VisualDesigner.Spx.Workflow.Commands.{name}, {ASM}"
def C(name): return f"Common.WorkflowDesigner.Spx.Core.{name}, {CORE}"

S = lambda v: str(v)          # 数值→字符串
_BASE = os.path.dirname(os.path.abspath(__file__))   # schema 随脚本走，与工作目录无关
SCHEMA = {k: {**v, "type": v["type"].replace("1.9.0.398", SW)} for k, v in
          json.load(open(os.path.join(_BASE, "wfp活动schema.json"), encoding="utf-8")).items()}

def sanitize(a):
    """按原厂 schema 白名单过滤字段 + 排序 + 用权威完整类型名（反序列化器严格，多余字段即拒）"""
    short = a["ActivityType"].split(",")[0].split(".")[-1]
    sch = SCHEMA[short]
    out = {}
    for f in sch["fields"]:
        if f in a: out[f] = a[f]
    out["ActivityType"] = sch["type"]          # 权威完整名
    for k, v in a.items():                      # 白名单内的非列表字段保留
        if k in sch["fields"]: out[k] = v
    # 强制默认值（原厂必有）
    out.setdefault("ActivityName", short)
    if "IsEnabled" in sch["fields"]: out.setdefault("IsEnabled", True)
    out.setdefault("DisplayName", a.get("DisplayName", short))
    return out

def sanitize_tree(a):
    if isinstance(a, dict):
        for k in ("Branches","Body","Activities"):
            if a.get(k): a[k] = [sanitize_tree(c) for c in a[k]]
        return sanitize(a)
    return a

def act(name, disp, **kw):
    d = {"ActivityType": kw.pop("_t", A(name)), "ActivityName": name,
         "DisplayName": disp, "IsEnabled": True}
    d.update(kw); return d

def well2cr(d):
    """Well:'6A' → Col/Row；兼容直接 Col/Row"""
    if 'Well' in d:
        w = str(d['Well']); return str(int(w[:-1])), w[-1].replace('A','1').replace('B','2')
    return str(d.get('Col','1')), str(d.get('Row','1'))

def pos(m): return str(m).replace('POS','').replace('Pos','')

def liq(name, disp, d, extra=None):
    """dict 参数 → 活动字段（同名数值字符串化）"""
    col, row = well2cr(d)
    o = {"Position": pos(d['Module']), "Col": col, "Row": row,
         "WellType": 0, "Tips": int(d.get('Tips', 96))}
    KEYMAP = {
        'AspirateVolume':'AspirateVolume','AspirateRateOfP':'AspirateRateOfP',
        'DispenseVolume':'DispenseVolume','DispenseRateOfP':'DispenseRateOfP',
        'BottomOffsetOfZ':'BottomOffsetOfZ','DelySeconds':'DelySeconds',
        'PreAirVolume':'PreAirVolume','PostAirVolume':'PostAirVolume',
        'SubMixLoopCounts':'SubMixLoopCounts','MixLoopVolume':'MixLoopVolume',
        'MixLoopAspirateRate':'MixLoopAspirateRate','MixLoopDispenseRate':'MixLoopDispenseRate',
        'MixOffsetOfZInLoop':'MixOffsetOfZInLoop','MixOffsetOfZAfterLoop':'MixOffsetOfZAfterLoop',
        'DispenseVolumeAfterSubmixLoop':'DispenseVolumeAfterSubmixLoop',
        'DispenseRateAfterSubmixLoop':'DispenseRateAfterSubmixLoop',
        'SubMixLoopCompletedDely':'SubMixLoopCompletedDely',
    }
    for k, wd in KEYMAP.items():
        if k in d and not isinstance(d[k], dict) and d[k] is not None: o[wd] = S(d[k])
    touch = 'TipTouchHeight' in d
    o['IfTipTouch'] = bool(touch)
    if touch: o['TipTouchHeight'] = S(d['TipTouchHeight'])
    if extra: o.update(extra)
    return act(name, disp, **o)

# ── AST 解析 ─────────────────────────────────────────────
src = open(SRC, encoding='utf-8').read()
tree = ast.parse(src)
funcs = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef)}
kw = lambda n: ast.dump(n)

def expr(e):
    """AST算术表达式→字符串（原厂存法：Col='1+x'、BottomOffsetOfZ='4.3-4*x'，运行时WD求值）"""
    if isinstance(e, ast.Constant):
        v = e.value
        return str(v) if isinstance(v, int) else repr(v)
    if isinstance(e, ast.Name): return e.id
    if isinstance(e, ast.BinOp):
        op = {ast.Add:'+', ast.Sub:'-', ast.Mult:'*', ast.Div:'/'}[type(e.op)]
        return f"{expr(e.left)}{op}{expr(e.right)}"
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        return '-' + expr(e.operand)
    return None

def const(e):
    if isinstance(e, ast.Constant): return e.value
    if isinstance(e, ast.Name) and e.id == 'pcr_method': return FIXED_PCR  # 变量替代
    if isinstance(e, ast.Dict):   # 字典字面量（液体操作参数）
        return {const(k): const(v) for k, v in zip(e.keys, e.values)}
    if isinstance(e, (ast.BinOp, ast.UnaryOp)): return expr(e)   # 循环变量表达式→字符串
    if isinstance(e, ast.Attribute): return None
    return None

def call2activity(node):
    """单条调用语句 → 活动 dict；返回 None 表示跳过"""
    f = node.func
    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else '')
    args = [const(a) for a in node.args]
    kws = {k.arg: const(k.value) for k in node.keywords}
    if args and isinstance(args[0], dict):   # 液体类：第一个位置参数是 dict
        kws.update(args[0]); args = args[1:]
    if name == 'aspirate':       return liq('Aspirate','Aspirate', kws)
    if name == 'dispense':       return liq('Dispense','Dispense', kws, {'IsEmpty': False, 'EmptyForDispense': False})
    if name == 'empty':          return liq('Dispense','Dispense', kws, {'IsEmpty': True,  'EmptyForDispense': False})
    if name == 'mix':            return liq('Mix','Mix', kws)
    if name == 'load_tips':
        col, row = well2cr(kws)
        return act('LoadTips','Load Tips', Position=pos(kws['Module']), Col=col, Row=row,
                   WellType=0, Tips=int(kws.get('Tips', 96)))
    if name == 'unload_tips':
        col, row = well2cr(kws)
        return act('UnloadTips','Unload Tips', Position=pos(kws['Module']), Col=col, Row=row,
                   WellType=0, Tips=int(kws.get('Tips', 96)))
    if name == 'mvkit':
        return act('MvKit','Move Plate', Source=pos(args[0]), Destination=pos(args[1]),
                   IsMoveAll=False, IfJc=False)
    if name == 'dely':           return act('Delay','Delay', Duration=S(args[0]))
    if name == 'report':         return act('Report','Report', Phase=kws.get('phase',''), Step=kws.get('step',''))
    if name == 'dialog':
        return act('Dialog','Dialog', Message=args[0], Caption='None', Tag='None',
                   IsSetTimeout=True, Timeout='2:00:00')
    if name == 'shake_on':       return act('ShakeOn','Shake On', Rate=S(args[0]), Direct=int(args[1]))
    if name == 'shake_off':      return act('ShakeOff','Shake Off')
    if name == 'pcr_run_methods':
        m = kws.get('method') or args[0]
        return act('PcrRun','', Method={"Text": m, "IsUseVariable": False,
                   "VariableName": None, "DisplayName": m}, PCRType=0)
    if name == 'pcr_open_door':  return act('PcrOpenDoor','', PCRType=0)
    if name == 'pcr_close_door': return act('PcrCloseDoor','', PCRType=0)
    if name == 'pcr_stop_heating': return act('PcrStop','', PCRType=0)
    if name == 'temp_set':       return act('TempSet','Temp. On', TempType=0, Target=S(args[0]))
    if name == 'temp_sleep':     return act('TempSleep','Temp Sleep', TempType=0)
    if name == 'update_feature': return act('UpdateDeck','Update Deck', Deck='DESK 2')
    if name == 'home':           return None
    if name in ('init','binding_map'): return None
    return None

def stmts2activities(body):
    out = []
    for st in body:
        a = stmt2activity(st)
        if a: out.append(a)
    return out

def stmt2activity(st):
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
        return call2activity(st.value)
    if isinstance(st, ast.For):
        var = st.target.id
        n = st.iter.args[0].value if (isinstance(st.iter, ast.Call) and st.iter.args) else None
        return act('Loop','Loop', _t=C('Loop'), VariableName=var,
                   LoopCount=S(n), LoopType=1, Body=stmts2activities(st.body))
    return None

# ── 顶层流程组装（parallel_block/Wait 规则）──────────────
# 功能标注：每个并行函数块在干什么（WDesigner 画布上直接可见）。
# 下面是参考项目（一步法）的示例；复用时换成自己项目的并行函数名，
# 未匹配的函数名会原样回退显示，不影响生成。
FUNC_LABEL = {
 'blockCapStart': 'PCR仪START预热', 'blockChill': '试剂板降温6℃',
 'blockBead': '磁珠预处理', 'blockFrag': '片段化85℃4min',
 'blockFirstPrep': '一链Mix配制分装', 'blockFirstStrand': '一链合成反应',
 'blockSecondPrep': '二链Mix配制分装', 'blockSecondStrand': '二链+末修反应',
 'blockLigPrep': '接头连接组装', 'blockPCR': 'PCR扩增(所选循环)',
 'blockPCRBeads': 'PCR纯化磁珠预分装', 'blockCool': 'PCR降温和热盖停止',
 'blockPCRPurify': 'PCR产物纯化收文库'}
def main_label(acts):
    for a in acts:
        if a.get('ActivityName') == 'Report':
            return '主流程·' + str(a.get('Phase','')) + str(a.get('Step',''))
    return '主流程'

root_acts, pending, buf = [], {}, []
def flush_wait():
    global buf
    branches = []
    tags = []
    for h, (fname, b) in pending.items():
        lab = FUNC_LABEL.get(fname, fname)
        tags.append(lab)
        branches.append(act('Block', lab, _t=None, Activities=b))
    if buf:
        branches.append(act('Block', main_label(buf), _t=None, Activities=buf)); buf = []
        tags.append('主流程')
    if len(branches) == 1:
        root_acts.extend(branches[0]['Activities'])
    elif branches:
        root_acts.append(act('Parallel', '并行:' + '+'.join(tags), _t=C('Parallel'), Branches=branches))
    pending.clear()

skip_defs = {'first_feature'}
for st in tree.body:
    if isinstance(st, ast.FunctionDef):
        continue
    if isinstance(st, ast.While):   # require2 循环数块 → 跳过（固定14C）
        continue
    if isinstance(st, ast.Assign) and isinstance(st.value, ast.Call) \
       and getattr(st.value.func, 'id', '') == 'parallel_block':
        # 提交前已执行的主流程操作=顺序块，不得并入Parallel分支（语义保真）
        if buf:
            root_acts.append(act('Block', main_label(buf), _t=None, Activities=buf)); buf = []
        fname = st.value.args[0].id
        pending[st.targets[0].id] = (fname, stmts2activities(funcs[fname].body))
    elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) \
         and isinstance(st.value.func, ast.Attribute) and st.value.func.attr == 'Wait':
        h = st.value.func.value.id
        if h in pending: flush_wait()
    elif isinstance(st, ast.Assign) and isinstance(st.value, ast.Constant) and st.value.value == 0:
        continue   # pcr_method = 0
    else:
        a = stmt2activity(st)
        if a: buf.append(a)
if pending: flush_wait()
if buf: root_acts.extend(buf); buf = []

# Block 的 ActivityType 修正（Parallel 分支的 Block）
BLOCK_T = "Common.WorkflowDesigner.Spx.Core.Block, " + CORE
def fixblocks(a):
    if isinstance(a, dict):
        if a.get('ActivityType') is None and 'Branches' not in a:
            a['ActivityType'] = BLOCK_T
        for k in ('Branches','Body','Activities'):
            for c in a.get(k) or []: fixblocks(c)
    elif isinstance(a, list):
        for c in a: fixblocks(c)
fixblocks(root_acts)

workflow = sanitize_tree(act('GlobalSequence','Workflow', _t=C('GlobalSequence'),
                             GlobalVariables=[],
                             Activities=[act('Initialize','Initialize', Comment='初始化')] + root_acts))
workflow.pop('IsEnabled', None)   # 原厂 GlobalSequence 无此字段

# ── 台面 PosInfos（从 first_feature / SWAP1_POS AST 提取）──
MARK2TYPE = {'PCR':None,'MagRack':6,'Shaker':8,'Temp_Module':9}
def feature_tuples(fn_name):
    if fn_name in funcs:                        # def first_feature(): return [...]
        f = funcs[fn_name]
        ret = next(s for s in f.body if isinstance(s, ast.Return)).value.elts
    else:                                       # SWAP1_POS = [...] 顶层赋值
        ret = next(s.value.elts for s in tree.body
                   if isinstance(s, ast.Assign) and s.targets[0].id == fn_name)
    out = []
    for t in ret:
        v = [const(e) for e in t.elts]
        out.append(v)
    return out

def build_deck(fn_name, name, is_main):
    posinfos = []
    for slot, kit, c1, c2, cover, replace, mark in feature_tuples(fn_name):
        n = int(slot.replace('Pos',''))
        pt = MARK2TYPE.get(mark, 0)
        if mark == 'PCR':
            pt = 4 if kit else 3
        if n == 5: pt = 1
        if n == 24: pt = 10
        posinfos.append({
            "Name": f"POS{n}", "KitName": kit, "PosType": pt,
            "Available": (pt != 3), "CoverName": None,   # 原厂：仅空PCR位(3)不可用；有板PCR位(4)=true
            "Comment1": c1, "Comment2": c2, "Comment3": c1, "Comment4": c2,
            "HaveCoverPlate": False, "IsNeedReplace": True,
            "IsAllowGripperAction": (n > 4), "Version": 1})
    return {"Name": name, "IsMainDeck": is_main,
            "DeviceConfigName": "2" if is_main else None, "PosInfos": posinfos}

# 台面变量名约定（单换台结构）：开机台面 = first_feature()，换台后 = 顶层 SWAP1_POS
main_deck = build_deck('first_feature', '\\MainDeck/', True)
desk2 = build_deck('SWAP1_POS', 'DESK 2', False)

# ── wfp 记录流写出（模板骨架 + 新载荷）──────────────────
tpl = open(TPL, 'rb').read()
# 头部动态定位（不依赖模板工程名长度）：
#   [14B Release 记录][4+L 工程名记录][5B '2' 记录][16B DateTime×2][4B 模块计数][Deck类型名记录]
name_len = struct.unpack('>I', tpl[14:18])[0]
HEAD0 = 14 + 4 + name_len
assert tpl[HEAD0:HEAD0+4] == struct.pack('>I', 1) and tpl[HEAD0+4:HEAD0+5] == b'2', \
    "模板头部布局异常：'2' 配置号记录不在预期位置（确认模板是 WDesigner 保存的 .wfp 工程）"
cnt = struct.unpack('>I', tpl[HEAD0+21:HEAD0+25])[0]
assert 2 <= cnt <= 6 and struct.unpack('>I', tpl[HEAD0+25:HEAD0+29])[0] == 121, \
    "模板头部布局异常：模块计数/Deck 类型名记录不在预期位置（确认模板含换台台面，即单换台以上工程）"
# 固定头21B（'2'配置号+DateTime×2）+ 模块计数（必须与实际模块数一致，否则解析器读到EOF报错）
N_MODULES = 3   # 单换台固定值：MainDeck + Workflow + DESK2；多次换台需重构
HDR = tpl[HEAD0:HEAD0+21] + struct.pack('>I', N_MODULES)
def recs_from_tpl():
    """模板里的类型名记录（Deck 121B / Workflow 133B / 'WorkflowModuleModel'）"""
    out, i = [], 0
    while i < len(tpl) - 4:
        n = struct.unpack('>I', tpl[i:i+4])[0]
        if 2 <= n <= 500000 and i+4+n <= len(tpl):
            try:
                t = tpl[i+4:i+4+n].decode('utf-8')
                if sum(1 for c in t if c.isprintable())/len(t) > 0.92:
                    out.append(tpl[i:i+4+n]); i += 4+n; continue
            except UnicodeDecodeError: pass
        i += 1
    return out
T = recs_from_tpl()   # [Release, 名, Deck类型名, MainDeck名, MainDeckJSON, Wf类型名, WfModel名, WfJSON, Deck类型名, DESK2名, DESK2JSON, Deck类型名, DESK3名, DESK3JSON]

def R(s):
    b = s.encode('utf-8') if isinstance(s, str) else s
    return struct.pack('>I', len(b)) + b

J = lambda o: json.dumps(o, ensure_ascii=False, separators=(',',':'))

FF = bytes([0xFF, 0xFF, 0xFF, 0xFF])  # 模块名与模块JSON之间的4字节填充标记（原厂字节级实锤，缺它打不开）
blob = b''.join([
    T[0],                          # Release V1（T 元素自带长度前缀）
    R(PROJ_NAME),                  # 工程名
    HDR,                           # 头部：'2'+DateTime×2+模块计数(N_MODULES)
    T[2],                          # Deck 类型名记录
    T[3],                          # \MainDeck/
    FF, R(J(main_deck)),           # 开机台面
    T[5],                          # Workflow 类型名记录
    T[6],                          # WorkflowModuleModel
    FF, R(J(workflow)),            # 流程
    T[8],                          # Deck 类型名记录
    R('DESK 2'),
    FF, R(J(desk2)),               # 换台后台面
])
blob = blob.replace(b'1.9.0.395', SW.encode())  # 模板如嵌旧版本串，对齐到目标版本
open(OUT, 'wb').write(blob)
print(f"✓ 生成 {OUT}（{len(blob)}B）")
print(f"  流程活动数: {len(workflow['Activities'])}（根下）")
print(f"  台面: MainDeck {len(main_deck['PosInfos'])}位 + DESK2 {len(desk2['PosInfos'])}位")

# ── 自检：重新解析 ──────────────────────────────────────
d2 = open(OUT,'rb').read()
recs, i = [], 0
while i < len(d2) - 4:
    n = struct.unpack('>I', d2[i:i+4])[0]
    if 2 <= n <= 500000 and i+4+n <= len(d2):
        try:
            t = d2[i+4:i+4+n].decode('utf-8')
            if sum(1 for c in t if c.isprintable())/len(t) > 0.92:
                recs.append(t); i += 4+n; continue
        except UnicodeDecodeError: pass
    i += 1
print(f"  自检: {len(recs)} 条记录")
wf2 = json.loads([t for t in recs if t.startswith('{"ActivityType')][0])
import collections
cnt = collections.Counter()
def wk(a):
    if isinstance(a, dict) and 'ActivityType' in a:
        cnt[a['ActivityType'].split(',')[0].split('.')[-1]] += 1
        for k in ('Branches','Body','Activities'):
            for c in a.get(k) or []: wk(c)
wk(wf2)
print("  活动统计:", dict(cnt.most_common()))
