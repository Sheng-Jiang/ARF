import base64
import os
import re

import requests


def main():
    md_path = "ARF_Investor_Whitepaper.md"
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found")
        return

    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    # Find the mermaid code block
    pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
    match = pattern.search(content)
    if not match:
        print("No mermaid code block found in Markdown")
        return

    mermaid_code = match.group(1).strip()
    print("Found mermaid code block for workflow.")

    # Try Kroki POST API
    img_data = None
    print("Attempting to render using Kroki...")
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "diagram_source": mermaid_code,
            "diagram_type": "mermaid",
            "output_format": "png"
        }
        resp = requests.post("https://kroki.io", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            img_data = resp.content
            print("Successfully rendered via Kroki.")
    except Exception as e:
        print(f"Kroki request failed: {e}")

    # Fallback to Mermaid.ink GET API
    if img_data is None:
        print("Attempting to render using Mermaid.ink...")
        try:
            b64_bytes = base64.b64encode(mermaid_code.encode("utf-8"))
            b64_str = b64_bytes.decode("utf-8")
            url = f"https://mermaid.ink/img/{b64_str}"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                img_data = resp.content
                print("Successfully rendered via Mermaid.ink.")
        except Exception as e:
            print(f"Mermaid.ink request failed: {e}")

    if img_data is None:
        print("Error: Failed to render diagram using both Kroki and Mermaid.ink.")
        return

    # Save the image
    os.makedirs("reports", exist_ok=True)
    img_path = os.path.join("reports", "workflow_diagram.png")
    with open(img_path, "wb") as f:
        f.write(img_data)
    print(f"Saved image to {img_path}")

    # Replace the mermaid block in the markdown with the image link
    replacement = "![ARF核心用户工作流与决策闭环图](reports/workflow_diagram.png)"
    new_content = content.replace(match.group(0), replacement)
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Updated {md_path} to reference the rendered image.")

if __name__ == "__main__":
    main()
