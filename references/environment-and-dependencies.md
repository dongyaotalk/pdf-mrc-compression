# 依赖、跨平台安装与检查

## 按功能准备，而不是要求安装所有工具

本 skill 是操作流程、参考资料和辅助脚本，不是包含全部第三方软件的安装包。Windows、Linux、macOS 使用同一套核心流程；依赖在当前操作系统中安装并验证。已有可用的系统环境、项目虚拟环境或运行时可以复用，不要求安装某个专属发行版或包管理器。

| 依赖 | 需要它的功能 | 必需程度 |
|---|---|---|
| Python 3.10+ | 所有随附脚本 | 必需；实际平台和版本验证范围见仓库 CI，其他组合以包支持和小样结果为准 |
| PyMuPDF，安装名 `PyMuPDF`，导入名 `pymupdf` | PDF 资源审计、逐页及原生图片比对 | 运行 `audit_pdf.py`、`verify_lossless.py` 必需 |
| Pillow，安装名 `Pillow`，导入名 `PIL` | 二值 PNG 输入和区域编码；部分图像处理 | 运行 `encode_jbig2_region.py` 必需 |
| `jbig2enc` 提供的 `jbig2` 可执行文件 | 无字形替换的 generic JBIG2 蒙版编码 | 采用 JBIG2 策略时必需；不是 Python 包 |
| `qpdf` 可执行文件 | 对象流/Flate 整理、PDF 结构检查 | 该优化及完整交付的结构检查需要 |
| Poppler 的 `pdftoppm`；`pdfinfo` 可辅助检查 | 与 PyMuPDF 独立的渲染验证、页面信息 | 完整交付的独立渲染检查需要 `pdftoppm` |
| libjpeg-turbo 的 `jpegtran` 可执行文件 | JPEG 熵编码优化、灰度转换、DCT 裁剪/wipe | 采用这些 JPEG 策略时需要；不是用 Pillow 高质量重存替代 |
| NumPy，导入名 `numpy` | 数组分析、蒙版和颜色场计算 | 分层实现使用它时安装；目前三个随附脚本不直接依赖它 |
| OpenCV，导入名 `cv2` | 连通域、局部修补、形态学及图块保护 | 分层/修复实现使用它时安装；目前三个随附脚本不直接依赖它 |

`PyYAML` 只用于维护时运行仓库或 skill-creator 的格式校验器，列在 `requirements-dev.txt`，不是 PDF 处理的运行依赖。MRC 本身不要求新增 OCR；若用户另行要求 OCR，再准备相应工具和语言数据。项目自有内容与第三方依赖的许可分别见仓库的 `LICENSE` 和 `NOTICE.md`。

## Python 环境：Windows、Linux、macOS

先选择有对应 PyMuPDF/Pillow 发行包的 Python 和 CPU 架构。优先使用适用的预编译 wheel；缺少 wheel 时可能进入源码编译，具体构建依赖查看 [PyMuPDF 安装说明](https://pymupdf.readthedocs.io/en/latest/installation.html) 和 [Pillow 安装说明](https://pillow.readthedocs.io/en/stable/installation/basic-installation.html)。安装包名是 PyMuPDF，不要误装同名无关的 `fitz` 包。

可以在工作目录建虚拟环境；无需激活，直接使用虚拟环境解释器，避免 shell 和激活策略差异。以下命令中的 skill 路径需换成实际位置。

Linux / macOS，使用系统中实际可用的 `python3`：

```bash
python3 -m venv .venv-mrc
.venv-mrc/bin/python -m pip install -r "/path/to/pdf-mrc-compression/requirements.txt"
.venv-mrc/bin/python "/path/to/pdf-mrc-compression/scripts/audit_pdf.py" input.pdf --output audit.json
```

Windows PowerShell，使用已安装的 Python Launcher `py`；没有 Launcher 时用 Python 的实际路径：

```powershell
py -3 -m venv .venv-mrc
.\.venv-mrc\Scripts\python.exe -m pip install -r "C:\path\to\pdf-mrc-compression\requirements.txt"
.\.venv-mrc\Scripts\python.exe "C:\path\to\pdf-mrc-compression\scripts\audit_pdf.py" input.pdf --output audit.json
```

后续说明中的 `python` 都指上面选定的解释器。安装、导入检查、执行脚本必须使用同一个解释器；另一个 Python 安装过模块不代表当前环境可用。不要把运行时缓存目录写进 skill 或要求其他电脑具备同一路径。

若当前分层实现需要 NumPy/OpenCV，再在该环境中安装：

```text
python -m pip install numpy opencv-python-headless
```

批处理不需要图形窗口时可使用 headless 发行包；若已经使用其他 OpenCV Python 发行包，应按 [OpenCV Python 安装说明](https://github.com/opencv/opencv-python#installation-and-usage) 选择一种，避免多个发行包共同占用 `cv2`。

## 外部命令的跨平台准备

先检查是否已经能执行，再选择系统包、上游发行包或源码构建。包名、版本、可用平台因发行版而异，不承诺一个包管理器命令适用于所有电脑。

| 系统 | 安装路径 |
|---|---|
| Windows | Python 包在同一个 Windows 虚拟环境中安装。qpdf、libjpeg-turbo 等优先按上游文档取得适合架构的发行包；Poppler 选择可用的 Windows 构建，并确认来源及版本。将实际可执行文件目录加入当前进程 PATH，或传入完整路径。JBIG2 没有合适构建时可按上游构建；也可自愿把整条流程放在 WSL/容器中。WSL 不是这个 skill 的必备条件。 |
| Linux | 优先查询当前发行版的软件包，例如 qpdf、Poppler 命令行工具、libjpeg-turbo 工具；不同发行版包名不完全一致。`jbig2enc` 无可用软件包时按上游说明构建。Python 环境和本机命令工具保持一致的架构。 |
| macOS | 可选 Homebrew，按需执行 `brew install qpdf poppler jbig2enc jpeg-turbo`；也可用其他兼容安装方式。Python 不限定 Homebrew 来源，工具目录也不假设一定是 `/usr/local/bin` 或 `/opt/homebrew/bin`。 |

安装与构建依据：[qpdf](https://qpdf.readthedocs.io/en/stable/installation.html)、[Poppler](https://poppler.freedesktop.org/)、[libjpeg-turbo](https://www.libjpeg-turbo.org/Documentation/Documentation)、[jbig2enc](https://github.com/agl/jbig2enc/blob/master/README.md)。macOS 的 Homebrew 包名分别见 [qpdf](https://formulae.brew.sh/formula/qpdf)、[Poppler](https://formulae.brew.sh/formula/poppler)、[jbig2enc](https://formulae.brew.sh/formula/jbig2enc)、[jpeg-turbo](https://formulae.brew.sh/formula/jpeg-turbo)。

Windows 的 `.exe`、Linux/macOS 的二进制程序、WSL 内的程序不能混作同一运行环境。若选择 WSL/容器，Python 包、可执行工具、输入路径和输出路径都在该环境中解析；宿主机安装了工具不等于容器或 WSL 中也能执行。

## 运行前检查

在选定环境中执行导入检查：

```text
python -c "import sys, pymupdf; from PIL import Image; print(sys.executable); print(pymupdf.__version__); print(Image.__version__)"
```

仅当当前实现要做 NumPy/OpenCV 分层时再检查：

```text
python -c "import numpy, cv2; print(numpy.__version__); print(cv2.__version__)"
```

用同一个 Python 检查命令发现结果，避免依赖某一种 shell 的 `which`、`where` 或 `command -v`：

```text
python -c "import shutil; print({name: shutil.which(name) for name in ['qpdf', 'pdftoppm', 'pdfinfo', 'jbig2', 'jpegtran']})"
```

PATH 找不到时可以选择完整路径，不等于软件一定没安装。区域编码器支持 `--jbig2`；自行编排其他操作时也将可执行文件完整路径作为单个参数传给 `subprocess.run([...])`，不拼成依赖 POSIX shell 的命令字符串。

按本次功能运行必要命令，检查实际退出状态和输出，不仅检查文件是否存在：

```text
qpdf --version
pdftoppm -v
pdfinfo -v
jbig2 --version
jpegtran -version
```

最后做一页实际的 PDF 渲染和蒙版编码/解码小样。可执行文件存在不证明它有正确的 DLL/共享库、所需编码器或兼容的段布局。计划用 Pillow 写 CCITT G4 时，还应通过 `PIL.features.check('libtiff')` 和实际 G4 回读检查编码支持。

## 缺少依赖时的处理

- 缺 PyMuPDF：随附审计和比对脚本不能执行。准备该环境后再运行，不把未运行的比对写成通过。
- 缺 Pillow 或 `jbig2`：不执行区域编码。保留现有 G4/JBIG2/Flate 蒙版，其他独立优化仍可继续；没有编码器不意味着允许换成有损符号匹配。
- 缺 `jpegtran`：保留原 JPEG 码流，跳过相关优化；不要用 Pillow JPEG 重存当作无损替代。
- 缺 NumPy/OpenCV：可审计和比对已有文件；依赖它们的重新分层或修复等待依赖就绪，或选用已经验证的其他实现。
- 缺 qpdf 或 Poppler：明确标注未完成结构检查或独立渲染检查，不声称完成了完整交付验证。

历史测试环境不代表所有平台都已实测。新平台要记录操作系统、Python 和工具版本，以及样本结果；内存和并发按原生图像尺寸测量，不固定为某台电脑的配置。
