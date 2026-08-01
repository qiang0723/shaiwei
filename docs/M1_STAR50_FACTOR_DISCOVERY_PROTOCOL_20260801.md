# M1-1 科创50新价量因子发现协议

> 日期：2026-08-01（Asia/Shanghai）  
> 协议：`m1-star50-price-volume-v1`  
> 状态：`FROZEN_BEFORE_IMPLEMENTATION_AND_RESULTS`  
> DeepSeek 本批：40个完成响应、串行、硬上限 `$1`  
> 策略效果：`NOT_EVALUATED`  
> 生产授权：`none`

## 1. 研究问题与结果边界

本批只回答：在官方PIT科创50股票池中，受限OHLCV/VWAP表达式能否产生值得进入后续独立验证的
新因子假设。它不回答因子是否通过G1、策略是否有效、组合如何构建或能否接入生产。

P2-2C的权威`REJECT`仅适用于既有`Alpha158 + LightGBM + Top10/n_drop2 + 10日调仓`基线。本批
建立独立研究家族，不改旧公式、模型、组合、窗口或阈值，也不以旧P2结果作为DeepSeek反馈。旧失败
永久保留，科创50官方谱系与工程GO继续作为输入证据。

## 2. 结果前冻结的数据与时钟

- 股票池：`star50-official-pit-v2`，官方指数`000688.SH`，逐日成员由P2 v2官方谱系唯一驱动；
- 发现信号日：2020-08-03至2022-12-15，共577个官方交易日，每日严格50只；
- 标签：信号次日开盘至T+11开盘收益，即10个交易日持有期；最后一条发现标签于2022-12-30成熟；
- 封存期：2023-01-03至2025-12-31。本目标禁止读取候选在封存期的IC、收益、换手、成本或压力表现；
- 特征：仅`open/close/high/low/volume/vwap`，最长回看50个交易日；
- 中性化：当日已知申万一级行业和`log(total_mv)`；最小横截面30；
- 候选发现有效性：覆盖率至少90%、有效日RankIC至少400日，方向不在发现期翻转；
- 输入真身绑定P2-1 qlib整树、`member_days.parquet`、工程manifest和M1注册表哈希；任何漂移fail closed。

发现期后续价格只允许用于冻结标签成熟，不得扩张信号日。2023-01-03是封存期首个交易日，禁止用它
及其后数据挑选、修改或替换候选。

## 3. 生成、语义与多重检验合同

固定五主题各8次，共40个完成响应；每主题前4次独立生成，后4次只接收同主题本家族此前全部发现
反馈并作有界变异。空响应、截断、格式错、重复AST、语法/沙箱/语义失败全部计入家族`N=40`，不得
补位或因表现提前停止。跨股票池评价单元不计作新的生成尝试。

每个响应只能有一个严格JSON候选和一条安全DSL表达式。结构通过后、候选有效前必须通过语义门：
正文只能解释唯一表达式，禁止第二公式、替代算子、不同窗口、调参建议、封存期线索及收益/准入/生产
声称；模糊即拒绝且该次仍计N。旧D1-3A的语义违约保持STOP，不被本工程回溯改变。

40次完成后才按以下固定顺序机械锁定最多2个候选：绝对发现期RankIC降序、覆盖率降序、表达式token
升序、全局序号升序。少于2个有效候选则`PAUSE`。Top2只表示“待独立复核”，不是因子准入。

## 4. DeepSeek与费用

2026-08-01复核DeepSeek官方合同：`deepseek-v4-pro`、thinking enabled、reasoning effort high、JSON
Output；每百万token价格为缓存命中输入`$0.003625`、缓存未命中输入`$0.435`、输出`$0.87`。每次
最多16k输入/8k输出，40次全未命中理论上限`$0.5568`，本批硬熔断`$1`。费用或模型身份变化、usage
缺失、计费不确定、敏感输出都在下一请求前fail closed；未使用额度不自动授权新批。

官方合同来源：

- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/guides/json_mode/

API只接收系统提示、公开知识摘要、候选JSON schema和同主题脱敏发现反馈；不发送行情行、股票持仓、
本地路径、日志或任何凭据。密钥只从被Git忽略的`.env`窄传入一次性容器，不读取或打印其值。

## 5. 工程与账本边界

- 新代码置于独立M1模块；不继续向超过600行的D1热点文件堆入STAR50业务职责；
- 专用attempt/transport账本与忽略区产物根，不修改旧D1账本字节；全局`experiments.csv`只通过现有
  append-only入口写入一一对应的40个生成尝试；
- 一次性Docker任务必须非root、只读根、无端口、无Docker socket，只写本批产物、专用账本、全局
  实验账本和日志；只传`DEEPSEEK_API_KEY`，不传Tushare或飞书秘密；
- paid run前另立执行release，绑定协议、prompt、知识、registry、数据、代码、镜像和远端提交；
- 重放不得产生新API调用、账本行或不同哈希；`.BJ`、身份/哈希漂移、未知字段和跨层越权均失败关闭；
- 不修改或重启scheduler，不build/promote Top20候选，不影响2026-08-03 16:05一次性发布守护。

## 6. 本目标的机器终态

只有40次完成、语义/DSL/数据/预算/静态证据/幂等/双账本门全部通过，才能裁定
`GO_DISCOVERY_TOP2_LOCKED`；少于2个有效候选为`PAUSE_INSUFFICIENT_DISCOVERY_CANDIDATES`；任何致命
控制门故障为`STOP_CONTROL_GATE`。三者均保持`strategy_effective=NOT_EVALUATED`和
`production_authorization=none`。

本目标完成后仍须新协议才能做Top2对抗复核、人工经济解释、2023—2025封存验证或G1；不得在本批
中顺带执行。
