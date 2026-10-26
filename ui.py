import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Dict, Any, Optional
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from engine import (
    load_settings,
    save_settings,
    scan_directory_for_sorting,
    scan_loose_folders,
    scan_unpackable_folders,
    scan_desktop_shortcuts,
    scan_scattered_apks,
    scan_duplicate_files,
    recycle_duplicates,
    execute_organization_moves,
    get_undo_history,
    undo_session,
    search_file_history,
    set_windows_context_menu,
    is_windows_context_menu_enabled,
    AutoPilotWatcher,
    get_downloads_path,
    get_real_desktop_path,
    format_bytes,
)
from updater import check_for_updates, download_and_apply_update, CURRENT_VERSION

# Cyber Dark Theme Palette
COLOR_BG = "#0b0b0e"
COLOR_SIDEBAR = "#121217"
COLOR_CARD = "#16161d"
COLOR_CARD_BORDER = "#23232e"
COLOR_TEXT_PRIMARY = "#f3f4f6"
COLOR_TEXT_SECONDARY = "#9ca3af"
COLOR_ACCENT_EMERALD = "#10b981"
COLOR_ACCENT_EMERALD_HOVER = "#059669"
COLOR_ACCENT_CYAN = "#06b6d4"
COLOR_ACCENT_CYAN_HOVER = "#0891b2"
COLOR_ACCENT_BLUE = "#3b82f6"
COLOR_ACCENT_BLUE_HOVER = "#2563eb"
COLOR_ACCENT_CRIMSON = "#e11d48"
COLOR_ACCENT_CRIMSON_HOVER = "#be123c"
COLOR_ACCENT_PURPLE = "#8b5cf6"

class VoidOrganizeApp(ctk.CTk):
    def __init__(self, initial_dir: Optional[str] = None):
        super().__init__()

        # Explicit Windows AppUserModelID for taskbar grouping & icon
        try:
            import ctypes
            myappid = "antigravity.voidorganize.filemanager.2.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        self.title("VoidOrganize — Automated High-Precision PC File & Clutter Optimizer")
        self.geometry("1240x800")
        self.minsize(1020, 680)
        self.configure(fg_color=COLOR_BG)

        self._setup_window_icon()

        # State storage
        self.settings = load_settings()
        self.current_tab = "downloads"
        self.planned_moves: List[Dict[str, Any]] = []
        self.item_checkbox_vars: List[ctk.BooleanVar] = []
        self.duplicate_items: List[Dict[str, Any]] = []
        self.dup_checkbox_vars: List[ctk.BooleanVar] = []
        self.custom_folder_path: str = initial_dir or ""

        # Auto-Pilot Watcher Instance
        self.watcher = AutoPilotWatcher(callback=self._watcher_log_callback)
        if self.settings.get("auto_pilot_enabled", False):
            self.watcher.start()

        # Layout build
        self._build_layout()

        # Initial view routing
        if initial_dir and os.path.isdir(initial_dir):
            self.switch_tab("custom")
            self._scan_custom(Path(initial_dir))
        else:
            self.after(300, self._scan_downloads_all)

        # Check for updates in background
        self._check_updates_background()

    def _setup_window_icon(self):
        try:
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
            ico_path = os.path.join(base_dir, "icon.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(default=ico_path)
        except Exception:
            pass

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Execution console
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main View

        # 1. Left Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=230, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)

        # Brand Title
        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=16, pady=(20, 4), sticky="w")

        try:
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
            png_path = os.path.join(base_dir, "icon.png")
            if os.path.exists(png_path):
                logo_pil = Image.open(png_path).resize((32, 32), Image.Resampling.LANCZOS)
                self.sidebar_logo_img = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(32, 32))
                self.logo_icon_label = ctk.CTkLabel(brand_frame, text="", image=self.sidebar_logo_img)
                self.logo_icon_label.pack(side="left", padx=(0, 8))
        except Exception:
            pass

        self.logo_label = ctk.CTkLabel(
            brand_frame,
            text="VOIDORGANIZE",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLOR_ACCENT_EMERALD,
        )
        self.logo_label.pack(side="left")

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Autonomous File & Clutter Optimizer",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.sub_label.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        # Sidebar Navigation Tabs
        self.nav_btns: Dict[str, ctk.CTkButton] = {}
        tabs = [
            ("downloads", "📥 Downloads Auto-Sort"),
            ("desktop", "🖥️ Desktop Tidy"),
            ("where", "🔎 Where Are My Files?"),
            ("duplicates", "♻️ Duplicate Hunter"),
            ("autopilot", "⚡ Auto-Pilot & Rules"),
            ("undo", "⏪ Undo & Rollback"),
            ("guide", "📖 User Guide & Safety"),
        ]

        for idx, (tab_id, tab_label) in enumerate(tabs, start=2):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=tab_label,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color="transparent",
                text_color=COLOR_TEXT_PRIMARY,
                hover_color=COLOR_CARD,
                height=38,
                corner_radius=8,
                command=lambda t=tab_id: self.switch_tab(t),
            )
            btn.grid(row=idx, column=0, padx=12, pady=3, sticky="ew")
            self.nav_btns[tab_id] = btn

        # Quick Links in Sidebar Footer
        self.update_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🔄 Check for Updates",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_CARD,
            hover_color=COLOR_CARD_BORDER,
            text_color=COLOR_ACCENT_EMERALD,
            height=30,
            command=self._manual_check_updates,
        )
        self.update_btn.grid(row=9, column=0, padx=12, pady=(10, 4), sticky="ew")

        self.open_dl_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="📁 Open Downloads",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_CARD,
            hover_color=COLOR_CARD_BORDER,
            text_color=COLOR_TEXT_SECONDARY,
            height=30,
            command=self._open_downloads_in_explorer,
        )
        self.open_dl_btn.grid(row=10, column=0, padx=12, pady=(0, 4), sticky="ew")

        self.open_desk_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🖥️ Open Desktop",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_CARD,
            hover_color=COLOR_CARD_BORDER,
            text_color=COLOR_TEXT_SECONDARY,
            height=30,
            command=self._open_desktop_in_explorer,
        )
        self.open_desk_btn.grid(row=11, column=0, padx=12, pady=(0, 16), sticky="ew")

        # 2. Main Content Frame
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self._build_top_header()
        self._build_preview_area()

        # 3. Bottom Execution Console
        self.console_frame = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, height=130, corner_radius=0)
        self.console_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        console_title_bar = ctk.CTkFrame(self.console_frame, fg_color="transparent", height=24)
        console_title_bar.grid(row=0, column=0, padx=16, pady=(6, 2), sticky="ew")

        console_label = ctk.CTkLabel(
            console_title_bar,
            text="ACTIVITY & TRANSPARENCY LOG",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
        )
        console_label.pack(side="left")

        clear_log_btn = ctk.CTkButton(
            console_title_bar,
            text="Clear",
            font=ctk.CTkFont(size=10),
            width=50,
            height=20,
            fg_color="transparent",
            hover_color=COLOR_CARD_BORDER,
            command=self._clear_console,
        )
        clear_log_btn.pack(side="right")

        self.console_textbox = ctk.CTkTextbox(
            self.console_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#08080a",
            text_color="#10b981",
            corner_radius=4,
        )
        self.console_textbox.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="nsew")

    def _build_top_header(self):
        self.header_card = ctk.CTkFrame(self.main_container, fg_color=COLOR_CARD, corner_radius=10)
        self.header_card.grid(row=0, column=0, pady=(0, 12), sticky="ew")
        self.header_card.grid_columnconfigure(1, weight=1)

        # Tab Info
        self.header_title = ctk.CTkLabel(
            self.header_card,
            text="Downloads Auto-Sort & Folder Unpacker",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        self.header_title.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        self.header_desc = ctk.CTkLabel(
            self.header_card,
            text="Routes loose files (.exe, .zip, .apk, scripts) and unpacks clutter folders like 'Anything' and '3 in 1'.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.header_desc.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # Action Buttons Area
        self.action_btn_frame = ctk.CTkFrame(self.header_card, fg_color="transparent")
        self.action_btn_frame.grid(row=0, column=1, rowspan=2, padx=16, pady=12, sticky="e")

        self.receipt_btn = ctk.CTkButton(
            self.action_btn_frame,
            text="📄 View Receipt",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_CARD_BORDER,
            hover_color=COLOR_SIDEBAR,
            height=34,
            command=self._open_latest_receipt,
        )
        self.receipt_btn.pack(side="left", padx=4)

        self.scan_btn = ctk.CTkButton(
            self.action_btn_frame,
            text="🔍 Scan",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_CARD_BORDER,
            hover_color=COLOR_SIDEBAR,
            height=34,
            command=self._trigger_active_scan,
        )
        self.scan_btn.pack(side="left", padx=4)

        self.execute_btn = ctk.CTkButton(
            self.action_btn_frame,
            text="⚡ 1-Click Organize",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT_EMERALD,
            hover_color=COLOR_ACCENT_EMERALD_HOVER,
            text_color="#000000",
            height=34,
            command=self._execute_organization,
        )
        self.execute_btn.pack(side="left", padx=4)

    def _build_preview_area(self):
        self.preview_card = ctk.CTkFrame(self.main_container, fg_color=COLOR_CARD, corner_radius=10)
        self.preview_card.grid(row=1, column=0, sticky="nsew")
        self.preview_card.grid_rowconfigure(1, weight=1)
        self.preview_card.grid_columnconfigure(0, weight=1)

        # Filter and Select Controls Bar
        self.controls_bar = ctk.CTkFrame(self.preview_card, fg_color="transparent", height=36)
        self.controls_bar.grid(row=0, column=0, padx=16, pady=(10, 4), sticky="ew")

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_chk = ctk.CTkCheckBox(
            self.controls_bar,
            text="Select All",
            font=ctk.CTkFont(size=12, weight="bold"),
            variable=self.select_all_var,
            command=self._toggle_select_all,
            fg_color=COLOR_ACCENT_EMERALD,
        )
        self.select_all_chk.pack(side="left")

        self.count_label = ctk.CTkLabel(
            self.controls_bar,
            text="0 items ready to organize (0 B)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.count_label.pack(side="left", padx=16)

        # Scrollable items table
        self.scroll_table = ctk.CTkScrollableFrame(self.preview_card, fg_color="transparent")
        self.scroll_table.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.scroll_table.grid_columnconfigure(1, weight=1)

    def switch_tab(self, tab_id: str):
        self.current_tab = tab_id
        for tid, btn in self.nav_btns.items():
            if tid == tab_id:
                btn.configure(fg_color=COLOR_CARD, text_color=COLOR_ACCENT_EMERALD)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_PRIMARY)

        # Re-show default controls if hidden by special tabs
        self.controls_bar.grid(row=0, column=0, padx=16, pady=(10, 4), sticky="ew")
        self.action_btn_frame.pack_forget() if False else None
        self.receipt_btn.pack(side="left", padx=4)
        self.scan_btn.pack(side="left", padx=4)
        self.execute_btn.pack(side="left", padx=4)

        if tab_id == "downloads":
            self.header_title.configure(text="Downloads Auto-Sort & Folder Unpacker")
            self.header_desc.configure(
                text="Routes loose files (.exe, .zip, .apk, media) and unpacks clutter folders like 'Anything' and '3 in 1'."
            )
            self.execute_btn.configure(text="⚡ Organize Downloads")
            self._scan_downloads_all()

        elif tab_id == "desktop":
            self.header_title.configure(text="Desktop Tidy")
            self.header_desc.configure(
                text="Sweeps loose .lnk shortcuts, .bat launchers, and web links into organized desktop folders."
            )
            self.execute_btn.configure(text="🧹 Tidy Desktop")
            self._scan_desktop()

        elif tab_id == "where":
            self.header_title.configure(text="Where Are My Files? — Instant Finder")
            self.header_desc.configure(
                text="Search any file you've organized to see its exact current path, destination folder, and open it instantly."
            )
            self.controls_bar.grid_remove()
            self.receipt_btn.pack_forget()
            self.scan_btn.pack_forget()
            self.execute_btn.pack_forget()
            self._show_where_files_tab()

        elif tab_id == "duplicates":
            self.header_title.configure(text="Duplicate Hunter & Space Reclaimer")
            self.header_desc.configure(
                text="Detects identical files using SHA-256 hashes and safely reclaims gigabytes of disk space."
            )
            self.receipt_btn.pack_forget()
            self.execute_btn.configure(text="🗑️ Recycle Duplicates")
            self._scan_duplicates()

        elif tab_id == "autopilot":
            self.header_title.configure(text="Auto-Pilot & System Settings")
            self.header_desc.configure(
                text="Configure live background sorting, Windows right-click context menu, and custom rules."
            )
            self.controls_bar.grid_remove()
            self.receipt_btn.pack_forget()
            self.scan_btn.pack_forget()
            self.execute_btn.pack_forget()
            self._show_autopilot_settings_tab()

        elif tab_id == "undo":
            self.header_title.configure(text="Undo & Rollback History")
            self.header_desc.configure(
                text="Every move is 100% reversible. Pick any past organization session to rollback files to their original locations."
            )
            self.receipt_btn.pack_forget()
            self.scan_btn.pack_forget()
            self.execute_btn.pack_forget()
            self._show_undo_history()

        elif tab_id == "guide":
            self.header_title.configure(text="User Guide & Transparency Map")
            self.header_desc.configure(
                text="How VoidOrganize organizes your PC, protects your files, and guarantees zero data loss."
            )
            self.controls_bar.grid_remove()
            self.receipt_btn.pack_forget()
            self.scan_btn.pack_forget()
            self.execute_btn.pack_forget()
            self._show_guide_tab()

    def _trigger_active_scan(self):
        if self.current_tab == "downloads":
            self._scan_downloads_all()
        elif self.current_tab == "desktop":
            self._scan_desktop()
        elif self.current_tab == "duplicates":
            self._scan_duplicates()
        elif self.current_tab == "undo":
            self._show_undo_history()

    def _scan_downloads_all(self):
        self.log_message("Scanning Downloads for loose files, loose folders, and APKs...")
        dl = get_downloads_path()

        def _worker():
            loose_files = scan_directory_for_sorting(dl, self.settings)
            loose_folders = scan_loose_folders(dl)
            unpack = scan_unpackable_folders(dl)
            apks = scan_scattered_apks()
            combined = loose_files + loose_folders + unpack + apks
            self.after(0, lambda: self._populate_table(combined))

        threading.Thread(target=_worker, daemon=True).start()

    def _scan_desktop(self):
        self.log_message("Scanning Desktop for loose shortcuts and launchers...")
        def _worker():
            moves = scan_desktop_shortcuts()
            self.after(0, lambda: self._populate_table(moves))
        threading.Thread(target=_worker, daemon=True).start()

    def _scan_custom(self, target_dir: Path):
        self.log_message(f"Scanning custom folder: {target_dir}...")
        self.header_desc.configure(text=f"Target: {target_dir}")
        def _worker():
            loose = scan_directory_for_sorting(target_dir, self.settings)
            folders = scan_loose_folders(target_dir)
            combined = loose + folders
            self.after(0, lambda: self._populate_table(combined))
        threading.Thread(target=_worker, daemon=True).start()

    def _scan_duplicates(self):
        self.log_message("Scanning Downloads for duplicate files (computing SHA-256 hashes)...")
        dl = get_downloads_path()

        def _worker():
            dups = scan_duplicate_files(dl)
            self.after(0, lambda: self._populate_duplicates_table(dups))

        threading.Thread(target=_worker, daemon=True).start()

    def _populate_table(self, moves: List[Dict[str, Any]]):
        self.planned_moves = moves
        self.item_checkbox_vars = []

        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        if not moves:
            lbl = ctk.CTkLabel(
                self.scroll_table,
                text="✨ Clean! No loose or disorganized items found.",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLOR_ACCENT_EMERALD,
            )
            lbl.pack(pady=40)
            self.count_label.configure(text="0 items to organize")
            return

        total_bytes = sum(m.get("size_bytes", 0) for m in moves)
        self.count_label.configure(
            text=f"{len(moves)} items ready to organize ({format_bytes(total_bytes)})"
        )

        for idx, item in enumerate(moves):
            row = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            row.grid_columnconfigure(1, weight=1)

            var = ctk.BooleanVar(value=True)
            self.item_checkbox_vars.append(var)

            chk = ctk.CTkCheckBox(row, text="", variable=var, width=24, fg_color=COLOR_ACCENT_EMERALD)
            chk.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8, sticky="w")

            filename_lbl = ctk.CTkLabel(
                row,
                text=item["filename"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
            )
            filename_lbl.grid(row=0, column=1, padx=4, pady=(6, 0), sticky="w")

            route_lbl = ctk.CTkLabel(
                row,
                text=f"{item.get('category', 'Category')} ➔ {Path(item['target_path']).parent.name}/",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_ACCENT_CYAN,
            )
            route_lbl.grid(row=1, column=1, padx=4, pady=(0, 6), sticky="w")

            size_lbl = ctk.CTkLabel(
                row,
                text=item["size_formatted"],
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
            )
            size_lbl.grid(row=0, column=2, rowspan=2, padx=14, sticky="e")

    def _populate_duplicates_table(self, duplicates: List[Dict[str, Any]]):
        self.duplicate_items = duplicates
        self.dup_checkbox_vars = []

        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        if not duplicates:
            lbl = ctk.CTkLabel(
                self.scroll_table,
                text="🎉 Zero duplicate files found! Your storage is completely optimized.",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLOR_ACCENT_EMERALD,
            )
            lbl.pack(pady=40)
            self.count_label.configure(text="0 duplicates found")
            return

        reclaimable_bytes = sum(d.get("size_bytes", 0) for d in duplicates)
        self.count_label.configure(
            text=f"{len(duplicates)} duplicates found ({format_bytes(reclaimable_bytes)} recoverable)"
        )

        for d in duplicates:
            row = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            row.grid_columnconfigure(1, weight=1)

            var = ctk.BooleanVar(value=True)
            self.dup_checkbox_vars.append(var)

            chk = ctk.CTkCheckBox(row, text="", variable=var, width=24, fg_color=COLOR_ACCENT_CRIMSON)
            chk.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8, sticky="w")

            title_lbl = ctk.CTkLabel(
                row,
                text=f"Duplicate: {d['filename']}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
            )
            title_lbl.grid(row=0, column=1, padx=4, pady=(6, 0), sticky="w")

            info_lbl = ctk.CTkLabel(
                row,
                text=f"Original in: {d['original_folder']}/  •  Duplicate in: {d['duplicate_folder']}/",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
            )
            info_lbl.grid(row=1, column=1, padx=4, pady=(0, 6), sticky="w")

            sz_lbl = ctk.CTkLabel(
                row,
                text=d["size_formatted"],
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLOR_ACCENT_EMERALD,
            )
            sz_lbl.grid(row=0, column=2, rowspan=2, padx=14, sticky="e")

    def _show_where_files_tab(self):
        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        search_container = ctk.CTkFrame(self.scroll_table, fg_color="transparent")
        search_container.pack(fill="x", padx=10, pady=(10, 16))

        prompt_lbl = ctk.CTkLabel(
            search_container,
            text="Type any file name or folder to find where VoidOrganize moved it:",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_PRIMARY,
        )
        prompt_lbl.pack(anchor="w", pady=(0, 6))

        input_box = ctk.CTkEntry(
            search_container,
            placeholder_text="e.g. AppMaka, setup.exe, TVCleaner, .apk, screenshot...",
            font=ctk.CTkFont(size=13),
            height=38,
            fg_color="#0e0f14",
            border_color=COLOR_CARD_BORDER,
        )
        input_box.pack(fill="x", side="left", expand=True, padx=(0, 8))

        results_frame = ctk.CTkFrame(self.scroll_table, fg_color="transparent")
        results_frame.pack(fill="both", expand=True, padx=10)

        def _do_search(event=None):
            q = input_box.get().strip()
            for w in results_frame.winfo_children():
                w.destroy()

            if not q:
                tip = ctk.CTkLabel(
                    results_frame,
                    text="Enter a keyword above to instantly trace your files.",
                    font=ctk.CTkFont(size=12),
                    text_color=COLOR_TEXT_SECONDARY,
                )
                tip.pack(pady=30)
                return

            matches = search_file_history(q)
            if not matches:
                no_match = ctk.CTkLabel(
                    results_frame,
                    text=f"No move records matching '{q}' found in history.",
                    font=ctk.CTkFont(size=13),
                    text_color=COLOR_TEXT_SECONDARY,
                )
                no_match.pack(pady=30)
                return

            count_match = ctk.CTkLabel(
                results_frame,
                text=f"Found {len(matches)} matching file movement records:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_ACCENT_EMERALD,
            )
            count_match.pack(anchor="w", pady=(0, 8))

            for m in matches:
                card = ctk.CTkFrame(results_frame, fg_color=COLOR_SIDEBAR, corner_radius=8)
                card.pack(fill="x", pady=4)
                card.grid_columnconfigure(0, weight=1)

                fn_lbl = ctk.CTkLabel(
                    card,
                    text=f"📄 {m['filename']}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLOR_TEXT_PRIMARY,
                )
                fn_lbl.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

                path_lbl = ctk.CTkLabel(
                    card,
                    text=f"Current Location: {m['current_path']}",
                    font=ctk.CTkFont(family="Consolas", size=11),
                    text_color=COLOR_ACCENT_CYAN,
                )
                path_lbl.grid(row=1, column=0, padx=12, pady=(0, 2), sticky="w")

                detail_lbl = ctk.CTkLabel(
                    card,
                    text=f"Category: {m['category']}  •  Moved: {m['timestamp']}  •  Size: {m['size_formatted']}",
                    font=ctk.CTkFont(size=11),
                    text_color=COLOR_TEXT_SECONDARY,
                )
                detail_lbl.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="w")

                open_btn = ctk.CTkButton(
                    card,
                    text="📂 Open File Location",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=COLOR_CARD,
                    hover_color=COLOR_CARD_BORDER,
                    height=30,
                    command=lambda p=m['current_path']: self._open_file_in_explorer(p),
                )
                open_btn.grid(row=0, column=1, rowspan=3, padx=12, pady=8, sticky="e")

        search_btn = ctk.CTkButton(
            search_container,
            text="🔎 Find File",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT_EMERALD,
            hover_color=COLOR_ACCENT_EMERALD_HOVER,
            text_color="#000000",
            height=38,
            command=_do_search,
        )
        search_btn.pack(side="left")
        input_box.bind("<Return>", _do_search)

    def _show_autopilot_settings_tab(self):
        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        card = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=10)
        card.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            card,
            text="⚡ Live Auto-Pilot Background Watcher",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            card,
            text="When enabled, VoidOrganize monitors your folders and automatically sorts completed downloads after 5 seconds.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # Auto-pilot switch
        ap_switch_var = ctk.BooleanVar(value=self.settings.get("auto_pilot_enabled", False))
        def _toggle_ap():
            val = ap_switch_var.get()
            self.settings["auto_pilot_enabled"] = val
            save_settings(self.settings)
            if val:
                self.watcher.start()
            else:
                self.watcher.stop()

        ap_switch = ctk.CTkSwitch(
            card,
            text="Enable Live Auto-Pilot Monitoring",
            font=ctk.CTkFont(size=13, weight="bold"),
            variable=ap_switch_var,
            command=_toggle_ap,
            progress_color=COLOR_ACCENT_EMERALD,
        )
        ap_switch.pack(anchor="w", padx=16, pady=(0, 10))

        # Checkboxes for watched folders
        watch_dl_var = ctk.BooleanVar(value=self.settings.get("auto_pilot_downloads", True))
        def _toggle_watch_dl():
            self.settings["auto_pilot_downloads"] = watch_dl_var.get()
            save_settings(self.settings)

        ctk.CTkCheckBox(
            card,
            text="Watch Downloads Folder",
            variable=watch_dl_var,
            command=_toggle_watch_dl,
            fg_color=COLOR_ACCENT_EMERALD,
        ).pack(anchor="w", padx=32, pady=4)

        watch_desk_var = ctk.BooleanVar(value=self.settings.get("auto_pilot_desktop", False))
        def _toggle_watch_desk():
            self.settings["auto_pilot_desktop"] = watch_desk_var.get()
            save_settings(self.settings)

        ctk.CTkCheckBox(
            card,
            text="Watch Desktop (Auto-sweep loose shortcuts)",
            variable=watch_desk_var,
            command=_toggle_watch_desk,
            fg_color=COLOR_ACCENT_EMERALD,
        ).pack(anchor="w", padx=32, pady=(4, 16))

        # Context Menu Card
        ctx_card = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=10)
        ctx_card.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            ctx_card,
            text="🖱️ Windows Explorer Right-Click Context Menu",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            ctx_card,
            text="Adds '⚡ Organize with VoidOrganize' to the right-click menu of any folder on your PC.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        ctx_var = ctk.BooleanVar(value=is_windows_context_menu_enabled())
        def _toggle_ctx():
            val = ctx_var.get()
            res = set_windows_context_menu(val)
            self.log_message(f"Windows Context Menu {'registered' if val else 'removed'}.")

        ctk.CTkSwitch(
            ctx_card,
            text="Enable 'Organize with VoidOrganize' Context Menu Option",
            font=ctk.CTkFont(size=13, weight="bold"),
            variable=ctx_var,
            command=_toggle_ctx,
            progress_color=COLOR_ACCENT_EMERALD,
        ).pack(anchor="w", padx=16, pady=(0, 16))

        # HTML Receipts Card
        rcpt_card = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=10)
        rcpt_card.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            rcpt_card,
            text="📄 Visual Receipts & Transparency",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(16, 4))

        rcpt_var = ctk.BooleanVar(value=self.settings.get("create_html_receipts", True))
        def _toggle_rcpt():
            self.settings["create_html_receipts"] = rcpt_var.get()
            save_settings(self.settings)

        ctk.CTkSwitch(
            rcpt_card,
            text="Drop interactive 'WHERE_DID_MY_FILES_GO.html' in organized folders",
            font=ctk.CTkFont(size=13, weight="bold"),
            variable=rcpt_var,
            command=_toggle_rcpt,
            progress_color=COLOR_ACCENT_EMERALD,
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def _show_undo_history(self):
        history = get_undo_history()
        self.planned_moves = []
        self.item_checkbox_vars = []

        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        if not history:
            lbl = ctk.CTkLabel(
                self.scroll_table,
                text="No past organization sessions recorded yet.",
                font=ctk.CTkFont(size=13),
                text_color=COLOR_TEXT_SECONDARY,
            )
            lbl.pack(pady=40)
            return

        for session in history:
            row = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=8)
            row.pack(fill="x", pady=4, padx=4)
            row.grid_columnconfigure(0, weight=1)

            title_lbl = ctk.CTkLabel(
                row,
                text=f"Session: {session.get('timestamp')} — ({session.get('count', 0)} files moved)",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
            )
            title_lbl.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

            detail_lbl = ctk.CTkLabel(
                row,
                text=f"Session ID: {session.get('session_id')}",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
            )
            detail_lbl.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

            undo_btn = ctk.CTkButton(
                row,
                text="⏪ Rollback This Session",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=COLOR_ACCENT_CRIMSON,
                hover_color=COLOR_ACCENT_CRIMSON_HOVER,
                command=lambda s=session.get("session_id"): self._execute_undo_session(s),
            )
            undo_btn.grid(row=0, column=1, rowspan=2, padx=12, pady=10, sticky="e")

    def _show_guide_tab(self):
        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        guide_card = ctk.CTkFrame(self.scroll_table, fg_color=COLOR_SIDEBAR, corner_radius=10)
        guide_card.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            guide_card,
            text="🛡️ VoidOrganize Safety & Transparency Architecture",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_ACCENT_EMERALD,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        guide_text = """
1. ZERO DATA LOSS GUARANTEE:
   • VoidOrganize NEVER deletes your files during organization.
   • If a file with the same name already exists in the destination, it resolves the collision safely (e.g. 'file (1).ext').
   • In-flight downloads (.crdownload, .tmp, .part) are automatically protected and skipped.

2. WHERE DO FILES GO BY DEFAULT?
   • APKs & Mobile: .apk, .xapk, .ipa ➔ Sideloading/APKs/
   • Installers: .exe, .msi, .iso ➔ Installers/
   • Archives: .zip, .rar, .7z, .tar ➔ Archives/
   • Media: .png, .jpg, .webp ➔ Images/  |  .mp4, .mkv ➔ Videos/
   • Documents: .pdf, .docx, .xlsx, .txt, .csv, .md ➔ Documents/
   • Scripts & Code: .cpp, .wh.cpp, .py, .js, .bat ➔ Scripts & Code/
   • Shortcuts: .lnk, .url ➔ Shortcuts & Launchers/ (Apps, Games, Tools)

3. WHERE ARE MY FILES?
   • Use the 'Where Are My Files?' tab to search for any file by name and open its location instantly.
   • Every organized folder receives an interactive 'WHERE_DID_MY_FILES_GO.html' map with a built-in search bar.

4. 1-CLICK ROLLBACK (UNDO):
   • Every movement is logged in local JSON history.
   • Open 'Undo & Rollback' at any time to return all files to their original spots with a single click.
"""
        lbl = ctk.CTkLabel(
            guide_card,
            text=guide_text.strip(),
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLOR_TEXT_PRIMARY,
            justify="left",
        )
        lbl.pack(anchor="w", padx=16, pady=(0, 16))

    def _execute_organization(self):
        if self.current_tab == "duplicates":
            self._execute_duplicates_cleanup()
            return

        selected_items = [
            self.planned_moves[i]
            for i, var in enumerate(self.item_checkbox_vars)
            if var.get()
        ]

        if not selected_items:
            messagebox.showinfo("VoidOrganize", "No items selected to organize.")
            return

        if not messagebox.askyesno(
            "Confirm Organization",
            f"Organize {len(selected_items)} selected items into their designated folders?\n\n(A visual receipt will be created, and all moves can be rolled back anytime via the Undo tab).",
        ):
            return

        self.log_message(f"Starting organization of {len(selected_items)} items...")

        def _worker():
            root_target = get_downloads_path() if self.current_tab == "downloads" else get_real_desktop_path()
            result = execute_organization_moves(selected_items, target_root=root_target, log_callback=self.log_message)
            self.log_message(
                f"[✓] Completed! Successfully organized {result['success_count']} items ({result['formatted_size']})."
            )
            self.after(0, self._trigger_active_scan)

        threading.Thread(target=_worker, daemon=True).start()

    def _execute_duplicates_cleanup(self):
        selected_dups = [
            self.duplicate_items[i]
            for i, var in enumerate(self.dup_checkbox_vars)
            if var.get()
        ]
        if not selected_dups:
            messagebox.showinfo("VoidOrganize", "No duplicate items selected.")
            return

        reclaim_str = format_bytes(sum(d.get("size_bytes", 0) for d in selected_dups))
        if not messagebox.askyesno(
            "Confirm Duplicate Recycle",
            f"Move {len(selected_dups)} duplicate files ({reclaim_str}) to the Windows Recycle Bin?\n\n(This recovers disk space safely without risking the original files).",
        ):
            return

        def _worker():
            res = recycle_duplicates(selected_dups, log_callback=self.log_message)
            self.log_message(f"[✓] Recycled {res['count']} duplicate files. Recovered {res['formatted_size']}.")
            self.after(0, self._scan_duplicates)

        threading.Thread(target=_worker, daemon=True).start()

    def _execute_undo_session(self, session_id: str):
        if not messagebox.askyesno(
            "Confirm Rollback",
            f"Are you sure you want to rollback this session?\nAll files will be moved back to their original locations.",
        ):
            return

        self.log_message(f"Starting rollback for session: {session_id}...")
        def _worker():
            restored, errors = undo_session(session_id, log_callback=self.log_message)
            self.log_message(f"Rollback complete: {restored} files restored, {errors} errors.")
            self.after(0, self._show_undo_history)

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_select_all(self):
        val = self.select_all_var.get()
        if self.current_tab == "duplicates":
            for var in self.dup_checkbox_vars:
                var.set(val)
        else:
            for var in self.item_checkbox_vars:
                var.set(val)

    def _open_latest_receipt(self):
        dl = get_downloads_path()
        receipt = dl / "WHERE_DID_MY_FILES_GO.html"
        if not receipt.exists():
            receipt = get_real_desktop_path() / "WHERE_DID_MY_FILES_GO.html"

        if receipt.exists():
            os.startfile(str(receipt))
        else:
            messagebox.showinfo("Receipt", "No organization receipt found yet. Run an organization pass first!")

    def _open_file_in_explorer(self, file_path_str: str):
        try:
            p = Path(file_path_str)
            if p.exists():
                subprocess.Popen(f'explorer /select,"{p.resolve()}"')
            elif p.parent.exists():
                os.startfile(str(p.parent))
            else:
                messagebox.showwarning("File Missing", f"File not found at:\n{file_path_str}")
        except Exception as e:
            self.log_message(f"Could not open file location: {e}")

    def _open_downloads_in_explorer(self):
        try:
            os.startfile(str(get_downloads_path()))
        except Exception as e:
            self.log_message(f"Could not open Downloads: {e}")

    def _open_desktop_in_explorer(self):
        try:
            os.startfile(str(get_real_desktop_path()))
        except Exception as e:
            self.log_message(f"Could not open Desktop: {e}")

    def _watcher_log_callback(self, msg: str):
        self.after(0, lambda: self.log_message(msg))

    def log_message(self, msg: str):
        self.console_textbox.insert("end", f"{msg}\n")
        self.console_textbox.see("end")

    def _check_updates_background(self):
        def _worker():
            info = check_for_updates()
            if info:
                self.after(0, lambda: self._prompt_update_available(info))
        threading.Thread(target=_worker, daemon=True).start()

    def _manual_check_updates(self):
        self.log_message("Checking GitHub for VoidOrganize updates...")
        def _worker():
            info = check_for_updates()
            if info:
                self.after(0, lambda: self._prompt_update_available(info))
            else:
                self.after(0, lambda: messagebox.showinfo(
                    "VoidOrganize",
                    f"You are running the latest version of VoidOrganize (v{CURRENT_VERSION})!"
                ))
        threading.Thread(target=_worker, daemon=True).start()

    def _prompt_update_available(self, info: Dict[str, Any]):
        ver = info.get("latest_version", "")
        name = info.get("release_name", ver)
        dl_url = info.get("download_url")

        msg = f"A new version of VoidOrganize is available!\n\nVersion: {ver} ({name})\nCurrent: v{CURRENT_VERSION}\n\n"
        if dl_url:
            msg += "Would you like to automatically download and apply the update now?"
            if messagebox.askyesno("Update Available", msg):
                self._apply_auto_update(dl_url)
        else:
            msg += "Visit the GitHub release page to view download assets."
            if messagebox.askyesno("Update Available", msg):
                import webbrowser
                webbrowser.open(info.get("html_url", "https://github.com/crtGhoul/VoidOrganize/releases"))

    def _apply_auto_update(self, dl_url: str):
        self.log_message(f"Downloading update from {dl_url}...")
        def _worker():
            def _progress(pct):
                self.after(0, lambda: self.log_message(f"Downloading update... {pct}%"))
            ok = download_and_apply_update(dl_url, progress_callback=_progress)
            if not ok:
                self.after(0, lambda: messagebox.showerror("Update Error", "Failed to download or apply update."))

        threading.Thread(target=_worker, daemon=True).start()

    def _clear_console(self):
        self.console_textbox.delete("1.0", "end")

def launch_app(initial_dir: Optional[str] = None):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = VoidOrganizeApp(initial_dir=initial_dir)
    app.mainloop()

if __name__ == "__main__":
    launch_app()
