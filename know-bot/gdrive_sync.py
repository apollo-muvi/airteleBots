"""
Know_Bot Google Drive Sync — Uploads saved HTML files to Google Drive.
"""
import os
import subprocess
import json
import config

GAPI_CMD = [
    "python3",
    os.path.expanduser("~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"),
]


def _run_gapi(*args, timeout=20):
    """Run a GAPI command and return parsed JSON result."""
    try:
        result = subprocess.run(
            GAPI_CMD + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        print(f"[GDrive] GAPI error (exit={result.returncode}): {result.stderr[:200]}")
        return None
    except subprocess.TimeoutExpired:
        print("[GDrive] GAPI timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"[GDrive] JSON parse error: {e}")
        return None
    except FileNotFoundError:
        print(f"[GDrive] GAPI script not found")
        return None
    except Exception as e:
        print(f"[GDrive] Error: {e}")
        return None


def ensure_folder() -> str:
    """Ensure the Know_Bot Knowledge folder exists in Drive. Returns folder ID."""
    if not config.GDRIVE_ENABLED:
        return ""

    # Search for existing folder
    result = _run_gapi("drive", "search", config.GDRIVE_FOLDER_NAME, "--max", "5")
    if result and isinstance(result, list) and len(result) > 0:
        return result[0].get("id", "")

    # Create folder
    result = _run_gapi("drive", "create-folder", config.GDRIVE_FOLDER_NAME)
    if result and isinstance(result, dict):
        return result.get("id", "")

    return ""


def upload_file(file_path: str, filename: str, folder_id: str = "") -> dict:
    """Upload a file to Drive. Returns the full result dict or None."""
    if not config.GDRIVE_ENABLED:
        return None

    args = ["drive", "upload", file_path]
    if folder_id:
        args.extend(["--parent", folder_id])
    if filename:
        args.extend(["--name", filename])

    result = _run_gapi(*args, timeout=30)
    return result


def sync_article(local_path: str, article_id: str, title: str) -> dict:
    """Sync a saved HTML article to Drive. Returns result dict or None."""
    if not config.GDRIVE_ENABLED:
        print("[GDrive] Sync disabled by config")
        return None

    if not os.path.exists(local_path):
        print(f"[GDrive] File not found: {local_path}")
        return None

    # Get folder
    folder_id = ensure_folder()
    if not folder_id:
        print("[GDrive] Failed to get/create folder")
        return None

    # Upload
    safe_title = title.replace("/", "_").replace(":", "_").replace("\n", " ")[:60]
    drive_filename = f"{article_id}-{safe_title}.html"

    result = upload_file(local_path, drive_filename, folder_id)
    if result and result.get("status") == "uploaded":
        print(f"[GDrive] ✅ Uploaded: {drive_filename}")
        return result
    else:
        print(f"[GDrive] ❌ Upload failed for {drive_filename}")
        return None