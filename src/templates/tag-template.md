# tag-template — aeps-llm-wiki-plugin 全局 tag 字典(6 轴)

> **状态**:v1.0 冻结版(2026-09-02)
> **权威性**:plugin 本体权威字典 —— plugin 维护者直接编辑维护
> **复制策略**:**复制到用户项目**。init 时复制 `tag-template.md` 到 `<project>/raw/tag-template.md`;**用户再次调用 init skill 时按 append 策略同步**(详见 design.md §4.1.1 "幂等再入"):用户为主,plugin 新版内容 append 到本地副本,**不覆盖用户改过的内容**,lint 提示"plugin 新版有 X 条本地没有"。
> **使用方**:SKILL.md 显式告知"需要时读 templates/tag-template.md";LLM ingest / lint 时必须查字典

---

## 1. 使用纪律与规则

### 1.1 维度正交与打标数量

每篇文档选 **6 个左右的不同维度 tag 组合**(最多不超过 10 个;超出此范围会推高维护成本且检索区分度下降)。

### 1.2 必填校验

- `docform/`(文档用途):**必填**
- `domain/`(业务领域):**必填**(domain 是文档主题的最基础坐标,缺失会让检索退化为"扫全表")
- `maturity/`(成熟度):推荐填,不强制

### 1.3 单值 / 多值

| axis         | 词数 | 单值/多值                                                                  | 必填?     |
| ------------ | ---- | -------------------------------------------------------------------------- | --------- |
| `domain`   | 14   | 单值(软上限 ≤ 2,最多 5)                                                   | ✅ 必填   |
| `layer`    | 9    | 单值优先                                                                   | 可选      |
| `phase`    | 9    | **可多值**(需求+验证同时存在常见)                                    | 可选      |
| `docform`  | 14   | **单值必填**                                                         | ✅ 必填   |
| `maturity` | 5    | **单值必填**(`concept < research < pilot < production < standard`) | ⚠️ 推荐 |
| `tec`      | ~40  | 单值优先                                                                   | 可选      |

### 1.4 隔离机制(防 tag 维度污染)

- **文档状态**(`草稿/已发布/废弃`)使用 frontmatter 字段 `status: draft / stable / deprecated`,**不进 tag**
- **项目 / 客户名称**(`BE13-VDP`、`FAW-CGW` 等)走 `entities/project/<项目名>.md` 路径,**不进 tag**
- **OKF type 字段**(`source / concept / standard / ...`)由 frontmatter `type` 字段承担,**不进 tag**

### 1.5 打标误区与收敛纪律

> 当单篇文档 tag 数量趋近上限(超过 10 个)或自检发现难以收敛时,通常意味着触发了以下"打标误区"。建议在打签前先自检一次,而不是继续加 tag。

| # | 误区                                    | 收敛做法                                                                                                                                                                          |
| - | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **`tec/` 轴罗列太多非核心技术** | 一篇文档可能用到 Git、CMake、Linux、Python、SOME/IP。**只保留核心突破点**(如 `tec/someip`),基础通用工具(`tec/git` `tec/cmake` `tec/linux`)由正文自然承载,无需打 tag |
| 2 | **`domain/` 选了太多业务域**    | 整车级 / 多模块文档不要把座舱 + 智驾 + 底盘全打上。**直接打 `domain/cross-domain` 收敛**(搭配范式 4 的 WARN 触发)                                                         |
| 3 | **把"属性 / 状态"当成 tag**       | 项目名(`BE13-VDP`)、作者、版本号、草稿状态 → 走 Frontmatter 字段(`status: draft`、`stale_after: 2027-01` 等),**严格排除在 tag 之外**(详见 §1.4 隔离机制)            |

**自检三问**:

1. 这 5 个 tag 里,有没有基础通用工具可以下移到正文?(误区 1)
2. 这 5 个 tag 里,有没有多个 `domain/` 可以收敛到 `cross-domain`?(误区 2)
3. 这 5 个 tag 里,有没有本该走 Frontmatter 字段的属性?(误区 3)

如果三问都不命中,确实需要 10+ tag,那 10+ 是合理的;否则先收敛再打签。

#### 1.5.1 犹豫时降维收敛原则(LLM / 开发者打标决策原则)

LLM 在 ingest 自动打标时,经常在两个边界 axis 之间产生模糊决策(如 `layer/bsw-os` vs `layer/platform-hypervisor`、`phase/architecture` vs `phase/detail-design`、`docform/technical-doc` vs `docform/interface-spec`)。犹豫时遵循:

> **收敛优先**:优先选择类目更收敛、信息密度更高的 tag —— 选完之后,跟其他维度(范式 1 主题-技术共存 / 范式 2 层级-技术对齐)的联动更明确的那个。

**典型边界参照**:
- **`layer/bsw-os` vs `layer/platform-hypervisor`**:跑在裸芯片上的 OS + 驱动 + AUTOSAR BSW → `bsw-os`;跑在 OS 之上的虚拟化 + 容器 + SDV 软件平台 → `platform-hypervisor`
- **`layer/middleware-soa` vs `layer/bsw-os`**:AUTOSAR RTE / DDS / 服务总线 → `middleware-soa`(SDK 视角的中间件);MCAL / OS Kernel / Driver → `bsw-os`。**犹豫时优先归 `middleware-soa`**,因其收敛面更广(详见 §3)
- **`phase/architecture` vs `phase/detail-design`**:概念选型 / 逻辑架构 → `architecture`;接口表 / 类图 / 代码级设计 → `detail-design`(详见 §4)
- **`docform/technical-doc` vs `docform/interface-spec`**:整体方案 → `technical-doc`;**独立成册的接口规范** → `interface-spec`(高频检索对象,详见 §6)

### 1.6 命名约定(plugin 维护 + LLM 写入都遵守)

- 全小写 + `-` 连字符(例:`autosar-adaptive` 不是 `Autosar_Adaptive`)
- 不含版本号 / 状态词(`autosar-adaptive-v4.4` 非法;`deprecated` 非法)
- 不含 OKF type 值(`tags: [concept]` 非法)
- 不含人名 / 公司名(除非 entity 页)
- 长度 ≤ 2-3 个词(防止过宽)

---

## 2. 车辆功能与业务领域 (`domain/`)

用于定位文档涉及的物理域、逻辑域或跨学科主题。

| 值                       | 含义                          | 适用场景                                                                      |
| ------------------------ | ----------------------------- | ----------------------------------------------------------------------------- |
| `domain/cockpit`       | 智能座舱                      | IVI、HUD、仪表、舱驾融合、座舱 HMI                                            |
| `domain/adas-ad`       | 智能驾驶 / 自动驾驶           | 感知、规控、定位、地图、VLA/端到端大模型                                      |
| `domain/chassis`       | 底盘域                        | 线控转向 Steer-by-Wire、线控制动 Brake-by-Wire、悬架、底盘协调控制 VMC        |
| `domain/powertrain`    | 动力与三电                    | 电驱、BMS 电池管理、MCU 电控、VCU、充电控制                                   |
| `domain/body-gateway`  | 车身与网关                    | Zone ECU 区域控制器、BCM 车身控制、车灯、门控                                 |
| `domain/ee-arch`       | 电子电气架构                  | 区域架构、SDV、整车拓扑、虚拟化拓扑                                           |
| `domain/cross-domain`  | 跨域协同 / 整车级控制         | 舱驾融合、跨域服务编排、整车 SOA 调度                                         |
| `domain/ai`            | AI 通用算法与方法论           | ML、LLM、RAG、Agent 框架                                                      |
| `domain/embodied-ai`   | 具身智能与新型载体            | 人形机器人、飞行汽车、具身大模型                                              |
| `domain/cloud-infra`   | 车联网云端基础设施            | 公有云 / 私有云、云端大数据分析                                               |
| `domain/enterprise-it` | 企业数字化与 IT               | 研发协同工具、协同平台                                                        |
| `domain/geopolitics`   | 地缘经济与供应链              | 产业链重构、技术封锁、合规限制                                                |
| `domain/process`       | 开发流程与方法论 + 跨层流程   | V 模型、敏捷、ASPICE、CMMI、AI for V-Model                                    |
| `domain/fusa`          | **功能安全主题**        | ISO 26262 / SOTIF 主题入口;具体流程走`phase/`,标准走 `tec/iso26262` 系列  |
| `domain/cybersecurity` | **信息 / 网络安全主题** | ISO 21434 主题入口;具体流程走`phase/`,技术走 `tec/secoc` / `tec/hsm` 等 |

**说明**:

- `domain` 整体表达"文档主题涉及的业务领域",**与 layer 正交**:同一份资料可以同时打 `domain/chassis + layer/middleware-soa`(底盘 + 中间件)
- **跨域边界规则**:`domain/cockpit` 与 `domain/adas-ad` 不重叠(都是主类目);舱驾融合这类跨域主题 → 打 `domain/cockpit + domain/adas-ad`(利用 §1.3 单值软上限 ≤ 2)
- **`domain/fusa` / `domain/cybersecurity` 与其他领域可同时打**(软上限 ≤ 2):一份"网关中央控制器功能安全设计"可以同时 `domain/fusa + domain/body-gateway`(安全主题 + 网关业务)
- **安全主题作为"主题类目"放在 domain/ 表尾**:功能安全 / 网络安全与其他业务领域正交,可与其他业务领域同时打(软上限 ≤ 2,例如 `domain/fusa + domain/body-gateway`)
  - 具体流程阶段走 `phase/`(HARA / TARA / 审计节点)
  - 具体标准 / 技术走 `tec/`(`tec/iso26262-asil-d` / `tec/iso21434` / `tec/secoc` / `tec/hsm` 等)
  - **三重锁定**:`domain/fusa + phase/architecture + tec/iso26262-asil-d`(主题 + 阶段 + 标准)

---

## 3. 技术层级与架构 (`layer/`)

用于定位文档在系统分层 / 软硬件堆栈中的位置。

| 值                            | 含义                   | 适用场景                                               |
| ----------------------------- | ---------------------- | ------------------------------------------------------ |
| `layer/hardware`            | 硬件层                 | PCB、传感器、执行器、供电电路、电气原理图              |
| `layer/chip`                | 芯片与控制器底座       | MCU、SoC 芯片平台、RISC-V、AURIX                       |
| `layer/bsw-os`              | 底层软件与操作系统     | AUTOSAR CP/AP、RTOS、Linux 内核、QNX、Bootloader、驱动 |
| `layer/platform-hypervisor` | 虚拟化与平台层         | Hypervisor、Docker 容器、SDV 软件平台                  |
| `layer/middleware-soa`      | 中间件与服务化层       | SOME/IP、DDS、RPC、ROS/ROS2、通信矩阵、IDL 定义        |
| `layer/ai-agent`            | 车载 AI 与大模型应用层 | 端侧 LLM 容器、MCP 协议工具化、Agent 意图理解与规划    |
| `layer/algorithm`           | 核心算法与模型层       | 感知算法、规控算法、VLA 端到端模型                     |
| `layer/application`         | 传统应用层功能         | App 逻辑、HMI 应用、业务控制逻辑                       |
| `layer/system`              | 系统 / 子系统级集成    | Zonal 系统、整车网络系统                               |

**说明**:

- `layer/platform-hypervisor` 与 `layer/bsw-os` 的边界:`bsw-os` 是跑在裸芯片上的 OS + 驱动 + AUTOSAR BSW;`platform-hypervisor` 是跑在 OS 之上的虚拟化 + 容器 + SDV 软件平台
- `layer/middleware-soa` 与 `layer/bsw-os` 的边界:AUTOSAR RTE / DDS / 服务总线属于 `middleware-soa`;MCAL / OS Kernel / Driver 属于 `bsw-os`(LLM 写入时犹豫时优先归 `middleware-soa`,因其在 SDK 视角下算中间件)

---

## 4. 研发流程与生命周期 (`phase/`)

按 ASPICE 及汽车功能安全规范定义的生命周期阶段。

| 值                      | 含义              | 适用场景                                         |
| ----------------------- | ----------------- | ------------------------------------------------ |
| `phase/requirements`  | 需求工程          | OEM 功能需求、技术规格书 TRS/SRS、需求追溯与变更 |
| `phase/architecture`  | 架构与概念设计    | 系统架构设计、概念选型、逻辑 / 物理架构          |
| `phase/modeling`      | 建模与仿真        | 物理大模型、VLA World Model、MIL 仿真            |
| `phase/detail-design` | 详细设计与实现    | 详细设计文档、代码编写、接口实现                 |
| `phase/integration`   | 系统集成          | 跨域融合集成、舱驾融合、ECU 软硬件集成           |
| `phase/verification`  | 开发者侧验证      | 单元测试、集成测试、SIL 软件在环、模型检查       |
| `phase/validation`    | 用户 / 系统级确认 | HIL 硬件在环、台架测试、整车实车路试             |
| `phase/ops`           | 运维与量产监控    | OTA 升级、售后监控、现场故障闭环                 |

**说明**:

- `phase/architecture` 与 `phase/detail-design` 的边界:概念选型 / 逻辑架构 → `architecture`;接口表 / 类图 / 代码级设计 → `detail-design`
- **`phase/` 是纯时间 / 研发阶段维度**:不包含安全主题。功能安全 / 网络安全相关流程归入通用阶段(需求 → 架构 → 详细设计 → 集成 → 验证 → 运维);安全**主题**走 `domain/fusa` / `domain/cybersecurity`,安全**标准 / 技术**走 `tec/`

---

## 5. 技术栈、协议与标准 (`tec/`)

用于精准定位文档涉及的技术细节、通信协议、芯片平台及工具链。本轴是字典最大的一轴,按子主题分块。

### 5.1 总线与通信协议

| 值               | 含义                   | 适用场景         |
| ---------------- | ---------------------- | ---------------- |
| `tec/can-fd`   | CAN FD 总线            | 车载 CAN FD 通信 |
| `tec/lin`      | LIN 总线               | 车身低速 LIN     |
| `tec/ethernet` | 车载以太网             | 100/1000BASE-T1  |
| `tec/tsn`      | 时间敏感网络           | TSN 调度 / 同步  |
| `tec/someip`   | SOME/IP 协议           | SOA 服务通信     |
| `tec/dds`      | DDS 数据分发服务       | RTPS / fastdds   |
| `tec/doip`     | DoIP 诊断协议          | UDS over IP      |
| `tec/uds`      | UDS 诊断协议           | UDS on CAN / Eth |
| `tec/tcp`      | TCP 协议               | 通用 TCP         |
| `tec/udp`      | UDP 协议               | 通用 UDP         |
| `tec/dhcp`     | DHCP 协议              | 网络配置         |
| `tec/arp`      | ARP 协议               | 地址解析         |
| `tec/vlan`     | VLAN 虚拟局域网        | 网络隔离         |
| `tec/v2x`      | V2X 车联网             | C-V2X / DSRC     |
| `tec/mcp`      | Model Context Protocol | Agent 工具化协议 |

### 5.2 软件架构与操作系统

| 值                 | 含义              | 适用场景             |
| ------------------ | ----------------- | -------------------- |
| `tec/autosar-cp` | Classic AUTOSAR   | CP BSW / RTE / OS    |
| `tec/autosar-ap` | Adaptive AUTOSAR  | AP ara::com / SM     |
| `tec/qnx`        | QNX RTOS          | 仪表 / 智驾 RTOS     |
| `tec/linux`      | Linux kernel      | 域控 / 云端 Linux    |
| `tec/rtos`       | 通用 RTOS         | ThreadX / VxWorks 等 |
| `tec/uefi`       | UEFI 固件开发     | 车载 UEFI            |
| `tec/uboot`      | U-Boot bootloader | Bootloader           |
| `tec/dtb`        | Linux 设备树      | DTB 调试             |
| `tec/rootfs`     | rootfs            | sysVinit / systemd   |
| `tec/ros`        | ROS / ROS2        | 机器人中间件         |
| `tec/docker`     | Docker 容器       | 工具链 / CI 容器     |
| `tec/qemu`       | QEMU 仿真         | 虚拟化 / 仿真        |

### 5.3 硬件与芯片平台

| 值                  | 含义               | 适用场景        |
| ------------------- | ------------------ | --------------- |
| `tec/s32g`        | NXP S32G 网关芯片  | 中央 / 区域网关 |
| `tec/tda4`        | TI TDA4            | 智驾域控 SoC    |
| `tec/am62a`       | TI AM62A           | 入门 SoC        |
| `tec/drive-orin`  | NVIDIA Drive Orin  | 自动驾驶        |
| `tec/jetson-orin` | NVIDIA Jetson Orin | 边缘 AI         |

### 5.4 功能安全与信息安全(FuSa + Cybersecurity)

**功能安全 (FuSa)** 主题在 `domain/fusa`,具体标准 / 技术细节在本节:

| 值                      | 含义                              | 适用场景                        |
| ----------------------- | --------------------------------- | ------------------------------- |
| `tec/iso26262`        | ISO 26262 功能安全(笼统词)        | ASIL 分解 / FMEA / 总体安全概念 |
| `tec/iso26262-qm`     | ISO 26262 QM(质量管理,无安全要求) | 非安全相关功能 / QM 流程要求    |
| `tec/iso26262-asil-a` | ISO 26262 ASIL-A 等级             | ASIL-A 流程要求                 |
| `tec/iso26262-asil-b` | ISO 26262 ASIL-B 等级             | ASIL-B 流程要求                 |
| `tec/iso26262-asil-c` | ISO 26262 ASIL-C 等级             | ASIL-C 流程要求                 |
| `tec/iso26262-asil-d` | ISO 26262 ASIL-D 等级             | ASIL-D 流程要求                 |
| `tec/sotif`           | ISO 21448 SOTIF                   | 预期功能安全                    |

**信息安全 (Cybersecurity)** 主题在 `domain/cybersecurity`,具体标准 / 技术细节在本节:

| 值               | 含义                         | 适用场景                                  |
| ---------------- | ---------------------------- | ----------------------------------------- |
| `tec/iso21434` | ISO 21434 汽车网络安全标准   | TARA 威胁建模 / 网络安全管理体系          |
| `tec/secoc`    | Secure Onboard Communication | AUTOSAR SecOC 车载安全通信(CMAC + 抗重放) |
| `tec/hsm`      | 硬件安全模块                 | SHE / EVITA HSM / TPM                     |
| `tec/atf`      | ARM Trust Firmware           | ATF 安全启动                              |
| `tec/optee`    | OP-TEE 可信执行环境          | TEE 应用                                  |
| `tec/rpmb`     | RPMB 安全存储                | 防回滚                                    |
| `tec/avb`      | Android Verified Boot        | 启动验证                                  |
| `tec/macsec`   | MACsec 协议                  | 链路层加密                                |
| `tec/ipsec`    | IPsec 协议                   | 网络层加密                                |
| `tec/gmssl`    | 国密算法 (GM/T 系列)         | SM2/SM3/SM4 等商用密码、车载国密合规      |

### 5.5 开发与工程工具链(Tooling)

| 值                           | 含义                          | 适用场景                         |
| ---------------------------- | ----------------------------- | -------------------------------- |
| `tec/vector-tools`         | Vector 工具链                 | CANoe / vTESTstudio              |
| `tec/preevision`           | ETAS PREEvision               | EE 架构设计                      |
| `tec/wireshark`            | Wireshark 抓包                | 网络协议分析                     |
| `tec/git`                  | Git 工具命令                  | 版本控制                         |
| `tec/gerrit`               | Gerrit Code Review            | 代码审查                         |
| `tec/jenkins`              | Jenkins CI                    | 持续集成                         |
| `tec/cmake`                | CMake                         | 编译构建                         |
| `tec/make`                 | Make                          | 编译构建                         |
| `tec/gdb`                  | GDB 调试器                    | 调试                             |
| `tec/yocto`                | Yocto 嵌入式构建              | BSP / SDK 构建                   |
| `tec/pet-ci`               | 恒润 PET 持续集成             | 内部 CI 平台                     |
| `tec/claude`               | Claude AI 开发工具            | AI 辅助开发                      |
| `tec/ollama`               | Ollama 端侧 LLM 推理框架      | 本地 / 车内 LLM 部署             |
| `tec/vllm`                 | vLLM 高吞吐 LLM 推理框架      | 服务端 LLM 推理                  |
| `tec/langchain`            | LangChain Agent / RAG 框架    | LLM 应用编排                     |
| `tec/llamaindex`           | LlamaIndex RAG / 数据索引框架 | 文档索引与问答                   |
| `tec/enterprise-architect` | Enterprise Architect (EA)     | SysML / UML 架构建模             |
| `tec/simulink`             | MATLAB Simulink               | MBD 基于模型的设计、MIL/SIL 仿真 |

**说明**:

- `tec/` 是字典最大一轴(~40 个词);按 5 个子主题分块,新增词请加到对应子块
- `tec/` 与 `domain` 正交:同一份非安全资料可 `domain/chassis + tec/someip`(底盘 + SOME/IP);安全资料走 `domain/fusa`(或 `domain/cybersecurity`)+ `tec/iso26262-asil-d`(或 `tec/iso21434` 等具体标准)
- `tec/` 与 `layer/middleware-soa` 在 SOME/IP / DDS 处有交集:协议本体归 `tec/`,协议实现层归 `layer/middleware-soa`

---

## 6. 文档用途与形态 (`docform/` —— 必填,单值)

表达"这份文档是用来做什么的"。

| 值                          | 含义                                     | 适用场景                                         |
| --------------------------- | ---------------------------------------- | ------------------------------------------------ |
| `docform/technical-doc`   | 技术方案 / 架构设计文档 / 技术说明       | 架构方案、设计说明、技术白皮书                   |
| `docform/interface-spec`  | 接口定义书 / ICD / IDL / API 规范文件    | SOME/IP IDL、API 定义、通信矩阵、MCP Tool Schema |
| `docform/requirement`     | 功能需求 / 技术需求规格书                | 功能需求清单、技术规格书(TRS/SRS)                |
| `docform/test-report`     | 测试用例 / HIL 测试报告 / 验证分析报告   | 单元测试结果、HIL 测试报告、验证报告             |
| `docform/issue-analysis`  | Crash 分析 / Bug 排查 / 故障诊断与闭环   | crash 分析 / bug 排查 / 故障闭环记录             |
| `docform/poc-case`        | POC 实验案例 / 测试 Demo / 验证总结      | POC 案例、Demo 验证、试点总结                    |
| `docform/experience`      | 实践心得 / 最佳实践 / 调试技巧总结       | 调试技巧、配置经验、优化建议                     |
| `docform/config-guide`    | 环境配置指南 / 工具配置 / 编译步骤说明   | 编译环境、工具链配置、系统参数                   |
| `docform/usage-guide`     | 工具使用手册 / 库使用指南 / API 调用说明 | 工具操作手册、API 调用示例                       |
| `docform/meeting-minutes` | 会议记录 / 技术评审总结 / 决策记录       | 技术评审会议、项目例会                           |
| `docform/study-notes`     | 学习总结 / 技术笔记 / 培训材料           | 技术学习笔记、培训材料                           |
| `docform/article`         | 学术论文 / 技术综述文章                  | arXiv 论文、综述、专题文章                       |
| `docform/whitepaper`      | 厂商白皮书 / 行业趋势报告                | 厂商白皮书、行业报告                             |
| `docform/standard-spec`   | 行业标准 / 法规全文解读与摘录            | ISO/IEC/UN ECE/GB 标准的解读或摘录               |

**说明**:

- `docform` 表达"文档用途",与 OKF `type` 字段正交:一篇事故复盘可以是 `type: analysis + docform/issue-analysis`
- `docform/technical-doc` 与 `docform/interface-spec` 边界:整体方案 → `technical-doc`;**独立成册的接口规范** → `interface-spec`(高频检索对象)

---

## 7. 工程成熟度 (`maturity/` —— 必填,单值)

表达技术方案或代码的成熟度等级(递进关系:`concept < research < pilot < production < standard`)。

| 值                      | 含义                             | 适用场景                             |
| ----------------------- | -------------------------------- | ------------------------------------ |
| `maturity/concept`    | 概念设想                         | PPT 架构构想 / 未形成原型的早期设想  |
| `maturity/research`   | 学术研究 / 算法原型              | arXiv 论文 / 未量产的预研 Demo       |
| `maturity/pilot`      | POC 验证阶段                     | POC 验证 / 单车型试点 / 部分客户试用 |
| `maturity/production` | 量产阶段                         | SOP 方案 / 多车型规模化落地          |
| `maturity/standard`   | 已推行成为行业通用标准或强制法规 | ISO/IEC/UN ECE/GB 标准               |

---

## 8. lint 治理(频次 + 合并 + 字典外建议)

| 规则                                                            | 行为                                              |
| --------------------------------------------------------------- | ------------------------------------------------- |
| **裸 tag**(`ai` 无前缀)                                 | FAIL                                              |
| **同 axis 重复**(如 `domain/ai` 出现 2 次)              | FAIL                                              |
| **缺失 `docform/`**                                     | FAIL(必填)                                        |
| **缺失 `domain/`**                                      | FAIL(必填)                                        |
| **缺失 `maturity/`**                                    | WARN(推荐填,缺失不影响检索底座)                   |
| **每页 tag 数量 > 10**                                    | WARN,提示"切片失去区分度,建议合并"                |
| **每页 tag 数量 < 5**                                     | WARN,提示"覆盖太薄,建议补"                        |
| **`domain` 软上限 ≤ 2,最多 5**                         | script 不强制,review 时把握                       |
| **OKF type 出现在 tag 里**                                | FAIL(应走`type` 字段)                           |
| **状态词出现在 tag 里**                                   | FAIL(应走`status` 字段)                         |
| **版本号出现在 tag 里**                                   | FAIL(走正文或`stale_after`)                     |
| **人名 / 公司名出现在 tag 里**(非 entity 页)              | FAIL(走`entities/` 目录)                        |
| **过宽 tag**(`software` `engineering` `safety`)     | WARN,提示"会污染主题筛选"                         |
| **OWL Disjointness 违反**:同轴内两词语义重叠              | WARN,提示"考虑合并或换更细的词"                   |
| **拼写变体聚类**(`autosar` / `AUTOSAR`)               | WARN,推荐字典 prefLabel                           |
| **词序变体**(`autosar-adaptive` / `adaptive-autosar`) | WARN,推荐字典 prefLabel                           |
| **频次 ≥ 10**                                            | "热门,可考虑固化(下次 plugin 升级时手动加入字典)" |
| **频次 = 1**                                              | "冷僻,真的需要保留吗?"                            |
| **字典外 tag 累计 ≥ 5 次**                               | plugin 维护者下次升级字典时考虑加入               |

### 8.1 通用校验范式

> **设计动机**:6 轴体系下若为每个业务场景单独写硬编码联动规则(`ai-agent` ↔ `mcp` / `fusa` ↔ `iso26262` ...),规则库会迅速膨胀且难以维护。下面 4 类**通用范式**(Validation Paradigms)对所有未来新增的领域 / 技术栈一视同仁。

#### 范式 1:主题-技术共存 (Theme-to-Tech Co-occurrence)

**逻辑**:指定了某些业务主题(`domain/`)时,要求 `tec/` 轴中至少存在一个支撑该主题的技术栈或标准,避免"空洞打签"。

**通用判定**:`domain/X ∈ Tags ⟹ Count(tec/Y associated with X) ≥ 1`

**示例族**:

- **安全类**:若含 `domain/fusa` 或 `domain/cybersecurity` → `tec/` 中须存在至少一个 `tec/iso26262-*` / `tec/iso21434` / `tec/secoc` / `tec/hsm` / `tec/gmssl` / `tec/sotif`
- **架构类**:若含 `domain/ee-arch` → `tec/` 中须存在至少一个 `tec/autosar-*` / `tec/someip` / `tec/dds` / `tec/preevision` / `tec/enterprise-architect`(SysML/UML 架构建模)
- **建模 / 仿真类**:若含 `phase/modeling` → `tec/` 中须存在至少一个 `tec/simulink`(MBD / MIL-SIL) / `tec/qemu`(虚拟化仿真) / `tec/enterprise-architect`(SysML/MIL 架构建模)
- **跨域协同类**:若含 `domain/cross-domain` → `tec/` 中须存在至少一个 `tec/someip` / `tec/dds` / `tec/tsn` / `tec/mcp`(跨域通信 / 编排类)

**提示**:`WARN — 检测到主题 [domain/X],建议在 tec/ 轴补充至少一个具体实施技术或标准`

#### 范式 2:层级-技术对齐 (Layer-to-Tech Alignment)

**逻辑**:`layer/` 与 `tec/` 的抽象层级不能严重错配(硬件层配纯应用框架 / 应用层配驱动)。

**通用判定**:`layer/X ∈ Tags ⟹ tec/Y 的抽象层级 must match layer/X`

**示例族**:

- **芯片/硬件层**:若含 `layer/chip` 或 `layer/hardware` → `tec/` 中应含芯片型号 / 固件 / 硬件工具(`tec/s32g` / `tec/tda4` / `tec/am62a` / `tec/drive-orin` / `tec/jetson-orin` / `tec/uboot` / `tec/dtb`)
- **OS / BSW 层**:若含 `layer/bsw-os` → `tec/` 中应含 OS / 驱动 / AUTOSAR 类(`tec/autosar-cp` / `tec/autosar-ap` / `tec/qnx` / `tec/linux` / `tec/rtos`)
- **中间件层**:若含 `layer/middleware-soa` → `tec/` 中应含通信协议 / 服务框架(`tec/someip` / `tec/dds` / `tec/doip` / `tec/uds`)
- **AI / Agent 应用层**:若含 `layer/ai-agent` → `tec/` 中应含 AI / Agent 技术栈(`tec/mcp` / `tec/claude` / `tec/ollama` / `tec/vllm` / `tec/langchain` / `tec/llamaindex`)
- **算法层**:若含 `layer/algorithm` → `tec/` 中应含 MBD / 模型 / 仿真工具(`tec/simulink` / `tec/qemu`)

**提示**:`WARN — 架构层级 [layer/X] 与所选技术栈 [tec/Y] 抽象层级可能不匹配,请检查 layer 是否填错`

#### 范式 3:形态-成熟度约束 (Docform-to-Maturity Constraint)

**逻辑**:文档用途(`docform/`)与成熟度(`maturity/`)之间存在工程合理性约束。严谨工程文档不能对应过于原始的成熟度;纯概念 / 学术文档不应被标成 standard / production。

**通用判定**:

- **下限约束**:严谨工程文档(`docform/interface-spec` / `docform/issue-analysis` / `docform/test-report` / `docform/standard-spec` / `docform/config-guide`)的 `maturity` 不能低于 `pilot`
- **上限约束**:纯概念 / 学术文档(`docform/article` / `docform/study-notes` / `docform/whitepaper`)的 `maturity` 不应标为 `production`(白皮书解读标准时例外)
- **强绑定**:`docform/standard-spec`(行业标准 / 法规全文解读与摘录)应强绑定 `maturity/standard` —— 标准类文档的成熟度在语义上就是"已成标准",若标成 `pilot` / `production` 语义失真
- **下限豁免**:`docform/poc-case`(POC 验证 / Demo)的下限放行,允许 `maturity/pilot` 是该形态的天然成熟度;若同时打 `maturity/concept` 才视为冲突

**示例**:`docform/interface-spec` + `maturity/concept` → 冲突(未初始化的概念不能作为正式接口规范);`docform/issue-analysis` + `maturity/concept` → 冲突(没有故障可分析);`docform/standard-spec` + `maturity/production` → 冲突(标准不是"在产方案",应是 `maturity/standard`)

**提示**:`FAIL / WARN — 文档形态 [docform/X] 与成熟度 [maturity/Y] 存在工程完备度冲突`

#### 范式 4:跨域粒度控制 (Cross-Domain Multi-Tag Threshold)

**逻辑**:控制单篇文档在 `domain/` 维度的组合粒度,防止"多标签滥用"导致知识切片失去区分度。

**通用判定**:

- `domain/` 多选数量 ≤ 2(软上限,§1.3 已述,这里升级为 WARN 阈值)
- 当 `domain/` ≥ 2 且不含 `domain/cross-domain` 时,触发跨域提示

**示例**:

- 同时 `domain/cockpit` + `domain/chassis` → 提示"是否需要补充 `domain/cross-domain` 收敛主题?"
- `domain/` 选了 4 个领域 → 触发粒度报警

**提示**:`WARN — 单篇文档 domain/ 维度超过 2 个,检索区分度可能下降;若为跨域文档请使用 domain/cross-domain 收敛`

#### §8.1 快速对照卡(供 lint engine 实现时直接落表)

| 规则类型                                | 通用判定条件                                                           | 行为 | 提示信息                                          |
| --------------------------------------- | ---------------------------------------------------------------------- | ---- | ------------------------------------------------- |
| **基础结构校验 (Required Axes)**  | 必填轴缺失:`docform/` 或 `domain/` 任一缺失                        | FAIL | "必填轴 [domain/docform] 缺失,请补充"             |
| **单值/软上限校验 (Cardinality)** | 单值轴(`docform/` `maturity/`)被多选                               | FAIL | "单值轴 [axis] 被多选,请只保留一个值"             |
| **主题-技术共存 (Co-occurrence)** | 存在特定`domain/` 但 `tec/` 轴缺少配套技术栈                       | WARN | "主题 [domain] 缺少对应的 [tec] 标准或技术栈支撑" |
| **层级-技术对齐 (Alignment)**     | `layer/` 与 `tec/` 的抽象层级严重失配                              | WARN | "架构层级 [layer] 与技术栈 [tec] 存在层级错配"    |
| **形态-成熟度约束 (Constraint)**  | `docform/interface-spec` 配 `maturity/concept`(及其他下限冲突案例) | FAIL | "接口规范/排查分析类文档的成熟度不能低于 pilot"   |
| **跨域粒度控制 (Threshold)**      | `domain/` 数量 > 2 且未打 `domain/cross-domain`                    | WARN | "多领域文档建议使用 domain/cross-domain 进行收敛" |

> 实现侧可把这 6 行直接落到 lint 配置文件(`.lint-rules.yaml` / `tag-lint.json`),每条范式在配置里只是一段条件表达式 + 提示模板,新增示例族挂到对应范式下,无需改 lint engine 主体。

---

---

## 9. 组合打签实例

```yaml
---
title: 基于 MCP 协议的座舱大模型调用线控转向 SOA 接口定义书
tags:
  - domain/cross-domain
  - domain/chassis
  - layer/middleware-soa
  - layer/ai-agent
  - phase/architecture
  - tec/mcp
  - tec/someip
  - docform/interface-spec
  - maturity/pilot
---
```

```yaml
---
title: ISO 26262 ASIL-D 流程下的 AUTOSAR Classic ECU 软件安全机制设计
tags:
  - domain/fusa
  - layer/bsw-os
  - layer/application
  - phase/architecture
  - tec/autosar-cp
  - tec/iso26262-asil-d              # 具体 ASIL 等级
  - docform/technical-doc
  - maturity/production
---
```

```yaml
---
title: S32G 网关 SoC 安全启动(ATF + OP-TEE + RPMB) 设计文档
tags:
  - domain/fusa
  - domain/body-gateway
  - layer/bsw-os
  - phase/detail-design
  - tec/s32g                         # 芯片平台
  - tec/atf                          # 安全启动
  - tec/optee                        # TEE 应用
  - tec/rpmb                         # 防回滚存储
  - docform/technical-doc
  - maturity/pilot
---
```

```yaml
---
title: 整车中央网关 TARA 威胁分析与 SecOC 安全通信方案
tags:
  - domain/cybersecurity
  - layer/middleware-soa
  - phase/architecture
  - tec/iso21434                     # TARA 威胁建模
  - tec/secoc                        # Secure Onboard Communication
  - tec/hsm                          # 硬件安全模块
  - tec/macsec                       # 链路层加密
  - docform/technical-doc
  - maturity/production
---
```
