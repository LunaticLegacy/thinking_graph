## P0（发布阻断项，先做）

### 1) 修复 README 与仓库实际内容不一致

这是第一优先级，影响信任感最大。README 里写了 `tests/`、`CONTRIBUTING.md`、`LICENSE`、`app_config.toml`，但当前仓库顶层实际可见的是 `app_config_example.toml`，且 `LICENSE`、`CONTRIBUTING.md` 链接/文件当前抓取为 404。([GitHub][1])

**整改动作**

* 补上 `LICENSE`（如果真是 MIT，就把标准文本落库）
* 补上 `CONTRIBUTING.md`
* README 的项目结构改成“与当前目录一致”
* 把 `app_config.toml` 改成 `app_config_example.toml` + `.gitignore` 说明
* 对尚未完成的能力（如插件系统/移动端）统一标注 `Planned`

**验收标准**

* README 中所有相对链接无 404
* README 项目结构与仓库实际一致
* 新人按 README 一次成功启动（至少本机）

---

### 2) 建立最小 CI（至少做 lint + test + 启动 smoke test）

当前 Actions 页呈现的是 GitHub Actions 介绍页，而不是项目工作流列表，说明 CI 信号缺失。([GitHub][2])

**整改动作**

* 新增 `.github/workflows/ci.yml`
* CI 步骤至少包含：

  * 安装依赖
  * 语法检查（`ruff` / `flake8`）
  * 单测（`pytest`）
  * 启动冒烟测试（`python main.py` 或 app factory import 测试）
* Python 版本矩阵：至少 `3.11`（README 也写了 3.11+）([GitHub][3])

**验收标准**

* PR 自动跑 CI
* 主分支 CI 常绿（绿灯）

---

### 3) 补最小测试集（不是追求覆盖率数字，是先保核心不炸）

README 写了“测试套件”，但仓库顶层没看到 `tests/`。([GitHub][3])

**优先测这些（高价值）**

* `backend/repository.py`

  * schema 初始化
  * transaction 提交/回滚
  * 节点/连接 CRUD 的基本一致性
* `web/__init__.py`

  * app factory 能创建 app
  * fallback DB 行为可预期（见下一条）
* `GraphService`（如果有）

  * 空节点、自环、引用完整性等规则
* `LLMService`

  * timeout / malformed JSON / provider error 的兜底路径

**验收标准**

* 至少 10–20 个核心用例
* 覆盖关键异常路径，而不只是 happy path

---

### 4) 把“生产模式”和“开发模式”分开（尤其是数据库 fallback）

`web/__init__.py` 里仓库写入失败会自动 fallback 到临时目录数据库（`tempfile.gettempdir()/thinking_graph.db`），并且还会把配置路径改掉。这个在开发期很友好，但在生产环境可能导致“数据写到了意外位置”。([GitHub][4])

**整改动作**

* 增加 `ENV=development|production`
* **production 模式下禁用 silent fallback**（直接 fail-fast 并报错）
* fallback 行为只保留给开发模式
* 启动时显式打印最终 DB 路径（日志）

**验收标准**

* 生产环境数据库不可写时，进程明确报错退出
* 开发环境 fallback 有显式 warning 日志

---

### 5) 依赖与安装整理（把“能装”变成“稳定可复现”）

当前 `requirements.txt` 很简，但比较粗；可见 `Flask`, `Flask-Cors`, `openai`, `toml`, `asyncpg`, `dataclasses` 混在一起。([GitHub][5])

**整改动作**

* 明确 Python 版本（README 已写 3.11+）并与依赖策略一致([GitHub][3])
* 拆分依赖：

  * `requirements/base.txt`
  * `requirements/dev.txt`
  * `requirements/llm-local.txt`（可选）
* 给出锁版本方案（`pip-tools` / `uv lock` / Poetry 任一）
* 检查 `dataclasses` 是否对 Py3.11 仍需要（通常不需要）
* `asyncpg` 若未使用，先移除或写明“预留”

**验收标准**

* 新环境安装成功率高
* 一条命令完成开发环境启动
* 依赖用途有说明

---

### 6) 做一个“正式发布最小清单”（Release hygiene）

虽然 README 写得很像成品，但仓库还缺对外发布的基本姿势。README 里甚至展示了类似库 API 用法 `from thinking_graph import GraphBuilder`，容易让用户以为已经是成熟包。([GitHub][3])

**整改动作**

* 明确当前定位：`Web App (alpha)` 还是 `Python package + Web UI`
* 加 `CHANGELOG.md`
* 版本号（SemVer）
* 打 tag / GitHub Release（哪怕先从 `v0.1.0-alpha` 开始）
* README 开头加状态徽章（Alpha/Beta）

**验收标准**

* 用户能分辨“演示版”和“稳定版”
* 每次发布有变更说明

---

## P1（接近产品化，建议第二阶段完成）

### 7) API/数据契约稳定化（避免前后端一起改一起炸）

你现在有 datamodels 和分层设计，这是好基础。下一步要把“结构化”升级成“契约化”。([GitHub][1])

**整改动作**

* 明确 REST API 路由文档（哪怕是简版）
* 请求/响应 schema 校验（Pydantic 或 dataclass + 手写校验也行）
* 统一错误码与错误响应结构
* 数据库 schema version（迁移策略）

**验收标准**

* 前端/后端可独立迭代
* 升级后旧数据不会无声损坏

---

### 8) 可观测性（日志/告警/基本指标）

没有可观测性，就不算“正式产品”。

**整改动作**

* 结构化日志（JSON 或标准字段）
* 请求级日志（request id）
* 错误分级（业务错误 / 系统错误 / 外部 LLM 错误）
* 基础指标（QPS、错误率、LLM 调用耗时、DB 操作耗时）
* Sentry/等价异常收集（可选但很值）

**验收标准**

* 出问题时能定位“是前端、后端、数据库还是 LLM provider”

---

### 9) LLM 接入可靠性（超时、重试、限流、成本控制）

README 把多后端 LLM 作为核心卖点之一，这部分如果不做可靠性治理，很容易一上线就翻车。([GitHub][3])

**整改动作**

* provider timeout / retry / backoff
* 熔断（连续失败时降级）
* 统一 provider 抽象接口
* 返回内容校验（尤其 JSON）
* token/成本统计
* 可配置降级策略（仅规则审计，不走 LLM）

**验收标准**

* 任一 provider 异常不导致整个功能不可用
* 错误可解释，且对用户友好

---

### 10) 安全基线（哪怕是个人项目，也要有）

尤其仓库是 Web 应用形态。([GitHub][6])

**整改动作**

* CORS 默认关闭或限域（不是全开）
* 配置文件里的 API key 严禁入库（只用环境变量或本地未跟踪文件）
* 输入长度限制 / 基础 XSS 处理（节点内容、描述字段）
* 速率限制（如果对外）
* 安全响应头（CSP 可后置，但至少基础头部）
* `.env.example` / `app_config_example.toml` 的敏感项说明

**验收标准**

* 不会因为一个恶意输入直接把页面或服务打崩
* 默认配置尽量安全

---

### 11) 备份与恢复（你的项目强调审计追踪，这项必须补）

你仓库里已有审计和快照表设计，这是优势；产品化要把“存在表结构”升级成“可恢复流程”。([GitHub][7])

**整改动作**

* 导出/导入（JSON 先行）
* 定时备份（即使是脚本）
* 启动时 schema/version 检查
* 恢复演练文档（不是只写“支持恢复”）

**验收标准**

* 可以从备份恢复到可运行状态
* 恢复步骤有文档可复现

---

## P2（体验与扩展，做了更像“完成品”）

### 12) 前端体验打磨

README 展示的是“可视化 + 交互编辑”的产品体验，正式产品需要更多 UX 细节。([GitHub][3])

**建议项**

* 空白状态引导（示例图模板）
* 撤销/重做
* 自动保存状态提示
* 大图性能优化（节点多时）
* 键盘快捷键
* 导入导出 UX（拖拽文件）

---

### 13) 文档体系拆分（用户文档 vs 开发者文档）

现在 README 很全，但偏“全塞一起”。

**整改动作**

* `README.md`：定位、安装、快速开始
* `docs/architecture.md`：架构设计
* `docs/configuration.md`：LLM/数据库配置
* `docs/deployment.md`：部署
* `docs/troubleshooting.md`：常见问题
* `docs/roadmap.md`：路线图与里程碑

---

### 14) 发布与部署模板（降低试用门槛）

**整改动作**

* Dockerfile
* `docker-compose.yml`（本地一键启动）
* 生产部署示例（Nginx + Gunicorn / Waitress）
* 反代与静态资源说明
