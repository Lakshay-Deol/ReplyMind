import json
from typing import Any

from app.paths import memory_dir


def safe_load_json(file_name: str, default: Any) -> Any:
    """Load JSON file safely, return default on missing or corrupted."""
    path = memory_dir() / file_name
    if not path.exists():
        return default
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return default
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return default

def safe_save_json(file_name: str, data: Any) -> None:
    """Save data to JSON file safely, creating directories if needed."""
    directory = memory_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name
    
    # write to temp and rename for atomic operation
    temp_path = path.with_suffix('.tmp')
    try:
        temp_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        pass
