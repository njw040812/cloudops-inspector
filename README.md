# CloudOps Inspector

![tests](https://github.com/njw040812/cloudops-inspector/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> 面向 Linux 云服务器的**只读巡检与基线报告工具**。不替代 Prometheus，补的是“配置基线 / 巡检报告 / 历史趋势”。

## 它解决什么问题

监控系统告诉你“CPU 高了”，CloudOps Inspector 告诉你：

- 哪台机器的磁盘/inode 快满了
- 哪些 systemd 单元失败了
- Docker 容器有没有 unhealthy / 反复重启
- SSH 是否允许 root 登录、是否还开着密码登录
- 防火墙、SELinux、时间同步、重启标记是否正常
- 和上次巡检相比，问题是变多还是变少

所有检查都是**只读命令**，不会修改服务器配置。

## 功能

- 22 个检查项：系统资源、systemd、Docker、网络、SSH、安全基线
- 并发巡检多台主机（asyncio + SSH）
- YAML 规则：阈值、严重度、启停
- 输出 HTML / Markdown / JSON 报告，带健康分和修复建议
- SQLite 保存历史，CLI 查看趋势
- FastAPI 查询历史 + Prometheus `/metrics`
- systemd timer 每日巡检；可选 Docker 镜像

示例报告（模拟数据）：[examples/sample-report.html](examples/sample-report.html)

## 架构

```
inventory.yml
     │
     ▼
SSH / Local executor ──► 22 checks ──► RuleSet(YAML)
     │                                   │
     └──────────────┬────────────────────┘
                    ▼
             HostReport / RunReport
              │        │         │
           HTML     SQLite    JSON / Markdown
                       │
                 FastAPI /metrics
```

## 快速开始（Linux）

要求 Python 3.9+、OpenSSH 客户端；被巡检主机需要 SSH key 登录。

默认使用系统 `ssh` 客户端（兼容性最好）。如果想用 `asyncssh` 后端：

```bash
pip install -r requirements-optional.txt
export CLOUDOPS_SSH_BACKEND=asyncssh
```

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp examples/inventory.yml inventory.yml
# 编辑 inventory.yml 里的主机、用户、key
python -m cloudops_inspector inspect \
  --inventory inventory.yml \
  --rules rules/default.yml \
  --db data/inspector.db \
  --output reports
```

打开 `reports/inspection-*.html` 查看报告。

如果巡检本机，把 inventory 的 `address` 设为 `localhost`，程序会使用本地执行器，不需要 SSH。

### 本机演示（不连远端）

```bash
python -m cloudops_inspector inspect \
  --inventory examples/inventory.local.yml \
  --db data/inspector.db \
  --output reports
```

## 检查项

| 类别 | 检查 |
|------|------|
| system | CPU、每核 load、内存、Swap、磁盘、inode、systemd failed、僵尸进程、fd 使用率、/var/log 大小、uptime、内核、时区 |
| docker | Docker 服务、容器 unhealthy/restarting、可回收空间 |
| network | 监听端口 |
| security | SSH 基线（root 登录/密码登录/MaxAuthTries）、firewalld、SELinux、时间同步、重启标记 |

查看全部：

```bash
python -m cloudops_inspector checks
```

## 规则

`rules/default.yml`：

```yaml
checks:
  disk_usage:
    warn: 80
    crit: 90
  ssh_config:
    severity: crit
  uptime:
    enabled: true
```

- `warn` / `crit` 是数值阈值
- `severity` 用于非数值检查（SSH/SELinux 等）
- `enabled: false` 可关闭检查

## 历史与 API

```bash
python -m cloudops_inspector history --db data/inspector.db --limit 10
python -m cloudops_inspector serve --db data/inspector.db --port 8000
```

接口：

- `GET /health`
- `GET /api/v1/checks`
- `GET /api/v1/runs?limit=20`
- `GET /api/v1/runs/{run_id}`
- `GET /metrics`

生产环境用 systemd 常驻 API（默认只监听 127.0.0.1；Docker 主机会绑定 172.17.0.1 供 Prometheus 抓取，不暴露公网）：

```bash
systemctl enable --now cloudops-inspector-api.service
curl -s http://172.17.0.1:8000/health     # Docker 主机
# 非 Docker 主机用 http://127.0.0.1:8000/health
curl -s http://172.17.0.1:8000/metrics | head
```

Prometheus 接入与告警规则见 [deploy/prometheus/README.md](deploy/prometheus/README.md)。

## Grafana 面板

可导入的看板 JSON：[deploy/grafana/cloudops-inspector-dashboard.json](deploy/grafana/cloudops-inspector-dashboard.json)

包含健康分、CRIT/WARN、最近巡检时间、Target 状态、7 天趋势和检查状态表格。导入方式见 [deploy/grafana/README.md](deploy/grafana/README.md)。

## 设计说明

架构、关键取舍和真实踩坑记录见 [docs/design.md](docs/design.md)。

## 部署到 CentOS Stream 9

```bash
sudo mkdir -p /opt/cloudops-inspector /etc/cloudops /var/lib/cloudops
# 把项目放到 /opt/cloudops-inspector
cd /opt/cloudops-inspector
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

sudo cp examples/inventory.local.yml /etc/cloudops/inventory.yml
sudo cp rules/default.yml /etc/cloudops/rules.yml
sudo .venv/bin/python -m cloudops_inspector inspect \
  --inventory /etc/cloudops/inventory.yml \
  --rules /etc/cloudops/rules.yml \
  --db /var/lib/cloudops/inspector.db \
  --output /var/lib/cloudops/reports
```

systemd：

```bash
sudo cp systemd/cloudops-inspector.service /etc/systemd/system/
sudo cp systemd/cloudops-inspector-api.service /etc/systemd/system/
sudo cp systemd/cloudops-inspector.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudops-inspector.timer cloudops-inspector-api.service
```

或者一键安装（CentOS Stream 9，root）：

```bash
git clone https://github.com/njw040812/cloudops-inspector.git /opt/cloudops-inspector
cd /opt/cloudops-inspector
bash scripts/install-centos9.sh
```

## Docker

```bash
docker build -t cloudops-inspector .
docker run --rm \
  -v "$PWD/inventory.yml:/app/inventory.yml:ro" \
  -v "$HOME/.ssh:/root/.ssh:ro" \
  -v "$PWD/reports:/app/reports" \
  cloudops-inspector inspect --inventory inventory.yml --output reports
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest
```

测试用 `FakeExecutor` 注入命令输出，不依赖真实服务器；覆盖规则、解析、报告、SQLite、API。

## 安全边界

- 只执行只读命令；不做自动修复
- 只支持 SSH key，不把密码写入 inventory
- 默认 `StrictHostKeyChecking=accept-new`；生产建议配置 `known_hosts`
- 不采集业务数据，只采集系统/容器/SSH 基线
- 报告里可能包含主机名和端口，公开仓库不要提交真实报告

## 限制

- 只支持 Linux（systemd + coreutils + OpenSSH）
- Docker 检查在未安装 Docker 时跳过
- 复杂环境（SELinux 自定义策略、非 systemd）需要扩展检查

## License

MIT
