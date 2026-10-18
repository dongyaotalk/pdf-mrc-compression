# pdf-mrc-compression

[English](README.en.md) · [Skill 入口](SKILL.md) · [版本下载](https://github.com/dongyaotalk/pdf-mrc-compression/releases)

面向 Codex 的扫描 PDF MRC 压缩 skill，包含分层策略、画面修复经验，以及可单独运行的审计、像素比对和 JBIG2 区域编码脚本。

它帮助在文件体积、字形、插图颜色和阅读速度之间作出可验证的选择。**随附脚本不是整本一键 MRC 分割器**；自动分层实现需要根据实际书页编排。

## 能做什么

- 审计图像、蒙版、共享资源、页面几何、有效 DPI 和编码体积。
- 指导扫描页的 MRC 分层，处理文字粘连、插图漏抠、灰条和灰色题字。
- 对已有 MRC 文件尝试结构、编码及资源复用优化，并比较渲染速度。
- 比对页面渲染、原生图像与蒙版，检查文字、书签、链接和部分交互信息。
- 在保留全画布尺寸及像素偏移的前提下，编码无字形替换的 generic JBIG2 区域。

初次分层、二值化、降采样或统一纸底会改变像素。严格无损只能相对明确的基准和已经验证的操作来描述。原生矢量/文本 PDF 不应为使用此 skill 而整本栅格化。

## 安装到 Codex

将本仓库克隆到 Codex 的个人 skills 目录，文件夹名保留 `pdf-mrc-compression`。
默认位置是 `~/.codex/skills`；设置了 `CODEX_HOME` 时使用其下的 `skills` 目录。
若目标目录已经存在，先检查已有内容，避免覆盖本地修改。

Linux / macOS：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/dongyaotalk/pdf-mrc-compression.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/pdf-mrc-compression"
```

Windows PowerShell：

```powershell
$skillBase = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$skillDir = Join-Path $skillBase 'skills'
New-Item -ItemType Directory -Force $skillDir | Out-Null
git clone https://github.com/dongyaotalk/pdf-mrc-compression.git (Join-Path $skillDir 'pdf-mrc-compression')
```

也可从 [Releases](https://github.com/dongyaotalk/pdf-mrc-compression/releases) 下载 ZIP，核对同页的 `SHA256SUMS`，将其中的 `pdf-mrc-compression` 文件夹放入上述目录。重新打开 Codex 后，在新对话中使用：

```text
使用 $pdf-mrc-compression 评估这份扫描 PDF，保留彩色插图，
先做代表性样本，再比较体积、画面和渲染速度。
```

## 运行依赖和脚本

使用 Python 3.10 或更高版本；发布检查覆盖的组合见 [CI](.github/workflows/ci.yml)。
Python 包和外部程序均需另行安装，完整的 Windows、Linux、macOS 说明见
[环境与依赖](references/environment-and-dependencies.md)。

在仓库或安装后的 skill 目录中执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/audit_pdf.py input.pdf --output audit.json
.venv/bin/python scripts/verify_lossless.py before.pdf after.pdf --dpi 96 --native-images --report verify.json
.venv/bin/python scripts/encode_jbig2_region.py black-on-white.png mask.jb2
```

Windows 使用 `py -3 -m venv .venv`，将 `.venv/bin/python` 换成 `.\.venv\Scripts\python.exe`。
路径有空格时加引号。三个脚本均提供 `--help`。

| 工具 | 用途与依赖 |
|---|---|
| `audit_pdf.py` | 只读 JSON 审计；需要 PyMuPDF |
| `verify_lossless.py` | 相同返回 `0`，不一致或失败返回 `1`，参数错误返回 `2`；需要 PyMuPDF |
| `encode_jbig2_region.py` | 二值图 → 可嵌入 PDF 的 `.jb2` 码流；需要 Pillow 和 `jbig2enc` 的 `jbig2` |
| `qpdf`、Poppler | PDF 结构检查和独立渲染验证；不由上述脚本自动执行 |

`mask.jb2` 不是 PDF 或独立 JBIG2 图像文件。嵌入 PDF 后还要验证极性、原生像素及实际渲染。
`--native-images` 要求页面资源名稳定且无歧义，不适合任意重建了资源树的 PDF。
指定 `--pages` 只验证所选页面；单一 DPI、单一渲染器相同不能证明所有 PDF 特征等价。

## 文档

- [工作流程与质量边界](SKILL.md)
- [依赖与跨平台运行](references/environment-and-dependencies.md)
- [分层和画面修复](references/segmentation-and-repairs.md)
- [无损优化和渲染速度](references/lossless-and-speed.md)
- [封面与页面几何](references/covers.md)
- [历史测量案例](references/case-study.md)：个案数据，不是压缩率保证；不附书籍文件。
- [开发、测试和发布](CONTRIBUTING.md) · [变更记录](CHANGELOG.md)

## 开发验证

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_skill.py
python -m unittest discover -s tests -v
python tools/build_release.py
```

测试使用临时生成的合成 PDF 和图像，不需要真实书籍。安装 `jbig2`、`qpdf` 和
`pdftoppm` 后，额外运行原生编码与独立渲染测试；缺少工具时会明确跳过。
CI 的 Linux 集成任务要求这些工具齐全。

## 许可证

项目自有代码和文档采用 [MIT](LICENSE)。依赖保留各自许可证，详见 [NOTICE.md](NOTICE.md)。
