#!/usr/bin/env python3
"""AI Code Review script — runs on Pi 4 self-hosted runner.

Fetches a PR diff, calls Hermes API for analysis,
posts review to GitHub PR, and sends Telegram notification.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error


# ─── Configuration ─────────────────────────────────────────
PR_NUMBER = os.environ.get("PR_NUMBER", sys.argv[1] if len(sys.argv) > 1 else "")
if not PR_NUMBER:
    print("❌ PR_NUMBER is required (env var or arg)")
    sys.exit(1)

REPO = os.environ.get("GITHUB_REPOSITORY", "apollo-muvi/airteleBots")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_HOME_CHANNEL", "8838496684")

# Load Hermes env vars from Pi 4
def load_env(path="/home/apollo/.hermes/.env"):
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()
    return env

hermes_env = load_env()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or hermes_env.get("TELEGRAM_BOT_TOKEN", "")
HERMES_API = os.environ.get("HERMES_API_BASE") or hermes_env.get("HERMES_API_BASE", "http://localhost:8642/v1")
HERMES_KEY = os.environ.get("API_SERVER_KEY") or hermes_env.get("API_SERVER_KEY", "hermes-api-key-local")

# GitHub token: env > git credentials
GH_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
if not GH_TOKEN:
    git_creds = os.path.expanduser("~/.git-credentials")
    if os.path.exists(git_creds):
        with open(git_creds) as f:
            for line in f:
                if "github.com" in line:
                    GH_TOKEN = line.split(":")[-1].split("@")[0]
                    break

if not GH_TOKEN:
    print("❌ No GITHUB_TOKEN available")
    sys.exit(1)

print(f"🔍 Reviewing PR #{PR_NUMBER} on {REPO}")


# ─── API Helpers ───────────────────────────────────────────
def gh_api(path, method="GET", data=None, accept=None):
    """Call GitHub API."""
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "User-Agent": "hermes-agent",
    }
    if accept:
        headers["Accept"] = accept
    if data is not None:
        data = json.dumps(data).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            if accept and "diff" in accept:
                return body
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ GitHub API error {e.code}: {body[:200]}")
        return None


def hermes_api(system_prompt, user_input):
    """Call Hermes API Server for code review."""
    payload = {
        "model": "hermes-agent",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        f"{HERMES_API}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {HERMES_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ Hermes API error: {e}")
        return None


def send_telegram(text, parse_mode="Markdown"):
    """Send Telegram notification via rain425bot."""
    if not TELEGRAM_TOKEN:
        return
    payload = {
        "chat_id": TELEGRAM_CHAT,
        "text": text[:4000],
        "parse_mode": parse_mode,
    }
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            pass
        print("✅ Telegram sent")
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")


# ─── Step 1: Fetch PR details ─────────────────────────────
print("\n📥 Fetching PR details...")

pr_data = gh_api(f"/repos/{REPO}/pulls/{PR_NUMBER}")
if not pr_data:
    sys.exit(1)

pr_title = pr_data.get("title", f"PR #{PR_NUMBER}")
pr_author = pr_data.get("user", {}).get("login", "unknown")
pr_body = pr_data.get("body", "") or ""
pr_url = pr_data.get("html_url", "")
head_sha = pr_data.get("head", {}).get("sha", "")

pr_diff = gh_api(
    f"/repos/{REPO}/pulls/{PR_NUMBER}",
    accept="application/vnd.github.v3.diff",
)
pr_diff = (pr_diff or "")[:8000]  # truncate to 8K

# Changed files
files_data = gh_api(f"/repos/{REPO}/pulls/{PR_NUMBER}/files?per_page=30")
changed_lines = []
if files_data:
    for f in files_data:
        status = f.get("status", "?")
        adds = f.get("additions", 0)
        dels = f.get("deletions", 0)
        changed_lines.append(f"  {status:10s} +{adds:-4d} -{dels:-4d}  {f['filename']}")
changed_str = "\n".join(changed_lines) if changed_lines else "  (no files)"

print(f"Title: {pr_title}")
print(f"Author: {pr_author}")
print(f"Files:\n{changed_str}")


# ─── Step 2: Call Hermes API ─────────────────────────────
print("\n🤖 Running code review via Hermes API...")

SYSTEM_PROMPT = """You are a JSON-only code review bot. You MUST respond with ONLY valid JSON and NOTHING else — no explanations, no markdown, no code fences, no backticks, no extra text. Your entire response must be parseable by json.loads().

Analyze the GitHub Pull Request diff below and return this JSON structure:
{
  "summary": "One-line summary",
  "score": 7,
  "issues": [
    {
      "severity": "critical",
      "file": "path/to/file.py",
      "line": 10,
      "message": "description",
      "suggestion": "how to fix"
    }
  ],
  "good_points": ["clean code"]
}

Rules:
- critical: security issues, bugs, data loss risks
- warning: code quality, potential bugs, missing edge cases
- suggestion: style improvements, best practices
- Score 8-10 = good, 5-7 = needs work, 0-4 = major issues
- If no issues, issues array is empty []
- Line number 0 if unclear
- Use exact file paths from the diff
- Start your response with { and end with }
- DO NOT write ANY text outside the JSON object"""

# More relaxed fallback prompt if JSON mode fails
FALLBACK_PROMPT = """You are a code reviewer. Analyze this PR diff.

Respond ONLY with valid JSON. Start with { and end with }. No other text.

{
  "summary": "...",
  "score": 7,
  "issues": [{"severity": "critical", "file": "", "line": 0, "message": "", "suggestion": ""}],
  "good_points": []
}"""

USER_INPUT = f"""PR #{PR_NUMBER}: "{pr_title}"
Author: {pr_author}

Description:
{pr_body}

Changed files:
{changed_str}

Diff:
{pr_diff}"""

# Try primary prompt first, fallback to simpler prompt
raw = hermes_api(SYSTEM_PROMPT, USER_INPUT)
if not raw:
    error_comment = {"body": "## 🤖 AI Code Review\n\n❌ Review failed: Hermes API unreachable\n\n---\n_Reviewed by Hermes Agent_"}
    gh_api(f"/repos/{REPO}/issues/{PR_NUMBER}/comments", method="POST", data=error_comment)
    sys.exit(1)

# Extract JSON with retry + fallback prompt
def extract_json(text):
    """Try multiple strategies to extract JSON from LLM response."""
    text = text.strip()
    
    # Strategy 1: direct parse
    for _ in range(2):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Strip ```json ... ``` fences
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()
    
    # Strategy 2: find outermost { }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    
    return None

review_json = extract_json(raw)

# If still no JSON, try fallback prompt
if not review_json:
    print("⚠️ First prompt returned non-JSON, trying fallback prompt...")
    raw2 = hermes_api(FALLBACK_PROMPT, USER_INPUT)
    if raw2:
        review_json = extract_json(raw2)

# If still no JSON, build from text heuristics
if not review_json:
    print("⚠️ Both prompts failed JSON. Building review from raw text...")
    # Extract score
    score_match = re.search(r'[Ss]core[:\s]*(\d+)/?(\d*)?', raw)
    score = int(score_match.group(1)) if score_match else 5
    
    # Extract issues count
    issue_count = len(re.findall(r'critical|bug|error|vulnerability', raw, re.IGNORECASE))
    
    # Find file references
    files_found = re.findall(r'`([^`]+\.py):?(\d+)?`', raw)
    
    review_json = {
        "summary": "Review generated from text analysis (JSON parsing failed)",
        "score": score,
        "issues": [],
        "good_points": []
    }
    
    # Extract first line as summary
    first_line = raw.strip().split("\n")[0][:100]
    if first_line:
        review_json["summary"] = first_line

print(json.dumps(review_json, indent=2, ensure_ascii=False))


# ─── Step 3: Post GitHub comment ──────────────────────────
print(f"\n📝 Posting review to PR #{PR_NUMBER}...")

def format_github_comment(data):
    summary = data.get("summary", "Review complete")
    score = data.get("score", 0)
    issues = data.get("issues", [])
    good = data.get("good_points", [])

    lines = [f"## 🤖 AI Code Review\n**{summary}** | **Score: {score}/10** | **Issues: {len(issues)}**\n"]
    sev_map = {"critical": ":red_circle:", "warning": ":warning:", "suggestion": ":bulb:"}

    if issues:
        lines.append("### Issues")
        for iss in issues:
            sev = iss.get("severity", "suggestion")
            emoji = sev_map.get(sev, ":bulb:")
            loc = f"{iss.get('file','')}:{iss.get('line',0)}" if iss.get("line") else iss.get("file","")
            lines.append(f"{emoji} **[{sev.upper()}]** {loc} — {iss.get('message','')}")
            if iss.get("suggestion"):
                lines.append(f"> {iss['suggestion']}")
        lines.append("")

    if good:
        lines.append("### ✅ Good Points")
        for gp in good:
            lines.append(f"- {gp}")
        lines.append("")

    lines.append("---")
    lines.append("_Reviewed by Hermes Agent_")
    return {"body": "\n".join(lines)}

comment_data = format_github_comment(review_json)
result = gh_api(f"/repos/{REPO}/issues/{PR_NUMBER}/comments", method="POST", data=comment_data)

if result and result.get("html_url"):
    print(f"✅ Review posted: {result['html_url']}")
else:
    print("⚠️ Failed to post comment")


# ─── Step 4: Telegram notification ────────────────────────
print("\n📱 Sending Telegram notification...")

def format_telegram(data):
    score = data.get("score", 0)
    issues = len(data.get("issues", []))
    summary = data.get("summary", "")
    stars = "⭐" * max(1, score // 2) if score else ""
    
    return (
        f"🔍 *Code Review — PR #{PR_NUMBER}*\n"
        f"*{pr_title}*\n"
        f"Author: {pr_author}\n\n"
        f"{stars} Score: {score}/10  |  Issues: {issues}\n"
        f"📊 {summary}\n\n"
        f"{pr_url}"
    )

tg_text = format_telegram(review_json)
send_telegram(tg_text)

print(f"\n🎉 Code review complete for PR #{PR_NUMBER}!")
