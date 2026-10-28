import axios from 'axios'
import { authState, clearCredentials } from '../rag/api'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 12000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use((response) => response, (error) => {
  if (error?.response?.status === 401) {
    clearCredentials()
    window.dispatchEvent(new Event('studypath:auth-expired'))
  }
  const message = error?.response?.data?.message || error?.response?.data?.detail || (error?.code === 'ECONNABORTED' ? '请求耗时较长，请稍后重试' : '') || error.message || '请求失败，请稍后重试'
  return Promise.reject(new Error(message))
})

api.interceptors.request.use((config) => {
  if (authState.token) config.headers.Authorization = `Bearer ${authState.token}`
  return config
})

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
