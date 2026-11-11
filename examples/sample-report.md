# CloudOps Inspector 巡检报告

- Run ID: `67b40ad3-1d52-4a19-a19f-799ce2186d36`
- 开始时间: 2026-11-11T09:24:50.191723+00:00
- 耗时: 0 ms
- 主机数: 1
- 总分: **72/100**
- 统计: OK 15 / WARN 6 / CRIT 1 / ERROR 0 / SKIP 0

## centos9 (`192.0.2.10`)

- 评分: **72/100**
- 统计: OK 15 / WARN 6 / CRIT 1 / ERROR 0 / SKIP 0

| 检查项 | 状态 | 数值 | 摘要 |
|--------|------|------|------|
| CPU 使用率 | 正常 | 21% | CPU 使用率: 21.00% |
| 每核负载 | 正常 | 0.1 | 每核 load1: 0.10 |
| 内存使用率 | 正常 | 50% | 内存使用率: 50.00% |
| Swap 使用率 | 严重 | 50% | Swap 使用率: 50.00% |
| 磁盘使用率 | 警告 | 85% | 最高磁盘使用率 (/data): 85.00% |
| Inode 使用率 | 正常 | 1% | 最高 inode 使用率 (/): 1.00% |
| systemd 失败单元 | 警告 | 1个 | 失败单元: 1 |
| 僵尸进程 | 警告 | 3个 | 僵尸进程数: 3.00个 |
| 文件描述符使用率 | 正常 | 0.1% | 文件描述符使用率: 0.10% |
| 日志目录大小 | 警告 | 3GB | 日志目录大小: 3.00GB |
| Docker 服务状态 | 正常 |  | Docker 服务: active |
| Docker 容器健康 | 警告 | 1个 | 容器 2 个；unhealthy=0 restarting=1 |
| Docker 可回收空间 | 警告 | 40% | Docker 可回收空间: 40.00% |
| 监听端口 | 正常 | 2个 | 监听端口 2 个 |
| SSH 安全基线 | 正常 |  | SSH 基线通过 |
| 防火墙状态 | 正常 |  | firewalld: active |
| SELinux 状态 | 正常 |  | SELinux: Enforcing |
| 时间同步 | 正常 |  | NTP 同步: yes |
| 是否需要重启 | 正常 |  | 重启标记: no |
| 运行时长 | 正常 | 1.4天 | 运行 1.4 天 |
| 内核版本 | 正常 |  | 内核: 5.14.0-427.el9.x86_64 |
| 时区 | 正常 |  | 时区: Asia/Shanghai |

**需要关注：**
- Swap 使用率: used=1.0GiB total=2.0GiB
  - 建议: Swap 持续使用说明内存压力大；检查内存占用，避免依赖 swap 运行数据库。
- 磁盘使用率: /data=85%; /=50%
  - 建议: 清理日志/镜像层，或扩容磁盘；不要只删除大文件而不排查增长来源。
- systemd 失败单元: nginx.service loaded failed failed nginx
  - 建议: systemctl status <unit> 查看失败原因；修复后 systemctl reset-failed。
- Docker 容器健康: api: restarting
  - 建议: 查看 docker ps -a / docker logs <name>；重启次数高要检查应用和资源限制。
- Docker 可回收空间: Images|1.2GB|1.2GB (40%); Containers|10MB|0B (0%)
  - 建议: 确认无用镜像/容器后执行 docker image prune / docker system prune，避免误删运行中依赖。
