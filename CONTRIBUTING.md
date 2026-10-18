# 开发与发布

仓库根目录就是可安装的 skill。修改 `SKILL.md` 时保持质量边界明确，将较长的
条件性操作说明放在 `references/`。`agents/openai.yaml` 提供界面元数据。
不要求修改用户已经安装的其他副本。

## 本地检查

使用 Python 3.10+ 创建虚拟环境，然后执行：

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_skill.py
python -m unittest discover -s tests -v
python tools/build_release.py
```

`validate_skill.py` 检查 skill frontmatter、界面元数据、本地文档链接与版本。
若安装了 Codex 的 `skill-creator`，还可运行其 `quick_validate.py`。
`unittest` 覆盖共享图像计数、画面或原生像素改变、页面几何、导航与交互信息、
输出保护、编码器输入边界和发布包内容。所有样本都由测试生成，不提交书籍扫描。

安装 `jbig2enc`、`qpdf`、Poppler 后，设置 `MRC_REQUIRE_NATIVE=1` 再运行同一套测试，
可将缺少原生工具的情况视为失败。Linux CI 使用此模式，实际编码黑白、空白、
稀疏及噪声图，比较原生解码像素，执行 qpdf 和 Poppler 验证。
测试日志中的 skips 表示未执行，不能作为通过的编码或渲染验证。

本地运行依赖的最低声明是 PyMuPDF 1.24.3 和 Pillow 10；它们不是每个操作系统
均已测试的版本组合。CI 通过包解析选择可安装版本，输出实际 Python 和包版本。
最低依赖组合另在 Linux/Python 3.10 测试。

## 提交内容

- 更新行为时补充能捕捉实际失败的测试，更新受影响的说明。
- 不提交 PDF、`.mrc-work/`、`output/`、虚拟环境、报告、密钥或个人路径。
- 报告缺陷时提供操作系统、Python/依赖版本、命令、预期与实际结果。
- 可公开的最小合成样本优于整本书；有权共享的私有样本也不要直接提交到公开 issue。
- 提交的自有代码和文档按本仓库 MIT 许可证提供；第三方内容须保留许可信息。

## 发布

1. 修改 `VERSION` 与 `CHANGELOG.md`，完成上述检查。
2. 合并到 `main`，等待 [CI](https://github.com/dongyaotalk/pdf-mrc-compression/actions/workflows/ci.yml) 全部通过。
3. 运行 `python tools/build_release.py`，检查 `dist/` 中 ZIP 与 `SHA256SUMS`。
4. 为已经通过 CI 的提交创建并推送对应 tag，然后用 `gh` 发布：

```bash
git tag -a v0.1.0 -m 'Release v0.1.0'
git push origin v0.1.0
gh release create v0.1.0 dist/pdf-mrc-compression-0.1.0.zip dist/SHA256SUMS \
  --verify-tag --title 'v0.1.0' --notes-file /path/to/release-notes.md
```

将示例版本与 release notes 路径替换为本次实际值。GitHub 发布由维护者显式执行；
CI 只验证和构建，不自动创建 release。打包程序采用文件白名单和固定 ZIP 元数据，
不会递归打包工作目录。相同源码在同一 Python/zlib 版本下重复构建应产生相同哈希。
ZIP 只包含 skill、辅助脚本、参考资料及用户文档，不包含依赖二进制或测试产物。
