import { courses, graphLinks, graphNodes, questions } from '../mock/data'
import type { StudyTask } from '../types'

const delay = (ms = 220) => new Promise((resolve) => setTimeout(resolve, ms))
export const mockApi = {
  async dashboard() {
    await delay()
    const read = <T>(key: string, fallback: T): T => { try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback } catch { return fallback } }
    const savedTasks = read<StudyTask[]>('studypath.tasks', [])
    const mistakes = read<Array<{ mastered?: boolean }>>('studypath.learning-loop.mistakes', [])
    const history = read<Array<{ at: string; score: number }>>('studypath.quiz-history', [])
    const weekHours = Array.from({ length: 7 }, () => 0)
    const weekScores = Array.from({ length: 7 }, () => 0)
    const weekCounts = Array.from({ length: 7 }, () => 0)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const localDate = (date: Date) => date.toLocaleDateString('sv-SE')
    const weekDays = Array.from({ length: 7 }, (_, index) => {
      const date = new Date(today)
      date.setDate(date.getDate() - (6 - index))
      return localDate(date)
    })
    const activeDays = new Set<string>()
    for (const item of history) {
      const date = new Date(item.at)
      if (Number.isNaN(date.getTime())) continue
      const key = localDate(date)
      activeDays.add(key)
      const day = weekDays.indexOf(key)
      if (day < 0) continue
      weekScores[day] += item.score
      weekCounts[day] += 1
    }
    let streak = 0
    const cursor = new Date(today)
    if (!activeDays.has(localDate(cursor))) cursor.setDate(cursor.getDate() - 1)
    while (activeDays.has(localDate(cursor))) { streak += 1; cursor.setDate(cursor.getDate() - 1) }
    return { hoursToday: '—', mastered: mistakes.filter(item => item.mastered).length, weeklyTasks: savedTasks.filter(item => item.done).length, streak, weekHours, weekScores: weekScores.map((score, index) => weekCounts[index] ? Math.round(score / weekCounts[index]) : null), courses, tasks: savedTasks }
  },
  async getCourses() { await delay(); return courses },
  async getGraph() { await delay(300); return { nodes: graphNodes, links: graphLinks } },
  async getTasks(): Promise<StudyTask[]> { await delay(); try { return JSON.parse(localStorage.getItem('studypath.tasks') || '[]') as StudyTask[] } catch { return [] } },
  async saveTasks(items: StudyTask[]) { localStorage.setItem('studypath.tasks', JSON.stringify(items)); return items },
  async getQuestions() { await delay(180); return questions },
  async ask(question: string) {
    await delay(850)
    return { answer: `当前处于本地演示模式，问题“${question}”没有连接真实检索与生成服务，因此不会生成带引用的课程答案。请从“AI 智能答疑”进入已连接资料库的问答页面。`, sources: [] }
  },
}
