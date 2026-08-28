# 先贤心语前端

本目录是 Next.js 16 App Router 前端。完整安装、启动、测试和真实模型配置说明见仓库根目录 [README.md](../README.md)。

本地默认通过 `/api/backend/*` 代理到 `http://127.0.0.1:8765/api/v1/*`，避免浏览器跨域并正确传递 HttpOnly 游客 Cookie。

## 路由

- `/`：人物发现、搜索和组合筛选
- `/paths`：三步思想路径
- `/figures/[figureId]`：人物详情和公开资料
- `/chat/[conversationId]`：真实主动开场与 SSE 对话
- `/notes`、`/notes/[noteId]`：本机心语札记
- `/settings/memory`：记忆查看与本机覆盖设置
- `/personas/[slug]`：兼容旧链接，重定向到 `/figures/[slug]`

## 本地数据边界

人物、会话、消息、候选记忆确认和公开资料来自 FastAPI 真实接口。思想路径匹配、札记和记忆编辑/暂停/隐藏覆盖层保存在浏览器 `localStorage`；界面会明确说明它们不是服务器级删除或跨设备同步。

## 命令

```bash
npm install
npm run dev -- --hostname 127.0.0.1
npm run typecheck
npm run lint
npm run test
npm run build
npm run test:e2e
```

E2E 使用 `3100` 前端端口和 `8876` Mock 后端端口，以免误用真实模型。Next.js 16 同一目录不能同时运行两个 dev 实例，因此执行 E2E 前需先停止 `3000` 上的开发服务，结束后再恢复。
