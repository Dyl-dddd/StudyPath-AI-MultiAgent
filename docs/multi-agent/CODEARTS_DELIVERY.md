# CodeArts 研发与交付配置

CodeArts 用于代码协作、检查、构建、测试、制品和部署；在线学习请求仍由 StudyPath 的 FastAPI 调度与业务 Agent 处理。CodeArts 不承担模型推理或 AgentHarness 运行时职责。

华为云官方产品说明将 CodeArts 描述为覆盖代码托管、流水线、代码检查、编译构建、测试计划、部署及制品管理的一站式交付平台。官方快速入门中，CCE/SWR/集群等资源是该部署路径的先决条件；本仓库不创建云资源，也不假设当前账号已开通这些服务。具体界面及服务权限以部署地区和账号实际可用服务为准。

## 仓库与分支

1. 在 CodeArts Repo 导入本目录副本的 Git 仓库，设定受保护的 `main` 分支；开发分支通过 Pull Request 合并。
2. `.gitignore` 已排除 `.env`、上传/向量/数据库数据、构建产物和 Python 缓存。只提交 `backend/.env.example`，不提交任何 `.env`、用户数据、模型缓存或评测个人数据。
3. 配置代码评审至少检查：用户 ID 过滤、课程管理员授权、RAG 证据拒答、密钥位置与迁移向后兼容性。

## 建议流水线阶段

| 顺序 | CodeArts 服务 | 配置内容 / 命令 | 成功条件 |
|---|---|---|---|
| 1 | CodeArts Pipeline / Repo | 触发条件为 PR 和主分支合并；来源 Repo；设定 Node 22、Python 3.12 构建镜像 | 源码检出完成 |
| 2 | CodeArts Check | 执行前端静态检查；Python 使用项目的类型/静态检查器（如团队启用 Ruff/Mypy，应先纳入依赖锁定） | 检查报告无阻断项 |
| 3 | CodeArts Build | `npm ci`、`npm run typecheck`、`npm run build`；Python 安装 `backend/requirements.txt` 后从 `backend` 执行 `python -m pytest -q` | 前端构建及后端测试通过 |
| 4 | TestPlan | 将 `backend/tests` 中隔离 API、资料隔离、拒答、Agent 路由、权限、输入校验和错误处理测试映射到测试计划 | 用例有通过/失败记录 |
| 5 | CodeArts Build + 制品仓库 | 打包前端静态制品与后端容器镜像；版本标记为提交 SHA/发行标签；制品不可包含 `.env` 或 `backend/data` | 制品可追溯到 Repo 提交 |
| 6 | CodeArts Deploy（可选） | 按实际已有环境选择主机或容器部署；部署变量从受控凭证库读取；健康检查 `/api/health` | 服务就绪且回滚版本可用 |
| 7 | CodeArts Pipeline | 汇总 Check、Build、TestPlan、制品和可选部署结果；失败时阻止向后阶段推进 | Pipeline 报告可审计 |

`deploy/` 提供 Dockerfile、compose 与 Nginx 配置，可作为 Build 的容器构建输入。`backend/.env` 只在开发人员或生产部署密钥存储中单独配置。CodeArts 的敏感流水线变量不得通过 `echo`、命令参数、前端构建参数或 artifact manifest 打印/打包。

## 云部署参数

仓库未选定云区域、ECS/CCE、SWR 组织、域名、TLS 证书、数据库或备份服务。这些值由部署者按实际账号与预算填写。容器部署至少持久化 `/app/data`（SQLite、Qdrant、上传原件和本机签名密钥）；正式多副本部署应迁移 PostgreSQL 与远程 Qdrant，并使用反向代理 HTTPS、加密备份和单独密钥管理。

## 官方资料

- [CodeArts 产品介绍](https://support.huaweicloud.com/intl/zh-cn/ally-visitor-1-usermanual-codearts/devcloud_pdtd_00001.html)
- [CodeArts 快速搭建流水线（CCE 示例及其云资源前提）](https://support.huaweicloud.com/intl/zh-cn/qs-devcloud/devcloud_qs_0002.html)
- [DeepSeek API 兼容接口与配置说明](https://api-docs.deepseek.com/quick_start/agent_integrations/)

