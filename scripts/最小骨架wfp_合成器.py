# -*- coding: utf-8 -*-
"""
最小骨架 .wfp 模板合成器 —— 零依赖生成合法 WDesigner 工程骨架（仓库自带模板的来源）

用法：python3 最小骨架wfp_合成器.py [输出.wfp] [--sw 1.9.0.395]
  输出默认 = 本脚本同目录的 最小骨架模板.wfp
  --sw     活动程序集版本串（默认 1.9.0.395，与作者现场实机一致；现场软件为
           1.9.0.398 时用 --sw 1.9.0.398 重生成，模块类型库版本 1.8.0.323 与软件版本无关、恒定）

产物：单换台最小合法工程（模块计数=3）：
  MainDeck + Workflow + DESK 2
  - 两个台面：24 板位按原厂台面规律（POS5 高板位、POS24 垃圾桶位、POS1-4 禁机械臂夹取）
  - Workflow：GlobalSequence + 单个 Initialize 占位活动（与生成器实战产物同构）
用途：作为 spredo转wfp_生成器.py 的 <模板.wfp>——生成器只借本文件的
  类型名记录与头部骨架（Release/工程名记录位/'2'+DateTime），台面与流程
  JSON 全部按新工程重建。也可在 WDesigner 中直接打开当空白起点。

字节布局依据：references/09_WD工程_wfp文件生成.md §三
  （每条记录 = int32 大端长度前缀 + UTF-8 内容；模块名与模块 JSON 之间
  有 4 字节 0xFF 填充标记，缺它打不开）。

常量去标签化自审（产物不含任何公司名/试剂盒/项目内容）：
  - 类型名记录 = .NET 程序集限定名（DeckModuleModel / WorkflowModuleModel），
    各版本原厂文件一致，纯格式常量；
  - DateTime×2 = 16B 创建/修改时间戳常量，无语义，WDesigner 保存时自行覆盖；
  - 台面 KitName 全 null，无任何耗材绑定。
"""
import json, os, struct, sys

# ── 参数 ────────────────────────────────────────────────
args = [a for a in sys.argv[1:]]
SW = "1.9.0.395"
if "--sw" in args:
    i = args.index("--sw"); SW = args[i + 1]; del args[i:i + 2]
OUT = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "最小骨架模板.wfp")
PROJ_NAME = "MinimalTemplate"

# ── 常量（见头部"去标签化自审"）────────────────────────
DT = bytes.fromhex("08deebd369bbacba")            # 16B 时间戳常量（8B×2，创建=修改）
DECK_TYPE = ("Deck.VisualDesigner.Spx.DeckModuleModel, Deck.VisualDesigner.Spx, "
             "Version=1.8.0.323, Culture=neutral, PublicKeyToken=null")          # 121B
WF_TYPE = ("Workflow.VisualDesigner.Spx.WorkflowModuleModel, Workflow.VisualDesigner.Spx, "
           "Version=1.8.0.323, Culture=neutral, PublicKeyToken=null")            # 133B
WF_MODEL = "WorkflowModuleModel"
FF = b"\xff\xff\xff\xff"                          # 模块名与模块 JSON 之间的填充标记

ASM = f"Lib.MGISP_960.VisualDesigner.Spx, Version={SW}, Culture=neutral, PublicKeyToken=null"
CORE = f"Common.WorkflowDesigner.Spx, Version={SW}, Culture=neutral, PublicKeyToken=null"

def R(s):
    b = s.encode("utf-8") if isinstance(s, str) else s
    return struct.pack(">I", len(b)) + b

J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))

def posinfo(n):
    return {"Name": f"POS{n}", "KitName": None,
            "PosType": 1 if n == 5 else (10 if n == 24 else 0),   # POS5 高板位 / POS24 垃圾桶
            "Available": True, "Comment1": None, "Comment2": None,
            "HaveCoverPlate": False, "IsNeedReplace": True,
            "IsAllowGripperAction": n > 4}                        # POS1-4 禁机械臂夹取

def deck(name, is_main):
    return {"Name": name, "IsMainDeck": is_main,
            "DeviceConfigName": "2" if is_main else None,
            "PosInfos": [posinfo(n) for n in range(1, 25)]}

workflow = {
    "ActivityType": f"Common.WorkflowDesigner.Spx.Core.GlobalSequence, {CORE}",
    "ActivityName": "GlobalSequence", "DisplayName": "Workflow",
    "GlobalVariables": [],
    "Activities": [{
        "ActivityType": f"Lib.MGISP_960.VisualDesigner.Spx.Workflow.Commands.Initialize, {ASM}",
        "ActivityName": "Initialize", "DisplayName": "Initialize",
        "IsEnabled": True, "Comment": "Initialize"}]}

# ── 组装记录流（布局见 09 §三）──────────────────────────
blob = b"".join([
    R("Release V1"), R(PROJ_NAME),
    R("2"), DT, DT,                                # 配置号 + 创建/修改时间戳
    struct.pack(">I", 3),                          # 模块计数：MainDeck+Workflow+DESK2
    R(DECK_TYPE), R("\\MainDeck/"), FF, R(J(deck("\\MainDeck/", True))),
    R(WF_TYPE), R(WF_MODEL), FF, R(J(workflow)),
    R(DECK_TYPE), R("DESK 2"), FF, R(J(deck("DESK 2", False))),
])
open(OUT, "wb").write(blob)

# ── 自检：重扫记录流 + 结构断言（生成器同款扫描器口径）──
data = open(OUT, "rb").read()
recs, i = [], 0
while i < len(data) - 4:
    n = struct.unpack(">I", data[i:i + 4])[0]
    if 2 <= n <= 500000 and i + 4 + n <= len(data):
        try:
            t = data[i + 4:i + 4 + n].decode("utf-8")
            if sum(1 for c in t if c.isprintable()) / len(t) > 0.92:
                recs.append(t); i += 4 + n; continue
        except UnicodeDecodeError:
            pass
    i += 1
assert i == len(data), "尾部存在无法解析的残留字节"
assert len(recs) == 11, f"记录数 {len(recs)} ≠ 11"
# 与生成器 recs_from_tpl 的索引约定逐位核对
expect = ["Release V1", PROJ_NAME, DECK_TYPE, "\\MainDeck/", '{"Name"',
          WF_TYPE, WF_MODEL, '{"ActivityType"', DECK_TYPE, "DESK 2", '{"Name"']
for k, head in enumerate(expect):
    assert recs[k].startswith(head), f"T[{k}] 不匹配：{recs[k][:40]}"
count_off = 14 + 4 + len(PROJ_NAME.encode()) + 5 + 16
assert struct.unpack(">I", data[count_off:count_off + 4])[0] == 3, "模块计数 ≠ 3"
json.loads(recs[4]); json.loads(recs[7]); json.loads(recs[10])   # 三大 JSON 载荷可解析
# 布局级硬解析自检（无启发式，防扫描器假咬合）：
off = 14 + 4 + len(PROJ_NAME.encode())
def _rec():
    global off
    n = struct.unpack(">I", data[off:off + 4])[0]
    s = data[off + 4:off + 4 + n].decode("utf-8"); off += 4 + n
    return s
assert _rec() == "2"; off += 16 + 4                     # '2' + DT×2 + 计数
for is_wf in (False, True, False):                      # MainDeck / Workflow / DESK2
    _rec()                                              # 模块类型名
    if is_wf:
        assert _rec() == "WorkflowModuleModel"
        assert data[off:off + 4] == FF; off += 4        # Workflow：FF 即 null 名占位
    else:
        _rec()                                          # Deck：真名记录
        assert data[off:off + 4] == FF; off += 4
    n = struct.unpack(">I", data[off:off + 4])[0]
    json.loads(data[off + 4:off + 4 + n]); off += 4 + n
assert off == len(data), "布局解析后存在残留字节"
print(f"✓ 合成 {OUT}（{len(data)}B，11 条记录，SW={SW}）")
print("  自检：记录流完整 / 索引约定匹配 / 三大 JSON 可解析 / 模块计数=3 / 布局级硬解析零尾余")
