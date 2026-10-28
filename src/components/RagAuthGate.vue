<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { BookOpen, BrainCircuit, Eye, EyeOff, LockKeyhole, Network, RefreshCw, UserRound } from 'lucide-vue-next'
import { authState, clearCredentials, ragRequest, setCredentials } from '../rag/api'
import '../styles/rag-auth.css'

const emit = defineEmits<{ authenticated: [] }>()
const mode = ref<'login'|'register'>('login')
const username = ref(''); const password = ref(''); const busy = ref(false); const error = ref('')
const showPassword = ref(false)
const confirmPassword = ref(''); const captchaId = ref(''); const captchaImage = ref(''); const captchaCode = ref(''); const captchaLoading = ref(false); const captchaError = ref('')
onMounted(async () => {
  if (!authState.token) return
  try { await ragRequest('/auth/me'); emit('authenticated') } catch { clearCredentials() }
})
async function submit() {
  error.value = ''
  if (username.value.trim().length < 3 || password.value.length < 10) { error.value = '用户名至少 3 位，密码至少 10 位'; return }
  if (mode.value === 'register' && password.value !== confirmPassword.value) { error.value = '两次输入的密码不一致'; return }
  if (mode.value === 'register' && (!captchaId.value || captchaCode.value.trim().length !== 5)) { error.value = '请填写 5 位图形验证码'; return }
  busy.value = true
  try {
    const payload = { username: username.value.trim(), password: password.value, ...(mode.value === 'register' ? { password_confirm: confirmPassword.value, captcha_id: captchaId.value, captcha_code: captchaCode.value.trim().toUpperCase() } : {}) }
    const result = await ragRequest<{access_token:string;username:string;user_id:string}>(`/auth/${mode.value}`, { method: 'POST', body: JSON.stringify(payload) })
    setCredentials(result); emit('authenticated')
  } catch (e) {
    error.value = e instanceof Error ? e.message : mode.value === 'register' ? '注册失败，请稍后重试' : '登录失败'
    if (mode.value === 'register') await refreshCaptcha()
  }
  finally { busy.value = false }
}
async function refreshCaptcha() {
  captchaLoading.value = true; captchaError.value = ''; captchaCode.value = ''; captchaId.value = ''; captchaImage.value = ''
  try {
    const challenge = await ragRequest<{ captcha_id: string; image_data: string }>('/auth/captcha')
    captchaId.value = challenge.captcha_id; captchaImage.value = challenge.image_data
  } catch (e) {
    captchaId.value = ''; captchaImage.value = ''
    captchaError.value = e instanceof Error ? e.message : '验证码加载失败，请重试'
  } finally { captchaLoading.value = false }
}
function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''; confirmPassword.value = ''; captchaCode.value = ''; captchaError.value = ''
  if (mode.value === 'register') void refreshCaptcha()
}
</script>

<template>
  <main class="rag-auth-screen">
    <section class="rag-auth-brand" aria-label="StudyPath AI 产品介绍">
      <div class="rag-auth-brand-top"><span class="rag-auth-brand-mark"><BookOpen :size="22"/></span><span><strong>智学研途</strong><small>STUDYPATH AI</small></span></div>
      <div class="rag-auth-brand-copy"><p class="rag-eyebrow"><i></i> AI 驱动的个性化学习空间</p><h1>让每一段学习，<br/><span>都看得见成长。</span></h1><p>把课程资料、知识脉络与智能答疑放进同一条学习路径，让理解逐步沉淀为自己的能力。</p></div>
      <div class="rag-auth-visual" aria-hidden="true"><div class="rag-auth-liquid"></div><div class="rag-auth-glass"><div><BrainCircuit :size="48" stroke-width="1.45"/></div></div><div class="rag-auth-float float-one"><Network :size="18"/><span><b>知识关联</b><small>让概念彼此连接</small></span></div><div class="rag-auth-float float-two"><BookOpen :size="18"/><span><b>循序渐进</b><small>沿着你的节奏学习</small></span></div></div>
      <div class="rag-auth-foot">把资料变成理解，把理解变成进步。</div>
    </section>
    <section class="rag-auth-panel" aria-label="账号登录">
      <div class="rag-auth-card">
        <div class="rag-auth-card-head"><div class="rag-auth-mark"><BookOpen :size="22"/></div><span><strong>智学研途</strong><small>STUDYPATH AI · PRIVATE WORKSPACE</small></span></div>
        <h2>{{ mode==='login' ? '欢迎回来' : '开启你的学习空间' }}</h2>
        <p class="rag-muted">{{ mode==='login' ? '登录后继续你的个性化学习旅程。' : '创建账号，安全保存你的学习资料与进度。' }}</p>
        <form class="rag-auth-form" @submit.prevent="submit" :aria-busy="busy">
          <label><span>用户名</span><div><UserRound :size="18" aria-hidden="true"/><input v-model="username" autocomplete="username" minlength="3" maxlength="48" required placeholder="请输入用户名"/></div></label>
          <label><span>密码</span><div><LockKeyhole :size="18" aria-hidden="true"/><input v-model="password" :autocomplete="mode==='login'?'current-password':'new-password'" :type="showPassword?'text':'password'" minlength="10" required placeholder="至少 10 位"/><button class="rag-password-toggle" type="button" :aria-label="showPassword?'隐藏密码':'显示密码'" :aria-pressed="showPassword" @click="showPassword=!showPassword"><EyeOff v-if="showPassword" :size="17"/><Eye v-else :size="17"/></button></div></label>
          <label v-if="mode==='register'"><span>确认密码</span><div><LockKeyhole :size="18" aria-hidden="true"/><input v-model="confirmPassword" autocomplete="new-password" :type="showPassword?'text':'password'" minlength="10" required placeholder="再次输入密码"/></div></label>
          <label v-if="mode==='register'" class="rag-captcha-label"><span>图形验证码</span><div class="rag-captcha-row"><div class="rag-captcha-input"><BrainCircuit :size="17" aria-hidden="true"/><input v-model="captchaCode" autocomplete="off" autocapitalize="characters" maxlength="5" minlength="5" required placeholder="输入图片中的 5 位字符" aria-label="图形验证码"/></div><button class="rag-captcha-refresh" type="button" :disabled="captchaLoading" aria-label="刷新验证码" @click="refreshCaptcha"><img v-if="captchaImage" :src="captchaImage" alt="5 位图形验证码"/><span v-else>{{ captchaLoading?'加载中':'验证码' }}</span><RefreshCw :size="15"/></button></div><small class="rag-captcha-help" aria-live="polite">{{ captchaError || '看不清？点击验证码图片刷新。' }}</small></label>
          <p v-if="error" class="rag-error" role="alert">{{ error }}</p>
          <button class="rag-button primary wide" :disabled="busy"><span v-if="busy" class="rag-spinner" aria-hidden="true"></span>{{ busy ? '正在连接…' : mode==='login' ? '登录学习空间' : '注册并登录' }}</button>
        </form>
        <button class="rag-link-button" type="button" @click="switchMode">{{ mode==='login' ? '首次使用？创建账号' : '已有账号？返回登录' }}</button>
        <small>账号资料仅用于本学习空间；请勿在此输入模型 API 密钥。</small>
      </div>
    </section>
  </main>
</template>
