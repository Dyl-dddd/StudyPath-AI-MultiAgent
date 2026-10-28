import { reactive } from 'vue'
import { studyApi } from '../api'
import { USE_MOCK } from '../api/client'

export interface StudyProfile {
  name: string
  school: string
  major: string
  grade: string
  educationStage: string
  learningSubjects: string[]
  learningGoal: string
  bio: string
}

const storageKey = 'studypath.profile'
const defaults: StudyProfile = {
  name: '',
  school: '',
  major: '',
  grade: '',
  educationStage: '大学',
  learningSubjects: [],
  learningGoal: '',
  bio: '',
}

function readProfile(): StudyProfile {
  try {
    const saved = localStorage.getItem(storageKey)
    return saved ? { ...defaults, ...JSON.parse(saved) as Partial<StudyProfile> } : { ...defaults }
  } catch {
    return { ...defaults }
  }
}

export const profileState = reactive<StudyProfile>(readProfile())

export async function loadProfile() {
  if (USE_MOCK) return
  let saved = await studyApi.profile() as StudyProfile & { weeklyGoalHours:number; dailyFocusHours:number; learningReminders:boolean }
  const legacy = readProfile()
  if (!saved.name && !saved.school && !saved.major && !saved.grade && !saved.bio && Object.values(legacy).some(Boolean)) {
    saved = await studyApi.saveProfile(legacy) as typeof saved
    localStorage.removeItem(storageKey)
  }
  Object.assign(profileState, { name:saved.name, school:saved.school, major:saved.major, grade:saved.grade, educationStage:saved.educationStage || '大学', learningSubjects:saved.learningSubjects || [], learningGoal:saved.learningGoal || '', bio:saved.bio })
  return saved
}

export async function saveProfile(profile: StudyProfile) {
  const normalized = { ...profile, name: profile.name.trim() }
  if (!USE_MOCK) {
    const saved = await studyApi.saveProfile(normalized) as StudyProfile
    Object.assign(profileState, saved)
    return
  }
  Object.assign(profileState, normalized)
  localStorage.setItem(storageKey, JSON.stringify(normalized))
}
