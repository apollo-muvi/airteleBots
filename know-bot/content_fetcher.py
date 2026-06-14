"""
Know_Bot Content Fetcher — Fetches content from shared URLs using Playwright.
"""
import re
import urllib.parse
import hashlib
from datetime import datetime
from html import escape
from config import MAX_CONTENT_CHARS


def extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def is_url(text: str) -> bool:
    """Check if text contains a URL (possibly with other content before it,
    like Telegram share format: 'Title\\nhttps://...')."""
    text = text.strip()
    if re.match(r"^https?://\S+$", text):
        return True
    # Check if a URL exists anywhere in the text
    return bool(re.search(r"https?://\S+", text))


def extract_url(text: str) -> str:
    """Extract the first URL from text. Handles Telegram share format."""
    text = text.strip()
    # If the whole text is a URL, return it directly
    if re.match(r"^https?://\S+$", text):
        return text
    # Find the first URL in the text
    match = re.search(r"https?://\S+", text)
    if match:
        return match.group(0).rstrip(".,;:!?）)」』")
    return ""


def generate_article_id(title: str, url: str = "") -> str:
    now = datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    hash_input = (title + url + str(now.timestamp())).encode("utf-8")
    short_hash = hashlib.md5(hash_input).hexdigest()[:8]
    return f"{date_prefix}-{short_hash}"


async def fetch_url_content(url: str) -> dict:
    """Fetch content using Playwright Async API (JavaScript rendering)."""
    result = {
        "title": "",
        "content": "",
        "summary": "",
        "source_url": url,
        "source_domain": extract_domain(url),
        "success": False,
        "error": "",
        "content_is_html": False,
    }

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
                ),
                viewport={"width": 390, "height": 844},  # Mobile viewport
                locale="zh-TW",
            )
            page = await context.new_page()

            # Navigate — use domcontentloaded to avoid hanging on pages with long-polling
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Additional wait for JS rendering
            await page.wait_for_timeout(4000)

            # Scroll down to trigger lazy-loaded content
            await page.evaluate("""() => {
                let totalHeight = 0;
                const distance = 300;
                const maxScrolls = 15;
                let scrolls = 0;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    scrolls++;
                    if (scrolls >= maxScrolls || totalHeight >= document.body.scrollHeight) {
                        clearInterval(timer);
                    }
                }, 200);
            }""")

            # Give JS a moment to render after scrolling
            await page.wait_for_timeout(3000)

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0);")
            await page.wait_for_timeout(500)

            # Get URL (may have redirected)
            final_url = page.url
            result["source_url"] = final_url
            result["source_domain"] = extract_domain(final_url)

            # Get title
            result["title"] = await page.title()

            # Get meta description
            meta_desc = await page.query_selector('meta[name="description"]')
            if meta_desc:
                result["summary"] = await meta_desc.get_attribute("content") or ""

            # Try Open Graph description
            if not result["summary"]:
                og_desc = await page.query_selector('meta[property="og:description"]')
                if og_desc:
                    result["summary"] = await og_desc.get_attribute("content") or ""

            # Get content — grab full body HTML and clean in Python
            await page.wait_for_timeout(2000)
            
            # First try CMS-specific selectors, then fall back to full body
            content_html = await page.evaluate("""() => {
                // Try Elementor/WordPress content area first
                const el = document.querySelector('.elementor-widget-theme-post-content') ||
                           document.querySelector('.entry-content') ||
                           document.querySelector('.post-content') ||
                           document.querySelector('.article-content') ||
                           document.querySelector('article') ||
                           document.querySelector('[role="main"]') ||
                           document.querySelector('main');
                if (el) return el.innerHTML;
                return document.body.innerHTML;
            }""")

            if content_html:
                # Clean the full body HTML in Python
                import html as html_mod

                # Remove non-rendering tags: script, style, noscript, svg, iframe
                content_html = re.sub(r'</?(?:script|style|noscript|svg|iframe)\s*[^>]*>', '', content_html, flags=re.IGNORECASE)
                # Remove event handlers (security)
                content_html = re.sub(r'\s+on\w+=["\'][^"\']*["\']', '', content_html, flags=re.IGNORECASE)
                # Remove HTML comments
                content_html = re.sub(r'<!--.*?-->', '', content_html, flags=re.DOTALL)
                # Remove empty paragraphs
                content_html = re.sub(r'<p>\s*</p>', '', content_html)
                # Collapse whitespace
                content_html = re.sub(r'>\s+<', '>\n<', content_html)
                content_html = re.sub(r'\n{3,}', '\n\n', content_html)

                # Truncate if too long
                if len(content_html) > MAX_CONTENT_CHARS:
                    content_html = content_html[:MAX_CONTENT_CHARS] + '\n\n[...內容過長已截斷...]'

                result["content"] = content_html
                result["content_is_html"] = True
                result["success"] = True
            else:
                # Fallback: get plain text
                body_text = await page.inner_text("body")
                if body_text:
                    body_text = re.sub(r"[ \t]+", " ", body_text)
                    body_text = re.sub(r"\n{3,}", "\n\n", body_text)
                    body_text = body_text.strip()
                    if len(body_text) > MAX_CONTENT_CHARS:
                        body_text = body_text[:MAX_CONTENT_CHARS] + "\n\n[...內容過長已截斷...]"
                    result["content"] = body_text
                    result["content_is_html"] = False
                    result["success"] = True
                else:
                    result["error"] = "No visible content found"

            # Fallback title
            if not result["title"]:
                result["title"] = result["source_domain"]

            await browser.close()

    except ImportError as e:
        result["error"] = f"Playwright not available: {e}"
    except Exception as e:
        error_msg = str(e)[:300]
        result["error"] = error_msg
        # Try fallback with requests
        try:
            import requests as req
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = req.get(url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            title_match = re.search(r"<title[^>]*>([^<]+)</title>", resp.text, re.IGNORECASE)
            if title_match:
                result["title"] = title_match.group(1).strip()

            text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) > MAX_CONTENT_CHARS:
                text = text[:MAX_CONTENT_CHARS]

            result["content"] = text
            result["success"] = True
            if not result["title"]:
                result["title"] = result["source_domain"]
        except Exception:
            pass  # Keep original error

    return result