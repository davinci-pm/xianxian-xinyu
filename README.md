# 先贤心语

本仓库是“先贤心语”本地端到端纵向切片：人物卡牌 → 人物详情 → AI 主动开场 → 用户回复 → AI 追问 → 保存会话 → 新会话读取已确认记忆。

当前包含 19 位可对话人物：原有孔子、峰哥亡命天涯视角、马可·奥勒留、尼采，以及 15 个从 GitHub 高星人物 Skill 扩展的人格。上游仓库完整保存在 `skills/upstream`，固定提交并记录在 `ALLOWLIST.yaml`；运行时只读取每个仓库的原版 `SKILL.md`，全部 Markdown 资料进入本地混合 RAG，仓库脚本和二进制不会执行。默认 Mock 模型用于工程闭环，不可用于真实用户上线。

## 环境要求

- Node.js 20+（当前已验证 26.7.0）
- npm 11+
- Python 3.11（不要使用本机默认 Python 3.9）
- SQLite 3.35+，需支持 FTS5

当前机器的 `127.0.0.1:8000` 已被其他 Python 服务占用，因此本项目后端统一使用 `8765`。

## 第一次安装与初始化

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[dev]'

cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed
.venv/bin/python -m app.scripts.ingest_rag
cd ../frontend
npm ci
```

配置均可省略并使用默认 Mock。需要自定义时，将 `.env.example` 复制为仓库根目录 `.env`，将 `frontend/.env.local.example` 复制为 `frontend/.env.local`。不得把真实密钥提交到仓库。

`ingest_rag` 会读取已审核并锁定版本的峰哥 Skill 和 15 个项目内上游 Skill，按 Markdown 标题切块，以 BM25 + `BAAI/bge-small-zh-v1.5` 本地向量建立索引。当前导入 255 份原始文档和 10,000 个分块，其中 15 个新增人物占 250 份文档、9,915 个分块。首次运行约下载 90 MB 以内的 ONNX 模型到 `data/models/fastembed`。完整语料、分块索引和向量保留在本机；聊天时只把本轮召回的最多 4 个片段随 Prompt 发给当前大模型提供商。重复执行会原位重建同一批分块，不会产生重复数据。

## 本地启动

终端一：

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

终端二：

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1
```

打开 <http://127.0.0.1:3000>。后端健康检查为 <http://127.0.0.1:8765/health>，OpenAPI 文档为 <http://127.0.0.1:8765/docs>。

## 全量检查

```bash
cd backend
.venv/bin/ruff check app tests alembic/env.py
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed
.venv/bin/python -m app.scripts.ingest_rag

cd ../frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Playwright 会自动启动 8765 后端和 3000 前端，并在 Chromium 桌面与移动视口各执行一次完整记忆链路。

## 接入真实模型

适配器支持 OpenAI-compatible `POST /chat/completions` 流式协议，可供火山方舟或其他兼容服务使用：

```bash
export LLM_PROVIDER=openai_compatible
export LLM_API_KEY='仅在本机环境设置'
export LLM_BASE_URL='供应商兼容接口基地址'
export LLM_MODEL='已开通的模型 ID'
```

重启后端后再进行聊天冒烟。密钥不会写入代码、文档、日志或数据库。模型是否可用以本地环境变量和实际冒烟结果为准。

人物生成与对话意图识别可以使用不同模型。当前推荐火山方舟的 `Doubao-Seed-Character` 生成人物回复，阿里云百炼北京区的 `qwen3.8-flash` 以严格 JSON Schema 输出意图、情绪和下一步对话动作。明显意图优先走零网络延迟的本地快速路径；模糊意图才调用 Flash，并设置 1.5 秒硬超时。意图模型缺少密钥、超时或格式错误时会自动回退本地规则，不影响安全流程和聊天可用性。具体配置与业务 benchmark 见 `docs/03_模型选型与中文对话意图Benchmark.md`。

## 重要边界

- 游客通过 HttpOnly Cookie 隔离会话，可在同一浏览器恢复；本切片尚未实现账号登录与跨设备归并。
- 长期记忆只在用户点“记住”后生效；当前是同浏览器跨会话记忆，不承诺跨设备。
- 未审核 GitHub Skills 处于 `allowlisted=false`、`enabled=false`，不会执行。已纳入的 16 个外部人物 Skill（含峰哥）均固定提交并记录 MIT 许可证；Adapter 只把原版 `SKILL.md` 作为常驻人格指令，其余 Markdown 由本地混合 RAG 按需召回，避免整库塞入上下文。仓库附带脚本没有命令执行权限，也不会被 Skill Adapter 调用。
- 自伤、自杀和极端痛苦信号会在模型调用前中断人物角色，进入确定性安全响应。
- 本阶段不包含部署、付费、语音、数字人、社区或自定义人物。
