import { reactive } from 'vue'
import { studyApi } from '../api'
import { USE_MOCK } from '../api/client'

export interface StudyPreferences {
  weeklyGoalHours: number
  dailyFocusHours: number
  learningReminders: boolean
}

const key = 'studypath.preferences'
const defaults: StudyPreferences = { weeklyGoalHours: 18, dailyFocusHours: 2, learningReminders: true }

function read(): StudyPreferences {
  try {
    const value = JSON.parse(localStorage.getItem(key) || 'null') as Partial<StudyPreferences> | null
    return { ...defaults, ...value }
  } catch {
    return { ...defaults }
  }
}

export const preferences = reactive<StudyPreferences>(read())

export async function loadPreferences() {
  if (USE_MOCK) return
  let value = await studyApi.profile() as StudyPreferences
  const legacy = read()
  const defaultsMatch = value.weeklyGoalHours === defaults.weeklyGoalHours && value.dailyFocusHours === defaults.dailyFocusHours && value.learningReminders === defaults.learningReminders
  const legacyChanged = legacy.weeklyGoalHours !== defaults.weeklyGoalHours || legacy.dailyFocusHours !== defaults.dailyFocusHours || legacy.learningReminders !== defaults.learningReminders
  if (defaultsMatch && legacyChanged) {
    value = await studyApi.saveProfile(legacy) as StudyPreferences
    localStorage.removeItem(key)
  }
  Object.assign(preferences, value)
}

export async function savePreferences() {
  if (!USE_MOCK) {
    await studyApi.saveProfile(preferences)
    return
  }
  localStorage.setItem(key, JSON.stringify(preferences))
}
