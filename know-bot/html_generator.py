"""
Know_Bot HTML Generator — Converts saved content to dark-theme HTML.
"""
import os
import re
from datetime import datetime
from html import escape


def generate_article_html(article_id, title, source_url, source_domain, content_text, summary="", content_is_html=False):
    """Generate a dark-theme HTML file for a saved article."""

    if content_is_html:
        # Content is already HTML — embed directly
        content_html = content_text
        # Ensure links open in new tabs (avoid double-target)
        content_html = content_html.replace('target="_blank"', '')
        content_html = content_html.replace('<a ', '<a target="_blank" ')
    else:
        # Convert plain text to HTML
        content_html = text_to_html(content_text)

    # Build summary HTML block (only if summary exists)
    safe_summary = escape(summary) if summary else ""
    summary_html = f'<div class="summary-box"><div class="label">📌 摘要</div><div class="text">{safe_summary}</div></div>' if summary else ""

    # Tags are empty for now (future feature)
    tags_html = ""

    # Read template
    template_path = os.path.join(os.path.dirname(__file__), "templates", "article.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Escape values
    safe_title = escape(title) if title else "(無標題)"
    safe_date = escape(datetime.now().strftime("%Y-%m-%d %H:%M"))
    safe_id = escape(article_id)
    safe_domain = escape(source_domain) if source_domain else ""

    # Replace placeholders
    html = template
    html = html.replace("{{ title }}", safe_title)
    html = html.replace("{{ id }}", safe_id)
    html = html.replace("{{ date }}", safe_date)
    html = html.replace("{{ source_domain }}", safe_domain)
    html = html.replace("{{ tags_html }}", tags_html)
    html = html.replace("{{ summary_html }}", summary_html)
    html = html.replace("{{ content_html }}", content_html)

    return html


def text_to_html(text):
    """Convert plain text with markdown features to HTML."""
    if not text:
        return "<p><em>無內容</em></p>"

    text = escape(text)
    lines = text.split("\n")
    html_parts = []
    in_code_block = False
    code_buffer = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block
        if line.startswith("```"):
            if in_code_block:
                code_text = "\n".join(code_buffer)
                html_parts.append(f"<pre><code>{escape(code_text)}</code></pre>")
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Headings
        if stripped.startswith("#### "):
            html_parts.append(f"<h4>{line[5:]}</h4>")
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif stripped.startswith("# "):
            html_parts.append(f"<h2>{line[2:]}</h2>")
        elif stripped in ("---", "***", "___"):
            html_parts.append("<hr>")
        elif stripped.startswith("> "):
            html_parts.append(f"<blockquote>{stripped[2:]}</blockquote>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            html_parts.append(f"<li>{stripped[2:]}</li>")
        elif re.match(r"^\d+[\.\)] ", stripped):
            inner = re.sub(r"^\d+[\.\)] ", "", stripped)
            html_parts.append(f"<li>{inner}</li>")
        elif stripped == "":
            html_parts.append("")
        else:
            formatted = line
            # **bold** -> <strong>
            formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", formatted)
            # *italic* -> <em>
            formatted = re.sub(r"\*(.+?)\*", r"<em>\1</em>", formatted)
            # `code` -> <code>
            formatted = re.sub(r"`(.+?)`", r"<code>\1</code>", formatted)
            # Inline URLs
            formatted = re.sub(
                r"(https?://[^\s]+)",
                r'<a href="\1" target="_blank">\1</a>',
                formatted
            )
            html_parts.append(f"<p>{formatted}</p>")

        i += 1

    # Handle unclosed code block
    if in_code_block and code_buffer:
        code_text = "\n".join(code_buffer)
        html_parts.append(f"<pre><code>{escape(code_text)}</code></pre>")

    # Wrap consecutive <li> in <ul>
    result = []
    in_list = False
    for part in html_parts:
        if part.startswith("<li>"):
            if not in_list:
                result.append("<ul>")
                in_list = True
            result.append(part)
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append(part)
    if in_list:
        result.append("</ul>")

    return "\n".join(result)


def save_html(article_id, title, source_url, source_domain, content_text, summary="", content_is_html=False):
    """Generate and save HTML file. Returns file path."""
    html = generate_article_html(
        article_id, title, source_url, source_domain, content_text, summary, content_is_html
    )

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    file_path = os.path.join(data_dir, f"{article_id}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

    return file_path


def verify_formatting(content: str, content_is_html: bool = False) -> dict:
    """Check if the content has proper visual formatting/structure.
    
    Returns: {
        "passed": bool,
        "score": float,        # 0.0 (no structure) to 1.0 (rich structure)
        "issues": [str],       # descriptions of what's missing
        "structural_tags": {tag: count}
    }
    """
    issues = []
    
    if not content or not content.strip():
        return {"passed": False, "score": 0.0, "issues": ["內容為空"], "structural_tags": {}}

    if content_is_html:
        # Count structural HTML tags
        tags = {}
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "pre", "code", "blockquote", "table", "img", "hr"]:
            count = len(re.findall(f'<{tag}[\\s>]', content, re.IGNORECASE))
            if count > 0:
                tags[tag] = count
        
        text_length = len(re.sub(r'<[^>]+>', '', content))
        
        # Quality checks
        if "h2" not in tags and "h3" not in tags and "h4" not in tags:
            issues.append("沒有任何標題標籤 (h2/h3/h4)")
        if "p" not in tags:
            issues.append("沒有任何段落標籤 (p)")
        if "li" not in tags and text_length > 2000:
            issues.append("長內容但沒有任何列表 (li)")
        if text_length > 0 and len(tags) == 0:
            issues.append("內容是純 HTML 但沒有任何結構化標籤")
        
        # Calculate score
        total_tags = sum(tags.values())
        if total_tags == 0:
            score = 0.1
        else:
            # More structural tags per 1000 chars = better formatting
            tag_density = total_tags / max(text_length / 1000, 1)
            # Bonus for diverse tag types
            diversity_bonus = min(len(tags) / 5, 1.0)
            
            raw_score = min(tag_density * 0.15 + diversity_bonus * 0.4, 1.0)
            # Penalty for missing headings
            if "h2" not in tags and "h3" not in tags and "h4" not in tags:
                raw_score *= 0.5
            score = round(max(raw_score, 0.05), 2)
    else:
        # Plain text verification
        lines = content.split("\n")
        total_lines = len(lines)
        # Check for markdown-like structure
        headings = sum(1 for l in lines if re.match(r'^#{1,6}\s', l))
        lists = sum(1 for l in lines if re.match(r'^[\s]*[-*]\s', l) or re.match(r'^\d+[\.\)]\s', l))
        
        text_length = len(content)
        
        if headings == 0 and text_length > 500:
            issues.append("純文字內容超過 500 字但沒有標題 (無 # 前綴)")
        if lists == 0 and text_length > 2000:
            issues.append("長內容但沒有任何列表格式")
        
        # Score plain text
        if headings > 0 or lists > 0:
            raw_score = min(0.3 + (headings * 0.15) + (lists * 0.05), 0.7)
            score = round(raw_score, 2)
        else:
            score = 0.1
        tags = {"headers": headings, "lists": lists}

    passed = len(issues) == 0 and score >= 0.3
    
    return {
        "passed": passed,
        "score": score,
        "issues": issues,
        "structural_tags": tags,
    }