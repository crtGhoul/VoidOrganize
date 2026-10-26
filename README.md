# VoidOrganize (v2.0) — Autonomous PC File & Clutter Optimizer

> **Zero Clutter. Zero Confusion. Zero Data Loss.**  
> A high-precision Windows utility that organizes loose files and directories, eliminates naked desktop clutter, hunts down duplicate files, and ensures users always know **exactly where their files went**.

---

## 🌟 Why VoidOrganize?

Most file organizers dump files into mystery folders and leave users lost. **VoidOrganize was engineered for 100% transparency, safety, and release-ready usability:**

1. **🔎 "Where Are My Files?" (Instant File Tracer)**
   - Type any keyword, extension, or filename in the app to immediately see its original location, new destination folder, move date, and click **"Open File Location"** to reveal it in Windows Explorer.
2. **📄 Visual Receipts (`WHERE_DID_MY_FILES_GO.html`)**
   - Automatically drops a sleek, responsive, dark-mode HTML interactive receipt right inside organized folders. Anyone opening the folder sees an interactive table with a live search bar showing where every file went.
3. **📁 "No Naked Folders" Engine**
   - Routes not just individual files, but naked folders (e.g. standalone game folders into `Games/`, driver & developer kits into `Tools/`, and unpacks cluttered containers like `Anything` and `3 in 1`).
4. **♻️ Duplicate Hunter & Space Reclaimer**
   - Employs cryptographic SHA-256 hashing to pinpoint redundant downloads (like `setup (1).exe` vs `setup.exe`) and safely sends duplicates to the **Windows Recycle Bin** (`send2trash`), freeing up gigabytes without risking originals.
5. **⚡ Live Auto-Pilot Background Watcher**
   - Optionally monitors `Downloads` and `Desktop` in real time. When a file finishes downloading (skipping in-flight `.crdownload` / `.tmp` files), it automatically categorizes it after a 5-second quiet period.
6. **🖱️ Windows Right-Click Context Menu Integration**
   - Toggle on "⚡ Organize with VoidOrganize" in Windows Explorer to right-click *any* folder on your PC and tidy it on demand.
7. **⏪ 100% Granular Rollback & Undo**
   - Every movement is recorded in local transactional JSON. Rollback any past session with one click.

---

## 📂 Default Organization Map

| Category | Extensions | Destination Folder |
| :--- | :--- | :--- |
| **APKs & Sideloading** | `.apk`, `.xapk`, `.apks`, `.ipa`, `.plist` | `Sideloading/APKs/` |
| **Installers & Setups**| `.exe`, `.msi`, `.iso`, `.img` | `Installers/` |
| **Archives & Zips**    | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2` | `Archives/` |
| **Images & Media**     | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.ico` | `Images/` |
| **Videos**             | `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`, `.flv` | `Videos/` |
| **Audio**              | `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.m4a` | `Audio/` |
| **Documents**          | `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.md` | `Documents/` |
| **Scripts & Code**     | `.cpp`, `.wh.cpp`, `.py`, `.js`, `.ts`, `.bat`, `.ps1` | `Scripts & Code/` |
| **Desktop Shortcuts**  | `.lnk`, `.url`, `.bat` | `Shortcuts & Launchers/` (`Apps`, `Games`, `Tools`) |

---

## 🛡️ Safety Guarantees

* **Non-Destructive**: Never deletes original files during organization.
* **Collision Resolution**: If a file named `report.pdf` already exists in `Documents/`, the new file is automatically saved safely as `report (1).pdf`.
* **Download Shield**: Files actively being downloaded (`.crdownload`, `.part`, `.tmp`) are automatically ignored until complete.
* **Local & Private**: Zero cloud dependencies, zero telemetry, runs 100% locally on your machine.

---

## 🚀 Building from Source

```cmd
git clone https://github.com/crtGhoul/VoidOrganize.git
cd VoidOrganize
pip install -r requirements.txt
build_exe.bat
```
Output standalone executable: `dist/VoidOrganize.exe`
