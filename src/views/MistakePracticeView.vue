<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, CheckCheck, LoaderCircle, RefreshCw, Sparkles, Target, X } from 'lucide-vue-next'
import { studyApi } from '../api'

interface VariantQuestion { id: number; title: string; options: string[] }
interface VariantResult { id: number; correct: boolean; answer: string; explanation: string }
interface VariantSet { setId: string; course: string; topic: string; sourceTitle: string; conceptDescription: string; difficulty: string; variants: VariantQuestion[] }
const route = useRoute()
const router = useRouter()
const questionId = Number(route.params.questionId)
const data = ref<VariantSet | null>(null)
const answers = ref<Record<number, string>>({})
const loading = ref(true)
const submitting = ref(false)
const submitted = ref(false)
const error = ref('')
const grade = ref<{correctCount:number;total:number;results:VariantResult[]}|null>(null)
const answeredCount = computed(() => Object.values(answers.value).filter(Boolean).length)
const correctCount = computed(() => grade.value?.correctCount || 0)
const score = computed(() => Math.round(correctCount.value / Math.max(1, grade.value?.total || 0) * 100))

async function loadVariants() {
  loading.value = true
  error.value = ''
  submitted.value = false
  grade.value = null
  answers.value = {}
  try {
    if (!Number.isInteger(questionId) || questionId <= 0) throw new Error('错题编号无效。')
    data.value = await studyApi.generateMistakeVariants(questionId) as VariantSet
    if (data.value.variants.length !== 3) throw new Error('暂时没有生成完整的三道练习题，请重试。')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '变式题生成失败，请重试。'
  } finally {
    loading.value = false
  }
}

async function submitPractice() {
  if (!data.value || answeredCount.value !== 3) {
    error.value = '请先完成全部三道题。'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    grade.value = await studyApi.submitMistakeVariants(questionId, data.value.setId, Object.fromEntries(data.value.variants.map(item => [String(item.id), answers.value[item.id]]))) as {correctCount:number;total:number;results:VariantResult[]}
    submitted.value = true
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '复习记录保存失败，请重试。'
  } finally {
    submitting.value = false
  }
}

onMounted(loadVariants)
</script>

<template>
  <main class="page-content variant-page">
    <button class="variant-back" @click="router.push('/mistakes')"><ArrowLeft :size="15"/>返回错题本</button>
    <header class="variant-heading">
      <span class="variant-icon"><Sparkles :size="19"/></span>
      <div><span class="variant-eyebrow">TRANSFER PRACTICE</span><h1>举一反三练习</h1><p>围绕同一考点生成三道新题，换个情境检验理解。</p></div>
    </header>

    <section v-if="loading" class="panel variant-state"><LoaderCircle class="variant-spin" :size="20"/>正在生成三道不同情境的变式题，请稍候（最多可能需要一分钟）…</section>
    <section v-else-if="error && !data" class="panel variant-state variant-error"><b>{{error}}</b><button class="btn btn-primary" @click="loadVariants"><RefreshCw :size="14"/>重新生成</button></section>
    <template v-else-if="data">
      <section class="panel variant-context"><div class="variant-context-top"><span><Target :size="14"/>{{data.course}} · {{data.topic}}</span><span>{{data.difficulty}}</span></div><h2>本次练习对应的错题</h2><p class="variant-source">{{data.sourceTitle}}</p><p class="variant-concept">{{data.conceptDescription}}</p><small>下面只练新题，不会重复这道原题。</small></section>

      <section v-if="submitted" class="panel variant-result" :class="{'all-correct':score===100}">
        <span class="variant-result-icon"><CheckCheck v-if="score===100" :size="20"/><Target v-else :size="20"/></span>
        <div><h2>{{score===100?'三道全对，掌握得很扎实！':`本轮答对 ${correctCount}/3`}}</h2><p>{{score===100?'错题复习记录已更新，间隔复测后即可确认掌握。':'错题复习记录已更新，查看解析后再练一次会更稳。'}}</p></div>
        <strong>{{score}}<small>%</small></strong>
      </section>

      <section class="variant-list">
        <article v-for="(item,index) in data.variants" :key="item.id" class="panel variant-card">
          <div class="variant-card-top"><span>变式 {{index+1}} / 3</span><span>{{data.difficulty}} · 单选题</span></div>
          <h2>{{item.title}}</h2>
          <div class="variant-options">
            <button v-for="(option,optionIndex) in item.options" :key="optionIndex" :disabled="submitted" :class="{chosen:answers[item.id]===option,correct:submitted&&option===grade?.results.find(result=>result.id===item.id)?.answer,incorrect:submitted&&answers[item.id]===option&&option!==grade?.results.find(result=>result.id===item.id)?.answer}" @click="answers[item.id]=option">
              <span>{{String.fromCharCode(65+optionIndex)}}</span>{{option}}<Check v-if="submitted&&option===grade?.results.find(result=>result.id===item.id)?.answer" :size="15"/><X v-else-if="submitted&&answers[item.id]===option" :size="15"/>
            </button>
          </div>
          <div v-if="submitted" class="variant-explanation"><b>{{grade?.results.find(result=>result.id===item.id)?.correct?'回答正确':'再留意这个考点'}}</b><p>{{grade?.results.find(result=>result.id===item.id)?.explanation}}</p></div>
        </article>
      </section>

      <p v-if="error" class="variant-inline-error" role="alert">{{error}}</p>
      <div class="variant-actions">
        <span>{{submitted?'三道题的答案与解析已显示':`已完成 ${answeredCount}/3 道`}}</span>
        <button v-if="!submitted" class="btn btn-primary" :disabled="submitting" @click="submitPractice"><LoaderCircle v-if="submitting" class="variant-spin" :size="14"/><Check v-else :size="14"/>{{submitting?'正在保存':'提交练习'}}</button>
        <template v-else><button class="btn btn-secondary" @click="router.push('/mistakes')">返回错题本</button><button class="btn btn-primary" @click="loadVariants"><RefreshCw :size="14"/>再练三题</button></template>
      </div>
    </template>
  </main>
</template>

<style scoped>
.variant-page{max-width:1000px;margin:0 auto;padding-bottom:36px}.variant-back{display:inline-flex;align-items:center;gap:6px;margin:3px 0 17px;padding:7px 10px;border:1px solid #e9e5ef;border-radius:8px;background:#fff;color:#706a7e;font-size:12px;cursor:pointer}.variant-heading{display:flex;align-items:center;gap:13px;margin-bottom:18px}.variant-icon{width:43px;height:43px;display:grid;place-items:center;border-radius:13px;background:#f0eaff;color:#7654d2}.variant-eyebrow{color:#9b87c8;font-size:10px;font-weight:700;letter-spacing:.14em}.variant-heading h1{margin:3px 0;color:#393448;font-size:23px}.variant-heading p{margin:0;color:#918c9b;font-size:13px}.variant-context{padding:16px 18px;margin-bottom:13px}.variant-context-top{display:flex;align-items:center;justify-content:space-between;color:#7c61bd;font-size:12px}.variant-context-top span:first-child{display:flex;align-items:center;gap:5px}.variant-context h2{margin:13px 0 5px;color:#514c60;font-size:13px}.variant-source{margin:0;color:#494457;font-size:14px;font-weight:650;line-height:1.6}.variant-concept{margin:8px 0;color:#7f7a8b;font-size:12px;line-height:1.7}.variant-context>small{color:#9b96a4;font-size:11px}.variant-list{display:flex;flex-direction:column;gap:12px}.variant-card{padding:17px 19px}.variant-card-top{display:flex;justify-content:space-between;color:#8f7abf;font-size:11px}.variant-card h2{margin:11px 0 13px;color:#3f3a50;font-size:15px;line-height:1.7}.variant-options{display:grid;grid-template-columns:1fr 1fr;gap:8px}.variant-options button{min-height:40px;display:flex;align-items:center;gap:9px;padding:8px 10px;border:1px solid #eeeaf3;border-radius:8px;background:white;color:#5b5669;text-align:left;font-size:12px;line-height:1.5;cursor:pointer}.variant-options button:hover:not(:disabled),.variant-options button.chosen{border-color:#a78be3;background:#faf8ff}.variant-options button>span{width:21px;height:21px;display:grid;place-items:center;flex:none;border-radius:6px;background:#f2eff8;color:#7961b4;font-size:11px;font-weight:700}.variant-options button>svg{margin-left:auto;flex:none;color:#43a286}.variant-options button.incorrect{border-color:#e8b5b8;background:#fff8f8}.variant-options button.incorrect>svg{color:#ca686e}.variant-options button.correct{border-color:#b9e1d1;background:#f6fcf9}.variant-options button.correct>span{background:#dff2e9;color:#398a72}.variant-explanation{margin-top:12px;padding:10px 12px;border-radius:8px;background:#f8f6fb}.variant-explanation b{color:#5d4a8c;font-size:12px}.variant-explanation p{margin:4px 0 0;color:#777284;font-size:12px;line-height:1.65}.variant-result{display:flex;align-items:center;gap:12px;padding:14px 17px;margin-bottom:13px;border-color:#eadff9;background:#fcfaff}.variant-result.all-correct{border-color:#d4eee3;background:#f7fcf9}.variant-result-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:11px;background:#eee8fa;color:#7253c8}.variant-result.all-correct .variant-result-icon{background:#e4f5ed;color:#3d9a7d}.variant-result h2{margin:0;color:#474156;font-size:14px}.variant-result p{margin:4px 0 0;color:#898494;font-size:11px}.variant-result>strong{margin-left:auto;color:#7252c4;font-size:21px}.variant-result>strong small{font-size:12px}.variant-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:13px}.variant-actions>span{margin-right:auto;color:#9994a2;font-size:12px}.variant-actions .btn,.variant-state .btn{display:inline-flex;align-items:center;gap:6px}.variant-state{min-height:150px;display:flex;align-items:center;justify-content:center;gap:12px;color:#777184;font-size:13px}.variant-state.variant-error{flex-direction:column}.variant-inline-error{color:#bc5960;font-size:12px}.variant-spin{animation:variant-spin .9s linear infinite}@keyframes variant-spin{to{transform:rotate(360deg)}}@media(max-width:620px){.variant-options{grid-template-columns:1fr}.variant-card{padding:14px}.variant-result{align-items:flex-start}.variant-actions{flex-wrap:wrap}.variant-actions>span{width:100%;margin-bottom:4px}}
</style>
