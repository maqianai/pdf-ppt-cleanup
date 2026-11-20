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
  "delete_pages": [2],
  "annotations": [{"page": 1, "xrefs": [42, 43]}],
  "forms": [],
  "text_removals": [{
    "pages": [1],
    "text": "Members only",
    "expected_rectangles_per_page": 1,
    "clip": [0, 350, 720, 405]
  }]
}
```

上面数字仅展示字段格式。每个输入重新检查，不按示例数字操作。

```sh
python scripts/pdf_workflow.py clean input.pdf output/clean --plan plan.json
```

输出 `clean.pdf`、`verification.json` 和自带页面对照图的 `report.html`。

### v1.1.0 普通文字水印

`inspect` 会在 `text_candidates` 列出会员推广、严禁外传、扫码获取等原生文字候选，包含文字与坐标。确认后使用 `text_removals` 删除普通文字。页码始终使用输入页码，整页删除前执行文字清理。

`expected_rectangles_per_page` 是当前输入中搜索到的矩形数量，跨行或多字体现为多个矩形时按检查结果填写。尾部连字符按原字匹配。相同文案也用于正常正文时，使用 `clip` 限制区域。图片与矢量图形保持，源文件保持。

保存后重新扫描。若 `residual_text_candidates` 非空，退出码为 **2**，HTML 顶部显示 **NEEDS REVIEW**。这时按候选复核，更新计划并使用新的空输出目录运行。此状态的 PDF 供中间复核，不能直接视为清理完成。关键词仅用于候选提示，不直接自动删除。

返回 0 的 `text_scan_clear` 表示原生文本候选已清空，仍需检查图片内文案和全页画面。
删除整页广告后，JSON 保留原页码到输出页码映射。保留数据检查需要结合视觉审阅与共享 Form 影响页判断。此命令覆盖独立 PDF 对象清理。图片中已经融合的水印需要另行修复，并记录局部损失。

## 生成可编辑 PPT

v1.2.0 的 `prepare-ppt` 会自动核对内置字体候选，发现字形与字宽一致的完整字体时覆盖旧的替代映射，并输出 `font-audit.json`。也可用其他合法字体库：先读 [字体指南](references/fonts.md)，运行 `scripts/match_fonts.py` 生成经核对的映射。内置附 OFL 许可的 BIZ UDPMincho 完整字体。匹配脚本会拒绝明确的明朝体→黑体风格冲突；匹配失败和替代均写入报告。

从已清理 PDF 生成可编辑候选。v1.3.0 默认阻止含营销文字候选的输入继续转换，输出 `cleanup-review.json`。分发方“会员私享／独家发布／严禁外传”页脚属于本清理场景的删除目标，不能仅因位于版权区而保留。用户明确需要保留原内容的 PPT 时，才加 `--allow-promotional-text`，该版本不能作为清理后交付。先检查每个原字体标识对应的完整字体是否可用，再创建字体映射文件。

```json
{"Helvetica": "Arial"}
```

该示例是替代映射，应在交付报告披露。严格原字体还原需填写并验证对应原字体。

```sh
python scripts/pdf_workflow.py prepare-ppt output/clean/clean.pdf output/ppt-work --font-map fonts.json
node scripts/build_ppt.cjs output/ppt-work/ppt-manifest.json output/clean-editable.pptx
```

PPT 使用 SVG 背景和原生段落文本框。v1.3.0 将连续正文行合并为一个文本框，并在段内保留字体、粗斜体与颜色。原换行是软换行，当前关闭自动折行以防替代字体导致二次换行；长段增字仍需调整框宽或启用自动换行并复核。复杂列布局和段落边界需继续检查。图像内文字需要 OCR、清除底图旧字并重建。PDF 页面中的曲线字可能留在 SVG 背景里。

字体映射缺项会停止构建。存在已映射但机器未安装的字体时，演示软件可能自动替代，因此需要实际应用验证。此脚本不执行字体嵌入。

在目标 PowerPoint 中编辑新字符、移动文本、保存重开并导出 PDF，再核对原版和输出。统一画布中的不同尺寸页面等比居中，可能产生留白。

## 可复现的公开测试

```sh
python tests/smoke.py
python tests/text_cleanup.py
python tests/font_matching.py
python tests/paragraph_cleanup.py
```

测试动态生成三页合成 PDF，验证对象清理、整页删除、输入保护、失败处理和 PPT 原生文字。测试素材由代码创建，未附带用户 PDF、字体源文件、截图或本机路径。

已执行的测试与局限见 [VALIDATION.md](VALIDATION.md)。本项目提供 Agent 工作流与基础脚本，广告语义识别、人工校对、图像修补和最终应用验收由执行 Agent 完成。

## 发布与版本

`main` 提供最新规则。需要可复现结果时使用固定提交或发布标签，并在处理报告记录所用版本。完整目录应与 SKILL.md 一起安装，保持相对路径。

## 许可

本仓库代码采用 MIT。PyMuPDF、PptxGenJS 等依赖各自遵循其许可，安装及分发时请核对依赖许可。
