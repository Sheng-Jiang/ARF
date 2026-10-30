#!/usr/bin/env python3
"""Build publication-grade Chinese PDFs from markdown documents using Pandoc + Headless Chrome."""

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
    margin: 18mm 15mm 18mm 15mm;
    @bottom-center {{
        content: counter(page);
        font-size: 9pt;
        color: #64748b;
    }}
}}

body {{
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Heiti SC", "Songti SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    line-height: 1.65;
    color: #1e293b;
    background: #ffffff;
    padding: 0;
    margin: 0;
    font-size: 10pt;
    text-rendering: optimizeLegibility;
}}

h1, h2, h3, h4, h5, h6 {{
    color: #0f172a;
    font-weight: 700;
    line-height: 1.3;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}}

h1 {{
    font-size: 20pt;
    border-bottom: 2px solid #0288d1;
    padding-bottom: 8px;
    margin-top: 0;
}}

h2 {{
    font-size: 14pt;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 5px;
    color: #0369a1;
}}

h3 {{
    font-size: 11.5pt;
    color: #0f172a;
}}

p, li {{
    margin-top: 0.4em;
    margin-bottom: 0.5em;
    color: #334155;
}}

a {{
    color: #0288d1;
    text-decoration: none;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.2em 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
}}

th, td {{
    border: 1px solid #cbd5e1;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
}}

th {{
    background-color: #f1f5f9;
    color: #0f172a;
    font-weight: 600;
}}

tr:nth-child(even) td {{
    background-color: #f8fafc;
}}

blockquote {{
    border-left: 4px solid #0288d1;
    margin: 1.2em 0;
    padding: 10px 16px;
    background-color: #f0f9ff;
    color: #0369a1;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
}}

blockquote p {{
    margin: 0.3em 0;
    color: #0c4a6e;
}}

code {{
    font-family: "SF Mono", Menlo, Monaco, Consolas, monospace;
    font-size: 8.5pt;
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
    font-size: 8.5pt;
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 1em 0;
}}

pre code {{
    background: transparent;
    color: #f8fafc;
    padding: 0;
}}

pre.mermaid {{
    background: transparent !important;
    text-align: center;
    padding: 10px 0;
    margin: 1.5em 0;
    page-break-inside: avoid;
}}

.mermaid svg {{
    max-width: 100%;
    height: auto;
}}

hr {{
    border: 0;
    border-top: 1px solid #e2e8f0;
    margin: 1.8em 0;
}}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }}
}});
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
{body}
</body>
</html>
"""


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    print(f"\n>>> Processing: {md_path.name} -> {pdf_path.name}")
    if not md_path.exists():
        print(f"Error: {md_path} does not exist!")
        return

    # 1. Read Markdown content
    content = md_path.read_text(encoding="utf-8")

    # Extract title from first line if # Header
    title = md_path.stem
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # 2. Use pandoc to render body HTML (with mathjax)
    pandoc_cmd = ["pandoc", str(md_path), "-f", "markdown", "-t", "html", "--mathjax"]
    res = subprocess.run(pandoc_cmd, capture_output=True, text=True, check=True)
    body_html = res.stdout

    # In body_html, pandoc renders ```mermaid as <pre class="mermaid"><code>...</code></pre>
    # Mermaid.js expects <pre class="mermaid">...</pre> or <div class="mermaid">...</div> without <code> tags inside
    body_html = body_html.replace('<pre class="mermaid"><code>', '<pre class="mermaid">')
    body_html = body_html.replace('</code></pre>', '</pre>')

    # 3. Assemble full HTML
    full_html = HTML_TEMPLATE.format(title=title, body=body_html)
    tmp_html = md_path.with_suffix(".tmp.html")
    tmp_html.write_text(full_html, encoding="utf-8")

    # 4. Use Google Chrome Headless to print to PDF
    chrome_cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=8000",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        str(tmp_html.resolve())
    ]
    print(f"Running Chrome to generate {pdf_path.name}...")
    chrome_res = subprocess.run(chrome_cmd, capture_output=True, text=True)

    if tmp_html.exists():
        tmp_html.unlink()

    if pdf_path.exists():
        size_kb = pdf_path.stat().st_size / 1024
        print(f"SUCCESS: Generated {pdf_path} ({size_kb:.1f} KB)")
    else:
        print(f"ERROR: Failed to generate {pdf_path}")
        print("Chrome stderr:", chrome_res.stderr)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir = repo_root / "docs"

    files_to_convert = [
        (
            docs_dir / "AI_CIO_CONNECTING_THE_DOTS_FINANCIAL_MODELING_ZH.md",
            docs_dir / "AI_CIO_CONNECTING_THE_DOTS_FINANCIAL_MODELING_ZH.pdf",
        ),
        (
            docs_dir / "ARF_DIGITAL_INVESTMENT_ANALYST_VISION_ZH.md",
            docs_dir / "ARF_DIGITAL_INVESTMENT_ANALYST_VISION_ZH.pdf",
        ),
    ]

    for md_file, pdf_file in files_to_convert:
        convert_md_to_pdf(md_file, pdf_file)


if __name__ == "__main__":
    main()

