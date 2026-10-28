# 多智能体升级验收记录

## 已执行检查

| 检查 | 结果 |
|---|---|
| `python -m pytest -q`（`backend` 目录） | 24 passed，2 skipped；跳过项为当前环境未启用/未安装 OCR 的检查 |
| `python -m compileall -q app tests migrations`（`backend` 目录） | 通过 |
| `npm run typecheck`（项目根目录） | 通过 |
| `npm run build`（项目根目录） | 通过，Vite 生产构建成功 |
| `npm ci` | 安装成功；npm 提示 1 项低危、1 项中危依赖审计告警，本次未强制升级依赖 |
| `compose.yaml` YAML 解析 | 通过 |
| `alembic history` | 通过；`0010_profile_learning_context` 接在 `0009_chat_answer_modes` 后 |
| Docker Compose 容器构建/启动 | 未执行：当前机器没有 Docker CLI |

## 交付能力

- 新增 `/api/agents` 认证 API：健康状态、意图路由、只读画像/图谱并行分析和结构化部分成功结果。
- 提供五个业务角色：画像分析、错题迁移练习、课程资料问答、通用模型助教、知识图谱分析；复用现有 RAG、错题提交判分、用户数据和图谱接口。
- 多智能体页面加入错题练习作答、服务端判分与解析、画像补充入口、错误/空数据状态；资料库问答跳转到原有流式 `/chat` 页面。
- 用户画像新增学段、学科和学习目标迁移；失败重试仅用于只读分析与通用助教，避免对有写入副作用的任务重复提交。
- 新增容器化配置、CodeArts 交付流程说明、本地运行与演示脚本、架构/隐私边界及实施清单。

## 外部依赖和未完成项

- AgentHarness 仅检查服务端配置状态。仓库和当前材料没有可核验的产品 Base URL、协议、认证契约及 Agent ID，因此远端执行保持关闭；需要部署方提供并验证正式接口文档后才能启用。密钥未复制或回显。
- 生产模型问答与变式题生成需要在副本 `backend/.env` 中填写获授权的 OpenAI 兼容服务配置；模型未配置或不可用时返回明确失败，不使用 Mock。
- CodeArts 仓库、流水线、制品及云部署资源尚未关联到任何云账号；按说明在目标账号实际配置。未声称已发布。
- Docker 未安装，因此这里只验证 Compose YAML 可解析，未声称容器镜像已构建或服务已容器启动。
- 当前本地 RAG 流式问答沿用原 `/chat` 的 SSE 实现；多智能体页面通过入口链接到该页面。`/api/agents/run` 的 `local_qa` 适配器是 JSON 请求/响应，不替代现有 SSE 流。

## 2026-10-26 并行调度增量

- 多智能体页面新增“画像 + 图谱综合分析”入口，实际调用只读并行接口；画像和图谱子任务仍各自返回依据，页面分别展示可调整建议与先修关系。
- `POST /api/agents/run/parallel` 新增 `merged` 字段，含画像结果、图谱结果和子任务错误；总状态在全部成功、部分完成、全部失败时分别返回 `completed`、`partial`、`failed`。
- 回归检查：`npm run typecheck` 通过；`npm run build` 通过；后端 `python -m pytest -q` 为 25 passed、2 skipped。跳过项仍是 OCR 环境未启用的检查。
