# APS Scheduler

基于 Flask + APScheduler 的定时任务调度系统。通过 REST API 管理 Python 脚本和定时任务，提供 CLI 工具 `aps_cli` 进行管理，支持 Docker 部署。

## 架构

```
REST API (Flask Blueprints) → APScheduler (后台调度器) → Python 脚本执行 (conda run)
```

## 功能

- **脚本管理** — Python 脚本的增删改查，自动写入 `scripts/` 目录
- **任务调度** — 基于 APScheduler 的定时任务（interval / cron / date 触发器），支持暂停/恢复/手动触发
- **执行日志** — 每次执行记录日志（状态、输出、错误、耗时），支持按任务查询
- **Conda 环境隔离** — 脚本运行在独立的 Conda 环境中，按 `requirements.txt` 自动创建/匹配环境
- **CLI 管理工具** — `aps_cli` 命令行管理脚本、任务、调度器状态、Docker 容器
- **Docker 部署** — 一键 Docker Compose 部署，含健康检查
- **统一错误处理** — JSON 格式的错误响应
- **JSON 日志** — 结构化日志输出，含请求耗时

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行开发服务器
python run.py

# 安装 CLI 工具（开发模式）
pip install -e .
```

## API 文档

### 脚本 (Scripts)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scripts` | 脚本列表 |
| GET | `/api/scripts/<id>` | 脚本详情 |
| POST | `/api/scripts` | 创建脚本 |
| PUT | `/api/scripts/<id>` | 更新脚本 |
| DELETE | `/api/scripts/<id>` | 删除脚本 |

创建脚本请求体：

```json
{
  "name": "my_task",
  "description": "任务描述",
  "content": "def run():\n    print('hello')",
  "requirements": "requests==2.31.0"
}
```

requirements 非空时将自动创建对应的 Conda 环境。

### 任务 (Jobs)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jobs` | 任务列表 |
| GET | `/api/jobs/<job_id>` | 任务详情 |
| POST | `/api/jobs` | 创建任务 |
| PUT | `/api/jobs/<job_id>` | 更新任务 |
| DELETE | `/api/jobs/<job_id>` | 删除任务 |
| POST | `/api/jobs/<job_id>/pause` | 暂停任务 |
| POST | `/api/jobs/<job_id>/resume` | 恢复任务 |
| POST | `/api/jobs/<job_id>/trigger` | 手动触发 |
| GET | `/api/jobs/<job_id>/logs` | 执行日志 |

创建任务请求体：

```json
{
  "job_id": "job1",
  "script_name": "my_task",
  "trigger": "interval",
  "trigger_args": "{\"seconds\": 30}",
  "enabled": true
}
```

支持的触发器：`interval`、`cron`、`date`。

### 调度器状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scheduler/status` | 调度器运行状态及任务列表 |
| GET | `/api/health` | 健康检查（含 DB 连接检查） |

### Conda 环境

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/envs` | 环境列表 |
| POST | `/api/envs/cleanup` | 清理未使用的环境 |

## CLI 工具

```bash
aps_cli script list          # 脚本列表
aps_cli script show <id>     # 脚本详情
aps_cli script create -n <name> -f <file> [-r requirements]
aps_cli script update <id> [-n name] [-f file]
aps_cli script delete <id>

aps_cli job list             # 任务列表
aps_cli job show <job_id>    # 任务详情
aps_cli job create --job-id <id> --script <name> --trigger interval --trigger-args '{"seconds":30}'
aps_cli job update <job_id> [--script name] [--trigger interval] [--enabled true]
aps_cli job delete <job_id>
aps_cli job pause <job_id>
aps_cli job resume <job_id>
aps_cli job trigger <job_id>
aps_cli job logs <job_id>

aps_cli sched status         # 调度器状态

aps_cli env list             # Conda 环境列表
aps_cli env cleanup          # 清理未使用的环境

aps_cli docker up -d         # Docker Compose 启动
aps_cli docker down          # 停止容器
aps_cli docker logs -f       # 查看日志
aps_cli docker restart       # 重启容器
aps_cli docker ps            # 容器列表
```

## Docker 部署

```bash
# 构建并启动
docker compose up --build -d

# 或使用 CLI
aps_cli docker up -d

# 服务运行在 http://localhost:5000
```

默认使用 SQLite 数据库，数据持久化在 Docker volume 中。

## 项目结构

```
├── app/
│   ├── __init__.py           # Flask app 入口
│   ├── config.py             # 配置类（环境变量覆盖）
│   ├── errors.py             # 统一错误处理
│   ├── models.py             # SQLAlchemy 模型（Script, Job, ExecutionLog, ScriptEnv）
│   ├── scheduler.py          # APScheduler 调度器核心
│   ├── script_manager.py     # 脚本文件与磁盘同步
│   └── routes/
│       ├── __init__.py       # 应用工厂，注册 Blueprint
│       ├── scripts.py        # 脚本 CRUD API
│       ├── jobs.py           # 任务 CRUD + 控制 API
│       ├── status.py         # 调度器状态 & 健康检查
│       └── envs.py           # Conda 环境管理 API
├── aps_cli/
│   ├── __init__.py
│   └── main.py               # Click CLI 入口
├── scripts/                  # 脚本文件存储目录
├── run.py                    # 开发服务器入口
├── wsgi.py                   # 生产部署入口
├── setup.py                  # CLI 工具安装配置
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
