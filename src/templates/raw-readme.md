## 1. 目录

```
01_raw/
├── 01_EE架构/                  ← 整车 EE 架构、拓扑、12V/48V、网段划分、电源与功耗预算
├── 02_芯片/                    ← 处理器架构（ARM/RISC-V）与芯片厂家（Infineon/NXP/Renesas/Nvidia/ST/TI/Andes）
├── 03_通信与网络/              ← 车载通信：Ethernet(100/1000BASE-T1)、CAN/CAN FD、LIN、FlexRay、TSN、SOME/IP、DoIP、UDS on CAN/Eth
├── 04_操作系统与中间件/         ← OS：Linux/QNX/SkyOS/WindRiver/VxWorks/ThreadX；中间件：AUTOSAR Classic & Adaptive、DDS、ROS2、CyberRT、Iceoryx
├── 05_软件工程/                ← 软件工程通用方法：需求/架构/设计/编码/Git/单元测试/CI/CD/Code Review/重构/设计模式
├── 06_功能安全/                ← ISO 26262、SOTIF、ASIL 分解、FMEA/FMEDA、安全机制、故障响应、E/E 系统安全设计
├── 07_信息安全/                ← ISO 21434、UN R155/R156、SecOC、TLS、HSM、密钥管理、OTA 安全、车内 IDS/IPS
├── 08_AI与AI工程/              ← AI 基础（大模型、Agent、RAG、GraphRAG、Embedding、训练/推理/评测）+ AI 工程化
├── 09_域控制器/                ← 智驾域（DCU/ADC）、座舱域（IVI/HUD）、中央计算单元、车身/底盘/动力域
├── 10_会议与活动/              ← 仅放跨主题合集；单主题演讲按主题散落到对应目录
├── 11_开发工具/                ← "写代码用的"：DaVinci/EB tresos/ETAS、IDE（VSCode/Keil/IAR）、调试器（JTAG/Lauterbach/iSystem）、Simulink
├── 12_法规_标准_政策/          ← 国标/行标（GB/T、GB）、UN ECE 系列（R155/R156/R157）、3GPP（V2X、C-V2X）、ISO 系列汇总入口（21262/21434/21448/…）、产业政策（百人会宏观、地缘经济、行业报告）
├── 13_流程体系/                ← ASPICE 4.0 / CMMI / ISO 9001 / IATF 16949 + 流程执行类工具（Polarion/Doors/Jira）
├── 14_测试与验证/              ← HiL/MiL/SiL/DIL/CI/CT、FMI 故障注入、渗透/模糊测试、自动化测试框架；测试工具：vTESTstudio/CANoe、dSPACE、NI VeriStand、ECU-TEST
└── 15_算法/                    ← 汽车场景下的感知/规控/端到端大模型/预测/定位/座舱/经典信号方法/数据闭环/仿真与生成/评测
```

## 2. 各目录的边界

### 2.1 `01_EE架构/`

- **放**：整车视角的"电 + 电子 + 网络"骨架；EE 拓扑演进、12V/48V 架构、网段划分、电源与功耗预算、整车线束拓扑。
- **不放**：芯片手册（→02）、具体 ECU 实现（→09）。

### 2.2 `02_芯片/`

- **放**：SoC/MCU 选型、架构手册、参考设计；处理器架构（ARM/RISC-V）；芯片厂家资料（Infineon/NXP/Renesas/Nvidia/ST/TI/Andes）。
- **不放**：板卡/整机（→09）、工具链（→11）。

### 2.3 `03_通信与网络/`

- **放**：车内总线 + 时间同步 + 诊断传输层：以太网 100/1000BASE-T1、CAN/CAN FD、LIN、FlexRay、TSN、SOME/IP、DoIP、UDS on CAN/Eth。
- **不放**：云端通信、V2X（→12_法规_标准_政策/V2X/ 或新讨论决定）。

### 2.4 `04_操作系统与中间件/`

- **放**：跑在 ECU 上的 OS 与应用与 OS 之间的中间件层。OS：Linux/QNX/SkyOS/WindRiver/VxWorks/ThreadX；中间件：AUTOSAR Classic & Adaptive、DDS、ROS2、CyberRT、Iceoryx。
- **不放**：纯算法（→15）、开发工具配置（→11）。

### 2.5 `05_软件工程/`

- **放**：方法论与通用实践，不限定汽车行业：架构/设计/编码、Git、单元测试、CI/CD、Code Review、设计模式、重构。
- **不放**：流程评估（→13）、专项测试（→14）。

### 2.6 `06_功能安全/`

- **放**：系统性 + 随机性硬件失效 + 软件安全：ISO 26262、SOTIF、ASIL 分解、FMEA/FMEDA、安全机制、故障响应、E/E 系统安全设计。
- **不放**：通用信息安全（→07）。

### 2.7 `07_信息安全/`

- **放**：恶意 / 非恶意但网络相关的威胁 + 加解密 + 防护机制：ISO 21434、UN R155/R156、SecOC、TLS、HSM、密钥管理、OTA 安全、车内 IDS/IPS。
- **不放**：通用 IT 安全（→05_软件工程/）、隐私合规（→12）。

### 2.8 `08_AI与AI工程/`

- **放**：模型 + 工程方法 + AI for SE；不分车载 / 研发两侧：大模型、Agent、RAG、GraphRAG、Embedding、训练/推理/评测、AI 工程化。
- **不放**：AI 产品落地在车端的功能（→09）、智能驾驶相关算法（VLA/VLM/WA）（→15）。

### 2.9 `09_域控制器/`

- **放**：以"控制器产品 / 集成系统"为单位：智驾域（DCU/ADC）、座舱域（IVI/HUD）、中央计算单元（One-Box/Central Compute）、车身/底盘/动力域。
- **不放**：单芯片（→02）、整车拓扑（→01）。

### 2.10 `10_会议与活动/`

- **放**：仅放**跨主题合集**、未分类演讲、花絮纪要。
- **不放**：可明确归入其它一级的内容——单主题演讲必须按主题散落到 08/09/12/15 等。

### 2.11 `11_开发工具/`

- **放**：开发者日常接触的 IDE + 配置 + 建模 + 版本 + 调试：DaVinci/EB tresos/ETAS、IDE（VSCode/Keil/IAR）、调试器（JTAG/Lauterbach/iSystem）、Simulink、Git/SVN。
- **不放**：测试工具（→14）、AI 平台（→08）、流程执行类工具 Polarion/Doors/Jira（→13）。

### 2.12 `12_法规_标准_政策/`

- **放**：法规 / 标准 / 政策 / 行业报告：国标/行标（GB/T、GB）、UN ECE 系列（R155/R156/R157）、3GPP（V2X、C-V2X）、ISO 系列汇总入口（21262/21434/21448/…）、产业政策（百人会宏观、地缘经济、行业报告）。
- **不放**：单一标准全文深入（→06/07）、ASPICE 流程（→13）。

### 2.13 `13_流程体系/`

- **放**：过程评估 + 流程框架 + 支撑流程落地的"流程执行类"工具：ASPICE 4.0、CMMI、ISO 9001、IATF 16949，以及 Polarion/Doors/Jira 这类**流程执行平台**。
- **不放**：开发 IDE、CI/CD（→11）、测试工具（→14）。

### 2.14 `14_测试与验证/`

- **放**：测试方法 + 测试执行工具：HiL/MiL/SiL/DIL/CI/CT、FMI 故障注入、渗透/模糊测试、自动化测试框架；测试工具：Vector vTESTstudio/CANoe、dSPACE、NI VeriStand、Excite、TraceTronic ECU-TEST。
- **不放**：开发工具（→11）、纯仿真平台（→04_操作系统与中间件/SIL）。

### 2.15 `15_算法/`

- **放**：「算法本身」——论文、方法、训练/推理/数据/评测一体；不论在车端还是云端：
  - 感知：BEV / Occupancy / 3D 检测 / 车道线 / 障碍物 / 目标跟踪 / 传感器融合（Camera/LiDAR/Radar/IMU/USS）
  - 规控：规划（Path / Speed / Lane）、行为决策（FSM/ML-Decision）、控制（纵向/横向/MPC/LQR/PID）、端到端（E2E）
  - 端到端大模型：E2E 架构 / World Model / VLA / VLM / WA
  - 预测：意图预测 / 轨迹预测 / 行为预测
  - 定位：高精地图 / SLAM / RTK-GNSS / NDT / 点云匹配
  - 座舱：多模态交互（语音/视觉/DMS/OMS）、推荐、车内 Agent 决策
  - 经典机器学习与信号处理：Kalman / Particle Filter / ICP / EM / GMM / 特征工程（车载语境下的非深度方法）
  - 数据闭环：数据采集 / 标注 / 挖掘（Mining）/ 自动标注 / 4D 标注 / Corner Case 发现
  - 仿真与生成：场景库（OpenSCENARIO）/ 神经渲染（NeRF / 3DGS）/ 世界模型生成 / Log2Scene
  - 评测与指标：离线评测（Open-Loop）/ 在线评测（Closed-Loop）/ nuScenes / KITTI / Waymo Open / CARLA Leaderboard
- **不放**：
  - AI 工程化方法（RAG / Agent 框架 / Embedding / Prompt 工程 / MLOps 通用） → 08_AI与AI工程/
  - 算力芯片 / SoC → 02_芯片/
  - 中间件或部署框架（AUTOSAR Adaptive ara::com / ROS2 / CyberRT / DDS） → 04_操作系统与中间件/
  - 域控制器整机集成 / 系统工程 → 09_域控制器/
  - 算法测试的"工具"（HiL/SIL 工具链、CANoe 仿真）→ 14_测试与验证/
  - 算法评测用的"标准法规"（NCAP / Euro-NCAP / C-IASI）→ 12_法规_标准_政策/

---

## 3. 流程工具 vs 开发工具的边界（关键判定）

| 类别           | 典型工具                                                | 归哪             |
| -------------- | ------------------------------------------------------- | ---------------- |
| 流程执行类工具 | Polarion、Doors、Jira、需求/配置/缺陷管理平台           | `13_流程体系/` |
| 开发工程类工具 | GitLab CI、Jenkins、VSCode、Keil、IAR、调试器、Simulink | `11_开发工具/` |

判定原则：**该工具服务于"流程运转 / 团队协作 / 评估"** 归 13；**该工具服务于"个人或小团队写代码 / 建模 / 调试"** 归 11。