ai伴侣，数字人，怎么做呢，那qwen3.5加qwen3tts？还是怎么样，联网搜索一下

我先查一下目前可用的 Qwen 相关模型能力，再给你一个可落地的技术方案，不只回答“能不能用”，也会说清楚该怎么拼。

已经确认两件事：一是现在确实有官方的 Qwen3-TTS；二是如果你想做“能听、能说、还能直接语音流式回复”的版本，Qwen3-Omni 这条线也值得优先考虑。接下来我补一下“数字人表现层”和工程拼装方式。

已思考 42s

可以做，而且别一上来就把它理解成“选一个模型就完事”。
AI 伴侣 / 数字人通常要拆成 4 层：

大脑：负责人设、记忆、对话策略、陪伴感
耳朵和嘴：ASR（语音识别）+ TTS（语音合成）
身体/脸：2D/3D 头像、口型、表情、动作
编排层：实时流式、打断、记忆、RAG、审核、计费、前端/RTC

所以“Qwen3.5 + Qwen3-TTS 行不行”，答案是：行，而且是很稳的一条路；但如果你追求更强的实时语音对话体验，Qwen3-Omni 也要认真考虑。

先给结论

如果你现在就要开工，我建议这样选：

文字/多轮陪伴为主，语音只是输入输出
用 Qwen3.5（LLM） + Qwen3-TTS（TTS） + Qwen3 ASR/FunASR（ASR）。
这是最容易控成本、最好调人设、最好做长期记忆的一种。Qwen3-TTS 官方已经支持流式语音生成、声音克隆、声音设计；阿里云也有 Qwen 实时语音识别服务。
实时语音陪聊为主，想减少“ASR→LLM→TTS”拼装复杂度
直接看 Qwen3-Omni。官方说明它是端到端 omni 模型，支持文本、音频、图像、视频输入，并能实时输出自然语音。这类架构更适合“打断、插话、低延迟语音互动”。
数字人表现是核心，想要像真人视频客服/主播
模型层继续用上面任一方案，表现层单独做：
2D 可用 Live2D；3D 可用 NVIDIA Audio2Face；托管式可看 HeyGen/LiveAvatar 这一类实时 avatar 服务。
你提到的两种思路，怎么选
方案 A：Qwen3.5 + Qwen3-TTS

这套的本质是经典 STT → LLM → TTS pipeline。

优点

好调教：人设、记忆、恋爱感、情绪回复、边界控制，都主要在 LLM 层做
组件清晰：ASR、LLM、TTS 可分别替换
最适合先做 MVP，再逐步升配
Qwen3-TTS 官方已提供 0.6B/1.7B 系列，并支持 10 种主要语言、3 秒声音克隆、voice design、流式生成等能力。

缺点

实时感取决于你编排得好不好
打断、抢话、边听边说，要自己做状态机
口型和情绪得额外接 avatar 层

适合

AI 女友/男友、陪聊、树洞、情绪陪伴
声音陪伴 + 轻量数字人
先做 App / Web MVP
方案 B：Qwen3-Omni

Qwen3-Omni 官方定位就是原生端到端多模态 + 实时自然语音回复，支持 19 种语音输入语言、10 种语音输出语言。

优点

更适合做实时语音 agent
更自然地处理连续音频流
理论上更适合“边听边理解边说”

缺点

你对“陪伴人设”的精细控制，未必比“独立 LLM + 独立 TTS”更好调
如果你最终还要上复杂记忆系统、剧情系统、亲密度系统，编排层仍然少不了
算力/部署复杂度通常更高

适合

语音优先产品
要“像打电话一样”自然聊天
想做接近 Realtime Voice Agent 的形态
我给你的推荐，不是一刀切，而是分阶段
第一阶段：先做能打样的 MVP

我会建议你先上：

ASR：Qwen 实时语音识别 或 FunASR
LLM：Qwen3.5
TTS：Qwen3-TTS
Avatar：先不做 3D，先做 2D 半身或纯语音球
RTC/流式框架：LiveKit

原因很简单：
先把陪伴感做出来，比先把“脸”做得很像更重要。LiveKit 官方已经明确支持 voice agent 场景，并同时兼容传统 STT-LLM-TTS pipeline 和 realtime model 路线，很适合做编排底座。

一个实用架构
架构 1：最稳的“陪伴型”

前端(Web/App)
→ VAD/RTC
→ ASR（Qwen realtime ASR / FunASR）
→ 对话编排器
→ Qwen3.5
→ Qwen3-TTS
→ 音频播放
→ 口型/表情驱动

其中：

ASR：阿里云 Qwen 实时语音识别支持 WebSocket、流式转写、多语种、自动语种检测、复杂环境适应，文档更新时间到 2026-02-14。
TTS：Qwen3-TTS 支持流式生成、voice clone、voice design，适合“固定伴侣音色”或“按角色描述生成声音”。
Avatar 2D：Live2D 官方文档明确支持基于音频电平实时口型同步，工程接入很直接。
Avatar 3D：NVIDIA Audio2Face-3D 支持从音频到面部动画、情绪驱动表情，并输出兼容渲染引擎的 blendshapes。

这套最适合你说的“AI伴侣”。

“数字人”到底要不要一开始就上

很多人会误判：以为数字人=项目核心。
其实对 AI 伴侣来说，先决定你要的是哪一种数字人：

1) 2D 数字人

最适合陪伴产品首发。

便宜
审美统一
可做二次元伴侣
Live2D 口型同步已经很成熟
2) 3D 数字人

适合高端版、直播版、展厅版。

更像真人
开发和美术成本高
通常要配 Unreal/Unity 或 NVIDIA 路线
NVIDIA 的 Audio2Face-3D 文档明确强调实时 speech-to-facial animation 和 emotion-driven expressions。
3) 托管视频 Avatar

适合你想最快上线一个会说话的人，而不是自己啃动画。

HeyGen 这类有 Streaming Avatar / Streaming API
但我查到 HeyGen 的旧 Interactive Avatar SDK 页面写明：该能力将于 2026-03-31 sunset，建议迁移到 LiveAvatar。这个点很重要，别基于即将下线的接口重投入。
真正难的不是模型，是“陪伴系统”

如果你要做 AI 伴侣，核心其实是这几个模块：

1. 人设系统

要有：

基础设定
说话风格
情绪阈值
关系阶段
禁区和边界
2. 记忆系统

至少分 3 层：

短时记忆：本轮上下文
长期记忆：用户偏好、关系事件
剧情记忆：你们共同经历、纪念日、梗
3. 关系状态机

比如：

初识
熟悉
依赖
冲突
修复
稳定陪伴
4. 情绪调度

不是每次都“高情商”就对。
陪伴感来自：

停顿
回问
犹豫
记得你上次说的事
用相同称呼体系持续回应

这部分主要在 LLM prompt + memory + policy layer，不是 TTS 决定的。
所以从产品角度，我会把 Qwen3.5 作为“大脑”优先级放高于 Qwen3-TTS。而 TTS 的职责是把这个人格“说出来”。

我会怎么选型
你预算有限，想先验证需求
Qwen3.5
Qwen3 realtime ASR / FunASR
Qwen3-TTS
LiveKit
Live2D

这是最务实组合。

你想做“语音打电话一样自然”
优先评估 Qwen3-Omni
不够稳时，再回退到 STT-LLM-TTS 方案

因为 Qwen3-Omni 官方就是面向实时多模态/语音交互设计的。

你想做“高拟真数字人主播/客服”
大脑：Qwen3.5 或 Qwen3-Omni
声音：Qwen3-TTS
面部：Audio2Face-3D 或托管 avatar 平台
前端传输：LiveKit / WebRTC

一句话回答你最开始那个问题

不是“Qwen3.5 加 Qwen3-TTS 还是怎么样”，而是：

做 AI 伴侣 MVP：就用 Qwen3.5 + Qwen3-TTS + 实时 ASR
做强实时语音助手：优先试 Qwen3-Omni
做数字人外观：再叠 Live2D / Audio2Face / 托管 Avatar

这是目前我查到的、比较稳且不容易踩坑的路线。尤其要注意：HeyGen 旧 Interactive Avatar SDK 页面标了 2026-03-31 下线，别直接押旧接口。

如果你愿意，我下一条可以直接给你一版：“从 0 到 1 的技术架构图 + 模块清单 + MVP 开发顺序”。

ommi是开源的吗
已思考 4s

是，Qwen3-Omni 是开源的。
我查到它的官方 GitHub 仓库是公开的，许可证是 Apache License 2.0，这属于比较宽松的开源许可，通常允许商用、修改和分发，但需要保留版权和许可证声明。

另外，Qwen3-Omni 的模型权重也已经公开发布在 Hugging Face 和 ModelScope 上，可以本地下载和部署。官方页面还提到，Transformers 对 Qwen3-Omni 的代码已合入，但当时 PyPI 版本还没正式发版，所以有些场景需要从源码安装。

你可以这样理解：

代码仓库：开源，公开可看可改
模型权重：也公开可下载
许可证：Apache 2.0，适合商业项目落地，但上线前最好还是让法务/你自己再核一遍合规条款。

不过要注意一个工程上的点：
“开源”不等于“部署很轻”。Qwen3-Omni 是全模态、实时语音方向的模型，推理成本和工程复杂度一般会高于单纯的 LLM + TTS 拼装方案。这个会直接影响你做 AI 伴侣时的延迟、GPU 成本和并发。这个判断是基于其官方仓库和模型页对多模态、实时语音能力的描述做的工程推断。

你这个场景里，实话说：

要快速做 MVP：Qwen3.5 + ASR + Qwen3-TTS 往往更稳
要极致实时语音互动：再认真评估 Qwen3-Omni

下一步我可以直接帮你列一版：“AI 伴侣项目里，Qwen3-Omni 和 Qwen3.5+TTS 的成本、延迟、开发复杂度对比表”。

性能消耗对比，对比一下

我去补官方资料里的模型规模、部署建议和流式能力，再把“算力、显存、延迟、工程复杂度”拆开对比，这样你能直接拿去做方案判断。

我已经把可核实的“硬指标”抠出来了：Qwen3-Omni 公开主力模型是 30B-A3B，Qwen3-TTS 有 0.6B 和 1.7B，Qwen3.5 这边可以从 4B/9B 起步，也可以上 35B-A3B。下面我会按你真正在乎的四个维度来比：显存、延迟、并发、工程复杂度。

已思考 45s

可以，按**“性能消耗”**来比，结论很明确：

先给结论

Qwen3-Omni 更省编排复杂度，但更吃单机资源和工程调优；
Qwen3.5 + ASR + Qwen3-TTS 更容易把成本压下来，也更容易做分层扩缩容。

换成产品决策语言就是：

你要极致实时语音互动，愿意吃更高算力和更复杂部署：选 Qwen3-Omni
你要先把 AI 伴侣做出来，并把成本、延迟、并发做平衡：优先 Qwen3.5 + ASR + Qwen3-TTS
为什么会这样
1）模型体量：Omni 天生更重

Qwen3-Omni 官方主公开模型是 Qwen3-Omni-30B-A3B-Instruct，支持文本、音频、图像、视频输入，并能实时流式输出文本和自然语音。官方还建议在 Transformers 下配合 FlashAttention 2 以降低 GPU 内存占用。

而拆分方案里，各模块可以选小很多的规格：

Qwen3.5-4B：4.0B 参数，32,768 原生上下文，支持到 131,072 with YaRN。
Qwen3.5-9B：9B 参数，262,144 原生上下文，可扩展到约 1,010,000 tokens。
Qwen3-TTS：官方已放出 0.6B 和 1.7B 两档。

所以从纯模型体量看，Omni = 一个大一统多模态 30B-A3B；拆分方案 = 你可以用 4B/9B 的 LLM，再配 0.6B/1.7B 的 TTS，加一个独立 ASR 服务。这意味着拆分方案更容易按业务量做精细化配置。

2）显存/算力：拆分方案更容易压低底线

官方 Qwen 文档给了 Qwen3 系列在 NVIDIA H20 96GB 上的速度/显存测试。虽然这份 benchmark 是 Qwen3，不是 Qwen3.5/Omni 的一一对照，但它至少能说明一个稳定趋势：模型越小，单卡显存和推理负担越低；量化后还能进一步降资源。

例如在 Transformers 测试里：

Qwen3-4B BF16，输入长度 1 时，显存约 7973 MB；AWQ-INT4 可到 2915 MB。
Qwen3-8B BF16，输入长度 1 时，显存约 15947 MB；AWQ-INT4 约 6177 MB。
Qwen3-1.7B BF16，输入长度 1 时，显存约 3412 MB。

这不能直接等同于 Qwen3.5-4B/9B 和 Qwen3-TTS 的真实显存，但足够支持一个工程判断：
若你把“脑子”控制在 4B/9B 档，把 TTS 放在 0.6B/1.7B，拆分部署的资源底线通常会明显低于直接跑一个 30B 级 omni 模型。 这里我是在用同系列官方 benchmark 做工程推断，不是官方给出的 Omni 对照表。

3）首包延迟：Omni 不一定稳赢

很多人以为端到端 Omni 一定延迟最低，但产品里不一定。

Qwen3-TTS 官方明确写了两件事：

支持 极低延迟流式生成
首个音频包可以在输入单个字符后立即输出
端到端合成延迟最低可到 97ms

同时，阿里云的 Qwen 实时语音识别是专门给连续音频流实时转写设计的，支持 WebSocket、流式输入、VAD 事件和实时转写。

这意味着如果你把链路做好：

VAD/分段 → 实时 ASR → Qwen3.5（非 thinking）→ Qwen3-TTS 流式出声

你是可以把交互做到很顺的。
而 Qwen3-Omni 的优势更多在于：少一次“拼装”与模态切换，天然更适合持续音频对话，但官方我没查到一份像 Qwen3-TTS 那样明确给出“97ms 首包”的 Omni 延迟数据，所以这里不能武断说 Omni 一定更快。能确认的是，Omni 官方强调它支持实时流式语音响应。

4）并发成本：拆分方案更容易做横向扩展

这是最关键的一点。

Qwen3-Omni

一个服务里同时承担：

语音理解
文本推理
自然语音输出
可能还要吃图像/视频

这类架构的好处是体验统一；坏处是一个重实例承担全部链路。
当并发上来时，你很难只给其中一个环节单独扩容。官方资料也显示 Omni 是原生多模态、端到端统一处理。

Qwen3.5 + ASR + TTS

可以拆成三池资源：

ASR 池
LLM 池
TTS 池

业务上通常是 LLM 最贵、TTS 次之、ASR 相对更线性。
拆分后你能按压力点单独扩容，比如：

用户在“听”的时间多，就扩 TTS
用户消息量大但输出短，就扩 LLM
语音房间数暴涨，就扩 ASR/TTS 边缘节点

所以从集群利用率和成本精细控制看，拆分方案通常更优。这是系统架构层面的工程推断，和官方公开的模型规格、流式能力是一致的。

5）工程复杂度：谁更复杂，要分开看
你看“模型接入”
Omni 更简单：一个主模型搞定多模态与语音输出。
你看“生产系统”
Omni 更难调资源
拆分方案更难编排状态机

所以两边复杂度不一样：

Qwen3-Omni 的复杂度在：

大模型部署
显存和吞吐优化
实时流式链路调优
整体实例更贵

Qwen3.5 + ASR + TTS 的复杂度在：

turn-taking（轮流说话）
打断
缓冲和回声处理
ASR/TTS/LLM 三段状态管理

如果你团队偏后端基础设施强，Omni 可以玩。
如果你团队更偏应用层和产品迭代，拆分方案更稳。

一张实用对比表
Qwen3-Omni vs Qwen3.5 + ASR + Qwen3-TTS
维度	Qwen3-Omni	Qwen3.5 + ASR + Qwen3-TTS
单模型规模	公开主力是 30B-A3B	可选 4B / 9B / 35B-A3B + 0.6B / 1.7B TTS
显存压力	更高，单实例更重	可拆开部署，底线更低
首包语音延迟	官方强调实时流式，但我没查到明确首包 ms	Qwen3-TTS 官方给出最低 97ms
并发扩展	整体扩容，粗粒度	分池扩容，细粒度
系统编排	简单一些	更复杂，需要自己编排
成本优化空间	相对小	相对大
做 AI 伴侣 MVP	不一定最优	更优
做强实时语音陪聊	更优	可做，但要精调

支持上表的关键事实包括：Qwen3-Omni 的 30B-A3B 定位与实时语音流式能力、Qwen3.5 的 4B/9B/35B-A3B 产品线、Qwen3-TTS 的 0.6B/1.7B 产品线以及 97ms 流式延迟、Qwen 实时语音识别的实时流式能力。

我给你的落地建议
你现在是做 AI 伴侣 / 数字人

我建议你这样选：

方案 1：先做 MVP
ASR：Qwen 实时 ASR
LLM：Qwen3.5-4B 或 9B
TTS：Qwen3-TTS 0.6B 或 1.7B
Avatar：先 2D / Live2D

这套通常是成本最低、迭代最快的。
因为你可以先把“人设、关系、记忆、情绪陪伴”做好，这些主要由 LLM 决定，不需要一开始就上最重的实时 omni。

方案 2：第二阶段再试 Omni

当你确认用户真的高度依赖：

连续语音对话
频繁打断
低停顿感
边听边说的自然互动

再把核心链路替换成 Qwen3-Omni 做 A/B test。
这样最稳，因为你先验证“陪伴需求”，再为“实时感”付更高算力账单。

最后给一句很直接的判断

只看“性能消耗”：

Qwen3-Omni：更像“豪华一体机”，爽，但重
Qwen3.5 + ASR + Qwen3-TTS：更像“可拆可配的工作站”，更容易控成本

所以你如果现在问我一句最实在的：

AI 伴侣第一版怎么做？
我还是会选 Qwen3.5 + 实时 ASR + Qwen3-TTS。

你要的话，我下一条直接给你一版：
“单用户 / 10 并发 / 100 并发”的粗略 GPU 配置建议。

TTSR是语音转文字是吧?然后请问3.5就是大脑是吧?TTS就是它文字转语音是吧?是不是这个意思?就肯定不能用那个豪华一体机的,那个太大了,然后那个的话,那个可以微调的吗?就是那个很重的那个可以微调的吗? 我觉得还是那个比较轻的方案会好一点,就你说的第一版方案会好一点。

我先把你这几个概念再核实一遍，并顺手查一下 Qwen3.5 / Qwen3-TTS / Qwen3-Omni 有没有官方微调入口，这样我能直接给你一个明确的是/不是。

已思考 36s

对，你现在的理解基本就是对的。我帮你把术语捋顺一下：

先把名词讲清楚
1）你说的 “TTSR”

通常大家不太这么叫，业界更常见的是：

ASR / STT：语音转文字
ASR = Automatic Speech Recognition
STT = Speech-to-Text

阿里云的 Qwen 实时语音识别文档写得很明确：它是通过 WebSocket 接收实时音频流，并实时转写成文本。

所以这块你可以直接理解成：

ASR = 语音转文字

2）Qwen3.5 是不是“大脑”

对，可以这么理解。

Qwen3.5 是大语言模型系列，负责：

理解你说的话
决定怎么回复
做人设、记忆、情绪表达、关系推进
输出“要说的文字内容”

也就是你项目里的大脑 / 中枢决策层。Qwen 官方仓库把 Qwen3.5 定位为 large language model series；Qwen3 系列模型卡也明确强调多轮对话、角色扮演、创意写作、指令跟随这些能力。

所以可以简化成：

Qwen3.5 = 大脑

3）TTS 是不是“文字转语音”

对。

Qwen3-TTS 官方说明就是一套开源 Text-to-Speech 模型，支持：

把文字变成语音
流式输出
音色克隆
声音设计
情绪和韵律控制

官方还特别提到，Qwen3-TTS 支持很低延迟的流式生成，首个音频包可以很快出来。

所以：

TTS = 文字转语音

你现在的理解，可以记成这一条链路

用户说话
→ ASR 把语音转成文字
→ Qwen3.5 理解并生成回复文字
→ TTS 把回复文字再变成声音
→ 播放给用户听

这就是我前面说的“轻方案”。
这套其实最适合你现在这种 AI 伴侣第一版。

你说“豪华一体机太大了”，这个判断我认同

你说的“豪华一体机”，就是 Qwen3-Omni 这种端到端 omni 模型。
它官方定位是：原生端到端、多模态，能处理文本、图像、音频、视频，并且可以实时流式输出文本和自然语音。

这类模型的优点是：

一体化
语音互动天然更顺
少一点手工拼装

但缺点也明显：

模型更重
部署更难
推理成本更高
做 MVP 容易一开始就把自己压得太重

所以你现在倾向于先上轻方案，这个方向是对的。

你问：那个很重的 Omni，可以微调吗？

这里我给你一个严格一点的回答：

结论

理论上可以；但我目前没有查到 Qwen 官方给普通开发者提供了一套明确、完整、开箱即用的 Qwen3-Omni 微调指南。

我查到的依据有两层：

第一层：说明“理论上可调”

Hugging Face 的 Qwen3-Omni 文档里明确提到，研究团队曾经把 Qwen3-Omni-30B-A3B 微调成了 Qwen3-Omni-30B-A3B-Captioner。这至少说明：
从模型本体上讲，它是可以被 fine-tune 的。

第二层：说明“对外公开的重点还是推理/使用，不是微调”

我查到的 Qwen3-Omni 官方 GitHub README 和 Hugging Face 模型页，公开重点主要是：

安装
推理
cookbook
音视频输入输出使用方式

我没有看到一份像“官方微调教程”那样清晰的公开 end-user 文档。

所以最稳妥的说法是：

模型本身：可以微调
官方公开支持度：目前我没查到一套成熟、面向普通开发者的官方微调流程
工程难度：会比较高，明显高于只调 Qwen3.5
那轻方案能不能微调？
对 Qwen3.5

这条线更适合微调。
Qwen 官方长期有 finetuning/LoRA/Q-LoRA 这类教程与生态支持；官方 Qwen 仓库里明确提到有 full-parameter tuning、LoRA、Q-LoRA 的微调教程。

所以如果你后面要做：

伴侣风格更稳定
特定说话方式
固定人设
特定亲密表达
行为边界更稳

那优先微调 Qwen3.5 或者做 SFT / LoRA，这条路更现实。

对 Qwen3-TTS

我查到公开资料里，Qwen3-TTS 重点是：

快速使用
语音克隆
声音设计
推理部署

我没有看到官方公开的、成熟的 end-user 微调手册。

所以实操上我会建议你：

大脑层（Qwen3.5）做定制
声音层（Qwen3-TTS）先用 voice clone / voice design，不急着微调

这通常就够做第一版了。

你这个项目，第一版我建议这样定
你的理解可以定稿成：
ASR：语音转文字
Qwen3.5：大脑
Qwen3-TTS：文字转语音
你的路线建议：
先不要碰 Qwen3-Omni
先上轻方案
优先把“人设、记忆、关系感、回复风格”做好
后面再考虑要不要做 LoRA 微调 Qwen3.5
我给你的实际开发顺序
第一阶段

先做通：

ASR
Qwen3.5
Qwen3-TTS
基础前端语音收发
打断/停止播放
聊天记录
长短期记忆
第二阶段

再增强：

固定人设 prompt
记忆抽取
关系状态机
亲密度系统
声音人设统一
Qwen3.5 的 SFT / LoRA
第三阶段

再决定要不要上：

Live2D / 数字人
视觉表情
更强实时音频模型
Omni 路线
一句最直接的话

你现在的判断，我赞成：

第一版就用轻方案：ASR + Qwen3.5 + Qwen3-TTS。
这比一开始上 Qwen3-Omni 更稳，也更容易做出一个能用、能测、能迭代的 AI 伴侣。相关公开资料支持 ASR 的实时转写定位、Qwen3.5 的对话/角色扮演能力定位，以及 Qwen3-TTS 的流式语音合成定位。

你要的话，我下一条直接给你画一版：

“AI 伴侣第一版最小可行架构图 + 每一层用什么开源组件”。

可以可以可以,你换来我看,就用这个方案吧,这个挺方案,这个快一点,熟悉一点。
继续

我把这套轻方案整理成一版“能直接开工”的最小架构，顺手再核一下各组件的官方入口，避免你后面接错版本。

已思考 12s

好，那就定这套轻方案。
我直接给你一版**“AI 伴侣第一版最小可行架构”，按能最快开工**来设计。

你这版就按这条链路做

用户说话
→ ASR（语音转文字）
→ Qwen3.5（大脑，负责理解/回复/人设/记忆调用）
→ Qwen3-TTS（把回复文字转成声音）
→ 前端播放语音
→ 如果要数字人，再把音频驱动口型/表情

这套里：

Qwen-ASR-Realtime 官方就是通过 WebSocket 接收实时音频流并实时转写，支持 VAD 模式和 Manual 模式，很适合语音对话。
Qwen3.5 是官方发布的 LLM 系列，已经提供 0.8B / 2B / 4B / 9B / 27B / 35B-A3B / 122B-A10B 等档位；对你这种第一版，4B 或 9B 最合适。
Qwen3-TTS 是开源 TTS 系列，官方已发布 0.6B / 1.7B 两档，并支持流式语音生成、voice clone、voice design。
我建议你第一版的选型
最小闭环版本
后端
ASR：Qwen-ASR-Realtime
LLM：Qwen3.5-4B 或 Qwen3.5-9B
TTS：Qwen3-TTS-0.6B 先起步
编排层：你自己写一个简单的 session service
存储：MySQL / PostgreSQL + Redis
对象存储：OSS / S3，用来存音频和头像素材
前端
Web/App 前端
麦克风采集
WebSocket 实时收音
音频播放
对话气泡
中断按钮
静音/重说按钮
数字人层

第一版先别上 3D。
先做两个版本二选一：

纯语音伴侣
2D 头像 + 口型动画

这样最快。

我给你一个最实用的系统拆分
1. ASR 服务

职责只有一个：
把用户语音流转成文字

你可以直接接阿里云的 Qwen-ASR-Realtime WebSocket。官方文档说明它支持：

WebSocket 实时接入
服务端 VAD 自动断句
或者客户端自己控制断句的 Manual 模式
返回实时识别结果和最终识别结果
你第一版怎么用

直接用 VAD 模式。
原因：你不用自己先写断句逻辑，开发更快。官方文档也说明 VAD 模式下服务端会自动检测语音起止并在一句结束后返回最终结果。

2. LLM 服务

职责是：

理解用户意图
按你定义的人设说话
查询/写入记忆
决定回复文本
决定情绪标签、动作标签
这一层用什么

建议：

先上 Qwen3.5-4B
如果觉得回复质量不够，再升到 Qwen3.5-9B

Qwen3.5 官方仓库明确写了 4B 和 9B 已发布；35B-A3B 也发布了，但对你第一版没必要上那么大。

这一层怎么设计

LLM 不直接裸聊，要包一层 Companion Orchestrator，里面做：

prompt 模板
用户资料注入
长短期记忆检索
安全规则
输出格式约束

我建议让 LLM 返回结构化 JSON，比如：

{
  "reply_text": "我刚刚在听，你今天是不是有点累？",
  "emotion": "gentle",
  "speed": "slow",
  "memory_write": [
    "用户今天加班",
    "用户最近睡眠不好"
  ],
  "animation": "soft_smile"
}

这样后面 TTS 和数字人会好接很多。

3. TTS 服务

职责：

接收 LLM 生成的文字
转成语音流
按角色音色输出

Qwen3-TTS 官方说明它支持：

0.6B / 1.7B
流式 speech generation
voice clone
voice design
多语言支持
第一版建议

先上：

Qwen3-TTS-0.6B
固定一个女性或男性音色
不先折腾复杂音色克隆

因为第一版重点不是“声音像谁”，而是：

能说
稳定
延迟可接受
陪伴感在线
4. 会话编排层

这是你这个项目真正的核心。

我建议单独做一个服务，名字都可以直接叫：

companion-service

它负责：

输入
用户文本
用户 ASR 结果
用户历史资料
当前会话状态
处理
取最近 10~20 轮上下文
检索长期记忆
拼 prompt
调 Qwen3.5
解析结构化回复
触发 TTS
写回记忆
输出
文本
音频流地址 / 音频 chunk
表情标签
亲密度变化
会话日志

这层不要省。
因为 AI 伴侣的产品差异，主要不在模型本身，而在这层。

我建议的数据库结构
你至少建这几张表
users

存用户基础信息

id
nickname
gender
birthday
timezone
created_at
companion_profiles

存你的 AI 伴侣设定

id
name
persona_prompt
voice_id
avatar_id
speaking_style
boundaries
sessions

一次会话

id
user_id
started_at
ended_at
channel(web/app)
messages

每轮消息

id
session_id
role(user/assistant)
text
audio_url
emotion
created_at
memories

长期记忆

id
user_id
content
type(preference/event/relationship)
importance
created_at
relationship_state

关系状态

user_id
intimacy_score
trust_score
last_mood
updated_at
第一版先别做太复杂的“真记忆”

先做这三层就够：

A. 短时上下文

最近 10~20 轮对话直接塞进上下文。

B. 用户画像

固定字段：

名字
喜欢什么
不喜欢什么
作息
最近烦恼
C. 事件记忆

每次对话后抽 0~3 条值得记住的内容存库。

例如：

用户今天和老板开会很紧张
用户喜欢被叫“小可爱”
用户最近在准备考试

这样已经能做出“记得你”的感觉了。

你第一版的 Prompt 结构，我建议这样
System Prompt

定义伴侣的长期人格：

年龄感
说话方式
情绪边界
陪伴目标
不能做什么
Developer Prompt

定义输出规则：

简洁
不说教
多共情
多追问
每次回复 1~3 句
输出 JSON
Memory Block

塞入用户画像 + 最近重要记忆

Conversation Block

最近若干轮对话

数字人怎么接
第一版最省事的方式
方案 A：先不做数字人

只做：

聊天气泡
音频播放
一个呼吸动效圆球

这个最快。

方案 B：做 2D 数字人

只做：

立绘头像
口型张合
简单眨眼
表情切换

不要第一版就上 3D。
因为你现在最大的瓶颈不是渲染，而是对话体验和陪伴感。

前端交互，我建议你先做这几个按钮
按住说话 / 点击开始说话
停止播放
重新生成
文字显示开关
静音开关
中断当前回复

尤其是“中断当前回复”很重要。
因为语音产品如果不能打断，会很难用。

你可以直接这样分目录
project/
  frontend/
  gateway/
  services/
    asr_adapter/
    companion_service/
    tts_adapter/
    memory_service/
  models/
  prompts/
  scripts/
  infra/
你第一版最小 API
1. 开始会话

POST /api/session/start

2. 上传语音流 / 建立 WS

WS /api/asr/stream

3. 发送文本消息

POST /api/chat

4. 获取语音回复

POST /api/tts

5. 拉取历史消息

GET /api/session/{id}/messages

6. 写记忆/查记忆

POST /api/memory/extract
POST /api/memory/search

你第一版最推荐的开发顺序
第 1 步

先把这条链路打通：

麦克风 → ASR → Qwen3.5 → TTS → 播放

这是第一个里程碑。

第 2 步

再加：

聊天记录
中断
重试
固定人设 prompt
第 3 步

再加：

长期记忆
关系分数
情绪标签
2D 头像
第 4 步

再考虑：

LoRA 微调 Qwen3.5
更细的音色设计
数字人升级
你这个方案里，具体型号我建议这样起步
最稳妥起步版
ASR：Qwen-ASR-Realtime
LLM：Qwen3.5-4B
TTS：Qwen3-TTS-0.6B

理由很简单：

Qwen-ASR-Realtime 本来就是实时语音流识别接口，适合对话。
Qwen3.5 官方已经提供 4B 档，适合第一版先起。
Qwen3-TTS 官方提供 0.6B 档，适合先压资源。
如果你觉得回复不够聪明

升级成：

Qwen3.5-9B
TTS 先不变

这个升级通常比你先升级 TTS 更值。

如果你想省掉很多实时音视频基础设施

可以把 LiveKit 当实时层底座。
官方文档明确写了它的 Agents 框架可以很快搭一个 voice assistant，而且能接浏览器、终端、电话、原生 App。

但如果你现在想“先快点熟悉”，那也可以先不用 LiveKit，直接：

前端 WebSocket 传音频
后端接 ASR / LLM / TTS

这样更直白。

最后给你一版一句话架构图
[Web/App]
  ├─ 麦克风采集
  ├─ WebSocket 发音频
  ├─ 播放 TTS 音频
  └─ 展示文字/头像/状态

        ↓

[ASR Adapter]
  └─ 接 Qwen-ASR-Realtime

        ↓

[Companion Service]
  ├─ 人设 Prompt
  ├─ 会话状态
  ├─ 记忆检索
  ├─ 调 Qwen3.5
  └─ 输出 reply_text / emotion / animation

        ↓

[TTS Adapter]
  └─ 接 Qwen3-TTS

        ↓

[DB + Memory]
  ├─ 用户画像
  ├─ 会话记录
  ├─ 长期记忆
  └─ 关系状态
你现在最适合的版本

我建议你就按这个定：

第一版不上 Omni
第一版不上 3D
第一版用 Qwen-ASR-Realtime + Qwen3.5-4B + Qwen3-TTS-0.6B
先把陪伴对话体验做出来

下一条我可以直接继续给你：
“如果你是一个人开发，这个项目 7 天内怎么排开发顺序”。

你可以给一个完整的那个项目数给我们,就是我要一个完整的项目,完整的系统,就是完完全全的,不是只有MVP那么简单,这种完整的,你列出来我看看,我们应该从完整的去裁切成MVP,这样会好一点,顺顺的给我一把完整的吧。
已思考 11s

可以。下面我给你一版完整产品级 AI 伴侣 / 数字人系统蓝图，不是 MVP，而是按“完整系统先设计，再往下裁成 MVP”的思路来写。你可以把它当成 PRD + 技术架构 + 模块清单 + 迭代路线图 的合体版。这里默认技术路线仍然是你已经选定的轻方案：ASR → Qwen3.5 → Qwen3-TTS；这条路线和官方能力是匹配的：Qwen-ASR-Realtime 走 WebSocket 实时转写，Qwen3.5 提供多规格 LLM，Qwen3-TTS 提供 0.6B/1.7B、流式生成、voice clone 和 voice design。

1. 完整项目的产品定义

这个完整系统，不是“能聊几句”的机器人，而是一个长期陪伴型智能体平台。它至少包含 6 个产品面：

实时语音陪伴
文字陪伴
长期记忆与关系成长
数字人表现层
运营后台与内容配置
安全、计费、监控、实验系统

也就是说，最终项目不是一个模型服务，而是一整套：

用户端产品
智能体编排系统
模型服务层
记忆与关系系统
数字人渲染层
运营与数据平台
2. 完整系统总架构

先给你一张总图：

用户端（iOS / Android / Web / 小程序）
  ├─ 语音输入
  ├─ 文本输入
  ├─ 数字人展示
  ├─ 消息流 / 通话 UI
  ├─ 设置 / 订阅 / 隐私
  └─ 推送 / 通知

接入层
  ├─ API Gateway
  ├─ WebSocket / RTC
  ├─ Auth / Session
  └─ Rate Limit / Anti-Abuse

实时交互层
  ├─ ASR Adapter（Qwen-ASR-Realtime）
  ├─ Turn Manager（打断 / 抢话 / 静音 / VAD 状态）
  ├─ Streaming Orchestrator
  └─ TTS Adapter（Qwen3-TTS）

智能体中台
  ├─ Persona Engine（人设）
  ├─ Dialogue Engine（对话）
  ├─ Memory Engine（记忆）
  ├─ Relationship Engine（关系成长）
  ├─ Emotion Engine（情绪）
  ├─ Scenario Engine（场景模式）
  ├─ Safety Engine（安全）
  └─ Tool / RAG Engine（工具与知识）

模型层
  ├─ Qwen3.5（大脑）
  ├─ Qwen3-TTS（语音输出）
  ├─ Qwen-ASR-Realtime（语音识别）
  └─ Embedding / Rerank（记忆检索）

数字人层
  ├─ 2D Avatar / Live2D
  ├─ Lip Sync
  ├─ Expression Controller
  ├─ Idle / Gesture / Pose
  └─ 3D/视频化扩展（后续）

平台与后台
  ├─ CMS（角色、人设、剧情、活动）
  ├─ 用户后台
  ├─ 风控后台
  ├─ 运营后台
  ├─ 实验平台 A/B
  └─ 数据看板

数据层
  ├─ 用户库
  ├─ 会话库
  ├─ 记忆库
  ├─ 向量库
  ├─ 关系状态库
  ├─ 内容库
  └─ 日志 / 埋点 / 音频对象存储
3. 完整产品功能树
A. 用户侧核心功能
3.1 账户与身份
注册 / 登录
游客体验
第三方登录
设备绑定
订阅与会员
隐私授权
注销与数据删除
3.2 陪伴入口
文字聊天
语音聊天
通话模式
数字人面对面模式
睡前陪伴模式
早安/晚安模式
情绪疏导模式
学习/工作陪伴模式
3.3 AI 伴侣形象
角色选择
角色卡展示
头像/立绘/动态形象
音色选择
称呼设置
关系称谓设置
角色背景故事
3.4 对话体验
实时语音输入
实时流式文字显示
流式语音播报
打断
重说
切换文本/语音回复
上下文连续对话
多轮追问
对话摘要
3.5 关系成长
亲密度
信任度
阶段变化
专属回忆
纪念日
任务 / 羁绊事件
成长轨迹
陪伴天数
3.6 记忆与个性化
记住喜好
记住禁忌
记住重要事件
记住关系细节
允许用户查看 / 删除某条记忆
用户对 AI 的“纠正反馈”
3.7 数字人表现
口型同步
表情切换
眨眼
呼吸
站姿 / 坐姿 / 小动作
不同情绪的脸部与动作模板

Live2D 官方文档明确支持基于实时音频电平控制嘴部开合，Web/TypeScript、C++、Java 都能做；这正适合你这个 2D 数字人层。

3.8 高级功能
AI 主动发消息
日程提醒式陪伴
场景切换
角色换装
多角色宇宙
语音留言
长文信件
图片/自拍回应
语音房/多人房（后续）
B. 后台与运营功能
3.9 角色运营后台
新建角色
配 persona prompt
配说话风格
配禁区与边界
配声音
配立绘
配情绪模板
配剧情线
3.10 内容系统
节日活动
任务系统
专题话题
文案热更新
角色专属台词
关系阶段解锁文案
3.11 用户运营
留存分析
召回策略
用户分层
消费画像
付费触达
会话质量打分
3.12 风控与审核
敏感话题检测
自伤/伤人检测
未成年人防护
违规内容留痕
人工复核队列
封禁 / 限流 / 黑名单
4. 核心技术系统拆解
4.1 实时交互系统

这是最关键的一层。
完整项目里，不是简单串一下 ASR 和 TTS，而是要有一个实时会话管理器。

子模块
Session Manager：会话生命周期
Turn Manager：轮次管理
Interrupt Manager：打断
Playback Manager：语音播放控制
Streaming Orchestrator：流式编排
Latency Monitor：延迟监控
它要解决的问题
用户说话时，AI 是否立刻停嘴
用户沉默多久算一句结束
ASR 中间结果要不要给 LLM
TTS 什么时候开始首包播放
用户中断后，上一轮语音怎么取消
网络抖动时如何降级

Qwen-ASR-Realtime 官方文档写明它支持 VAD 模式和 Manual 模式，VAD 模式下由服务端自动做语音起止检测并返回实时结果与最终结果；这很适合你的通话式对话系统。

4.2 智能体编排中台

完整系统里，Qwen3.5 不是直接拿来 chat completion 就完了。
它前面要有一层 Agent Orchestrator。

这层包含 7 个引擎
1）Persona Engine

负责角色稳定性：

人设主设定
说话方式
称呼系统
禁止行为
情绪边界
关系阶段语气差异
2）Dialogue Engine

负责每轮回复生成：

输入理解
意图识别
回答策略
多轮上下文
追问与共情策略
输出结构化结果
3）Memory Engine

负责记忆管理：

短时记忆
长期记忆
事件记忆
偏好记忆
关系记忆
记忆淘汰与更新
4）Relationship Engine

负责“陪伴感”成长：

intimacy_score
trust_score
attachment_stage
mood_bond
anniversary events
conflicts / repair
5）Emotion Engine

负责情绪推断与表达：

用户情绪识别
AI 当前情绪状态
音色情绪参数
表情标签
语速/停顿调节
6）Scenario Engine

负责模式切换：

睡前安抚
叫醒
工作陪伴
倾诉模式
撒娇模式
陪学模式
节日模式
7）Safety Engine

负责安全：

危险话题检测
极端依赖预防
自伤/他伤风险
违规输出二次过滤
合规降级回复
4.3 模型服务层
LLM

Qwen3.5 官方仓库公开了多规格，从 0.8B 到 122B-A10B，其中 4B、9B、35B-A3B 对你这个场景最有参考意义。

完整系统建议：

在线主模型：Qwen3.5-4B 或 9B
高质量慢路径：Qwen3.5-35B-A3B
离线总结/记忆抽取：可单独用更大模型
ASR
在线识别：Qwen-ASR-Realtime
模式：VAD 为主，Manual 作为补充
接入：WebSocket 实时流
TTS

Qwen3-TTS 官方公开了 0.6B / 1.7B 两档，并且仓库里不只是推理示例，还有单独的 finetuning 目录和数据准备/训练流程。也就是说，它不只是能用，还具备官方公开的微调入口。

完整系统建议：

在线主 TTS：0.6B
VIP / 高质量线路：1.7B
角色语音定制：voice design / voice clone / 后续微调
微调能力

Qwen 官方总仓库明确提供了 full-parameter tuning、LoRA、Q-LoRA 教程；Qwen3-TTS 仓库还公开了 finetuning 目录与 SFT 流程示例。

所以完整项目的模型定制路线可以是：

Qwen3.5 做 LoRA/SFT：稳定角色人格、语气、恋爱风格
Qwen3-TTS 做 voice 定制：稳定音色与表达风格
5. 数据系统设计

完整系统至少分 8 类数据。

5.1 用户主数据
user_id
profile
locale
timezone
age gate
subscription
privacy flags
5.2 会话数据
session_id
channel
start/end time
latency trace
interruption stats
quality score
5.3 消息数据
role
text
partial text
audio url
emotion tag
tokens
cost
moderation result
5.4 记忆数据
memory_id
user_id
source_message_ids
memory_type
content
salience
confidence
valid_until
embedding vector
5.5 关系状态数据
intimacy_score
trust_score
dependency_risk_score
stage
anniversaries
unresolved_topics
5.6 角色内容数据
persona version
prompt template
style prompt
forbidden rules
story pack
voice pack
expression pack
5.7 运营事件数据
DAU
retention
avg session length
paid conversion
active talk minutes
TTS minute cost
ASR minute cost
5.8 风控数据
self-harm flags
harassment flags
sexual content flags
youth risk
escalation status
6. 数据库与存储建议

完整系统建议至少有这几类存储：

PostgreSQL/MySQL：主业务库
Redis：会话态、流式状态、限流
对象存储 OSS/S3：音频、头像、缓存文件
向量库：长期记忆检索
ClickHouse / OLAP：埋点分析
日志平台：错误与链路追踪
7. 完整系统的 API 与服务拆分

建议按微服务或清晰模块化拆：

核心在线服务
gateway-service
auth-service
session-service
asr-adapter-service
orchestrator-service
memory-service
relationship-service
tts-adapter-service
avatar-service
moderation-service
billing-service
notification-service
平台服务
cms-service
ops-admin-service
analytics-service
experiment-service
8. 数字人系统完整设计

你说“完整项目”，那数字人层也要完整列出来。

8.1 第一阶段主路线：2D 数字人

建议用 Live2D。原因是：

开发成熟
接 Web 前端方便
适合陪伴型角色
口型同步实现直接

Live2D 官方文档明确给出了用音频电平控制嘴部参数的方式。

子模块
Avatar Renderer
Lip Sync Controller
Expression Controller
Idle Motion Controller
Emotion-to-Expression Mapper
Asset Manager
8.2 第二阶段扩展：3D/高拟真

这时再加：

3D rig
blendshape
face animation
streaming avatar

但这一层不是你第一阶段最优先的，优先级低于“陪伴感”和“实时互动”。

9. 完整的“陪伴感”系统

这个才是项目灵魂。

9.1 人设系统

每个角色至少有：

基础身份
世界观设定
说话风格
情绪风格
喜欢的互动方式
关系推进边界
冲突处理风格
禁止输出规则
9.2 关系系统

完整项目不要只做一个 intimacy 分数。建议至少四维：

亲密度
信任度
熟悉度
依赖风险

这样可以避免产品只会“越聊越黏”，而没有健康边界。

9.3 记忆系统

分四层：

会话上下文记忆
长期画像记忆
事件记忆
关系记忆
记忆管线
对话结束后抽取候选记忆
给记忆打重要度
做去重与冲突合并
写入数据库与向量库
下轮按相关性召回
9.4 情绪系统
用户情绪识别
AI 回复情绪
音色情绪
表情情绪
语速与停顿

Qwen3-TTS 官方支持自然语言控制声音、voice design 和高质量流式生成，这正好适合把“情绪标签”送给声音层。

9.5 剧情与事件系统

完整项目里建议有一个事件引擎：

节日问候
周年纪念
回忆触发
连续任务
关系节点解锁
角色专属剧情线
10. 风控与合规系统

完整项目不能没有这一层，尤其是 AI 伴侣。

至少要有：

自伤风险检测
他伤风险检测
过度依赖预警
敏感色情与未成年人风险
政策黑白名单
高风险话题人工接管策略
回复降级模板

这是产品能不能上线的底层条件，不是“以后再说”。

11. 监控、实验和数据分析

完整项目需要三套看板：

11.1 技术看板
ASR 首字延迟
LLM 首 token 延迟
TTS 首包延迟
全链路 P50/P95
中断成功率
流式断连率
GPU 利用率
错误率
11.2 产品看板
次日/7日/30日留存
日均会话数
日均陪伴时长
文本/语音占比
角色偏好
记忆命中率
关系成长分布
付费转化
11.3 模型质量看板
用户满意度
重复回复率
跑题率
角色稳定性
风险命中率
ASR 准确率
TTS 中断率
12. 推荐技术栈
前端
Web：Next.js / React
App：Flutter 或 React Native
WebSocket 音频流
WebAudio / AudioWorklet
Live2D Web SDK
后端
Python FastAPI 或 Node.js NestJS
WebSocket 服务
Redis
PostgreSQL
向量检索
对象存储
实时框架

如果后续你要更强的实时音视频能力，LiveKit 的 Agents 框架是一个成熟底座，官方就是给 voice/video AI agent 场景设计的，支持 Python 和 Node.js agent 作为实时房间参与者。

13. 你们应该如何从“完整项目”裁成 MVP

你前面说得对：应该先看完整系统，再裁 MVP。

我建议这样裁：

必做层
账户
文本/语音聊天
ASR
Qwen3.5
Qwen3-TTS
基础会话编排
基础记忆
基础关系分数
最简单角色后台
最简单风控
埋点与日志
暂缓层
复杂剧情
多角色宇宙
高级换装
3D 数字人
多人语音房
高级运营活动
完整实验平台
后期层
模型微调平台
高级关系系统
情绪精细建模
用户主动触达系统
跨端生态
14. 一版可执行的“完整项目目录”
ai-companion/
  apps/
    web/
    mobile/
    admin/
  services/
    gateway-service/
    auth-service/
    session-service/
    asr-adapter-service/
    orchestrator-service/
    memory-service/
    relationship-service/
    tts-adapter-service/
    avatar-service/
    moderation-service/
    billing-service/
    notification-service/
    analytics-service/
    cms-service/
  packages/
    prompt-kit/
    persona-kit/
    memory-kit/
    audio-kit/
    avatar-kit/
    sdk/
  infra/
    docker/
    k8s/
    terraform/
    monitoring/
  data/
    schemas/
    migrations/
  docs/
    prd/
    architecture/
    api/
    runbooks/
15. 我给你的最终建议

对于你们现在这个项目，我会这样定义：

完整项目目标：
做一个“可持续运营的 AI 伴侣平台”，而不是只做一个语音聊天 demo。

核心路线：
用 Qwen-ASR-Realtime + Qwen3.5 + Qwen3-TTS 打造完整陪伴底座；这条路线既和官方能力对齐，也比直接上 Qwen3-Omni 更容易做成可控、可扩、可运营的产品。Qwen-ASR-Realtime 明确支持实时 WebSocket 交互和 VAD/Manual 两种模式；Qwen3.5 提供多档模型可按成本和质量分层部署；Qwen3-TTS 既支持流式语音，也支持 voice clone / voice design，并公开了 finetuning 目录。

下一步最有价值的，不是再抽象讨论，而是把这份完整蓝图落成三份文档：
《模块清单》+《数据库设计》+《开发排期》。

嗯,可以,我需要。来一个一个来吧,你先把那个模块清单给发出来。

我先把模块清单按“完整系统可落地”的粒度整理成一份结构化清单，并用官方资料把关键依赖点钉住，避免后面排期时模块边界不清。

已思考 11s

好，先给你 《完整项目模块清单》。
我按“完整系统”来列，不是 MVP；你们后面可以从这里往下裁。

这套清单默认技术主线是：

ASR：Qwen-ASR-Realtime，官方支持 WebSocket 实时音频流转写，并有 VAD / Manual 两种断句模式。
LLM：Qwen3.5，官方仓库已公开多规格模型系列。
TTS：Qwen3-TTS，官方公开了 0.6B / 1.7B、流式生成、voice clone、voice design，并且仓库里有 finetuning 目录。
2D 数字人：Live2D，官方手册支持用音频输入值驱动嘴型参数。
一、用户端模块
1. 账户与身份模块

负责用户进入系统后的账号生命周期。

子模块：

注册 / 登录
游客模式
第三方登录
设备绑定
Token 刷新
注销与数据删除
隐私授权
年龄分级入口

产出：

user_id
auth token
用户基础档案
合规状态
2. 会话入口模块

负责让用户进入“陪伴”场景。

子模块：

文本聊天入口
语音聊天入口
通话模式入口
数字人模式入口
快捷场景入口
早安
晚安
倾诉
陪学
陪工作
哄睡

产出：

session_id
当前场景 mode
当前角色 persona_id
3. 聊天界面模块

这是主界面。

子模块：

消息流 UI
语音输入按钮
文本输入框
语音播放条
打断按钮
重说按钮
文本/语音切换
表情状态显示
网络状态与加载状态

产出：

用户输入事件
播放控制事件
前端埋点
4. 角色展示模块

负责 AI 伴侣的可视化呈现。

子模块：

角色卡
头像
立绘
Live2D 模型挂载
表情状态切换
呼吸/眨眼/待机动作
换装入口
角色背景故事页
5. 用户设置模块

子模块：

称呼设置
回复风格偏好
语音开关
自动播放开关
声音选择
文本显示开关
通知设置
隐私与数据导出/删除
6. 会员与支付模块

子模块：

套餐页
订阅购买
权益展示
订单查询
支付回调
发票/账单
会员状态同步
二、实时交互模块
7. 音频采集模块

负责从前端采集用户语音。

子模块：

麦克风权限
PCM/Opus 采集
降噪/回声控制
分帧发送
静音检测
音量电平

输入：

用户语音

输出：

音频 chunk 流
8. 实时连接模块

负责长连接和实时消息通道。

子模块：

WebSocket 连接
心跳保活
重连策略
顺序消息投递
流式事件分发
backpressure 控制
9. ASR 适配模块

对接 Qwen-ASR-Realtime。

Qwen-ASR-Realtime 官方文档明确说明它通过 WebSocket 接收实时音频流并实时转写，支持 VAD 模式 和 Manual 模式。

子模块：

ASR 鉴权
音频流转发
实时识别结果接收
最终识别结果接收
VAD 模式管理
Manual 模式管理
错误码处理
ASR 延迟监控

输入：

音频 chunk

输出：

partial text
final text
10. Turn Manager 轮次管理模块

负责“谁在说话、什么时候轮到谁”。

子模块：

用户说话开始检测
用户说话结束检测
AI 说话开始/结束状态
打断规则
抢话策略
超时策略
沉默处理
轮次切分

这是语音产品必须单独存在的一层，不然对话会很乱。

11. 流式编排模块

负责把 ASR、LLM、TTS 串成一条在线链路。

子模块：

ASR partial 是否参与理解
何时触发 LLM
LLM 流式输出接入
TTS 分段触发
流式播放队列
中断后清理
会话状态同步
12. TTS 适配模块

对接 Qwen3-TTS。

Qwen3-TTS 官方仓库说明它支持 voice clone、voice design、流式语音生成，并已公开 0.6B / 1.7B 系列。

子模块：

TTS 模型调用
音色选择
说话风格参数
分句切片
流式音频输出
音频格式转换
音频缓存
TTS 失败重试

输入：

reply_text
emotion
voice_id
speed/style 参数

输出：

音频流 / 音频文件 URL
13. 播放控制模块

子模块：

音频队列
播放/暂停/停止
打断清空
自动连续播放
进度同步
首包播放优化
三、智能体中台模块
14. Persona 人设模块

这是完整系统里最核心的一块之一。

子模块：

角色基础设定
说话风格
称呼体系
边界规则
禁忌话题
情感表达风格
关系阶段语气差异
人设版本管理

输入：

persona_id

输出：

system prompt
style rules
forbidden rules
15. Dialogue 对话引擎模块

负责每轮回复生成逻辑。

子模块：

输入理解
意图识别
回复策略
共情策略
追问策略
场景化回复
结构化输出
fallback 回复

输出建议统一成结构化：

reply_text
emotion
animation
memory_write
policy_flags
16. Prompt 编排模块

子模块：

system prompt 模板
developer prompt 模板
memory block 注入
scenario block 注入
style block 注入
JSON schema 约束
prompt version 管理
17. 场景引擎模块

负责不同“陪伴模式”。

子模块：

普通陪聊
晚安哄睡
情绪安抚
陪学
陪工作
恋爱模式
节日模式
周年纪念模式
18. 情绪引擎模块

负责识别和表达情绪。

子模块：

用户情绪识别
AI 当前情绪状态
语速/停顿参数
TTS 情绪标签
表情标签
风格微调
19. 安全与合规模块

完整项目必须有。

子模块：

敏感内容检测
自伤/他伤风险检测
色情/未成年人风险
依赖风险评分
输出二次审核
降级回复
高风险上报
审计留痕
20. 工具与知识模块

如果后面要接日历、提醒、百科、RAG，都放这里。

子模块：

外部知识检索
用户资料查询
日程/提醒调用
RAG
工具权限控制
工具调用日志
四、记忆与关系系统模块
21. 短时记忆模块

子模块：

最近 N 轮上下文
轮次摘要
会话内状态
临时偏好
22. 长期记忆模块

子模块：

偏好记忆
事件记忆
人际关系记忆
情绪触发点
用户禁忌
重要日期
用户自定义记忆修正
23. 记忆抽取模块

子模块：

候选记忆抽取
重要度评分
去重
冲突合并
写入数据库
写入向量库
24. 记忆检索模块

子模块：

语义召回
规则召回
时间召回
关系召回
Top-K 排序
relevance score
25. 关系状态模块

这是 AI 伴侣区别于普通 chatbot 的关键。

子模块：

intimacy_score
trust_score
familiarity_score
dependency_risk_score
关系阶段 state
纪念日系统
冲突/修复状态
26. 用户画像模块

子模块：

基础资料
兴趣偏好
作息习惯
沟通偏好
情绪画像
历史总结
五、数字人模块
27. Avatar 渲染模块

子模块：

2D 模型加载
资源管理
角色切换
渲染层生命周期
低性能降级
28. 口型同步模块

Live2D 官方文档说明可以通过给嘴部参数设置 0 到 1 的值来控制开合，并可从音频输入映射到 lip-sync 参数。

子模块：

音频电平分析
嘴型参数映射
平滑处理
延迟对齐
多嘴型兼容
29. 表情控制模块

子模块：

开心
温柔
害羞
委屈
生气
安抚
惊讶
默认待机

输入：

emotion / animation 标签

输出：

expression state
30. 动作系统模块

子模块：

呼吸
眨眼
点头
倾斜
挥手
待机随机动作
场景动作
31. 资源管理模块

子模块：

模型资源包
贴图
动作文件
表情文件
版本控制
CDN 分发
六、平台后台模块
32. 角色 CMS 模块

运营和策划要用。

子模块：

新建角色
编辑 persona
编辑背景故事
编辑说话风格
编辑边界规则
绑定音色
绑定形象
发布/下线
版本回滚
33. 剧情与活动配置模块

子模块：

节日活动
关系节点剧情
台词包
专题事件
周年纪念事件
场景包配置
34. 用户运营后台模块

子模块：

用户查询
会话查询
留存分析
活跃分析
召回配置
标签系统
客服支持工具
35. 风控后台模块

子模块：

风险会话列表
人工复核
黑白名单
封禁
风险规则配置
申诉处理
36. 实验平台模块

子模块：

A/B 实验
prompt 实验
persona 实验
TTS 音色实验
召回策略实验
指标对比
七、数据与基础设施模块
37. 用户库模块

存用户主数据。

38. 会话库模块

存 session 和消息。

39. 记忆库模块

存结构化长期记忆。

40. 向量检索模块

如果要做长期记忆召回，建议单列。

41. 对象存储模块

存：

原始音频
TTS 音频
头像资源
数字人资源包
导出数据
42. 缓存模块

子模块：

session state
热点记忆
音色配置
角色配置
限流状态
43. 埋点与分析模块

子模块：

DAU/留存
会话时长
首字延迟
首包延迟
中断率
记忆命中率
付费转化
用户满意度
44. 日志与监控模块

子模块：

接口日志
链路追踪
GPU/CPU 指标
ASR 错误率
TTS 错误率
异常告警
审计日志
45. 计费与成本模块

子模块：

token 成本统计
ASR 分钟成本
TTS 分钟成本
用户级成本分摊
套餐额度控制
超额策略
八、服务拆分清单

如果你们按服务来拆，建议至少是这 16 个：

gateway-service
auth-service
session-service
realtime-service
asr-adapter-service
orchestrator-service
persona-service
memory-service
relationship-service
tts-adapter-service
avatar-service
moderation-service
cms-service
analytics-service
billing-service
notification-service
九、按优先级分层
P0：没有它系统跑不起来
账户与身份
聊天界面
音频采集
实时连接
ASR 适配
Turn Manager
流式编排
Qwen3.5 对话引擎
TTS 适配
播放控制
Persona 模块
短时记忆
会话库
日志监控
基础安全
P1：完整产品必须有
长期记忆
记忆抽取/检索
关系状态
用户画像
角色 CMS
会员支付
埋点分析
风控后台
数字人渲染
口型同步
表情控制
P2：上线后强化体验和运营
剧情活动配置
实验平台
主动触达
多角色宇宙
高级动作系统
精细化情绪引擎
高级成本系统
十、你们现在最应该先锁定的“主模块边界”

如果只看架构主干，完整项目先锁这 8 块就够了：

用户端
实时交互层
LLM 编排中台
记忆系统
关系系统
TTS/声音系统
数字人系统
后台运营系统

这 8 块定清楚，后面数据库设计和排期就顺了。

十一、我建议你们内部用的模块总表

给你一版适合直接贴到文档里的目录：

01 账户与身份模块
02 会话入口模块
03 聊天界面模块
04 角色展示模块
05 用户设置模块
06 会员与支付模块
07 音频采集模块
08 实时连接模块
09 ASR适配模块
10 Turn Manager模块
11 流式编排模块
12 TTS适配模块
13 播放控制模块
14 Persona人设模块
15 Dialogue对话引擎模块
16 Prompt编排模块
17 场景引擎模块
18 情绪引擎模块
19 安全与合规模块
20 工具与知识模块
21 短时记忆模块
22 长期记忆模块
23 记忆抽取模块
24 记忆检索模块
25 关系状态模块
26 用户画像模块
27 Avatar渲染模块
28 口型同步模块
29 表情控制模块
30 动作系统模块
31 资源管理模块
32 角色CMS模块
33 剧情与活动配置模块
34 用户运营后台模块
35 风控后台模块
36 实验平台模块
37 用户库模块
38 会话库模块
39 记忆库模块
40 向量检索模块
41 对象存储模块
42 缓存模块
43 埋点与分析模块
44 日志与监控模块
45 计费与成本模块

下一步最顺的就是做 《数据库设计》，因为现在模块边界已经出来了。

可以，下一步就是这个

我先把数据库设计按“完整系统可直接落库”的标准展开，同时用官方资料再把 ASR、Qwen3.5、Qwen3-TTS、Live2D 这些会影响表结构的能力点对齐一下。

已思考 14s

好，下面给你 《完整项目数据库设计》。
我会按“完整系统”来设计，不是 MVP 版；你们后面可以从这里裁切。

这套库设计默认还是你已经定下来的轻方案：

Qwen-ASR-Realtime 通过 WebSocket 接收实时音频流，并支持 VAD / Manual 两种断句模式，所以数据库里需要同时容纳实时转写片段、最终转写结果、轮次状态。
Qwen3.5 是多规格 LLM 系列，适合把“对话生成、摘要、记忆抽取、关系更新”拆成不同任务与版本管理，因此库里要有 prompt/version/model_run 这类可追踪结构。
Qwen3-TTS 支持 流式生成、voice clone、voice design，而且官方仓库里公开了 finetuning 目录，所以语音层不能只存一个 audio_url，还要留 voice profile、tts job、音频分段、声音版本。
Live2D 官方 lip-sync 手册说明可以把音频输入映射到模型参数，因此数字人层要保留 avatar asset、expression preset、lip-sync 参数映射。
一、数据库总体原则

我建议你们不要只用一套数据库硬扛全部数据，而是分成 5 类存储：

1）OLTP 主库

用 PostgreSQL 或 MySQL
存强一致业务数据：

用户
会话
消息
角色
关系状态
订单
配置
2）缓存/状态库

用 Redis
存：

session 在线状态
WebSocket 连接状态
turn manager 当前轮次
TTS 播放队列
热门 persona 配置缓存
3）对象存储

用 S3 / OSS
存：

原始语音
TTS 音频
角色资源包
Live2D 模型文件
导出数据
4）向量库

存：

长期记忆 embedding
用户画像 embedding
对话摘要 embedding
5）分析库

用 ClickHouse / BigQuery / Doris 之类
存：

埋点
会话统计
风控事件
模型质量数据
成本报表
二、分库分域设计

完整系统建议按 9 个数据域来建：

用户域
角色域
会话域
记忆域
关系域
语音域
数字人域
运营域
风控与审计域
三、核心表清单总览

先给你总表：

用户域
- users
- user_profiles
- user_preferences
- user_devices
- user_subscriptions

角色域
- companions
- companion_versions
- companion_voice_profiles
- companion_style_presets
- companion_scenario_configs

会话域
- sessions
- session_participants
- turns
- messages
- message_contents
- message_feedback
- model_runs
- prompt_snapshots

记忆域
- memories
- memory_fragments
- memory_links
- memory_embeddings
- memory_write_logs
- summaries

关系域
- relationship_states
- relationship_events
- relationship_milestones

语音域
- audio_assets
- asr_streams
- asr_segments
- tts_jobs
- tts_segments
- playback_logs

数字人域
- avatar_assets
- avatar_versions
- expression_presets
- lip_sync_profiles
- motion_presets

运营域
- campaigns
- campaign_triggers
- notifications
- experiments
- experiment_assignments
- feature_flags

风控与审计域
- moderation_events
- risk_cases
- policy_hits
- audit_logs
- consent_records

支付与成本域
- orders
- payments
- usage_ledger
- cost_ledger
四、用户域设计
1. users

用户主表。

users
- id bigint pk
- user_uuid varchar(64) unique
- status varchar(20)            -- active, banned, deleted, guest
- register_channel varchar(50)  -- ios, android, web, h5
- country_code varchar(10)
- locale varchar(20)
- timezone varchar(50)
- age_verified boolean
- birth_year int null
- created_at datetime
- updated_at datetime
- deleted_at datetime null
说明
status 不要只做 enable/disable，后面风控会用到
locale/timezone 对“早安/晚安/节日触达”很关键
age_verified 必须单列，方便未成年人策略

索引建议：

uk_user_uuid
idx_status_created_at
2. user_profiles

更偏业务画像，不跟 auth 混在一起。

user_profiles
- id bigint pk
- user_id bigint unique
- nickname varchar(50)
- gender varchar(20) null
- preferred_name varchar(50) null
- avatar_url varchar(500) null
- bio text null
- emotional_style varchar(50) null
- communication_style varchar(50) null
- updated_at datetime
3. user_preferences

用户偏好。

user_preferences
- id bigint pk
- user_id bigint
- key varchar(100)              -- preferred_voice, wakeup_time, pet_name
- value_json json
- source varchar(20)            -- explicit, inferred, imported
- confidence decimal(5,4)
- created_at datetime
- updated_at datetime

索引：

(user_id, key) unique
(user_id, updated_at)
4. user_devices

设备与推送。

user_devices
- id bigint pk
- user_id bigint
- device_id varchar(128)
- platform varchar(20)
- push_token varchar(255) null
- app_version varchar(50)
- last_active_at datetime
- created_at datetime
5. user_subscriptions

订阅状态。

user_subscriptions
- id bigint pk
- user_id bigint
- plan_code varchar(50)
- status varchar(20)            -- active, expired, canceled, grace_period
- started_at datetime
- expired_at datetime
- auto_renew boolean
- source varchar(30)            -- appstore, play, stripe, manual
- created_at datetime
- updated_at datetime
五、角色域设计
6. companions

AI 伴侣角色主表。

companions
- id bigint pk
- companion_code varchar(50) unique
- name varchar(100)
- display_name varchar(100)
- type varchar(30)              -- romantic, comfort, study, custom
- status varchar(20)            -- draft, online, offline, archived
- default_locale varchar(20)
- default_voice_profile_id bigint null
- default_avatar_asset_id bigint null
- created_at datetime
- updated_at datetime
7. companion_versions

角色版本表。
完整系统必须有，不然后面改 prompt 会乱。

companion_versions
- id bigint pk
- companion_id bigint
- version_no varchar(30)
- system_prompt text
- style_prompt text
- boundary_prompt text
- safety_prompt text
- memory_policy_json json
- relationship_policy_json json
- scenario_policy_json json
- is_published boolean
- created_by bigint
- created_at datetime
说明

这张表是 角色可追溯性核心表。
以后同一个角色不同阶段的表现差异，都能回查到具体版本。

索引：

(companion_id, is_published)
(companion_id, version_no) unique
8. companion_voice_profiles

角色声音配置。

companion_voice_profiles
- id bigint pk
- companion_id bigint
- name varchar(100)
- provider varchar(50)          -- qwen3_tts
- model_name varchar(100)
- voice_mode varchar(30)        -- preset, clone, designed, finetuned
- voice_prompt text null
- speaker_ref_audio_url varchar(500) null
- params_json json
- status varchar(20)
- created_at datetime
- updated_at datetime

Qwen3-TTS 官方支持 voice clone、voice design 和流式语音生成，所以这里不能只存一个“voice_id”；要能区分预置音色、克隆音色、设计音色和以后可能的微调音色。

9. companion_style_presets

说话风格预设。

companion_style_presets
- id bigint pk
- companion_id bigint
- style_code varchar(50)
- label varchar(100)            -- 温柔、活泼、姐姐感、恋人感
- llm_style_json json
- tts_style_json json
- avatar_style_json json
- created_at datetime
10. companion_scenario_configs

场景配置。

companion_scenario_configs
- id bigint pk
- companion_id bigint
- scenario_code varchar(50)     -- sleep, morning, comfort, study
- title varchar(100)
- prompt_patch text
- memory_filter_json json
- tts_profile_override_id bigint null
- avatar_expression_override_json json
- status varchar(20)
- created_at datetime
六、会话域设计
11. sessions

一次完整会话。

sessions
- id bigint pk
- session_uuid varchar(64) unique
- user_id bigint
- companion_id bigint
- companion_version_id bigint
- channel varchar(20)           -- text, voice, call, avatar
- mode varchar(50)              -- free_chat, sleep, study, comfort
- status varchar(20)            -- active, ended, failed, timeout
- started_at datetime
- ended_at datetime null
- first_token_latency_ms int null
- first_audio_latency_ms int null
- total_duration_ms bigint null
- last_turn_no int default 0
- created_at datetime
- updated_at datetime
说明
companion_version_id 必须冗余存，不要只靠当前角色表查，不然后面角色升级后历史不可回放
首 token / 首音频延迟值得入库，后面监控和 AB 很有用
12. session_participants

给多人房、客服介入、后续群聊留口子。

session_participants
- id bigint pk
- session_id bigint
- participant_type varchar(20)  -- user, companion, moderator
- participant_ref_id bigint
- joined_at datetime
- left_at datetime null
13. turns

轮次表。
语音产品一定要单列，不要只靠 messages 推轮次。

turns
- id bigint pk
- session_id bigint
- turn_no int
- started_by varchar(20)        -- user, assistant, system
- input_mode varchar(20)        -- text, voice
- asr_stream_id bigint null
- status varchar(20)            -- collecting, processing, speaking, done, interrupted
- user_started_at datetime null
- user_ended_at datetime null
- llm_started_at datetime null
- llm_ended_at datetime null
- tts_started_at datetime null
- tts_ended_at datetime null
- interrupted_by varchar(20) null
- created_at datetime
- updated_at datetime
说明

Qwen-ASR-Realtime 有 VAD 和 Manual 两种模式，并返回实时结果和最终结果，所以 turn 级别必须能记录“采集中、处理中、播报中、被打断”。

索引：

(session_id, turn_no) unique
(session_id, status)
14. messages

消息头表。

messages
- id bigint pk
- session_id bigint
- turn_id bigint
- role varchar(20)              -- user, assistant, system
- message_type varchar(20)      -- text, voice, event, summary
- status varchar(20)            -- partial, final, revoked, failed
- created_at datetime
- updated_at datetime
15. message_contents

消息内容表。
把内容拆开，后续扩展更稳。

message_contents
- id bigint pk
- message_id bigint
- text_content longtext null
- normalized_text longtext null
- language varchar(20) null
- emotion_label varchar(50) null
- animation_label varchar(50) null
- audio_asset_id bigint null
- content_json json null
- created_at datetime
为什么拆表

因为后面可能有：

partial 文本
最终文本
音频
动作标签
结构化输出 JSON

放一张表会很快变脏。

16. message_feedback

用户对单条回复的反馈。

message_feedback
- id bigint pk
- message_id bigint
- user_id bigint
- rating int null               -- 1~5
- action varchar(30)            -- like, dislike, report, regenerate
- reason_code varchar(50) null
- comment text null
- created_at datetime
17. model_runs

模型调用日志。
这个非常关键，别省。

model_runs
- id bigint pk
- session_id bigint
- turn_id bigint
- message_id bigint null
- model_provider varchar(50)    -- qwen
- model_name varchar(100)       -- qwen3.5-4b, qwen3-tts-0.6b
- task_type varchar(30)         -- chat, summary, memory_extract, tts, asr_post
- prompt_snapshot_id bigint null
- input_tokens int null
- output_tokens int null
- latency_ms int
- status varchar(20)
- cost_amount decimal(18,6) null
- request_meta_json json
- response_meta_json json
- created_at datetime
说明

Qwen3.5 是多规格模型系列，完整项目里通常不会只跑一种调用；你会有：

主对话
记忆抽取
摘要
关系更新
风险复判
所以 task_type 必须独立。
18. prompt_snapshots

prompt 快照表。

prompt_snapshots
- id bigint pk
- session_id bigint
- turn_id bigint
- prompt_type varchar(30)       -- chat, summary, memory_extract
- companion_version_id bigint
- system_prompt longtext
- developer_prompt longtext
- memory_block longtext null
- scenario_block longtext null
- user_context_block longtext null
- output_schema_json json null
- created_at datetime
说明

以后你们做 A/B、查问题、复盘输出漂移，这张表是命根子。

七、记忆域设计
19. memories

长期记忆主表。

memories
- id bigint pk
- user_id bigint
- companion_id bigint
- memory_type varchar(30)       -- preference, event, relationship, taboo, schedule
- title varchar(200)
- content text
- salience_score decimal(6,4)
- confidence_score decimal(6,4)
- source_type varchar(20)       -- inferred, explicit, imported
- valid_status varchar(20)      -- active, superseded, deleted, expired
- happened_at datetime null
- created_at datetime
- updated_at datetime
20. memory_fragments

细粒度记忆片段。
用于一个 memory 下挂多个事实点。

memory_fragments
- id bigint pk
- memory_id bigint
- key_name varchar(100)         -- favorite_food, boss_name, exam_date
- value_text text
- value_json json null
- confidence_score decimal(6,4)
- created_at datetime
- updated_at datetime
21. memory_links

记忆与来源消息的关联。

memory_links
- id bigint pk
- memory_id bigint
- source_message_id bigint
- source_turn_id bigint null
- relation_type varchar(30)     -- extracted_from, confirmed_by, contradicted_by
- created_at datetime
22. memory_embeddings

向量索引映射表。

memory_embeddings
- id bigint pk
- memory_id bigint
- embedding_model varchar(100)
- vector_ref varchar(128)       -- 向量库里的主键
- text_for_embedding text
- created_at datetime
23. memory_write_logs

记忆写入日志。

memory_write_logs
- id bigint pk
- session_id bigint
- turn_id bigint
- model_run_id bigint
- operation varchar(20)         -- insert, update, merge, delete
- memory_id bigint null
- before_json json null
- after_json json null
- created_at datetime
24. summaries

摘要表。

summaries
- id bigint pk
- user_id bigint
- session_id bigint null
- summary_type varchar(30)      -- session_summary, weekly_summary, profile_summary
- content longtext
- source_range_json json
- model_run_id bigint
- created_at datetime
八、关系域设计
25. relationship_states

用户与角色的当前关系快照。

relationship_states
- id bigint pk
- user_id bigint
- companion_id bigint
- intimacy_score decimal(8,2)
- trust_score decimal(8,2)
- familiarity_score decimal(8,2)
- dependency_risk_score decimal(8,2)
- stage_code varchar(30)        -- stranger, familiar, close, bonded
- mood_state varchar(30) null
- last_significant_event_at datetime null
- updated_at datetime

索引：

(user_id, companion_id) unique
26. relationship_events

关系变化流水。

relationship_events
- id bigint pk
- user_id bigint
- companion_id bigint
- session_id bigint null
- turn_id bigint null
- event_type varchar(50)        -- comfort_success, conflict, anniversary, deep_talk
- delta_intimacy decimal(8,2)
- delta_trust decimal(8,2)
- delta_dependency_risk decimal(8,2)
- reason_json json
- created_at datetime
27. relationship_milestones

里程碑。

relationship_milestones
- id bigint pk
- user_id bigint
- companion_id bigint
- milestone_code varchar(50)
- title varchar(100)
- reached_at datetime
- meta_json json null
九、语音域设计
28. audio_assets

统一音频资产表。

audio_assets
- id bigint pk
- asset_type varchar(30)        -- user_raw, asr_ref, tts_output, cloned_voice_ref
- storage_provider varchar(30)
- bucket_name varchar(100)
- object_key varchar(500)
- duration_ms int null
- sample_rate int null
- channels int null
- format varchar(20) null
- size_bytes bigint null
- checksum varchar(128) null
- created_at datetime
29. asr_streams

一次 ASR 流会话。

asr_streams
- id bigint pk
- session_id bigint
- turn_id bigint
- provider varchar(50)          -- qwen_asr_realtime
- mode varchar(20)              -- vad, manual
- ws_connection_id varchar(100) null
- language_hint varchar(20) null
- status varchar(20)            -- started, committed, completed, failed
- raw_audio_asset_id bigint null
- started_at datetime
- ended_at datetime null
- created_at datetime

Qwen-ASR-Realtime 官方明确支持 VAD / Manual 两种模式，所以 mode 必须是一级字段。

30. asr_segments

ASR 片段结果表。

asr_segments
- id bigint pk
- asr_stream_id bigint
- seq_no int
- segment_type varchar(20)      -- partial, final
- text_content text
- start_ms int null
- end_ms int null
- confidence_score decimal(6,4) null
- is_committed boolean
- created_at datetime
说明

因为官方返回实时结果和最终结果，所以 segment_type 一定要有 partial/final。

31. tts_jobs

一次 TTS 任务。

tts_jobs
- id bigint pk
- session_id bigint
- turn_id bigint
- message_id bigint
- provider varchar(50)          -- qwen3_tts
- model_name varchar(100)
- voice_profile_id bigint
- input_text longtext
- input_ssml text null
- style_params_json json null
- status varchar(20)            -- queued, running, completed, failed, canceled
- first_packet_latency_ms int null
- total_latency_ms int null
- audio_asset_id bigint null
- created_at datetime
- updated_at datetime
32. tts_segments

流式 TTS 分段。

tts_segments
- id bigint pk
- tts_job_id bigint
- seq_no int
- text_chunk text null
- audio_asset_id bigint null
- duration_ms int null
- created_at datetime

Qwen3-TTS 官方支持流式语音生成，所以如果你们前端要边生成边播，这张表很有价值。

33. playback_logs

播放日志。

playback_logs
- id bigint pk
- session_id bigint
- turn_id bigint
- tts_job_id bigint
- user_id bigint
- action varchar(20)            -- start, stop, pause, resume, interrupted, finished
- position_ms int null
- created_at datetime
十、数字人域设计
34. avatar_assets

数字人资源主表。

avatar_assets
- id bigint pk
- companion_id bigint
- avatar_type varchar(20)       -- live2d, image, 3d
- name varchar(100)
- cover_url varchar(500)
- resource_manifest_json json
- status varchar(20)
- created_at datetime
- updated_at datetime
35. avatar_versions

数字人版本表。

avatar_versions
- id bigint pk
- avatar_asset_id bigint
- version_no varchar(30)
- model_file_url varchar(500)
- texture_pack_json json
- motion_pack_json json
- expression_pack_json json
- is_published boolean
- created_at datetime
36. expression_presets

表情预设。

expression_presets
- id bigint pk
- avatar_asset_id bigint
- expression_code varchar(50)   -- happy, shy, gentle, sad
- display_name varchar(100)
- param_json json
- created_at datetime
37. lip_sync_profiles

口型同步映射。

lip_sync_profiles
- id bigint pk
- avatar_asset_id bigint
- profile_name varchar(100)
- mouth_open_param varchar(100)
- mouth_form_param varchar(100) null
- gain decimal(8,4)
- smoothing decimal(8,4)
- delay_ms int
- mapping_json json
- created_at datetime

Live2D 官方说明 lip-sync 依赖 .model3.json 里映射到参数的配置，所以这里需要保留参数映射和增益/平滑配置。

38. motion_presets

动作预设。

motion_presets
- id bigint pk
- avatar_asset_id bigint
- motion_code varchar(50)
- motion_group varchar(50)      -- idle, greeting, comfort
- resource_url varchar(500)
- trigger_rule_json json
- created_at datetime
十一、运营域设计
39. campaigns

活动表。

campaigns
- id bigint pk
- campaign_code varchar(50) unique
- title varchar(200)
- campaign_type varchar(30)     -- holiday, anniversary, growth
- status varchar(20)
- start_at datetime
- end_at datetime
- config_json json
- created_at datetime
40. campaign_triggers

触发器。

campaign_triggers
- id bigint pk
- campaign_id bigint
- trigger_type varchar(30)      -- date, relationship_stage, event_count
- trigger_rule_json json
- created_at datetime
41. notifications

通知与主动触达。

notifications
- id bigint pk
- user_id bigint
- companion_id bigint
- type varchar(30)              -- push, inbox, sms, email
- title varchar(200)
- content text
- status varchar(20)            -- pending, sent, clicked, failed
- scheduled_at datetime null
- sent_at datetime null
- meta_json json
- created_at datetime
42. experiments

实验表。

experiments
- id bigint pk
- experiment_code varchar(50) unique
- name varchar(200)
- target_type varchar(30)       -- prompt, voice, avatar, scenario
- status varchar(20)
- config_json json
- started_at datetime null
- ended_at datetime null
- created_at datetime
43. experiment_assignments

实验分桶。

experiment_assignments
- id bigint pk
- experiment_id bigint
- user_id bigint
- bucket_code varchar(50)
- assigned_at datetime
44. feature_flags

功能开关。

feature_flags
- id bigint pk
- flag_key varchar(100) unique
- description varchar(255)
- scope varchar(20)             -- global, user, plan, companion
- rule_json json
- enabled boolean
- updated_at datetime
十二、风控与审计域设计
45. moderation_events

单次风控命中。

moderation_events
- id bigint pk
- session_id bigint
- turn_id bigint null
- message_id bigint null
- source_side varchar(20)       -- user_input, model_output
- risk_type varchar(50)         -- self_harm, violence, sexual, minor
- score decimal(6,4)
- decision varchar(20)          -- allow, block, escalate, soften
- raw_result_json json
- created_at datetime
46. risk_cases

风险案件表。

risk_cases
- id bigint pk
- user_id bigint
- session_id bigint null
- severity varchar(20)          -- low, medium, high, critical
- case_type varchar(50)
- status varchar(20)            -- open, reviewing, resolved, ignored
- assigned_to bigint null
- created_at datetime
- updated_at datetime
47. policy_hits

策略命中明细。

policy_hits
- id bigint pk
- moderation_event_id bigint
- policy_code varchar(100)
- rule_version varchar(30)
- hit_detail_json json
- created_at datetime
48. audit_logs

审计日志。

audit_logs
- id bigint pk
- actor_type varchar(20)        -- user, admin, system
- actor_id bigint null
- action varchar(100)
- target_type varchar(50)
- target_id bigint
- before_json json null
- after_json json null
- created_at datetime
49. consent_records

用户授权记录。

consent_records
- id bigint pk
- user_id bigint
- consent_type varchar(50)      -- privacy, voice_clone, marketing_push
- version_no varchar(30)
- granted boolean
- granted_at datetime
- revoked_at datetime null
十三、支付与成本域设计
50. orders
orders
- id bigint pk
- order_no varchar(64) unique
- user_id bigint
- plan_code varchar(50)
- amount decimal(18,2)
- currency varchar(10)
- status varchar(20)
- source varchar(30)
- created_at datetime
- paid_at datetime null
51. payments
payments
- id bigint pk
- order_id bigint
- provider varchar(30)
- provider_txn_no varchar(128)
- amount decimal(18,2)
- status varchar(20)
- callback_payload_json json
- created_at datetime
- updated_at datetime
52. usage_ledger

用户维度用量账本。

usage_ledger
- id bigint pk
- user_id bigint
- session_id bigint null
- usage_type varchar(30)        -- llm_tokens, asr_seconds, tts_seconds
- quantity decimal(18,4)
- unit varchar(20)
- source_ref_id bigint null
- created_at datetime
53. cost_ledger

系统维度成本账本。

cost_ledger
- id bigint pk
- model_run_id bigint null
- usage_type varchar(30)
- provider varchar(50)
- model_name varchar(100)
- cost_amount decimal(18,6)
- currency varchar(10)
- created_at datetime
十四、表关系主线

最核心的链路是：

users
  -> sessions
    -> turns
      -> messages
        -> message_contents
      -> asr_streams
        -> asr_segments
      -> model_runs
      -> tts_jobs
        -> tts_segments

users
  -> memories
    -> memory_fragments
    -> memory_links
    -> memory_embeddings

users + companions
  -> relationship_states
  -> relationship_events

companions
  -> companion_versions
  -> companion_voice_profiles
  -> avatar_assets
    -> avatar_versions
    -> expression_presets
    -> lip_sync_profiles
十五、你们最该注意的几个设计点
1）消息和轮次必须拆开

这是语音系统最容易设计错的地方。

turns 负责“过程”
messages 负责“内容”

因为一次 turn 里可能出现：

ASR partial
ASR final
LLM partial
LLM final
TTS streamed audio
interruption

如果不拆，后面系统会越来越脏。

2）prompt 和 model run 必须留档

完整产品到中后期，最常见的问题不是“模型不会说”，而是：

为什么这个角色昨天还正常，今天变味了
为什么这个用户命中了错误记忆
为什么这个实验留存变差了

这些都得靠：

prompt_snapshots
model_runs
companion_versions

来查。

3）记忆不要只做一张表

至少拆成：

memories
memory_links
memory_embeddings

因为长期记忆系统本质上是：
事实存储 + 来源追踪 + 语义召回
三件事不是一回事。

4）语音系统必须保留分段结果

Qwen-ASR-Realtime 会给你实时结果和最终结果；Qwen3-TTS 支持流式输出，所以：

asr_segments
tts_segments

这两张表别省。

5）角色、声音、数字人都要版本化

因为：

人设会改
音色会改
头像动作会改

不做版本化，历史会话永远复盘不出来。

十六、第一版真正必建的表

虽然这是完整设计，但你们马上开工的话，最小完整骨架先建这些：

用户与角色
users
user_profiles
companions
companion_versions
companion_voice_profiles
会话与消息
sessions
turns
messages
message_contents
model_runs
prompt_snapshots
记忆与关系
memories
memory_links
relationship_states
relationship_events
语音
audio_assets
asr_streams
asr_segments
tts_jobs
tts_segments
数字人
avatar_assets
expression_presets
lip_sync_profiles
风控与运营
moderation_events
audit_logs
usage_ledger
cost_ledger
十七、推荐的命名和工程约定

建议统一约定：

所有主表都有：
id
created_at
updated_at
所有状态字段统一枚举风格：
status
type
mode
所有复杂扩展字段用：
xxx_json
所有多版本实体必须有：
version_no
is_published
所有外部资源统一走：
audio_assets
avatar_assets

这样后面工程最好维护。

十八、我给你的落地建议

下一步最顺的，不是再继续抽象，而是把这份数据库设计继续落成两份：

ER 图
建表 SQL 初稿

因为现在模块清单和数据库主干已经齐了，接下来直接进入“能开工”的文档形态最合适。

你觉得先APP还是小程序还是

我查一下现在的小程序、原生/跨端 App 和应用商店/分发侧的现实约束，再给你一个直接可执行的判断，不空谈。

已思考 24s

我会直接给判断：先做 App，再补小程序。
你这个项目是 AI 伴侣 / 数字人 / 实时语音陪聊，核心竞争力不在“能不能打开”，而在实时语音体验、长时留存、推送唤回、付费订阅、稳定播放和打断控制。这些维度上，原生/跨端 App 通常都比小程序更适合做第一主阵地。LiveKit 现在对 Android、iOS 都有成熟的实时音视频/语音 SDK 和 quickstart，比较贴合你前面定下来的语音实时方案。

我的推荐顺序
路线一：最稳

App 先做主产品
然后做：

H5 落地页 用来介绍、引流、收集预约
小程序 作为轻入口和裂变入口
后面再做更完整的小程序版

这个顺序最适合你现在。因为你要做的不是轻工具，而是一个高频、长时、强关系、强语音产品。App 更适合承接这种产品心智。苹果对账号体系、订阅、账号删除等要求也很明确，说明 App 生态对“长期账户关系”和“持续付费产品”是成熟的；但这也意味着你要按平台规范把账号删除、订阅管理等基础能力做好。

为什么不是先小程序
1. 你这个产品的“爽点”在实时语音，不在轻触达

AI 伴侣最重要的是：

说话要顺
打断要自然
音频播放要稳
连接要稳
会话要能持续很久

LiveKit 官方现在把移动端 voice AI 场景单独做了 Android quickstart，也有跨平台实时 SDK 体系，这对 App 明显更友好。

2. 小程序更适合“轻入口”，不适合先做“主体验”

小程序当然能做语音，不是不能做。现实里也能通过录音、分帧、WebSocket 往后端送音频，再拿回识别或 TTS 结果；很多开发实践都这么干。
但从产品策略上，小程序更适合：

拉新试用
分享传播
快速体验
简单文本/轻语音版

不太适合你一上来就把它当最终主战场。因为你后面还要做：

推送召回
长关系沉淀
付费订阅
更稳定的音频链路
更重的数字人体验

这些更适合放在 App 里先做扎实。

什么时候先小程序反而是对的

只有这几种情况，我才会建议你先小程序：

情况 A：你现在主要目标是验证拉新，不是验证体验

比如你想先看：

有没有人愿意点进来
愿不愿意聊 3 分钟
什么角色更吸引人
什么文案转化高

那小程序会更快，因为进入门槛低、传播链路短。这个适合“市场验证”。

情况 B：你现在没有足够人力做双端 App

如果团队现在人少，前端移动端经验弱，小程序可以先做一个：

文本聊天
短语音输入
简单 TTS 播放
轻量 2D 展示

但我会把它定义成验证器，不是最终主产品。

你这个项目，我更建议怎么落
第一优先级

先做 App 主产品

我会建议：

移动端先做一个主端
最好用 Flutter 或 React Native 做一版跨端
语音实时链路直接按你前面定的
ASR → Qwen3.5 → Qwen3-TTS
数字人先上 2D 轻展示

原因是这样你能更快拿到：

更完整的会话体验
更真实的留存数据
更稳定的付费和账号体系
更像“陪伴产品”的日常使用场景
第二优先级

再做小程序轻入口

小程序版建议只承接：

新用户首次体验
角色展示
轻量语音试聊
活动裂变
引导下载 App

也就是把小程序当成：
获客前台，不是核心陪伴容器。

如果你逼我二选一
我会这样拍板

先 App。

因为你现在不是在做“AI 工具”，而是在做“AI 关系型产品”。
关系型产品最值钱的是：

复访
依赖
陪伴时长
付费持续性

这些都更偏 App。苹果的规则也能反过来说明，App 生态默认你要认真处理账号、订阅、删除、隐私这些长期关系问题，而这正符合 AI 伴侣产品形态。

给你一个很实用的决策表
先 App，适合你现在

如果你更看重：

实时语音体验
长时陪伴
会员订阅
推送召回
更稳的数字人展示
后续做成正式产品

选 App。

先小程序，只适合验证市场

如果你更看重：

上线快
易传播
低门槛试用
拉新验证
活动转化

选 小程序。不过在你这个项目里，我还是把它放第二阶段。

我替你定一个更具体的实施顺序
Phase 1

App 主产品

文本聊天
实时语音
TTS 播放
基础记忆
关系成长
2D 角色
Phase 2

小程序引流版

轻体验
活动传播
新用户试聊
引导下载 App
Phase 3

再看要不要把小程序做成半正式端
前提是你发现微信生态给你带来的拉新成本特别低、转化特别高。

最后一句结论

你现在最该先做的是 App，不是小程序。
小程序适合后面做“入口”和“增长”，App 适合先把“陪伴体验”和“产品闭环”做对。

下一步你要的话，我可以继续直接给你一版：
“如果先做 App，iOS/Android/Flutter/React Native 该怎么选”。

肯定是APP的，然后是安卓，然后怎么弄，接下来呢，我手机我安卓13

我去把 Android 13 上做实时语音 App 会碰到的关键约束一起查掉，然后给你一条“从现在开始怎么做”的开发顺序，不只说框架名。

已思考 16s

对，就按这个走：先做 Android App。
而且你手上是 Android 13 手机，这很合适做第一台真机测试机，因为你会正好碰到现在语音 App 最关键的两个现实点：麦克风权限和 通知权限。Android 13 开始，通知权限 POST_NOTIFICATIONS 需要运行时申请；语音录制则需要 RECORD_AUDIO。

我建议你下一步就这么推进
第一步：先定技术路线

你现在不要一上来就写业务逻辑，先定开发框架。

我对你这个项目的建议是：

客户端：先用 Flutter
后端：你的语音链路还是按之前定的
ASR → Qwen3.5 → Qwen3-TTS
实时层：先用 WebSocket
数字人：先不上复杂 3D，先做简单 UI 或 2D

为什么我这里先推 Flutter：
Flutter 官方现在的安装、Android 配置、构建发布路径都比较完整，适合你这种“先 Android，后面还大概率会上 iOS”的项目；后面你不用重写一套 UI。

第二步：先把你的开发环境搭起来

你现在这台 Android 13 手机，可以直接当开发测试机。

你要准备的是：

Android Studio
Flutter SDK
Android SDK
USB 数据线
打开手机开发者选项和 USB 调试

Flutter 官方文档现在把安装 Flutter、配置 Android 开发环境分开讲得很清楚，适合直接照着做。

你手机这边要做的事

在 Android 13 手机上：

打开“关于手机”
连点版本号，开启开发者选项
打开 USB 调试
用数据线连电脑
第一次连接时允许这台电脑调试

这样你后面可以直接把 App 装到自己手机上跑。

第三步：先做一个“空壳 App”

先别急着做 AI 伴侣全功能。
你先把一个最小 Android 客户端壳子做出来，页面就 3 块：

顶部：角色头像 / 名字 / 状态
中间：聊天消息流
底部：说话按钮 + 停止播放按钮

你第一版 Android 客户端只需要先支持这几个动作：

点按钮开始录音
点按钮结束录音
把音频发到后端
收到文字结果后显示
收到 TTS 音频后播放

这一步的目标不是“产品完整”，而是把端到端链路跑通。

第四步：先做权限层

你是 Android 13，必须先把权限这一层想清楚。

必要权限
1）麦克风权限

语音 App 必要。你要申请：

RECORD_AUDIO
2）通知权限

如果你后面要做：

前台录音提示
主动消息提醒
陪伴唤回
后台播放状态通知

那 Android 13 上需要申请：

POST_NOTIFICATIONS

Android Developers 官方文档明确说，Android 13 引入了通知运行时权限，应用必须在合适的上下文中申请。

你现在该怎么做

第一版建议：

进 App 时不要立刻弹通知权限
先在真正需要时再申请
麦克风权限在第一次点“开始说话”时申请

这个用户体验更顺。

第五步：先做“语音输入 → 后端 → 文本返回”

别一开始就做 TTS。
先只做：

录音 → 发后端 → 后端 ASR → 返回文本 → UI 展示

因为这一步最容易验证：

音频采集对不对
WebSocket 或上传链路对不对
ASR 接得对不对
文本 UI 流程顺不顺

Qwen-ASR-Realtime 官方就是按 WebSocket 实时音频流来设计的，而且有 VAD 和 Manual 两种模式。你第一版建议先走 VAD 模式，省很多断句判断工作。

第六步：再加“大脑”

也就是把 Qwen3.5 接进去。

这一层你先别做太复杂，先让后端完成这件事：

收到 ASR 最终文本
拼一个固定 prompt
调 Qwen3.5
返回 reply_text

客户端这时只负责：

展示用户消息
展示 AI 回复文字

这样你先确认“对话脑子”是通的。

第七步：最后再加 TTS

等文字回复稳定了，再接 Qwen3-TTS。

这一阶段客户端需要多一个功能：

播放服务端返回的音频

你可以先不用做边生成边播，先做“整段音频返回后播放”。
等通了以后，再升级成流式。

Qwen3-TTS 官方支持流式语音生成，所以后面你要做更顺滑的说话体验，是有技术路线可走的。

第八步：你要不要现在就上 LiveKit？

我的建议是：

第一版先不上

如果你现在还在“把 Android 端跑起来”的阶段，先别急着接 LiveKit。
先用你熟悉的后端接口把：

录音
传输
文本回显
音频播放

这条线打通。

第二版再考虑

等你要做：

真正实时连续通话
更自然打断
边听边说
更稳定的房间连接

再认真接 LiveKit。
LiveKit 官方现在已经有 Android Voice AI quickstart，而且明确提供了 Kotlin/Compose 的 Android 语音 AI 起步方案。

第九步：Android 13 上你要特别注意的坑
1）通知权限

不申请就不能正常发通知。
这会影响：

后台提醒
前台服务通知体验
陪伴消息唤回

Android 13 文档已经写得很明确。

2）前台服务

如果你后面要做长时间录音、通话中持续服务、后台语音会话，你迟早会碰到 Foreground Service。Android 官方现在要求在清单里声明前台服务类型；如果你目标 API 到 34 及以上，还要请求对应权限。

这对你现在的意义是：

Android 13 测试机能先跑
但你设计项目时就要把“前台服务”留出来
不然等你要上后台持续语音时会返工
第十步：我替你排一个最顺的开发顺序
第 1 周

把 Android 客户端壳子搭起来

Flutter 安装
Android Studio 配好
真机运行成功
基础页面完成
麦克风权限申请完成
第 2 周

做语音输入链路

录音
上传/流式发送
接 ASR
返回文字
页面展示文本
第 3 周

接 Qwen3.5

后端对接大脑
返回 AI 文本
UI 完整聊天流
第 4 周

接 Qwen3-TTS

服务端合成音频
客户端播放
停止/打断
第 5 周

补体验层

会话记录
基础记忆
角色头像
简单状态动画
你现在最适合的技术决策

我替你拍板会是这样：

客户端框架：Flutter
首发平台：Android
测试设备：你这台 Android 13 手机
实时方式：先 WebSocket
第一阶段不做：LiveKit、3D 数字人、复杂后台保活
第一阶段必须做：录音、权限、ASR、Qwen3.5、TTS、播放控制
一句话总结你现在该干嘛

先把 Android 开发环境搭好，然后先做一个能“录音 → 出文字”的 Android App，再往上叠 Qwen3.5 和 Qwen3-TTS。
这条路最顺，也最不容易一开始把自己搞复杂。Flutter 的安装与 Android 集成路径、Android 13 的通知权限要求、以及 LiveKit 的 Android 语音 AI 起步资料，都已经比较成熟。

下一条我可以直接给你一份 Android 端开发待办清单，按“今天就能开始做”的粒度列出来。

可以
已思考 5s

可以，下面这份就是你现在能直接照着做的 Android 端开发待办清单。
我按“先把 Android App 跑起来”来排，不空谈。

你现在的基础前提已经很清楚了：

先做 Android App
设备是 Android 13
技术链路是 ASR → Qwen3.5 → Qwen3-TTS
Android 13 需要特别注意 麦克风权限 和 通知权限；通知权限 POST_NOTIFICATIONS 从 Android 13 开始是运行时权限。
Qwen-ASR-Realtime 官方明确是 WebSocket 实时音频流，支持 VAD 和 Manual 两种模式。
一、先定目标

你第一阶段的 Android 客户端，不要追求“完整 AI 伴侣”，只追求这 4 件事：

能装到你手机上
能录音
能把语音发到后端并拿回文字
能把 AI 回复的音频播放出来

也就是说，你先做一个：

“会听、会显示、会说”的 Android 壳子

二、今天先做的事情
1. 装开发环境

先把 Flutter + Android 开发环境装好。Flutter 官方现在把安装 Flutter 和 Android 开发环境配置分开写得很清楚，Android 端还专门有 setup 页面。

你今天先完成这几项：

安装 Android Studio
安装 Flutter SDK
配好 Android SDK
配好环境变量
终端执行 flutter doctor
确保 Android toolchain 是绿色的
验收标准

你终端里运行：

flutter doctor

至少要看到：

Flutter OK
Android toolchain OK
Android Studio OK
Connected device 能识别你的手机
2. 把你的 Android 13 手机接上

手机上先做：

打开开发者选项
打开 USB 调试
用数据线连电脑
允许这台电脑调试
验收标准

Android Studio 或 flutter devices 能看到你的手机。

3. 新建一个 Flutter 项目

先不要考虑业务架构，先建壳子。

项目先做这 3 个页面元素：

顶部：角色头像、名称、在线状态
中间：聊天消息列表
底部：录音按钮、停止按钮、发送按钮
验收标准

App 能在你 Android 13 手机上正常启动。

三、第一批必须做的客户端模块
4. 权限模块

这是 Android 13 第一关。

必做权限
录音权限：RECORD_AUDIO
通知权限：POST_NOTIFICATIONS

Android 官方文档明确说明，Android 13 引入 POST_NOTIFICATIONS 运行时权限；只有用户允许后，应用才能正常发通知。

你的做法

第一版不要一打开 App 就全弹。

建议这样：

第一次点“开始说话”时，申请 录音权限
后面真正要做提醒/前台通知时，再申请 通知权限
验收标准
用户第一次点录音时能触发授权
拒绝后页面有明确提示
允许后进入录音状态
5. 音频采集模块

你先做最简单版本：

点击按钮开始录音
再点一次结束录音
得到音频数据
发给后端

第一版不一定非要先做复杂流式；你可以先做：

短录音上传
或者
简单 WebSocket 分帧

不过因为你后端的 Qwen-ASR-Realtime 官方就是 WebSocket 实时流接口，所以客户端迟早还是会走流式更顺。

验收标准
你能在本地看到音频采集开始/结束日志
能拿到音频字节流或临时文件
能把它发到你自己的后端接口
6. WebSocket 通信模块

因为你后面要接：

实时 ASR
流式返回
未来 TTS 分段播放

所以 Android 端建议尽早有一个统一的 WebSocket 客户端模块。

这个模块要负责：

建立连接
自动重连
发 JSON 事件
接 JSON 事件
心跳
错误处理
验收标准
手机能连上你的测试后端
你能从客户端发一个测试事件
后端回一个测试消息，客户端能收到
四、第二批：先把“听懂”做通
7. ASR 对接模块

这一步你先不直接在 App 里对接 Qwen-ASR-Realtime，建议走你自己的后端转发层。

原因是：

API key 不要放客户端
后面好做日志和限流
好做 VAD/Manual 模式切换
好做 session 管理

Qwen-ASR-Realtime 官方文档说明：

通过 WebSocket 接收实时音频流
支持 VAD 模式：服务端自动断句
支持 Manual 模式：客户端提交整句后 commit。
你的第一版建议

先走 VAD 模式。

因为这样你客户端只要：

持续发音频
等后端/服务端给你返回最终转写
验收标准
你说一句话
手机页面能显示用户文本
页面里区分：
识别中
最终文本
8. 聊天消息模块

这时候 UI 要开始像聊天 App 了。

至少做：

用户消息气泡
AI 消息气泡
“识别中...” 状态
“思考中...” 状态
时间戳
错误提示
验收标准

一次语音输入结束后，消息流里能落下：

一条用户文本
后面预留 AI 回复位置
五、第三批：把“大脑”接进去
9. LLM 请求模块

这一步是把 Qwen3.5 接到你的后端。

客户端只需要做两件事：

把用户文本发给后端
接收 AI 回复文本

建议后端返回结构先简单一点：

{
  "reply_text": "今天辛苦啦，我在。",
  "emotion": "gentle"
}
验收标准
你说一句
App 上出现 AI 的文字回复
至少能连续聊 3 轮
10. 会话状态模块

客户端要维护基本状态，不然后面很乱。

至少有这些状态：

idle
recording
uploading/streaming
recognizing
thinking
speaking
interrupted
error
验收标准

UI 会根据状态切换按钮和提示文案。

六、第四批：把“会说”做通
11. TTS 播放模块

Qwen3-TTS 官方公开支持流式生成、voice clone、voice design，并有 0.6B / 1.7B 系列。

第一版客户端先别追求边生成边播，先做最稳版本：

后端生成整段音频
返回音频地址或字节流
客户端直接播放
客户端至少要有
开始播放
停止播放
播放完成回调
播放中状态 UI
验收标准
AI 回复后，手机能播出声音
你能手动停止
播放完状态恢复
12. 打断模块

语音陪伴 App 很重要的一点是：
用户一说话，AI 就要闭嘴。

第一版客户端先做简单规则：

如果当前正在播放 TTS
用户点击“开始说话”
立即停止播放
清空当前播放队列
进入 recording
验收标准

AI 正在讲话时，你点录音，AI 立刻停。

七、第五批：Android 13 上要预留的系统能力
13. 通知模块

Android 13 的通知权限是运行时权限，所以你后面做：

每日问候
主动召回
会话提醒
前台服务通知

都要走规范申请。Android 官方建议在合适上下文下请求权限，而不是一上来就弹。

第一版建议

先只做：

本地测试通知
权限检测
授权失败降级
14. 前台服务预留

如果你未来做：

长时间录音
通话模式
后台保持会话
后台持续播放/采集

你迟早要用 Foreground Service。

Android 官方现在要求：

在 manifest 里声明前台服务
指定 android:foregroundServiceType
如果目标 API 34+，还要申请对应前台服务权限。
你现在怎么处理

第一版可以先不启用复杂前台服务逻辑，
但项目结构里要预留一个：

VoiceSessionService
或者
ForegroundAudioService

避免后面重构。

八、你现在的 Android 客户端目录建议

如果你用 Flutter，我建议先这样分：

lib/
  main.dart
  app/
    router/
    theme/
  pages/
    home/
    chat/
    settings/
  widgets/
    chat_bubble/
    record_button/
    avatar_header/
    audio_player_bar/
  services/
    auth_service.dart
    websocket_service.dart
    asr_service.dart
    chat_service.dart
    tts_service.dart
    permission_service.dart
    audio_record_service.dart
    audio_play_service.dart
  models/
    session.dart
    message.dart
    chat_state.dart
    tts_response.dart
  stores/
    chat_store.dart
    session_store.dart
九、你这周的开发待办
Day 1
装 Flutter
配 Android Studio
真机连接
flutter doctor 通过
创建项目并在 Android 13 手机上跑起来
Day 2
搭聊天首页 UI
做录音按钮
申请 RECORD_AUDIO
本地录音成功
Day 3
接 WebSocket
音频发到测试后端
回显测试消息
Day 4
接 ASR 后端
页面显示用户识别文本
加识别中状态
Day 5
接 Qwen3.5 后端
AI 文本回复展示
形成完整聊天流
Day 6
接 TTS 播放
完成停止播放
完成“点击录音即打断”
Day 7
修状态机
修权限流程
真机回归测试
录一段演示视频
十、你先不要做的东西

为了不把自己搞复杂，这几个先别做：

不先做 3D 数字人
不先做 LiveKit
不先做复杂后台保活
不先做多角色切换
不先做复杂记忆系统
不先做流式 TTS 分片播放
不先做订阅支付

这些都可以晚一点。

十一、你现在第一阶段的完成标准

只要你做到下面这些，就算 Android 第一阶段成功：

App 能装到你 Android 13 手机
能申请录音权限
能录音并发送到后端
能显示 ASR 文本
能显示 Qwen3.5 回复
能播放 TTS 音频
能打断播放开始下一轮

这就已经是一个真正能演示的 AI 伴侣雏形了。

十二、我给你的直接建议

你现在就从这三件事开始：

把 Flutter 和 Android Studio 装好
让你的 Android 13 手机跑起一个空 Flutter App
先做录音权限 + 录音按钮

这是最顺的起点。Flutter 官方 Android setup、Android 13 通知权限要求、以及前台服务声明要求都已经很明确，照文档走不容易踩大坑。

下一步我建议直接给你做一份 Android 客户端 PRD/页面清单，这样你就能开始画页面和拆任务。

可以

我先把 Android 端页面清单和关键系统页按正式产品形态整理出来，并用官方 Android/Flutter 文档把权限页、通知页、前台服务这些会影响页面设计的点钉住。

已思考 7s

可以，下面我给你一份 Android 客户端 PRD / 页面清单。
这份是按你现在的方向来的：先 Android、先 App、先语音陪伴主链路。同时我会把 Android 13 相关的权限页、通知页、以及后面可能要预留的前台服务位一起纳进去，因为这些会直接影响页面设计和交互流程。Android 13 开始，通知权限 POST_NOTIFICATIONS 是运行时权限；前台服务从 Android 14 目标版本开始还要声明具体服务类型。Flutter 官方也已经把 Android 开发环境、构建发布流程单独整理好了，适合你现在直接开工。

一、产品定义
产品名称

先用工作名：

AI Companion Android

产品目标

做一个以实时语音陪伴为核心的 Android App，支持：

用户语音输入
AI 实时理解
AI 文字与语音回复
长期记忆
关系成长
后续接 2D 数字人
第一阶段产品定位

不是纯工具，不是语音助手，而是：

可长期使用的语音陪伴型 App

二、用户核心路径

先把主流程定清楚，后面页面就顺了。

主路径

打开 App
→ 首次引导
→ 选角色
→ 进入聊天页
→ 点按钮说话
→ ASR 转文字
→ Qwen3.5 回复文字
→ Qwen3-TTS 播放语音
→ 用户继续聊
→ 形成历史与记忆

次路径
修改称呼
切换角色
开关通知
查看关系进度
查看历史会话
开会员
三、信息架构

我建议 Android 端先用 5 个一级区块：

启动与引导
聊天主界面
角色与关系
历史与设置
会员与运营
四、页面清单总览

先给你总表：

01 启动页
02 登录/游客页
03 首次引导页
04 权限引导页
05 角色选择页
06 首页/聊天页
07 语音通话态页面
08 文字聊天态页面
09 会话详情页
10 历史会话列表页
11 角色主页
12 关系成长页
13 记忆管理页
14 设置页
15 通知设置页
16 声音与播放设置页
17 账号与隐私页
18 会员页
19 支付结果页
20 活动/消息中心页
21 错误与空状态页
22 调试页（内部）
五、逐页 PRD
01 启动页
目标

完成冷启动、资源初始化、自动登录检查。

页面元素
Logo
品牌文案
loading 动效
初始化进度
逻辑
检查本地 token
检查远端配置
检查是否首次启动
检查是否需要去权限引导
跳转
首次用户 → 首次引导页
已登录用户 → 首页/聊天页
未登录 → 登录/游客页
02 登录 / 游客页
目标

让用户进系统。

页面元素
手机号登录
第三方登录
游客试用
用户协议
隐私政策
关键点

AI 伴侣是长期关系型产品，账号体系最好一开始就有，不然记忆、付费、跨设备同步都会乱。

按钮
手机号登录
微信登录/Google 登录（后续）
先试试
03 首次引导页
目标

快速告诉用户这是个什么产品。

建议 3 屏以内
第 1 屏

“这是一个可以陪你聊天、陪你说话的 AI 伴侣”

第 2 屏

“支持语音对话、文字回复、长期记忆”

第 3 屏

“选择你喜欢的角色开始聊天”

按钮
下一步
跳过
04 权限引导页

这个页面很重要。
因为 Android 13 的通知权限不能乱弹，官方建议在合适上下文中请求，而不是用户一进来就突然弹系统框；通知是否开启可以通过 areNotificationsEnabled() 检查。

页面目标

解释为什么要这些权限。

子区块
麦克风权限

文案：

“需要麦克风权限，才能和 TA 说话”
通知权限

文案：

“开启通知后，你可以收到主动问候和提醒”
第一版这里可以先不强求立即授权
按钮
开启麦克风
稍后开启通知
继续
注意
录音权限：第一次真要录音时弹更自然
通知权限：Android 13 上要在明确场景下再弹，别首开即弹。
05 角色选择页
目标

完成第一次角色选择。

页面元素
角色卡列表
角色头像/立绘
角色简介
声音标签
性格标签
卡片字段
角色名
一句话介绍
风格标签：温柔 / 活泼 / 治愈 / 陪学
声音试听按钮
操作
选中角色
试听语音
开始聊天
后续扩展
多角色宇宙
限时角色
会员专属角色
06 首页 / 聊天页

这是最核心页面。

页面目标

承接主要语音/文字聊天。

布局建议
顶部
角色头像
角色名
在线状态
关系等级入口
设置入口
中间
消息流
用户消息
AI 消息
系统提示
“识别中/思考中/说话中”状态条
底部
按住说话/点击说话按钮
文本输入入口
停止播放按钮
更多操作
状态机

聊天页至少要覆盖：

idle
recording
recognizing
thinking
speaking
interrupted
error
为什么这个页要优先

因为你现在第一阶段所有能力都围绕这个页展开：

录音
ASR
LLM
TTS
打断
07 语音通话态页面

这个页是聊天页的“重语音模式”。

目标

让用户进入更沉浸的连续语音体验。

页面元素
大头像/半身角色
说话波形
当前状态提示：正在听 / 正在思考 / 正在说话
挂断按钮
静音按钮
文本字幕开关
适合什么场景
睡前陪伴
长时聊天
陪学/陪工作
后续和前台服务的关系

如果你以后要做更持续的通话体验，Android 侧可能会用到前台服务。Android 官方要求在 manifest 中声明前台服务类型；对于目标 API 34+ 的应用，还要按类型声明权限。这个现在就要在 PRD 里预留。

08 文字聊天态页面
目标

给不方便说话的用户一个纯文字模式。

页面元素
文本输入框
快捷回复建议
表情状态
语音播放按钮
切回语音模式入口
作用
静音环境使用
办公场景
低延迟 fallback
09 会话详情页
目标

查看当前会话内容和详细信息。

页面元素
会话标题
会话时间
消息列表
音频播放记录
关系变化摘要
本轮记忆提取结果
后续价值

这个页后面可以变成“导出聊天记录”入口。

10 历史会话列表页
目标

查看过往聊天。

页面元素
日期分组
每次会话标题
最后一条摘要
时长
角色
场景标签
操作
点进会话详情
删除记录
收藏会话
11 角色主页
目标

把角色作为“可运营资产”展示。

页面元素
角色立绘
名字
背景故事
性格标签
声音样例
当前关系状态
换装入口（后续）
角色切换按钮
12 关系成长页
目标

把“陪伴关系”可视化。

页面元素
亲密度
信任度
熟悉度
关系阶段
陪伴天数
纪念事件
最近里程碑
说明

这个页面对 AI 伴侣非常重要，因为它能把“陪伴感”从抽象体验变成可感知成长。

13 记忆管理页
目标

让用户看到“TA 记得什么”。

页面元素
用户偏好
重要事件
禁忌
重要日期
可删除记忆
可纠正记忆
操作
删除某条记忆
标记“这不对”
手动新增昵称/偏好
产品意义

这是建立用户信任的关键页。

14 设置页
目标

集中放通用设置。

分组
聊天设置
默认回复方式
自动播放语音
字幕显示
说话速度
通知设置
主动问候
每日提醒
活动通知
账户设置
修改资料
会员
隐私
15 通知设置页

Android 13 通知权限是运行时权限，所以这页必须做。官方建议在合适上下文申请，并在发通知前先确认应用是否已开启通知。

页面元素
总开关
每日问候
晚安提醒
活动通知
新角色通知
系统消息通知
状态
已授权
未授权
被系统关闭
操作
去开启权限
管理通知类型
16 声音与播放设置页
目标

管语音体验。

页面元素
角色音色选择
语速
自动播放
听筒/扬声器偏好
播放打断策略
字幕开关
17 账号与隐私页
目标

处理正式产品必须有的合规入口。

页面元素
账号信息
数据导出
删除账号
清除聊天记录
清除记忆
用户协议
隐私政策
说明

如果你后面上架，这页不能缺。

18 会员页
目标

做付费承接。

页面元素
免费版权益
会员权益
高级语音/高级角色/更长记忆
套餐价格
购买按钮
会员权益示例
更高质量语音
专属角色
更长会话时长
更多记忆容量
更高优先级
19 支付结果页
页面元素
支付成功
支付失败
订单信息
去聊天
联系支持
20 活动 / 消息中心页
目标

承接后续运营。

页面元素
节日活动
角色来信
官方消息
更新公告
专属任务
21 错误与空状态页

这个要独立设计，不要临时凑。

需要覆盖的状态
无网络
权限被拒绝
录音失败
识别失败
回复失败
播放失败
无历史记录
暂无活动
22 调试页（内部）

这个页很实用，建议你一开始就做。

页面元素
当前环境：dev / test / prod
WebSocket 状态
当前 session_id
当前角色
最后一次 ASR 文本
最后一次 LLM 回复
最后一次 TTS 音频地址
延迟数据
为什么要做

你现在是边开发边调链路，没有调试页会很痛苦。

六、底部导航建议

你第一版不要太复杂，建议只做 3 tab：

Tab 1：聊天

主入口。

Tab 2：角色

角色主页、关系成长、记忆管理。

Tab 3：我的

设置、会员、通知、隐私。

这个结构最稳。

七、页面优先级
P0：第一阶段必须有
启动页
登录/游客页
权限引导页
角色选择页
首页/聊天页
语音通话态页面
设置页
通知设置页
错误/空状态页
调试页
P1：产品闭环需要
历史会话列表页
会话详情页
角色主页
关系成长页
会员页
账号与隐私页
P2：运营增强
记忆管理页
活动/消息中心页
支付结果页
八、Android 端必须纳入 PRD 的系统约束
1）通知权限

Android 13 起，非豁免通知包括前台服务通知在内都受 POST_NOTIFICATIONS 运行时权限影响，必须在 manifest 声明，并在合适上下文请求。

这意味着你的 PRD 里必须有：

通知解释页
通知设置页
被拒绝后的降级逻辑
2）前台服务

如果你后面做长时语音通话、后台持续播放或录音，前台服务类型要提前规划。Android 官方要求在 manifest 里声明 android:foregroundServiceType，Android 14 目标版本及以上还要按类型声明权限。

这意味着你的 PRD 里要预留：

通话态页面
后台保持说明
通知栏播放/通话状态
3）Flutter 作为客户端框架

Flutter 官方已经把 Android 开发环境搭建、Android 特定集成、以及 Android 打包发布单独拆成正式文档，说明这条路线很适合你现在“先 Android、后续可能多端”的路径。

九、我建议你先画的页面顺序

不要一口气全画。
先按这个顺序出线框图：

首页/聊天页
语音通话态页面
权限引导页
角色选择页
设置页
通知设置页
角色主页
关系成长页

因为这 8 页就已经能撑起第一版完整体验了。

十、给你一版更适合分任务的页面拆分
A. 启动与进入
- 启动页
- 登录/游客页
- 首次引导页
- 权限引导页

B. 主体验
- 首页/聊天页
- 语音通话态页面
- 文字聊天态页面
- 错误与空状态页

C. 角色与关系
- 角色选择页
- 角色主页
- 关系成长页
- 记忆管理页

D. 历史与设置
- 历史会话列表页
- 会话详情页
- 设置页
- 通知设置页
- 声音与播放设置页
- 账号与隐私页

E. 商业化与运营
- 会员页
- 支付结果页
- 活动/消息中心页

F. 内部支持
- 调试页
十一、我对你现在的建议

你现在最该做的不是继续扩功能，而是：

先把这份页面清单变成低保真线框图。

顺序就是我上面那 8 个优先页面。
等你把页面定下来，下一步最自然的就是做：

《Android 客户端功能拆解 + 接口清单》

这样你就能开始让前端和后端真正并行干活。

可以

我把 Android 端功能拆解和接口边界一起整理成可开工版本，顺手用官方文档把权限、前台服务和语音链路再钉一遍，避免你后面接口返工。

已思考 14s

好，下面直接给你 《Android 客户端功能拆解 + 接口清单》。
这份是按你现在的路线来的：Android App + Flutter + WebSocket + ASR → Qwen3.5 → Qwen3-TTS。Flutter 官方有完整的 Android setup 路径；Qwen-ASR-Realtime 官方是 WebSocket 实时音频流，支持 VAD/Manual；Android 13 的通知权限和前台服务约束也要提前纳进接口设计。

一、客户端功能拆解
1. 启动与基础能力
1.1 启动初始化

功能：

读取本地 token
读取本地用户资料
拉取远端配置
检查 App 版本
检查是否首次启动
检查通知是否开启

说明：Android 13 上通知权限需要运行时申请，且官方建议在合适上下文里请求，同时可以通过 areNotificationsEnabled() 检查当前通知状态。

1.2 登录与游客

功能：

游客登录
手机号登录
三方登录预留
登录态刷新
登出
2. 权限模块
2.1 麦克风权限

功能：

首次录音时申请 RECORD_AUDIO
拒绝后弹解释
永久拒绝后引导去系统设置
2.2 通知权限

功能：

首次在“开启陪伴提醒/主动问候”场景下申请 POST_NOTIFICATIONS
被拒绝后展示说明页
进入设置页重新授权

说明：Android 13 将通知权限改成运行时权限，官方建议“在上下文中请求”，不要无意义首开即弹。

3. 音频输入模块
3.1 录音控制

功能：

点击开始录音
点击结束录音
录音中状态展示
音量波形展示
录音失败处理
3.2 音频采集

功能：

PCM/Opus 采样
分帧
缓冲区管理
静音检测
错误重试
3.3 录音状态机

状态：

idle
recording
stopping
failed
4. 实时连接模块
4.1 WebSocket 连接

功能：

建立连接
鉴权
心跳
自动重连
断线提示
顺序消息分发
4.2 会话级连接管理

功能：

一个 session 对应一条实时链路
进聊天页自动连接
离开页面按策略断开或保活

说明：Qwen-ASR-Realtime 官方就是基于 WebSocket 协议，客户端通过事件不断追加音频、提交音频，并接收实时文本和最终文本。

5. ASR 模块
5.1 音频流发送

功能：

将录音 chunk 推给后端
支持实时流式发送
支持结束录音后 commit/finish
5.2 转写结果展示

功能：

partial 文本展示
final 文本落消息流
“识别中”状态显示
错误提示
5.3 模式支持

功能：

VAD 模式
Manual 模式预留

说明：Qwen-ASR-Realtime 官方支持 VAD 和 Manual 两种模式。VAD 模式由服务端自动断句并返回最终结果；Manual 模式则由客户端在整句发送后主动 commit。

6. 聊天消息模块
6.1 消息列表

功能：

用户消息
AI 消息
系统消息
时间戳
状态提示
6.2 消息类型

类型：

text
voice
event
status
6.3 本地态

状态：

sending
partial
final
failed
retrying
7. LLM 对话模块
7.1 文本发送

功能：

将用户最终文本发给后端
携带 session_id / turn_id / companion_id
支持流式回复预留
7.2 AI 回复展示

功能：

thinking 状态
AI 文本气泡
emotion 标签
animation 标签预留
7.3 失败与重试

功能：

生成失败提示
一键重试
降级文案
8. TTS 模块
8.1 TTS 请求

功能：

请求后端生成语音
支持 voice_profile_id
支持 emotion/style 参数
支持 streaming 预留
8.2 音频播放

功能：

开始播放
暂停
停止
播放完成
播放失败
重放
8.3 打断策略

功能：

用户开始录音时，立即停止当前 AI 播放
清空未播队列
状态切到 recording
9. 会话状态模块

统一维护以下状态：

idle
recording
recognizing
thinking
speaking
interrupted
reconnecting
error

这个状态机会直接驱动页面按钮、顶部提示、波形、以及“现在是不是能说话”。

10. 历史与本地缓存模块
10.1 本地缓存

功能：

本地最近会话列表
最近消息缓存
本地角色配置缓存
音频缓存
10.2 历史会话

功能：

会话列表
点进会话详情
删除本地缓存
下拉刷新
11. 角色与关系模块
11.1 角色选择

功能：

获取角色列表
角色切换
试听音色
11.2 角色主页

功能：

查看角色资料
查看当前关系状态
查看已解锁内容
11.3 关系成长

功能：

亲密度
信任度
陪伴天数
里程碑展示
12. 设置模块
12.1 通用设置
自动播放
文本字幕开关
播放速度
默认输入模式
12.2 通知设置
主动问候
每日提醒
活动通知
12.3 隐私与账号
账号信息
删除账号
导出数据
清除聊天记录
13. 调试模块

建议开发期必做。

功能：

当前环境 dev/test/prod
WebSocket 状态
session_id
turn_id
最后一次 ASR partial/final
最后一次 LLM 回复
最后一次 TTS URL
首字/首包延迟
二、客户端分层建议
表现层
pages
widgets
theme
状态层
chat_store
session_store
permission_store
settings_store
服务层
auth_service
websocket_service
asr_service
chat_service
tts_service
audio_record_service
audio_play_service
notification_service
数据层
models
repositories
local_cache
三、接口清单

下面按“客户端调用后端”的方式给你列。

A. 认证与用户
1. 游客登录

POST /api/v1/auth/guest/login

请求：

{
  "device_id": "android_xxx",
  "platform": "android",
  "app_version": "0.1.0"
}

响应：

{
  "user_id": 10001,
  "token": "xxx",
  "refresh_token": "xxx",
  "is_new_user": true
}
2. 获取当前用户

GET /api/v1/users/me

响应：

{
  "user_id": 10001,
  "nickname": "keke",
  "subscription_status": "free",
  "notification_enabled": false
}
3. 更新用户偏好

PATCH /api/v1/users/me/preferences

请求：

{
  "preferred_input_mode": "voice",
  "auto_play_tts": true,
  "subtitle_enabled": true
}
B. 角色与关系
4. 获取角色列表

GET /api/v1/companions

响应：

{
  "items": [
    {
      "id": 1,
      "name": "Luna",
      "intro": "温柔陪伴型",
      "avatar_url": "https://...",
      "voice_preview_url": "https://..."
    }
  ]
}
5. 获取角色详情

GET /api/v1/companions/{companion_id}

响应：

{
  "id": 1,
  "name": "Luna",
  "intro": "温柔陪伴型",
  "persona_tags": ["温柔", "治愈"],
  "relationship": {
    "intimacy_score": 12.5,
    "trust_score": 9.0,
    "stage_code": "familiar"
  }
}
6. 获取关系状态

GET /api/v1/companions/{companion_id}/relationship

响应：

{
  "intimacy_score": 12.5,
  "trust_score": 9.0,
  "familiarity_score": 7.0,
  "dependency_risk_score": 1.0,
  "stage_code": "familiar"
}
C. 会话与消息
7. 创建会话

POST /api/v1/sessions

请求：

{
  "companion_id": 1,
  "channel": "voice",
  "mode": "free_chat"
}

响应：

{
  "session_id": 900001,
  "session_uuid": "sess_xxx",
  "status": "active"
}
8. 获取会话列表

GET /api/v1/sessions?cursor=...

响应：

{
  "items": [
    {
      "session_id": 900001,
      "title": "晚安聊天",
      "started_at": "2026-03-24T20:00:00Z",
      "last_message_preview": "今天辛苦啦。"
    }
  ],
  "next_cursor": null
}
9. 获取会话详情

GET /api/v1/sessions/{session_id}

响应：

{
  "session_id": 900001,
  "status": "active",
  "messages": [
    {
      "message_id": 1,
      "role": "user",
      "text": "我今天有点累"
    },
    {
      "message_id": 2,
      "role": "assistant",
      "text": "我在，慢慢说。"
    }
  ]
}
10. 结束会话

POST /api/v1/sessions/{session_id}/end

请求：

{
  "reason": "user_exit"
}
D. 实时链路
11. 建立实时 WebSocket

WS /api/v1/realtime/ws?token=...&session_id=...

WebSocket 用来承载：

音频 chunk 上传
ASR partial/final 回推
状态事件
LLM 流式回复预留
TTS 进度事件

说明：这层设计和 Qwen-ASR-Realtime 的 WebSocket 交互方式是对齐的，因为其官方实时接口就是事件驱动式 WebSocket 会话。

12. 客户端发送音频 chunk

WS Event audio.append

请求：

{
  "event": "audio.append",
  "session_id": 900001,
  "turn_id": 1,
  "seq": 12,
  "audio_format": "pcm16",
  "sample_rate": 16000,
  "payload_base64": "..."
}
13. 客户端结束录音
VAD 模式

可以不显式 commit，只发送结束事件或停止追加，由后端决定 finish 节点。

Manual 模式

WS Event audio.commit

{
  "event": "audio.commit",
  "session_id": 900001,
  "turn_id": 1
}

说明：Qwen-ASR-Realtime 文档里，Manual 模式需要在整句音频发送完后显式 commit；VAD 模式则主要依赖服务端自动断句。

14. 服务端回推 ASR partial

WS Event asr.partial

{
  "event": "asr.partial",
  "session_id": 900001,
  "turn_id": 1,
  "text": "我今天有点",
  "seq": 3
}
15. 服务端回推 ASR final

WS Event asr.final

{
  "event": "asr.final",
  "session_id": 900001,
  "turn_id": 1,
  "text": "我今天有点累"
}
16. 服务端回推状态事件

WS Event session.state

{
  "event": "session.state",
  "session_id": 900001,
  "state": "thinking"
}

state 枚举建议：

recognizing
thinking
speaking
interrupted
error
E. 聊天与 LLM
17. 提交用户文本给大脑

POST /api/v1/chat/turns

请求：

{
  "session_id": 900001,
  "turn_id": 1,
  "input_mode": "voice",
  "user_text": "我今天有点累"
}

响应：

{
  "assistant_message_id": 2001,
  "reply_text": "今天辛苦啦，我在。",
  "emotion": "gentle",
  "animation": "soft_smile",
  "tts_required": true
}
18. 流式回复预留

如果后面要做流式文本，可在 WebSocket 回推：

WS Event llm.partial

{
  "event": "llm.partial",
  "session_id": 900001,
  "turn_id": 1,
  "text": "今天辛苦啦，"
}

WS Event llm.final

{
  "event": "llm.final",
  "session_id": 900001,
  "turn_id": 1,
  "text": "今天辛苦啦，我在。"
}
F. TTS
19. 创建 TTS 任务

POST /api/v1/tts/jobs

请求：

{
  "session_id": 900001,
  "turn_id": 1,
  "message_id": 2001,
  "text": "今天辛苦啦，我在。",
  "voice_profile_id": 101,
  "emotion": "gentle"
}

响应：

{
  "tts_job_id": 3001,
  "status": "queued"
}
20. 查询 TTS 结果

GET /api/v1/tts/jobs/{tts_job_id}

响应：

{
  "tts_job_id": 3001,
  "status": "completed",
  "audio_url": "https://...",
  "duration_ms": 2100
}
21. 流式 TTS 预留

如果后面做边生成边播，可回推：

WS Event tts.segment

{
  "event": "tts.segment",
  "tts_job_id": 3001,
  "seq": 1,
  "audio_url": "https://..."
}

说明：Qwen3-TTS 官方支持流式语音生成，所以你这样留接口边界是合理的。

G. 历史、记忆、关系
22. 获取历史消息

GET /api/v1/sessions/{session_id}/messages?cursor=...

23. 获取记忆列表

GET /api/v1/memories?companion_id=1

响应：

{
  "items": [
    {
      "memory_id": 1,
      "type": "preference",
      "title": "喜欢安静地聊天",
      "content": "用户更喜欢晚上聊天"
    }
  ]
}
24. 删除记忆

DELETE /api/v1/memories/{memory_id}

25. 纠正记忆

PATCH /api/v1/memories/{memory_id}

请求：

{
  "content": "用户更喜欢周末晚上聊天"
}
H. 设置与通知
26. 获取设置

GET /api/v1/settings

27. 更新设置

PATCH /api/v1/settings

请求：

{
  "auto_play_tts": true,
  "subtitle_enabled": true,
  "daily_notification_enabled": false
}
28. 上报通知权限状态

POST /api/v1/notifications/permission

请求：

{
  "enabled": true
}

说明：Android 13 的通知权限状态要单独感知和同步，不然你后台以为能发，客户端其实被系统关了。

I. 调试与埋点
29. 上报客户端埋点

POST /api/v1/analytics/events

请求：

{
  "event_name": "voice_record_start",
  "session_id": 900001,
  "properties": {
    "platform": "android",
    "app_version": "0.1.0"
  }
}
30. 上报错误日志

POST /api/v1/logs/client-errors

请求：

{
  "page": "chat",
  "error_code": "AUDIO_PLAY_FAIL",
  "message": "player init failed"
}
四、WebSocket 事件总表

建议统一这些事件名：

client -> server
- session.start
- audio.append
- audio.commit
- audio.finish
- chat.send
- tts.request
- playback.stop
- ping

server -> client
- session.started
- session.state
- asr.partial
- asr.final
- llm.partial
- llm.final
- tts.started
- tts.segment
- tts.completed
- error
- pong
五、客户端本地数据模型

建议先有这些 model：

User
Companion
RelationshipState
Session
Turn
Message
MessageContent
ChatState
AudioChunk
AsrPartialResult
AsrFinalResult
TtsJob
TtsSegment
Settings
六、Android 端必须预留的系统能力
1. 通知权限链路

要有：

查询当前是否开启通知
首次在合适场景申请 POST_NOTIFICATIONS
被拒绝后的解释页
跳系统设置页

这个是 Android 13 明确要求的运行时权限逻辑。

2. 前台服务预留

如果后面你要做：

长时语音通话
后台持续采集/播放
挂后台不中断

那要提前预留：

VoiceForegroundService
通知栏会话状态
manifest 里的 android:foregroundServiceType

Android 官方要求在 manifest 中声明前台服务类型；若目标 API 34+，还需请求对应类型权限。

七、第一阶段真正必做的接口

如果你现在要最短时间开工，先只做这 12 个：

POST /api/v1/auth/guest/login
GET /api/v1/companions
POST /api/v1/sessions
WS /api/v1/realtime/ws
audio.append
asr.partial
asr.final
POST /api/v1/chat/turns
POST /api/v1/tts/jobs
GET /api/v1/tts/jobs/{id}
POST /api/v1/settings
POST /api/v1/analytics/events

只靠这套，你已经能完成：

登录
选角色
录音
转写
文本回复
语音播放
基础埋点
八、前后端联调顺序

建议按这个顺序：

第 1 步

先通：

guest/login
companions
sessions
第 2 步

再通：

WS realtime
audio.append
asr.partial/final
第 3 步

再通：

chat/turns
第 4 步

最后通：

tts/jobs
播放逻辑
打断逻辑

这个顺序最稳，因为它严格按“听懂 → 思考 → 说话”推进，也和 Qwen-ASR-Realtime 的 WebSocket 事件模式对齐。

九、你现在最该做的事

把这份内容拆成两张表发给开发：

客户端任务表
接口联调表

最先开工的客户端任务只有 4 组：

权限与录音
WebSocket
消息流 UI
音频播放

最先开工的后端任务只有 4 组：

鉴权与 session
ASR 转发
Qwen3.5 对话
TTS 任务

下一步最顺的，就是我继续给你出 《Android 开发任务排期表（按天/按周）》。

还有子分期,就是单前子分期。如果说我前不止见这个APP,我直接在后端就把这个整个后端做出来,并验证,可以吧。后端可以做到这些吧。

我先按“后端先行”的思路，把能独立做、能单独验收的部分拆出来，再对应到官方接口和模型能力，给你一套可执行的后端分期。

已思考 19s

可以，而且我很建议你这么做：
先把后端整套做出来并验证，再接 Android App。对你这个项目，这不是退而求其次，反而是更稳的主线。因为你核心链路本来就是后端主导的：Qwen-ASR-Realtime 官方就是 WebSocket 实时音频流 + VAD/Manual 断句 + partial/final 事件回推；Qwen3.5 是大脑；Qwen3-TTS 负责流式或非流式语音输出，TTS 仓库还公开了 finetuning 目录。也就是说，App 只是消费这套能力的一个客户端，不是能力本体。

所以你的思路可以定成：
先做“后端可独立运行、可独立联调、可独立压测”的完整能力平台，然后 Android 只是第一个接入端。FastAPI 官方文档也明确把 WebSocket 作为原生移动应用可直接连接的后端接口形态之一，这正适合你现在先把服务端跑通，再让 Android 去接。

先给结论

你可以把整个项目拆成两条线：

线 A：后端能力平台先行
把这些全做完并验证：

账号与 session
WebSocket 实时通道
ASR 网关与事件转发
Qwen3.5 编排
Qwen3-TTS 生成
记忆与关系状态写库
埋点、日志、成本统计
Mock 客户端 / CLI / Web 调试台

线 B：Android 只是后接入

录音
WebSocket
UI 状态机
音频播放

这条顺序对你特别合适，因为 Qwen-ASR-Realtime 的协议和事件流本身就足够复杂，单独把后端打磨好，后面 Android 会轻松很多。

我建议你的“后端先行”总分期
第 0 期：接口协议先定死

先不写太多代码，先把这些定下来：

REST 接口
WebSocket 事件名
session/turn/message 状态机
错误码
数据库表
回包 JSON 结构

为什么这一步必须先做：
Qwen-ASR-Realtime 官方事件已经比较明确，包括 session.created、input_audio_buffer.speech_started、conversation.item.input_audio_transcription.text、conversation.item.input_audio_transcription.completed、session.finished 等。你最好先把你自己的内部事件模型映射好，不然后面 Android、后台、调试工具都会跟着改。

这一期的交付物
openapi.yaml
websocket_events.md
db_schema.sql
state_machine.md
这一期的验收
团队内部能对着文档模拟一整轮：
session 创建
音频追加
ASR partial/final
chat reply
tts job
playback stop
第 1 期：先做“后端骨架”

先把不依赖模型的基础后端搭起来。

子模块
auth-service
session-service
gateway-service
realtime-ws-service
config-service
logging/trace
analytics-event-ingest

FastAPI 官方有正式的 WebSocket 支持，适合你先快速把移动端未来会直连的实时网关做出来。

这一期要完成的能力
游客登录
创建 session
建立 WebSocket
心跳与重连协议
session state 广播
mock 事件回推
这一期怎么验证

完全不需要 App。
你可以直接用：

Python 脚本
WebSocket CLI
一个简单网页调试台

去连你的后端，把假音频事件、假 ASR 结果、假 TTS 结果走通。

这一期验收标准
能创建 session
能连上 WebSocket
能收发自定义事件
数据能入库
日志能查
第 2 期：ASR 网关先打通

这是第一条真正的“模型链路”。

Qwen-ASR-Realtime 官方确认了几件很重要的事：

接口是 WebSocket
支持 VAD 模式
支持 Manual 模式
服务端会回推高频实时文本事件
最终结果由 completed 事件给出
事件里还能带语种和情绪信息。
你这期要做的后端模块
asr-adapter-service
audio-buffer-service
turn-manager
asr-event-normalizer
你要做的事

把 Qwen-ASR-Realtime 原始事件，统一归一成你自己的后端事件，比如：

asr.partial
asr.final
turn.started
turn.stopped
turn.failed
这一期怎么验证

还是不需要 App。
你可以直接用：

本地 wav/pcm 文件
Python 脚本分帧发送
用 CLI 模拟 append / commit / finish

去测两条线：

VAD 模式
Manual 模式
这一期验收标准
给一段音频，能拿到 partial
能拿到 final transcript
能在数据库生成 turn/message
能记录 ASR 延迟
能正确处理失败事件
第 3 期：把“大脑”接进去

这期才是 Qwen3.5 真正上场。

Qwen3.5 官方仓库是公开模型系列入口；你当前项目里，4B/9B 非常适合在线主路径，35B-A3B 更适合高质量慢路径或离线任务。35B-A3B 的模型卡也明确写了可兼容 Transformers、vLLM、SGLang 等推理栈。

你要做的模块
orchestrator-service
persona-service
prompt-builder
chat-service
model-run-recorder
这一期不先做什么
不先做复杂 RAG
不先做多工具
不先做复杂剧情
先做什么

只做一条最稳的链：

asr.final → prompt 组装 → Qwen3.5 → reply_text/emotion → 入库

这一期怎么验证

继续不需要 App。
直接用：

curl / Postman 发文本
或者由 ASR 流程自动触发
这一期验收标准
输入一句文本，能出 AI 回复
回复能写入 messages
model_runs 能记录模型、耗时、tokens
prompt_snapshots 能留档
第 4 期：把 TTS 打通

Qwen3-TTS 官方仓库说明它支持：

streaming speech generation
voice clone
voice design
公开 0.6B / 1.7B 系列
仓库里有 finetuning 目录和 README。
你要做的模块
tts-adapter-service
voice-profile-service
tts-job-service
audio-asset-service
先做的版本

先做最稳的：

输入整段文本
返回整段音频 URL

不要一开始就做边合成边播。

这一期怎么验证

还是不需要 App。
你可以：

curl 创建 TTS job
轮询 job 状态
下载返回的音频文件
本地播放器直接听
这一期验收标准
给定 reply_text，能产出音频
音频能落对象存储
tts_jobs / audio_assets 正常入库
voice_profile 可切换
第 5 期：把“完整会话后端”做出来

到这一步，你已经不是单点能力了，而是完整闭环：

音频输入 → ASR → LLM → TTS → 会话入库

这期你要做的，是把这些能力收束成真正的产品后端。

你要补的模块
memory-service
relationship-service
summary-service
moderation-service
usage/cost-service
这一期要完成的能力
会话结束后生成 summary
抽取长期记忆
更新 intimacy/trust
写 usage_ledger / cost_ledger
风险内容打标
这一期怎么验证

依然可以不靠 App。
你可以做一个：

后端调试控制台
或者 网页版测试客户端
或者 命令行语音回放器

拿测试音频集跑完整流程。

这一期验收标准
一轮会话结束后，数据库里有：
sessions
turns
messages
model_runs
tts_jobs
memories
relationship_events
成本账能统计出来
日志能回放问题
第 6 期：后端验证和压测

这期非常关键，而且最适合放在 App 之前。

你要验证的内容
WebSocket 长连接稳定性
ASR 事件顺序一致性
turn 状态机正确性
TTS 任务吞吐
数据写库一致性
并发成本
故障降级
推荐做的验证方式
自动化集成测试
回放音频样本集
压测脚本
错误注入测试
超时与重试测试
重点验收指标
ASR final 成功率
LLM 成功率
TTS 成功率
全链路 P50/P95
session 完成率
平均每轮成本

这一步做完，你的 Android 前端其实就变成了“接一个成熟后端”，项目风险会小很多。

你问“后端可以做到这些吧”

可以，而且完全可以做到比 App 更先成熟。

因为你这个产品真正复杂的部分，本来就在后端：

Qwen-ASR-Realtime 的事件流处理
会话状态机
Qwen3.5 的人设编排
Qwen3-TTS 的任务化输出
记忆与关系状态更新
成本、埋点、风控、日志

这些全部都可以在没有 Android 客户端的情况下先做完、先验完。官方资料已经足够支持你把 ASR 的 VAD/Manual 双模式、TTS 的流式/音色能力、以及 WebSocket 后端接口先完整搭起来。

我建议你的“后端先行”最小工具包

为了让后端能独立验证，我建议你同时做 3 个辅助工具：

1）Web 调试台

功能：

建 session
发文本
上传音频文件
实时看 ASR partial/final
触发 TTS
播放音频
2）CLI 回放器

功能：

输入 wav/pcm
模拟 append/commit/finish
打印事件流
输出最终 transcript / reply / tts job
3）管理后台最小版

功能：

查 session
查 turns
查 messages
查 model_runs
查错误日志

这三个东西一做，Android 会非常好接。

我替你拍一个最实际的顺序
先做
协议与库表
WebSocket 骨架
ASR adapter
LLM orchestrator
TTS job service
memory / relationship
调试台与压测
最后再做
Android 端

这个顺序最适合你现在。
因为你现在不是缺页面，而是缺一套可靠的后端能力底座。

最后一句结论

对，你完全可以先不管 App，先把整个后端做出来并验证；而且我认为你就应该这么干。
对 AI 伴侣这种语音链路重、状态机重、模型编排重的项目，后端先行通常比“客户端先堆页面”更稳。Qwen-ASR-Realtime 的 WebSocket 事件流、Qwen3.5 的多规格模型路线、Qwen3-TTS 的流式与微调能力，都足够支撑你先把完整后端平台做扎实。

下一步最顺的就是我直接给你一份：《后端分期排期表（P0/P1/P2 + 每期交付物）》。

就是前端也是要的是吧,就是我没有前端,就比如说我在电脑上插上我那个风,然后它是连不到我的那个Linux的后台,就是WSL了吗,就是它连不到的嘛,那就只能提升前端,前端可以连吗? 就我那语音输入,我怎么输入给它呢?

我先查一下两个关键点：一是浏览器/前端能不能直接采集麦克风并发给本机后端，二是 WSL2 和 Windows 本机之间现在的联网方式和 localhost 转发细节。

已思考 19s

对，你这个理解已经接近关键点了：

后端本身不会“自己拿到你的麦克风”。
麦克风一定要有一个“采集端”来读音频，然后再把音频发给后端。这个采集端可以是：

前端网页
Android App
桌面客户端
本地 Python 小工具

所以不是“必须先做完整 App 前端”，而是你至少要有一个输入端。这一点和浏览器麦克风权限模型是一致的：浏览器要通过 getUserMedia() 采集麦克风，而且这个能力只能在安全上下文里用，localhost 也算安全上下文。

先回答你最实际的问题
1）我电脑插上麦克风，能不能直接给 WSL 里的 Linux 后端？

能，但不是“Linux 后端直接读你的麦克风设备”，而是“Windows 侧的程序采集音频，再发给 WSL 后端”。

最简单的做法有两种：

做法 A：最推荐

开一个很薄的网页前端

浏览器拿麦克风
浏览器通过 WebSocket 把音频发给你的后端
后端跑在 WSL 里

这个方案最顺，因为：

浏览器天然能拿麦克风 getUserMedia()
WSL 里跑的服务，Windows 浏览器通常可以直接通过 localhost 访问
你不需要先写 Android App
做法 B：也可以

写一个本地 Python/Node 小工具

在 Windows 上采集麦克风
通过 WebSocket 发给 WSL 后端

这个更像“调试客户端”，也行，但开发体验通常不如网页直观。

2）WSL 里的后端，Windows 浏览器连得到吗？

大多数情况下，连得到。

微软现在的 WSL 文档明确写了两件事：

默认 NAT 架构下，Windows 上的浏览器可以用 localhost 访问 WSL 里运行的服务
如果开启 mirrored networking，Windows 和 WSL 之间也可以继续直接用 127.0.0.1 互连，兼容性更好

所以你完全可以这样跑：

后端在 WSL 里监听 0.0.0.0:8000
Windows 上开 Chrome/Edge
打开 http://localhost:8000 或 http://localhost:3000
网页前端拿麦克风，再把音频用 WS 发到 ws://localhost:8000/...

这里有个关键点：
如果后端只绑定 127.0.0.1，有时会让调试更绕。微软文档也特别提到，涉及远程或跨侧访问时，很多服务要绑定到 0.0.0.0 而不是 127.0.0.1。

3）所以是不是“还是得有前端”？

对，但这个前端可以非常薄。

你现在不需要一个完整产品前端。
你只需要一个采集麦克风 + 发 WS + 显示文本/播放音频的调试页就够了。

也就是说，先做这种就行：

最小 Web 调试页

页面只有这几个东西：

一个“开始说话”按钮
一个“停止”按钮
一个文本框显示 ASR partial/final
一个文本框显示 Qwen3.5 回复
一个播放器播放 TTS 音频

这个就已经能把你整条链路验证掉了。

4）如果我完全没有前端，后端怎么测语音输入？

也不是没办法，但会更笨一点。

你可以用这两种方式：

方式 1：音频文件回放
先录一段 wav/pcm
用 Python 脚本分帧发给后端
后端照样走 ASR → LLM → TTS

这个适合测后端协议和状态机。

方式 2：本地麦克风采集脚本
Windows 上写 Python/Node 脚本
实时读麦克风
发给 WSL 后端

这个适合不想先写网页。

但从效率上说，最省事的仍然是一个很薄的网页调试前端。

你现在最适合的结构
方案：后端先行 + 薄网页调试台

我建议你立刻这样分：

A. WSL 里的后端

负责：

REST
WebSocket
ASR 转发
Qwen3.5 调用
Qwen3-TTS 调用
数据入库
B. Windows 浏览器里的调试页

负责：

getUserMedia() 拿麦克风
采集音频
WS 发音频给后端
显示 partial/final
显示 AI 回复
播放返回音频

这样你就能在没有 Android App 的情况下，把整个产品主链路都跑通。
而且浏览器在 localhost 上可以使用 getUserMedia()，因为 localhost 被视为安全上下文。

你担心的核心问题，我直接替你拆开
问题 A：WSL 能不能直接拿到 Windows 麦克风设备？

不要按这个方向想。
你没必要让 WSL 直接碰物理麦克风。
正确思路是：

Windows 侧采集 → 网络发送 → WSL 后端处理

这才是最稳的架构。

问题 B：浏览器能不能连 WSL 后端？

能，通常直接 localhost 就行。
微软官方就是这么写的。

问题 C：那我是不是还得写前端？

要，但先写一个极薄的调试前端，不是正式前端。

我建议你现在就这么落
第一阶段

先做：

WSL 后端
一个本地网页调试台
第二阶段

网页调试台跑通后，再做：

Android App

这条顺序是最顺的。

最后给你一句非常直接的话

你不是“必须先做完整前端”，你只是必须先有一个“音频采集入口”。
这个入口最适合先用本地网页调试页来承担，因为浏览器能拿麦克风，localhost 又能访问 WSL 服务。

下一步最有价值的是，我直接给你一份：
“网页调试台最小功能清单 + 页面结构 + WS 事件流”。

还有,我要一个,现在是我要一个最小验证,就是已经确定了这些了吗,我要做一个最小验证, 就是最小的MVP嘛,我要做一个最小的MVP,我要怎么做?

我先把“最小可验证版本”压到最小：只保留一条能跑通的语音链路，然后给你一个 7 天内可做完的 MVP 方案。

已思考 16s

可以。
而且你现在最该做的，不是“完整产品”，而是一个最小可验证 MVP：

先把 MVP 定义成一句话

用户对着电脑麦克风说一句话，系统能：

收到语音
转成文字
用 Qwen3.5 生成回复
再把回复变成语音播出来

这就够了。

一、这个 MVP 只做什么
保留 4 个核心模块
1）一个很薄的网页调试页

用浏览器拿麦克风。浏览器可以通过 getUserMedia() 采集音频，而且 localhost 属于安全上下文，可以直接开发测试。

2）一个后端 WebSocket 服务

负责收音频、转发、回推结果。

3）ASR → LLM → TTS 三段链路
ASR：Qwen-ASR-Realtime，官方就是 WebSocket 实时音频流，支持 VAD 和 Manual 两种模式。
LLM：Qwen3.5 做回复生成。Qwen 官方仓库已公开 Qwen3.5 系列。
TTS：Qwen3-TTS，官方说明支持流式生成，已公开 0.6B / 1.7B 系列。
4）一个最简单的数据库

只存：

sessions
messages
model_runs
二、这个 MVP 不做什么

先明确砍掉这些，不然你会做不完：

不做 Android App
不做小程序
不做 2D/3D 数字人
不做长期记忆
不做关系成长
不做支付
不做复杂权限系统
不做复杂后台
不做流式 TTS 分段播放
不做微调

你现在只验证一件事：

这条语音闭环，到底能不能跑顺。

三、最小 MVP 的结构
结构图
浏览器网页
  ├─ 点按钮开始录音
  ├─ getUserMedia 拿麦克风
  ├─ WebSocket 发音频给后端
  ├─ 显示 ASR 文本
  ├─ 显示 AI 回复文本
  └─ 播放 TTS 音频

后端
  ├─ WebSocket 接音频
  ├─ 调 Qwen-ASR-Realtime
  ├─ 拿 final transcript
  ├─ 调 Qwen3.5
  ├─ 调 Qwen3-TTS
  └─ 把文本和音频 URL 回给前端
四、MVP 的页面就一个
页面元素

只做一个网页，放这些东西：

一个“开始说话”按钮
一个“停止录音”按钮
一个“用户识别文本”区域
一个“AI 回复文本”区域
一个“播放音频”按钮或自动播放
一个“状态提示”区域

状态就 5 个：

idle
recording
recognizing
thinking
speaking

这就够了。

五、后端接口也压到最小
只要 2 类接口
1）一个 WebSocket

负责：

前端发音频
后端回 ASR partial/final
后端回状态
后端回最终 reply_text
后端回 tts 音频地址

Qwen-ASR-Realtime 官方文档明确要求先发 session.update，再持续发 input_audio_buffer.append；VAD 模式下服务端自动断句，Manual 模式下客户端要发 input_audio_buffer.commit。

2）一个健康检查接口

例如：

GET /health
六、我建议你 MVP 先用 VAD 模式

原因很简单：

前端更省事
不用自己判断一句话什么时候结束
只要持续发音频，服务端检测到一句结束后会返回最终识别结果

这正是 Qwen-ASR-Realtime 官方对 VAD 模式的说明。

所以你的 MVP 先不要用 Manual。
先上 VAD。

七、MVP 的最小事件流
前端到后端
建立 WebSocket
发送 session.update
点击开始说话
持续发送音频 chunk
点击停止
发送 session.finish 或由后端按流程结束
后端到前端
state = recording
asr.partial
asr.final
state = thinking
reply_text
state = speaking
audio_url
state = idle
八、MVP 的最小数据库
sessions

字段：

id
started_at
ended_at
status
messages

字段：

id
session_id
role
text
created_at
model_runs

字段：

id
session_id
task_type
model_name
latency_ms
status
created_at

这 3 张表就够验证了。

九、MVP 的技术选型，我替你拍板
前端

网页调试页

HTML + JS 就行
不用 React 都可以
重点是 getUserMedia() + WebSocket

MDN 明确说明 getUserMedia() 用来请求音频输入流。

后端

Python FastAPI

REST + WebSocket 一起做
快速
调试方便
模型链路
ASR：Qwen-ASR-Realtime
LLM：Qwen3.5
TTS：Qwen3-TTS-0.6B 先上

Qwen3-TTS 官方仓库明确支持实时交互场景，且强调低延迟；0.6B / 1.7B 两档已经公开。

十、你这个 MVP 的完成标准

只要做到下面这 6 条，就算 MVP 成功：

打开网页能申请麦克风权限
说一句中文，后端能收到音频
后端能拿到 ASR 最终文本
后端能调用 Qwen3.5 生成一条回复
后端能调用 Qwen3-TTS 生成音频
网页能播出 AI 的声音

这就已经是可演示 MVP 了。

十一、最小开发顺序
第 1 步

先把网页录音跑通
目标：

浏览器拿到麦克风
WebSocket 连上后端
第 2 步

先只做 ASR
目标：

你说一句
页面显示识别结果
第 3 步

再接 Qwen3.5
目标：

识别后自动生成文字回复
第 4 步

最后接 TTS
目标：

AI 回复能播放出来

顺序一定是：

听懂 → 思考 → 说出来

十二、7 天 MVP 版排期
Day 1
起 FastAPI 项目
起一个最简单网页页
WebSocket 打通
浏览器麦克风权限拿到
Day 2
前端能发音频 chunk
后端能收音频
打印日志确认音频流到了
Day 3
接 Qwen-ASR-Realtime
先跑 VAD 模式
页面显示 asr.final
Day 4
接 Qwen3.5
页面显示 reply_text
Day 5
接 Qwen3-TTS
返回音频 URL
页面播放成功
Day 6
整体串联
状态机补齐
错误处理补齐
Day 7
测试 20 轮真实对话
录 demo 视频
写下问题清单
十三、你现在最容易做错的地方
1）一开始就做 App

没必要。
网页调试页更快验证。

2）一开始就做长期记忆

没必要。
MVP 不看这个。

3）一开始就做数字人

没必要。
先把语音闭环跑通。

4）一开始就做复杂协议

先最小化。
只保留：

音频输入
最终文本
AI 回复
音频播放
十四、我替你定一个“最小到不能再小”的版本
MVP v0.1

只支持：

中文
单角色
单轮对话
浏览器输入
后端返回整段 TTS 音频
不保存历史
MVP v0.2

再加：

会话历史
多轮对话
简单日志
成本统计
MVP v0.3

再加：

基础记忆
基础关系状态
Android 客户端
十五、最后一句最直接的话

你现在的最小 MVP，不要定义成“一个 AI 伴侣 App”，
而要定义成：

“一个本地网页 + 后端的语音聊天验证器。”

只要它能完成：
说话 → 识别 → 回复 → 播放
你这个项目就算真正启动成功了。Qwen-ASR-Realtime 的 WebSocket/VAD 流程、Qwen3.5 的公开模型线、Qwen3-TTS 的低延迟实时语音能力，以及浏览器 getUserMedia() 的本地安全上下文支持，都足够支撑这个 MVP。

下一步最顺的，就是我直接给你一份 MVP 任务清单（按文件和模块拆开）。

可以
已思考 4s

可以。下面这份就是你现在要的 MVP 任务清单，按“最小能跑通语音闭环”来拆，不按完整产品拆。

这个 MVP 只验证一件事：

你对着电脑麦克风说一句话 → 后端能识别 → Qwen3.5 能回复 → Qwen3-TTS 能说出来。

这里有几个已确定的基础事实：

浏览器可以用 getUserMedia() 采集麦克风，而且 localhost 属于安全上下文，可以直接本地开发测试。
Qwen-ASR-Realtime 是 WebSocket 实时音频流接口，支持 VAD 模式和 Manual 模式；你这个 MVP 最适合先用 VAD 模式。
Qwen3.5 官方仓库已公开，可以作为大脑。
Qwen3-TTS 官方仓库已公开，支持 voice clone、voice design 和高质量语音生成。
一、MVP 目标
成功标准

只要做到下面 6 条，这个 MVP 就算成功：

网页能申请麦克风权限
网页能把音频发给后端
后端能拿到 ASR 最终文本
后端能调用 Qwen3.5 生成回复
后端能调用 Qwen3-TTS 生成音频
网页能自动播放 AI 的声音
二、MVP 范围
做
一个网页调试页
一个后端 WebSocket 服务
Qwen-ASR-Realtime 接入
Qwen3.5 接入
Qwen3-TTS 接入
最基础日志
不做
Android App
小程序
数据库复杂设计
长期记忆
关系成长
数字人
支付
用户系统
多角色
微调
流式 TTS 分段播放
三、任务拆分
A. 前端：最小网页调试页
A1. 起一个本地网页

做一个最简单页面，只有：

开始说话按钮
停止按钮
状态显示区
用户识别文本区
AI 回复文本区
音频播放区
A2. 麦克风采集

用 getUserMedia() 申请麦克风权限。
这一步是浏览器采集音频的标准入口，且 localhost 可用。

A3. 音频处理

先做最简单版本：

采到音频
切小块
发给 WebSocket

这里不要先追求完美格式转换，先能送达后端。

A4. WebSocket 客户端

需要支持：

建立连接
发送事件
接收事件
断线提示
A5. 前端状态机

页面状态只保留这几个：

idle
recording
recognizing
thinking
speaking
error
A6. 文本和音频展示

前端要能：

显示 ASR partial
显示 ASR final
显示 AI reply_text
播放 TTS 音频 URL
B. 后端：最小服务骨架
B1. 起后端服务

建议：

Python
FastAPI
WebSocket

FastAPI 官方对 WebSocket 有原生支持，适合你这种“网页调试页 + 实时事件流”场景。

B2. 提供两个入口

只要：

GET /health
WS /realtime
B3. 建一个最小会话状态

后端内存里先维护：

session_id
当前状态
当前音频缓冲
当前 transcript
当前 reply

先不接数据库也行。

B4. 日志

至少打印：

WebSocket 连接建立
音频 chunk 收到
ASR final
LLM reply
TTS 完成
错误信息
C. ASR：先跑通语音转文字
C1. 接入 Qwen-ASR-Realtime

WebSocket 连接建立后，先发 session.update。
官方文档明确建议把这个作为连接成功后的第一步。

C2. 先选 VAD 模式

在 session.update 中配置：

input_audio_format
sample_rate
language = zh
turn_detection = server_vad

官方文档说明，VAD 模式下服务端自动检测语音起止并返回最终识别结果。

C3. 持续发送音频

把网页传来的音频 chunk 映射成：

input_audio_buffer.append

这是 Qwen-ASR-Realtime 的核心流式送音频事件。

C4. 结束时发 finish

一句话结束后或页面点停止后，发：

session.finish

官方说明客户端收到 session.finished 后需要主动断开连接。

C5. 处理服务端事件

至少处理这些：

实时文本事件
最终文本事件
finished 事件

然后统一回推给网页：

asr.partial
asr.final
C6. 验收

验收标准：

对着麦克风说一句中文
页面能看到最终识别文本
D. LLM：接 Qwen3.5 做回复
D1. 最小 prompt

先只做一个固定 prompt，比如：

你是一个温柔的 AI 伴侣
用简短中文回复
每次回复 1~2 句
D2. 输入

只吃：

asr.final 文本
D3. 输出

先只返回：

reply_text
D4. 模型

先接 Qwen3.5。官方仓库已经公开，你可以按自己的推理方式接入。

D5. 验收

验收标准：

后端拿到用户文本后
能返回一条中文回复
页面能显示出来
E. TTS：接 Qwen3-TTS 做说话
E1. 先只做整段合成

不要先做流式播放。
先做：

输入 reply_text
返回完整音频
E2. 模型

先用 Qwen3-TTS。官方仓库已公开，并支持高质量语音生成。

E3. 音频输出

后端把生成音频：

存成本地文件
或
直接转成可播放 URL
E4. 前端播放

网页收到 audio_url 后：

自动播放
E5. 验收

验收标准：

页面显示 AI 回复后
能立即播出声音
四、最小事件流
前端发给后端
ws.connect
audio_chunk
stop_recording
后端发给前端
state: recording
asr.partial
asr.final
state: thinking
reply_text
state: speaking
audio_url
state: idle
五、目录建议
前端
frontend/
  index.html
  app.js
  ws.js
  audio.js
  player.js
  styles.css
后端
backend/
  main.py
  ws_handler.py
  asr_client.py
  llm_client.py
  tts_client.py
  state.py
  utils.py
六、7 天任务表
Day 1
起网页
起 FastAPI
打通 WebSocket
网页能连上后端
Day 2
网页拿到麦克风权限
音频 chunk 发给后端
后端打印收到音频
Day 3
接 Qwen-ASR-Realtime
先跑 VAD 模式
页面显示 asr.final
Day 4
接 Qwen3.5
页面显示 reply_text
Day 5
接 Qwen3-TTS
页面自动播放声音
Day 6
状态机补齐
错误处理补齐
多测几轮中文对话
Day 7
录 demo
写问题清单
决定下一步是上 Android 还是先补记忆
七、你现在最应该先做的 3 件事
起一个本地网页，先拿到麦克风权限
因为浏览器这一步是整个 MVP 的入口。
起一个最小 WebSocket 后端
因为 ASR 本身就是 WebSocket 事件流。
先只打通 ASR，再接 LLM，再接 TTS
顺序不要反。先听懂，再思考，再说出来。
八、最后给你一句最直接的话

你这个 最小 MVP，不要把它想成“做一个 App”。
它其实只是：

一个本地网页 + 一个后端语音闭环验证器。

只要这条链路通了，你后面接 Android 就是“换个输入输出壳子”，不是从零开始。

下一步最顺的是我直接给你一份 MVP 文件级任务单，也就是“每个文件写什么”。