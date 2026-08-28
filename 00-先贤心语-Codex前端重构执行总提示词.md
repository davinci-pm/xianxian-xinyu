# 先贤心语：Codex 前端重构与功能实现总任务书

> 使用方式：把本文件与同目录所有图片和文档一起放入现有项目，交给 Codex 执行。  
> 目标：直接修改并跑通现有前端，不要只输出建议、示例代码或新的静态 Demo。

---

# 一、你的角色与任务

你是一名资深 AI 产品前端负责人、交互设计工程师和全栈开发者。请在当前“先贤心语”项目中，基于本目录下的目标高保真图和规范，完成一次可运行、可交互、可渐进接入真实 AI 后端的前端重构。

产品定位：

> 先贤心语是一个主动型 AI 思想人格聊天网站。用户可以从当前困惑或历史人物出发，与基于公开资料构建的 AI 思想人格交流。AI 会主动开场、复述、追问、挑战假设、引用依据并引导用户形成可执行的反思。

本次任务同时包含：

1. 重新设计视觉、布局、字体、人物立绘呈现、气泡、微交互和响应式体验。
2. 保留现有可用业务功能和数据，不做无意义推倒重写。
3. 把当前静态或粗糙页面改成完整可操作链路。
4. 没有后端接口的功能先使用类型安全的 Mock Service 实现，但必须预留真实 API Adapter。
5. 对话、资料引用、长期记忆和札记等核心能力必须有真实状态流转，不能只做无法点击的视觉壳。

不要停在分析阶段。先审计、列出计划，然后持续修改、运行、截图和测试，直到达到验收标准。

---

# 二、必须先读取的参考文件

## 目标设计图

| 编号 | 文件 | 对应页面 |
| --- | --- | --- |
| 01 | `design-references/01-首页-人物发现-桌面端.png` | 首页、人物发现与筛选 |
| 02 | `design-references/02-思想路径-桌面端.png` | 从当前困惑出发的引导与推荐 |
| 03 | `design-references/03-孔子人物详情-桌面端.png` | 人物详情与主动开场预览 |
| 04 | `design-references/04-孔子正式聊天-桌面端.png` | 桌面端正式聊天 |
| 05 | `design-references/05-心语札记-桌面端.png` | 历史对话、札记和长期主题 |
| 06 | `design-references/06-孔子正式聊天-移动端.png` | 移动端正式聊天 |

## 补充资料

- `01-交互流程与页面状态.md`
- `02-人物立绘与视觉素材生成提示词.md`
- `03-竞品与视觉改版方案.md`
- `current-screenshots/` 下的 7 张当前页面截图

设计图用于确定视觉层级、组件关系和体验目标。禁止把整张截图设为页面背景，禁止通过绝对定位复刻一张只能在单一分辨率下工作的图片。

---

# 三、执行原则

## 3.1 先审计，再修改，但不要等待用户二次确认

第一步检查：

- `package.json`、锁文件、构建脚本、TypeScript 配置。
- 路由、页面目录、全局样式、组件库、状态管理和请求层。
- 当前人物数据、聊天数据、接口和环境变量。
- 是否存在 `.openai/hosting.json`、部署配置、测试框架和 CI。
- 是否有未提交的用户改动。不得覆盖或清除无关改动。

生成 `docs/先贤心语-redesign-audit.md`，记录：

- 当前技术栈。
- 可复用部分。
- 需要替换的粗糙实现。
- 依赖变更。
- 路由迁移表。
- 风险和 Mock/真实接口边界。

完成审计后直接进入实现，不要只等待用户确认。

## 3.2 保留框架，渐进重构

- 当前若为 React + TypeScript + Vite，继续使用，不迁移 Next.js。
- 当前若为 Next.js，保持现有 App Router 或 Pages Router，不迁移框架。
- 当前若为 Vue/Svelte 等成熟实现，优先在现有框架内实现同样设计，不因本任务强行改成 React。
- 当前若是 JavaScript，可为新增核心模块使用 TypeScript；不要为了“全量类型化”延误视觉和交互主链路。
- 不要同时引入两个组件库或两个状态管理库。

## 3.3 参考方法，不复制品牌资产

可以参考竞品的信息架构、卡牌发现、主动开场、流式对话、引用展开、记忆管理和反思闭环。不得复制第三方 Logo、插画、文案、音效、字体文件、专有图标或完整页面代码。

---

# 四、推荐技术方案

根据现有项目做最小适配；缺少对应能力时再添加。

| 能力 | 推荐选择 | 实施要求 |
| --- | --- | --- |
| UI 框架 | 保留现有 React/Vue 等 | 不无故迁移 |
| 类型 | TypeScript | 人物、会话、引用、记忆必须有类型 |
| 样式 | 现有 Tailwind 则继续；否则 CSS Modules + CSS Variables | Design Token 统一放入全局变量 |
| 无障碍组件 | Radix UI 或现有 Headless 组件 | 只用于 Dialog/Sheet/Tooltip/Dropdown 等基础能力，视觉完全自定义 |
| 图标 | Lucide 或项目现有线性图标 | 统一 1.5～1.75px 线宽 |
| 动效 | CSS Transition/Web Animations；已有 Motion 时继续使用 | 不为简单动效强加大依赖 |
| 服务端状态 | TanStack Query 或项目现有请求层 | 处理缓存、重试和失效 |
| 本地 UI 状态 | React state；跨页复杂状态才用 Zustand/现有 Store | 不把所有状态塞进全局 Store |
| 表单与校验 | React Hook Form + Zod 或等价方案 | 思想路径输入、札记编辑、记忆编辑 |
| Markdown | react-markdown + GFM + sanitize 或等价方案 | AI 输出必须防止 XSS |
| 流式聊天 | fetch + ReadableStream 或 SSE | 支持停止、重试和部分文本保留 |
| 测试 | Vitest/Jest + Testing Library；E2E 用 Playwright | 覆盖主链路和关键状态 |
| 图片 | picture + WebP/AVIF + lazy loading | 首屏人物图预加载，列表图懒加载 |

不要在没有必要时引入重量级图表库、游戏引擎、3D 库或整套商业 UI 主题。

---

# 五、建议目录结构

按现有项目习惯调整命名，但保持关注点分离。

```text
src/
  app-or-pages/
    discovery/
    paths/
    figures/
    chat/
    notes/
    settings/
  components/
    layout/
    figure/
    chat/
    sources/
    memory/
    notes/
    ui/
  features/
    discovery/
    thought-path/
    conversation/
    citations/
    memory/
    notes/
  data/
  services/
  mocks/
  styles/
  types/
public/
  characters/{figureId}/
  textures/
  motifs/
```

---

# 六、路由与页面范围

必须实现或映射以下路由：

```text
/                         人物发现首页
/paths                    思想路径
/figures/:figureId        人物详情
/chat/:conversationId     正式对话
/notes                    心语札记列表
/notes/:noteId            心语札记详情
/settings/memory          长期记忆管理，可由抽屉复用
```

如果项目已有不同路由，不要制造重复页面；建立映射并保留旧链接重定向。

---

# 七、全局 Design Token

在 `tokens.css` 或等价位置实现，组件禁止到处硬编码颜色。

```css
:root {
  --color-paper: #F4F0E6;
  --color-paper-elevated: #FBF8F0;
  --color-ink: #1D1B18;
  --color-ink-secondary: #6D655A;
  --color-vermilion: #A4472D;
  --color-vermilion-hover: #8F3924;
  --color-vermilion-soft: #F1DED4;
  --color-antique-gold: #9B7A3A;
  --color-gold-soft: #E9DFC8;
  --color-divider: #D8D0C2;
  --color-clay-user: #EFE2CE;
  --color-success: #667A55;
  --color-danger: #9B3F33;

  --font-serif: "Noto Serif SC", "Source Han Serif SC", "Songti SC", serif;
  --font-sans: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", system-ui, sans-serif;

  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;
  --radius-pill: 999px;

  --shadow-card: 0 8px 28px rgba(46, 36, 24, 0.06);
  --shadow-card-hover: 0 14px 34px rgba(46, 36, 24, 0.10);
  --shadow-composer: 0 -10px 30px rgba(46, 36, 24, 0.07);

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  --duration-fast: 140ms;
  --duration-base: 220ms;
  --duration-slow: 420ms;
  --ease-standard: cubic-bezier(.2,.8,.2,1);
}
```

## 字体层级

| 用途 | 桌面端 | 移动端 | 字重/行高 |
| --- | --- | --- | --- |
| 首页主标题 | 56～64px | 38～44px | Serif 700 / 1.15 |
| 页面标题 | 38～44px | 30～34px | Serif 700 / 1.2 |
| 人物名 | 36～54px | 30～38px | Serif 700 |
| 区块标题 | 22～26px | 20～22px | Serif 600 |
| 正文 | 16px | 16px | Sans 400 / 1.7 |
| 气泡正文 | 17px | 16px | Sans 400 / 1.75 |
| 标签/辅助 | 12～14px | 12～14px | Sans 500 |

通过字体子集或可靠字体 CDN 加载；加载失败必须有中文系统字体回退，避免 FOIT。

## 纸张纹理

- 使用非常轻的 CSS noise、可授权纹理或自制纹理，透明度不超过 3%。
- 不要让纹理影响正文对比度。
- 不要用一张巨大的位图覆盖全部页面。

---

# 八、全局布局与响应式

## 桌面端

- 设计基准宽度 1440px，内容最大宽度 1480px，左右边距 32～48px。
- Header 高 76～92px；滚动后可压缩为 68px。
- 首页使用 12 列栅格。
- 聊天页为 240px / minmax(620px, 1fr) / 300px 三列。
- 正文阅读列控制在 720～780px。

## 断点

```text
< 768px       手机
768–1023px    平板
1024–1279px   小桌面
>= 1280px     桌面
```

## 移动端

- 横向内边距 16px。
- 触控目标至少 44×44px。
- 对话页隐藏全局导航，保留返回、人物状态、朗读和更多。
- 输入框固定底部并处理 `env(safe-area-inset-bottom)`。
- 禁止横向溢出；唯一允许横向滚动的是步骤条和快捷回答。

---

# 九、页面一：首页与人物发现

参考 `01-首页-人物发现-桌面端.png`。

## 页面目标

用户在 10 秒内理解“可以和历史思想人物聊现实困惑”，并从人物或困惑两条路径进入。

## 必须包含

- Logo“先贤心语”。
- 导航“发现人物 / 思想路径 / 心语札记”。
- 主标题与一句简短解释。
- 困惑输入入口，例如“最近什么一直在心里绕？”。
- 推荐人物主卡。
- 时代、领域、话题、当前困惑四类筛选。
- 搜索、筛选结果数量、清空筛选、加载和空状态。

## 人物卡字段

```ts
type FigureCardData = {
  id: string;
  name: string;
  originalName?: string;
  era: string;
  region: string;
  summary: string;
  conversationAngle: string;
  suitableTopics: string[];
  portrait: string;
  accentColor: string;
  motif: string;
};
```

## 卡牌交互

- Hover：整体上移 4px，阴影加强，立绘产生不超过 3px 的轻视差。
- Focus：显示 2px 朱砂外框，键盘可操作。
- 点击卡牌任意主体区域进入人物详情。
- “直接开聊”按钮单独创建会话，阻止卡牌点击冒泡。
- 图片加载失败使用人物姓名首字和专属色占位，不显示破图图标。

至少保留并配置孔子、尼采、马可·奥勒留、安德烈·卡帕西、查理·芒格，以及现有项目已有的人物。

对于“峰哥亡命天涯”等当代网络人物：默认不使用“先贤”暗示，不得声称本人授权；产品上线前必须经过肖像权、人格权、内容和平台规则审核。开发阶段可以保留数据开关，但默认不进入公开推荐首屏。

---

# 十、页面二：思想路径

参考 `02-思想路径-桌面端.png`。

核心文案：

- 眉题：“从你的困惑出发”
- 标题：“先不急着选人物，说说最近什么一直困扰着你。”
- 说明：“我们会从你的处境里，找到一个值得继续追问的问题，再邀请合适的思想伙伴与你谈。”
- 步骤：“说出困惑 / 找到问题 / 遇见合适的人”

```ts
type ThoughtPathStep = 'describe' | 'clarify' | 'recommend';
type ThoughtPathResult = {
  rawConcern: string;
  themes: string[];
  followUpQuestion: string;
  quickAnswers: string[];
  selectedAnswer?: string;
  recommendations: Array<{
    figureId: string;
    angle: string;
    teaserQuestion: string;
    reasons: string[];
  }>;
};
```

- 输入后调用分析接口或 Mock，显示 2～4 个可编辑线索。
- 每次只出现一个追问。
- 推荐 3 位人物，并说明角度，禁止输出虚假的“匹配度 98%”。
- 点击推荐人物进入详情，同时保存当前困惑。
- 进入聊天后，当前困惑用于生成主动开场。

---

# 十一、页面三：人物详情与主动相遇

参考 `03-孔子人物详情-桌面端.png`。

孔子示例文案：

- 时代：“春秋 · 鲁国”
- 标题：“孔子”
- 介绍：“从关系、责任与日常践履出发，陪你把抽象困惑落到可以行动的一步。”
- 谈话方式：“先听处境 / 追问责任 / 回到行动”
- 适聊话题：“人际关系 / 人生选择 / 自我修养 / 责任边界”
- 方式说明：“不急着给结论，会先问清你在这段关系中承担了什么，也提醒你看见对方所处的位置。”
- 主按钮：“让孔子先开口”
- 次按钮：“查看思想与资料来源”
- 声明：“AI 思想人格 · 基于公开资料构建 · 非真人本人”

主动开场：

> 你说自己总在迁就别人。可我想先问：你这样做，是出于真诚，还是害怕关系破裂？

快捷回答：“我怕让别人失望 / 我不知道边界在哪里 / 我想换个角度谈”。

```ts
type FigureProfile = FigureCardData & {
  fullName?: string;
  birthDeath?: string;
  dialogueMethods: string[];
  suitableQuestions: string[];
  coreIdeas: Array<{ title: string; explanation: string }>;
  representativeTexts: SourceSummary[];
  limitations: string[];
  disclosure: string;
  defaultOpeners: string[];
};
```

“核心思想 / 代表文本 / 时代局限 / 资料来源”必须可切换，不能只是装饰。

---

# 十二、页面四：正式对话

参考 `04-孔子正式聊天-桌面端.png` 和 `06-孔子正式聊天-移动端.png`。

## 桌面布局

- 左栏：人物状态、本次对话、最近交谈、记忆和人物资料。
- 中栏：会话标题、消息、快捷回答、输入框。
- 右栏：思考路径、当前洞察、资料引用、长期记忆、结束并生成札记。
- 左右栏在中等宽度可折叠；小于 1024px 时右栏默认收起。

## 气泡

- 人物气泡：米白纸张、人物专属左侧纹样、头像、朗读和查看依据。
- 用户气泡：浅陶土色，右对齐，最大宽度 76%。
- 系统反思：居中、窄条、低对比度，不伪装成人物消息。

## 示例会话

人物：“你说自己总在迁就别人。可我想先问：你这样做，是出于真诚，还是害怕关系破裂？”

用户：“我更怕别人失望。只要有人不高兴，我就会觉得是不是自己做错了。”

人物：“你愿意顾及别人，这是善意。但若把所有人的情绪都当成自己的责任，你还能诚实地表达自己吗？”

强调句：“你可以照顾关系，也可以保留自己的位置。”

```ts
type ConversationStage = 'situation' | 'motivation' | 'boundary' | 'action';
type MessageStatus = 'queued' | 'sending' | 'streaming' | 'complete' | 'failed' | 'stopped';
type ChatMessage = {
  id: string;
  conversationId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  status: MessageStatus;
  createdAt: string;
  stage?: ConversationStage;
  citations?: Citation[];
  quickReplies?: string[];
  reflection?: string;
  audioUrl?: string;
  retryOf?: string;
};
```

## 必须实现

- 用户发送后立即显示本地消息和发送状态。
- AI 流式返回，支持停止生成。
- 失败消息原位显示“重试”，且不重复插入用户消息。
- 快捷回答点击后写入输入框，默认不自动发送。
- Enter 发送，Shift+Enter 换行；中文输入法合成阶段不误发送。
- 未发送草稿离开时提醒或保留。
- 朗读具备播放、暂停、加载和失败状态。
- 引用 Chip 可展开简版来源并打开完整资料抽屉。
- 记忆卡可查看、编辑、停用和删除。
- 结束对话后生成札记，生成期间不可重复触发。

```ts
type DialogueMove =
  | 'open'
  | 'reflect'
  | 'clarify'
  | 'challenge'
  | 'connect_source'
  | 'suggest_action'
  | 'summarize';
```

每条人物回复最多承担 1～2 个主要动作，避免变成长篇教科书。

---

# 十三、页面五：心语札记

参考 `05-心语札记-桌面端.png`。

核心文案：

- 标题：“心语札记”
- 说明：“把每一次认真交谈，留成可以重新理解自己的线索。”
- 示例主题：“总在迁就别人”
- 核心总结：“你并非没有边界，只是习惯用别人的满意，确认自己是否做得正确。”

```ts
type ThoughtNote = {
  id: string;
  conversationId: string;
  figureId: string;
  title: string;
  createdAt: string;
  durationMinutes?: number;
  coreInsight: string;
  situation: string;
  possibleRoot: string;
  newUnderstanding: string;
  nextAction?: string;
  practiceUntil?: string;
  quote?: string;
  citations: Citation[];
  userAddition?: string;
  saveStatus: 'saved' | 'saving' | 'local-only' | 'failed';
};
```

必须实现：

- 左侧按时间展示对话，可搜索人物和困惑。
- 中间札记全部字段可编辑，800ms 防抖自动保存。
- 保存失败保留本地草稿并显示恢复按钮。
- 右侧展示持续主题、思想伙伴和长期记忆。
- 支持继续交谈、设为提醒、导出 Markdown/PDF、删除札记。
- 删除需要确认，完成后返回列表，并提供短时间撤销。

---

# 十四、资料来源与 RAG 展示

```ts
type Citation = {
  id: string;
  sourceId: string;
  title: string;
  author?: string;
  work?: string;
  section?: string;
  originalText?: string;
  translation?: string;
  explanation: string;
  url?: string;
  sourceType: 'primary' | 'academic' | 'reference' | 'commentary' | 'web';
  claimType: 'direct_quote' | 'paraphrase' | 'ai_synthesis';
  retrievedAt?: string;
};
```

展示规则：

- `direct_quote` 使用引号并显示具体篇章。
- `paraphrase` 标记“相关思想”，不得伪装成原句。
- `ai_synthesis` 标记“AI 基于资料的模拟表达”。
- 无可靠来源时不要生成假的引用标签。
- 点击引用必须能看到它支持的是回复中的哪句话。

如果同时实现后端 RAG：

- 将资料按作品、章节和段落入库，保留完整元数据。
- 中文分块建议 600～1000 字，10%～15% 重叠；优先按章节边界。
- 使用向量检索与关键词检索混合召回，首轮召回后重排。
- 模型只能引用检索结果中真实存在的 `sourceId`。
- 返回前校验引用 ID、标题和支持关系。
- 不要让前端持有模型或数据库密钥。

---

# 十五、长期记忆

```ts
type UserMemory = {
  id: string;
  category: 'preference' | 'background' | 'goal' | 'pattern' | 'boundary';
  content: string;
  sourceConversationId?: string;
  confidence?: number;
  status: 'candidate' | 'active' | 'paused';
  createdAt: string;
  updatedAt: string;
};
```

必须支持：

- 查看记忆来自哪次对话。
- 编辑错误内容。
- 暂停引用而不删除。
- 永久删除。
- 关闭自动保存记忆。
- 新记忆保存后显示可撤销 Toast。

禁止保存临时情绪、诊断、模型猜测出的敏感身份、账号密钥、支付信息和用户没有表达过的经历。

---

# 十六、建议 API 合约

如果当前后端已有接口，请写 Adapter，不要破坏旧接口。如果没有后端，使用 MSW 或同类 Mock Service，并保持相同响应结构。

```text
GET    /api/figures
GET    /api/figures/:figureId
POST   /api/thought-path/analyze
POST   /api/conversations
GET    /api/conversations/:id
POST   /api/conversations/:id/messages
POST   /api/conversations/:id/stop
POST   /api/conversations/:id/summary
GET    /api/notes
GET    /api/notes/:id
PATCH  /api/notes/:id
DELETE /api/notes/:id
GET    /api/memories
POST   /api/memories
PATCH  /api/memories/:id
DELETE /api/memories/:id
GET    /api/sources/:id
```

新建会话请求：

```json
{
  "figureId": "confucius",
  "initialConcern": "我总是在迁就别人",
  "entryPoint": "thought_path"
}
```

响应：

```json
{
  "conversationId": "conv_001",
  "figureId": "confucius",
  "title": "总在迁就别人",
  "stage": "situation",
  "openingMessage": {
    "id": "msg_001",
    "role": "assistant",
    "content": "你说自己总在迁就别人。可我想先问：你这样做，是出于真诚，还是害怕关系破裂？",
    "status": "complete",
    "quickReplies": ["我怕让别人失望", "我不知道边界在哪里", "我想换个角度谈"]
  }
}
```

流式事件：

```text
event: message.start
event: message.delta
event: citation.added
event: stage.changed
event: quick_replies.ready
event: message.completed
event: error
```

断线后允许基于 conversationId 重新拉取完整消息，前端不能只依赖内存中的流。

---

# 十七、Persona Pack 与人物 Skills

```ts
type PersonaPack = {
  figureId: string;
  identity: {
    displayName: string;
    disclosure: string;
    era: string;
    limits: string[];
  };
  voice: {
    tone: string[];
    sentenceLength: 'short' | 'medium' | 'long';
    challengeLevel: 1 | 2 | 3;
    forbiddenBehaviors: string[];
  };
  dialoguePolicy: {
    openingMoves: DialogueMove[];
    preferredMoves: DialogueMove[];
    maxQuestionsPerTurn: number;
    endCondition: string;
  };
  skills: Array<{
    id: string;
    name: string;
    description: string;
    enabled: boolean;
  }>;
  ragCollectionId: string;
  visual: {
    accent: string;
    motif: string;
    portraitCard: string;
    portraitDetail: string;
    avatar: string;
  };
};
```

人物 Skills 示例：

- `clarify_context`：澄清处境。
- `reflect_responsibility`：区分用户与他人的责任。
- `challenge_assumption`：挑战未经检验的假设。
- `connect_primary_source`：连接原典。
- `translate_to_action`：把思想落成一步行动。
- `summarize_note`：生成札记。

人物系统提示必须明确：这是基于公开资料构建的模拟人格，不得声称是真人、灵魂、复活或本人授权。

---

# 十八、加载、失败和空状态文案

| 场景 | 文案 |
| --- | --- |
| 人物加载 | “正在整理人物档案…” |
| 人物列表失败 | “人物档案暂时没有展开。” / “重新载入” |
| 思想路径分析 | “正在整理你的问题” |
| 思想路径失败 | “暂时没听清，但你仍可以从主题或人物开始。” |
| 创建对话 | “正在准备这次谈话…” |
| AI 等待 | “他在等你想一想” |
| AI 回复中 | “正在回应…” / “停止” |
| 消息失败 | “这句话没有送达。” / “重试” |
| 引用失败 | “暂时无法载入这条依据。” / “重试” |
| 记忆为空 | “还没有保存长期记忆。你可以随时决定让我们记住什么。” |
| 札记为空 | “认真谈过一次之后，札记会出现在这里。” |
| 札记保存 | “已自动保存” |
| 札记保存失败 | “已保存在本机，联网后继续同步。” |

Toast 文案短且可行动，不使用“Oops”。

---

# 十九、动效规范

所有动效必须尊重 `prefers-reduced-motion`。

| 元素 | 动效 | 参数 |
| --- | --- | --- |
| 人物卡 Hover | 上移 + 阴影 | `translateY(-4px)`，220ms |
| 立绘 | 轻微视差 | 最大 3px，不持续晃动 |
| 页面切换 | 淡入上移 | 12px → 0，300ms |
| 人物消息进入 | 纸张淡入 | opacity + 8px，260ms |
| 快捷回答 | Hover 上移 | 2px，140ms |
| 活动步骤 | 朱砂呼吸圈 | 1.8s，低透明度 |
| 等待圆点 | 三段透明度 | 1.2s stagger |
| 发送按钮 | Hover/Pressed | 轻光晕与 0.97 缩放 |
| 抽屉 | 桌面右滑、移动底部上滑 | 300ms |

禁止大幅缩放、弹跳、粒子、持续漂浮、强视差、霓虹光和游戏升级动画。

---

# 二十、无障碍、性能和安全

## 无障碍

- 正文与背景对比度至少达到 WCAG AA。
- 所有按钮、卡牌和标签支持键盘操作。
- Dialog/Sheet 打开后锁定焦点，关闭后焦点返回触发器。
- 图标按钮必须有 `aria-label`。
- 头像和立绘提供有意义的 alt；装饰纹样使用空 alt。
- 流式输出使用合适的 `aria-live`，避免每个 token 都被朗读。
- 不用颜色作为唯一状态标识。
- 触控目标至少 44px。

## 性能

- 首页首屏优先加载 3 张关键人物图，其余懒加载。
- 使用图片宽高属性防止布局偏移。
- 人物图生成 `srcset`，移动端不下载桌面大图。
- 纸纹和纹样尽量使用小纹理、CSS 或 SVG。
- 路由级代码拆分。
- 避免每个流式 token 导致整个聊天树重渲染。

## 安全与内容边界

- AI 输出按不可信内容渲染，Markdown 必须 sanitize。
- 前端不得暴露模型 Key、数据库 Key 或内部 Prompt。
- 人物不得宣称自己是真人或本人授权。
- 医疗、心理危机、法律、投资等高风险问题显示现实边界和求助入口。
- 不把产品包装为心理治疗或诊断。
- 资料引用可追溯，不伪造名言。
- 当代真人和网红配置上线开关与合规字段。

---

# 二十一、实现顺序

## Phase 0：审计和视觉基础

- 审计项目。
- 建立 Design Token、字体、背景、Header、Button、Chip、Card、Sheet。
- 整理人物数据和图片路径。

## Phase 1：首页与思想路径

- 完成人物发现、筛选、搜索和空状态。
- 完成困惑输入、线索提取、追问和推荐。

## Phase 2：人物详情与主动开场

- 完成人物详情、资料 Tab、开场预览和创建会话。

## Phase 3：正式聊天

- 完成消息状态机、流式适配、停止/重试、快捷回答和响应式布局。
- 完成资料和记忆抽屉。

## Phase 4：心语札记

- 完成列表、搜索、编辑、自动保存、继续交谈和导出。

## Phase 5：测试和视觉对齐

- 桌面 1440×960、移动 390×844/430×932 截图对比。
- 修复布局、溢出、字体、点击区域和异常状态。

每个 Phase 完成后运行测试和构建，不要把所有问题留到最后。

---

# 二十二、必须完成的测试

组件测试：

- 筛选组合和清空。
- 快捷回答写入输入框。
- 输入法合成时 Enter 不发送。
- 消息失败后重试不重复用户消息。
- 引用展开和抽屉关闭后的焦点恢复。
- 记忆暂停、编辑、删除。
- 札记防抖保存和离线草稿。

E2E 主链路：

```text
首页 → 输入困惑 → 选择追问回答 → 选择孔子 → 人物详情
→ 让孔子先开口 → 发送回答 → 查看资料 → 查看/管理记忆
→ 结束对话 → 生成札记 → 编辑补充 → 继续交谈
```

响应式检查 1440×960、1024×768、768×1024、430×932、390×844。确保无横向滚动、输入框不遮挡最后一条消息、抽屉不超出安全区。

---

# 二十三、量化验收标准

| 类别 | 标准 |
| --- | --- |
| 路由 | 7 个目标路由均可访问，旧链接有重定向或映射 |
| 主链路 | E2E 从首页到札记无阻断 |
| 视觉 | 颜色、字体、布局、卡牌、气泡与目标图保持同一系统 |
| 响应式 | 390px～1440px 无横向溢出和关键内容遮挡 |
| 状态 | 加载、空、失败、重试、停止、保存中均有界面 |
| 图片 | 所有人物卡无破图，有尺寸和懒加载策略 |
| 聊天 | 可发送、流式/模拟流式、停止、重试、快捷回答 |
| 引用 | 可展开，能区分原句、转述和 AI 综合 |
| 记忆 | 可查看、编辑、暂停、删除 |
| 札记 | 可生成、编辑、自动保存、继续对话、导出 |
| 无障碍 | 核心链路键盘可操作，主要文本达到 AA |
| 构建 | lint、typecheck、test、build 全部通过 |

---

# 二十四、Codex 最终交付格式

完成后必须给出：

1. 修改结果摘要。
2. 实际复用和新增的技术栈。
3. 路由与页面清单。
4. 关键组件清单。
5. Mock 与真实后端边界。
6. 环境变量示例，禁止包含真实密钥。
7. 运行命令和测试命令。
8. 已通过的测试和截图尺寸。
9. 未完成项、原因和下一步，不得隐瞒。
10. 关键文件路径。

不要只交一张首页，不要只改颜色，不要用静态图片冒充交互，不要在测试失败时声称完成。
