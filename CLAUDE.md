# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

基于 Flask + APScheduler 的任务调度系统。通过 REST API 管理 Python 脚本和定时任务，提供 CLI 工具 aps_cli 进行管理，支持 Docker 部署。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行开发服务器
python run.py

# 运行生产服务
gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app

# 运行所有测试
pytest

# 运行单个测试
pytest tests/test_jobs_api.py
pytest tests/test_scheduler.py -k "test_interval"

# 带覆盖率运行测试
pytest --cov=app --cov=aps_cli

# 安装 CLI 工具（开发模式）
pip install -e .

# 使用 CLI 工具
aps_cli script list
aps_cli job list
aps_cli sched status
aps_cli docker up -d

# Docker 部署
docker compose up --build -d
```

## 项目架构

### 三层结构

```
REST API (Flask Blueprints) → APScheduler (后台调度器) → Python 脚本执行
```

### 核心模块

- **app/routes/__init__.py** — Flask 应用工厂，注册 Blueprint、初始化 DB、配置日志（JSON 格式）
- **app/routes/scripts.py** — 脚本 CRUD API (`/api/scripts/*`)
- **app/routes/jobs.py** — 任务 CRUD + 暂停/恢复/触发/日志 API (`/api/jobs/*`)
- **app/routes/status.py** — 调度器状态 & 健康检查 (`/api/scheduler/status`, `/api/health`)
- **app/scheduler.py** — APScheduler 调度器核心：脚本执行（线程池+超时控制）、重试机制、触发解析、执行日志记录
- **app/script_manager.py** — 脚本文件与磁盘同步（写入/删除 .py 文件到 scripts/ 目录）
- **app/models.py** — SQLAlchemy 模型：Script（脚本）、Job（任务）、ExecutionLog（执行日志）
- **app/config.py** — 配置类，支持环境变量覆盖
- **app/errors.py** — 统一错误处理（AppError 异常 + 全局 errorhandler）
- **aps_cli/main.py** — Click CLI，子命令分组：script、job、sched、docker

### 数据流

1. 用户通过 API/CLI 创建 Script → 存入 DB 并同步写入 `scripts/` 目录
2. 用户创建 Job（关联 Script）→ 存入 DB 并注册到 APScheduler
3. 调度器触发时调用 `_execute_script(script_name)` → 动态导入并执行脚本的 `run()` 或 `main()` 函数
4. 执行结果（成功/失败/超时）记录到 ExecutionLog

### 关键设计

- **run.py** 和 **wsgi.py** 在启动时从 DB 加载所有已启用的 Job 注册到调度器
- APScheduler 使用 SQLAlchemyJobStore，任务持久化到同一 SQLite 数据库
- 脚本执行使用 4 线程的 ThreadPoolExecutor，支持超时和自动重试
- DB 操作放在 SQLite 文件（默认 `instance/scheduler.db`），测试时使用 `:memory:`
- 所有 API 响应是 JSON 格式，AppError 异常由统一 errorhandler 捕获
