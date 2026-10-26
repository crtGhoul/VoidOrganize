import os
import sys
import shutil
import hashlib
import json
import time
import winreg
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Callable
import send2trash

# App directory for configuration, logs, and undo history
APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VoidOrganize"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
UNDO_LOG_PATH = APP_DATA_DIR / "undo_history.json"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Standard Category Mapping
DEFAULT_CATEGORY_MAP: Dict[str, List[str]] = {
    "APKs & Sideloading": [".apk", ".xapk", ".apks", ".ipa", ".plist"],
    "Installers": [".exe", ".msi", ".iso", ".img"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Images": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico", ".tiff", ".heic"],
    "Videos": [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"],
    "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".csv", ".md", ".epub", ".rtf", ".log"],
    "Scripts & Code": [".cpp", ".h", ".py", ".js", ".ts", ".html", ".css", ".json", ".bat", ".ps1", ".sh", ".vbs", ".wh.cpp", ".rs", ".go"],
    "Shortcuts": [".lnk", ".url"],
}

# Subfolder destination names
DEFAULT_CATEGORY_FOLDERS: Dict[str, str] = {
    "APKs & Sideloading": os.path.join("Sideloading", "APKs"),
    "Installers": "Installers",
    "Archives": "Archives",
    "Images": "Images",
    "Videos": "Videos",
    "Audio": "Audio",
    "Documents": "Documents",
    "Scripts & Code": "Scripts & Code",
    "Shortcuts": "Shortcuts",
}

# Loose folder categorization rules
FOLDER_CATEGORY_RULES: Dict[str, List[str]] = {
    "Games": ["game", "games", "keeper", "zomboid", "minecraft", "steam", "valorant", "gta", "mod", "ankergames"],
    "Tools": ["tools", "platform-tools", "driver", "vbcable", "cleaner", "quicmic", "adb", "serein", "omnireel", "ollama"],
    "Sideloading": ["sideload", "altstore", "sidestore", "jailbreak", "ipa", "apk"],
}

# Default Application Settings
DEFAULT_SETTINGS: Dict[str, Any] = {
    "auto_pilot_enabled": False,
    "auto_pilot_downloads": True,
    "auto_pilot_desktop": False,
    "auto_pilot_delay_sec": 5,
    "create_html_receipts": True,
    "category_map": DEFAULT_CATEGORY_MAP,
    "category_folders": DEFAULT_CATEGORY_FOLDERS,
    "ignored_names": ["desktop.ini", ".webui_secret_key", "thumbs.db"],
    "ignored_folders": ["ai", "antigravity", "projects", "node_modules", ".git", "venv", "documents", "pictures", "music", "videos"],
}

def load_settings() -> Dict[str, Any]:
    """Load settings from persistent JSON file or return defaults."""
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any]) -> None:
    """Save settings dictionary to disk."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_real_desktop_path() -> Path:
    """Detect real Windows desktop (handles OneDrive Desktop synchronization)."""
    onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
    if onedrive_desktop.exists():
        return onedrive_desktop
    standard_desktop = Path.home() / "Desktop"
    if standard_desktop.exists():
        return standard_desktop
    return onedrive_desktop

def get_downloads_path() -> Path:
    """Return standard user Downloads directory."""
    return Path.home() / "Downloads"

def compute_sha256(file_path: Path, max_bytes: int = 15 * 1024 * 1024) -> str:
    """Calculate SHA-256 hash of a file (sampling first 15MB for fast comparison)."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(max_bytes)
            hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def format_bytes(size: int) -> str:
    """Human-readable byte size."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

def get_category_for_file(file_path: Path, custom_map: Optional[Dict[str, List[str]]] = None) -> Optional[str]:
    """Identify which category a file belongs to based on extension and naming."""
    name_lower = file_path.name.lower()
    
    # In-progress downloads should NEVER be touched
    if any(name_lower.endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".downloading", ".opdownload"]):
        return None

    # Special double-extension detection
    if name_lower.endswith(".wh.cpp"):
        return "Scripts & Code"
    
    cat_map = custom_map or DEFAULT_CATEGORY_MAP
    ext = file_path.suffix.lower()
    for category, extensions in cat_map.items():
        if ext in extensions:
            return category
    return None

def resolve_destination_collision(target_dir: Path, filename: str) -> Path:
    """Generate conflict-free path if a file already exists in target."""
    dest = target_dir / filename
    if not dest.exists():
        return dest
    
    stem = dest.stem
    suffix = dest.suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

def scan_directory_for_sorting(root_dir: Path, custom_settings: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Scan a directory for loose files that belong in organized subfolders.
    Returns list of planned move actions.
    """
    settings = custom_settings or load_settings()
    planned_moves: List[Dict[str, Any]] = []
    if not root_dir.exists():
        return planned_moves

    ignored_names = set(k.lower() for k in settings.get("ignored_names", []))
    cat_folders = settings.get("category_folders", DEFAULT_CATEGORY_FOLDERS)

    try:
        entries = list(root_dir.iterdir())
    except Exception:
        return planned_moves

    for entry in entries:
        if entry.is_file():
            name_lower = entry.name.lower()
            if name_lower in ignored_names or name_lower.startswith("~$"):
                continue

            category = get_category_for_file(entry, settings.get("category_map"))
            if not category:
                continue

            subfolder_rel = cat_folders.get(category, category)
            target_folder = root_dir / subfolder_rel
            
            # If the file is already inside its designated category folder, ignore
            if entry.parent.resolve() == target_folder.resolve():
                continue

            try:
                size_bytes = entry.stat().st_size
            except Exception:
                size_bytes = 0

            target_path = resolve_destination_collision(target_folder, entry.name)

            planned_moves.append({
                "type": "file",
                "source": str(entry.resolve()),
                "filename": entry.name,
                "category": category,
                "target_dir": str(target_folder.resolve()),
                "target_path": str(target_path.resolve()),
                "size_bytes": size_bytes,
                "size_formatted": format_bytes(size_bytes),
                "selected": True,
            })
    return planned_moves

def scan_loose_folders(root_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan root folder for naked loose directories that should live under Games, Tools, or Sideloading.
    """
    planned_moves: List[Dict[str, Any]] = []
    if not root_dir.exists():
        return planned_moves

    known_categories = {
        "installers", "archives", "images", "videos", "audio", "documents",
        "scripts & code", "shortcuts", "sideloading", "games", "tools",
        "githubpjs", "ai", "antigravity", ".git", "node_modules", "shortcuts & launchers"
    }

    try:
        entries = [e for e in root_dir.iterdir() if e.is_dir()]
    except Exception:
        return planned_moves

    for folder in entries:
        name_low = folder.name.lower()
        if name_low in known_categories or name_low.startswith("."):
            continue

        target_cat = None
        for cat, keywords in FOLDER_CATEGORY_RULES.items():
            if any(k in name_low for k in keywords):
                target_cat = cat
                break

        if target_cat:
            target_parent = root_dir / target_cat
            # Avoid moving if already there
            if folder.parent.resolve() == target_parent.resolve():
                continue

            target_path = target_parent / folder.name
            if target_path.exists():
                target_path = resolve_destination_collision(target_parent, folder.name)

            # Compute folder size
            folder_size = 0
            item_count = 0
            try:
                for p in folder.rglob("*"):
                    if p.is_file():
                        folder_size += p.stat().st_size
                        item_count += 1
            except Exception:
                pass

            planned_moves.append({
                "type": "loose_folder",
                "source": str(folder.resolve()),
                "filename": f"{folder.name}/ ({item_count} items)",
                "category": f"Folder ➔ {target_cat}",
                "target_dir": str(target_parent.resolve()),
                "target_path": str(target_path.resolve()),
                "size_bytes": folder_size,
                "size_formatted": format_bytes(folder_size),
                "selected": True,
            })

    return planned_moves

def scan_unpackable_folders(downloads_dir: Path) -> List[Dict[str, Any]]:
    """
    Scans legacy or user clutter folders like 'Anything' and '3 in 1'
    to route files and delete the empty wrapper folders.
    """
    planned_moves: List[Dict[str, Any]] = []
    if not downloads_dir.exists():
        return planned_moves

    # 1. 'Anything' Folder
    anything_dir = downloads_dir / "Anything"
    if anything_dir.exists() and anything_dir.is_dir():
        installers_dir = downloads_dir / "Installers"
        tools_dir = downloads_dir / "Tools"
        sideload_dir = downloads_dir / "Sideloading" / "APKs"
        
        for item in anything_dir.iterdir():
            if item.is_file():
                cat = get_category_for_file(item)
                if cat == "APKs & Sideloading":
                    tgt_dir = sideload_dir
                elif cat == "Installers" or item.suffix.lower() in [".exe", ".msi"]:
                    tgt_dir = installers_dir
                else:
                    tgt_dir = downloads_dir / (DEFAULT_CATEGORY_FOLDERS.get(cat, "Installers"))

                tgt_path = resolve_destination_collision(tgt_dir, item.name)
                try:
                    size = item.stat().st_size
                except Exception:
                    size = 0

                planned_moves.append({
                    "type": "unpack_item",
                    "source": str(item.resolve()),
                    "filename": f"Anything / {item.name}",
                    "category": f"Unpack ➔ {cat or 'Installers'}",
                    "target_dir": str(tgt_dir.resolve()),
                    "target_path": str(tgt_path.resolve()),
                    "size_bytes": size,
                    "size_formatted": format_bytes(size),
                    "parent_to_clean": str(anything_dir.resolve()),
                    "selected": True,
                })
            elif item.is_dir():
                # Subfolder inside Anything (e.g. Aniimo, Discord Plugins)
                tgt_dir = tools_dir / item.name
                planned_moves.append({
                    "type": "unpack_folder",
                    "source": str(item.resolve()),
                    "filename": f"Anything / {item.name}/",
                    "category": "Unpack ➔ Tools",
                    "target_dir": str(tools_dir.resolve()),
                    "target_path": str(tgt_dir.resolve()),
                    "size_bytes": 0,
                    "size_formatted": "Folder",
                    "parent_to_clean": str(anything_dir.resolve()),
                    "selected": True,
                })

    # 2. '3 in 1' Folder
    three_in_one = downloads_dir / "3 in 1"
    if three_in_one.exists() and three_in_one.is_dir():
        tools_dir = downloads_dir / "Tools" / "quicmic"
        for item in three_in_one.iterdir():
            tgt_path = resolve_destination_collision(tools_dir, item.name)
            try:
                size = item.stat().st_size if item.is_file() else 0
            except Exception:
                size = 0
            planned_moves.append({
                "type": "unpack_item",
                "source": str(item.resolve()),
                "filename": f"3 in 1 / {item.name}",
                "category": "Unpack ➔ Tools/quicmic",
                "target_dir": str(tools_dir.resolve()),
                "target_path": str(tgt_path.resolve()),
                "size_bytes": size,
                "size_formatted": format_bytes(size) if item.is_file() else "Folder",
                "parent_to_clean": str(three_in_one.resolve()),
                "selected": True,
            })

    return planned_moves

def scan_desktop_shortcuts() -> List[Dict[str, Any]]:
    """Scan loose shortcuts, .bat, and .url files on Desktop to tidy them into categories."""
    desktop = get_real_desktop_path()
    planned_moves: List[Dict[str, Any]] = []
    if not desktop.exists():
        return planned_moves

    desktop_shortcuts_dir = desktop / "Shortcuts & Launchers"
    games_shortcuts_dir = desktop_shortcuts_dir / "Games"
    tools_shortcuts_dir = desktop_shortcuts_dir / "Tools & Launchers"
    apps_shortcuts_dir = desktop_shortcuts_dir / "Apps"

    game_keywords = ["deadlock", "steam", "valorant", "game", "mod manager", "zomboid", "minecraft"]
    tool_keywords = ["terminal", "cmd", "opencode", "voidpurge", "gpu", "sharex", "audit", "cleaner", "organize"]

    for entry in desktop.iterdir():
        if entry.is_file():
            ext = entry.suffix.lower()
            if ext in [".lnk", ".url", ".bat"]:
                name_low = entry.stem.lower()
                
                if any(k in name_low for k in game_keywords):
                    target_dir = games_shortcuts_dir
                    cat = "Desktop: Games"
                elif any(k in name_low for k in tool_keywords):
                    target_dir = tools_shortcuts_dir
                    cat = "Desktop: Tools"
                else:
                    target_dir = apps_shortcuts_dir
                    cat = "Desktop: Apps"

                target_path = resolve_destination_collision(target_dir, entry.name)
                try:
                    size = entry.stat().st_size
                except Exception:
                    size = 0

                planned_moves.append({
                    "type": "desktop_item",
                    "source": str(entry.resolve()),
                    "filename": entry.name,
                    "category": cat,
                    "target_dir": str(target_dir.resolve()),
                    "target_path": str(target_path.resolve()),
                    "size_bytes": size,
                    "size_formatted": format_bytes(size),
                    "selected": True,
                })
    return planned_moves

def scan_scattered_apks() -> List[Dict[str, Any]]:
    """Scan development sandboxes and folders to gather all APKs into Sideloading/APKs."""
    planned_moves: List[Dict[str, Any]] = []
    downloads = get_downloads_path()
    dest_dir = downloads / "Sideloading" / "APKs"

    search_roots = [
        Path.home() / "Documents" / "antigravity",
        downloads / "TVCleaner-v1.2-PC-Tools",
        downloads / "Tools" / "TVCleaner-v1.2-PC-Tools",
        downloads / "Sideloading",
    ]

    seen_sources = set()
    for root in search_roots:
        if not root.exists():
            continue
        try:
            for apk in root.rglob("*.apk"):
                if apk.parent.resolve() == dest_dir.resolve():
                    continue
                resolved = str(apk.resolve())
                if resolved in seen_sources:
                    continue
                seen_sources.add(resolved)

                try:
                    size = apk.stat().st_size
                except Exception:
                    size = 0

                target_path = resolve_destination_collision(dest_dir, apk.name)
                planned_moves.append({
                    "type": "apk_gather",
                    "source": resolved,
                    "filename": f"{apk.parent.name} / {apk.name}",
                    "category": "APKs & Sideloading",
                    "target_dir": str(dest_dir.resolve()),
                    "target_path": str(target_path.resolve()),
                    "size_bytes": size,
                    "size_formatted": format_bytes(size),
                    "selected": True,
                })
        except Exception:
            pass

    return planned_moves

def scan_duplicate_files(root_dir: Path) -> List[Dict[str, Any]]:
    """
    Find duplicate files in a directory hierarchy based on file size and SHA-256 hash.
    Returns list of duplicate candidates for safe recycling.
    """
    duplicates: List[Dict[str, Any]] = []
    if not root_dir.exists():
        return duplicates

    size_map: Dict[int, List[Path]] = {}
    
    # 1. First pass: Group by file size (instant)
    try:
        for file_path in root_dir.rglob("*"):
            if file_path.is_file():
                try:
                    sz = file_path.stat().st_size
                    if sz > 1024:
                        size_map.setdefault(sz, []).append(file_path)
                except Exception:
                    continue
    except Exception:
        pass

    # 2. Second pass: Compute SHA-256 for size collisions
    hash_map: Dict[str, List[Path]] = {}
    for sz, paths in size_map.items():
        if len(paths) > 1:
            for p in paths:
                h = compute_sha256(p)
                if h:
                    hash_map.setdefault(h, []).append(p)

    # 3. Third pass: Identify duplicates
    for h, paths in hash_map.items():
        if len(paths) > 1:
            paths_sorted = sorted(paths, key=lambda p: (len(p.stem), p.stat().st_ctime))
            original = paths_sorted[0]
            for dup in paths_sorted[1:]:
                sz = dup.stat().st_size
                duplicates.append({
                    "original_path": str(original.resolve()),
                    "duplicate_path": str(dup.resolve()),
                    "filename": dup.name,
                    "original_folder": original.parent.name,
                    "duplicate_folder": dup.parent.name,
                    "size_bytes": sz,
                    "size_formatted": format_bytes(sz),
                    "hash": h,
                    "selected": True,
                })

    return duplicates

def recycle_duplicates(duplicates: List[Dict[str, Any]], log_callback=None) -> Dict[str, Any]:
    """Safely move selected duplicate files to Windows Recycle Bin."""
    reclaimed_bytes = 0
    reclaimed_count = 0
    errors = 0

    for item in duplicates:
        if not item.get("selected", True):
            continue
        dup_path = Path(item["duplicate_path"])
        if not dup_path.exists():
            continue
        try:
            sz = item.get("size_bytes", 0)
            send2trash.send2trash(str(dup_path))
            reclaimed_bytes += sz
            reclaimed_count += 1
            if log_callback:
                log_callback(f"[🗑️] Recycled Duplicate: {dup_path.name} (Saved {item.get('size_formatted')})")
        except Exception as e:
            errors += 1
            if log_callback:
                log_callback(f"[-] Failed to recycle {dup_path.name}: {e}")

    return {
        "count": reclaimed_count,
        "bytes": reclaimed_bytes,
        "formatted_size": format_bytes(reclaimed_bytes),
        "errors": errors,
    }

def execute_organization_moves(moves: List[Dict[str, Any]], target_root: Optional[Path] = None, log_callback=None) -> Dict[str, Any]:
    """
    Execute selected moves, record them in the Undo log, generate an HTML receipt, and return summary.
    """
    settings = load_settings()
    successful_moves: List[Dict[str, Any]] = []
    failed_moves: List[Dict[str, Any]] = []
    total_bytes = 0

    session_id = f"session_{int(time.time())}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    parents_to_check_for_cleanup = set()

    for item in moves:
        if not item.get("selected", True):
            continue

        src = Path(item["source"])
        tgt = Path(item["target_path"])
        tgt_dir = Path(item["target_dir"])

        if not src.exists():
            if log_callback:
                log_callback(f"[!] Source missing: {src.name}")
            failed_moves.append({"item": item, "error": "Source not found"})
            continue

        try:
            tgt_dir.mkdir(parents=True, exist_ok=True)
            
            # Avoid self-move
            if src.resolve() == tgt.resolve():
                continue

            shutil.move(str(src), str(tgt))
            sz = item.get("size_bytes", 0)
            total_bytes += sz

            record = {
                "session_id": session_id,
                "timestamp": timestamp,
                "source": str(src.resolve()),
                "destination": str(tgt.resolve()),
                "filename": src.name,
                "category": item.get("category", "General"),
                "size_bytes": sz,
                "size_formatted": format_bytes(sz),
            }
            successful_moves.append(record)

            if "parent_to_clean" in item:
                parents_to_check_for_cleanup.add(Path(item["parent_to_clean"]))

            if log_callback:
                log_callback(f"[+] Moved: {src.name} ➔ {tgt_dir.name}/")

        except Exception as e:
            if log_callback:
                log_callback(f"[-] Failed to move {src.name}: {e}")
            failed_moves.append({"item": item, "error": str(e)})

    # Cleanup empty clutter folders
    for parent in parents_to_check_for_cleanup:
        try:
            if parent.exists() and parent.is_dir():
                remaining = list(parent.iterdir())
                if len(remaining) == 0:
                    parent.rmdir()
                    if log_callback:
                        log_callback(f"[x] Removed empty clutter folder: {parent.name}")
        except Exception:
            pass

    # Save to Undo Log
    if successful_moves:
        _save_undo_records(session_id, timestamp, successful_moves)

        # Generate "WHERE_DID_MY_FILES_GO.html" receipt in root folder
        receipt_dir = target_root or Path(successful_moves[0]["source"]).parent
        if settings.get("create_html_receipts", True) and receipt_dir.exists():
            generate_html_receipt(session_id, timestamp, successful_moves, receipt_dir)
            generate_txt_receipt(session_id, timestamp, successful_moves, receipt_dir)
            if log_callback:
                log_callback(f"[📄] Created file receipt: {receipt_dir / 'WHERE_DID_MY_FILES_GO.html'}")

    return {
        "success_count": len(successful_moves),
        "failed_count": len(failed_moves),
        "total_bytes": total_bytes,
        "formatted_size": format_bytes(total_bytes),
        "session_id": session_id,
    }

def _save_undo_records(session_id: str, timestamp: str, records: List[Dict[str, Any]]) -> None:
    """Append move operations to undo log file."""
    history = []
    if UNDO_LOG_PATH.exists():
        try:
            with open(UNDO_LOG_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    session_entry = {
        "session_id": session_id,
        "timestamp": timestamp,
        "count": len(records),
        "moves": records,
    }
    history.append(session_entry)

    with open(UNDO_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def get_undo_history() -> List[Dict[str, Any]]:
    """Retrieve full history of past organization sessions."""
    if not UNDO_LOG_PATH.exists():
        return []
    try:
        with open(UNDO_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        return []

def search_file_history(query: str) -> List[Dict[str, Any]]:
    """
    Search historical move records to answer 'Where did my file go?'.
    Matches filename, source path, or destination path.
    """
    if not query.strip():
        return []
    q_low = query.strip().lower()
    history = get_undo_history()
    matches: List[Dict[str, Any]] = []

    for session in history:
        for m in session.get("moves", []):
            name = m.get("filename", "").lower()
            src = m.get("source", "").lower()
            dst = m.get("destination", "").lower()

            if q_low in name or q_low in src or q_low in dst:
                cur_path = Path(m["destination"])
                exists_now = cur_path.exists()
                matches.append({
                    "filename": m.get("filename", ""),
                    "category": m.get("category", "General"),
                    "original_path": m.get("source", ""),
                    "current_path": m.get("destination", ""),
                    "current_folder": cur_path.parent.name,
                    "timestamp": m.get("timestamp", session.get("timestamp", "")),
                    "size_formatted": m.get("size_formatted", format_bytes(m.get("size_bytes", 0))),
                    "exists_at_destination": exists_now,
                    "session_id": session.get("session_id", ""),
                })
    return matches

def undo_session(session_id: str, log_callback=None) -> Tuple[int, int]:
    """
    Rollback all moves from a specified organization session.
    Returns (restored_count, error_count).
    """
    if not UNDO_LOG_PATH.exists():
        return 0, 0

    try:
        with open(UNDO_LOG_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        return 0, 0

    session_to_undo = None
    remaining_history = []
    for s in history:
        if s.get("session_id") == session_id:
            session_to_undo = s
        else:
            remaining_history.append(s)

    if not session_to_undo:
        return 0, 0

    restored = 0
    errors = 0

    for record in reversed(session_to_undo.get("moves", [])):
        current_loc = Path(record["destination"])
        original_loc = Path(record["source"])

        if not current_loc.exists():
            errors += 1
            if log_callback:
                log_callback(f"[!] Cannot restore (missing): {current_loc.name}")
            continue

        try:
            original_loc.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current_loc), str(original_loc))
            restored += 1
            if log_callback:
                log_callback(f"[<] Restored: {original_loc.name} ➔ {original_loc.parent.name}/")
        except Exception as e:
            errors += 1
            if log_callback:
                log_callback(f"[-] Restore error {original_loc.name}: {e}")

    try:
        with open(UNDO_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(remaining_history, f, indent=2)
    except Exception:
        pass

    return restored, errors

def generate_html_receipt(session_id: str, timestamp: str, records: List[Dict[str, Any]], output_dir: Path) -> Path:
    """
    Generate an interactive, dark-mode, responsive single-file HTML receipt
    so anyone opening the folder knows exactly where every file moved.
    """
    receipt_file = output_dir / "WHERE_DID_MY_FILES_GO.html"
    
    rows_html = ""
    for r in records:
        src = r.get("source", "")
        dst = r.get("destination", "")
        fname = r.get("filename", Path(src).name)
        cat = r.get("category", "General")
        sz = r.get("size_formatted", format_bytes(r.get("size_bytes", 0)))
        dest_folder = Path(dst).parent.name
        
        rows_html += f"""
        <tr>
            <td class="file-name"><strong>{fname}</strong></td>
            <td><span class="badge">{cat}</span></td>
            <td><span class="folder-badge">📁 {dest_folder}/</span></td>
            <td class="path-cell" title="{dst}">{dst}</td>
            <td class="size-cell">{sz}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VoidOrganize — Where Did My Files Go?</title>
    <style>
        :root {{
            --bg: #0b0b0e;
            --card: #16161d;
            --border: #23232e;
            --emerald: #10b981;
            --cyan: #06b6d4;
            --text-main: #f3f4f6;
            --text-sub: #9ca3af;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: var(--bg); color: var(--text-main); padding: 30px 20px; }}
        .container {{ max-width: 1100px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 24px; }}
        .brand {{ display: flex; align-items: center; gap: 12px; }}
        .brand h1 {{ font-size: 24px; color: var(--emerald); letter-spacing: 0.5px; }}
        .brand span {{ font-size: 13px; color: var(--text-sub); }}
        .meta-pill {{ background: rgba(16, 185, 129, 0.1); border: 1px solid var(--emerald); color: var(--emerald); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: bold; }}
        .search-box {{ width: 100%; padding: 12px 16px; background: #0f1015; border: 1px solid var(--border); border-radius: 8px; color: #fff; font-size: 14px; margin-bottom: 20px; outline: none; }}
        .search-box:focus {{ border-color: var(--emerald); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ background: #121217; padding: 12px 14px; font-size: 12px; color: var(--text-sub); text-transform: uppercase; border-bottom: 1px solid var(--border); }}
        td {{ padding: 12px 14px; border-bottom: 1px solid var(--border); font-size: 13px; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}
        .badge {{ background: rgba(6, 182, 212, 0.15); color: var(--cyan); padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .folder-badge {{ background: #1f2029; color: var(--emerald); padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .path-cell {{ color: var(--text-sub); font-family: Consolas, monospace; font-size: 11px; max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .size-cell {{ color: var(--text-sub); text-align: right; }}
        .footer {{ margin-top: 24px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--text-sub); border-top: 1px solid var(--border); padding-top: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">
                <div>
                    <h1>VOIDORGANIZE</h1>
                    <span>Automatic File Organization & Clarity Map</span>
                </div>
            </div>
            <div class="meta-pill">{len(records)} Files Organized ({timestamp})</div>
        </div>

        <input type="text" id="searchInput" class="search-box" placeholder="🔍 Search by file name, category, or destination folder..." onkeyup="filterTable()">

        <table id="filesTable">
            <thead>
                <tr>
                    <th>File Name</th>
                    <th>Category</th>
                    <th>Destination Folder</th>
                    <th>Exact Path</th>
                    <th style="text-align: right;">Size</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="footer">
            <span>Session ID: {session_id}</span>
            <span>All moves are 100% reversible in the <strong>VoidOrganize</strong> app under the <em>Undo & Rollback</em> tab.</span>
        </div>
    </div>

    <script>
        function filterTable() {{
            const input = document.getElementById("searchInput").value.toLowerCase();
            const rows = document.querySelectorAll("#filesTable tbody tr");
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(input) ? "" : "none";
            }});
        }}
    </script>
</body>
</html>
"""
    try:
        with open(receipt_file, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        print(f"Failed to generate HTML receipt: {e}")

    return receipt_file

def generate_txt_receipt(session_id: str, timestamp: str, records: List[Dict[str, Any]], output_dir: Path) -> Path:
    """Generate a quick text file summary."""
    txt_file = output_dir / "WHERE_DID_MY_FILES_GO.txt"
    lines = [
        "=" * 70,
        f"VOIDORGANIZE MOVE RECEIPT — {timestamp}",
        f"Total Files Organized: {len(records)}",
        f"Session ID: {session_id}",
        "=" * 70,
        "",
        "FILENAME -> DESTINATION FOLDER",
        "-" * 70,
    ]
    for r in records:
        fname = r.get("filename", "")
        dst = r.get("destination", "")
        folder = Path(dst).parent.name
        lines.append(f"{fname:<40} -> {folder}/")

    lines.extend([
        "",
        "-" * 70,
        "Note: To undo this move, open VoidOrganize and click 'Rollback This Session'.",
        "=" * 70,
    ])

    try:
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass
    return txt_file

# --- Windows Shell Context Menu Integration ---
def set_windows_context_menu(enable: bool = True) -> bool:
    """
    Register or unregister '⚡ Organize with VoidOrganize' in the Windows Explorer
    right-click context menu (HKCU - no admin required).
    """
    try:
        exe_path = Path(sys.executable).resolve()
        # If running as python script in dev, point to python main.py, else point to VoidOrganize.exe
        if exe_path.name.lower().startswith("python"):
            script_path = (Path(__file__).parent / "main.py").resolve()
            command_str = f'"{exe_path}" "{script_path}" "%1"'
        else:
            command_str = f'"{exe_path}" "%1"'

        key_path = r"Software\Classes\Directory\shell\VoidOrganize"
        key_bg_path = r"Software\Classes\Directory\Background\shell\VoidOrganize"

        if enable:
            # 1. Directory right-click
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "⚡ Organize with VoidOrganize")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(exe_path))
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\command") as cmd_key:
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command_str)

            # 2. Directory background right-click
            bg_command_str = command_str.replace('"%1"', '"%V"')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_bg_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "⚡ Organize this folder with VoidOrganize")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(exe_path))
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key_bg_path}\command") as cmd_key:
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, bg_command_str)

            return True
        else:
            # Delete keys
            _delete_reg_key_tree(winreg.HKEY_CURRENT_USER, key_path)
            _delete_reg_key_tree(winreg.HKEY_CURRENT_USER, key_bg_path)
            return False
    except Exception as e:
        print(f"Context menu registry error: {e}")
        return False

def is_windows_context_menu_enabled() -> bool:
    """Check if context menu item is registered."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\VoidOrganize"):
            return True
    except Exception:
        return False

def _delete_reg_key_tree(root, subkey):
    """Recursively delete registry key tree."""
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    sub = winreg.EnumKey(key, 0)
                    _delete_reg_key_tree(key, sub)
                except OSError:
                    break
        winreg.DeleteKey(root, subkey)
    except Exception:
        pass

# --- Live Auto-Pilot Watcher Engine ---
class AutoPilotWatcher:
    """
    Background file watcher that monitors Downloads & Desktop.
    Automatically sorts newly completed files after a safety cooldown.
    """
    def __init__(self, callback: Optional[Callable[[str], None]] = None):
        self.callback = callback
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._tracked_mtimes: Dict[str, float] = {}

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if self.callback:
            self.callback("[⚡] Auto-Pilot Watcher started (Monitoring Downloads & Desktop).")

    def stop(self):
        self.is_running = False
        if self.callback:
            self.callback("[⚡] Auto-Pilot Watcher paused.")

    def _run_loop(self):
        settings = load_settings()
        delay_sec = settings.get("auto_pilot_delay_sec", 5)

        while self.is_running:
            try:
                targets = []
                if settings.get("auto_pilot_downloads", True):
                    targets.append(get_downloads_path())
                if settings.get("auto_pilot_desktop", False):
                    targets.append(get_real_desktop_path())

                for root in targets:
                    if not root.exists():
                        continue
                    loose = scan_directory_for_sorting(root, settings)
                    # Filter files that are quiet (file size stopped changing for delay_sec seconds)
                    now = time.time()
                    ready_to_move = []
                    for item in loose:
                        p = Path(item["source"])
                        try:
                            mtime = p.stat().st_mtime
                            last_seen = self._tracked_mtimes.get(str(p), mtime)
                            if now - mtime >= delay_sec:
                                ready_to_move.append(item)
                                if str(p) in self._tracked_mtimes:
                                    del self._tracked_mtimes[str(p)]
                            else:
                                self._tracked_mtimes[str(p)] = mtime
                        except Exception:
                            continue

                    if ready_to_move:
                        execute_organization_moves(ready_to_move, target_root=root, log_callback=self.callback)

            except Exception as e:
                if self.callback:
                    self.callback(f"[Watcher Error] {e}")

            time.sleep(3)
