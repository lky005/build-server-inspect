#!/usr/bin/env bash
# 编译服务器全方位检测入口：收集系统信息 -> 性能基准 -> 渲染报告
# 用法: bash scripts/inspect.sh [full|quick]   在仓库根目录运行
set -euo pipefail

MODE="${1:-full}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p artifacts

echo "==> [1/3] 收集系统配置、硬件、工具链信息..."
python3 scripts/collect.py > artifacts/sysinfo.json

echo "==> [2/3] 运行性能基准（${MODE} 模式，约 30~60 秒）..."
python3 scripts/bench.py --mode "$MODE" > artifacts/bench.json

echo "==> [3/3] 渲染详细报告..."
python3 scripts/render_report.py

echo "完成。报告: artifacts/report.md （原始数据: sysinfo.json / bench.json）"
