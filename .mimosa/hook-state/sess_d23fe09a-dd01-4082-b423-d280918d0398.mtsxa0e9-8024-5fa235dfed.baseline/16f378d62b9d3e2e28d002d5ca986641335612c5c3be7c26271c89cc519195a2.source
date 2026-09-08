#!/usr/bin/env python3
"""读取 sysinfo.json / bench.json，渲染中文 Markdown 检测报告（artifacts/report.md）。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "artifacts"
with (BASE / "sysinfo.json").open(encoding="utf-8") as f:
    S = json.load(f)
with (BASE / "bench.json").open(encoding="utf-8") as f:
    B = json.load(f)

STARS = "★★★★★"


def stars(score, t5, t4, t3, t2):
    """score 达到 t5/t4/t3/t2 分别给 5/4/3/2 星，否则 1 星。返回 (星串, 等级名)。"""
    levels = [(5, t5, "优"), (4, t4, "良"), (3, t3, "中"), (2, t2, "偏弱")]
    for n, thr, name in levels:
        if score is not None and score >= thr:
            return STARS[:n] + "☆" * (5 - n), f"{name}（≥{thr}）"
    return "★☆☆☆☆", "弱（<{})".format(t2)


def esc(v):
    return str(v).replace("|", "\\|") if v is not None else "n/a"


cpu = B.get("cpu") or {}
mem = B.get("memory") or {}
disk = B.get("disk") or {}
build = B.get("build")

records = []
records.append(("CPU 单线程", cpu.get("single_millions_per_sec"), "百万迭代/秒",
                {5: 10, 4: 6.5, 3: 3.5, 2: 1.8}))
if cpu.get("multi_iters_per_sec"):
    base = 10 * (cpu.get("threads") or 1)
    records.append(("CPU 多核并行吞吐", cpu.get("multi_millions_per_sec"), "百万迭代/秒",
                    {5: base * 0.8, 4: base * 0.6, 3: base * 0.4, 2: base * 0.25}))
if cpu.get("speedup") is not None:
    records.append(("CPU 多核扩展比", cpu.get("speedup"), "倍数（理想=核数）",
                    {5: 0.85, 4: 0.65, 3: 0.45, 2: 0.25}))
records.append(("内存顺序写带宽", mem.get("write_gbs"), "GB/s", {5: 6, 4: 4, 3: 2, 2: 1}))
records.append(("内存顺序读带宽", mem.get("read_gbs"), "GB/s", {5: 6, 4: 4, 3: 2, 2: 1}))
records.append(("磁盘顺序写", disk.get("seq_write_mbs"), "MB/s", {5: 700, 4: 250, 3: 80, 2: 30}))
records.append(("磁盘顺序读", disk.get("seq_read_mbs"), "MB/s", {5: 1400, 4: 500, 3: 120, 2: 40}))
if disk.get("rand_4k_read_iops") is not None:
    records.append(("磁盘随机 4K 读", disk.get("rand_4k_read_iops"), "IOPS",
                    {5: 80000, 4: 20000, 3: 2000, 2: 300}))
if build:
    records.append(("编译吞吐", build.get("throughput_units_per_s"), "翻译单元/秒",
                    {5: 1.5, 4: 0.8, 3: 0.4, 2: 0.15}))

rated = []
for name, val, unit, th in records:
    s, lv = stars(val, th[5], th[4], th[3], th[2])
    rated.append((name, val, unit, s, lv))

scores = [s.count("★") for _, _, _, s, _ in rated]
avg = sum(scores) / len(scores) if scores else 0
if avg >= 4.5:
    overall = "顶尖（非常适合作为正式编译服务器）"
elif avg >= 3.5:
    overall = "优秀（满足大部分大型项目编译需求）"
elif avg >= 2.5:
    overall = "良好（可编译中小型项目，大型项目会偏慢）"
elif avg >= 1.5:
    overall = "一般（建议重点优化短板项）"
else:
    overall = "较弱（仅适合轻量任务，建议升级硬件）"

# ---------------- 建议 ----------------
sugg = []
threads = S.get("cpu_threads") or 0
mem_gb = S.get("mem_total_gb") or 0
if threads <= 2:
    sugg.append(f"CPU 线程数偏少（{threads}），并行编译收益有限；若长期用于构建，建议升级多核，"
                f"当前并行度建议 make -j{threads}。")
if mem_gb and mem_gb < 8:
    sugg.append(f"内存仅 {mem_gb} GB，大型构建（内核、LLM、鸿蒙工程）容易 OOM 或触发 swap；"
                f"建议 ≥16GB，并确保有 swap 兜底。")
hdd = [d["name"] for d in S.get("disks", []) if d.get("type") == "HDD"]
if hdd:
    sugg.append(f"检测到机械硬盘（{'/'.join(hdd)}）。编译大量读写中间文件，HDD 会显著拖慢构建，"
                f"建议将工作目录/缓存移到 SSD 或 NVMe。")
riops = disk.get("rand_4k_read_iops")
if riops is not None and riops < 20000:
    sugg.append(f"随机读 IOPS（{round(riops)}）偏低，属云盘/机械盘典型表现；构建缓存目录建议置于本地高性能盘，"
                f"或使用 ccache 减少 IO。")
sp = cpu.get("speedup")
if sp is not None and sp < 0.6:
    sugg.append(f"多核扩展比仅 {sp}，核心间性能不均衡，常见于 vCPU 超售、共享邻居或散热降频；"
                f"追求稳定构建时长建议用独占实例或物理机。")
bt = build.get("elapsed_s") if build else None
if bt is not None and bt > 15:
    sugg.append(f"6 个翻译单元实测编译 {bt} 秒，吞吐中等偏慢；小文件高频编译受单核性能主导，"
                f"可考虑换单核更强的 CPU 或启用 ccache。")
cgrp = S.get("cgroup_cpu_quota")
if cgrp:
    sugg.append(f"检测到 cgroup CPU 配额：{cgrp}。这是平台对 CPU 用量的上限（GitHub 托管 Runner 常见），"
                f"构建并行度超过配额并不会提速，建议并行度设为配额对应的核数。")

sugg += [
    "长期作编译服务器建议开启性能调度：`cpupower frequency-set -g performance`（或写入内核参数），避免降频波动。",
    "把本 workflow 挂到你的自托管 Runner（仓库 Settings → Actions → Runners 添加标签），每次触发即可对比机器性能变化。",
    "增量构建强烈建议上 ccache 或 sccache，实测可减少 60%~90% 重复编译时间。",
]

# ---------------- 渲染报告 ----------------
L = []
L.append("# 🔧 编译服务器全方位检测报告\n")
L.append(f"> 检测时间：{esc(S.get('date'))} · 主机：`{esc(S.get('hostname'))}`\n")
L.append("## 一、概览\n")
L.append("| 项目 | 值 |")
L.append("| --- | --- |")
L.append(f"| 操作系统 | {esc(S.get('os'))} |")
L.append(f"| 内核 / 架构 | {esc(S.get('kernel'))} / {esc(S.get('arch'))} |")
L.append(f"| 在线时长 | {esc(S.get('uptime'))} |")
L.append(f"| 综合评级 | **{overall}**（{avg:.1f}/5 星） |")
L.append("")

L.append("## 二、硬件配置\n")
L.append(f"**CPU：** `{esc(S.get('cpu_model'))}`\n")
L.append("| 项目 | 值 |")
L.append("| --- | --- |")
ht = "是" if (S.get("cpu_threads") or 0) > (S.get("cpu_cores") or 0) else "否/不可见"
L.append(f"| 插槽 / 核心 / 线程 | {esc(S.get('cpu_sockets'))} / {esc(S.get('cpu_cores'))} / {esc(S.get('cpu_threads'))}（超线程: {ht}） |")
L.append(f"| 当前频率 | {esc(S.get('cpu_mhz_now'))} MHz |")
if S.get("cpu_min_ghz"):
    L.append(f"| 频率范围 | {esc(S.get('cpu_min_ghz'))} ~ {esc(S.get('cpu_max_ghz'))} GHz |")
L.append(f"| 缓存 | {'，'.join(S.get('cpu_cache') or [])} |")
L.append(f"| NUMA 节点 | {esc(S.get('numa_nodes'))} |")
if S.get("cgroup_cpu_quota"):
    L.append(f"| ⚠ cgroup CPU 配额 | {esc(S.get('cgroup_cpu_quota'))}（平台限制） |")
L.append("")
mem_line = f"**内存：** 总量 {esc(S.get('mem_total_gb'))} GB，可用 {esc(S.get('mem_available_gb'))} GB，Swap {esc(S.get('mem_swap_gb'))} GB"
if S.get("cgroup_mem_max_gb"):
    mem_line += f"，cgroup 上限 {esc(S.get('cgroup_mem_max_gb'))} GB"
L.append(mem_line + "\n")
L.append("**磁盘：**\n")
L.append("| 设备 | 类型 | 容量 | 型号 |")
L.append("| --- | --- | --- | --- |")
for d in S.get("disks", []):
    L.append(f"| {esc(d['name'])} | {esc(d['type'])} | {esc(d['size_gb'])} GB | {esc(d['model'])} |")
L.append("")
L.append("磁盘占用：\n")
L.append("```\n" + "\n".join(S.get("disk_usage", [])) + "\n```\n")
L.append("**网络接口：**\n")
L.append("| 接口 | IPv4 | MAC |")
L.append("| --- | --- | --- |")
for n in S.get("net_ifaces", []):
    L.append(f"| {esc(n['iface'])} | {esc(n['ipv4'])} | `{esc(n['mac'])}` |")
L.append("")

L.append("## 三、工具链与运行环境\n")
L.append("| 工具 | 版本 |")
L.append("| --- | --- |")
for t, v in S.get("toolchain", {}).items():
    L.append(f"| {t} | `{esc(v)}` |")
if S.get("toolchain_missing"):
    L.append(f"\n未安装（可选）：{', '.join(S['toolchain_missing'])}")
L.append("\nRunner 关键环境：\n")
L.append("```")
for k, v in S.get("runner_env", {}).items():
    L.append(f"{k}={v}")
L.append("```\n")

L.append("## 四、性能实测\n")
L.append("| 项目 | 实测值 | 评级 |")
L.append("| --- | --- | --- |")
for name, val, unit, s, lv in rated:
    L.append(f"| {name} | {esc(val)} {unit} | {s} {lv} |")
L.append("")
L.append("> 评级阈值为经验参考值，可在 `scripts/render_report.py` 中调整；"
          "CPU 单线程 10 百万迭代/秒 ≈ 高端桌面核，6.5 ≈ 普通服务器核；"
          "内存 ≥6GB/s、磁盘顺序写 ≥700MB/s、随机 4K ≥8 万 IOPS 为 NVMe 水平；"
          "编译吞吐 ≥1.5 翻译单元/秒 ≈ 高端多核。\n")

L.append("## 五、编译基准（真实构建实测）\n")
if build:
    L.append("| 项目 | 值 |")
    L.append("| --- | --- |")
    L.append(f"| 编译器 | {esc(build.get('compiler'))} |")
    L.append(f"| 规模 | {esc(build.get('translation_units'))} 个翻译单元 × 40 函数，make -j{esc(build.get('jobs'))} -O2 |")
    L.append(f"| 总耗时 | **{esc(build.get('elapsed_s'))} 秒** |")
    L.append(f"| 吞吐 | {esc(build.get('throughput_units_per_s'))} 翻译单元/秒 |")
    L.append("")
    L.append(f"> {esc(build.get('note'))}\n")
else:
    L.append("> 本次为 quick 模式，未跑编译基准；触发 full 模式可测。\n")

L.append("## 六、结论与建议\n")
L.append(f"**综合评级：{avg:.1f} / 5 星 —— {overall}**\n")
if sugg:
    L.append("自动诊断：\n")
    for i, s in enumerate(sugg, 1):
        L.append(f"{i}. {s}")
L.append("")

report = "\n".join(L)
(BASE / "report.md").write_text(report, encoding="utf-8")
print(report)
print("\n[渲染完成] 综合评级:", f"{avg:.1f}/5", overall)
