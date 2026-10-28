# 智学研途 · StudyPath AI

Vue 3 学习工作台，带独立 FastAPI RAG 服务。**AI 答疑和资料库使用真实服务端处理；学习总览、课程、测验、路径、图谱、计划等其他模块仍是原有演示数据。** RAG 页面不会在服务失败时切回 Mock 回复。

## 当前实现

- 账号注册/登录，密码以 PBKDF2 派生哈希保存；后端以账号 ID 隔离知识库、文档、会话和向量检索。注册、登录带数据库支持的 IP 与账号/IP 窗口限流。
- 知识库新建、重命名、按课程归类和删除。
- PDF、DOCX、TXT、Markdown 多部分上传，扩展名/MIME/内容检查、20 MB 限制、SHA-256 去重和安全文件名。
- PyMuPDF 按 PDF 页提取原文；DOCX 按段落、标题与表格顺序提取；TXT/Markdown 支持 UTF-8 和 GB18030。启用 `OCR_ENABLED` 并安装 Tesseract 及语言包后，可对扫描 PDF 页面和 DOCX 内嵌图片 OCR。
- 标题/段落感知递归分块，保存稳定 Chunk ID、内容哈希、页码、章节和估算 token 数。
- FastEmbed 在 CPU 上运行 `BAAI/bge-small-zh-v1.5` 的 Qdrant ONNX 模型；实际向量维度在运行时读取，目前模型元数据为 512 维。Qdrant 本地持久化模式或远程 Qdrant 可选。
- Dense Qdrant 检索先按账号与知识库过滤，再由 SQL 记录核验 READY 状态及归属。FastEmbed `BAAI/bge-reranker-base` Cross-Encoder 对候选重排；本地默认 `RERANKER_MIN_SCORE=-1.002625`，低于校准门槛时返回确定性无证据答复、不调用 LLM。门槛开启后若重排模型不可用，则失败关闭，避免绕过证据门控。
- OpenAI 兼容 Chat Completions API、真实 token SSE、历史会话、引用编号清理、原文片段与页码预览。LLM 未配置或调用失败会返回错误，不产生替代答案。
- Markdown 使用 `html:false` 渲染，代码块和 KaTeX 数学公式可显示。文档片段会发送到 `.env` 指定的模型服务；不要上传未获授权的敏感材料。
- `/agents` 提供服务端调度入口和学习画像、错题变式、本地资料问答、通用模型助教、课程图谱分析五条受限角色路径；既有 RAG/SSE 与错题提交/服务端判分沿用原实现。画像建议标明真实记录依据；计划不会被智能体擅自修改。
- 个人设置支持学段（小学/初中/高中/大学/其他）、年级、学习学科和目标。题目讲解和变式提示按学段适配。新字段通过 `0010_profile_learning_context` 向后兼容迁移。
- AgentHarness 仅提供配置状态边界。由于仓库没有 SDK/API 契约，而 `AGENTHARNESS_API` 不能单独确认厂商、Base URL、协议或 Agent ID，不会假装已接通或把该凭证发送给其他模型。

## 环境要求

- Node.js 20.19+ 或 22.12+。
- Python 3.12（Windows 本机已验证）。
- 初次索引会下载约 90 MB 中文 ONNX Embedding 模型；重排还会下载约 1.1 GB 的 Cross-Encoder ONNX 模型。开发态 Qdrant 与 SQLite 不需要 Docker。
- 使用受信任的 OpenAI 兼容 LLM 服务，并配置其 URL、密钥和模型名。API key 只保存在后端 `backend/.env`，不要放入前端 `.env`。

## 启动

在仓库根目录安装前端依赖，并启动 Vite：

```powershell
npm install
npm run dev
```

另开终端启动后端：

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env：配置 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL；密钥只写在此文件。
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端默认连接 `http://localhost:8000/api`。也可以在仓库根目录 `.env.local` 设置 `VITE_RAG_API_BASE_URL`。后端 Swagger 页面：`http://127.0.0.1:8000/docs`。

### LLM 配置

在 `backend/.env` 设置服务商给出的 OpenAI 兼容 Chat Completions 地址（常见路径以 `/v1` 结束）、服务端 API key 和该服务商支持的聊天模型 ID：

```env
LLM_BASE_URL=https://<provider-host>/v1
LLM_API_KEY=<provider-secret>
LLM_MODEL=<provider-chat-model>
```

项目不猜测服务商或模型，也不会自动使用本机其他环境变量中的密钥。运行 `GET /api/health` 只检查是否具备三项配置，不返回密钥。LLM 服务商接收被检索到的课程片段；请先确认数据处理授权。

### Qdrant 配置

默认 `QDRANT_URL` 留空，向量库落在 `backend/data/qdrant`。也可以指定 `QDRANT_LOCAL_PATH`。远程服务设置 `QDRANT_URL` 与 `QDRANT_API_KEY`，确认备份、TLS 与网络访问策略。远程 Qdrant 与本地模式使用同一集合；集合模型维度不匹配时服务报错并保留原数据，不会自动删除或重建集合。嵌入模型变更需新集合并经备份后迁移。

## 第一次验证真实 RAG

1. 在 `/library` 注册/登录。
2. 新建“操作系统基础”知识库。
3. 上传 `backend/examples/operating_systems_sample.md` 或自己的 PDF/DOCX/TXT/Markdown。
4. 等待状态从“已上传 → 解析 → 分块 → 向量化 → 写入向量库”变为“已就绪”。
5. 在 `/chat` 选择该知识库，问“进程和线程分别共享什么？”；右侧显示真实检索片段。点击来源查看保存的原文片段和页码。
6. 删除文档后再次检索，服务端会先删 Qdrant 点；SQL 状态核验也会排除非 READY 文档。

扫描件 OCR 配置见 [backend/OPERATIONS.md](backend/OPERATIONS.md)。默认关闭 OCR；PDF OCR 仅处理几乎没有可提取文本且包含图像的页面，DOCX OCR 处理内嵌图片，并受页数、图像大小和超时限制。

## API

所有 `/api` 除 `/health` 外的接口需要 `Authorization: Bearer <token>`。

| 接口 | 用途 |
| --- | --- |
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `DELETE /auth/me` | 账号与数据删除 |
| `GET/POST /knowledge-bases`, `GET/PATCH/DELETE /knowledge-bases/{id}` | 知识库管理 |
| `POST /knowledge-bases/{id}/documents`, `GET /knowledge-bases/{id}/documents` | 上传、列出文档 |
| `GET /documents/{id}/status`, `POST /documents/{id}/reindex`, `DELETE /documents/{id}` | 状态、重建、删除 |
| `GET /documents/{id}/preview`, `GET /documents/{id}/file` | 原文与文件预览/下载 |
| `POST /rag/sessions`, `GET /rag/sessions`, `GET /rag/sessions/{id}/messages`, `PATCH/DELETE /rag/sessions/{id}` | 会话管理 |
| `POST /rag/retrieve`, `POST /rag/chat`, `POST /rag/chat/stream` | 检索调试、问答和 SSE 问答 |
| `GET /agents/health`, `POST /agents/run`, `POST /agents/run/parallel` | 已登录用户的智能体状态、单任务调度和只读画像/图谱并行分析；并行响应含 `results` 与合并的 `merged`，总状态区分 `completed`、`partial`、`failed` |

SSE 事件为 `citations`（来自真实检索的片段）、`delta`（模型文本增量）、`done`（最终答案与检索模式）、`error`（真实请求失败）。中断连接不会保存未完成轮次。

文档状态：`UPLOADED`、`PARSING`、`CHUNKING`、`EMBEDDING`、`INDEXING`、`READY`、`FAILED`。模型引用号只保留当前证据集合中的编号；UI 匹配分显示为检索分数，不作为正确率。

## 测试与评测

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

单元和 API 隔离测试不覆盖真实 LLM 质量。`evaluation/questions.jsonl` 有 56 个带章节、参考答案与无答案标签的问题：34 个课程内可回答校准问题、2 个课程内无答案校准问题、20 个域外无答案留出问题。启动真实服务后可运行：

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_rag.py --username <已有用户名> --password <密码>
```

脚本会上传内置公开样例、测量 Dense+Rerank 的 Recall@5、MRR、按 split 统计的证据保留/拒答率与实际检索延迟，并创建一个不覆盖既有结果的 JSON 报告。当前门槛在课程内样本保留 33/34 个可回答证据，并在留出集拒绝 19/20 个域外问题。这是小样本检索证据门控结果，不代表任意问题都能安全拒答，也不覆盖真实 LLM 回答 Faithfulness/Correctness；生成质量仍需配置获授权模型并人工评审。脚本会删除自身测试知识库及向量。评测运行前先确认服务使用的是预期测试数据库。

## 持久化、备份与恢复

- `backend/data/studypath.db`：账号、知识库、文档状态、文本块、会话和引用关系（可由 `DATABASE_URL` 指向 PostgreSQL）。
- `backend/data/qdrant/`：默认本地持久化向量库（或配置远程 Qdrant）。
- `backend/data/uploads/<user-id>/`：上传原件。`backend/data/auth.secret`：自动生成的本地签名密钥。
- FastEmbed 模型缓存由本机 Hugging Face/FastEmbed 缓存目录管理。

启动时通过 Alembic 执行数据库迁移；旧版数据库会先标记为基线，再应用后续增量迁移。备份与恢复脚本及 PostgreSQL/远程 Qdrant 注意事项见 [backend/OPERATIONS.md](backend/OPERATIONS.md)。恢复时停止服务，恢复数据库、上传原件、向量快照及相同向量模型配置，再启动服务。不要在服务运行时复制本地 Qdrant 数据库。

## 已知边界

- Dense RAG、真实文档处理、Qdrant 存取、来源定位与账号隔离已实现；本机资源允许的轻量中文模型已下载并在本地运行验证。索引任务写入数据库队列，由单进程后台 worker 处理。
- 实际聊天需要你提供兼容服务商的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。模型/密钥未配置时接口明确失败，不返回 Mock。
- 本机已下载并启用 Cross-Encoder 重排与基于校准分数的拒答门槛。Hybrid/BM25、知识图谱证据联动和 PDF 版面坐标高亮尚未实现；OCR 需要按 `backend/OPERATIONS.md` 安装语言包并用实际扫描材料验收。
- 当前账号服务提供本地密码登录及注册/登录限流，不包含邮件验证、密码找回和企业 SSO；正式部署前仍需接入成熟身份服务，并通过 HTTPS 反向代理、备份加密和上传限流保护服务。
- 测验、错题与学习路径使用账号 API 保存。个性化路径由课程图谱先修关系、知识点掌握度和到期错题生成；课程内容管理员可在 `/admin/curriculum` 维护课程、知识节点、关系与题目（需登录并配置 `CONTENT_ADMIN_TOKEN`）。
- 当前练习题仍来自课程题库，不等于用户资料的 RAG 检索结果。用户上传资料与知识点/练习题之间的证据关联、LLM 学习诊断仍待实现；课程内容和学习统计以已接入的账号 API 数据为准，空数据会显示空状态。
# 学习空间数据接口

学习空间的个人数据由 FastAPI 账号接口持久化。首次启动时 Alembic 会应用 `0003_learning_workspace`，并将 `backend/app/learning_catalog.json` 中的课程、知识点关系和题目导入数据库；目录记录可由后端维护，用户的个人记录按 `user_id` 隔离。

新增的认证接口均需携带 `Authorization: Bearer <access_token>`：

- `GET/PATCH /api/profile`：个人资料、学习偏好及课程收藏。
- `GET /api/courses`、`GET /api/courses/{course_id}/graph`：课程目录、知识节点和关系。
- `GET /api/quizzes`：题库；`POST/GET /api/quiz-attempts`：提交并读取服务端判分的测验记录。
- `GET/PUT /api/mistakes`：读取及同步当前账号错题。
- `GET/PUT /api/study-plans`：读取及保存当前账号学习计划。
- `GET /api/dashboard`：从账号测验、错题和计划聚合学习统计。

本地前端默认连接 `http://localhost:8000/api` 并关闭 Mock。启动 FastAPI 后，页面会先显示账号登录/注册入口；迁移旧浏览器中的个人资料、偏好和学习计划后会清除对应本地副本。
