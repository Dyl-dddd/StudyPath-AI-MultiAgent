"""Compact, editable starter curricula for courses with no imported syllabus yet."""

DEFAULT_CURRICULA: dict[str, list[tuple[str, str, str, str, str]]] = {
    # tuple: node id, name, type, description, parent id
    "os": [
        ("os-process", "进程管理", "chapter", "操作系统对进程的创建、调度、同步和通信进行管理。", "os"),
        ("os-process-state", "进程状态与转换", "concept", "进程在就绪、运行、阻塞等状态之间转换；状态转换由调度、等待事件和事件完成等条件触发。", "os-process"),
        ("os-scheduling", "处理器调度", "concept", "调度器根据调度算法从就绪队列选择进程，常见目标包括响应时间、吞吐量与公平性。", "os-process"),
        ("os-sync", "进程同步与互斥", "concept", "临界区需要互斥访问；信号量、互斥锁等机制用于协调并发进程对共享资源的访问。", "os-process"),
        ("os-deadlock", "死锁与处理", "concept", "死锁需要互斥、占有并等待、不可剥夺和循环等待四个必要条件同时成立。", "os-process"),
        ("os-memory", "内存管理", "chapter", "内存管理负责地址转换、空间分配、保护与虚拟内存。", "os"),
        ("os-virtual-memory", "虚拟内存与分页", "concept", "分页把虚拟地址空间划分为页，通过页表映射到物理页框，并可按需调入页面。", "os-memory"),
        ("os-replacement", "页面置换", "concept", "物理内存不足时，页面置换算法选择牺牲页；常见算法包括 FIFO、LRU 和时钟算法。", "os-memory"),
    ],
    "net": [
        ("net-transport", "传输层", "chapter", "传输层为应用进程提供端到端的数据传输服务。", "net"),
        ("net-tcp", "TCP 可靠传输", "concept", "TCP 使用序号、确认、校验和与重传机制，在不可靠网络上提供可靠、有序的字节流。", "net-transport"),
        ("net-handshake", "TCP 三次握手", "concept", "TCP 建立连接时通过 SYN、SYN-ACK、ACK 三步确认双方的发送与接收能力及初始序号。", "net-transport"),
        ("net-congestion", "拥塞控制", "concept", "TCP 通过拥塞窗口调节注入网络的数据量，典型机制包括慢启动、拥塞避免、快速重传和快速恢复。", "net-transport"),
        ("net-flow", "流量控制", "concept", "接收方通过通告接收窗口限制发送方速率，避免接收缓存被过快填满。", "net-transport"),
        ("net-network", "网络层", "chapter", "网络层负责跨网络寻址和转发数据报。", "net"),
        ("net-ip", "IP 寻址与子网", "concept", "IP 地址标识网络接口；子网掩码用于区分网络前缀与主机部分。", "net-network"),
        ("net-routing", "路由选择", "concept", "路由器依据路由表和路由协议选择数据报的下一跳。", "net-network"),
    ],
    "se": [
        ("se-process", "软件过程", "chapter", "软件过程组织需求、设计、实现、测试、交付和维护活动。", "se"),
        ("se-requirements", "需求工程", "concept", "需求工程包括需求获取、分析、规格说明、验证与管理，产出可追踪的需求基线。", "se-process"),
        ("se-design", "软件设计与架构", "concept", "软件设计把需求转化为模块、接口和架构决策，并关注内聚、耦合与可维护性。", "se-process"),
        ("se-testing", "软件测试", "concept", "软件测试通过设计用例发现缺陷；单元、集成、系统和验收测试分别覆盖不同层次。", "se-process"),
        ("se-unit-test", "单元测试", "concept", "单元测试验证最小可独立测试的软件单元，通常隔离外部依赖并断言可观察结果。", "se-testing"),
        ("se-agile", "敏捷迭代", "concept", "敏捷开发以短周期迭代交付可工作的软件，并通过持续反馈调整需求和计划。", "se-process"),
        ("se-maintenance", "软件维护", "concept", "软件维护包括纠错、适应环境变化、完善功能和预防性改进。", "se-process"),
    ],
    "db": [
        ("db-relational", "关系模型", "chapter", "关系数据库以关系、元组和属性组织数据，并使用约束保证数据一致性。", "db"),
        ("db-sql", "SQL 查询", "concept", "SQL 使用 SELECT、FROM、WHERE、GROUP BY 和 HAVING 等子句检索与汇总关系数据。", "db-relational"),
        ("db-join", "关系连接", "concept", "连接根据相关属性组合多个关系；内连接仅保留匹配行，外连接还保留未匹配行。", "db-relational"),
        ("db-normalization", "规范化与范式", "concept", "规范化依据函数依赖分解关系模式，以减少冗余并避免插入、更新和删除异常。", "db-relational"),
        ("db-index", "索引", "concept", "索引以额外存储结构加速检索，但会增加存储开销并影响写入性能。", "db-relational"),
        ("db-transaction", "事务与 ACID", "chapter", "事务把一组数据库操作作为一个逻辑工作单元执行。", "db"),
        ("db-acid", "ACID 特性", "concept", "原子性、一致性、隔离性和持久性共同描述事务的 ACID 特性。", "db-transaction"),
        ("db-isolation", "并发控制与隔离级别", "concept", "隔离级别通过限制并发事务可见性，权衡一致性与并发度。", "db-transaction"),
    ],
    "co": [
        ("co-datapath", "数据通路", "chapter", "处理器数据通路由寄存器、运算部件、总线和控制信号协同构成。", "co"),
        ("co-instruction", "指令执行周期", "concept", "指令执行通常经历取指、译码、执行、访存和写回等阶段。", "co-datapath"),
        ("co-pipeline", "流水线", "concept", "流水线把指令处理划分为多个阶段并重叠执行，以提高单位时间的指令吞吐量。", "co-datapath"),
        ("co-interrupt", "中断与异常", "concept", "中断和异常使处理器保存现场并转入处理程序，完成后恢复被打断的执行流程。", "co-datapath"),
        ("co-memory", "存储系统", "chapter", "存储系统利用多级存储结构平衡速度、容量和成本。", "co"),
        ("co-cache", "Cache 映射与命中", "concept", "Cache 依据地址映射规则保存主存块；命中表示所需数据已经位于 Cache 中。", "co-memory"),
        ("co-locality", "程序局部性", "concept", "时间局部性表示近期访问的数据可能再次访问，空间局部性表示邻近地址可能很快被访问。", "co-memory"),
        ("co-virtual-address", "虚拟地址与地址转换", "concept", "地址转换机制将程序使用的地址映射到实际存储位置，并支持隔离与保护。", "co-memory"),
    ],
}
