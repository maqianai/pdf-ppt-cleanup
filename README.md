# PDF / PPT Cleanup Agent Skill

PDF 转可编辑 PPT，尽量保真。直接清理 PDF 的独立二维码、水印与整页无关广告，验证保留内容，并生成离线 HTML 对照报告。

## 给 Agent 的入口

读取仓库根目录的 [SKILL.md](SKILL.md)，再按下面步骤准备运行环境。支持 Agent Skills 的客户端可将整个仓库安装到其技能目录中的 `pdf-ppt-cleanup/`。支持通用网页读取的 Agent 可以先读 SKILL.md，再下载整个仓库。

Agent 需要本地文件读写与脚本执行能力。Python 负责 PDF，Node.js 负责 PPT。PowerPoint 的实际编辑、保存重开与 PDF 导出需要目标应用环境。OCR 与图片修复使用 Agent 自身可用工具。

## 安装

Python 3.10+、Node.js 18+。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
```

Windows 使用 `.venv\Scripts\activate` 激活 Python 环境。字体需要安装在用于最终编辑和导出的机器上。

## 直接清理 PDF

```sh
python scripts/pdf_workflow.py inspect input.pdf output/inspection
```

Agent 查看全部页面图像与 `inspection.json`，判断品牌正文、第三方独立广告与整页引流广告。将确认的操作写入 plan.json。页码从 1 开始，xref 和 SHA256 来自当前输入的检查结果。

```json
{
  "source_sha256": "从 inspection.json 复制当前输入的 SHA256",
  "delete_pages": [8, 17],
  "annotations": [{"page": 7, "xrefs": [53, 54]}],
  "forms": [{"xref": 123, "sha256": "当前 Form 内容流 SHA256"}]
}
```

上面数字仅展示字段格式。每个输入重新检查，不按示例数字操作。

```sh
python scripts/pdf_workflow.py clean input.pdf output/clean --plan plan.json
```

输出 `clean.pdf`、`verification.json` 和自带页面对照图的 `report.html`。删除整页广告后，JSON 保留原页码到输出页码映射。保留数据检查需要结合视觉审阅与共享 Form 影响页判断。此命令覆盖独立 PDF 对象清理。图片中已经融合的水印需要另行修复，并记录局部损失。

## 生成可编辑 PPT

从已清理 PDF 或原 PDF 生成可编辑候选。先检查每个原字体标识对应的完整字体是否可用，再创建字体映射文件。

```json
{"Helvetica": "Arial"}
```

该示例是替代映射，应在交付报告披露。严格原字体还原需填写并验证对应原字体。

```sh
python scripts/pdf_workflow.py prepare-ppt output/clean/clean.pdf output/ppt-work --font-map fonts.json
node scripts/build_ppt.cjs output/ppt-work/ppt-manifest.json output/clean-editable.pptx
```

PPT 使用 SVG 背景和原生文本框。当前脚本按提取行建立对象，Agent 需要进一步合并语义段落、核对多字体混排、乱码、字距与行距。图像内文字需要 OCR、清除底图旧字并重建。PDF 页面中的曲线字可能留在 SVG 背景里。

字体映射缺项会停止构建。存在已映射但机器未安装的字体时，演示软件可能自动替代，因此需要实际应用验证。此脚本不执行字体嵌入。

在目标 PowerPoint 中编辑新字符、移动文本、保存重开并导出 PDF，再核对原版和输出。统一画布中的不同尺寸页面等比居中，可能产生留白。

## 可复现的公开测试

```sh
python tests/smoke.py
```

测试动态生成三页合成 PDF，验证对象清理、整页删除、输入保护、失败处理和 PPT 原生文字。测试素材由代码创建，未附带用户 PDF、字体源文件、截图或本机路径。

已执行的测试与局限见 [VALIDATION.md](VALIDATION.md)。本项目提供 Agent 工作流与基础脚本，广告语义识别、人工校对、图像修补和最终应用验收由执行 Agent 完成。

## 发布与版本

`main` 提供最新规则。需要可复现结果时使用固定提交或发布标签，并在处理报告记录所用版本。完整目录应与 SKILL.md 一起安装，保持相对路径。

## 许可

本仓库代码采用 MIT。PyMuPDF、PptxGenJS 等依赖各自遵循其许可，安装及分发时请核对依赖许可。
