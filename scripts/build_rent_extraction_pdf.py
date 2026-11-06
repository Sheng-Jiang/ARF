#!/usr/bin/env python3
"""Build publication-grade comparative research PDF:
'China vs US Asset Management - Rent Extraction and Moral Hazard.pdf'
using Pandoc + Headless Google Chrome.
"""

import shutil
import subprocess
from pathlib import Path

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
@page {{
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
    @bottom-center {{
        content: counter(page);
        font-size: 8.5pt;
        color: #64748b;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
}}

body {{
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Heiti SC", "Songti SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    line-height: 1.68;
    color: #1e293b;
    background: #ffffff;
    padding: 0;
    margin: 0;
    font-size: 9.8pt;
    text-rendering: optimizeLegibility;
}}

.report-header {{
    border-bottom: 2px solid #0f766e;
    padding-bottom: 14px;
    margin-bottom: 24px;
}}

.report-meta-bar {{
    display: flex;
    justify-content: space-between;
    font-size: 8.5pt;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}}

.report-tag {{
    background-color: #0f766e;
    color: #ffffff;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 7.5pt;
    font-weight: 700;
}}

h1, h2, h3, h4, h5, h6 {{
    color: #0f172a;
    font-weight: 700;
    line-height: 1.35;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}}

h1 {{
    font-size: 18.5pt;
    color: #0f172a;
    margin-top: 6px;
    margin-bottom: 12px;
}}

h2 {{
    font-size: 13.5pt;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 5px;
    color: #0f766e;
    margin-top: 1.6em;
}}

h3 {{
    font-size: 11pt;
    color: #1e293b;
    margin-top: 1.2em;
}}

p, li {{
    margin-top: 0.4em;
    margin-bottom: 0.5em;
    color: #334155;
    text-align: justify;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.4em 0;
    font-size: 8.2pt;
    page-break-inside: avoid;
}}

th, td {{
    border: 1px solid #cbd5e1;
    padding: 6px 9px;
    text-align: left;
    vertical-align: middle;
}}

th {{
    background-color: #f1f5f9;
    color: #0f172a;
    font-weight: 700;
}}

tr:nth-child(even) td {{
    background-color: #f8fafc;
}}

blockquote {{
    border-left: 4px solid #0f766e;
    margin: 1.2em 0;
    padding: 10px 16px;
    background-color: #f0fdf4;
    color: #166534;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
}}

blockquote p {{
    margin: 0.3em 0;
    color: #14532d;
}}

code {{
    font-family: "SF Mono", Menlo, Monaco, Consolas, monospace;
    font-size: 8.2pt;
    background-color: #f1f5f9;
    padding: 2px 5px;
    border-radius: 4px;
    color: #0f172a;
}}

pre {{
    background-color: #0f172a;
    color: #f8fafc;
    padding: 12px 14px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 8pt;
    line-height: 1.42;
    page-break-inside: avoid;
    margin: 1.2em 0;
    font-family: "SF Mono", Menlo, Monaco, Consolas, monospace;
}}

pre code {{
    background: transparent;
    color: #f8fafc;
    padding: 0;
}}

hr {{
    border: 0;
    border-top: 1px solid #e2e8f0;
    margin: 1.8em 0;
}}

.math {{
    font-size: 105%;
}}

.math.display {{
    margin: 1em 0;
    text-align: center;
}}
</style>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  }},
  svg: {{
    fontCache: 'global'
  }}
}};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
</head>
<body>

<div class="report-header">
    <div class="report-meta-bar">
        <span>ARF Global Asset Management Comparative Series &bull; Macro & Micro Institutions</span>
        <span class="report-tag">Institutional Research</span>
    </div>
</div>

{body}

</body>
</html>
"""


def main():
    repo_root = Path(__file__).resolve().parents[1]
    artifact_md = Path(
        "/Users/sheng/.gemini/antigravity/brain/233e5019-cf3b-492b-b259-a7608c15347c/china_us_rent_extraction_and_moral_hazard.md"
    )
    ref_dir = repo_root / "Reference"

    target_md = ref_dir / "China vs US Asset Management - Rent Extraction and Moral Hazard.md"
    target_pdf = ref_dir / "China vs US Asset Management - Rent Extraction and Moral Hazard.pdf"

    print(f"1. Copying Markdown to Reference: {target_md.name}")
    shutil.copy2(artifact_md, target_md)

    print("2. Converting Markdown to HTML via Pandoc...")
    pandoc_cmd = ["pandoc", str(target_md), "-f", "markdown", "-t", "html", "--mathjax"]
    res = subprocess.run(pandoc_cmd, capture_output=True, text=True, check=True)
    body_html = res.stdout

    title = "资本中介的租金挤占与道德风险异化：中美资管与股票市场的微观制度经济学实证对比"
    full_html = HTML_TEMPLATE.format(title=title, body=body_html)

    tmp_html = ref_dir / "china_us_rent_extraction_temp.html"
    tmp_html.write_text(full_html, encoding="utf-8")

    print(f"3. Printing PDF via Headless Chrome to {target_pdf.name}...")
    chrome_cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=9000",
        "--no-pdf-header-footer",
        f"--print-to-pdf={target_pdf}",
        str(tmp_html.resolve()),
    ]
    chrome_res = subprocess.run(chrome_cmd, capture_output=True, text=True)

    if tmp_html.exists():
        tmp_html.unlink()

    if target_pdf.exists():
        size_kb = target_pdf.stat().st_size / 1024
        print(f"SUCCESS: Generated {target_pdf} ({size_kb:.1f} KB)")
    else:
        print("ERROR: Chrome generation failed!")
        print("STDOUT:", chrome_res.stdout)
        print("STDERR:", chrome_res.stderr)


if __name__ == "__main__":
    main()

