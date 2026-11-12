# Grafana 面板

`cloudops-inspector-dashboard.json` 是可直接导入的 Grafana 面板，包含：

- 健康分、CRIT、WARN 三个统计卡片
- 最近巡检时间、Prometheus Target 状态
- 健康分趋势（7 天）
- OK / WARN / CRIT / ERROR / SKIP 数量趋势
- 最近一次检查状态表格

## 导入

Grafana → Dashboards → New → Import → Upload JSON，选择 Prometheus 数据源。

或者用 API：

```bash
export GRAFANA_URL=http://127.0.0.1:3000
export GRAFANA_USER=admin
export GRAFANA_PASSWORD='...'

# 先取 Prometheus datasource UID
DS_UID=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  "$GRAFANA_URL/api/datasources" \
  | python3 -c 'import json,sys; print(next(x["uid"] for x in json.load(sys.stdin) if x["type"]=="prometheus"))')
export DS_UID

python3 - <<'PY'
import json, os
p = "cloudops-inspector-dashboard.json"
d = json.load(open(p, encoding="utf-8"))
d = json.loads(json.dumps(d).replace("${DS_PROMETHEUS}", os.environ["DS_UID"]))
json.dump({"dashboard": d, "overwrite": True}, open("/tmp/dash-payload.json", "w"))
PY

curl -s -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  -H 'Content-Type: application/json' \
  -X POST "$GRAFANA_URL/api/dashboards/db" \
  -d @/tmp/dash-payload.json
```

Dockprom 的 Grafana 默认在 `127.0.0.1:3000`，不要直接对公网开放；本地用 SSH 隧道：

```bash
ssh -L 3000:127.0.0.1:3000 root@<server>
```

然后访问 `http://127.0.0.1:3000/d/cloudops-inspector`。
