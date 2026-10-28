<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Bot, BookOpenCheck, BrainCircuit, ChartNoAxesCombined, CircleAlert, LoaderCircle, Network, RotateCw, Sparkles, Target } from 'lucide-vue-next'
import { studyApi } from '../api'

type Intent = 'profile' | 'mistake' | 'tutor' | 'graph'
type AgentResponse = {
  task_id: string; intent: string; agent: string; status: 'completed' | 'partial' | 'failed'
  evidence: Array<Record<string, unknown>>; citations: Array<Record<string, unknown>>
  result: Record<string, any>; error?: { code: string; message: string } | null; elapsed_ms: number
}
type Course = { id: string; name: string }
type Mistake = { questionId: number; title: string; topic: string; course: string }
const router = useRouter()
const intent = ref<Intent>('tutor')
const question = ref('')
const courseId = ref('')
const questionId = ref<number | null>(null)
const courses = ref<Course[]>([])
const mistakes = ref<Mistake[]>([])
const profile = ref<{ educationStage: string; grade: string; learningGoal: string } | null>(null)
const health = ref<any>(null)
const loading = ref(false)
const loadError = ref('')
const error = ref('')
const response = ref<AgentResponse | null>(null)
const selectedMistake = computed(() => mistakes.value.find(item => item.questionId === questionId.value))
const agentMeta: Record<Intent, { label: string; description: string; icon: Component }> = {
  tutor: { label: '大模型助教', description: '使用已配置的后端模型回答通用学习问题，不读取本地资料。', icon: BrainCircuit },
  profile: { label: '学习画像分析', description: '依据当前账号的画像、测验、掌握度与错题记录给出可调整建议。', icon: ChartNoAxesCombined },
  mistake: { label: '错题举一反三', description: '从错题本选一道题，生成三道同考点新情境练习；提交后再判分。', icon: Target },
  graph: { label: '知识图谱分析', description: '结合课程中的真实先修关系和本账号掌握度解释学习顺序。', icon: Network },
}
const currentMeta = computed(() => agentMeta[intent.value])
const modelReady = computed(() => health.value?.providers?.openai_compatible?.status === 'configured')
const variantAnswers = ref<Record<string, string>>({})
const variantGrade = ref<any>(null)

function selectIntent(value: Intent) { intent.value = value; response.value = null; error.value = ''; variantAnswers.value = {}; variantGrade.value = null }

async function runCombinedAnalysis() {
  error.value = ''
  response.value = null
  if (!courseId.value) { error.value = '当前没有可分析的课程图谱。'; return }
  loading.value = true
  try {
    const combined = await studyApi.runParallelAgents(courseId.value)
    const results = combined.results || []
    const profileResult = combined.merged?.profile
    const graphResult = combined.merged?.graph
    response.value = {
      task_id: results[0]?.task_id || 'parallel-analysis',
      intent: 'parallel',
      agent: 'user_profile + knowledge_graph',
      status: combined.status,
      evidence: results.flatMap((item: any) => (item.evidence || []).map((entry: any) => ({ agent: item.agent, ...entry }))),
      citations: [],
      result: {
        message: combined.merged?.message || '综合分析已返回。',
        suggestions: profileResult?.suggestions || [],
        recommendations: graphResult?.recommendations || [],
        errors: combined.merged?.errors || [],
      },
      elapsed_ms: results.reduce((total: number, item: any) => total + (item.elapsed_ms || 0), 0),
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '综合分析失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const [catalog, mistakeRows, healthState, profileRow] = await Promise.all([
      studyApi.courses(), studyApi.mistakes(), studyApi.agentHealth(), studyApi.profile(),
    ])
    courses.value = catalog
    mistakes.value = mistakeRows
    health.value = healthState
    profile.value = profileRow
    if (catalog.length) courseId.value = catalog[0].id
    if (mistakeRows.length) questionId.value = mistakeRows[0].questionId
  } catch (cause) {
    loadError.value = cause instanceof Error ? cause.message : '智能体状态加载失败'
  }
})

async function run() {
  error.value = ''
  response.value = null
  if (intent.value === 'tutor' && !question.value.trim()) { error.value = '先输入想问的问题。'; return }
  if (intent.value === 'mistake' && !questionId.value) { error.value = '当前账号错题本没有可选题目，请先完成一次测验。'; return }
  if (intent.value === 'graph' && !courseId.value) { error.value = '请选择要分析的课程。'; return }
  loading.value = true
  try {
    response.value = await studyApi.runAgent({
      intent: intent.value,
      ...(question.value.trim() ? { question: question.value.trim() } : {}),
      ...(intent.value === 'mistake' && questionId.value ? { question_id: questionId.value } : {}),
      ...(intent.value === 'graph' && courseId.value ? { course_id: courseId.value } : {}),
    }) as AgentResponse
    variantAnswers.value = {}
    variantGrade.value = null
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '智能体调用失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function submitVariants() {
  if (!questionId.value || !response.value?.result.setId || Object.keys(variantAnswers.value).length !== 3) {
    error.value = '请先完成三道练习题。'
    return
  }
  loading.value = true
  error.value = ''
  try {
    variantGrade.value = await studyApi.submitMistakeVariants(questionId.value, response.value.result.setId, variantAnswers.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '判分失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="agent-page">
    <header class="agent-heading">
      <div class="agent-heading-icon"><Sparkles :size="21" /></div>
      <div><span class="eyebrow">STUDYPATH AI · LEARNING AGENTS</span><h1>AI 多智能体学习</h1><p>按任务调用边界清晰的学习服务，建议都能追溯到课程或账号记录。</p></div>
      <div class="agent-heading-actions">
        <button class="btn btn-secondary" :disabled="loading" @click="runCombinedAnalysis"><BrainCircuit :size="16"/>画像 + 图谱综合分析</button>
        <button class="btn btn-secondary" @click="router.push('/chat')"><BookOpenCheck :size="16"/>进入资料库问答</button>
      </div>
    </header>

    <section class="agent-layout">
      <aside class="panel agent-picker">
        <div class="agent-section-title"><Bot :size="17"/>选择学习任务</div>
        <button v-for="(meta, key) in agentMeta" :key="key" class="agent-option" :class="{active:intent===key}" @click="selectIntent(key as Intent)">
          <span class="agent-option-icon"><component :is="meta.icon" :size="17"/></span><span><b>{{meta.label}}</b><small>{{meta.description}}</small></span><i v-if="intent===key"></i>
        </button>
        <div class="agent-footnote"><CircleAlert :size="14"/><span>画像与图谱建议仅依据当前账号记录；不会自动改动学习计划或课程内容。</span></div>
      </aside>

      <section class="panel agent-workbench">
        <header class="workbench-header"><div><span class="eyebrow">{{currentMeta.label}}</span><h2>{{currentMeta.label}}</h2><p>{{currentMeta.description}}</p></div><span class="provider-status" :class="{ready: intent!=='tutor'||modelReady}"><i/>{{intent==='tutor'?(modelReady?'模型已配置':'模型未配置'):intent==='mistake'?'需要模型服务':'读取账号数据'}}</span></header>
        <div v-if="loadError" class="agent-alert"><CircleAlert :size="16"/>{{loadError}}</div>
        <div v-if="intent==='tutor'" class="agent-form"><label for="agent-question">你的问题</label><textarea id="agent-question" v-model="question" rows="5" maxlength="5000" placeholder="例如：如何区分进程和线程？"></textarea><small>通用大模型回答不会查询课程资料库。需要基于自己的课程文件作答，请使用“资料库问答”。</small></div>
        <div v-else-if="intent==='mistake'" class="agent-form"><label for="mistake-select">选择一道已记录的错题</label><select id="mistake-select" v-model.number="questionId"><option :value="null" disabled>请选择错题</option><option v-for="item in mistakes" :key="item.questionId" :value="item.questionId">{{item.course}} · {{item.title}}</option></select><div v-if="selectedMistake" class="selection-note">考查主题：{{selectedMistake.topic}}。模型会生成三道不同情境的新题，答案在提交后显示。</div></div>
        <div v-else-if="intent==='graph'" class="agent-form"><label for="course-select">选择课程图谱</label><select id="course-select" v-model="courseId"><option v-for="course in courses" :key="course.id" :value="course.id">{{course.name}}</option></select><div class="selection-note">分析依据来自课程目录中的正式先修边和当前账号掌握记录；空白掌握度表示尚无记录。</div></div>
        <div v-else class="profile-snapshot"><div><small>学段 / 年级</small><b>{{profile?.educationStage||'未设置'}} · {{profile?.grade||'未填写'}}</b></div><div><small>学习目标</small><b>{{profile?.learningGoal||'尚未填写，可在个人设置中补充'}}</b></div><button class="btn btn-secondary" @click="router.push('/settings')"><Target :size="15"/>完善画像</button></div>

        <div class="agent-actions"><button class="btn btn-primary" :disabled="loading" @click="run"><LoaderCircle v-if="loading" class="agent-spin" :size="16"/><RotateCw v-else :size="15"/>{{loading?'正在处理…':'运行学习任务'}}</button><span v-if="intent==='mistake'">生成结果只暂存为当前账号的限时练习，不会自动增加掌握度。</span></div>
        <div v-if="error" class="agent-alert"><CircleAlert :size="16"/>{{error}}</div>

        <article v-if="response" class="agent-result" :class="'state-'+response.status">
          <header><div><span class="eyebrow">任务 {{response.task_id.slice(0,8)}}</span><h3>{{response.status==='failed'?'任务未完成':response.status==='partial'?'部分结果':'任务完成'}}</h3></div><small>{{response.elapsed_ms}} ms · {{response.agent}}</small></header>
          <p v-if="response.error" class="result-error">{{response.error.message}}</p>
          <p v-if="response.result.answer" class="agent-answer">{{response.result.answer}}</p>
          <p v-if="response.result.message" class="agent-answer">{{response.result.message}}</p>
          <p v-if="response.result.notice" class="selection-note">{{response.result.notice}}</p>
          <section v-if="response.result.errors?.length" class="result-list"><h4>未完成的子任务</h4><div v-for="item in response.result.errors" :key="item.intent" class="result-suggestion"><b>{{agentMeta[item.intent as Intent]?.label||item.intent}}</b><span>{{item.message}}</span></div></section>
          <section v-if="response.result.suggestions?.length" class="result-list"><h4>可调整建议</h4><div v-for="(item,index) in response.result.suggestions" :key="index" class="result-suggestion"><b>{{item.title||item.node}}</b><span>{{item.reason||`当前掌握度 ${item.mastery}%，建议先完成：${item.reviewPrerequisites?.join('、')}`}}</span></div></section>
          <section v-if="response.result.recommendations?.length" class="result-list"><h4>先修关系提示</h4><div v-for="(item,index) in response.result.recommendations" :key="index" class="result-suggestion"><b>{{item.node}}</b><span>掌握度记录 {{item.mastery}}%；建议回看 {{item.reviewPrerequisites.join('、')}}</span></div></section>
          <section v-if="response.result.variants?.length" class="result-list"><h4>新情境练习 · {{response.result.topic}}</h4><div v-for="item in response.result.variants" :key="item.id" class="variant-preview"><b>{{item.id}}. {{item.title}}</b><button v-for="(option,index) in item.options" :key="index" class="variant-option" :class="{chosen:variantAnswers[String(item.id)]===option,correct:variantGrade?.results?.find((result:any)=>result.id===item.id)?.answer===option,wrong:variantGrade?.results?.find((result:any)=>result.id===item.id)?.answer!==option&&variantAnswers[String(item.id)]===option}" :disabled="Boolean(variantGrade)" @click="variantAnswers[String(item.id)]=option">{{String.fromCharCode(65+Number(index))}}. {{option}}</button><p v-if="variantGrade?.results?.find((result:any)=>result.id===item.id)" class="grade-explanation">{{variantGrade.results.find((result:any)=>result.id===item.id).correct ? '回答正确。' : `正确答案：${String(variantGrade.results.find((result:any)=>result.id===item.id).answer)}。`}}{{variantGrade.results.find((result:any)=>result.id===item.id).explanation}}</p></div><button v-if="!variantGrade" class="btn btn-primary" :disabled="loading" @click="submitVariants">提交三题并查看解析</button><p v-else class="grade-summary">本次答对 {{variantGrade.correctCount}} / {{variantGrade.total}} 题。错题复习记录已更新。</p></section>
          <details v-if="response.evidence.length" class="result-evidence"><summary>查看依据（{{response.evidence.length}}）</summary><pre>{{JSON.stringify(response.evidence,null,2)}}</pre></details>
          <section v-if="response.citations.length" class="result-list"><h4>资料来源</h4><div v-for="citation in response.citations" :key="String(citation.chunk_id)" class="result-suggestion"><b>{{citation.document_name}}</b><span>{{citation.section_title||'文档片段'}} · {{citation.page_start?`第 ${citation.page_start} 页`:''}} {{citation.snippet}}</span></div></section>
        </article>
      </section>
    </section>
  </main>
</template>

<style scoped>
.agent-page{max-width:1280px;margin:0 auto;padding:28px 30px 46px;color:#332b48}.agent-heading{display:flex;align-items:center;gap:15px;margin-bottom:22px}.agent-heading-icon{width:46px;height:46px;border-radius:15px;background:#f0eaff;color:#7951df;display:grid;place-items:center}.agent-heading h1{font-size:24px;margin:4px 0}.agent-heading p,.workbench-header p{font-size:12px;color:#8d849e;margin:0}.eyebrow{font-size:10px;letter-spacing:.1em;color:#957cce}.agent-heading-actions{display:flex;align-items:center;gap:8px;margin-left:auto}.agent-heading-actions button:disabled{opacity:.65;cursor:wait}.agent-layout{display:grid;grid-template-columns:minmax(250px,310px) minmax(0,1fr);gap:16px;align-items:start}.agent-picker,.agent-workbench{border:1px solid #eee9f5;border-radius:17px;background:#fff;box-shadow:0 5px 18px #33225c08}.agent-picker{padding:18px}.agent-section-title{display:flex;align-items:center;gap:8px;font-weight:650;font-size:13px;margin-bottom:13px}.agent-option{display:flex;align-items:flex-start;gap:10px;width:100%;padding:12px 10px;background:white;border:1px solid transparent;border-radius:12px;text-align:left;color:#4f4761;cursor:pointer;margin:5px 0}.agent-option:hover,.agent-option.active{background:#f7f3ff;border-color:#e7ddff}.agent-option-icon{display:grid;place-items:center;width:30px;height:30px;flex:none;color:#805de0;background:#eee8ff;border-radius:9px}.agent-option>span:nth-child(2){display:grid;gap:5px}.agent-option b{font-size:12px}.agent-option small{font-size:10px;line-height:1.55;color:#8c8498}.agent-option i{width:7px;height:7px;margin:6px 0 0 auto;border-radius:50%;background:#7652dc;flex:none}.agent-footnote{display:flex;gap:8px;border-top:1px solid #f0edf4;padding:14px 2px 0;margin-top:10px;color:#8c8399;font-size:10px;line-height:1.6}.agent-footnote svg{flex:none;color:#9275dc;margin-top:1px}.agent-workbench{padding:22px;min-height:510px}.workbench-header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #f0edf4;padding-bottom:17px;margin-bottom:18px;gap:18px}.workbench-header h2{font-size:18px;margin:4px 0 6px}.provider-status{display:flex;align-items:center;gap:6px;font-size:10px;color:#a78a7e;white-space:nowrap}.provider-status i{width:6px;height:6px;border-radius:50%;background:#e4a06d}.provider-status.ready i{background:#44b99d}.agent-form{display:grid;gap:8px;margin:20px 0}.agent-form label{font-size:12px;font-weight:600}.agent-form textarea,.agent-form select{width:100%;border:1px solid #e8e1f0;border-radius:10px;padding:12px;color:#443b55;background:#fff;font:inherit;font-size:12px;outline:none}.agent-form textarea:focus,.agent-form select:focus{border-color:#a98be9;box-shadow:0 0 0 3px #8c68e515}.agent-form small,.selection-note{font-size:10px;line-height:1.6;color:#91899d}.selection-note{padding:11px 12px;border-radius:9px;background:#faf8fd}.profile-snapshot{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}.profile-snapshot>div{display:grid;gap:7px;padding:14px;background:#faf8fd;border-radius:10px}.profile-snapshot small{font-size:10px;color:#938ba0}.profile-snapshot b{font-size:12px;font-weight:550}.profile-snapshot button{justify-self:start}.agent-actions{display:flex;align-items:center;gap:12px;margin-top:18px}.agent-actions>span{font-size:10px;color:#938ba0;line-height:1.5}.agent-actions button{min-width:156px}.agent-actions button:disabled{opacity:.7;cursor:wait}.agent-spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.agent-alert{display:flex;align-items:center;gap:8px;padding:12px;margin-top:14px;border:1px solid #f3d5d5;border-radius:10px;background:#fff8f8;color:#a84b51;font-size:12px}.agent-result{border:1px solid #e8e1f1;border-radius:13px;padding:16px;margin-top:22px}.agent-result.state-failed{border-color:#f1d9d9;background:#fffdfd}.agent-result>header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f0edf4;padding-bottom:11px}.agent-result h3{font-size:15px;margin:3px 0 0}.agent-result header small{font-size:10px;color:#928a9d}.agent-answer{font-size:13px;line-height:1.9;white-space:pre-wrap;color:#4e4561}.result-error{color:#a84b51;font-size:12px}.result-list{display:grid;gap:9px;margin:17px 0}.result-list h4{font-size:12px;margin:0;color:#5d536d}.result-suggestion,.variant-preview{display:grid;gap:6px;padding:12px;background:#faf8fd;border-radius:10px}.result-suggestion b,.variant-preview b{font-size:12px}.result-suggestion span,.variant-preview span{font-size:11px;line-height:1.7;color:#736b81}.variant-preview{margin:8px 0}.variant-option{border:1px solid #e9e3f1;border-radius:8px;background:white;padding:9px 10px;color:#645b73;text-align:left;font-size:11px;line-height:1.5;cursor:pointer}.variant-option.chosen{border-color:#9777e4;background:#f6f1ff;color:#6345be}.variant-option.correct{border-color:#71c4aa;background:#edfaf5;color:#287e65}.variant-option.wrong{border-color:#e59a9a;background:#fff1f1;color:#a44343}.grade-explanation,.grade-summary{padding:10px;border-radius:9px;background:#f1fbf7;color:#39836e;font-size:11px;line-height:1.7}.result-evidence{margin-top:15px;color:#716980;font-size:11px}.result-evidence summary{cursor:pointer}.result-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:#faf8fd;border-radius:9px;font-size:10px}.result-list>.btn{justify-self:start}.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid #e7e0f0;border-radius:9px;padding:9px 13px;background:white;color:#7054cc;font-size:11px;cursor:pointer}.btn-primary{border-color:#8054df;background:linear-gradient(120deg,#7045da,#976fe9);color:white;box-shadow:0 4px 11px #7849d52a}.btn-secondary{background:#f8f5ff}.agent-result .btn{margin-top:8px}@media(max-width:850px){.agent-page{padding:18px 14px 32px}.agent-layout{grid-template-columns:1fr}.agent-heading{align-items:flex-start;flex-wrap:wrap}.agent-heading-actions{margin-left:auto;flex-wrap:wrap}.agent-heading-actions button{font-size:0;padding:8px}.agent-heading-actions button svg{margin:0}.agent-picker{display:grid;grid-template-columns:1fr 1fr}.agent-section-title,.agent-footnote{grid-column:1/-1}.agent-option{min-height:86px}.workbench-header{display:grid}.profile-snapshot{grid-template-columns:1fr}}
</style>
