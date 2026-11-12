# 设计说明

## 目标

CloudOps Inspector 不是再做一个 Prometheus，而是补上监控栈不擅长的部分：

- 配置基线：SSH、firewalld、SELinux、时间同步
- 巡检报告：一次运行给出可读的 HTML/Markdown/JSON
- 历史趋势：SQLite 保存每次运行，能看到问题是变多还是变少
- 只读安全：不自动改生产配置，修复建议只写在报告里

它和 Dockprom 的分工：

```text
Dockprom:  指标采集 + 告警 + 可视化
Inspector: 配置基线 + 巡检报告 + 历史趋势 + 巡检结果指标
```

## 架构

```text
inventory.yml
      │
      ▼
OpenSSH / Local executor
      │  (asyncio, timeout, per-host isolation)
      ▼
22 个 Check ──► YAML RuleSet ──► CheckResult
      │                              │
      └──────────────┬───────────────┘
                     ▼
              HostReport / RunReport
               │        │         │
            HTML     SQLite    JSON / Markdown
                        │
                  FastAPI /metrics
                        │
                  Prometheus ──► Grafana / Alertmanager
```

## 关键取舍

### 1. 只读，不做自动修复

自动改 SSH、firewalld、SELinux 的风险很高：

- 改 `PermitRootLogin` 可能把自己锁在服务器外
- 开 firewalld 可能破坏 Docker 端口映射
- SELinux 切 Enforcing 可能影响容器挂载

所以 v1 只输出建议，修复动作交给变更窗口。这个边界也让工具可以安全地在生产环境跑。

### 2. 默认用系统 OpenSSH，而不是 asyncssh

`asyncssh` 是可选后端，但默认走系统 `ssh`：

- 兼容用户已有的 `~/.ssh/config`、ProxyJump、agent
- 不需要在 Python 里重新实现 SSH 细节
- 出问题时可以直接用同样的 `ssh` 命令复现

`CLOUDOPS_SSH_BACKEND=asyncssh` 可以切换，依赖在 `requirements-optional.txt`。

### 3. YAML 规则，而不是把阈值写死在代码里

阈值因环境而异。比如数据库机器的内存阈值和跳板机不一样，所以：

```yaml
checks:
  disk_usage:
    warn: 80
    crit: 90
  ssh_config:
    severity: crit
```

规则和采集分离，新增机器只需要改 inventory，调阈值不需要改 Python。

### 4. SQLite，而不是只依赖 Prometheus

Prometheus 适合看时间序列，但不适合保存完整报告和每个检查的明细。SQLite 负责：

- 保存每次 run 的摘要
- 保存每个 host / check 的结果
- 给 HTML、CLI history、FastAPI 提供数据

Prometheus 只暴露最近一次运行的聚合指标，避免把高基数明细塞进时序库。

### 5. 定时任务用 `--exit-zero`

CLI 默认在出现 CRIT/ERROR 时返回 1，方便 CI 或人工判断；但 systemd oneshot 会把 1 当成失败，导致 timer 显示 failed。

所以：

- 人工跑：默认非 0，方便脚本判断
- systemd：加 `--exit-zero`，报告照常生成，服务状态保持 success

### 6. Prometheus 接入

API 默认只监听本机；Docker 场景下绑定 `172.17.0.1:8000`，只让 Docker 网桥访问，不对公网开放。

Dockprom 的 Prometheus 在容器里，通过：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

访问宿主机 API。指标只保留最近一次 run 的聚合值：

- `cloudops_inspector_last_score`
- `cloudops_inspector_last_checks{status=...}`
- `cloudops_inspector_last_run_timestamp_seconds`

## 真实踩过的坑

### Docker 29 的 `ps --format`

最初用了：

```text
{{.Names}}|{{.State}}|{{.RestartCount}}|{{.Status}}
```

Docker 29 不支持 `.RestartCount`，命令直接失败，报告显示 0 个容器。修复：

- 只使用 `Names/State/Status`
- 命令失败且无输出时标记 ERROR，而不是当成 0
- 补了失败测试

这个坑很适合在面试里讲：**工具最危险的不是报错，而是静默地把失败当成正常**。

### 主机指纹变化

重开实例后 SSH host key 变化，`known_hosts` 冲突。处理方式是先确认实例身份，再更新 known_hosts；不能直接忽略指纹告警。

### SSH / firewalld / SELinux 告警

工具会把这些标为 CRIT/WARN，但不自动修。实际处理顺序：

1. 先确认还有别的登录方式
2. 再改 SSH
3. 在维护窗口验证 firewalld/SELinux 对 Docker 的影响
4. 改完重新巡检，确认分数变化

## 可以继续扩展

- MySQL 检查：连接数、主从延迟、慢查询
- 证书到期检查
- `--only` / `--skip` 按检查项运行
- 多主机分组和标签过滤
- Grafana 面板嵌入报告

## 面试时怎么讲

建议按这个顺序：

1. 为什么做：Dockprom 能看指标，但看不到 SSH/防火墙/SELinux 这些基线
2. 怎么设计：inventory → executor → checks → rules → report/storage → Prometheus
3. 最难的点：只读安全边界、命令失败不能静默、Docker 格式兼容
4. 怎么验证：22 个测试、真实 CentOS 巡检、Prometheus target UP
5. 怎么改进：MySQL 检查、证书、按标签过滤
