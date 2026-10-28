import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { studyApi } from '../api'
import type { StudyTask } from '../types'

export const useStudyStore = defineStore('study', () => {
  const tasks = ref<StudyTask[]>([])
  const loaded = ref(false)
  const dark = ref(localStorage.getItem('studypath.theme') === 'dark')
  const taskCount = computed(() => tasks.value.filter((task) => !task.done).length)
  async function loadTasks() { if (!loaded.value) { tasks.value = await studyApi.tasks(); if (!tasks.value.length) { try { const legacy = JSON.parse(localStorage.getItem('studypath.tasks') || '[]') as StudyTask[]; if (legacy.length) { tasks.value = await studyApi.saveTasks(legacy); localStorage.removeItem('studypath.tasks') } } catch { /* Ignore malformed legacy browser state. */ } } loaded.value = true } }
  async function persist() { tasks.value = await studyApi.saveTasks(tasks.value) }
  async function toggleTask(id: number) { const item = tasks.value.find((task) => task.id === id); if (item) { const previous = item.done; item.done = !previous; try { await persist() } catch (error) { item.done = previous; throw error } } }
  async function addTask(title: string, course = '学习空间', date = `${new Date().toLocaleDateString('sv-SE')} · 09:00`) { const item: StudyTask = { id: Date.now(), title, course, date, priority: '中', done: false }; tasks.value.unshift(item); try { await persist() } catch (error) { tasks.value = tasks.value.filter((task) => task.id !== item.id); throw error } }
  function toggleTheme() { dark.value = !dark.value; document.documentElement.classList.toggle('dark-mode', dark.value); localStorage.setItem('studypath.theme', dark.value ? 'dark' : 'light') }
  if (dark.value) document.documentElement.classList.add('dark-mode')
  return { tasks, loaded, dark, taskCount, loadTasks, persist, toggleTask, addTask, toggleTheme }
})
