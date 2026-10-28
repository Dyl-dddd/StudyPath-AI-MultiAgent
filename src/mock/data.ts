import type { Course, KnowledgeNode, Question, StudyTask } from '../types'

export const courses: Course[] = [
  { id: 'ds', name: '数据结构', category: '专业基础', progress: 68, points: 42, chapter: '树与二叉树 · 二叉搜索树', color: '#7357dc', icon: '⌘' },
  { id: 'os', name: '操作系统', category: '专业基础', progress: 46, points: 38, chapter: '进程管理 · 同步与互斥', color: '#1caaa0', icon: '◉' },
  { id: 'net', name: '计算机网络', category: '专业核心', progress: 32, points: 36, chapter: '传输层 · TCP 拥塞控制', color: '#ed9a50', icon: '⌁' },
  { id: 'se', name: '软件工程', category: '专业选修', progress: 82, points: 31, chapter: '软件测试 · 单元测试', color: '#ed6d9a', icon: '✳' },
  { id: 'db', name: '数据库系统', category: '专业基础', progress: 57, points: 35, chapter: '关系数据库 · SQL 查询', color: '#587be6', icon: '▤' },
  { id: 'co', name: '计算机组成原理', category: '专业核心', progress: 24, points: 40, chapter: '存储系统 · Cache 映射', color: '#9a6cc4', icon: '▦' },
]

export const graphNodes: KnowledgeNode[] = [
  ['ds','数据结构','course',82,'研究数据的组织、存储与处理方式。'],['linear','线性结构','chapter',76,'数据元素之间存在一对一的顺序关系。'],['array','顺序表','concept',91,'使用连续存储单元实现的线性表。'],['list','链表','concept',68,'通过指针连接离散存储结点的线性表。'],['stack','栈','concept',73,'仅允许在栈顶进行插入和删除的线性结构。'],['queue','队列','concept',61,'遵循先进先出原则的线性结构。'],['tree','树与二叉树','chapter',58,'具有层次关系的非线性数据结构。'],['binary','二叉树','concept',67,'每个结点最多有两个子结点的树。'],['bst','二叉搜索树','concept',42,'左子树键值较小、右子树键值较大的二叉树。'],['avl','平衡二叉树','concept',35,'通过旋转操作维持高度平衡的搜索树。'],['heap','堆','concept',54,'满足堆序性质的完全二叉树。'],['traverse','树的遍历','concept',49,'按特定顺序访问树中所有结点。'],['graph','图','chapter',62,'由顶点和边构成的网状数据结构。'],['bfs','广度优先搜索','concept',28,'按层次逐步扩展访问顶点的图算法。'],['dfs','深度优先搜索','concept',39,'沿路径深入访问顶点的图算法。'],['sort','排序算法','chapter',70,'将数据元素按关键字重新排列。'],['quick','快速排序','concept',63,'基于分治思想的高效比较排序算法。'],['merge','归并排序','concept',51,'将有序子序列合并的分治排序算法。'],['search','查找算法','chapter',59,'在数据集合中定位目标元素的方法。'],['hash','散列表','concept',44,'通过散列函数实现快速查找的数据结构。'],['dp','动态规划','application',33,'将复杂问题分解为重叠子问题并复用结果。'],['complexity','复杂度分析','concept',77,'描述算法随输入规模增长的资源消耗。'],
  ['trie','字典树','concept',38,'利用字符串前缀共享路径，支持高效的前缀检索。'],['rbtree','红黑树','concept',41,'通过颜色与旋转规则维持平衡的二叉搜索树。'],['threaded','线索二叉树','concept',46,'利用空指针保存遍历前驱或后继信息。'],['priority','优先队列','concept',57,'按优先级而非到达顺序取出元素，常用堆实现。'],['radixsort','基数排序','concept',48,'按位或关键字分组进行多轮稳定排序。'],['topological','拓扑排序','concept',53,'对有向无环图中的依赖关系进行线性排序。'],['mst','最小生成树','concept',36,'连接连通图所有顶点且总权重最小的生成树。'],['collision','散列冲突处理','concept',43,'通过链地址法或开放定址法解决散列冲突。'],
].map(([id,name,type,mastery,description]) => ({ id: String(id), name: String(name), type: type as KnowledgeNode['type'], mastery: Number(mastery), description: String(description) }))

export const graphLinks = [
  ['ds','linear'],['ds','tree'],['ds','graph'],['ds','sort'],['ds','search'],['ds','complexity'],['linear','array'],['linear','list'],['linear','stack'],['linear','queue'],['tree','binary'],['binary','bst'],['bst','avl'],['binary','heap'],['binary','traverse'],['graph','bfs'],['graph','dfs'],['sort','quick'],['sort','merge'],['search','hash'],['complexity','dp'],['array','sort'],['stack','dfs'],['queue','bfs'],['tree','threaded'],['bst','rbtree'],['heap','priority'],['search','trie'],['hash','collision'],['sort','radixsort'],['graph','topological'],['graph','mst'],
].map(([source,target]) => ({ source, target }))

export const tasks: StudyTask[] = [
  { id: 1, title: '复习二叉搜索树的插入与删除', course: '数据结构', date: '今天 · 14:00', priority: '高', done: false },
  { id: 2, title: '完成进程同步章节练习', course: '操作系统', date: '今天 · 19:30', priority: '中', done: false },
  { id: 3, title: '整理 TCP 拥塞控制笔记', course: '计算机网络', date: '明天 · 10:00', priority: '低', done: false },
]

export const questions: Question[] = [
  { id: 1, type: '单选题', difficulty: '基础', topic: '二叉搜索树', course: '数据结构', conceptId: 'bst', title: '在一棵二叉搜索树中查找元素，平均时间复杂度与哪项最相关？', options: ['树的高度', '结点的颜色', '叶子结点的数量', '树的度数'], answer: '树的高度', misconceptions: { '结点的颜色': '把红黑树等平衡机制误当成所有二叉搜索树查找成本的直接决定因素。', '叶子结点的数量': '关注了结点总量特征，但查找实际沿根到目标的路径进行。', '树的度数': '混淆了树的分支数与查找路径长度。' }, transferQuestionIds: [6], evidence: { title: '二叉搜索树知识卡（内置示例）', section: '查找复杂度', excerpt: '查找沿根结点到目标结点的路径进行，时间复杂度由树高 h 决定，为 O(h)。树平衡时约为 O(log n)，退化时最坏为 O(n)。' }, explanation: '查找过程沿树高方向进行，平均时间复杂度为 O(h)。当树较平衡时为 O(log n)，退化时可能为 O(n)。' },
  { id: 2, type: '判断题', difficulty: '基础', topic: '栈与队列', course: '数据结构', conceptId: 'queue', title: '队列是一种先进后出的数据结构。', options: ['正确', '错误'], answer: '错误', misconceptions: { '正确': '把队列的 FIFO 和栈的 LIFO 顺序混淆了。' }, transferQuestionIds: [7], evidence: { title: '栈与队列知识卡（内置示例）', section: '队列的访问顺序', excerpt: '队列遵循先进先出（FIFO）：先进入队列的元素先离开；栈遵循后进先出（LIFO）。' }, explanation: '队列遵循先进先出（FIFO），栈才是后进先出（LIFO）。' },
  { id: 3, type: '多选题', difficulty: '进阶', topic: '图遍历', course: '数据结构', conceptId: 'bfs', title: '关于图的广度优先搜索（BFS），下列说法正确的是？', options: ['通常使用队列实现', '可用于求无权图最短路径', '递归是唯一实现方式', '按层次扩展访问顶点'], answer: ['通常使用队列实现','可用于求无权图最短路径','按层次扩展访问顶点'], misconceptions: { '递归是唯一实现方式': '把深度优先搜索常见的递归实现误套到了 BFS；BFS 通常用队列维护待访问结点。' }, transferQuestionIds: [8], evidence: { title: '广度优先搜索知识卡（内置示例）', section: '队列与层序扩展', excerpt: 'BFS 使用队列按层次扩展顶点，因此可在无权图中求从起点出发的最短路径。' }, explanation: 'BFS 使用队列按层次扩展，适合求无权图的单源最短路径。深度优先搜索更常使用递归或栈。' },
  { id: 4, type: '单选题', difficulty: '进阶', topic: '排序算法', course: '数据结构', conceptId: 'merge', title: '对 n 个元素进行归并排序，最坏情况下的时间复杂度是？', options: ['O(n)', 'O(n log n)', 'O(log n)', 'O(n²)'], answer: 'O(n log n)', misconceptions: { 'O(n)': '只计算了一层合并成本，忽略了递归树的对数层数。', 'O(log n)': '只考虑了递归层数，忽略每层对全部元素的合并。', 'O(n²)': '把简单排序的最坏复杂度误套到了归并排序。' }, evidence: { title: '归并排序知识卡（内置示例）', section: '时间复杂度', excerpt: '归并排序递归树有 O(log n) 层，每层合并总成本 O(n)，因此最坏时间复杂度为 O(n log n)。' }, explanation: '归并排序每一层合并需要 O(n) 时间，递归树高度为 O(log n)，总时间复杂度为 O(n log n)。' },
  { id: 5, type: '简答题', difficulty: '进阶', topic: '动态规划', course: '数据结构', conceptId: 'dp', title: '简述动态规划中“重叠子问题”的含义。', answer: '', evidence: { title: '动态规划知识卡（内置示例）', section: '重叠子问题', excerpt: '重叠子问题是指递归求解中相同子问题会反复出现；动态规划通过保存子问题结果避免重复计算。' }, explanation: '重叠子问题指递归求解过程中，相同的子问题会被重复计算。动态规划通过保存子问题结果减少重复工作。' },
  { id: 6, type: '单选题', difficulty: '基础', topic: '二叉搜索树', course: '数据结构', conceptId: 'bst', title: '插入一个新键值后，若二叉搜索树严重偏斜，查找性能最可能如何变化？', options: ['仍为 O(log n)', '可能退化到 O(n)', '变为 O(1)', '只与叶子数量有关'], answer: '可能退化到 O(n)', misconceptions: { '仍为 O(log n)': '把平衡树的性质误认为普通二叉搜索树始终具备。', '变为 O(1)': '忽略查找仍需沿树中的路径逐层比较。', '只与叶子数量有关': '复杂度主要取决于树高，而不是叶子数量。' }, evidence: { title: '二叉搜索树知识卡（内置示例）', section: '退化情形', excerpt: '普通二叉搜索树不保证平衡；当树退化成链表时，树高为 O(n)，查找最坏为 O(n)。' }, explanation: '普通二叉搜索树不保证平衡，偏斜时高度可能达到 n，查找最坏为 O(n)。' },
  { id: 7, type: '单选题', difficulty: '基础', topic: '栈与队列', course: '数据结构', conceptId: 'queue', title: '打印队列中，最早提交的打印任务通常会怎样处理？', options: ['最后打印', '最先打印', '随机打印', '按任务大小决定'], answer: '最先打印', misconceptions: { '最后打印': '将队列误认为栈，颠倒了先进先出顺序。', '随机打印': '误以为队列不保留任务到达顺序。', '按任务大小决定': '混淆了普通队列与优先队列。' }, evidence: { title: '栈与队列知识卡（内置示例）', section: '队列的应用', excerpt: '普通队列按先进先出规则处理任务，因此先入队的打印任务先被服务。' }, explanation: '普通队列按先进先出处理任务，先提交的打印任务位于队首并先被处理。' },
  { id: 8, type: '单选题', difficulty: '进阶', topic: '图遍历', course: '数据结构', conceptId: 'bfs', title: '无权图中从起点到某顶点的最少边数，适合用哪种遍历求得？', options: ['深度优先搜索', '广度优先搜索', '先序遍历', '快速排序'], answer: '广度优先搜索', misconceptions: { '深度优先搜索': 'DFS 可能先走入较深路径，不按距离层次保证最少边数。', '先序遍历': '混淆了树的访问序与一般图的最短路遍历。', '快速排序': '把排序算法与图最短路径问题混淆。' }, evidence: { title: '广度优先搜索知识卡（内置示例）', section: '无权图最短路径', excerpt: 'BFS 按距起点的边数逐层访问结点，首次到达目标时得到无权图中的最少边数。' }, explanation: 'BFS 按距起点的边数逐层访问顶点，首次到达目标时得到无权图中的最少边数。' },
]

export const weekHours = [0.8, 1.4, 1.1, 2.2, 1.6, 2.8, 1.9]
