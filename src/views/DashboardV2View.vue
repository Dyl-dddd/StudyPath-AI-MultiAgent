<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, ArrowUpRight, BookOpen, Bookmark, Check, ChevronRight, Clock3, Flame, Layers3, Network, Play, Sparkles, Target, TrendingUp } from 'lucide-vue-next'
import { studyApi } from '../api'
import ChartPanel from '../components/ChartPanel.vue'
import { useStudyStore } from '../stores/study'
import type { Course, KnowledgeNode } from '../types'
import { profileState } from '../stores/profile'
import '../styles/dashboard-v2.css'
import dataCover from '../assets/course-covers/data-structures.svg'
import osCover from '../assets/course-covers/operating-systems.svg'
import netCover from '../assets/course-covers/computer-networks.svg'
import dbCover from '../assets/course-covers/database-systems.svg'
import seCover from '../assets/course-covers/software-engineering.svg'

interface CourseCard extends Course { cover: string; description: string; nextLesson: string; }
const router = useRouter()
const store = useStudyStore()
const dateLabel = new Intl.DateTimeFormat('zh-CN', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date())
const coverById: Record<string,string> = { ds:dataCover, os:osCover, net:netCover, db:dbCover, se:seCover }
function getPreviewCourses(source: Course[]) { return source.map(course => ({ ...course, cover:coverById[course.id]||dataCover, description:course.chapter, nextLesson:course.chapter })) }
const courses = ref<CourseCard[]>([])
const stats = ref({ hoursToday: '—', mastered: 0, weeklyTasks: 0, streak: 0, weekHours: Array(7).fill(0), weekScores: Array<number | null>(7).fill(null) })
const tasks = computed(() => store.tasks.slice(0, 3))
const mistakes = ref<Array<{topic:string;wrong:number;mastered:boolean}>>([])
const weakestMistake = computed(() => mistakes.value.filter(item=>!item.mastered).sort((a,b)=>b.wrong-a.wrong)[0] || null)
const tasksCompleted = computed(() => tasks.value.filter(task => task.done).length)
const favorites = ref<string[]>([])
const cardElements: HTMLElement[] = []
let cardObserver: IntersectionObserver | undefined
const reduceMotion = ref(false)
const quizHistory = ref<unknown[]>([])
const hasQuizHistory = computed(() => quizHistory.value.length > 0)
const graphNodes = ref<KnowledgeNode[]>([])
const graphLinks = ref<Array<{source:string;target:string}>>([])
const miniGraphNodes = computed(() => {
  const root = graphNodes.value.find(node => node.type === 'course') || graphNodes.value[0]
  const leaves = graphNodes.value.filter(node => node.id !== root?.id).slice(0, 6)
  return [root, ...leaves].filter((node): node is KnowledgeNode => Boolean(node)).map((node, index) => ({ ...node, x:index===0?210:[72,112,176,244,308,348][index-1], y:index===0?78:[38,122,24,132,40,112][index-1] }))
})
const miniGraphEdges = computed(() => graphLinks.value.filter(edge => miniGraphNodes.value.some(node=>node.id===edge.source)&&miniGraphNodes.value.some(node=>node.id===edge.target)))
function miniNode(id:string) { return miniGraphNodes.value.find(node=>node.id===id) }
const weekTotal = computed(() => { const values=stats.value.weekScores.filter((score): score is number => score!==null); return values.length ? Math.round(values.reduce((sum,score)=>sum+score,0)/values.length) : null })
const todayStudyHours = computed(() => {
  const hours = Number(stats.value.hoursToday)
  return Number.isFinite(hours) ? hours.toFixed(1) : '—'
})
const activeStudy = ref<{ id: string; startedAt: string } | null>(null)
const studyElapsed = ref(0)
const studyActionError = ref('')
const taskActionError = ref('')
let studyTimer: number | undefined
const studyClock = computed(() => `${String(Math.floor(studyElapsed.value / 3600)).padStart(2, '0')}:${String(Math.floor(studyElapsed.value % 3600 / 60)).padStart(2, '0')}:${String(studyElapsed.value % 60).padStart(2, '0')}`)


onMounted(async () => {
  reduceMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  try {
    const profile = await studyApi.profile()
    favorites.value = profile.favoriteCourseIds || []
    if (!favorites.value.length) {
      try {
        const legacy = JSON.parse(localStorage.getItem('studypath.v2.favorites') || '[]') as string[]
        if (legacy.length) {
          const catalog = await studyApi.courses() as Course[]
          favorites.value = legacy.filter(id => catalog.some(course => course.id === id))
          if (favorites.value.length) await studyApi.saveProfile({ favoriteCourseIds: favorites.value })
          localStorage.removeItem('studypath.v2.favorites')
        }
      } catch { /* Ignore malformed legacy favorite state. */ }
    }
  } catch { favorites.value = [] }
  await store.loadTasks()
  try {
    const dashboard = await studyApi.dashboard()
    stats.value = dashboard
    courses.value = getPreviewCourses(dashboard.courses as Course[])
    const [records, attempts] = await Promise.all([studyApi.mistakes(), studyApi.quizAttempts()])
    mistakes.value = records
    quizHistory.value = attempts
    const firstCourse = (dashboard.courses as Course[])[0]
    if (firstCourse) {
      try {
        const graph = await studyApi.graph(firstCourse.id)
        graphNodes.value = graph.nodes
        graphLinks.value = graph.links
      } catch (error) { console.error('课程图谱预览加载失败', error) }
    }
  } catch (error) { console.error('学习总览加载失败', error) }
  try {
    activeStudy.value = await studyApi.activeStudySession()
    if (activeStudy.value) {
      studyElapsed.value = Math.max(0, Math.floor((Date.now() - new Date(activeStudy.value.startedAt).getTime()) / 1000))
      studyTimer = window.setInterval(() => {
        if (activeStudy.value) studyElapsed.value = Math.max(0, Math.floor((Date.now() - new Date(activeStudy.value.startedAt).getTime()) / 1000))
      }, 1000)
    }
  } catch (error) { console.error('专注计时状态加载失败', error) }
  await nextTick()
  cardObserver = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible')
      cardObserver?.unobserve(entry.target)
    }
  }), { threshold: .14 })
  cardElements.forEach(card => cardObserver?.observe(card))
})
onBeforeUnmount(() => { cardObserver?.disconnect(); window.clearInterval(studyTimer) })

async function toggleStudyTimer() {
  studyActionError.value = ''
  try {
    if (activeStudy.value) {
      await studyApi.finishStudySession(activeStudy.value.id)
      activeStudy.value = null
      studyElapsed.value = 0
      window.clearInterval(studyTimer)
    } else {
      activeStudy.value = await studyApi.startStudySession(courses.value[0]?.id)
      studyElapsed.value = 0
      studyTimer = window.setInterval(() => {
        if (activeStudy.value) studyElapsed.value = Math.max(0, Math.floor((Date.now() - new Date(activeStudy.value.startedAt).getTime()) / 1000))
      }, 1000)
    }
    stats.value = await studyApi.dashboard()
  } catch (error) {
    studyActionError.value = error instanceof Error ? error.message : '专注计时操作失败，请重试。'
  }
}

function setCardRef(element: Element | null, index: number) {
  if (element instanceof HTMLElement) cardElements[index] = element
}
async function toggleFavorite(id: string) {
  const previous = [...favorites.value]
  favorites.value = favorites.value.includes(id) ? favorites.value.filter(item => item !== id) : [...favorites.value, id]
  try { await studyApi.saveProfile({ favoriteCourseIds: favorites.value }) }
  catch { favorites.value = previous; console.error('课程收藏保存失败') }
}
async function toggleTask(id: number) {
  taskActionError.value = ''
  try { await store.toggleTask(id) }
  catch (error) { taskActionError.value = error instanceof Error ? error.message : '任务状态保存失败，请重试。' }
}
function tiltCard(event: PointerEvent) {
  if (reduceMotion.value || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
  const card = event.currentTarget as HTMLElement
  const bounds = card.getBoundingClientRect()
  const x = (event.clientX - bounds.left) / bounds.width - .5
  const y = (event.clientY - bounds.top) / bounds.height - .5
  card.style.setProperty('--tilt-x', `${(-y * 3.5).toFixed(2)}deg`)
  card.style.setProperty('--tilt-y', `${(x * 3.5).toFixed(2)}deg`)
}
function resetTilt(event: PointerEvent) {
  const card = event.currentTarget as HTMLElement
  card.style.removeProperty('--tilt-x')
  card.style.removeProperty('--tilt-y')
}
function openCourse(course: CourseCard) { router.push({ path: '/courses', query: { course: course.id } }) }
function continueCourse(course: CourseCard) { router.push({ path: '/path', query: { course: course.id } }) }
</script>

<template>
  <main class="page-content dashboard-v2">
    <section class="v2-welcome">
      <div class="v2-welcome-copy">
        <div class="v2-date"><span class="v2-live"></span>{{ dateLabel }} <span>·</span> 学习数据已同步到账户</div>
        <h1>欢迎回来，{{ profileState.name }}<span class="v2-wave">✦</span></h1>
        <p>今天也向你的学习目标更近一步。</p>
        <div class="v2-welcome-actions"><button class="v2-button v2-button-primary" @click="router.push('/path')"><Play :size="16" fill="currentColor" />继续今天的学习</button><button class="v2-button v2-button-quiet" @click="router.push('/library')">整理学习资料 <ArrowRight :size="15" /></button></div>
      </div>
      <div class="v2-welcome-art" aria-label="书本与学习知识点插画">
        <div class="v2-art-halo"></div><div class="v2-art-page page-back"></div><div class="v2-art-page page-front"><BookOpen :size="42" stroke-width="1.55" /><span>LEARN<br>WITH PURPOSE</span></div>
        <span class="v2-art-chip chip-a"><Network :size="15" /> 知识关联</span><span class="v2-art-chip chip-b"><Sparkles :size="14" /> 个性化学习</span><i class="art-spark spark-one">✳</i><i class="art-spark spark-two">✦</i>
      </div>
    </section>

    <section class="v2-stats" aria-label="学习数据概览">
      <article class="v2-stat"><span class="v2-stat-icon tint-violet"><Clock3 :size="19" /></span><div><span class="v2-stat-label">今日累计专注时长</span><strong>{{ todayStudyHours }}<small> 小时</small></strong><small>{{ activeStudy ? `正在计时 ${studyClock}` : '按账号计时记录汇总' }}</small><button class="v2-timer-action" :aria-pressed="Boolean(activeStudy)" @click="toggleStudyTimer"><Play v-if="!activeStudy" :size="12" fill="currentColor"/>{{ activeStudy ? '结束专注' : '开始专注' }}</button><small v-if="studyActionError" class="v2-timer-error" role="alert">{{ studyActionError }}</small></div><span class="v2-stat-spark spark-violet"><i v-for="(hour,index) in stats.weekHours" :key="index" :style="{height:`${10 + hour * 18}px`}"></i></span></article>
      <article class="v2-stat"><span class="v2-stat-icon tint-mint"><Layers3 :size="19" /></span><div><span class="v2-stat-label">间隔复测掌握错题</span><strong>{{ stats.mastered }}</strong><small>只统计完成间隔复测的错题</small></div><span class="v2-stat-orbit"><b>{{ stats.mastered }}</b></span></article>
      <article class="v2-stat"><span class="v2-stat-icon tint-peach"><Target :size="19" /></span><div><span class="v2-stat-label">所选任务完成率</span><strong>{{ tasks.length ? Math.round(tasksCompleted / tasks.length * 100) : 0 }}<small>%</small></strong><small>完成 {{ tasksCompleted }} / {{ tasks.length }} 项</small></div><span class="v2-stat-progress"><i :style="{width:`${tasks.length ? tasksCompleted / tasks.length * 100 : 0}%`}"></i></span></article>
      <article class="v2-stat"><span class="v2-stat-icon tint-rose"><Flame :size="19" /></span><div><span class="v2-stat-label">连续测验活跃天数</span><strong>{{ stats.streak }}<small> 天</small></strong><small>按账号测验提交日期计算</small></div><span class="v2-streak-dots"><i v-for="i in 7" :key="i" :class="{filled:i <= stats.streak}"></i></span></article>
    </section>

    <section class="v2-recommend">
      <div class="v2-recommend-copy"><span class="v2-recommend-label"><Sparkles :size="14" /> 为你准备的下一步</span><h2>{{ weakestMistake ? `先复习${weakestMistake.topic}` : '完成一次测验，生成个性化建议' }}</h2><p>{{ weakestMistake ? `账户错题记录中有 ${weakestMistake.wrong} 次相关错误，可安排一次间隔复测。` : '完成测验后，首页会根据真实错题记录展示下一步建议。' }}</p><button class="v2-recommend-link" @click="router.push(weakestMistake ? '/mistakes' : '/quiz')">{{ weakestMistake ? '查看错题记录' : '开始测验'}} <ArrowRight :size="15" /></button></div>
      <div class="v2-recommend-visual" aria-hidden="true"><span class="rec-book"><BookOpen :size="38" /></span><span class="rec-node node-root">二叉树</span><span class="rec-node node-left">遍历</span><span class="rec-node node-right">搜索树</span><span class="rec-link link-a"></span><span class="rec-link link-b"></span><i class="rec-glow"></i></div>
    </section>

    <section class="v2-courses-section">
      <div class="v2-section-heading"><div><div class="v2-section-kicker">MY LEARNING SPACE</div><h2>我的学习课程</h2><p>课程、进度与下一步，一眼就能找到。</p></div><button class="v2-button v2-button-outline" @click="router.push('/courses')">查看全部课程 <ArrowRight :size="15" /></button></div>
      <div class="v2-course-grid">
        <article v-for="(course,index) in courses" :key="course.id" :ref="element => setCardRef(element as Element | null,index)" class="v2-course-card" :style="{'--stagger':`${index * 75}ms`}" @pointermove="tiltCard" @pointerleave="resetTilt" @click="openCourse(course)">
          <div class="v2-cover-wrap"><img class="v2-cover" :src="course.cover" :alt="`${course.name}课程插画`" /><span class="v2-cover-tag">{{ course.category }}</span><button class="v2-favorite" :class="{saved:favorites.includes(course.id)}" :aria-label="favorites.includes(course.id)?'取消收藏课程':'收藏课程'" :aria-pressed="favorites.includes(course.id)" @click.stop="toggleFavorite(course.id)"><Bookmark :size="17" :fill="favorites.includes(course.id)?'currentColor':'none'" /></button></div>
          <div class="v2-course-body"><div class="v2-course-title-row"><div><h3>{{ course.name }}</h3><p>{{ course.description || '课程章节尚未填写' }}</p></div><div class="v2-course-ring" :aria-label="`课程学习进度 ${course.progress}%`"><svg viewBox="0 0 44 44" aria-hidden="true"><circle class="ring-track" cx="22" cy="22" r="18"/></svg><span>{{ course.progress }}%</span></div></div>
            <div class="v2-course-meta"><span><Layers3 :size="14" />{{ course.points }} 个知识点</span><span><TrendingUp :size="14" />课程学习进度 {{ course.progress }}%</span></div><div class="v2-next-lesson"><span>接下来</span>{{ course.nextLesson }}</div><button class="v2-continue" @click.stop="continueCourse(course)"><Play :size="14" fill="currentColor" />继续学习<ArrowRight :size="14" /></button></div>
        </article>
      </div>
    </section>

    <section class="v2-insights-row">
      <article class="v2-insight-panel v2-week-panel"><div class="v2-panel-heading"><div><div class="v2-section-kicker">YOUR MOMENTUM</div><h2>每日测验正确率</h2><p>统计已提交的测验记录。</p></div><span class="v2-week-total">{{ weekTotal ?? '—' }}<small v-if="weekTotal!==null"> %</small></span></div><div v-if="hasQuizHistory" class="v2-week-chart"><div v-for="(hour,index) in stats.weekScores" :key="index" class="v2-week-column"><span class="v2-hour-tip">{{ hour ?? '—' }}%</span><i :style="{height:`${Math.max(12,hour ?? 0)}%`}" :class="{today:index===6}"></i><small>{{ ['一','二','三','四','五','六','日'][index] }}</small></div></div><div v-else class="v2-empty-chart">完成测验后，这里会显示你的每日正确率。</div><div class="v2-chart-foot"><span><i></i> 测验平均分</span><button @click="router.push('/analytics')">查看完整分析 <ArrowRight :size="14" /></button></div></article>
      <article class="v2-insight-panel v2-graph-panel"><div class="v2-panel-heading"><div><div class="v2-section-kicker">CONNECTED KNOWLEDGE</div><h2>课程知识图谱预览</h2><p>知识关系来自课程目录，掌握程度按个人测验记录计算。</p></div><button class="v2-icon-link" aria-label="进入课程知识图谱" @click="router.push({path:'/graph',query:{course:courses[0]?.id}})"><ArrowUpRight :size="18" /></button></div><div v-if="miniGraphNodes.length" class="v2-mini-graph"><svg viewBox="0 0 420 156" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><g class="v2-graph-edges"><line v-for="edge in miniGraphEdges" :key="`${edge.source}-${edge.target}`" :x1="miniNode(edge.source)?.x" :y1="miniNode(edge.source)?.y" :x2="miniNode(edge.target)?.x" :y2="miniNode(edge.target)?.y" /></g><g class="v2-graph-leaves"><circle v-for="node in miniGraphNodes" :key="node.id" :cx="node.x" :cy="node.y" :r="node.type==='course'?23:10" /></g><g class="v2-graph-labels"><text v-for="node in miniGraphNodes" :key="node.id" :x="node.x" :y="node.y+4">{{ node.name }}</text></g></svg></div><div v-else class="v2-empty-chart">添加课程图谱后，这里会显示知识点关系。</div><button class="v2-graph-link" @click="router.push({path:'/graph',query:{course:courses[0]?.id}})">探索课程知识图谱 <ArrowRight :size="14" /></button></article>
    </section>

    <section class="v2-plan-panel"><div class="v2-panel-heading"><div><div class="v2-section-kicker">SMALL STEPS, BIG GROWTH</div><h2>接下来要做的事</h2><p>把今天的小目标，变成掌握的新知识。</p></div><button class="v2-button v2-button-outline" @click="router.push('/plan')">打开学习计划 <ArrowRight :size="15" /></button></div><p v-if="taskActionError" class="v2-timer-error" role="alert">{{taskActionError}}</p><div v-if="tasks.length" class="v2-task-list"><div v-for="task in tasks" :key="task.id" class="v2-task-row"><button class="v2-task-check" :class="{checked:task.done}" :aria-label="task.done?'标记未完成':'完成任务'" @click="toggleTask(task.id)"><Check v-if="task.done" :size="14" /></button><span class="v2-task-title" :class="{done:task.done}">{{ task.title }}</span><span class="v2-task-course">{{ task.course }}</span><span class="v2-task-date"><Clock3 :size="14" />{{ task.date }}</span><button class="v2-task-open" :aria-label="`开始${task.course}学习`" @click="router.push({path:'/path',query:{course:courses.find(course=>course.name===task.course)?.id}})"><ChevronRight :size="17" /></button></div></div><div v-else class="v2-tasks-done"><span><Check :size="16" /></span>还没有保存的学习计划。<button @click="router.push('/plan')">看看本周计划 <ArrowRight :size="14" /></button></div></section>
    <div class="v2-demo-note"><span class="v2-demo-dot"></span>课程目录来自服务端；计划、测验与错题记录按账号保存<RouterLink to="/">返回原首页</RouterLink></div>
  </main>
</template>
