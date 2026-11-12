# Prometheus 接入

CloudOps Inspector 的 API 默认只监听 `127.0.0.1:8000`，不会暴露公网。Dockprom 场景需要让 API 监听 Docker 网桥地址，供 Prometheus 容器访问。

## Dockprom（Prometheus 在容器里）

1. 让 API 监听 `172.17.0.1:8000`（systemd drop-in）：

```bash
mkdir -p /etc/systemd/system/cloudops-inspector-api.service.d
cat > /etc/systemd/system/cloudops-inspector-api.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/opt/cloudops-inspector/.venv/bin/python -m cloudops_inspector serve \
  --db /var/lib/cloudops/inspector.db \
  --host 172.17.0.1 \
  --port 8000
EOF
systemctl daemon-reload
systemctl restart cloudops-inspector-api.service
curl -s http://172.17.0.1:8000/health
```

2. 给 Dockprom 的 `prometheus` 服务加 host gateway：

```yaml
  prometheus:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

3. 把 `cloudops-inspector-scrape.yml` 里的 job 加到 `prometheus/prometheus.yml` 的 `scrape_configs:` 下。

4. 把 `cloudops-inspector-alert.rules.yml` 放到 `prometheus/`，并在 `prometheus.yml` 里引用：

```yaml
rule_files:
  - /etc/prometheus/cloudops-inspector-alert.rules.yml
```

5. 校验并重载 Prometheus：

```bash
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
cd /opt/dockprom
docker compose up -d prometheus
```

6. 在 Prometheus `Status -> Targets` 里确认 `cloudops-inspector` 为 UP，在 `Alerts` 里确认规则已加载。

## 宿主机直接装 Prometheus

把 target 改成 `127.0.0.1:8000`，并确保 API 服务已启动：

```bash
systemctl status cloudops-inspector-api.service
curl -s http://127.0.0.1:8000/metrics | head
```

## 指标

| 指标 | 说明 |
|------|------|
| `cloudops_inspector_runs_total` | 历史巡检次数 |
| `cloudops_inspector_last_score` | 最近一次健康分 |
| `cloudops_inspector_last_duration_ms` | 最近一次耗时 |
| `cloudops_inspector_last_run_timestamp_seconds` | 最近一次运行时间 |
| `cloudops_inspector_last_checks{status="ok\|warn\|crit\|error\|skip"}` | 最近一次各状态数量 |

## 告警规则

- `CloudOpsInspectorLowScore`: 分数低于 80，持续 15 分钟
- `CloudOpsInspectorCriticalFindings`: 出现 CRIT，持续 5 分钟
- `CloudOpsInspectorExecutionErrors`: 检查执行失败
- `CloudOpsInspectorStale`: 超过 25 小时没有新巡检

告警只是提示，修复动作仍应走变更窗口；尤其是 SSH、firewalld、SELinux 相关项。
