# build-server-inspect · 编译服务器全方位检测

一个 GitHub Action，对任意编译服务器（GitHub 托管 Runner 或**你的自托管 Runner**）做全方位体检，自动生成一份**详细的中文配置与性能报告**：

- 硬件配置：CPU 型号/核心/频率/缓存/NUMA、内存、磁盘（SSD/HDD/容量/型号）、网络接口
- 性能实测（不依赖任何第三方安装包，纯 Python 基准）：
  - CPU 单线程 & 多线程并行吞吐、多核扩展比
  - 内存顺序读写带宽
  - 磁盘顺序读写、随机 4K 读 IOPS
  - **真实编译基准**：6 个中等 C++ 翻译单元 `make -jN -O2` 实测编译耗时
- 运行环境：OS/内核/架构、工具链版本表（gcc/clang/make/cmake/ninja/python/java/rustc/go/docker…）、Runner 关键环境变量、cgroup CPU/内存配额
- 自动诊断：按实测结果给出评级（星级）、瓶颈分析和针对性建议（内存不足、机械盘、IOPS 低、核数少、配额限制等）

报告生成后：写入 Actions 摘要页可直接查看，同时作为 artifact 上传（30 天内可下载）。

## 用法

### 方式一：检测 GitHub 托管 Runner（默认）

仓库 → Actions → **编译服务器全方位检测** → Run workflow：
- `runner` 填 `ubuntu-latest`（或其他托管镜像：`windows-latest`、`macos-14` 等，Linux 脚本在 Windows/macOS 上部分项会降级）
- `mode` 选 `full`（完整，约 1 分钟）或 `quick`（跳过多核扩展、随机 IO 与编译基准）

### 方式二：检测你自己的编译服务器（自托管 Runner）

1. 仓库 → Settings → Actions → Runners → 在服务器上按提示添加 runner（记得填 Label，如 `self-hosted`）
2. 触发 workflow 时 `runner` 填你的 Label（如 `self-hosted` 或服务器标签组）
3. 报告中的硬件与基准即为**你服务器的真实性能**，可用于长期监控机器是否降频、磁盘是否老化

### 方式三：服务器本地直接运行（不经过 GitHub）

在装有 Python 3.8+ 的编译机上：

```bash
git clone https://github.com/lky005/build-server-inspect.git
cd build-server-inspect
bash scripts/inspect.sh full   # 或 quick
# 报告输出在 artifacts/report.md
```

## 报告示例结构

| 项目 | 实测值 | 评级 |
| --- | --- | --- |
| CPU 单线程 | 8.4 百万迭代/秒 | ★★★★☆ 良（≥6.5） |
| 内存顺序写带宽 | 5.2 GB/s | ★★★★☆ 良（≥4） |
| 磁盘随机 4K 读 | 45210 IOPS | ★★★★☆ 良（≥2万） |
| 编译吞吐 | 0.72 翻译单元/秒 | ★★★☆☆ 中（≥0.4） |

## 说明

- 评级阈值为经验参考值，可在 `scripts/render_report.py` 中按需调整。
- 检测为只读 + 临时文件基准：会在临时目录写入并删除 1GB 测试文件，不会改动系统配置。
- 报告含主机名、内网/公网 IP、MAC 等环境信息，**仓库建议保持 private**；artifact 默认 30 天后自动清理。
- 如需扩展检测项（如网络带宽测试、更多编译器），在 `scripts/collect.py` / `scripts/bench.py` 中追加即可。
