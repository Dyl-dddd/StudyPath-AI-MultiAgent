# 学习功能 API

所有 `/api` 接口需要登录并携带 `Authorization: Bearer <token>`。

## 学习记录和进度

- `POST /api/study-sessions`：开始一次计时，可传 `{"course_id":"ds"}`。
- `GET /api/study-sessions/active`：恢复当前账号正在进行的计时。
- `POST /api/study-sessions/{id}/finish`：结束计时；时长由服务端起止时间计算。
- `GET /api/analytics?days=30`：返回按日汇总的学习时长。
- `GET/PATCH /api/me/courses/{course_id}/progress`：读取或更新 0–100 的课程进度及最近知识点。
- `PUT /api/knowledge-mastery`：传 `{"node_id":"bst","mastery":80}` 更新当前账号的知识点掌握度。客观题提交也会调整相关知识点掌握度。
- `GET /api/me/courses/{course_id}/learning-path`：根据当前账号未掌握的概念、图谱先修关系和错题复习状态生成学习步骤，并返回课程概念掌握进度。
- `GET/PUT/DELETE /api/me/courses/{course_id}/knowledge-base`：查看、绑定或解除当前账号课程的个人资料库。通过 `POST /api/rag/sessions` 传 `course_id` 创建课程范围的对话。

## 测验和错题

- `GET /api/quizzes?course_id=ds` 只返回题目和选项，不含答案与解析。
- `POST /api/quiz-attempts` 服务端判分并返回每题正确性、答案和解析；答案仅在提交后返回。
- `GET /api/quiz-attempts/{id}` 读取本人测验详情。
- `PATCH /api/mistakes/{question_id}` 更新收藏、掌握状态、复习时间或错因。
- `POST /api/mistakes/{question_id}/review` 提交一次复习结果；`DELETE /api/mistakes/{question_id}` 删除个人错题。
- `POST /api/mistakes/{question_id}/variants` 为本人错题生成 3 道不同情境的同考点单选题；生成服务依赖 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`。答案保存在服务端，提交 `POST /api/mistakes/{question_id}/variants/{set_id}/submit` 后才返回判分和解析。

## 反馈和提醒

- `PUT /api/rag/messages/{message_id}/feedback` 评价本人答疑消息：`{"rating":"helpful","comment":""}`。
- `GET /api/notifications`、`POST /api/notifications/{id}/read`、`POST /api/notifications/read-all` 管理账号提醒。测验完成及至少 5 分钟的专注计时会按个人提醒开关生成站内通知。

## 课程内容维护

现有 `GET /api/courses`、`GET /api/courses/{course_id}/graph`、`GET /api/quizzes` 提供学员侧内容读取。管理读取为 `GET /api/admin/courses/{course_id}/graph` 和 `GET /api/admin/questions?course_id=...`（包括答案）；写入接口为 `POST/PATCH/DELETE /api/admin/courses`、课程下 `/nodes` 和 `/edges`，以及 `POST/PATCH/DELETE /api/admin/questions`。

课程内容接口要求当前登录账号在服务端 `CONTENT_ADMIN_USERNAMES` 名单中，并额外设置 `CONTENT_ADMIN_TOKEN`，请求附带 `X-Content-Admin-Token`。用户名以逗号分隔，例如 `CONTENT_ADMIN_USERNAMES=teacher01,admin02`。`/api/auth/me` 会返回账号角色，普通用户不能访问课程维护接口。管理令牌只应由管理员输入并保存在可信的管理服务端，不能编译进公开前端包。
