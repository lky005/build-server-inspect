#!/usr/bin/env python3
"""性能基准：
1) CPU 单线程（混合整数/浮点负载）
2) CPU 多线程并行吞吐与扩展比
3) 内存顺序读写带宽
4) 磁盘顺序写/顺序读/随机 4K 读（IOPS）
5) 微型 C++ 并行构建计时（真实反映编译吞吐）
输出 bench.json。
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

OUT = {}


def bench_dir(prefix):
    """创建受控临时目录并返回 Path（mkdtemp 随机生成，位于系统临时目录内）。"""
    return Path(tempfile.mkdtemp(prefix=prefix)).resolve()


def work_loop(seconds):
    """混合负载：xorshift 整数运算 + 三角函数浮点运算，返回迭代次数。"""
    t_end = time.perf_counter() + seconds
    it = 0
    x = 123456789
    y = 1.0000001
    while time.perf_counter() < t_end:
        for _ in range(64):
            x ^= (x << 13) & 0xFFFFFFFF
            x ^= x >> 17
            x ^= (x << 5) & 0xFFFFFFFF
            y = math.sin(y) * 1.0000001 + 0.4999999
        it += 1
    return it


def bench_cpu(mode):
    threads = os.cpu_count() or 1
    single_ips = work_loop(1.5) / 1.5
    multi_ips = None
    speedup = None
    if mode == "full":
        with ProcessPoolExecutor(max_workers=threads) as ex:
            results = list(ex.map(work_loop, [2.0] * threads))
        multi_ips = sum(results) / 2.0
        speedup = multi_ips / single_ips
    return {
        "threads": threads,
        "single_iters_per_sec": round(single_ips, 1),
        "single_millions_per_sec": round(single_ips / 1e6, 2),
        "multi_iters_per_sec": round(multi_ips, 1) if multi_ips else None,
        "speedup": round(speedup, 2) if speedup else None,
        "note": "负载为 xorshift 整数运算与 sin/cos 浮点运算混合，模拟编译期 CPU 高压力场景",
    }


def bench_mem():
    size = 256 * 1024 * 1024  # 256MB，避免占用过多内存
    buf = bytearray(size)
    mv = memoryview(buf).cast("I")
    t0 = time.perf_counter()
    for i in range(0, size, 4096):
        buf[i:i + 4096] = b"\x01" * 4096
    write_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    total = sum(mv)
    read_s = time.perf_counter() - t0
    del buf
    return {
        "buf_mb": size // 1024 // 1024,
        "write_gbs": round(size / write_s / 1e9, 2),
        "read_gbs": round(size / read_s / 1e9, 2),
        "checksum": total & 0xFF,
        "note": "256MB 内存块顺序读写，反映内存带宽",
    }


def bench_disk(mode):
    tdir = bench_dir("bench_io_")
    try:
        size = 1024 * 1024 * 1024  # 1GB 测试文件
        chunk = 8 * 1024 * 1024
        fpath = tdir / "io_test.bin"
        data = os.urandom(chunk)
        with fpath.open("wb", buffering=0) as f:
            for _ in range(size // chunk):
                f.write(data)
            f.flush()
            os.fsync(f.fileno())
        wt = time.perf_counter()
        with fpath.open("rb", buffering=0) as f:
            while f.read(chunk):
                pass
        rt = time.perf_counter() - wt
        res = {
            "file_mb": size // 1024 // 1024,
            "seq_write_mbs": round(size / wt / 1e6, 1),
            "seq_read_mbs": round(size / rt / 1e6, 1),
            "note": "1GB 文件 8MB 块顺序读写（写含 fsync），随机读 4K 块 65536 次",
        }
        if mode == "full":
            n = 65536
            t0 = time.perf_counter()
            with fpath.open("rb", buffering=0) as f:
                for _ in range(n):
                    f.seek(random.randrange(0, size - 4096, 4096))
                    f.read(4096)
            rand_s = time.perf_counter() - t0
            res["rand_4k_read_iops"] = round(n / rand_s, 0)
            res["rand_4k_read_mbs"] = round(n * 4096 / rand_s / 1e6, 2)
    finally:
        for p in tdir.iterdir():
            p.unlink(missing_ok=True)
        shutil.rmtree(tdir, ignore_errors=True)
    return res


def bench_build(mode):
    if mode != "full":
        return None
    cc = shutil.which("g++") or shutil.which("clang++")
    if not cc:
        return None
    tdir = bench_dir("bench_build_")
    try:
        src = tdir / "src"
        src.mkdir()
        units = 6
        for u in range(units):
            lines = []
            for fn in range(40):
                fname = f"f{fn}_{u}"
                lines.append(f"double {fname}(double x) {{ double s=0; for(int i=0;i<2000;i++) "
                             f"s += std::sin(x*{fn+1}.0)+std::cos(x*{u+1}.0); return s; }}")
            lines.append(f"double reg{u}(double x) {{ return " +
                         "+".join(f"f{i}_{u}(x+{i})" for i in range(40)) + "; }")
            (src / f"tu{u}.cpp").write_text("#include <cmath>\n" + "\n".join(lines))
        main_lines = [f"extern double reg{u}(double);" for u in range(units)]
        main_lines += ["int main(){ double s=0; for(int i=0;i<500;i++) "
                       f"for(int u=0;u<{units};u++) s+=reg{units-1}(0.001*i); return (int)s; }}"]
        (src / "main.cpp").write_text("\n".join(main_lines))
        objs = " ".join(f"tu{u}.o" for u in range(units)) + " main.o"
        (src / "Makefile").write_text(
            f"prog: {objs}\n\t{cc} -O2 $^ -o prog -lm\n"
            "%.o: %.cpp\n\t"
            f"{cc} -O2 -std=c++17 -c $< -o $@\n")
        jobs = os.cpu_count() or 1
        t0 = time.perf_counter()
        subprocess.run(["make", "-j", str(jobs)], cwd=src, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = time.perf_counter() - t0
        return {
            "translation_units": units,
            "jobs": jobs,
            "compiler": os.path.basename(cc),
            "elapsed_s": round(elapsed, 2),
            "throughput_units_per_s": round(units / elapsed, 2),
            "note": f"{units} 个中等大小 C++ 翻译单元（每个含 40 个函数）make -j{jobs} -O2 编译耗时",
        }
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full", choices=["full", "quick"])
    args = ap.parse_args()
    OUT["cpu"] = bench_cpu(args.mode)
    OUT["memory"] = bench_mem()
    OUT["disk"] = bench_disk(args.mode)
    OUT["build"] = bench_build(args.mode)
    print(json.dumps(OUT, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
