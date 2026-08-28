# 先贤心语前端重构验证记录

> 2026-08-28，执行包 Phase 0～5。

## 阶段结果

| 阶段 | 结果 | 截图证据 |
| --- | --- | --- |
| Phase 0 审计 | 完成现有栈、路由、接口、可复用逻辑与 Mock/真实边界审计 | `docs/redesign-evidence/phase-0/` |
| Phase 1 首页/思想路径 | 完成人物发现、组合筛选、困惑输入、三步路径与推荐 | `docs/redesign-evidence/phase-1/` |
| Phase 2 人物详情 | 完成原创人物视觉、资料标签页、开场预览与真实创建会话 | `docs/redesign-evidence/phase-2/` |
| Phase 3 正式聊天 | 完成桌面三栏/移动单栏、SSE、停止/重试、引用与记忆抽屉、安全恢复 | `docs/redesign-evidence/phase-3/` |
| Phase 4 心语札记 | 完成列表、搜索、编辑、防抖保存、离线草稿、导出、继续对话和记忆设置 | `docs/redesign-evidence/phase-4/` |
| Phase 5 响应式/测试 | 五组断点无横向溢出；单元、组件、E2E、构建通过 | `docs/redesign-evidence/phase-5/` |

## 响应式截图

- 1440×960：`home-1440x960.png`、`chat-1440x960.png`
- 1024×768：`home-1024x768.png`、`chat-1024x768.png`
- 768×1024：`home-768x1024.png`、`chat-768x1024.png`
- 430×932：`home-430x932.png`、`chat-430x932.png`
- 390×844：`home-390x844.png`、`chat-390x844.png`

自动检查五组尺寸的 `documentElement.scrollWidth > innerWidth`，最终结果均为 `false`。

## 测试覆盖

- 人物筛选组合与清空。
- 快捷回答只写入输入框。
- IME composition 时 Enter 不发送。
- 失败重试不重复添加用户消息。
- 引用抽屉关闭后恢复触发按钮焦点，并限制 Tab 焦点在抽屉内。
- 记忆暂停、修改展示与本机隐藏。
- 札记本机保存、650ms 防抖、离线草稿和重载恢复。
- E2E：首页困惑 → 思想路径 → 孔子详情 → 主动开场 → 回复 → 引用/记忆 → 札记 → 编辑 → 继续 → 跨会话记忆。
- E2E：危机安全响应与输入恢复。
- E2E：在世公众人物的非本人、非授权和高风险建议边界。

## 视觉资产

孔子、尼采、马可·奥勒留使用内置图像生成工具制作的原创纸本编辑插画，生成提示遵循执行包的人物资产规范：竖版 4:5、暖纸色、无文字/标识/水印、完整头肩构图，并压缩为 WebP：

- `frontend/public/characters/confucius/portrait.webp`
- `frontend/public/characters/nietzsche/portrait.webp`
- `frontend/public/characters/marcus-aurelius/portrait.webp`

其余人物使用不会破图的统一纸刻字印视觉。新增独立立绘后可沿同一路径直接替换，不改组件接口。

## 已知边界

- 后端没有札记 API，札记目前仅保存在本浏览器。
- 后端没有已确认记忆的编辑、暂停和删除 API；设置页操作是明确标识的本机覆盖层。
- 执行包未提供独立人物立绘源文件，P0 三位使用原创生成资产，其余人物使用统一字印视觉。
- 浏览器插件本机缓存的客户端/服务端版本不一致，阶段截图使用项目已安装的 Playwright Chromium 完成。

