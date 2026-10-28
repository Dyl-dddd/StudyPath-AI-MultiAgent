<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, ChevronDown, Command, Search, Sparkles, Menu, X, LayoutDashboard, MessagesSquare, Network, BookOpen, FolderOpen, Route, ClipboardCheck, ChartNoAxesCombined, NotebookPen, CalendarDays, Settings2, ChevronRight } from 'lucide-vue-next'
import { navItems } from './router'
import { useStudyStore } from './stores/study'
import { profileState } from './stores/profile'
import { loadProfile } from './stores/profile'
import { loadPreferences } from './stores/preferences'
import { authState, ragRequest } from './rag/api'
import { USE_MOCK } from './api/client'
import RagAuthGate from './components/RagAuthGate.vue'
import { studyApi } from './api'

const route = useRoute(); const router = useRouter(); const store = useStudyStore()
const sidebarOpen = ref(false); const searchOpen = ref(false); const query = ref('')
const isAdmin = ref(false)
const moreExpanded = ref(false)
const notificationsOpen=ref(false); const notifications=ref<Array<{id:number;title:string;body:string;read:boolean;createdAt:string}>>([])
const authenticated = ref(USE_MOCK)
const iconMap: Record<string, object> = { LayoutDashboard, Sparkles, MessagesSquare, Network, BookOpen, FolderOpen, Route, ClipboardCheck, ChartNoAxesCombined, NotebookPen, CalendarDays, Settings2 }
const title = () => String(route.meta.title || '学习总览')
const filtered = () => navItems.flatMap(group => group.items).filter(item => item.label.includes(query.value) && (item.path !== '/admin/curriculum' || isAdmin.value))
const secondaryItems = computed(() => navItems.slice(1).flatMap(group => group.items))
const goalDone = computed(() => store.tasks.filter(task => task.done).length)
const goalProgress = computed(() => store.tasks.length ? Math.round(goalDone.value / store.tasks.length * 100) : 0)
async function initializeAccount() {
  try {
    const account = await ragRequest<{ role?: string }>('/auth/me')
    isAdmin.value = account.role === 'admin'
    await Promise.all([loadProfile(), loadPreferences(), store.loadTasks()])
    await refreshNotifications()
    authenticated.value = true
  } catch (error) {
    authenticated.value = false
    console.error('学习空间数据加载失败', error)
  }
}
async function refreshNotifications(){if(USE_MOCK)return;try{notifications.value=await studyApi.notifications()}catch(error){console.error('学习提醒加载失败',error)}}
function expireAuth() { isAdmin.value = false; authenticated.value = USE_MOCK }
onMounted(async () => {
  window.addEventListener('studypath:auth-expired', expireAuth)
  window.addEventListener('studypath:notifications-updated', refreshNotifications)
  if (USE_MOCK) await store.loadTasks()
  else if (authState.token) {
    try { await initializeAccount() } catch { authenticated.value = false }
  }
})
onBeforeUnmount(() => {window.removeEventListener('studypath:auth-expired', expireAuth);window.removeEventListener('studypath:notifications-updated',refreshNotifications)})
watch(() => route.path, (path) => { sidebarOpen.value = false; searchOpen.value = false; if (secondaryItems.value.some(item => item.path === path)) moreExpanded.value = true })
function go(path: string) { router.push(path) }
async function markNotification(item: {id:number;read:boolean}) { if(item.read)return; try { await studyApi.markNotificationRead(item.id); item.read=true } catch(error) { console.error('通知状态保存失败',error) } }
</script>

<template>
  <RagAuthGate v-if="!authenticated" @authenticated="initializeAccount" />
  <div v-else class="app-shell-root">
  <div class="app-shell">
    <div v-if="sidebarOpen" class="mobile-scrim" @click="sidebarOpen=false"></div>
    <aside class="sidebar" :class="{ 'sidebar-open': sidebarOpen }">
      <div class="brand-lockup" @click="go('/')">
        <div class="brand-mark" aria-hidden="true"><svg viewBox="0 0 64 64" fill="none"><path d="M30 51c1-14-4-27-16-39 17 7 26 18 25 32 4-12 4-22-1-34 13 14 16 28 7 39 6-5 10-11 12-19 2 15-4 27-18 31-7 2-13 0-20-2-5-1-9-1-13 1 4-6 10-9 18-9-6-5-13-8-21-9 11-3 20 0 27 9Z" fill="currentColor"/></svg></div>
        <div class="brand-copy"><strong>智学研途</strong><span>STUDYPATH AI</span></div>
        <button class="icon-button sidebar-close" aria-label="关闭导航" @click.stop="sidebarOpen=false"><X :size="18" /></button>
      </div>
      <button class="course-switch" @click="go('/courses')"><span class="course-switch-icon">数</span><span class="course-switch-copy"><b>我的课程</b><small>查看课程目录</small></span><ChevronDown :size="15" /></button>
      <nav class="side-nav">
        <section class="nav-group nav-primary">
          <div class="nav-group-label">学习空间</div>
          <button v-for="item in [...navItems[0].items.filter(item => item.path !== '/library'), navItems[1].items[0]]" :key="item.path" class="nav-item" :class="{ active: route.path===item.path }" @click="go(item.path)">
            <span class="nav-symbol"><component :is="iconMap[item.icon]" :size="18" stroke-width="1.8" /></span>
            <span>{{ item.label }}</span><span v-if="item.path==='/plan' && store.taskCount" class="nav-count">{{ store.taskCount }}</span>
          </button>
        </section>
        <button class="nav-more-toggle" :aria-expanded="moreExpanded" @click="moreExpanded=!moreExpanded"><span class="nav-symbol"><Sparkles :size="18" stroke-width="1.8" /></span><span>更多功能</span><ChevronRight class="more-chevron" :class="{ expanded: moreExpanded }" :size="16" /></button>
        <div v-if="moreExpanded" class="nav-secondary">
          <section v-for="group in navItems.slice(1)" :key="group.group" class="nav-group">
            <div class="nav-group-label">{{ group.group }}</div>
            <button v-for="item in group.items.filter(item => item.path !== '/path' && (item.path !== '/admin/curriculum' || isAdmin))" :key="item.path" class="nav-item" :class="{ active: route.path===item.path }" @click="go(item.path)">
              <span class="nav-symbol"><component :is="iconMap[item.icon]" :size="18" stroke-width="1.8" /></span>
              <span>{{ item.label }}</span><span v-if="item.path==='/plan' && store.taskCount" class="nav-count">{{ store.taskCount }}</span>
            </button>
          </section>
          <button class="nav-item" :class="{ active: route.path==='/library' }" @click="go('/library')"><span class="nav-symbol"><FolderOpen :size="18" stroke-width="1.8" /></span><span>学习资料库</span></button>
        </div>
      </nav>
      <div class="sidebar-bottom">
        <button class="sidebar-goal" @click="go('/plan')"><div class="goal-head"><span>今日学习目标</span><span class="goal-progress-label">{{ store.tasks.length ? `${goalProgress}%` : '计划' }}</span></div><div class="goal-copy"><b>{{ store.tasks.length ? `${goalDone} / ${store.tasks.length} 项完成` : '安排今天的学习任务' }}</b><small>{{ store.tasks.length ? '坚持每天进步一点' : '制定计划，稳步向前' }}</small></div><div class="goal-track"><i :style="{ width: `${goalProgress}%` }"></i></div><div class="sidebar-books" aria-hidden="true"><i></i><i></i><i></i></div></button>
        <div class="profile-row"><div class="avatar avatar-small">{{ profileState.name.slice(0, 1) || '学' }}</div><div class="profile-copy"><b>{{ profileState.name || '学习者' }}</b><small>{{ profileState.major }}</small></div><button class="icon-button" title="个人设置" @click="go('/settings')"><ChevronDown :size="16" /></button></div>
      </div>
    </aside>
    <main class="main-area">
      <header class="topbar">
        <div class="topbar-left"><button class="icon-button menu-trigger" aria-label="打开导航" @click="sidebarOpen=true"><Menu :size="19" /></button><div class="breadcrumbs"><span>学习空间</span><span class="crumb-slash">/</span><b>{{ title() }}</b></div></div>
        <div class="topbar-actions">
          <button class="global-search" @click="searchOpen=true"><Search :size="16" /><span>搜索课程、知识点或资料…</span><kbd><Command :size="11" /> K</kbd></button>
          <div class="notification-wrap"><button class="icon-button notification-button" title="学习提醒" aria-label="查看学习提醒" :aria-expanded="notificationsOpen" @click="notificationsOpen=!notificationsOpen"><Bell :size="18" /><i v-if="notifications.some(item=>!item.read)"></i></button><section v-if="notificationsOpen" class="notification-panel"><header><b>学习提醒</b><span>{{notifications.filter(item=>!item.read).length}} 条未读</span></header><button v-for="item in notifications.slice(0,8)" :key="item.id" class="notification-item" :class="{unread:!item.read}" @click="markNotification(item)"><i></i><span><b>{{item.title}}</b><small>{{item.body}}</small><time>{{new Date(item.createdAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}}</time></span></button><p v-if="!notifications.length" class="notification-empty">暂无学习提醒</p></section></div>
          <button class="user-chip" @click="go('/settings')"><div class="avatar">{{ profileState.name.slice(0, 1) || '学' }}</div><span>{{ profileState.name || '学习者' }}</span><ChevronDown :size="14" /></button>
        </div>
      </header>
      <div class="route-wrap"><RouterView v-slot="{ Component }"><Transition name="page" mode="out-in"><component :is="Component" /></Transition></RouterView></div>
      <footer class="app-footer"><span>© 2026 智学研途 StudyPath AI</span><span><i class="status-dot"></i>学习数据按账号保存 · AI 答疑与资料库连接 RAG 服务</span></footer>
    </main>
    <Transition name="fade"><div v-if="searchOpen" class="overlay" @click.self="searchOpen=false"><div class="search-dialog"><div class="search-input-row"><Search :size="19" /><input v-model="query" autofocus placeholder="搜索页面与学习内容…" @keydown.esc="searchOpen=false" /><kbd>ESC</kbd></div><p>快速跳转</p><button v-for="item in filtered()" :key="item.path" class="search-result" @click="go(item.path)"><span>{{ item.label }}</span><span>进入 <span class="arrow">↗</span></span></button><div v-if="!filtered().length" class="search-empty">没有找到相关页面</div><div class="search-hint">按 <kbd>⌘ K</kbd> 随时打开全局搜索</div></div></div></Transition>
  </div>
  </div>
</template>

<style>
.notification-wrap{position:relative}.notification-panel{position:absolute;z-index:40;top:calc(100% + 12px);right:0;width:min(340px,calc(100vw - 32px));max-height:430px;overflow:auto;padding:10px;background:#fff;border:1px solid #eee9f4;border-radius:14px;box-shadow:0 14px 42px #34235820}.notification-panel>header{display:flex;justify-content:space-between;align-items:center;padding:8px 9px 12px;border-bottom:1px solid #f0edf4;color:#373247;font-size:13px}.notification-panel>header span{font-size:10px;color:#8a8299}.notification-item{display:flex;align-items:flex-start;gap:9px;width:100%;padding:10px 8px;border:0;border-bottom:1px solid #f5f3f7;background:transparent;text-align:left;cursor:pointer;color:#635d70}.notification-item>i{width:7px;height:7px;flex:none;margin-top:5px;border-radius:50%;background:transparent}.notification-item.unread>i{background:#815ce0}.notification-item span{display:grid;gap:3px}.notification-item b{font-size:11px}.notification-item small,.notification-item time{font-size:10px;color:#8e8899;line-height:1.5}.notification-item time{font-size:9px}.notification-empty{padding:22px 8px;text-align:center;color:#9a94a4;font-size:11px}
</style>

