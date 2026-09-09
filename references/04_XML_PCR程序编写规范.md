# PCR 温控程序 XML 编写规范（MethodSet 结构）

> 实例参考：一步法定稿项目的 PCR XML（文件名与路径见语料索引 S7）

## 一、文件结构

```xml
<?xml version="1.0" encoding="utf-8"?>
<MethodSet>
  <PreMethod methodName="START" dateTime="...">        <!-- 预热/待机 -->
    <TargetBlockTemperature>25</TargetBlockTemperature>
    <TargetLidTemp>110</TargetLidTemp>
  </PreMethod>
  <Method methodName="FRAG_85C4MIN" dateTime="...">
    <Variant>960000</Variant>
    <PlateType>0</PlateType>
    <FluidQuantity>0</FluidQuantity>
    <PostHeating>true</PostHeating>                    <!-- 结束后保持末步温度 = hold -->
    <StartBlockTemperature>4</StartBlockTemperature>
    <StartLidTemperature>110</StartLidTemperature>
    <Step>
      <Number>1</Number>
      <Slope>4.4</Slope>                               <!-- 升降温速率 -->
      <PlateauTemperature>85</PlateauTemperature>
      <PlateauTime>240</PlateauTime>                   <!-- 秒 -->
      <OverShootSlope1>4.4</OverShootSlope1>
      <OverShootTemperature>6.6</OverShootTemperature>
      <OverShootTime>0</OverShootTime>
      <OverShootSlope2>2.2</OverShootSlope2>
      <GotoNumber>0</GotoNumber>                       <!-- 循环回跳目标步 -->
      <LoopNumber>0</LoopNumber>                       <!-- 循环次数 -->
      <PIDNumber>1</PIDNumber>
      <LidTemp>110</LidTemp>
    </Step>
    <Step>...</Step>
    <PIDSet/>
  </Method>
  <!-- 更多 Method... -->
</MethodSet>
```

## 二、手工说明书温度表 → XML 转换规则

| 手工写法 | XML 写法 |
|---|---|
| `85℃ 4 min` | `PlateauTemperature=85, PlateauTime=240`（**min×60 变秒**） |
| `4℃ hold` | 末尾加一步 `4℃×5~10s` + `PostHeating=true`（运行完保持=hold） |
| 热盖 `105℃` / `off` | **平台惯例统一 110**（全项目+原厂 XML 历史一致；960 开孔板场景热盖=防蒸发罩，与手动管式 PCR 不等价。如用户强制对齐手册改 105 也可，无 off 写法） |
| 循环 `[98℃15s,60℃30s,72℃30s]×14` | 三步各一条 Step，循环末步 `GotoNumber=循环首步号`，`LoopNumber=13`（**N-1**） |
| 预热/待机（如降 4℃ 备用） | `PreMethod`（START）或普通方法（如 25-4 / 4-25） |

## 三、循环数可选化（弹窗选 cycles）标准做法

**触发条件**：手动说明书给出多档推荐循环数（按投入量/样本类型分档），且用户
在理解表确认阶段**拍板要做弹窗选择**（必问项，见 00 §四问题 7）。用户不做
选择模块时，只写一个固定循环数的方法即可。

1. XML 里把 PCR 方法**克隆 N 份**：`PCR_10C` … `PCR_16C`，
   每份只有 `LoopNumber` 不同（= N-1，如 14 循环→13）
2. 脚本开机弹窗：
```python
pcr_method = 0
while pcr_method == 0:
    sel = require2({'PCR_cycles':['10','11','12','13','14','15','16']}, {'':''})
    if sel.Item1[0] == "10": pcr_method = 'PCR_10C'
    ...
pcr_run_methods(method=pcr_method)
```
3. 说明书注明循环数可选范围

## 四、命名与验证

- 方法名规范：`{步骤}_{温度}{时长}`（可按需加项目前缀，但勿用公司名），如 `FRAG_85C4MIN`、`FIRST_STRAND_V3`
- 验证：`xmllint --noout 文件.xml`；Goto/Loop 配对人工核对（每方法循环体首末步闭合）
- 方法名即脚本的 `pcr_run_methods(method='...')` 引用键——**改名必须两头同步**

## 五、典型方法簇模板（RNA 建库全套，与手工说明书 100% 对齐的实例）

| 方法名 | 步骤 | 对应手工 |
|---|---|---|
| START | 25℃ 待机 | 开机预热 |
| oligodT_cap | 80℃×120s → 25℃×300s | 捕获结合/洗脱（热盖105→平台110） |
| FRAG_85C4MIN | 85℃×240s → 4℃ | 片段化 85℃ 4min 4℃hold |
| FIRST_STRAND_V3 | 25×600→50×900→70×900→4℃ | 一链 25/50/70℃ |
| SECOND_STRAND_V3 | 16×1800→65×1800→4℃ | 二链+末修 16/65℃ |
| LIGATION | 20×900→4℃ | 连接 20℃ 15min |
| PCR_10C..16C | 98×45 → [98×15,60×30,72×30]↺ → 72×300 → 4℃ | 扩增 |
| 25-4 / 4-25 | 单步过渡 | 模块降温/回温 |

> 主体温度（模块温度/时间/循环）必须与手工说明书逐项核对——这是化学核心；
> 热盖 110 是平台惯例（见二），差异要向用户披露让其拍板。

## 六、PCR 仪硬件限速与编辑软件版本（官方培训课件 5）

### 硬件限速（Limits——XML 参数取值红线）

- 最大**升温**斜率 **4.4 K/s**；板温 **4–99°C**；单步最短 **1 s**（slope+plateau）
- **降温**斜率上限取决于每孔体积与温度段（官方 Limits 截图，μL=每孔反应体积）：

| 温度段 | 96×250μL | 96×100μL | 96×50μL |
|---|---|---|---|
| 99→60°C | 2.2 | 1.8 | 2.0 |
| 60→40°C | 1.4 | 0.8 | 1.3 |
| 40→20°C | 0.8 | 0.5 | 0.75 |
| 20→4°C | 0.25 | 0.18 | 0.25 |

体积越大降温上限越低——大体积程序别照抄小体积的 Slope/OverShoot 斜率，
超出对应档上限实机达不到或报错。

### PCR 程序编辑器（官方 HelperDoc S10 p60–67：按机型配置三选一）

| | 基础版（SILA XML Script Editor v3.6.x） | ODTC（V2.19.6.0 / V3.0.2） | MTC-96A（品牌 B，v1.7.0） |
|---|---|---|---|
| 安装 | 无需安装，双击直接用 | 需要安装 | WD 工具栏进入 |
| 热盖 | **固定 110°C 不可改** | Start temperature LID：unlock 后可编辑 | 勾选热盖后设置（界面例 110） |
| 温度范围 | 板温 4–99°C | — | **4–105°C**（节温度编辑框 Range） |
| 保存 | 直接 .xml（Method→Save Method Set） | 先存 **.sep**（ScriptEditor Project），**不能直接导入** 960 软件；需 **Tools→Export MethodSet→另存 .xml** | 可导入 .mset/.xml/.sep 并转换；导出脚本 |
| 特有项 | type: temperature initialization / method；wall type SKIRTED 96；plate type BioRad | 程序三类：Temp. Init. Steps / Methods / PCR；**Max cooling/heating slopes**（是否以最大温度升降，无特殊要求可勾 On）；Start temperature Mount | 节（step）图形化编辑 + 循环 Times×N；加液量；温度保持 |

- ODTC 勾 **Max cooling/heating slopes = On** 即直接用硬件最大斜率（不手填 Slope）——
  与下方限速表互为替代
- 通用步骤五列：slope (K/s) / plateau temp (°C) / plateau time (s) / go to step / loops
- fluid quantity（反应体积）三档：10–29 / 30–74 / 75–100 μL

- 导入约束：**一次只能导入一个 PCR 程序集**，有多个需分多次导入（课程 8）；
  导入完成弹窗"重启软件后生效"。导入工具另带调试命令
  （GetParameters/SetParameters/ExecuteMethod 等），可单程序调试（课程 8 p16 截图）
- START 程序与"上一程序结束温度=下一程序开始温度"两条注意事项两版通用（与本文 §一/§二 一致）
