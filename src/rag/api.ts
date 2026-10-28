import { reactive } from 'vue'

const API_BASE = import.meta.env.VITE_RAG_API_BASE_URL || 'http://localhost:8000/api'
const saved = (() => {
  try { return JSON.parse(localStorage.getItem('studypath.rag.auth') || 'null') } catch { return null }
})()

export const authState = reactive<{ token: string; username: string; userId: string }>({
  token: saved?.token || '', username: saved?.username || '', userId: saved?.userId || '',
})

export function setCredentials(data: { access_token: string; username: string; user_id: string }) {
  authState.token = data.access_token
  authState.username = data.username
  authState.userId = data.user_id
  localStorage.setItem('studypath.rag.auth', JSON.stringify({ token: authState.token, username: authState.username, userId: authState.userId }))
}

export function clearCredentials() {
  authState.token = ''; authState.username = ''; authState.userId = ''
  localStorage.removeItem('studypath.rag.auth')
}

export async function ragRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (authState.token) headers.set('Authorization', `Bearer ${authState.token}`)
  if (!(init.body instanceof FormData) && init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (response.status === 401) {
    clearCredentials()
    window.dispatchEvent(new Event('studypath:auth-expired'))
  }
  if (!response.ok) {
    let detail = `请求失败 (${response.status})`
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : detail } catch { /* response may not be JSON */ }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function ragPath(path: string) { return `${API_BASE}${path}` }
