# WD 工程文件（.wfp）· 从说明书/spredo 生成

> 定位：主链路是"说明书 → spredo + wfp 双版本"。本参考讲 wfp 的格式与两条生成路径：
> 路径A（说明书直接生成）＝按活动 schema 拼装 JSON；路径B（spredo 转换）＝
> `scripts/spredo转wfp_生成器.py` AST 自动转换（已实战：一步法 444 节点工程）。

> 格式结论来自对 1.9.0.395/398 运行环境的系统分析（两版结论一致；生成器与
> schema 的程序集版本串现统一为 **395**——作者现场实机版本，2026-09-10 实测
> WDesigner 与四个 Spx DLL 均为 1.9.0.395；现场为其他版本时用 `--sw` 同步替换
> ——版本不匹配时 .NET 反序列化**确证拒载**，实战见踩坑库"wfp 拒载诊断树"），
> 已固化为正文（记录流布局/转换规则）与 `scripts/wfp活动schema.json`，
> 日常使用自含、无需任何外部材料。

## 〇、项目目录同含 .wfp 与 .python——只认 .wfp

**960 项目文件夹通常同时有 `.wfp` 和 `.python/`，要读流程永远读 `.wfp`：**

- `.wfp` = WDesigner 工程源头，用户每次保存即最新（头部还带创建/修改时间）；
- `.python/` = 从 wfp **导出**的执行脚本，是产物不是源——机器里"慢慢导出更新"，
  天然滞后于 wfp（改了工程没重导出时整个过时，见踩坑 #14）；
- 判断"流程现在是什么"只看 wfp；只有怀疑有人绕过 GUI 手改过 .python 时，
  才两份 diff 找不同步（§六 决定性映射）。

## 一、格式分析背景

.wfp 记录流布局与活动 schema 的结论均已固化在本文与 `scripts/wfp活动schema.json`，
按"格式规范 + schema 白名单"使用即可；本文不展开分析过程。

## 二、软件结构（装好后什么在哪）

| 目录 | 内容 | 价值 |
|---|---|---|
| `Engineer/Lib/spredo/__init__.py` | **spredo API 完整源码**（245 行） | API 一手来源，写脚本直查 |
| `Engineer/Lib/head/spx.py` | 台面检查/移液底层（loose_check@852, mvkit_redo@1208, prompt@184） | 报错调试对照 |
| `Engineer/Lib/` 其余 | Python 2.7 标准库（运行时） | — |
| `Engineer/py/test.*.py` | 官方测试样例（dialog/grasp/axis/barcode/csv…） | API 用法范例 |
| `Engineer/ScriptLib/ZLIMS/` | 随机应用脚本全套（DNA提取/gDNA归一/建库/分选/Pooling/DNB/环化…zh-cn+en-us） | spredo 范例库 |
| `WDesigner/Config/DeckAllPos/Pos/N.json` | 各台面配置的板位定义（PosType/Available/IsAllowGripperAction） | 台面配置号对照 |
| `WDesigner/Libs/*.Spx.dll` | 设计器核心（.NET 程序集） | .wfp schema 参考 |

## 三、.wfp 工程文件格式（决定性结论）

**完整字节布局（2026-08-31 逐段实锤，v1.3 全对齐）**：
```
[REC]Release V1 → [REC]工程名 → [REC]'2'(配置号) → [GAP]DateTime×2(16B裸字节)
→ [REC]int32(模块计数N)+int32(121) → [GAP]Deck类型名121B(裸)
每模块 N 个： [REC]模块类型名 / [REC]模块名 / [GAP]0xFFFFFFFF×1 / [REC]模块JSON
模块序：MainDeck → Workflow → DESK 2 → DESK 3(每次换台+1)
```
⚠️ 三个字节级陷阱（全踩过）：① 模块名后必须有 4 字节 0xFF 填充标记；
② 头部 int32=模块计数必须与实际一致；③ Deck 类型名的 121B 块紧跟模块计数。
**2026-09-10 精确实锤（逐字节硬解析双样例）**：121B/133B"裸字节"实为**普通文本记录**
（.NET 程序集限定名，`Deck.VisualDesigner.Spx.DeckModuleModel, …Version=1.8.0.323…`/
`Workflow.…WorkflowModuleModel, …`），可程序化合成；`FF×4` 在 Deck 模块=分隔标记、
在 Workflow 模块=**null 名占位**（Workflow 无模块名记录，FF 后直接 JSON）。
模块类型库版本 1.8.0.323 与软件版本无关恒定；头部 DateTime×2 为 16B 时间戳常量
（各文件不同、创建=修改，无语义，照抄即可）。活动 JSON 见下。

**.wfp = 自定义记录流（未加密）：每条记录 = int32 大端长度前缀 + UTF-8 内容**。
2026-08-30 PoC 实测：改工程名（含长度前缀重算）后记录流完好；台面/流程两大 JSON 完全可解析。
（修正早前"BinaryFormatter"的判断——实际是更简单的长度前缀记录流。）

```
BinaryFormatter 记录流
 ├─ "Release V1"                     根
 ├─ 工程名字符串（如 "My_Project"）
 ├─ .NET DateTime ×2                 创建/修改时间
 ├─ DeckModuleModel  (Deck.VisualDesigner.Spx, v1.8.0.323)
 │    └─ JSON: {"Name":"\\MainDeck/","IsMainDeck":true,"DeviceConfigName":"2",
 │        "PosInfos":[{"Name":"POS1","KitName":...,"Comment2":"50...",
 │        "HaveCoverPlate":false,"IsNeedReplace":true,
 │        "IsAllowGripperAction":true}, ...POS1-24]}
 └─ WorkflowModuleModel (Workflow.VisualDesigner.Spx)
      └─ JSON: {"ActivityType":"...GlobalSequence...", 活动树：
           Block → [Report{Step}, Dialog, Parallel, Loop,
           液体操作Activity(Lib.MGISP_960.VisualDesigner.Spx.Workflow...)]}
```

**关键映射**：JSON 的 `PosInfos` 字段 ↔ spredo `first_feature` 7字段一一对应
（KitName=耗材型号，Comment=名称，HaveCoverPlate/IsNeedReplace/IsAllowGripperAction）。

**版本兼容性（wfp 特点，2026-09-10 实战）**：
1. **wfp 与软件版本强相关**——每条记录写死程序集限定名（含 `Version=`），
   .NET 反序列化按版本**精确匹配**。⚠️ 但"多余字段拒载"在 2026-09-10 Oligo
   案例被**证伪**：395 成功打开含新版排空字段（EmptyForDispenseDely 等）的
   文件——活动树经 `RootObject:JObject` 动态解析，字段层天然宽松；
   schema 白名单仅作生成器的防御性过滤，不是拒载依据。
2. 兼容性是**单向**的：高版本软件可打开低版本文件（398 开 395 可；395 现场
   打开 1.8.0.323 老工程成功例），低版本打不开高版本产物须个案验证——
   版本串精确匹配仍是红线，但"395 拒 398"当时归因存疑（见踩坑 §20，
   同期存在布局错位问题未排除）。
3. 现场间传文件铁律：**对齐版本最低的机器**；本 skill 生成器/模板默认 395
   （作者现场实机，2026-09-10 实锤），他版现场 `--sw` 同步。
4. "系统无法读取此项目文件"**先看日志再分析内容**：`C:\MGISP-960\WDesigner\Logs\Logs_日期.txt`
   （log4net，完整异常堆栈）。诊断树见踩坑库 §20。

## 四、生成 WD 工程的可行路径（模板改造法）

1. **骨架**：取一个同版本结构的现有 .wfp（作者本地有两个原厂样例，
   路径见语料索引 S5）。**2026-09-10 起不再依赖原厂样例**：
   `scripts/最小骨架wfp_合成器.py` 按本文 §三布局零依赖合成单换台最小合法工程
   （产物 `scripts/最小骨架模板.wfp`，`--sw` 可切 395/398）——
   骨架段与原厂样例 byte-diff 对齐，以它为模板生成 444 节点级工程与原厂模板
   产物载荷 byte 级一致；操作与验证步骤见 `docs/生成WFP文件操作指南.md`
2. **解析**：按 BinaryFormatter 记录格式（NRBF 协议）解析记录流，定位两大 JSON 载荷
3. **替换**：按 payload JSON schema 构造新的台面/流程 JSON，替换载荷并重算长度前缀
4. **验证**：✅ **2026-08-30 PoC 实机验证通过**——改工程名生成的 TEST.wfp
   在 WDesigner 正常打开、保存后 MGISP-960 控制软件正常加载（用户截图确认）。
   **.wfp 程序化生成全链路打通**
5. 手术式修改要点：只动目标记录（重算其长度前缀），其余字节原样保留；
   记录布局（顺序流）：格式版本→工程名→DateTime×2→Deck类型名→Deck名→台面JSON→
   Workflow类型名→Workflow名→流程JSON。注意 JSON 内字符串值可能为 null（解析时防 None）。
6. 深挖 schema：在实机环境中对照类型定义补充（新活动类型先小样验证再固化）

**结论：WD 工程可以直接程序化生成（全链路已实机验证），不再只能给设置指南。**
**生成器 v1 已建**：`scripts/spredo转wfp_生成器.py`（源自"生成wfp_一步法.py"）——
AST 解析 spredo 脚本 → 活动树 JSON + 台面 JSON → wfp 记录流。首个产出：
一步法 `RNA_Onestep.wfp`（168KB，444 活动节点，MainDeck+DESK2 双台面，
顺序解析自检通过）。已实锤的转换规则：
- 活动类型全名 = `Lib.MGISP_960.VisualDesigner.Spx.Workflow.Commands.<Name>, ...Version=1.9.0.395...`
- 数值参数→字符串；WellType/Tips/LoopType/Direct/PCRType/TempType 保持 int
- Position='POS21'→'21'；Well '6A'→Col='6' Row='1'
- empty() = Dispense 活动 + IsEmpty:true
- 换台 = UpdateDeck(Deck='DESK 2') + 文件尾追加 DESK 2 台面记录
- PosType 编码：0普通/1=POS5高板位/**2=POS7 专属**（2026-09-04 实测 8 个真实工程
  全部如此，与该位有无枪头盒无关）/3 PCR空/4 PCR有板/6磁架/8振荡/9温控/10垃圾桶；
  **Available: 仅空PCR位(3)=false，有板PCR位(4)=true**（v1.7 实机教训：置false→台面灰→引用操作全红）；grip: POS1-4 false 其余 true
- 台面 PosInfo: KitName/Comment1-4(C1=C3,C2=C4)/HaveCoverPlate/IsNeedReplace/Version=1
- 并行规则：连续 parallel_block 提交 + Wait 触发 → Parallel(Branches=[Block...])
- TempSet: TempType=0(TargetA)/Target=温度串——原厂 Parallel 分支实例背书
v1 已知限制：require2 弹窗不转换（PCR 固定 PCR_14C，界面可改）；
TempSleep/Parallel内Block 的字段为推断（无原厂实例），WDesigner 打开报错时按报错修。
**活动语义官方出处已获得**（HelperDoc S10）：Require=列表型/输入型/多样型、
Variable/Condition（And/Or/嵌套/len()）、Loop 三模式（按次数/按变量 0..n-1/按列表）、
Async+WaitAsync、LanguageCondition（按软件语言走分支）、Dialog/Require 超时可选
（默认 2h 可改）——wfp 的 JSON 字段映射靠格式解析，语义对照有了权威基准；
官方指令全集（移液器 5 + 机械臂 2 + PCR 4 + 温控 2 + 振荡 2 + 交互 4 + 常规 12）
即活动类型白名单的官方参照。

## 五、源码级 API 勘误/补充（vs 之前行为对照法）

- `temp_sleep` 与 `temp_sleep_a` **源码等价**（都是 `temps_sleep_redo('TempA')`）——
  当年 NoneType 判断本就是误诊（真因 POS20 has kit，见 08 踩坑实录）
- 温控多通道：`temp_a/b/c/d/e/f(t)`、`temp_sleep_a..f()`（A-F 六模块可选）
- spredo 里 `initialize` 存在（WD 脚本用的）；我们直写版用 `init(spx96)` 即可
- **新发现的隐藏 API**：`hoodon/hoodoff/hoodspeed`（舱门）、`lighton/lightoff`（照明）、
  `uvon/uvoff`（UV消毒）、`lock/unlock`、`scan/scans/export_barcodes`（扫码）、
  `grasp/loosen`（显式抓放板）、`jc`（?）、`direct_*` 振荡方向组（逆时针/顺时针/
  对角线/上下/左右）、`go_to`、`load_tips_with_retry`、`temp_set_random`
- PCR 双组：`a_pcr_*` 与 `b_pcr_*`（两组 PCR 仪）+ `*_get_temp` 读温

## 六、2026-08-31 格式补充（V2.2→V2.3 对比实战）

- **记录流布局精解**：`Release V1` → 工程名 → `"2"`（各 4B 长度前缀）→ NRBF
  DateTime×2（各 8B：`0x08`+7B，无前缀）→ int32 分隔值（如 `3`=后续模块数）→
  后续均为 4B 大端长度前缀记录（模块类型名/模块名/JSON 载荷交替）。带换台的
  工程文件尾会追加第 2、3 个台面 JSON（`DESK 2`/`DESK3`，`IsMainDeck:false`）。
- **决定性映射：`UpdateDeck(DESKx)` 活动 ↔ 导出 py 的 `update_feature+binding_map`
  双块**——WD 里删"换台声明块"（如弹窗②后导致 `empty POS19 is None` 的那次热修）
  在 wfp 层面就是删 1 个 UpdateDeck 节点 + 对应 DESKx 台面记录（台面记录数同步减 1）。
  流程中途加 UpdateDeck = 中途全量重置板位绑定，等价于踩坑实录里的 binding_map 全量重置。
- 流程 JSON 与 py 导出严格同源：字段级 diff 活动树即可核验"改了工程但没导出 py"
  （例：V2.3 wfp 已改 Delay/Z 值而 .python 仍为旧导出——交付前必须重导出或声明以
  wfp 为准）。活动树拍平顺序：GlobalSequence→Block/Parallel/Branches/Body/Activities
  深度优先，与 py 执行顺序一致，可直接逐行对位。

## 七、2026-09-05/06 程序化直改（V2.9 全程实战，往返字节一致已验证）

**改任何字节前先做往返字节级一致验证**：parse → 按 §三布局重组 → 与原文件
逐字节比对相等，才允许动 JSON。序列化两个关键参数缺一不可：
`json.dumps(wf, ensure_ascii=False, separators=(',', ':'))`（ensure_ascii 影响
CJK 转义、separators 影响空格）；活动数值字段一律字符串（'150' 非 150）；
回写重算每条记录 4B 大端长度前缀，21B 头与模块间 4B ff 原样保留。

**断言式直改流程**（防误伤，捕获+建库双段交付实战全程使用）：
1. DFS 拍平活动树（GlobalSequence→Block/Parallel→Branches/Body/Activities）
2. 定位用 **pred + assert 计数**（如"P21 吸 108 且 Z=3.8"必须恰命中 1 处），
   绝不按序号猜——同名操作多处出现（循环/分装）时尤其如此
3. 改字段 → dumps → 回写；插入活动用 deepcopy 兄弟节点改造
4. **安全闸**：写盘前账本液面 ≤0 拒写（曾因补丁吞语句全液面归零）；写后重
   parse 验尾字节 = 0
5. **用户在 WDesigner 手改后对账**：重 parse → 与上次审计快照逐活动 diff →
   重跑账本审计五项（排空带宽/吸液深度/混匀双约束/⚠裁决/尾字节）

首例：捕获+建库两工程全程直改交付（WDesigner 打开正常、模拟通过），
工具为项目 `09_wfp工具/`（wfp_lib 解析器 + 账本 + 各修正器）；本 skill
`scripts/账本_全流程液量模拟_模板.py` 内嵌同源解析器（只读不写）。

## 八、产线惯例对齐（Reference-first · 2026-09-10 实战沉淀）

> 背景：用最小骨架模板+生成器从零生成的 wfp **能打开但设计贫瘠**（台面缺位、
> 流程平铺无 Block、活动全默认名）——用户退回。根因：最小骨架只是**字节锚点**
> （9 条固定记录），不是质量基准；生成器转换的 spredo 脚本本身写得太"平"
> （纯串行、无并行块），且生成器只覆盖语法子集。
> **规范化质量基准 = 现场现役 .wfp（Reference），不是模板。**

### 八.1 Reference-first 三步

1. **S0 索要 Reference**：请用户提供一个现役 .wfp（**只读承诺，绝不可改**——
   用户明确警告过）。从它**实证**两件事：软件版本串（看任意活动 ActivityType 的
   `Version=`）+ 台面 24 位定义模式。禁止凭档案/记忆拍版本。
2. **提取惯例档案**（对 Reference 逐项解析，一次成本，固化复用）：
   - **台面**：24 位全定义（含空位），每位 13 字段；空位 KitName=null 但
     PosType 按物理功能声明（磁架 6/温控 9/振荡 8/垃圾 10）；封闭 PCR 位
     `PosType:3 + Available:false`；有板 PCR 位 `PosType:4`；
     Comment1/2 = 新旧状态+用途（含装量标注），Comment3/4 成对（双语界面）
   - **根结构**：Initialize + 少量 Block/Parallel（产线工程根下仅 5-9 个活动）；
     逻辑按化学阶段装 **Block**（DisplayName=阶段语义名）；开机
     **Parallel** = PCR 预热分支 × 首段液体操作分支
   - **等待分工**：磁吸澄清/乙醇静置/干燥等**非温控等待用 Delay 活动**；
     只有需要控温的孵育才 PcrRun；收尾 **PcrStop**
   - **语义 DisplayName**：全活动中文命名（"试剂源吸取·XX 50µL"、"排空入废液"、
     "混匀120µL×15·Z3.5↔10.7"、"循环·XX×12列"）——画布可读性核心
   - **字段级**：Block/Parallel 子活动键 = `Activities`；Loop 子活动键 = `Body`；
     PcrRun 方法名在 `Method: {Text, IsUseVariable, VariableName, DisplayName}`
3. **生成链（2026-09-10 定，builder 优先）**：
   - **首选 = `scripts/wfp_builder.py` 直接生成**（用户需求：不经 spredo/转换器）
     ——API 直构活动树（block/parallel/loop/dely/pcr_stop/液体），语义命名与
     循环公式生成时即写；样板 scripts/wfp_builder_示例.py（自证：与参考工程字段零差异）。
   - 兼容 = 已有 spredo 脚本时：脚本按惯例组织（`parallel_block` 开机并行、
     阶段 report() 划界、`dely()` 非温控等待、`pcr_stop_heating()` 收尾）→
     `spredo转wfp_生成器` 转换 → `scripts/wfp后处理_模板.py`（阶段 Block 分组 +
     语义命名 + 版本串归一；CONFIG①~⑤ 换项目真值，示例全假名）。

### 八.2 96 头/8 头语义（部分板样本的通道分工硬约束）

96 头只有**两种模式**：`Tips:96` = 全板一次（Col/Row=基准位）、`Tips:8` = 单列
（仅 POS5 取头，第 12 列移液头）。**没有"96 头逐列"**。因此：
- 样本不满板（如 4 列）时，小体积试剂分装/磁珠/洗脱/产物**必须 8 头逐列**
  （储液板装不满 96 孔，96 头全板吸会吸空孔）
- 96 头全板任务只适合"储液与目标都天然整板"的操作：弃上清、乙醇洗
  （乙醇板/废液板整板装）。注意：会把液体打到样本板空列——空列污染无化学
  影响、多耗试剂，设计时要明示并算进装量
- 8 头逐列的总列数 >12 时需要换盒：把换盒点**嵌进既有 PCR 温育窗口或弹窗**
  （换盒提示写进弹窗文本），不新增人工干预次数

### 八.3 交付前结构对齐检查（新增，生成器自检之外）

| 检查 | 通过标准 |
|---|---|
| 根下活动数 | 个位数（Initialize+Block/Parallel），不是几十个平铺 |
| 台面 | MainDeck 与每个 DESK 均 24 位全定义；禁用位写法与 Reference 一致 |
| 版本串 | 与 Reference 逐类型一致（`grep Version=` 全文件归一） |
| 语义命名 | 无裸 "Aspirate/Dispense" 默认名（Initialize/门开关除外） |
| 文件头 | hexdump 前 48B：`Release V1` + 工程名记录完整（post 写出 bug 检测） |
| parse 断言 | 尾余=0；活动统计与脚本 AST 对得上 |

### 八.4 实战坑录（详见 08 #21–#24）

① 版本串 398 文件在 395 现场软件报"项目文件版本高，升级系统"——版本必须实证；
   等长字符串可字节级替换补救。② post 写出把字符串记录写成 r[1]（字符索引），
   文件头变 'e'/'r' 单字符记录——写出后必 hexdump 头。③ 生成器 `range(0,4)`
   双参 → LoopCount=0 全循环跳过；裸循环变量 Col→'None'（必须表达式 col+1）；
   行尾注释可致语句块吞行。④ 8 头操作漏 `'Tips':8` 默认按 96 全板执行。
