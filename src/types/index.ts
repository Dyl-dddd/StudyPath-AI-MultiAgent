export interface Course { id: string; name: string; category: string; progress: number; points: number; chapter: string; color: string; icon: string; }
export interface KnowledgeNode { id: string; name: string; type: 'course' | 'chapter' | 'concept' | 'application'; mastery: number; description: string; }
export interface StudyTask { id: number; title: string; course: string; date: string; priority: '高' | '中' | '低'; done: boolean; }
export interface Material { id: number; name: string; type: string; size: string; status: '待处理' | '处理中' | '已索引' | '失败'; course: string; date: string; }
export interface Question { id: number; type: string; difficulty: string; topic: string; title: string; options?: string[]; answer?: string | string[]; explanation?: string; course?: string; courseId?: string; conceptId?: string; misconceptions?: Record<string, string>; transferQuestionIds?: number[]; evidence?: { title: string; section: string; excerpt: string }; }
