# 本地启动与演示流程

## 本地运行

1. 安装 Node.js 20.19+/22.12+ 和 Python 3.12。
2. 复制 `backend/.env.example` 为 `backend/.env`。只在后端配置获授权的 OpenAI 兼容服务 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`；密钥不得放入前端环境变量。没有模型密钥时，模型助教和错题变式会明确报未配置/调用失败，画像和图谱仍可基于真实记录分析。
3. 安装依赖：根目录 `npm ci`；后端创建虚拟环境并运行 `python -m pip install -r requirements.txt`。
4. 启动后端：在 `backend` 执行 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。
5. 启动前端：根目录运行 `npm run dev`。使用 `VITE_USE_MOCK=false` 的真实 API 模式；不把服务端凭证写入 `VITE_*`。
6. 容器演示可用 `docker compose -f compose.yaml up --build`，浏览器访问 `http://localhost:8080`。首次检索会按现有配置初始化/下载 Embedding 和重排模型，需预留磁盘空间及网络。

## 演示脚本

1. 注册两个测试学生账号，分别建个人资料库，验证对方资料和问答不可见。
2. 为学生 A 设置学段/年级、学习学科、目标与可用时长；解释这些字段可跳过、修改。
3. 上传 A 的课程讲义，等文档 READY；进入 `/chat` 选择“本地资料库”，问文档内有答案的问题，演示 SSE 增量和引用原文；再问无证据问题，演示拒答。
4. 进入“AI 多智能体学习”，分别查看画像建议、课程图谱先修解释和通用大模型回答。面向模型的内容使用对应服务；无模型配置时展示真实错误提示。
5. 完成一份测验产生真实错题，从“错题举一反三”生成三道新情境练习，先作答再由服务端判分；验证未提交前没有答案且掌握度不变。
6. 手动编辑学习计划，查看测验/错题记录如何形成画像建议；确认 Agent 不擅自写计划。
7. 展示 AgentHarness 状态：API 身份/URL/协议/Agent ID 未核验时必须显示 `configured_unverified` 或 `not_configured`，不得声称已连接。

## 自动化检查

后端：`python -m pytest -q`（在 `backend` 且使用副本 `.venv`）。
前端：`npm run typecheck` 与 `npm run build`（副本根目录）。

