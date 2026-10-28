<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ArrowLeft, Check, KeyRound, Link2, Plus, RefreshCw, Save, Trash2 } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { studyApi } from '../api'
import { ragRequest } from '../rag/api'
import type { Course } from '../types'

interface AdminNode { id: string; name: string; type: string; description: string }
interface AdminEdge { source: string; target: string }
interface AdminQuestion { id: number; courseId: string; type: string; difficulty: string; topic: string; conceptId: string; title: string; options: string[]; answer: string | string[]; explanation: string }
const router = useRouter()
const adminChecking = ref(true)
const isAdmin = ref(false)
const token = ref('')
const courses = ref<Course[]>([])
const courseId = ref('')
const nodes = ref<AdminNode[]>([])
const edges = ref<AdminEdge[]>([])
const questions = ref<AdminQuestion[]>([])
const busy = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const editingCourse = ref(false)
const editingNodeId = ref('')
const editingQuestionId = ref<number | null>(null)
const newEdge = reactive({ source: '', target: '' })
const courseForm = reactive({ id: '', name: '', category: '专业基础', points: 0, chapter: '', color: '#7357dc', icon: '' })
const nodeForm = reactive({ id: '', name: '', type: 'concept', description: '' })
const questionForm = reactive({ type: '单选题', difficulty: '基础', topic: '', conceptId: '', title: '', options: '', answer: '', explanation: '' })
const activeCourse = computed(() => courses.value.find(item => item.id === courseId.value))
const availableTargets = computed(() => nodes.value.filter(item => item.id !== newEdge.source))

function message(value: unknown) { return value instanceof Error ? value.message : '操作失败，请检查网络或管理员凭据。' }
function resetCourse() { editingCourse.value = false; Object.assign(courseForm, { id: '', name: '', category: '专业基础', points: 0, chapter: '', color: '#7357dc', icon: '' }) }
function editCourse(course: Course) { editingCourse.value = true; Object.assign(courseForm, course) }
async function refreshCourses() { courses.value = await studyApi.courses() as Course[]; if (!courseId.value && courses.value.length) courseId.value = courses.value[0].id }
async function loadCourseData() {
  if (!token.value || !courseId.value) return
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const [graph, bank] = await Promise.all([studyApi.adminGraph(courseId.value, token.value), studyApi.adminQuestions(courseId.value, token.value)])
    nodes.value = graph.nodes; edges.value = graph.edges; questions.value = bank
  } catch (cause) { error.value = message(cause) }
  finally { loading.value = false }
}
async function connect() { token.value = token.value.trim(); if (!token.value) { error.value = '请输入服务端配置的课程内容管理令牌。'; return } await loadCourseData() }
watch(courseId, () => { resetNode(); resetQuestion(); if (token.value) void loadCourseData() })
onMounted(async () => {
  try {
    const account = await ragRequest<{ role?: string }>('/auth/me')
    isAdmin.value = account.role === 'admin'
    if (!isAdmin.value) {
      await router.replace('/')
      return
    }
    await refreshCourses()
  } catch (cause) {
    error.value = message(cause)
    await router.replace('/')
  } finally {
    adminChecking.value = false
  }
})

async function saveCourse() {
  busy.value = true; error.value = ''; notice.value = ''
  try { const saved = await studyApi.saveAdminCourse({ ...courseForm }, token.value, editingCourse.value); await refreshCourses(); courseId.value = saved.id; resetCourse(); notice.value = '课程信息已保存。' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function removeCourse() {
  if (!activeCourse.value || !window.confirm(`删除“${activeCourse.value.name}”会同时删除课程图谱和题目，确定继续吗？`)) return
  busy.value = true
  try { await studyApi.deleteAdminCourse(courseId.value, token.value); courseId.value = ''; await refreshCourses(); nodes.value = []; edges.value = []; questions.value = []; notice.value = '课程已删除。' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
function resetNode() { editingNodeId.value = ''; Object.assign(nodeForm, { id: '', name: '', type: 'concept', description: '' }) }
function editNode(node: AdminNode) { editingNodeId.value = node.id; Object.assign(nodeForm, node) }
async function saveNode() {
  busy.value = true; error.value = ''
  try { await studyApi.saveAdminNode(courseId.value, { ...nodeForm }, token.value, Boolean(editingNodeId.value)); await loadCourseData(); resetNode(); notice.value = '知识点已保存。' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function removeNode(node: AdminNode) {
  if (!window.confirm(`删除“${node.name}”会同时移除关联边。确定继续吗？`)) return
  try { await studyApi.deleteAdminNode(courseId.value, node.id, token.value); await loadCourseData(); notice.value = '知识点已删除。' }
  catch (cause) { error.value = message(cause) }
}
async function saveEdges() {
  busy.value = true; error.value = ''
  try { await studyApi.saveAdminEdges(courseId.value, edges.value, token.value); notice.value = '先修关系已保存。' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
function addEdge() {
  if (!newEdge.source || !newEdge.target) return
  if (edges.value.some(item => item.source === newEdge.source && item.target === newEdge.target)) { error.value = '这条关系已经存在。'; return }
  edges.value.push({ ...newEdge }); newEdge.source = ''; newEdge.target = ''; error.value = ''
}
function resetQuestion() { editingQuestionId.value = null; Object.assign(questionForm, { type: '单选题', difficulty: '基础', topic: '', conceptId: '', title: '', options: '', answer: '', explanation: '' }) }
function editQuestion(item: AdminQuestion) { editingQuestionId.value = item.id; Object.assign(questionForm, { ...item, options: (item.options || []).join('\n'), answer: Array.isArray(item.answer) ? item.answer.join('、') : item.answer }) }
async function saveQuestion() {
  busy.value = true; error.value = ''
  try {
    const payload = { course_id: courseId.value, ...questionForm, options: questionForm.options.split('\n').map(value => value.trim()).filter(Boolean), answer: questionForm.type === '多选题' ? questionForm.answer.split(/[、，,\s]+/).map(value => value.trim()).filter(Boolean) : questionForm.answer.trim(), misconceptions: {}, transfer_question_ids: [], evidence: null }
    await studyApi.saveAdminQuestion(payload, token.value, editingQuestionId.value || undefined); await loadCourseData(); resetQuestion(); notice.value = '题目已保存。'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function removeQuestion(item: AdminQuestion) {
  if (!window.confirm('删除这道题后，新测验将不再使用它。确定继续吗？')) return
  try { await studyApi.deleteAdminQuestion(item.id, token.value); await loadCourseData(); notice.value = '题目已删除。' }
  catch (cause) { error.value = message(cause) }
}
</script>

<template>
  <main v-if="isAdmin" class="page-content content-admin-page">
    <header class="admin-heading"><button class="admin-back" @click="router.push('/courses')"><ArrowLeft :size="16"/>返回课程</button><div><span class="eyebrow">CURRICULUM WORKSPACE</span><h1>课程内容维护</h1><p>管理课程目录、知识节点、先修关系与练习题。</p></div></header>
    <section class="admin-access panel"><div class="admin-access-copy"><span class="admin-key-icon"><KeyRound :size="18"/></span><div><b>管理员验证</b><small>令牌仅保存在本页内存中，不会写入浏览器存储或前端构建文件。</small></div></div><div class="admin-token-row"><input v-model="token" type="password" autocomplete="off" placeholder="输入服务端 CONTENT_ADMIN_TOKEN" aria-label="课程内容管理令牌" @keydown.enter="connect"/><button class="btn btn-primary" :disabled="loading" @click="connect"><KeyRound :size="15"/>验证并加载</button></div></section>
    <p v-if="error" class="admin-message is-error" role="alert">{{error}}</p><p v-else-if="notice" class="admin-message is-success" role="status"><Check :size="15"/>{{notice}}</p>
    <section class="admin-toolbar panel"><label>当前课程<select v-model="courseId"><option value="" disabled>选择一门课程</option><option v-for="course in courses" :key="course.id" :value="course.id">{{course.name}}</option></select></label><span v-if="activeCourse">{{activeCourse.points}} 个目录知识点 · {{activeCourse.category}}</span><button class="btn btn-soft" :disabled="!token||loading" @click="loadCourseData"><RefreshCw :size="14"/>刷新内容</button></section>
    <section class="admin-grid">
      <article class="panel admin-editor"><header><div><h2>{{editingCourse?'编辑课程':'新增课程'}}</h2><p>课程信息保存在课程目录中。</p></div></header><div class="admin-fields"><label>课程 ID<input v-model="courseForm.id" :disabled="editingCourse" maxlength="80" placeholder="例：linear-algebra"/></label><label>课程名称<input v-model="courseForm.name" maxlength="160" placeholder="课程名称"/></label><label>课程分类<input v-model="courseForm.category" maxlength="80" placeholder="专业基础"/></label><label>知识点数量<input v-model.number="courseForm.points" type="number" min="0" max="100000"/></label><label class="span-two">当前章节<input v-model="courseForm.chapter" maxlength="240" placeholder="章节或当前学习位置"/></label><label>主题颜色<input v-model="courseForm.color" maxlength="20"/></label><label>图标<input v-model="courseForm.icon" maxlength="20"/></label></div><div class="admin-actions"><button class="btn btn-primary" :disabled="busy||!token" @click="saveCourse"><Save :size="14"/>保存课程</button><button class="btn btn-soft" @click="resetCourse">清空</button><button v-if="editingCourse" class="btn btn-danger" :disabled="busy" @click="removeCourse"><Trash2 :size="14"/>删除课程</button></div><div class="admin-course-list"><button v-for="course in courses" :key="course.id" @click="courseId=course.id;editCourse(course)"><span>{{course.name}}</span><small>{{course.id}} · {{course.category}}</small></button></div></article>
      <article class="panel admin-editor"><header><div><h2>{{editingNodeId?'编辑知识点':'新增知识点'}}</h2><p>{{activeCourse?.name||'请先选择课程'}} · 图谱节点</p></div></header><div class="admin-fields"><label>节点 ID<input v-model="nodeForm.id" :disabled="Boolean(editingNodeId)" maxlength="100" placeholder="唯一 ID"/></label><label>节点名称<input v-model="nodeForm.name" maxlength="180" placeholder="知识点名称"/></label><label>节点类型<select v-model="nodeForm.type"><option value="chapter">章节</option><option value="concept">知识点</option><option value="application">综合应用</option><option value="course">课程</option></select></label><label class="span-two">说明<textarea v-model="nodeForm.description" maxlength="5000" rows="3" placeholder="知识点说明"/></label></div><div class="admin-actions"><button class="btn btn-primary" :disabled="busy||!token||!courseId" @click="saveNode"><Save :size="14"/>保存知识点</button><button class="btn btn-soft" @click="resetNode">清空</button></div><div class="admin-list"><div v-for="node in nodes" :key="node.id"><span><b>{{node.name}}</b><small>{{node.id}} · {{node.type}}</small></span><span><button @click="editNode(node)">编辑</button><button class="danger-text" @click="removeNode(node)">删除</button></span></div><p v-if="!nodes.length" class="admin-empty">验证令牌并选择课程后加载图谱。</p></div></article>
      <article class="panel admin-editor"><header><div><h2>先修关系</h2><p>箭头方向为“先修知识 → 后续知识”。</p></div></header><div class="admin-fields"><label>先修节点<select v-model="newEdge.source"><option value="">选择节点</option><option v-for="node in nodes" :key="node.id" :value="node.id">{{node.name}}</option></select></label><label>后续节点<select v-model="newEdge.target"><option value="">选择节点</option><option v-for="node in availableTargets" :key="node.id" :value="node.id">{{node.name}}</option></select></label></div><div class="admin-actions"><button class="btn btn-soft" @click="addEdge"><Plus :size="14"/>添加关系</button><button class="btn btn-primary" :disabled="busy||!token||!courseId" @click="saveEdges"><Save :size="14"/>保存关系</button></div><div class="admin-list"><div v-for="(edge,index) in edges" :key="`${edge.source}-${edge.target}`"><span><b>{{nodes.find(node=>node.id===edge.source)?.name||edge.source}}</b><small><Link2 :size="12"/>{{nodes.find(node=>node.id===edge.target)?.name||edge.target}}</small></span><button class="danger-text" @click="edges.splice(index,1)">移除</button></div><p v-if="!edges.length" class="admin-empty">暂无先修关系。</p></div></article>
      <article class="panel admin-editor"><header><div><h2>{{editingQuestionId?'编辑练习题':'新增练习题'}}</h2><p>答案只向学生端在提交后返回。</p></div></header><div class="admin-fields"><label class="span-two">题干<textarea v-model="questionForm.title" maxlength="10000" rows="3" placeholder="输入题目内容"/></label><label>题型<select v-model="questionForm.type"><option>单选题</option><option>多选题</option><option>简答题</option></select></label><label>难度<select v-model="questionForm.difficulty"><option>基础</option><option>中等</option><option>较难</option></select></label><label>主题<input v-model="questionForm.topic" maxlength="160" placeholder="知识主题"/></label><label>关联知识点<select v-model="questionForm.conceptId"><option value="">不关联</option><option v-for="node in nodes" :key="node.id" :value="node.id">{{node.name}}</option></select></label><label class="span-two">选项<textarea v-model="questionForm.options" rows="3" placeholder="每行一个选项"/></label><label>正确答案<input v-model="questionForm.answer" placeholder="填写正确选项"/></label><label class="span-two">解析<textarea v-model="questionForm.explanation" maxlength="10000" rows="3" placeholder="题目解析"/></label></div><div class="admin-actions"><button class="btn btn-primary" :disabled="busy||!token||!courseId" @click="saveQuestion"><Save :size="14"/>保存题目</button><button class="btn btn-soft" @click="resetQuestion">清空</button></div><div class="admin-list"><div v-for="item in questions" :key="item.id"><span><b>{{item.title}}</b><small>#{{item.id}} · {{item.topic||item.difficulty}}</small></span><span><button @click="editQuestion(item)">编辑</button><button class="danger-text" @click="removeQuestion(item)">删除</button></span></div><p v-if="!questions.length" class="admin-empty">当前课程还没有练习题。</p></div></article>
    </section>
  </main>
  <main v-else class="page-content content-admin-page"><section class="panel admin-access-denied"><b>{{adminChecking?'正在验证管理员身份…':'仅课程内容管理员可以访问此页面。'}}</b></section></main>
</template>

<style scoped>
.content-admin-page{max-width:1440px;margin:0 auto;padding-bottom:32px}.admin-access-denied{padding:24px;color:#716b80;font-size:14px}.admin-heading{display:flex;align-items:flex-start;gap:24px;margin:10px 0 22px}.admin-back{display:inline-flex;align-items:center;gap:6px;padding:9px 12px;border:1px solid #e9e3f3;border-radius:10px;background:#fff;color:#665b82;cursor:pointer}.admin-heading .eyebrow{font-size:10px;letter-spacing:.16em;color:#8d6ce5}.admin-heading h1{margin:4px 0 5px;color:#2f2940;font-size:26px}.admin-heading p{margin:0;color:#827b91;font-size:13px}.admin-access,.admin-toolbar{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:14px;padding:16px 18px}.admin-access-copy{display:flex;align-items:center;gap:12px}.admin-key-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#f3edff;color:#7652d8}.admin-access-copy div,.admin-fields label,.admin-list span{display:grid;gap:5px}.admin-access-copy b{font-size:14px;color:#383246}.admin-access-copy small,.admin-toolbar>span{color:#898295;font-size:11px}.admin-token-row{display:flex;gap:8px;width:min(480px,55%)}.admin-token-row input,.admin-fields input,.admin-fields select,.admin-fields textarea,.admin-toolbar select{min-width:0;width:100%;border:1px solid #e8e3f0;border-radius:9px;background:#fff;padding:10px 11px;color:#423950;font:inherit;font-size:12px;outline:none}.admin-token-row input:focus,.admin-fields input:focus,.admin-fields select:focus,.admin-fields textarea:focus,.admin-toolbar select:focus{border-color:#9a7be8;box-shadow:0 0 0 3px #8b68df20}.admin-toolbar label{display:flex;align-items:center;gap:10px;color:#514966;font-size:12px}.admin-toolbar select{width:240px}.admin-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.admin-editor{min-width:0;padding:18px}.admin-editor>header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:15px}.admin-editor h2{margin:0;color:#393249;font-size:16px}.admin-editor header p{margin:5px 0 0;color:#918a9d;font-size:11px}.admin-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.admin-fields label{color:#675f75;font-size:11px}.admin-fields .span-two{grid-column:1/-1}.admin-fields input,.admin-fields select,.admin-fields textarea{box-sizing:border-box}.admin-fields input:disabled{background:#f5f3f8;color:#a39cad}.admin-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}.admin-actions .btn{display:inline-flex;align-items:center;gap:6px}.btn-danger{border:1px solid #f1d5d5;background:#fff7f7;color:#bb5151;border-radius:9px;padding:9px 12px;cursor:pointer}.admin-course-list,.admin-list{display:grid;max-height:300px;overflow:auto;margin-top:14px;border-top:1px solid #f0edf4}.admin-course-list button,.admin-list>div{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 4px;border-bottom:1px solid #f3f0f6;background:transparent;text-align:left;color:#514966}.admin-course-list button{display:grid;cursor:pointer}.admin-course-list small,.admin-list small{color:#958da1;font-size:10px}.admin-list span small{display:flex;align-items:center;gap:5px}.admin-list>div>span:last-child{display:flex;gap:9px}.admin-list button{border:0;background:transparent;color:#7654cf;font-size:11px;cursor:pointer}.admin-list .danger-text{color:#c35b5b}.admin-empty{padding:12px 4px;color:#9a93a4;font-size:11px}.admin-message{display:flex;align-items:center;gap:7px;margin:0 0 12px;padding:10px 13px;border-radius:10px;font-size:12px}.admin-message.is-error{background:#fff0f0;color:#ab4343}.admin-message.is-success{background:#effaf5;color:#277b5c}@media(max-width:850px){.admin-grid{grid-template-columns:1fr}.admin-access{align-items:stretch;flex-direction:column}.admin-token-row{width:100%}}@media(max-width:560px){.admin-heading{gap:10px;flex-direction:column}.admin-toolbar{align-items:stretch;flex-direction:column}.admin-toolbar label{align-items:flex-start;flex-direction:column}.admin-toolbar select{width:100%;box-sizing:border-box}.admin-fields{grid-template-columns:1fr}.admin-fields .span-two{grid-column:auto}.admin-token-row{flex-direction:column}}
</style>
