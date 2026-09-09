# spredo 语法规范（Python 直写版 · 写脚本前必读）

> 运行环境：WDesigner 系控制软件（内嵌 Python + spredo 模块）；存在多个发行版，细节有差异。
> 双验证源：原厂官方 RNA 脚本（官方语料发行版环境）+ DNA 验证版脚本（控制软件实机跑通）。
> 权威参考文件：官方 RNA 脚本 + DNA 验证版脚本（双验证源，本地路径见语料索引 S3/S4）

## 一、脚本头部固定结构（顺序不能错）

```python
# -*- coding: utf-8 -*-
"""docstring：项目说明"""
# 台面映射：开机初始状态
pos_type_map = {"POS1":"useless", "POS2":"useless", ...,
                "POS15":None, "POS20":[None,"shake"], ...}

#region HEAD
spx96 = globals().get("Spx96")
from spredo import *
init(spx96)              # most important
binding_map(pos_type_map)
shake.binding(spx96)     # 用了 shake_on/shake_off 必须有

def first_feature():
    """7 字段台面（见下）"""
    return [('Pos1', 'TipGEBAF250A', '去上清专用', 'NEW', False, True, ''), ...]
```

**pos_type_map 值 = 当时物理真实状态**（红线）：
| 写法 | 含义 |
|---|---|
| `None` | 空位 |
| `"耗材型号"` | 该位放着这块板 |
| `["耗材型号","shake"]` | 有板且振荡位 |
| `[None,"shake"]` | **空振荡位**（实机验证版 1_DOP.py line11 实机验证写法） |
| `"useless"` | 不可抓放（枪头位等） |

**first_feature / update_feature 元组 = 7 字段**：
`('Pos1', 耗材型号, 功能名称, 特性描述, 有盖板False, 台面显示标灰True, 标记)`
- 第 6 字段官方语义（课程 6/7 原文："[可选]在台面显示时是否标灰"）=
  **运行向导台面上该耗材是否标灰提示**（标灰 = 提示用户此位耗材不用动）；
  早期写法把它命名成"需更换"是推断，以官方"标灰"语义为准，顺序不能打乱
- 首字段 `'Pos1'`（大写 P 小写 os，不是 POS1）
- 标记合法集合仅：`'PCR' / 'MagRack' / 'Shaker' / 'Temp_Module'`（无 HigherPosition/Mag(DW)/Temp 等）
- 功能属性（磁架/振荡）由第 7 字段标记承载，与 pos_type_map 无关

## 二、换台写法（弹窗 + 台面更新）

```python
dialog('请执行换台：\r\n【取出丢弃】...\r\n【保留】...\r\n【放入】...\r\n确认后点击【继续】。')
SWAP1_POS = [('Pos1', ...7字段...), ...]     # 全 24 位重新声明
update_feature(SWAP1_POS)
pos_type_map = {...新的物理真实状态...}
binding_map(pos_type_map)
```

## 三、API 全清单（控制软件验证过的形态）

### 液体操作（dict 参数）
```python
load_tips({'Module':'POS1','Col':1,'Row':1,'Tips':96})          # 96头整盒
load_tips({'Module':'POS5','Well':'6A','Tips':8})               # 8头单列（仅POS5）
aspirate({'Module':'POS17','Col':1,'Row':1,'AspirateVolume':50,
          'BottomOffsetOfZ':0.5,'AspirateRateOfP':50,'PreAirVolume':5,
          'PostAirVolume':0,'DelySeconds':0.5})                 # 8头加 'Tips':8
dispense({'Module':'POS13','Col':1,'Row':1,'DispenseVolume':27,
          'BottomOffsetOfZ':2,'DispenseRateOfP':100,'DelySeconds':0.5})
empty({...BottomOffsetOfZ/DispenseRateOfP/DelySeconds...})       # 排空吹净
mix({'Module':'POS15','Col':1,'Row':1,'SubMixLoopCounts':10,'MixLoopVolume':30,
     'BottomOffsetOfZ':0.5,'MixLoopAspirateRate':20,'MixOffsetOfZInLoop':0.5,
     'MixLoopDispenseRate':20,'MixOffsetOfZAfterLoop':6,
     'DispenseVolumeAfterSubmixLoop':8,'DispenseRateAfterSubmixLoop':20,
     'PreAirVolume':10,'SubMixLoopCompletedDely':0.5})
unload_tips({'Module':'POS24','Well':'1A'})                     # 不带 Tips 键
unload_tips({'Module':'POS1','Well':'1A','SafePointOfZ':15})     # 移动中避让
```
- 寻址两式并存：`Well:'1A'` 或 `Col/Row` 数字——同脚本可混用（官方脚本先例）
- dict 里 API 未定义的键**不报错 ≠ 忽略**（2026-09-09 纠偏）：`SecondRouteRate`（Z 二段速度）、
  `TipTouch*`（靠壁）均为有效参数——旧结论"会被忽略"曾致漏配靠壁，作废
- **靠壁 = TipTouch 参数组**（用户 2026-09-09 确认）：WD 指令进阶参数的官方功能；
  `OffsetX` 一般 **2mm 左右**（贴孔壁内缘），`Height` 按需求调（悬空打乙醇 = 液面上方蹭壁）。
  WD 导出语料实例：Height 15–22、OffsetX 2.5–3（13 §一排废液行，V2.2 产线实机验证）；
  spredo 纯直写环境键生效性待查 spredo 源码存档后标注

**物理硬约束与官方语义（课程 6/8，写参数前先过一遍）**：
- **枪头量程**：带滤芯 **2–165μL**、不带滤芯 **2–200μL**（官方保证）；吸液+前吸+后吸
  的总量不超量程（empty 排的正是这个总量）。产线有 165–200μL 实机通过先例
  （带滤芯超保证量程=精度参考而非运行必炸）；自检按 165 警告 / 200 报错两档判级
- **DispenseVolume ≤ 上一步吸液体积**（官方明示）
- 移液器速度 **0–250 μL/s**（参考数据）
- **8 头体积语义歧义（2026-09 发现，待实机终核）**：`AspirateVolume/DispenseVolume`
  在 `Tips:8` 时是**每通道**还是 **8 通道总量**？仪器标准语义=每通道；但一步法语料
  的 bulk 配制算术仅按"总量"读法才自洽（168.8×2 ≤ 400 源井），两种读法历史上并存。
  **写脚本必须全项目统一一种并自洽**（新项目按每通道编写，水跑用 1 列试吸称重终核）；
  审查时先判定被审脚本用的是哪种，再核体积账
- **BottomOffsetOfZ 可设负数、无限制**（官方明示；推荐默认极低正 Z 见 13 铁律 2）
- PreAirVolume 目的 = 使下一步排液更干净；PostAirVolume 目的 = 防止表面张力小
  的液体（如乙醇）漏液
- **load_tips 允许 POS1–24**（均需物理枪头盒）；**Row 只能为 1，Col 1–12**；
  Tips=8 时仪器使用移液头**第 12 列**；不写 Tips 默认 96
- mix 内部时序 = 前吸 → mix 吸液 → mix 排液 → 排空；`SecondRouteRate` = Z 轴
  第二段速度（默认 38，见 11 §二）

### 运动
```python
mvkit('POS17','POS19')    # 搬板：源位必须有板、目标位必须空（软件 loose_check）
home()                    # 归位（开头结尾各一次）
```

### PCR 仪（对应 XML 方法名）
```python
pcr_run_methods(method='FRAG_85C4MIN')
pcr_open_door() / pcr_close_door()
pcr_stop_heating()        # pcr_stop 不存在
```

### 温控模块（POS21/22）
```python
temp_set(6)               # 设定温度（℃）
temp_sleep()              # 等待到温（控制软件环境）；官方语料发行版环境为 temp_sleep_a()，同无参
```
官方映射（课程 6）：只配一台温控（Pos21）时 `temp_set` 与 `temp_a` 等效；
配两台时 Pos21=温控a、Pos22=温控b，`temp_set` 默认指 a。

### 振荡器（POS20）
```python
shake_on(1200, 1)         # 速率rpm, 方向（6 种：1逆时针 2顺时针 3↗ 4↘ 5上下 6左右，课程 6/7）
shake_off()
```

### 交互 / 并行 / 进度
```python
dialog('单参数字符串')      # 不是 4 参数（那是 WD 语法）
# 超时（官方 HelperDoc S10 p50/55）：WD 的 Dialog/Require 均可勾选"是否设置超时"，
# 默认 2h **可改**；倒计时结束未处理=流程停止。spredo 单参 dialog 的 2h 报错
# （08 #4）对应默认值；直写版能否改参 → 待查 spredo 源码 prompt/dialog 实现
PCR = require2({'PCR_cycles':['10','11','12','13','14','15','16']}, {'':''})
# WD 的 Require 有三种询问模式：列表型（=require2）/输入型（用户输数值）/多样型；
# spredo 语料只见列表型——输入型 API 是否存在待查源码
# 返回对象 .Item1[0] 取所选字符串；配 while 循环做选项映射
def blockA():
    pcr_close_door()
    pcr_run_methods(method='PCR_14C')
a = parallel_block(blockA)   # 后台并行（温育期间做别的）
a.Wait()                     # 等待完成；注意别漏括号
report(phase='接头连接', step='2/3混匀反应体系')   # 关键字参数，软件界面显示进度
```

## 四、控制软件环境 vs 官方语料发行版的 API 差异（实锤踩坑）

| API | 说明 | 用哪个 |
|---|---|---|
| `temp_sleep()` / `temp_sleep_a()` | **源码等价**（运行环境源码：两者都是 `temps_sleep_redo('TempA')`，2026-08-30 核对实锤；当年"控制软件环境无 _a"的判断是误诊，真因见踩坑实录#1） | 均可，习惯用 `temp_sleep()` |
| `log()` | 官方脚本用；控制软件环境未验证 | 谨慎起见不用 |
| 多温控 | `temp_a..f(t)` / `temp_sleep_a..f()` 对应 A-F 六个温控模块 | 按模块选 |

**API 核对来源**：控制软件安装目录 `Engineer/Lib/spredo/__init__.py`（245 行）
与 `Engineer/ScriptLib/` 随机应用脚本为最直接参照；写脚本遇到不确定的 API，
先与实机验证版脚本对照，仍存疑则上机单步验证。

排查法：脚本全部 API 与"实机验证版"（1_DOP.py / 2_libraryprep.py）逐一对照，
验证版没出现过的名字就是嫌疑。

## 五、双语版（en-us）

英文版 = 中文版**纯字符串映射替换**（docstring/dialog/report/台面 feature 字段），
零逻辑改动。验证方法（必须做）：AST 等价——所有字符串字面量置空后两版语法树
必须 `ast.dump()` 完全一致。生成器模板见 `scripts/生成英文版_模板.py`。
注意映射表**长串优先**替换（短词先命中会污染长串）。

## 六、WD 语法 → spredo 转换对照（如果从 WD 版迁移）

| WD（a_ 前缀） | spredo |
|---|---|
| `a_pcr_run("X")` | `pcr_run_methods(method='X')` |
| `initialize()` | `init(spx96)`（initialize 不存在） |
| 9 字段台面 + 'POS1' 大写 | 7 字段 + 'Pos1' |
| `dialog(msg, None, None, "2:00:00")` 4 参 | `dialog(msg)` 单参 |
| 台面 3 元组 / temp 二元 | 字符串式 pos_type_map |
| unload_tips 带 Tips 键 | Well 形态无 Tips 键 |
| report 位置参数 | 关键字参数 |
| Temp/Mag(DW) 标记 | Temp_Module/MagRack |
| Variable / Condition（官方 HelperDoc S10） | Python 变量 / `if`（条件支持 And/Or 多条件、嵌套、`len()`） |
| Async + WaitAsync（异步/等待异步） | `parallel_block` + `.Wait()` |
| LanguageCondition（按软件语言走分支，仅配 Report/Require/Dialog） | 无对应——双语弹窗官方解法，WD 版专属 |
| Loop 三模式：按次数 / 按变量（i=0..n-1）/ 按列表 | `for` / `range` / 列表遍历 |
