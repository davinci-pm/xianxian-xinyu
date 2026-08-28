# 高星人物 Skills 与本地 RAG 扩展记录

更新日期：2026-08-27

## 1. 本次范围

在原有 4 个人物基础上新增 15 个可对话人物，形成 19 张人物卡。候选来源首先参考 GitHub 人物 Skill 合集 `momozi1996/awesome-ai-persona-skills`，再按独立仓库实际 Star、许可证、文件完整度和产品适配度逐个复核。

每个入选仓库执行以下处理：

1. 验证 GitHub 来源、默认分支、MIT 许可证和最新提交。
2. 使用 Skill Installer 按提交 SHA 完整安装至 `skills/upstream/<skill>`。
3. 在 `skills/upstream/ALLOWLIST.yaml` 记录来源、提交、Star 快照和权限。
4. Skill Adapter 只读原版 `SKILL.md`，拒绝执行仓库脚本。
5. 仓库内全部 Markdown 导入 SQLite，生成本地 BGE 向量。
6. 对话时以中文 BM25、向量余弦和 RRF 融合召回最多 4 个片段。
7. 活着的公众人物统一增加“非本人、非授权、非专业建议”提示。

## 2. 已接入清单

| 人物/方法 | GitHub 仓库 | Star 快照 | 许可证 | 固定提交前 8 位 |
| --- | --- | ---: | --- | --- |
| 张雪峰视角 | `alchaincyf/zhangxuefeng-skill` | 10,200 | MIT | `3501b1e6` |
| 毛选方法 | `leezythu/maoxuan-skill` | 1,074 | MIT | `4376a650` |
| 史蒂夫·乔布斯视角 | `alchaincyf/steve-jobs-skill` | 936 | MIT | `8ae40e10` |
| 埃隆·马斯克视角 | `alchaincyf/elon-musk-skill` | 494 | MIT | `b5dad76f` |
| 查理·芒格视角 | `alchaincyf/munger-skill` | 350 | MIT | `12d582ce` |
| 新青年实践方法 | `SamadhiFire/xinqingnian-maoxuan-skill` | 319 | MIT | `4382484d` |
| 安德烈·卡帕西视角 | `alchaincyf/karpathy-skill` | 296 | MIT | `0b10e859` |
| 理查德·费曼视角 | `alchaincyf/feynman-skill` | 257 | MIT | `3ec26652` |
| 纳瓦尔视角 | `alchaincyf/naval-skill` | 238 | MIT | `0de29b12` |
| 张一鸣视角 | `alchaincyf/zhang-yiming-skill` | 163 | MIT | `db80fcc0` |
| 纳西姆·塔勒布视角 | `alchaincyf/taleb-skill` | 117 | MIT | `69d58a00` |
| MrBeast 创作视角 | `alchaincyf/mrbeast-skill` | 106 | MIT | `f63f0c5d` |
| 毛泽东战略方法 | `wwwaapplleecu-source/mao-skill` | 103 | MIT | `b6b39634` |
| 保罗·格雷厄姆视角 | `alchaincyf/paul-graham-skill` | 92 | MIT | `e6ed220c` |
| 伊利亚·苏茨克维视角 | `alchaincyf/ilya-sutskever-skill` | 47 | MIT | `4829975a` |

Star 是 2026-08-27 的检索快照，只作为候选排序信号，不代表内容准确性或官方授权。

## 3. 导入结果

- 新增人物：15
- 完整安装的上游仓库：15
- 新增 Markdown 文档：250
- 新增知识分块：9,915
- 已生成本地向量：9,915 / 9,915
- 向量模型：`BAAI/bge-small-zh-v1.5`
- 最终卡牌数：19

## 4. 权限与能力边界

- “完整安装”表示上游仓库文件完整保存在项目中，不表示自动信任或执行其中所有程序。
- 当前产品复刻的是人物对话能力：原版 Skill 指令、表达方法、知识资料、主动对话、记忆和引用。
- 上游 CLI、抓取器、浏览器自动化、测试脚本和系统命令不会运行；它们需要独立安全审计后才能单项开放。
- 完整语料和向量保存在本机；本轮召回的最多 4 个片段会发送给当前生成模型 DeepSeek。
- MIT 许可证只证明仓库作者以 MIT 发布仓库内容，不自动证明其中引用的所有第三方材料已获得重新授权。正式商业发布前仍需逐文档版权复核。

## 5. 与冻结 PRD 的差异

冻结 PRD 原计划测试版展示约 30 人、第一阶段重点跑通 3 人。本次根据产品负责人新指令，当前本地版本提前扩展为 19 个可聊天人物，其中 16 个外部 Skill 人物已接入本地 RAG。该变化增加了模型成本、内容审核量、公众人物合规工作和首页信息密度；正式发布名单仍应在上线前重新冻结。
