# Video to Anime (CUDA / Windows)

一个本地运行的 Windows 视频动画化小工具：

- 默认使用 **AnimeGANv2**
- 优先走 **CUDA / NVIDIA GPU**
- 自动下载 ONNX 模型
- 支持 **GUI** 和 **命令行**
- 尽量保留原视频音频
- 输出旁边会生成一份 `json` 元数据，方便排查问题
- 现在支持 **Anaconda 3.9 一键启动**

## 当前默认风格

- `hayao`：默认日漫风
- `paprika`：偏暖色
- `shinkai`：更干净、偏电影感

## 目录结构

- `app.py`：GUI + CLI 入口
- `anime_pipeline.py`：模型下载、CUDA 推理、音频合并
- `requirements.txt`：依赖
- `environment.yml`：Conda 环境定义
- `setup_conda.bat`：自动创建/修复 conda 环境
- `run_gui.bat`：**双击即可启动**
- `build_exe.bat`：**一键打包 EXE**
- `video2anime.spec`：PyInstaller 打包配置
- `setup_windows.ps1`：保留的 venv 版初始化脚本

## 你这台机器的当前默认方案

已经按你的环境调整为：

- 默认 Python：**Anaconda 3.9.7**
- 默认 pip：**Anaconda pip**
- 默认 `py` launcher：**Anaconda 3.9.7**
- GPU：**NVIDIA RTX 3070 Laptop GPU**

所以你现在最简单的用法就是：

## 一键启动

现在有两种启动方式：

### 1. `run_gui.bat`

这是原来的自动准备环境 + 启动 GUI 方式。

### 2. `run_gpu_gui.bat`（当前最推荐）

这是基于你已经修好的 `video2anime39` conda 环境直接启动的版本。
当前机器上它是**最接近“开箱即用 + 真走 GPU”**的方式。

直接双击：

```text
run_gpu_gui.bat
```

它会自动做这些事：

1. 检查 Anaconda 是否可用
2. 检查 conda 环境 `video2anime39` 是否存在
3. 没有的话自动创建
4. 检查依赖是否齐全
5. 缺依赖就自动安装
6. 自动启动 GUI

## 当前最稳的可用结论

- **源码 / conda 启动**：已确认可走 GPU
- 已修正 AnimeGANv2 ONNX 输入布局适配（NHWC / NCHW），避免出现 `generator_input:0` 维度错误
- 现在开始切到新的 EXE 方案：**主程序瘦打包，onnxruntime/cudnn 首次启动自动下载并缓存**
- 如果你现在就要用，优先双击：

```text
run_gpu_gui.bat
```

## 首次启动会稍慢

第一次双击时，脚本可能需要：

- 创建 conda 环境
- 安装 `opencv-python`
- 安装 `onnxruntime-gpu`
- 安装其他依赖
- 首次运行时下载 AnimeGANv2 模型

所以**第一次慢是正常的**，后面再开会快很多。

## 一键打包 EXE

直接双击：

```text
build_exe.bat
```

它会自动：

1. 检查 / 修复 conda 环境
2. 补齐打包依赖（PyInstaller）
3. 清理旧的 build / dist
4. 打包生成可分发启动器

默认输出位置：

```text
dist\Video2AnimeCUDA\Video2AnimeCUDA.exe
```

### 打包版说明（新方案）

- 打包后的 EXE 是**瘦启动器**，不再强行内置 `onnxruntime-gpu`
- 第一次启动时会自动下载并缓存运行时到：

```text
%LOCALAPPDATA%\Video2AnimeCUDA\runtime\py39\site-packages
```

- 之后再次启动会直接复用缓存，不重复下载
- 模型仍然会缓存到：

```text
%LOCALAPPDATA%\Video2AnimeCUDA\models
```

## 命令行用法（conda 环境）

如果你想手动跑：

```powershell
cd C:\Users\HAOTIAN ZHANG\video2anime_cuda_windows
conda activate video2anime39
python app.py --input input.mp4 --output output_anime.mp4 --style hayao --device auto
```

不保留音频：

```powershell
python app.py --input input.mp4 --output output_anime.mp4 --style hayao --device auto --no-audio
```

## GUI 用法

1. 选择输入视频
2. 选择输出视频路径
3. 选风格（默认 `hayao`）
4. 设备选择：
   - `auto`：优先 CUDA，失败再 CPU
   - `cuda`：强制 CUDA
   - `cpu`：只用 CPU
5. 点 **Start Convert**

## 工作原理

1. 首次运行时自动下载 AnimeGANv2 ONNX 模型
2. 用 OpenCV 读取视频逐帧
3. 每帧缩放并 letterbox 到模型输入尺寸
4. 用 ONNX Runtime 推理（优先 CUDA）
5. 输出写回 MP4
6. 用 FFmpeg（二进制由 `imageio-ffmpeg` 自动提供）尽量提取并合并原音频

## 已知限制

- 第一版更偏 **稳妥可跑**，不是影视级超精细版本
- 超长视频会比较耗时
- 如果源视频很大（如 4K），建议先试短片段
- 目前是 **逐帧处理**，没有做时序一致性优化，所以少量闪烁是正常的
- 不同 AnimeGANv2 ONNX 模型在不同场景上的表现会有差异
- 如果 CUDA provider 没装好，`auto` 会退回 CPU

## 运行时下载缓存说明

首次启动 EXE 时会下载两类运行时包：

- `onnxruntime-gpu`
- `nvidia-cudnn-cu11`

这一步会比较慢，而且需要联网。
下载完成后会缓存在本地，后面就不会重复拉。

## 额外说明：为什么脚本里强制用了 `C:\Temp\conda_tmp`

你这台机器上，conda 在某些场景下会被带空格的用户临时目录绊住。
所以启动脚本会临时把：

- `TEMP`
- `TMP`

指到：

```text
C:\Temp\conda_tmp
```

这是为了让 conda 更稳，不影响你正常使用。

## 后续可升级方向

如果你要，我下一步可以继续给这个项目加：

- 批量处理整个文件夹
- 拖拽视频到窗口直接转换
- 输出分辨率/码率设置
- 进度预估剩余时间
- 更高级模型（比如更强的 cartoon / anime stylization）
- 单文件 onefile EXE / 安装包
- 帧插值 / 去闪烁 / 时序稳定

## 故障排查

### 1. 一键启动时报 conda 错误

先确认：

```powershell
conda --version
python --version
py --version
```

### 2. 没走 CUDA

CLI 或 GUI 日志里会显示：

- `ONNX Runtime provider: CUDAExecutionProvider`
- 或 `ONNX Runtime provider: CPUExecutionProvider`

如果看到 CPU，说明 CUDA provider 没启起来。

### 3. 没有音频

第一版会尽量提取并合并音频，但如果源视频音频流很特殊，可能会退回无音频输出。

## 建议

先找一个 **10~30 秒** 的小视频试跑。

如果你愿意，我下一步可以继续帮你把它：

1. **补成可直接双击的 EXE 打包版**
2. **做成更好看的 GUI**
3. **加“批量处理整个文件夹”**
