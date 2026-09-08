#!/usr/bin/env python3
"""收集系统的硬件配置、工具链版本与 Runner 环境信息（只读，无需 root），输出 sysinfo.json。"""
import json
import os
import platform
import re
import shutil
import subprocess
import time

OUT = {}


def read(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


# ---------------- 系统 ----------------
os_release = {}
for line in read("/etc/os-release").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os_release[k] = v.strip('"')
OUT["os"] = os_release.get("PRETTY_NAME") or os_release.get("NAME") or platform.system()
u = platform.uname()
OUT["kernel"] = f"{u.system} {u.release} {u.version}"
OUT["arch"] = u.machine
OUT["hostname"] = u.node

try:
    r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=10, shell=False)
    OUT["uptime"] = (r.stdout or r.stderr).strip() or "n/a"
except Exception:
    OUT["uptime"] = "n/a"

OUT["date"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")

# ---------------- CPU ----------------
cpuinfo = read("/proc/cpuinfo")
models = set(re.findall(r"^model name\s*:\s*(.+)$", cpuinfo, re.M))
OUT["cpu_model"] = models.pop() if models else ""
OUT["cpu_threads"] = len(re.findall(r"^processor\s*:", cpuinfo, re.M))
sockets = set(re.findall(r"^physical id\s+:+\s*(\d+)$", cpuinfo, re.M))
core_ids = set(re.findall(r"^core id\s+:+\s*(\d+)$", cpuinfo, re.M))
OUT["cpu_sockets"] = len(sockets) or 1
OUT["cpu_cores"] = len(core_ids) if core_ids else OUT["cpu_threads"]

mhz = re.findall(r"^cpu MHz\s*:\s*([\d.]+)$", cpuinfo, re.M)
if mhz:
    OUT["cpu_mhz_now"] = round(float(mhz[0]), 1)
freq_max = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
if freq_max:
    OUT["cpu_max_ghz"] = round(int(freq_max) / 1e6, 2)
freq_min = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq")
if freq_min:
    OUT["cpu_min_ghz"] = round(int(freq_min) / 1e6, 2)

caches = []
for i in range(4):
    level = read(f"/sys/devices/system/cpu/cpu0/cache/index{i}/level")
    ctype = read(f"/sys/devices/system/cpu/cpu0/cache/index{i}/type")
    size = read(f"/sys/devices/system/cpu/cpu0/cache/index{i}/size")
    if level and size:
        caches.append(f"L{level} {ctype}: {size}")
OUT["cpu_cache"] = caches

numa_online = read("/sys/devices/system/node/online")
OUT["numa_nodes"] = numa_online or "1"

# Runner 的 CPU 配额（cgroup v2，GitHub 托管 Runner 可能有限制）
cpu_max = read("/sys/fs/cgroup/cpu.max")
if cpu_max and cpu_max not in ("max", "max max"):
    parts = cpu_max.split()
    OUT["cgroup_cpu_quota"] = f"{parts[0]}/{parts[1]}（每 100 万周期 ≈ 1 核）" if len(parts) == 2 else cpu_max

# ---------------- 内存 ----------------
meminfo = {}
for line in read("/proc/meminfo").splitlines():
    parts = line.split(":")
    if len(parts) == 2:
        meminfo[parts[0]] = parts[1].strip()


def gb(kb_str):
    try:
        return round(int(kb_str.split()[0]) / 1024 / 1024, 2)
    except Exception:
        return None


OUT["mem_total_gb"] = gb(meminfo.get("MemTotal", "0"))
OUT["mem_available_gb"] = gb(meminfo.get("MemAvailable", "0"))
OUT["mem_swap_gb"] = gb(meminfo.get("SwapTotal", "0"))
mem_max = read("/sys/fs/cgroup/memory.max")
if mem_max and mem_max.isdigit():
    OUT["cgroup_mem_max_gb"] = round(int(mem_max) / 1024**3, 2)

# ---------------- 磁盘 ----------------
disks = []
block_root = "/sys/block"
if os.path.isdir(block_root):
    for name in os.listdir(block_root):
        if re.match(r"^(loop|ram|sr|fd|zram|dm-)", name):
            continue
        try:
            sectors = int(read(os.path.join(block_root, name, "size")))
            rota = read(os.path.join(block_root, name, "queue/rotational"))
            model = (read(os.path.join(block_root, name, "device/model")) or name).strip()
            vendor = read(os.path.join(block_root, name, "device/vendor")).strip()
            if vendor:
                model = f"{vendor} {model}"
            disks.append({
                "name": name,
                "size_gb": round(sectors * 512 / 1024**3, 1),
                "type": "HDD" if rota == "1" else "SSD",
                "model": model,
            })
        except Exception:
            continue
OUT["disks"] = disks

try:
    r = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=10, shell=False)
    df_lines = [ln for ln in (r.stdout or "").splitlines() if ln]
    OUT["disk_usage"] = df_lines[:12]
except Exception:
    OUT["disk_usage"] = []

# ---------------- 网络 ----------------
nets = []
for iface in sorted(os.listdir("/sys/class/net")):
    if iface == "lo" or not re.fullmatch(r"[A-Za-z0-9_.-]+", iface):
        continue
    mac = read(f"/sys/class/net/{iface}/address")
    ipv4 = ""
    if shutil.which("ip"):
        try:
            r = subprocess.run(["ip", "-4", "-o", "addr", "show", iface],
                               capture_output=True, text=True, timeout=10, shell=False)
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", r.stdout)
            ipv4 = m.group(1) if m else ""
        except Exception:
            pass
    nets.append({"iface": iface, "ipv4": ipv4, "mac": mac})
OUT["net_ifaces"] = nets

# ---------------- 工具链 ----------------
TOOLS = [
    "gcc", "g++", "clang", "clang++", "cc", "make", "cmake", "ninja",
    "python3", "node", "npm", "java", "mvn", "rustc", "cargo", "go",
    "docker", "docker-compose", "podman", "apt", "dnf", "yum",
    "git", "zip", "unzip", "tar", "jq", "lscpu", "sysbench", "fio",
]
toolchain = {}
missing = []
SPECIAL_FIRST_LINE = {"java": ["java", "-version"], "rustc": ["rustc", "--version"]}
for t in TOOLS:
    if not shutil.which(t):
        missing.append(t)
        continue
    if t in ("lscpu", "sysbench", "fio"):
        toolchain[t] = "已安装"
        continue
    args = SPECIAL_FIRST_LINE.get(t, [t, "--version"])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=10, shell=False)
        out = (r.stdout or r.stderr)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        toolchain[t] = lines[0][:110].strip() if lines else "已安装"
    except Exception:
        toolchain[t] = "已安装"
OUT["toolchain"] = toolchain
OUT["toolchain_missing"] = missing

# ---------------- Runner 环境 ----------------
env = {k: v for k, v in os.environ.items()
       if k.startswith(("CI", "RUNNER", "GITHUB_")) and k != "GITHUB_TOKEN"}
OUT["runner_env"] = env

print(json.dumps(OUT, ensure_ascii=False, indent=2))
