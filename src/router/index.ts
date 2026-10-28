import { createRouter, createWebHistory } from 'vue-router'

export const navItems = [
  { group: '学习空间', items: [{ label: '学习总览', path: '/', icon: 'LayoutDashboard' }, { label: 'V2 首页预览', path: '/v2', icon: 'Sparkles' }, { label: 'AI 智能答疑', path: '/chat', icon: 'MessagesSquare' }, { label: 'AI 多智能体学习', path: '/agents', icon: 'Sparkles' }, { label: '课程知识图谱', path: '/graph', icon: 'Network' }, { label: '我的课程', path: '/courses', icon: 'BookOpen' }, { label: '学习资料库', path: '/library', icon: 'FolderOpen' }] },
  { group: '智能学习', items: [{ label: '个性化学习路径', path: '/path', icon: 'Route' }, { label: '智能练习与测验', path: '/quiz', icon: 'ClipboardCheck' }, { label: '学习数据分析', path: '/analytics', icon: 'ChartNoAxesCombined' }, { label: '错题本', path: '/mistakes', icon: 'NotebookPen' }] },
  { group: '个人中心', items: [{ label: '我的学习计划', path: '/plan', icon: 'CalendarDays' }, { label: '个人设置', path: '/settings', icon: 'Settings2' }, { label: '课程内容维护', path: '/admin/curriculum', icon: 'Settings2' }] },
]

export default createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: () => import('../views/DashboardView.vue'), meta: { title: '学习总览' } },
  { path: '/v2', component: () => import('../views/DashboardV2View.vue'), meta: { title: 'V2 首页预览' } },
  { path: '/admin/curriculum', component: () => import('../views/ContentAdminView.vue'), meta: { title: '课程内容维护', section: 'admin-curriculum' } },
  { path: '/mistake-practice/:questionId', component: () => import('../views/MistakePracticeView.vue'), meta: { title: '举一反三练习', section: 'mistake-practice' } },
  { path: '/agents', component: () => import('../views/AgentLearningView.vue'), meta: { title: 'AI 多智能体学习', section: 'agents' } },
  ...navItems.flatMap((group) => group.items.filter((item) => item.path !== '/' && item.path !== '/agents').map((item) => ({ path: item.path, component: item.path === '/chat' ? () => import('../views/RagChatView.vue') : item.path === '/library' ? () => import('../views/RagLibraryView.vue') : () => import('../views/WorkspaceView.vue'), meta: { title: item.label, section: item.path.slice(1) } }))),
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
