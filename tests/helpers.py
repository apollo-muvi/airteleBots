"""Test helpers — load bot modules from hyphenated directories."""
import sys
import os
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_module(bot_dir: str, module_name: str):
    """Load a Python module from a bot's directory.
    
    Also registers the module under its simple name (e.g. 'transcript')
    so that sibling modules (e.g. bot.py importing transcript) can find it.
    
    Args:
        bot_dir: e.g. 'know-bot'
        module_name: e.g. 'content_fetcher' (no .py)
    Returns:
        The loaded module object.
    """
    path = os.path.join(REPO_ROOT, bot_dir, f"{module_name}.py")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such module: {path}")
    spec = importlib.util.spec_from_file_location(
        f"{bot_dir}.{module_name}", path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Register under both qualified name (for module identity) and
    # simple name (for sibling imports like 'import transcript')
    sys.modules[spec.name] = mod
    sys.modules[module_name] = mod
    return mod