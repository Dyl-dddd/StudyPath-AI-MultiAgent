# StudyPath AI RAG 实现与验证记录

验证日期：2026-10-19  
范围：本轮新增的 RAG 后端、问答/资料库前端、公开样例文档和评测脚本。`2026-10-18-system-audit.md` 记录的是改造前状态。

## 已完成实现

- FastAPI + SQLite 账号、知识库、资料、分块、会话和引用存储；本地密码哈希与签名令牌。
- PDF、DOCX、TXT、Markdown 的文件校验和解析；有章节/页码元数据的重叠分块。
- FastEmbed `BAAI/bge-small-zh-v1.5` 生成 512 维向量，Qdrant 持久化；检索结果再次按账户与 READY 状态核验。
- OpenAI 兼容 SSE 生成接口、真实来源事件、原文预览和服务端会话存储。未配置 LLM 时明确报错，不回退到假答案。
- `/library` 与 `/chat` 提供登录、上传/索引状态、删除/重建、流式问答、引用预览、会话管理。

## 自动化结果

- `backend/.venv/Scripts/python -m pytest -q`：11 passed。
- `npm run typecheck`：通过。
- `backend/scripts/e2e_smoke.py first`：真实 PDF 解析、512 维嵌入、Qdrant 写入/检索、页码引用、重建索引、账户隔离和未配置 LLM 的 SSE 失败路径均通过。
- 在同一隔离集成数据库与向量目录下重启后端，再运行 `backend/scripts/e2e_smoke.py second`：SQLite/Qdrant 持久化、删除后不可检索和测试数据清理均通过。
- 前端生产构建：通过；Vite 输出写入系统临时目录 `studypath-rag-validation-build-20261019-5`，没有覆盖仓库既有 `dist/`。ECharts 相关压缩 JS chunk 超过 Vite 默认 500 kB 警告线。
- 本地运行检查：前端 `/`、`/chat`、`/library` HTTP 200；后端 `/api/health` 正常。Codex 内置浏览器拒绝访问 localhost，未能完成浏览器截图级目视检查。

集成测试使用 `backend/data/integration.sqlite` 与 `backend/data/integration-qdrant/` 隔离目录，不应将其当成用户资料库。

## 检索小样本结果与边界

36 条手工标注问题（34 条可回答、2 条无答案）只评估了向量召回：Recall@5 = 1.00、MRR@5 = 0.9088，Dense 检索延迟 P50 约 23 ms、P95 约 45 ms。无答案问题仍然各有检索候选；这不是回答正确率、拒答准确率或忠实度指标。当前没有可信的 Dense 分数阈值可将无答案样本与可回答样本区分，因此不可声称拒答安全已验证。

尝试下载并对比 `BAAI/bge-reranker-base` 时 Hugging Face 权重传输失败，模型未完整下载，本轮没有重排评测，也没有启用重排。需要在网络可用环境完成模型下载后再评估，并建立独立的拒答/答案忠实度人工评测。

## 尚未验证的能力

- 未配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。未向任何模型服务发送资料或发起计费请求，无法证明生成答案质量、SSE token 流或真实模型拒答行为。用户配置获授权的服务商后才能完成该阶段。
- 扫描 PDF OCR、Hybrid/BM25、已下载的 CrossEncoder reranker、生产级账号安全与数据库迁移尚未完成。
- 非 `/library`、`/chat` 的学习页面仍是演示数据，不使用本轮 RAG 后端。

## 复现

参见根目录 `README.md` 的 Windows 本地启动、环境变量和测试说明。运行真实 HTTP 集成测试前，需在专用测试配置下启动后端；测试会建立并清理专用测试账户和知识库。

## 2026-10-19 后续整改复测

- `BAAI/bge-reranker-base` 已完整下载至本机 FastEmbed 缓存，并通过中文相关性排序冒烟验证。默认本地后端已启用 Cross-Encoder 与实测门槛 `RERANKER_MIN_SCORE=-1.002625`。
- 在隔离数据库/向量目录中，对 56 条问题进行真实 `dense+rerank` 复测：34 个可回答问题保留 33 个证据（97.06%）；22 个无答案问题拦截 21 个（95.45%）。分切分结果为：课程内校准集无答案 2/2 拒答、可回答 33/34 保留；20 个域外留出无答案 19/20 拒答。Recall@5 与 MRR@5 均为 0.9706；P50/P95 检索耗时约 2.93/3.11 秒。报告位于 `backend/evaluation/results/reranker-gated-20261019-final.json`。
- 拒答通过空引用证据确认，且在 E2E 中验证 SSE 返回确定性无证据答复、不调用 LLM；这不是自然语言模型拒答准确度评测。当前 LLM 未配置，生成答案正确性、忠实度及拒答措辞仍需在授权模型配置后人工评审。留出集仍有 1/20 域外问题被保留，不能将此小样本结果解释为普遍安全保证。
- 门槛启用时，存在候选但 reranker 不可用会失败关闭；无候选则直接安全拒答。该空集合边界由 E2E 删除文档路径和单元测试覆盖。
- 后端 `pytest -q`：14 passed，1 条 Starlette/httpx 弃用告警。两阶段 E2E 通过：文档解析/重建、引用预览、账号隔离、门控拒答、无 LLM 时不伪造回答，以及 SQLite/Qdrant 跨重启持久化与删除后不可检索。
- `npm run typecheck` 通过。Windows 模块路径规范化修复了 Rollup 手动分包条件；最终 Vite 生产构建无 500 kB chunk 警告：ECharts 383.11 kB、zrender 174.35 kB、主 JS chunk 184.84/105.67 kB、CSS 112.26 kB。构建产物输出至系统临时目录。
- Codex 内置浏览器仍对 localhost 报 `ERR_BLOCKED_BY_CLIENT`，这是当前内置浏览器策略限制。使用本机 Chrome headless 对 `/`、`/chat` 和 `/library` 生成截图并完成页面级检查，开发服务返回 HTTP 200；应用本身可访问。
