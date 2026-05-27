# **智能算力时代的光电同辉：中国光通信产业链在AI五层架构中的护城河与资本估值逻辑深度解析**

全球资本市场在经历人工智能（AI）浪潮的初步洗礼后，正不可逆转地进入以底层基础设施大规模重构为核心的第二阶段。在这一历史性进程中，中国资本市场展现出了一个具有高度结构性与深刻产业内涵的现象：以中际旭创、新易盛、天孚通信和源杰科技为代表的光通信模块及器件股票群体，不仅在核心财务指标（营收与净利润）上实现了跨越式的爆发，其在二级市场的市值与估值也呈现出“一飞冲天”的凌厉态势。这种资本现象绝非单纯的情绪炒作或概念投机，而是全球算力物理架构演进、大国供应链深度绑定以及底层核心光电技术节点实现历史性突破的综合映射。

本报告将从底层物理学与计算体系架构的基石出发，穿透表层的产品迭代周期，深度剖析中国光通信器件厂商在全球头部科技巨头（以英伟达NVIDIA为绝对核心）主导的AI产业链中的真实生态卡位。结合算力网络的技术演进路线（如1.6T超高速率、硅光集成技术、光电共封装CPO）、全球宏观地缘政治博弈的极限施压，以及资本市场估值体系的底层重塑，全面解析这一处于极高景气度赛道的核心护城河与中长期资本发展逻辑。

## **算力革命的物理学基石：黄仁勋“五层蛋糕”架构与基础设施的网络瓶颈**

要准确理解光通信模块在当今全球科技生态与资本市场中的核心战略价值，必须彻底跳出传统的“通信网络设备”分析框架，将其置于全球算力网络重构的宏大叙事中。人工智能经济并非仅仅建立在普通消费者所感知的聊天机器人（Chatbots）、智能副驾驶（Copilots）或自动驾驶系统之上，而是扎根于深层、庞大且极度消耗资源的工业级技术栈之中 1。

### **工业级AI的五层架构模型（The Five-Layer Cake）**

英伟达首席执行官黄仁勋（Jensen Huang）在多个重量级场合（如达沃斯世界经济论坛、CES及GTC大会）将现代AI工业体系精准地抽象为“五层蛋糕”（Five-Layer Cake）工业架构模型。这五层分别是：能源（Energy）、芯片（Chips）、基础设施（Infrastructure）、模型（Models）以及应用（Applications） 1。这是一个严格遵循自下而上物理依赖关系的价值链条，底层的物理极限直接决定了顶层智能系统的前沿天花板 1。

在这一体系中，AI不再被视为单纯的软件或算法堆栈，而是被等同于电力、公路或供水系统的国家级关键基础设施（Critical National Infrastructure） 3。第一层的“能源”是智能生成的绝对物理基础；正如黄仁勋所言，实时生成的智能需要实时生成的电力，这一层涉及得克萨斯州的土地收购、斯堪的纳维亚半岛的工业级液冷塔以及庞大的电力输送网络 3。第二层的“芯片”则是将电能高效转化为计算能力的物理中枢，承载着算力的绝对爆发 3。然而，当大语言模型（LLM）的参数量向多模态、万亿乃至十万亿级别演进时，单颗芯片或单台服务器的算力已远远无法满足大模型训练与推理的需求。算力集群的规模化互联，成为了决定木桶容量的最短板。

这正是第三层“基础设施”（Infrastructure）的核心意义与价值支点。该层级不仅包含制冷与配电，更核心的是将数以万计、甚至百万计的图形处理器（GPU）编排、连接成一台逻辑上统一的超级计算机的网络系统 3。光通信模块及光纤网络，正处于这层“基础设施”中最为关键的数据传输命脉节点。它们不再是传统数据存储中心的简单配套组件，而是连接“智能工厂”（Intelligence Factories）各个算力大脑的神经突触 6。没有极高带宽、极低延迟的光互联网络，再强大的算力芯片也只能沦为数据堆积的“算力孤岛”。

### **从算力瓶颈到网络瓶颈的物理转移：以GB200/GB300为例**

随着GPU单卡性能的指数级跃升，整个AI系统的发展瓶颈已经发生根本性的物理转移：从单一的逻辑计算能力（FLOPS），快速转向了芯片间（GPU-to-GPU）、节点间（Node-to-Node）以及机架间（Rack-to-Rack）的数据互联吞吐能力（I/O Bandwidth） 8。在云服务提供商的战略投资中，资本支出（CAPEX）正以肉眼可见的速度向交换机和互联网络领域倾斜，网络带宽必须与计算能力同步、甚至超前升级 8。

我们可以通过英伟达的新一代算力架构来量化这种网络瓶颈的压力。以GB200 NVL72超级计算机（SuperPOD）为例，该系统在单一液冷机柜内集成了72颗Blackwell GPU，通过第五代NVLink技术实现了高达1.8 TB/s的单向GPU间互联带宽 10。然而，NVLink的物理传输距离极短（通常局限于单机架或相邻机架的铜缆互联），一旦需要将这种互联扩展至数万颗GPU的超大规模AI集群，则必须依赖基于Quantum-X800的InfiniBand网络或Spectrum-X800的以太网架构 13。

在这种多层级的胖树（Fat-Tree）或无阻塞网络拓扑中，电信号在跨机架、跨机房的长距离传输时，面临着不可逾越的物理损耗（Signal Integrity）与能耗墙（Power Wall），必须通过光模块进行光电转换 7。进一步地，随着架构向GB300及未来的Rubin架构演进，单节点的网络适配卡从ConnectX-7升级至ConnectX-8，光模块的速率需求直接从800G跨越至1.6T 15。Rubin架构搭载的第六代NVLink预计将单节点GPU间带宽翻倍至约3.6 TB/s，为了匹配这种恐怖的吞吐量，部署1.6 Tb/s甚至更高速率的光网络已成为必然选择 16。单台GB200服务器可能需要配置多达72个1.6T光模块，这种算力密度的激增，直接催生了对高速光模块的指数级、刚性市场需求 9。

## **算力洪流中的“卖水人”：中国光通信器件厂商的深层护城河解构**

在全球光通信模块的残酷竞争格局中，中国企业已经完成了一场波澜壮阔的产业升级，从早期的技术跟随者、代工者，蜕变为如今掌握定价权、主导技术标准的绝对统治者。知名光通信市场研究机构LightCounting的数据表明，中国厂商在全球前十大光模块供应商中占据了半壁以上的江山，并在高端800G及以上速率市场实现了断层式领先 17。

以下表格展示了2024年全球光模块市场的核心竞争格局及其市场份额分布：

| 全球排名 | 企业名称 | 总部所在地 | 2024年估算市场份额 | 核心优势领域与技术标签 |
| :---- | :---- | :---- | :---- | :---- |
| 1 | 中际旭创 (InnoLight) | 中国 | 23.40% | 800G/1.6T首发, 硅光技术, 全球化规模化交付 |
| 2 | Coherent (高意) | 美国 | 16.87% | 传统电信市场, 400ZR/800ZR相干光, 垂直整合 |
| 3 | 博通 (BROADCOM) | 美国 | 11.06% | 核心DSP/交换芯片, 芯片级定制化与生态壁垒 |
| 4 | 新易盛 (Eoptolink) | 中国 | 8.84% | LPO技术高毛利, 极致成本控制, 泰国产能集群 |
| 5 | 光迅科技 (Accelink) | 中国 | 8.46% | 产业链极高完整度, 传统电信及数通双轮驱动 |
| 6 | Lumentum | 美国 | 9.99% | EML/VCSEL高端光芯片, 特种工业激光器 |

数据来源：基于LightCounting及行业调研综合测算 17。

中国厂商的群体性崛起并非偶然的运气，而是建立在数十年如一日的深度工程制造能力积累、对前瞻性技术路线的果断押注，以及对全球顶级云厂商（CSP）需求极度敏捷的响应基础之上。以下将对资本市场最为关注的四家领军企业——中际旭创、新易盛、天孚通信与源杰科技的核心护城河进行深度穿透与剖析。

### **中际旭创（InnoLight）：绝对的硅光霸权与规模化交付的物理壁垒**

作为全球光模块无可争议的龙头，中际旭创的市值跃升建立在其双重核心护城河之上：“极致的产能响应速度”与“前沿技术的快速工程化量产能力”。在AI算力需求爆发、客户急于抢占大模型高地的窗口期，按时、保质、超大规模的交付能力（Delivery Capability）本身就是最强大的护城河。

在产能与订单维度，中际旭创展现出了统治级的统治力。据行业深度调研，截至2026年初，中际旭创的800G与1.6T订单已经排满至2026年第三至第四季度，产能利用率长期维持在93%至95%的高位极值 19。其在国内以及泰国、马来西亚和墨西哥的多地海外产能基地实现了24小时连轴转的满负荷运转状态，甚至具备在15天内交付海外大客户紧急补单的极端响应能力 19。

以下表格详细拆解了中际旭创与新易盛在2026年的核心产能扩张节点：

| 产能节奏 (2026年) | 中际旭创 (300308) | 新易盛 (300502) |
| :---- | :---- | :---- |
| **Q1 实际月产能** | 800G+1.6T合计 40万只/月 | 800G约30万只/月，1.6T约10万只/月 |
| **Q2 预期月产能** | 提升至 60万只/月 | 泰国二期满产，1.6T提升至 50万只/月 |
| **Q3-Q4 目标产能** | 满产 83万只/月 | 维持满产，1.6T稳定 50万只/月 |
| **全年规划总产能** | 800G约1500万只，1.6T 1000-1500万只 | 800G约1000万只，1.6T 400-500万只 |
| **海外核心基地** | 泰国 \+ 马来西亚 \+ 墨西哥 | 泰国（承载60%以上高端产能） |

数据来源：供应链排产数据追踪（截至2026年2月） 19。

除了庞大的物理产能，中际旭创在硅光（Silicon Photonics, SiPh）技术路线上的绝对领先，是其维持高毛利率、对冲产品年度降价（Annual Price Down）压力的隐形护城河。随着行业惯例的价格下降，中际旭创依然能够保持利润率的高增长，这主要得益于其高端速率产品（1.6T）结构的优化以及硅光技术渗透率的急剧提升 20。相关数据显示，中际旭创的800G硅光模块已实现超过92%的极高良率，且单模块功耗被严苛地控制在14W以下，深得北美云巨头青睐 22。在2025年第三季度，公司已正式向重点客户批量交付1.6T光模块，并在2025年第四季度开启1.6T加速上量的时代，标志着其在下一代技术周期中依然死死锁定了首发红利与最高位的利润池 21。

### **新易盛（Eoptolink）：极简网络架构的信徒与成本效率的极致演绎**

新易盛在全球供应链中的异军突起，深刻体现了中国企业在商业模式中对“成本效率”与“差异化技术路线”的完美结合。其核心护城河集中在两个相互反哺的维度：一是海外产能的前瞻性重资产布局与低成本前置；二是线性驱动可插拔光（LPO）技术的高毛利变现。

在产能布局战略上，新易盛将约60%的高端产能集中于泰国基地 19。相较于国内生产线，泰国基地在人力与运营方面的制造成本具有显著优势（约低15%），且通过严苛的质量管理，其海外产线的良品率高达98% 19。这种全球化的产能布局不仅在宏观上化解了潜在的关税惩罚与地缘政治风险，更在白热化的供应链价格战中确立了坚实的成本护城河。当其泰国二期工程在2026年4月底实现满产后，1.6T模块的月产能将稳定在50万只的巨大规模 19。

在技术路线上，新易盛坚定押注并取得了在LPO（Linear-drive Pluggable Optics）技术领域的绝对优势地位。传统的DSP（数字信号处理器）模块虽然信号重整能力强，但功耗大、成本高、延迟长。LPO技术通过去除光模块中的DSP芯片，转而依赖交换机ASIC的均衡能力，大幅降低了光模块本身的功耗（降低约50%）和材料成本 22。然而，这一极简架构对光电器件的模拟信号补偿能力与封装一致性提出了近乎苛刻的工程挑战。新易盛凭借在LPO工艺上的突破，成功拿下了大量追求极致低延迟与低功耗的AI集群订单，其相关800G LPO产品的毛利率一度达到了45%的行业高位水平，远超传统DSP方案 22。

### **天孚通信（TFC）：纳米级精密制造的“卖铲人”与光引擎一站式霸主**

与中际旭创、新易盛作为直接面对最终客户的终端模块总成商（Tier 1）不同，天孚通信在产业链中扮演着“光器件整体解决方案提供商”的上游角色（Tier 2）。作为“卖水人”的“卖铲人”，天孚通信的业绩表现呈现出恐怖的爆发力：2025年营业收入历史性突破51.63亿元人民币大关（同比增长58.79%），归母净利润高达20.17亿元（同比增长50.15%） 23。

天孚通信真正的护城河，深深隐藏在微观的物理世界中——那是在光无源器件与高速光引擎领域积累十余年的“纳米级精密制造工艺”与“多技术路线混合封装能力”（Know-how） 25。光通信元器件的核心物理诉求是“光信号在跨介质传输时的无损耗精准传导”。在1.6T时代，光路设计的精密度呈指数级上升，任何微米级的对准偏差都会导致致命的信号衰减。天孚的护城河就在于其超高精度的先进光学封装制造良率，这种良率优势在1.6T时代初期的产能爬坡阶段，是携带巨资的新进入者极难在短期内通过砸钱复制的硬核物理壁垒 25。

从财务指标深度拆解，天孚通信的商业模式展现出了惊人的盈利含金量。2025年，其加权平均净资产收益率（ROE）高达41.91%，稳居A股已公布年报的上市公司前列，甚至碾压了绝大多数高端电子制造业公司 23。

以下为天孚通信核心财务指标的深度杜邦分析（DuPont Analysis）表：

| 财务与杜邦分析指标 | 2023年报 | 2024年报 | 2025年报 | 2026年Q1 (最新) | 核心业务研判与趋势 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **营业收入 (亿元)** | 19.39 | 32.52 | 51.63 | 13.30 | 营收呈现跨越式爆发，Q1 YoY+40.82% |
| **归母净利润 (亿元)** | 7.30 | 13.43 | 20.17 | 4.92 | 利润释放强劲，高端制造溢价凸显 |
| **综合毛利率** | 53.9% | 56.3% | 52.9% | 56.6% | 产品结构切换（有源占比上升）带来短期阵痛，Q1现修复迹象 |
| **销售净利率** | 37.6% | 41.3% | 39.08% | 37.01% | 维持极高盈利含金量，费用控制极佳 |
| **资产周转率 (次)** | \~0.65 | 0.75 | 0.92 | \- | 资产周转效率显著提高，运营效率极值化 |
| **权益乘数 (杠杆率)** | \~1.15 | \~1.20 | 1.18 | \- | 几乎不依赖债务杠杆，资产负债表极度健康 |

数据来源：企业公开财报及深度财务拆解 23。

通过杜邦分析可以看出，高达41.91%的ROE并非依赖高风险的财务杠杆（权益乘数仅为常年1.18的极低水平），而是源于其高达39.08%的极高销售净利率和大幅改善的资产周转率 23。这证明了其依靠先进光学封装制造所赚取的“高端制造产品溢价”极具安全边际。此外，为了防御下游云厂商降价诉求向上传导的侵蚀，天孚通信正积极配合客户开发下一代光电共封装（CPO）配套的光纤阵列单元（FAU）和外置光源（ELS）等前沿产品，不断拓宽其技术的护城河 23。

### **源杰科技：突破物理发光极限的光芯片上游锚点与国产化先锋**

如果说光模块是AI数据中心的血管，那么高速光芯片就是泵血的心脏。在整个AI光通信产业链中，上游高端光通信芯片的研发与制造是最为薄弱、物理极限挑战最大、也是技术门槛最高的核心环节 20。EML（电吸收调制激光器）和CW（连续波）大功率激光器芯片的生产周期漫长、外延生长（Epitaxy）工艺极度复杂，构成了当前算力供应链产能真正的核心掣肘 21。源杰科技作为国内极少数具备IDM（垂直整合制造）全流程能力的光芯片企业，其护城河正是建立在这种极度稀缺的国产替代能力之上 26。

源杰科技的核心突破在于其在磷化铟（InP）基激光器芯片领域的全链条自主可控——从最底层的外延片生长、高精度光栅工艺到芯片封装测试，这一IDM模式在国内光芯片企业中占比不足10%，构成了竞争对手难以逾越的时间与技术壁垒 26。在具体产品线上，源杰科技在25G DFB芯片领域已实现国内市占率超40%，其高温阈值电流、斜效率、带宽等核心物理参数甚至优于全球龙头Lumentum 26。

更为资本市场所看重的是其在高速率时代的突破。作为国内独家实现100G EML芯片量产的厂商，源杰科技在2025年4月已顺利完成客户的严苛验证，并开始向中际旭创、新易盛等头部光模块厂商批量供货，直接支撑了800G及1.6T光模块最核心器件的国产化需求 26。不仅如此，其大功率（300mW）CW激光器芯片已经送样英伟达，直接瞄准了未来CPO（光电共封装）架构对外部稳定光源的核心需求。预计未来该领域的市场需求增速将超过传统800G光模块的三倍以上 26。

在二级市场资金流向的博弈层面，源杰科技的股票走势呈现出显著的“机构主导”特征。在2026年春季的几轮大幅上涨中，呈现出完美的“上涨放量、回调缩量”健康形态。例如在2026年3月20日的大涨中，北向资金（外资）净买入占比达25.2%，机构席位净买入占比达58.6%，散户资金更多是追涨杀跌 26。长线产业资金对其在100G EML和高端CW激光器领域垄断性地位的重金押注，实质上是对未来中国AI算力基础设施不再被海外芯片“卡脖子”的期权定价。

## **光网络物理架构的代际跃迁：1.6T、硅光革命与CPO的终局图谱**

资本市场对光通信板块的狂热追捧，其底层的技术逻辑在于光互联产业正处于一个极为罕见、极具爆发力的“多技术路线并行突破”的技术折叠期。

### **1.6T周期的全面爆发与以太网标准的跃迁**

随着AI/ML大模型（如万亿参数的混合专家模型MoE）复杂度的呈指数级上升，数据并行与张量并行训练产生了海量的参数同步需求。这使得1.6T超高速互联产品迎来了前所未有的增长机遇 9。以单台英伟达GB200服务器为例，其需要配置多达72个1.6T光模块，创造了空前的市场拉动力 9。

全球云服务巨头（如谷歌、微软、亚马逊、Meta）正在对其骨干网络和大型AI集群进行400G/800G向1.6T的全面升级换代 9。据行业顶级分析机构Cignal AI及野村证券（Nomura）预测，到2026年，全球1.6T光模块的出货量有望突破500万只，甚至年底可能冲击2000万只的惊人规模，创造超过10亿美元的纯增量市场价值 9。

在这一周期内，底层电气标准也在发生深刻变革。IEEE 802.3dj标准（涵盖单通道200G PAM4信号技术）预计将于2026年中期正式定稿落地 27。这意味着为了匹配1.6T的传输，底层物理布线必须全面升级，例如在数据中心布线系统中全面转向16芯MPO主干光纤，同时淘汰无法承受高频损耗的传统铜缆（DAC/AEC将在1.6T时代全面退出长距离互联舞台） 28。

### **硅光技术（SiPh）的黄金分水岭与材料学替代**

传统的光模块大量依赖分立的化合物半导体激光器（如基于GaAs的VCSEL或基于InP的EML）。然而，当单通道传输速率突破200G、模块总速率达到1.6T时，分立器件在寄生电容、功耗控制、热管理与封装成本上面临着严酷的物理极限。

硅光技术（Silicon Photonics）带来了材料学与制造工艺的降维打击。它将发光、调制、探测等光学元器件直接集成在传统的硅晶圆上，利用极为成熟的CMOS集成电路制造工艺进行大规模批量制造 22。这不仅实现了光学器件体积的极致压缩（例如华为发布的1.6Tbps硅光模块实现了70%的体积缩减），更带来了40%以上的功耗下降 22。

2026年是全球光模块制造工艺史上的一个关键分水岭。行业数据深度测算表明，硅光技术在光模块中的市场份额预计将在2026年历史性地突破50%的绝对关口（作为对比，2018年仅为10%，2024年为33%） 29。在具体的1.6T产品结构中，硅光方案的占比预计将高达70%，彻底压倒传统的EML方案 29。这种底层制造材料和工艺体系的转换，不仅将重塑产业链上下游的利润分配格局，也为那些早年不惜重金布局硅光技术的中国龙头企业（中际旭创便是最大赢家）提供了深厚的长期技术溢价。

### **光电共封装（CPO）与“功耗墙”的彻底终结**

尽管1.6T可插拔光模块目前如日中天，但在更深远的战略层面上，行业龙头已经在为下一代颠覆性物理架构——光电共封装（CPO，Co-Packaged Optics）铺平道路。

现代超级AI数据中心正面临着足以危及产业发展的“功耗墙”（Power Wall）危机。基于Rubin级GPU的单机架功率已从传统的50-75kW直接飙升至150kW甚至更高区间 16。风冷技术在40kW/rack以上便彻底失效，液冷技术虽能缓解芯片散热压力，但无法解决电信号在PCB板上长距离传输过程中的极致衰耗与巨大的能量浪费 16。

英伟达于2026年3月发布的Spectrum-X1600以太网光子平台，标志着数据中心互联从电信号主导向全光网演进的实质性跨越 30。该平台利用先进的224G SerDes技术，在单一交换机内实现409.6 Tb/s的恐怖吞吐量。更为关键的是，它直接将硅光引擎与以太网交换机芯片在同一个物理封装基板上进行了共封装（CPO） 30。

CPO技术彻底消除了传统可插拔光模块中极其耗电的数字信号处理器（DSP），电信号在芯片内部即转化为光信号，从而实现网络延迟和功耗的断崖式下降 30。英伟达甚至通过资本手段，豪掷20亿美元入股光通信DSP巨头Marvell，以此作为对抗博通（Broadcom）的战略毒丸，同时死死锁定Marvell在光DSP和模拟技术上的产能，为其Vera Rubin架构的光子网络保驾护航 31。在CPO全面落地的未来，数据中心将被彻底重塑为“光定义AI工厂”（Optically-Defined AI Factory） 31。中国企业如天孚通信（提前卡位提供外置光源ELS和高密度光纤阵列）和源杰科技（研发大功率CW激光器供给英伟达）正是精准卡位了这一未来架构中不可替代的物理引擎组件 23。

## **跨越周期的资产重估：中国资本市场对光通信板块的估值逻辑解密**

中国资本市场对光通信板块给予的极高估值与连续拉升，引发了传统价值投资者的广泛探讨与困惑。要深刻理解这一估值逻辑的合理性，必须跳出传统的硬件制造业估值框架，引入“成长性溢价”、“宏观基建属性”与“确定性折现”的综合资本视角。

### **估值体系重塑：彻底脱离传统电信资本开支的死亡周期**

在过去10年的4G/5G建设周期内，光模块通常被资本市场视为典型的周期性硬件制造业。其需求曲线高度依赖中国移动等电信运营商的资本开支计划，且常面临集采招标带来的极度压价与毛利反噬。在这种逻辑下，市场通常只愿意给予光模块企业15-25倍的市盈率（PE）估值。

然而，在当前的AI五层架构中，光通信模块的宏观属性被彻底重新定义，跃升为“算力时代的核心关键基础设施” 5。这种基础设施建设呈现出极其惨烈的“全球军备竞赛”特征——云服务提供商（CSP）如微软、谷歌、亚马逊等，为了不在生成式AI的算力争夺战中被淘汰，其针对高带宽互联集群的投资展现出极强的刚性、持续性与不计成本性 9。这使得光模块赛道由“强周期、低毛利”属性，瞬间转变为“高成长、高毛利、高确定性”的稀缺资产属性。资本市场随之启动了典型的戴维斯双击（Davis Double Play）：即企业盈利预期的大幅上修，伴随着估值倍数（PE Multiple）的系统性扩张。

### **跨越国界对标与溢价合理性：Lumentum与Coherent的启示**

为准确衡量中国光通信资产当前估值的合理性与泡沫程度，将其置于全球资本市场的坐标系中对标美国同行是最佳路径。以美国光通信器件巨头Lumentum（股票代码：LITE）为例，随着其业务重心向 datacom（数通）领域倾斜，截至2026年5月，其静态市盈率（Trailing P/E）一度被资金推高至惊人的262.41倍，远超其过去十年的历史平均值87.37倍 32。即便是基于分析师对其2026财年盈利爆发的预期，其前瞻市盈率（Forward P/E）依然高达57.43倍，2027年预期亦维持在41.29倍的高位 34。同样，另一巨头Coherent（高意）凭借在电信与数通市场的双轮驱动，其营收预期从2025年的16.5亿美元大幅提升至2027年的46亿美元，获得了标普全球评级（S\&P Global Ratings）的强劲上调与资本市场的热烈追捧 35。

以下表格直观展示了中美核心光通信企业的资本市场估值锚点对比：

| 企业名称 (代码) | 市场定位 | 2026年估算市盈率 (Forward P/E) | 2025-2026 盈利复合增速预期 | 资本市场核心关注点 |
| :---- | :---- | :---- | :---- | :---- |
| **Lumentum (LITE)** | 美国高端光芯片/器件 | 57.43x | 极高 (基数低，实现扭亏为盈或暴增) | AI数通转型，特种激光器溢价 |
| **Coherent (COHR)** | 美国全能型光电巨头 | 高估值通道 | 营收由![][image1]4.6B | 400ZR/800ZR长距离相干光垄断 |
| **中际旭创 (300308)** | 全球数通模块龙头 | 35x \- 45x 区间 | \~90% \- 130% 21 | 英伟达/谷歌核心供货商，业绩高确定性兑现 |
| **天孚通信 (300394)** | 精密光器件/引擎 | 40x \- 50x 区间 | \~50% 以上 23 | 超高ROE (41.9%)，极佳的盈利质量 |
| **源杰科技 (688498)** | 国产高端光芯片独苗 | 动态溢价极高 | 处于产能放量与国产替代初期 | “卡脖子”技术突破，自主可控稀缺性溢价 |

数据来源：基于综合研报、SeekingAlpha及A股公开财报预期测算 21。

对比可知，尽管中国头部光通信企业（如中际旭创、新易盛、天孚通信）在二级市场涨幅惊人，但在其实现了远超海外同行的营收基数与净利润增速（同比动辄50%乃至130%翻倍）的前提下，其动态市盈率（PE）及市盈率相对盈利增长比率（PEG）在相当长一段时间内仍处于具有安全边际的合理区间。中国市场的资金并非盲目炒作市梦率，而是对“业绩高确定性兑现”进行提前折现。

### **稀缺性溢价：国产替代与自主可控的时代红利**

对于天孚通信、源杰科技等偏向产业链上游器件与芯片的标的而言，其极高的估值逻辑不仅来源于财务报表上的业绩高增，更叠加了一层厚重的“国产替代与国家供应链安全”的时代溢价。在全球地缘政治日益紧张的宏观背景下，能够真正突破海外技术封锁、在高速InP激光器、高精密硅光集成工艺上实现规模化量产的企业，具备极强的资产稀缺性。市场给予的不仅是其当期利润的乘数，更是对其填补国内AI算力底层产业链空白、掌握未来定价权的“看涨期权”。

## **地缘政治博弈、制裁之剑与供应链的极限承压**

在深度看好并享受光通信行业空前景气度的同时，宏观资本无法忽视笼罩在高端半导体与光通信产业链上方的地缘政治阴霾。大国博弈正通过各种复杂、多维度的法案、长臂管辖与金融制裁工具，深刻重塑着全球科技供应链的物理走向与生态格局。

### **出口管制、天价罚款与双向制裁的白热化**

2025至2026年间，美国政府及其监管机构密集出台了一系列旨在遏制中国获取高端信息和通信技术（ICT）及AI相关领域核心组件的限制措施。基于第13873号行政命令的“保护信息和通信技术与服务供应链”规则（ICTS rule）于2025年初全面生效，赋予了相关部门审查所有涉及关键基础设施、敏感个人数据及新兴技术交易的宽泛且模糊的裁量权 37。同时，具有深远影响的《全面对外投资国家安全法》（COINS Act，2025年底签署）正式落地，配合美国财政部的对外投资安全计划（OISP），使得美国资本在半导体、微电子、量子计算和人工智能领域的对华直接投资面临严苛的持续性审查甚至禁令 37。

此外，美国商务部工业和安全局（BIS）通过实体清单（Entity List）构筑了实质性的技术与贸易壁垒。为了杀鸡儆猴，BIS对各类试图规避制裁的行为实施了毁灭性的顶格处罚。例如，全球半导体设备巨头应用材料公司（Applied Materials）因未获出口许可，将其关键离子注入设备经由韩国（AMK）作为跳板，非法转运至已被列入实体清单的中国企业，被美国商务部处以高达2.52亿美元的天价罚款（该罚款额度为非法交易总值的两倍，系BIS历史上的第二大罚单） 38。这一雷霆行动在全球高科技供应链中产生了极强的震慑与寒蝉效应 38。

作为回应，中国亦祭出了强有力的反制措施。中国大幅加强了对稀土等关键光学与半导体制造材料的出口管制，并通过《不可靠实体清单》（UEL）精准打击参与对台军售或损害国家安全的海外实体，如通用动力、斯凯迪奥（Skydio）等企业被明确禁止向其出口军民两用物项 37。这种双向的极限施压，使得身处其中的光通信企业必须在夹缝中寻求生存与发展的平衡。

### **全球化产能重构与战略避险（China Plus One）**

面对严峻且难以预测的宏观政策与贸易关税风险，中国光通信巨头展现出了卓越的战略定力与执行力。其核心对策是通过产能的“去中心化与全球化”来实现供应链的极致韧性。前文深入探讨的中际旭创与新易盛之所以在泰国、马来西亚甚至北美后花园墨西哥大规模砸下重金建立制造基地，绝不仅仅是为了追求东南亚低廉的人力成本，其核心战略诉求是：在合规的框架内规避高昂的潜在关税壁垒以及原产地制裁风险 19。

通过将极高附加值、高精密度的前端光芯片研发、硅光晶圆制造及核心光学封装技术保留在中国本土，而将劳动密集、对关税敏感的后端光模块组装与测试环节大规模转移至东南亚等中立地带，中国光通信企业巧妙地化解了贸易壁垒的冲击。正是这种全球化产能调配的灵活性，使得中国厂商成功保住了包括英伟达、谷歌、亚马逊等北美超级大厂在内的核心AI集群订单。这种具备前瞻性的、重资产的海外工厂布局能力与跨国管理能力，本身就为后来者构筑了一道令中小企业望尘莫及的宏大生态护城河。

## **终局推演与宏观展望：光定义的智能未来**

将黄仁勋构筑的AI“五层蛋糕”架构与中国光通信产业过去五年的发展轨迹与未来三年的产能规划相叠印，我们可以无比清晰地洞察到一幅智能互联时代的宏伟画卷。底层AI芯片的算力军备竞赛，正以物理层面的数据风暴形式，毫无保留、甚至是超负荷地倾泻在网络互联基础设施之上。

首先，**我们正在经历一次行业成长周期的超预期延长**。尽管资本市场时刻通过放大镜审视，警惕光通信产业是否会因全球产能的大幅扩张而重蹈过去“周期性产能过剩”的覆辙。然而，基于从800G到1.6T，再到未来预研的3.2T的极速技术跨越，以及单模光纤物理传输极限的逼近、设备接口标准的不断演进，每一次产品的代际升级都需要进行庞大而复杂的产线重新改造与海量研发资金的投入 40。这种极高的资本支出门槛与令人窒息的技术迭代速度，天然地淘汰了落后产能，确保了光通信行业的高景气度在未来3-5年内仍将展现出强大的韧性，且绝大部分利润池将不可逆地加速向少数掌握核心技术的头部企业集中 40。

其次，**“光电一体化”将彻底重塑产业链的竞争边界**。随着硅光技术（SiPh）渗透率的全面突破以及光电共封装（CPO）架构的商业化落地，传统光通信模块与交换机/GPU芯片之间的物理边界正在彻底消融 7。这不仅是底层工程技术的物理演进，更是全球千亿美元商业价值的重新洗牌与分配。在这个过程中，能够具备底层光芯片独立研发能力（如源杰科技）、纳米级高度集成封装与引擎制造能力（如天孚通信）以及极速全球化规模总成交付能力（如中际旭创、新易盛）的中国军团，将不仅仅是依附于他人的“代工厂”。

综上所述，中国资本市场对光通信板块核心标的给予的强劲估值与市值跃升，有着极其坚实的底层物理规律、难以跨越的技术代差、极高的资金回报率以及全球供应链现实作为强硬支撑。在人工智能逐步从实验室走向工业界、最终兑现其重塑全球经济面貌宏大愿景的进程中，以中国厂商为主导的光互联技术，将继续作为整个AI五层架构中最不可或缺、也是最能感知时代脉搏的底层基础设施引擎，推动人类计算架构向着全光互联的更高智能维度无限延伸。

#### **Works cited**

1. From Electricity to Intelligence: Mapping the AI Five-Layer Ecosystem \- Reddit, accessed May 4, 2026, [https://www.reddit.com/r/bootstrapstartup/comments/1rvtacb/from\_electricity\_to\_intelligence\_mapping\_the\_ai/](https://www.reddit.com/r/bootstrapstartup/comments/1rvtacb/from_electricity_to_intelligence_mapping_the_ai/)  
2. Jensen Huang: "AI is a five-layer cake. Energy, chips, infrastructure, models, and applications." : r/deeplearning \- Reddit, accessed May 4, 2026, [https://www.reddit.com/r/deeplearning/comments/1pffjse/jensen\_huang\_ai\_is\_a\_fivelayer\_cake\_energy\_chips/](https://www.reddit.com/r/deeplearning/comments/1pffjse/jensen_huang_ai_is_a_fivelayer_cake_energy_chips/)  
3. AI Is a 5-Layer Cake | NVIDIA Blog, accessed May 4, 2026, [https://blogs.nvidia.com/blog/ai-5-layer-cake/](https://blogs.nvidia.com/blog/ai-5-layer-cake/)  
4. Jensen Huang: "AI is a five-layer cake. Energy, chips, infrastructure, models, and applications." \- YouTube, accessed May 4, 2026, [https://www.youtube.com/shorts/nzIVBKXeGwQ](https://www.youtube.com/shorts/nzIVBKXeGwQ)  
5. 'Largest Infrastructure Buildout in Human History': Jensen Huang on AI's 'Five-Layer Cake' at Davos | NVIDIA Blog, accessed May 4, 2026, [https://blogs.nvidia.com/blog/davos-wef-blackrock-ceo-larry-fink-jensen-huang/](https://blogs.nvidia.com/blog/davos-wef-blackrock-ceo-larry-fink-jensen-huang/)  
6. The AI “5-Layer Cake”: How Nvidia's CEO Explains the Real Economics of Intelligence | by Shane Collins | Activated Thinker | Mar, 2026 | Medium, accessed May 4, 2026, [https://medium.com/activated-thinker/the-ai-5-layer-cake-how-nvidias-ceo-explains-the-real-economics-of-intelligence-7fa367c3cefc](https://medium.com/activated-thinker/the-ai-5-layer-cake-how-nvidias-ceo-explains-the-real-economics-of-intelligence-7fa367c3cefc)  
7. NVIDIA Announces Spectrum-X Photonics, Co-Packaged Optics Networking Switches to Scale AI Factories to Millions of GPUs \- NVIDIA Investor Relations, accessed May 4, 2026, [https://investor.nvidia.com/news/press-release-details/2025/NVIDIA-Announces-Spectrum-X-Photonics-Co-Packaged-Optics-Networking-Switches-to-Scale-AI-Factories-to-Millions-of-GPUs/default.aspx](https://investor.nvidia.com/news/press-release-details/2025/NVIDIA-Announces-Spectrum-X-Photonics-Co-Packaged-Optics-Networking-Switches-to-Scale-AI-Factories-to-Millions-of-GPUs/default.aspx)  
8. "Scale-up Optical Interconnect" Related News — BigGo Finance, accessed May 4, 2026, [https://finance.biggo.com/s/Scale-up%20Optical%20Interconnect](https://finance.biggo.com/s/Scale-up%20Optical%20Interconnect)  
9. 1.6T Transceiver Market Insights：Future of AI and HPC Networking \- NADDOD Blog, accessed May 4, 2026, [https://www.naddod.com/blog/1-6t-transceiver-market-insights-future-of-ai-and-hpc-networking](https://www.naddod.com/blog/1-6t-transceiver-market-insights-future-of-ai-and-hpc-networking)  
10. GB200 NVL72 | NVIDIA, accessed May 4, 2026, [https://www.nvidia.com/en-us/data-center/gb200-nvl72/](https://www.nvidia.com/en-us/data-center/gb200-nvl72/)  
11. Key Components of the DGX SuperPOD \- NVIDIA Documentation, accessed May 4, 2026, [https://docs.nvidia.com/dgx-superpod/reference-architecture-scalable-infrastructure-gb200/latest/dgx-superpod-components.html](https://docs.nvidia.com/dgx-superpod/reference-architecture-scalable-infrastructure-gb200/latest/dgx-superpod-components.html)  
12. NVIDIA GB200 Interconnect Architecture Analysis: NVLink, InfiniBand, and Future Trends, accessed May 4, 2026, [https://www.naddod.com/blog/nvidia-gb200-interconnect-architecture-analysis-nvlink-infiniband-and-future-trends](https://www.naddod.com/blog/nvidia-gb200-interconnect-architecture-analysis-nvlink-infiniband-and-future-trends)  
13. NVIDIA Quantum-X800 InfiniBand Platform, accessed May 4, 2026, [https://www.nvidia.com/en-us/networking/products/infiniband/quantum-x800/](https://www.nvidia.com/en-us/networking/products/infiniband/quantum-x800/)  
14. Networking Solutions for the Era of AI \- NVIDIA, accessed May 4, 2026, [https://www.nvidia.com/en-us/networking/](https://www.nvidia.com/en-us/networking/)  
15. NVIDIA GB300 Deep Dive: Performance Breakthroughs vs GB200, Liquid Cooling Innovations, and Copper Interconnect Advancements. \- NADDOD, accessed May 4, 2026, [https://www.naddod.com/blog/nvidia-gb300-deep-dive-performance-breakthroughs-vs-gb200-liquid-cooling-innovations-and-copper-interconnect-advancements](https://www.naddod.com/blog/nvidia-gb300-deep-dive-performance-breakthroughs-vs-gb200-liquid-cooling-innovations-and-copper-interconnect-advancements)  
16. Rubin-Class Shift and Its Implications for AI Infrastructure | by elongated\_musk \- Medium, accessed May 4, 2026, [https://medium.com/@Elongated\_musk/rubin-class-shift-and-its-implications-for-ai-infrastructure-e66ce4cd61cc](https://medium.com/@Elongated_musk/rubin-class-shift-and-its-implications-for-ai-infrastructure-e66ce4cd61cc)  
17. The Top 10 Competitiveness Enterprises in the Optical Communications Industry of China & Global market in 2023, accessed May 4, 2026, [http://list.nti.news/](http://list.nti.news/)  
18. Top 10 Global Optical Modules in 2023: Chinese Manufacturers Ranked First for the First Time, with a Total of 7 on the List, accessed May 4, 2026, [https://htfuture.com/top-10-global-optical-modules-in-2023-chinese-manufacturers-ranked-first-for-the-first-time-with-a-total-of-7-on-the-list/](https://htfuture.com/top-10-global-optical-modules-in-2023-chinese-manufacturers-ranked-first-for-the-first-time-with-a-total-of-7-on-the-list/)  
19. 新易盛中际旭创排班到2027年 \- 财富号, accessed May 4, 2026, [https://caifuhao.eastmoney.com/news/20260223090334149785680?from=guba\&name=5oub6YeR55%2B%2F5Lia5ZCn\&gubaurl=aHR0cHM6Ly9ndWJhLmVhc3Rtb25leS5jb20vbGlzdCxoazAxODE4Lmh0bWw%3D](https://caifuhao.eastmoney.com/news/20260223090334149785680?from=guba&name=5oub6YeR55%2B/5Lia5ZCn&gubaurl=aHR0cHM6Ly9ndWJhLmVhc3Rtb25leS5jb20vbGlzdCxoazAxODE4Lmh0bWw%3D)  
20. 中际旭创：今年1.6T光模块需求将出现较大增长, accessed May 4, 2026, [https://cj.sina.cn/articles/view/2311077472/89c03e6002002j99e](https://cj.sina.cn/articles/view/2311077472/89c03e6002002j99e)  
21. 中际旭创(300308)公司点评报告：1.6T光模块订单增长迅速硅光占比持续提升, accessed May 4, 2026, [https://www.9fzt.com/detail/sz\_300308\_10\_823506318612.html](https://www.9fzt.com/detail/sz_300308_10_823506318612.html)  
22. High-Speed Optical Transceiver Market丨C-LIGHT, accessed May 4, 2026, [https://www.c-light.com/news/details/High\_Speed\_Optical\_Transceiver\_Market.html](https://www.c-light.com/news/details/High_Speed_Optical_Transceiver_Market.html)  
23. 6倍股天孚通信：净利润增长50%，拟赴港上市 \- 证券市场周刊, accessed May 4, 2026, [https://static.weeklyonstock.com/26/0423/wd160424.html](https://static.weeklyonstock.com/26/0423/wd160424.html)  
24. 6倍股天孚通信：净利润增长50%，拟赴港上市 \- 新浪财经, accessed May 4, 2026, [https://finance.sina.com.cn/stock/wbstock/2026-04-23/doc-inhvnnwy5006435.shtml?cre=tianyi\&mod=pcfinhkst\&loc=6\&r=0\&rfunc=62\&tj=cxvertical\_pc\_finhkst\&tr=12](https://finance.sina.com.cn/stock/wbstock/2026-04-23/doc-inhvnnwy5006435.shtml?cre=tianyi&mod=pcfinhkst&loc=6&r=0&rfunc=62&tj=cxvertical_pc_finhkst&tr=12)  
25. 天孚通信（300394）深度分析报告\_财富号\_东方财富网, accessed May 4, 2026, [https://caifuhao.eastmoney.com/news/20260424225732605281030](https://caifuhao.eastmoney.com/news/20260424225732605281030)  
26. 源杰科技（688498.SH）2025-2026年股价暴涨逻辑与深度分析报告（一）, accessed May 4, 2026, [https://caifuhao.eastmoney.com/news/20260416232933863541740](https://caifuhao.eastmoney.com/news/20260416232933863541740)  
27. Optical Networking \- MLQ.ai | AI for investors, accessed May 4, 2026, [https://mlq.ai/research/optical-networking/](https://mlq.ai/research/optical-networking/)  
28. 800G Data Center Interconnect Guide: DAC, AEC, AOC & Optical \- Vitex LLC, accessed May 4, 2026, [https://www.vitextech.com/blogs/blog/800g-data-center-interconnect-selection-guide](https://www.vitextech.com/blogs/blog/800g-data-center-interconnect-selection-guide)  
29. Semiconductors \- Optical transceivers, accessed May 4, 2026, [https://hk-official.cmbi.info/upload/ab33e7b6-35dd-4d82-b418-b4ad1ce4a66b.pdf](https://hk-official.cmbi.info/upload/ab33e7b6-35dd-4d82-b418-b4ad1ce4a66b.pdf)  
30. NVIDIA Shakes the 'Power Wall': Spectrum-X Ethernet Photonics Bridges the Gap to Million-GPU Rubin Clusters \- FinancialContent \- Stock Market, accessed May 4, 2026, [https://markets.financialcontent.com/stocks/article/tokenring-2026-2-5-nvidia-shakes-the-power-wall-spectrum-x-ethernet-photonics-bridges-the-gap-to-million-gpu-rubin-clusters](https://markets.financialcontent.com/stocks/article/tokenring-2026-2-5-nvidia-shakes-the-power-wall-spectrum-x-ethernet-photonics-bridges-the-gap-to-million-gpu-rubin-clusters)  
31. NVIDIA and Marvell's $2B Alliance: Architecting the Optically-Defined AI Factory, accessed May 4, 2026, [https://hyperframeresearch.com/2026/04/01/nvidia-and-marvells-2b-alliance-architecting-the-optically-defined-ai-factory/](https://hyperframeresearch.com/2026/04/01/nvidia-and-marvells-2b-alliance-architecting-the-optically-defined-ai-factory/)  
32. LITE \- Lumentum Holdings PE ratio, current and historical analysis \- FullRatio, accessed May 4, 2026, [https://fullratio.com/stocks/nasdaq-lite/pe-ratio](https://fullratio.com/stocks/nasdaq-lite/pe-ratio)  
33. Lumentum Holdings PE Ratio 2013-2025 | LITE \- Macrotrends, accessed May 4, 2026, [https://www.macrotrends.net/stocks/charts/LITE/lumentum-holdings/pe-ratio](https://www.macrotrends.net/stocks/charts/LITE/lumentum-holdings/pe-ratio)  
34. Coherent Corp. (COHR) PE Ratio | PEG Ratios \- Seeking Alpha, accessed May 4, 2026, [https://seekingalpha.com/symbol/COHR/valuation/price-earnings-peg-ratios](https://seekingalpha.com/symbol/COHR/valuation/price-earnings-peg-ratios)  
35. Research Update: Lumentum Holdings Inc. Upgraded | S\&P Global Ratings, accessed May 4, 2026, [https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3553946](https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3553946)  
36. Lumentum ($LITE) valuation breakdown : r/options \- Reddit, accessed May 4, 2026, [https://www.reddit.com/r/options/comments/1sdhyr5/lumentum\_lite\_valuation\_breakdown/](https://www.reddit.com/r/options/comments/1sdhyr5/lumentum_lite_valuation_breakdown/)  
37. 2025: A review of foreign sanctions and export control developments involving China, accessed May 4, 2026, [https://www.alixpartners.com/insights/102m1vv/2025-a-review-of-foreign-sanctions-and-export-control-developments-involving-chi/](https://www.alixpartners.com/insights/102m1vv/2025-a-review-of-foreign-sanctions-and-export-control-developments-involving-chi/)  
38. all-press-releases | Bureau of Industry and Security, accessed May 4, 2026, [https://www.bis.gov/news-updates](https://www.bis.gov/news-updates)  
39. A Summary of China's Retaliation Actions Since The Trump Administration, accessed May 4, 2026, [https://www.tradepractitioner.com/2025/03/a-summary-of-chinas-retaliation-actions-since-the-trump-administration/](https://www.tradepractitioner.com/2025/03/a-summary-of-chinas-retaliation-actions-since-the-trump-administration/)  
40. 订单排满至2028年：光通信如何成为AI时代“卖水人” \- 中国能源网, accessed May 4, 2026, [https://www.cnenergynews.cn/article/4R85Fy8njvd](https://www.cnenergynews.cn/article/4R85Fy8njvd)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAE4AAAAWCAYAAABud6qHAAADp0lEQVR4Xu2XWchOURSGFz+FyBySkqHIEHJhJmNcyHhHQilkKuOdKW6IuECmUpKhkKHEhVAUQolcSCJj5kjm9f5r7+9f3/ud8w3Jf+H/nno7Z79rnWmdffbeR6RMmTL/loeqVmwWYIjqMJs1jd+qd2wWoLfYcXkLvlQ1l80iGKD6KHaBLRTDhS+o+qhqqzqotqpO+CTHc9U3sXNBn1RvwjZ6KzPZRhPVY/KSwLHr2CxAZ7HjInXiziHJvtF5MVAkV1UvXfu+apVrj5Sqc0e9cvEk2orlLeOAckcsNpF8vAj4eDngtotFiikcci6JvWzoSvBiG8qh1MLhJvzbaBHaZ503VHVGtUe1VtXQxdLYJtlF8IwTi10mvyL43VT9VH1VO7Mycgs3QnXLtZNoJ9nPmEiphUP+XvK6UHuQag15hfgp6Td7Uyw2jHxwLWwRx5iE7XQntE+69pHgDbbDMuArrBf2uXD4OnMopXBjxPInh/Z4F/MMlNILh/O+ZVOsJyF2lwOOCapFqkaSW3zucRhSOAccFPvUMXZ2F8vBPpSUX1LhMEUjf5pqtaqp6onY4O7pL3YjyMWb/CI2hqTRWCx3o6qj2OCMCQZLCfj4vPIRH+xvCrdPrGcD7nFJ+ZXmfDZTeCCWzz0D3nbXxmzKMx5yeIyKbBaLo0ejSNAo1e7gY12VBlYE98J+tRduAZspXBfLn0M+vMSTO15Iek6+8S328l4cCCDWPOy3D21PsYU7IDZ7g3jN4apmYT8HmAvZTGG/WD4+J08xhbsolpO0qIT/gc0AxlHEz5E/RfUoxCJYW6I90wntU659LHgMljZPVfUl+3m+B+WAhMVspjBWLL8r+Vw4boMbwYszVyQuZ5aTH4mzIGZET63gn3YeisnXRdv3uBWqHa4d6RG2mEE3iR23S1U3k0EgYQmbgamS20OQj8mBvV/UPuraIC64GTwE/KQbxIqdz+1BzP9RZFb4Di5cPmaLTWRxjKsI27jkyRDfNirMxDfKD4uxAGNSBItb5LR2HqZ1LEkibcRyZjgvknQNMEvMf88BB+K84GWQs57NBDpJ1X1gKPL3lNlHb3gt9k1jOYEtfqF4oYfvHv+yzHGxkz0LW6x7GMx0iMWeht8wz2fVD7HeFIsHoY0xBWMRDwkM8vF7lA/kbGCTaKn66to9Jbtwo93+fwEejpc9DHKSvqhIA7HJw4N1qC9cjQQFwCCfBk9WYJKUC1dZAHyKpYBly3k2y5SpPv4Ab3YmL8Di9XkAAAAASUVORK5CYII=>