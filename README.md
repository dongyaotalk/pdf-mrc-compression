# pdf-mrc-compression

[English](README.en.md) · [Skill 入口](SKILL.md) · [版本下载](https://github.com/dongyaotalk/pdf-mrc-compression/releases)

当前版本：**[v0.3.0](https://github.com/dongyaotalk/pdf-mrc-compression/releases/tag/v0.3.0)** · [下载 ZIP](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/pdf-mrc-compression-0.3.0.zip) · [SHA256SUMS](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/SHA256SUMS)

**v0.3.0：扫描书籍工作流升级。** 新增显式 JSON 计划工具，处理页面尺寸、原生黑白编码与稀疏灰阶、书签/标签和成品清理。按任务选择验证，连续编辑可复用可靠的可见基线备份。
详情见 [整书工作流](references/book-workflow.md) 和 [变更记录](CHANGELOG.md)。

面向 Codex 的扫描 PDF 优化 skill，帮助在字形、插图颜色、体积和阅读速度之间作出有证据的选择。随附工具有明确支持边界；复杂彩色扫描仍需根据样本设计 MRC 分层，不是任意书籍的一键自动分割器。

## 能做什么

- 审计图像、蒙版、共享资源、页面几何、有效 DPI 和编码体积。
- 等比统一正常页面尺寸、修复明确的单扫描放置错误，不重采样原图。
- 在原生网格生成 G4/generic JBIG2，按明确预算保留稀疏灰阶，复杂页保留原样。
- 独立修改层级书签和页码标签；附属书签用“书名”“版权”，保留手工导航。
- 按范围清理成品目录，保留 PDF 和指定处理说明；备份需明确选择才删除。
- 修改已有 PDF 前，在输入文件旁保存可见、独立且经过校验的备份。
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

也可下载 [v0.3.0 ZIP](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/pdf-mrc-compression-0.3.0.zip)，核对同页的 [SHA256SUMS](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/SHA256SUMS)，将其中的 `pdf-mrc-compression` 文件夹放入上述目录。重新打开 Codex 后，在新对话中使用：

```text
使用 $pdf-mrc-compression 评估这份扫描 PDF，保留彩色插图，
先做代表性样本，再比较体积、画面和渲染速度。
```

## 更新已安装的 skill

- **通过 Git 安装：** 在实际的 skill 安装目录先运行 `git status --short`，确认没有
  未保存的本地修改后运行 `git pull --ff-only`。
- **通过 ZIP 安装：** 下载上方新版 ZIP 并核对 `SHA256SUMS`；保留自己修改过的内容，
  用新版的 `pdf-mrc-compression` 文件夹替换旧版。无需重新下载 Python 或原生依赖。
- 更新后重新打开 Codex，并在新对话中使用 skill。已有 PDF、历史备份和编码缓存不会自动搬动或删除。

## 使用提示词样例

安装 skill 后，将下面的提示词直接发送给 Codex。把文件名、输出目录和页码换成实际值，
并提供 Codex 能访问的输入文件。示例页码均指从 1 开始的 PDF 页码。
提示词中的质量要求用于指导本次处理，具体方案仍需根据文件审计和样本验证选择。

### 1. 先评估是否适合 MRC

```text
使用 $pdf-mrc-compression 审计 input.pdf，先不生成压缩版。
检查扫描图、原生文字/矢量、OCR、图像与蒙版编码、共享资源及主要体积来源。
判断哪些页适合 MRC，哪些页应保留原样，并给出代表性测试页和压缩建议。
将审计报告保存到 output/audit.json。
```

### 2. 首次压缩，以字形和插图质量为先

```text
使用 $pdf-mrc-compression 压缩扫描版 input.pdf，输出到 output/input-mrc.pdf。
优先保留小字、数学公式、上下标和细线，保持彩色插图、灰色题字及封面的原色。
先检查小字、密集公式、插图、灰条和封面的代表性样本，样本满足要求后继续整本处理。
保留原始文件及现有 OCR、书签和链接；不要使用有损字形替换。
交付时报告压缩前后大小、画面变化、验证范围和同设置下的渲染耗时。
```

### 3. 对已有 MRC 文件继续做严格无损优化

```text
使用 $pdf-mrc-compression 优化 current-mrc.pdf，输出到 output/compact.pdf。
以 current-mrc.pdf 为像素一致性的基准，仅尝试已验证无损的编码、结构整理和资源复用。
保持原有页面几何、文字、书签、链接和颜色，不重新二值化、降采样或统一底纹。
验证改动图像及蒙版的原生解码像素，并逐页比较同 DPI 渲染；另做结构检查和独立渲染抽查。
报告节省的字节数、渲染速度和验证局限；如果没有安全收益，保留基准文件。
```

### 4. 修复指定页的粘连、漏抠和黑块

```text
使用 $pdf-mrc-compression 对照 original.pdf 修复 compressed.pdf，输出到 output/repaired.pdf。
第 11 页图注的小字有笔画粘连，第 18 页彩色插图的浅色部分漏抠并出现黑块。
只调整这些问题区域，保护负号、小数点、上下标、图中细线和原有颜色。
检查旧文字层是否重复叠印，并验证修复区域外的内容保持一致。
提供问题区域的修复前后对比和验证结果。
```

### 5. 经允许统一灰条底纹，减少重复数据

```text
使用 $pdf-mrc-compression 优化 input-mrc.pdf 中的灰条标题，输出到 output/shared-texture.pdf。
我允许将各页灰条的扫描底纹替换为视觉接近的共享纹理，标题仍保留各页原扫描字形和灰阶边缘。
先验证代表性灰条，检查漏字、重复叠印、接缝及颜色变化，再处理其余页面。
报告资源复用节省的体积，标明底纹替换属于视觉近似，并验证灰条区域外的内容。
```

### 6. 文件已经很小，但翻页慢

```text
使用 $pdf-mrc-compression 排查 small-but-slow.pdf 的渲染性能。
检查高分辨率蒙版、冗余透明层、重复绘制和巨幅图像，测量代表性页面的解码成本。
优先保持画面，比较适用的 G4、generic JBIG2、常量前景与资源复用方案。
如体积与速度存在取舍，分别输出快读版和紧凑版，并在相同设置下比较大小和渲染耗时。
说明离线渲染测试的范围，不将其直接当作阅读器实际翻页速度。
```

### 7. 拆分书衣并替换高清封面

```text
使用 $pdf-mrc-compression 处理 book.pdf 的书衣，高清封面使用 cover.jpg。
先确认扫描图中封面、前内封、后内封和封底的实际边界，不按四等分猜测。
按封面、前内封、正文、后内封、封底排列，四封页面框与正文一致，图片等比缩放并留白完整显示。
前内封靠左、后内封靠右；除替换封面外，尽量复用同一个原扫描图像对象。
输出到 output/book-covers.pdf，更新受插页影响的书签和链接，并验证正文内容未变。
```

### 8. 整套书沿用前册策略

```text
使用 $pdf-mrc-compression 优化这套扫描书。第 1–3 册已有压缩版，请提取已用策略，对第 4–7 册做相同处理。
先审计正常正文尺寸、异常旋转、灰阶/颜色与共享资源。按实际页面判断是否适合原生黑白编码，保护连续灰阶和插图。
压缩后补齐原书目录层级及封面、书名、版权、分部扉页、封底；没有实际版权内容的册不加版权书签。
页码标签根据每册实际正文与印刷起号设置；先给出映射方案，再按确认方案执行。
处理说明只记录做了哪些处理，不包含目录位置、机器路径或完整书目目录。
```

### 9. 只改标签，保留手工书签

```text
使用 $pdf-mrc-compression 只修改 ready.pdf 的页面标签，保留我已手动调整的所有书签。
物理第 1–3 页用 A、B、C，第 4–19 页用大写罗马数字 I–XVI，第 20 页开始用阿拉伯数字 1 起，后附页与封底继续数字。
页面顺序已经确认，不用额外校验，直接修改并记录未验证；不要重新压缩正文或跑全书渲染。
```

### 10. 清理交付目录

```text
使用 $pdf-mrc-compression 清理指定的这本书目录：保留所有成品 PDF 和处理说明，删除其余本任务文件。
处理说明只保留实际完成的处理，不包含目录位置、缓存、日志或完整章节目录。
我也授权删除这次任务的备份及恢复包，不要另建隐藏副本，不处理其他书籍目录。
```

## 运行依赖和脚本

需要修改已有 PDF（例如书签或页码标签）时，备份放在**输入文件同级的可见
`pdf-mrc-backups/` 目录**，不放进隐藏工作目录或 skill 安装目录。
`backup_pdf.py` 保留文件名，为每次调用建立独立的阶段目录，回读校验大小和 SHA-256，
并输出实际路径和 `backup.json` 恢复记录。备份失败时停止后续修改，不回退到其他位置。
原件不变、另存新成品时无需额外复制整本原件。
详见 [备份与工作文件位置](references/backups-and-work-files.md)；历史备份不会自动搬动或删除。

使用 Python 3.10 或更高版本；发布检查覆盖的组合见 [CI](.github/workflows/ci.yml)。
Python 包和外部程序均需另行安装，完整的 Windows、Linux、macOS 说明见
[环境与依赖](references/environment-and-dependencies.md)。

在仓库或安装后的 skill 目录中执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/audit_pdf.py input.pdf --output audit.json
.venv/bin/python scripts/backup_pdf.py input.pdf --stage before-bookmarks
.venv/bin/python scripts/verify_lossless.py before.pdf after.pdf --dpi 96 --native-images --report verify.json
.venv/bin/python scripts/encode_jbig2_region.py black-on-white.png mask.jb2
```

Windows 使用 `py -3 -m venv .venv`，将 `.venv/bin/python` 换成 `.\.venv\Scripts\python.exe`。
路径有空格时加引号。所有 CLI 均提供 `--help`。

| 工具 | 用途与依赖 |
|---|---|
| `audit_pdf.py` | 只读 JSON 审计；需要 PyMuPDF |
| `backup_pdf.py` | 在输入文件旁保存独立备份及恢复记录；仅需 Python 标准库 |
| `verify_lossless.py` | 相同返回 `0`，不一致或失败返回 `1`，参数错误返回 `2`；需要 PyMuPDF |
| `encode_jbig2_region.py` | 二值图 → 可嵌入 PDF 的 `.jb2` 码流；需要 Pillow 和 `jbig2enc` 的 `jbig2` |
| `normalize_pages.py` | 显式几何计划，原图不重采样；需要 PyMuPDF |
| `compress_scans.py` | 显式页选择、G4/generic JBIG2 与有限灰阶保护；需要 PyMuPDF、Pillow；JBIG2 另需 jbig2enc |
| `set_navigation.py` | 独立书签/标签计划，不重编码扫描；需要 PyMuPDF |
| `cleanup_outputs.py` | 有界清理，默认预览，`--apply` 才删除；仅需标准库 |
| `qpdf`、Poppler | PDF 结构检查和独立渲染验证；不由上述脚本自动执行 |

新工具的计划例子、命令和支持边界见 [页面几何](references/page-geometry.md)、[原生扫描编码](references/segmentation-and-repairs.md)、[导航与标签](references/navigation-and-labels.md) 和 [清理](references/backups-and-work-files.md)。计划中的页码均为从 1 开始的物理页。

```bash
python scripts/normalize_pages.py input.pdf sized.pdf --plan geometry.json
python scripts/compress_scans.py sized.pdf compact.pdf --plan compression.json --cache work/encoding
python scripts/set_navigation.py compact.pdf ready.pdf --plan navigation.json
python scripts/cleanup_outputs.py books --plan cleanup.json
```

压缩工具默认核对实际嵌入对象的原生目标像素，不自动完成结构与全部画面检查。仅元数据任务不要求全书图像校验；明确跳过校验会如实记录。连续编辑可加同一 `--session work/session.json`，备份仍在 PDF 同级可见目录。

`mask.jb2` 不是 PDF 或独立 JBIG2 图像文件。嵌入 PDF 后还要验证极性、原生像素及实际渲染。
`--native-images` 要求页面资源名稳定且无歧义，不适合任意重建了资源树的 PDF。
指定 `--pages` 只验证所选页面；单一 DPI、单一渲染器相同不能证明所有 PDF 特征等价。

## 文档

- [工作流程与质量边界](SKILL.md)
- [整套书籍工作流](references/book-workflow.md)
- [页面几何](references/page-geometry.md)
- [导航与标签](references/navigation-and-labels.md)
- [依赖与跨平台运行](references/environment-and-dependencies.md)
- [备份与工作文件位置](references/backups-and-work-files.md)
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
