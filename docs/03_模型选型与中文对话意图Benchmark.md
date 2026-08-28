# 先贤心语模型选型与中文对话意图 Benchmark

更新时间：2026-08-27

## 结论

本项目不再用一个模型同时承担全部职责，推荐如下：

| 职责 | 首选 | 原因 |
|---|---|---|
| 人物回复生成 | Doubao-Seed-Character | 官方明确定位于虚拟陪伴和角色扮演，重点匹配人设保持、多轮互动和自然对话，和“先贤心语”的核心场景最接近。 |
| 对话意图识别/导演 | 本地快速路径 + qwen3.8-flash（非思考模式） | 明显意图不走网络；模糊表达才调用 Flash。北京区可直接调用并支持严格 JSON Schema，兼顾结构稳定与首字速度。 |
| 生成降级 | 当前 DeepSeek 接口 + Persona Pack 固定降级语 | 新密钥或供应商异常时保持服务可用。 |
| 意图降级 | 本地 `heuristic-intent-v1` | 不依赖网络，不允许意图模型故障阻断聊天。 |

这不是“某个通用榜单第一名就是对话意图第一名”的结论。公开榜单主要测知识、推理、代码、工具调用或通用偏好，目前没有权威公开榜单能完整覆盖本产品的“隐含困惑 + 情绪 + 对话动作 + 人格推进”。因此公开资料只负责筛选候选，最终上线结论由项目业务集盲测决定。

## 公开资料依据

- [火山引擎豆包产品页](https://www.volcengine.com/product/doubao)将 Doubao-Seed-Character 明确列为面向新一代虚拟陪伴的角色扮演模型；方舟同时提供 Chat API、流式输出及角色扮演提示词指南。
- [千问模型更新页](https://help.aliyun.com/zh/model-studio/newly-released-models)将 `qwen3.8-flash` 定位为兼顾理解能力、响应速度和高并发的模型。
- [qwen3.8-max 官方模型页](https://help.aliyun.com/zh/model-studio/qwen3-8-max)仍作为准确率上限对照组，而不放在每轮在线链路中。
- [百炼结构化输出文档](https://help.aliyun.com/zh/model-studio/qwen-structured-output)确认 JSON Schema 可通过 `strict: true`约束字段结构，适合意图分类这类机器消费结果。
- [GLM-4.7 官方文档](https://docs.bigmodel.cn/cn/guide/models/text/glm-4.7)强调多轮上下文、意图理解与角色扮演，是第二轮对照候选。
- [豆包 2.0 官方发布说明](https://developer.volcengine.com/articles/7610285824933445675)显示其强化复杂指令、格式稳定性和多轮指令遵循，可作为意图导演的同供应商备选。

## 为什么 DeepSeek 体感不够好

当前代码原先只有顺序推进的状态机：破冰后机械地从“识别问题”进入“澄清”和“思想引导”。模型负责组织回复，但没有一个结构化对话导演先判断用户本轮到底是在求安慰、求决定、想被挑战、想听例子还是准备结束。因此问题不只在模型本身，也在编排层。

本次已新增独立意图层，输出：

- `primary_intent`
- `emotion`
- `user_need`
- `unresolved_issue`
- `recommended_move`
- `recommended_stage`
- `should_ask_question`
- `confidence`

只有置信度不低于 0.80 的模型建议可以改变普通对话阶段；任何模型都不能进入或退出安全状态。自伤、自杀等规则仍在模型调用前执行。

## 项目专用 Benchmark

初始数据集位于 `data/benchmarks/intent_v1.jsonl`，包含 24 条中文多义表达，覆盖职业、选择、情绪支持、关系、学习、自我理解、闲聊和结束意图。评分为：

- 主意图准确率：50%
- 情绪准确率：20%
- 推荐动作准确率：20%
- JSON Schema 成功率：10%
- 同时记录失败数和平均延迟，不将超时样本排除出准确率分母。

候选至少比较 `qwen3.8-flash`、`qwen3.8-max`、`glm-4.7`、`doubao-seed-2.0-pro` 与当前 DeepSeek。测试密钥只通过环境变量引用，脚本不会输出密钥：

```bash
export QWEN_API_KEY='本机密钥'
export GLM_API_KEY='本机密钥'
export ARK_API_KEY='本机密钥'
export DEEPSEEK_API_KEY='本机密钥'
export INTENT_BENCH_TARGETS_JSON='[
  {"name":"qwen-flash","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model":"qwen3.8-flash","api_key_env":"QWEN_API_KEY","reasoning_effort":"none"},
  {"name":"qwen-max","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model":"qwen3.8-max","api_key_env":"QWEN_API_KEY","reasoning_effort":"none"},
  {"name":"glm","base_url":"https://open.bigmodel.cn/api/paas/v4","model":"glm-4.7","api_key_env":"GLM_API_KEY","reasoning_effort":null},
  {"name":"doubao","base_url":"https://ark.cn-beijing.volces.com/api/v3","model":"doubao-seed-2-0-pro-260215","api_key_env":"ARK_API_KEY","reasoning_effort":"minimal"},
  {"name":"deepseek","base_url":"https://api.deepseek.com","model":"deepseek-v4-pro","api_key_env":"DEEPSEEK_API_KEY","reasoning_effort":null}
]'
cd backend
.venv/bin/python -m app.scripts.benchmark_intent
```

2026-08-27 已用当前 `deepseek-v4-pro` 接口跑过 24 条初始集：严格 JSON Schema 请求 24/24 返回 HTTP 400，因此 Schema 成功率为 0。这个结果只说明当前接口不能按本项目要求直接充当强约束导演，不能解释为 DeepSeek 的通用语义能力是 0 分；若要比较其纯分类能力，需要另跑 `json_object` 或无约束 JSON 组，但该组不满足本项目结构稳定性门槛。

正式决定前应把数据集扩到至少 200 条，由两人独立标注并处理分歧。上线门槛建议为：主意图准确率不低于 90%、Schema 成功率不低于 99%、高风险样本不得漏过确定性安全层、意图 P95 不高于 1.2 秒、用户提交至首个回复字符 P95 不高于 2.5 秒。

在线速度策略：

- 结束、职业焦虑等具有两个以上明确信号的输入直接走本地快速路径。
- 模糊输入才调用 `qwen3.8-flash`，关闭思考，最多输出 320 Token，硬超时 1.5 秒。
- 意图请求与本地记忆读取、混合 RAG 并行执行，不串行累加耗时。
- 人物回复最多生成 560 Token，并从流式接口立即显示首个字符。
- SSE `meta` 和 `done` 事件返回 `preprocessing_ms`、`first_chunk_ms`、`total_ms`，用于统计 P50/P95。

### 当前本机速度基线

2026-08-27 在相同网络、孔子 Persona Pack、短中文输入下完成小样本实测：

| 生成模型 | 本地预处理 | 首个回复字符 | 整轮完成 |
|---|---:|---:|---:|
| deepseek-v4-pro | 338ms | 12,089ms | 13,235ms |
| deepseek-v4-flash（冷请求） | 330ms | 4,521ms | 5,693ms |
| deepseek-v4-flash（热请求） | 1ms | 3,087ms | 4,154ms |

这只是单机小样本，不代表 P95。它足以定位当前主要瓶颈在生成模型而非 RAG，并证明 Flash 比 Pro 的首字速度明显改善。当前本地服务已暂时切换至 `deepseek-v4-flash`；最终仍要求 Doubao-Seed-Character 做至少 20 轮连续测速并达到首字 P95 不高于 2.5 秒，否则继续和 Doubao-Seed-2.1-Turbo 做盲测取舍。

## 接入配置

人物模型：

```dotenv
LLM_PROVIDER=doubao
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-character-260628
LLM_API_KEY=仅在本机填写
```

具体快照 ID 必须以账号在方舟控制台实际开通的模型 ID 为准，不静默替换。

意图模型：

```dotenv
INTENT_LLM_ENABLED=true
INTENT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
INTENT_LLM_MODEL=qwen3.8-flash
INTENT_LLM_API_KEY=仅在本机填写
INTENT_LLM_REASONING_EFFORT=none
INTENT_LLM_TIMEOUT_SECONDS=1.5
INTENT_LOCAL_FAST_PATH_ENABLED=true
INTENT_LOCAL_FAST_PATH_THRESHOLD=0.82
```

## 当前阻塞

当前运行环境只有 DeepSeek 密钥，没有 `ARK_API_KEY` 或 `DASHSCOPE_API_KEY`。代码接入、回退和测试框架已完成，但 Doubao-Seed-Character 与 qwen3.8-flash 的真实请求尚不能冒烟。拿到两个密钥后，应先跑 24 条小集和 20 轮连续测速，再进行人物对话人工盲测；不得只根据供应商宣传直接切换生产流量。
