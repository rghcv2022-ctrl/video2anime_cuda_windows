# Video to Anime (CUDA / Windows)

一个本地运行的 Windows 视频动画化小工具。

当前项目路线已经收敛为：

- **本地运行**
- **Anaconda / conda 环境启动**
- **优先走 NVIDIA CUDA**
- **AnimeGANv2 动画化**
- **自动下载模型**
- **保留原音频**
- **GUI + 命令行**

> 说明：项目已经**移除 EXE 打包路线**，不再维护 PyInstaller 方案。
> 当前推荐方式是直接运行 conda / bat 启动器。

## 当前默认风格

- `hayao`：默认日漫风
- `paprika`：偏暖色
- `shinkai`：更干净、偏电影感

## 当前最推荐的启动方式

直接双击：

```text
run_gpu_gui.bat
```

这条路径会：

1. 激活 `video2anime39` conda 环境
2. 直接启动 GUI
3. 使用当前已经验证过的 CUDA / cuDNN 环境

如果你更想走“自动检查环境”的方式，也可以用：

```text
run_gui.bat
```

## 目录结构

- `app.py`：GUI + CLI 入口
- `anime_pipeline.py`：核心推理与视频处理流程
- `requirements.txt`：依赖
- `environment.yml`：Conda 环境定义
- `setup_conda.bat`：自动创建 / 修复 conda 环境
- `run_gui.bat`：自动准备环境后启动 GUI
- `run_gpu_gui.bat`：直接用现成 GPU 环境启动 GUI（推荐）
- `setup_windows.ps1`：保留的 venv 初始化脚本

## 你这台机器上的当前状态

已经确认：

- Python：**Anaconda 3.9.7**
- GPU：**NVIDIA RTX 3070 Laptop GPU**
- CUDA：可用
- cuDNN：可用
- ONNX Runtime：在 conda 环境里可激活 **CUDAExecutionProvider**

## 清晰度说明（已做的改进）

你之前觉得输出视频不够清楚，这个问题我已经针对性修了两处：

1. **修正 AnimeGANv2 ONNX 输入布局**
   - 模型实际输入是 **NHWC**
   - 不再错误按 NCHW 喂入

2. **动态输入模型不再强制缩到 512**
   - 如果模型支持动态尺寸，就直接使用源视频帧尺寸
   - 不再默认先缩小再放大
   - 这会明显减少“发糊”问题

所以当前版本比之前的第一版更清楚。

## GUI 用法

1. 选择输入视频
2. 选择输出视频路径
3. 选风格（默认 `hayao`）
4. 设备选择：
   - `auto`：优先 CUDA，失败再 CPU
   - `cuda`：强制 CUDA
   - `cpu`：只用 CPU
5. 点 **Start Convert**

## 命令行用法

```powershell
cd C:\Users\HAOTIAN ZHANG\video2anime_cuda_windows
conda activate video2anime39
python app.py --input input.mp4 --output output_anime.mp4 --style hayao --device auto
```

不保留音频：

```powershell
python app.py --input input.mp4 --output output_anime.mp4 --style hayao --device auto --no-audio
```

## 工作原理

1. 首次运行时自动下载 AnimeGANv2 ONNX 模型
2. 用 OpenCV 读取视频逐帧
3. 根据模型输入布局（NHWC / NCHW）自动适配
4. 对支持动态输入的模型，尽量保持源分辨率处理
5. 用 ONNX Runtime 推理（优先 CUDA）
6. 输出写回视频并尽量合并原音频

## 已知限制

- 第一版更偏 **稳妥可跑**，不是影视级超精细版本
- 超长视频会比较耗时
- 如果源视频很大（如 4K），建议先试短片段
- 目前是 **逐帧处理**，没有做时序一致性优化，所以少量闪烁是正常的
- AnimeGANv2 本身更偏风格化，不是超分辨率模型

## 故障排查

### 1. 没走 CUDA

日志里会显示：

- `ONNX Runtime provider: CUDAExecutionProvider`
- 或 `ONNX Runtime provider: CPUExecutionProvider`

如果看到 CPU，说明当前环境没有正确启用 GPU。

### 2. 没有音频

第一版会尽量提取并合并音频，但如果源视频音频流很特殊，可能会退回无音频输出。

### 3. 视频还是不够清楚

如果你对清晰度要求更高，下一步建议不是继续堆 AnimeGANv2，而是：

- 换更强的 stylization 模型
- 或增加独立的超分辨率 / 去闪烁步骤

## 后续可升级方向

如果你要，我下一步可以继续给这个项目加：

- 批量处理整个文件夹
- 拖拽视频到窗口直接转换
- 输出分辨率 / 码率设置
- 更高质量的视频编码流程
- 去闪烁 / 帧稳定
- 更强的动画化模型
