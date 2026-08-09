# autoquant-research

![一位头发花白的资深投资人用放大镜揭开一份漂亮的回测，发现底下藏着一份崩盘的回测，周围是研究闭环的图标和一座挂满失败案例的博物馆](docs/assets/hero.jpg)

<p align="center">
  <a href="https://github.com/Heihaierr/autoquant-research/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Heihaierr/autoquant-research/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg"></a>
  <a href="skills/"><img alt="Agent Skills" src="https://img.shields.io/badge/agent%20skills-7-blue"></a>
  <a href="https://github.com/Heihaierr/autoquant-research/stargazers"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/Heihaierr/autoquant-research?style=flat&color=yellow"></a>
</p>

<p align="center">
  <a href="docs/en/README.md">English</a> | <b>简体中文</b>
</p>

**一份自动化的量化研究方法论——严谨到能挑出假的 edge，高效到能把真的那个跑出来。**

一份系统化策略研究的 spec——覆盖 ETF、基金、个股，多资产配置、walk-forward
验证、诚实的业绩归因，以 portable Agent Skills 的形式打包，不是框架，没有
任何东西需要 import。装进 Claude Code、Cursor、Codex，或任何能读 Agent
Skills 的 agent，它就能把你的研究闭环从头跑到尾：先和你对一次目标，然后
自己去拉数据、搭并测试引擎、找机制、做诚实评测、下裁决、上线后持续对账——
中途不会再打断你，除非真的遇到只有你能拍板的分叉。

## 快速开始

<details open>
<summary><b>Claude Code</b></summary>

```bash
/plugin marketplace add Heihaierr/autoquant-research
/plugin install autoquant-research@autoquant-research
```
</details>

<details>
<summary><b>Cursor</b></summary>

```text
/add-plugin autoquant-research
```

或者直接克隆到 skills 目录：
```bash
git clone https://github.com/Heihaierr/autoquant-research ~/.cursor/skills/autoquant-research
```
</details>

<details>
<summary><b>任何支持 portable Agent Skills 的 agent</b></summary>

```bash
git clone https://github.com/Heihaierr/autoquant-research
```
把你的 agent 的 skill 目录指向 `skills/` 即可。这些 skill 都是纯 Markdown +
YAML frontmatter，没有任何运行时依赖。
</details>

装好之后，直接跟你的 agent 聊一个策略想法就行。`using-autoquant` 是所有其他
skill 的入口，它会先问你唯一一件它自己拍不了板的事——目标——然后把剩下的闭环
自己跑完。

想先看看效果，不急着接自己的数据？`templates/` 里带了两张现成的价格表，
断网、不需要任何 API key 就能跑完整闭环：

```bash
cd templates && pip install -r requirements.txt
pytest tests/ -q
PYTHONPATH=. python framework/walk_forward.py --config config.us.yaml --strategy s0_passive
```

## 为什么要做这个

市面上已经有工具能扫描你的回测代码，找出未来函数、漏算成本，它们有用——但
**静态检查能抓代码错误，抓不到推理错误。** "真实可执行的选池规则跑不过
基准，所以这就是事后选择偏差"这类结论，可以完全建立在算得没错的数字上，
结论却仍然是错的——因为把一个测出来的差距归因到正确的原因，是一次判断，
不是一个统计量，算术本身完全不会检查这次判断有没有走对。这就是这份闭环要
补的那一小块：把标准验证方法按正确的顺序串起来，并且在一个检验刚好通过、
即将被写成结论之前，把那些推理陷阱点出来。

## 研究闭环

`using-autoquant` 是入口。下面几个阶段它一个都不亲自执行——它只负责派发、
校验每一次交接，并让这个环转下去，中途不会打断你。

| | Skill | 负责什么 |
|---|---|---|
| | [`using-autoquant`](skills/using-autoquant/SKILL.md) | 入口：派发下面各阶段，并持有"什么条件下才允许打断你"那份封闭清单 |
| ① | [`framing-the-goal`](skills/framing-the-goal/SKILL.md) | 目标、载体、执行语义、成本模型。唯一与你对话的一步 |
| ② | [`building-the-foundation`](skills/building-the-foundation/SKILL.md) | 数据抓取与质检、引擎正确性测试，以及后续每个数字都要对照的被动基线 |
| ③ | [`running-experiments`](skills/running-experiments/SKILL.md) | 候选从哪来——机制地图、灵敏度排序、事前写死的裁决线——以及结果是否真的说明了什么：三层评测、错峰调仓、两档成本 |
| ④ | [`judging-the-round`](skills/judging-the-round/SKILL.md) | 把差距归因到某一层，走 SHIP / ITERATE / STOP 三个出口之一，走哪个都要入档 |
| ⑤ | [`shipping-and-tracking`](skills/shipping-and-tracking/SKILL.md) | 证据包、参数冻结，以及上线之后的三层对账 |

还有一个不是阶段，因此在上面这条链里没有位置：

| | Skill | 负责什么 |
|---|---|---|
| ★ | [`detecting-self-deception`](skills/detecting-self-deception/SKILL.md) | 按机械条件触发——Sharpe 超过 1.5、超额超过 2pp、一个裁决即将写下——而不是靠你判断结果"看起来不错" |

它是个环，因为真实研究要绕好几圈，而每次从 `judging-the-round` 绕回
`running-experiments`，带回去的都应该是一个没试过的机制类别，不是刚失败那个
方向的又一次重复。

每个 skill 也可以单独调用——"帮我评测一下这个已有的策略"直接进
`running-experiments`，"我现在有资金，今天该买什么"直接进
`shipping-and-tracking`——不需要从头走完整个闭环。

<p align="center">
  <img src="docs/assets/automation-chart.jpg" width="640" alt="红线：一路上都在打断、汇报，回测结束后直接崩掉。蓝线：只在一开始确认过目标，跑得更快，回测结束后照样往上走。">
</p>

## 和其他工具比

| | 一个普通的 coding agent | 回测框架（backtrader、vectorbt……） | 未来函数/泄漏 linter | **autoquant-research** |
|---|---|---|---|---|
| 是什么 | 一个空白的 prompt | 一个你拿来写策略的引擎 | 一个静态检查器 | 一套打包成 Agent Skills 的封闭研究闭环 |
| 抓代码错误（未来函数、时间戳泄漏） | 你问了才查 | 不抓 | 抓 | 抓，靠引擎正确性测试 |
| 抓推理错误（数字算对了，结论错了） | 不抓 | 不抓 | 不抓 | 抓——这就是它存在的理由 |
| 强制要求 walk-forward + 成本压力测试才能下裁决 | 不强制 | 不强制 | 不强制 | 强制 |
| 带一份能跑的参考实现 | 没有 | 有，生产级 | 没有 | 有，教学级——不是生产用的 |
| 需要 import 或依赖 | —— | 需要 | 有的需要 | 不需要——纯 Markdown，没有运行时 |

它是和另外三种工具配合用的：引擎用回测框架跑，代码过一遍 linter，剩下那一层
——一个算对的数字得出的结论到底是不是真的——用这个。

## 用模板

`templates/` 是这份 spec 的**参考实现**，不是一个要依赖的库。它让上面的 skill
可核验而不是空谈——你能看到 look-ahead 防护具体长什么样，研究截止是哪一行
代码断言的，三层对账到底怎么算的。

随包带了两张价格表——11 只美股 ETF（自 2006 年）、11 只 A 股 ETF（自 2011 年），
均为总回报复权，且都用第二数据源交叉验证过——所以断网、不需要任何 API key 就能跑：

```bash
cd templates && pip install -r requirements.txt

pytest tests/ -q                                                     # 引擎 + 对账逻辑的断言
PYTHONPATH=. python data/qc_data_quality.py --config config.us.yaml   # 数据是真的吗？
PYTHONPATH=. python framework/walk_forward.py --config config.us.yaml --strategy s0_passive
```

换成 `config.cn.yaml` 就是 A 股那张表。完整说明见
[`templates/README.md`](templates/README.md)。

要接自己的市场：把整个目录复制一份，换掉市场相关的部分（标的代码、涨跌幅规则、
成本模型）——或者直接读源码，把同样的防护搬进你已有的技术栈。

```bash
cp -r templates/ my-research-project/
```

## 适用边界（诚实说明）

这套方法论本身不绑定载体——`framing-the-goal` 会先问清楚你的账户到底能买
什么（ETF、场外基金、个股），后面整个闭环都按这个答案走。`templates/` 里
带的参考实现演示的是全球多资产 ETF 轮动——美股与中国境内场内外载体，日线
数据，月频调仓，只做多，不加杠杆——这只是因为它是最简单、能讲完整的例子，
不是这套闭环能处理的上限。

个股比 ETF 篮子多几个 ETF 没有的问题——单一标的退市和公司行动、财报驱动的
跳空、板块和因子拥挤、你真正想交易的那些标的流动性更差——参考实现没有为
任何一条配防护。如果你要把这套方法用在个股上，把 `building-the-foundation`
里的数据质检那一层当成一个需要往上补的地板，而不是一个已经封顶的天花板。

**能迁移的是推理纪律**：把差距归因到正确的层、把平台和尖峰分开、把调仓日运气
和窗口运气分开、搞清楚一个验证到底还留下了什么没测到。这些是人和 agent 如何
被回测欺骗的问题，与具体市场无关。

**不会自动迁移的**：针对某一个市场校准的具体阈值——涨跌幅表、成本模型、
offset 离散度的拒绝线。每个 skill 里都明确写了哪些数字是示例默认值（需要你
按自己的情况重新校准），哪些是不管市场都成立的结构性规则。

**完全没覆盖的**：机构规模下的容量与市场冲击、经典的（退市标的意义上的）
幸存者偏差、正式的多重检验校正（如 deflated Sharpe ratio）、把汇率暴露当作
独立风险因子处理，以及任何日内、加杠杆或衍生品相关的场景。如果你的项目落在
这些范围里，把这里当作起点，而不是完整答案。

## 理念

- **研究的目的不是找到一个好看的回测。** 是搞清楚一个好看的回测到底说明了什么。
- **每一种验证回答的问题都比你实际在问的更窄。** 把它没回答的部分写下来。
- **报告边界比制造数字更有价值。** 研究和造假的区别，就在于你是说"我们找过了，
  它不在那"，还是悄悄放低标准直到输出看起来还行。
- **一个机制能排除一整类尝试，一个数字只能排除一次尝试。** 不管走哪个出口，
  都要入档。

## 参与贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。最有价值的贡献是让某个 skill 的
流程更精确、修正一个在别的市场上是错的阈值，或者补上闭环里的一个缺口——
不是策略代码或实盘参数。

## 免责声明

本仓库是研究方法论，不是投资建议。见 [DISCLAIMER.md](DISCLAIMER.md)。
