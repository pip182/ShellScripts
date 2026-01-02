#!/usr/bin/env python3
"""
GUI for creating a live and installable Arch Linux ISO from current
installation.

Changes in this version:
- Live ISO boots to GNOME (graphical) by:
  - Writing /root/customize_airootfs.sh into airootfs (executed by mkarchiso)
  - Enabling gdm + NetworkManager
  - Setting default.target to graphical.target
  - Creating user BEFORE gdm starts, and optional GDM autologin
- Writes /root/pkglist.txt into the ISO (from the final packages.x86_64 list)
- Replaces /root/install.sh with a real UEFI installer that:
  - Wipes selected disk, creates EFI+root partitions
  - pacstrap using /root/pkglist.txt (if present)
  - Enables NetworkManager + GDM and installs systemd-boot

Requires: PyQt6 (pip install PyQt6 or pacman -S python-pyqt6)
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from typing import List, Tuple

# Constants


class Colors:
    """Color constants for UI styling - comprehensive dark theme palette"""

    # Status colors
    SUCCESS = "#51cf66"
    ERROR = "#ff6b6b"
    INFO = "#74c0fc"
    WARNING = "#ff6b6b"

    # Background colors (dark theme)
    BG_PRIMARY = "#1e1e1e"              # Main window background
    BG_SECONDARY = "#252525"            # Input fields, list widgets
    BG_TERTIARY = "#2a2a2a"             # Hover states, tooltips
    BG_QUATERNARY = "#292929"           # Alternate backgrounds
    BG_DARKEST = "#1a1a1a"              # Text edit backgrounds
    BG_BUTTON = "#3a3a3a"               # Default button background
    BG_BUTTON_HOVER = "#454545"         # Button hover state
    BG_BUTTON_PRESSED = "#2d2d2d"       # Button pressed state
    BG_DISABLED = "#1e1e1e"             # Disabled widget background

    # Text colors
    TEXT_PRIMARY = "#f0f0f0"            # Primary text color
    TEXT_SECONDARY = "#e0e0e0"          # Secondary text (group box titles)
    TEXT_DISABLED = "#707070"           # Disabled text
    TEXT_SELECTION = "#ffffff"          # Selected text color

    # Border colors
    BORDER_DEFAULT = "#404040"          # Default border
    BORDER_HOVER = "#505050"            # Hover border
    BORDER_ACTIVE = "#606060"           # Active/hover border (lighter)
    BORDER_FOCUS = "#4682b4"            # Focus border (blue)
    BORDER_DISABLED = "#353535"         # Disabled border (dashed)

    # Button colors
    BUTTON_SUCCESS = "#4a7c59"          # Success button (green)
    BUTTON_SUCCESS_HOVER = "#5a9c69"
    BUTTON_SUCCESS_PRESSED = "#295137"
    BUTTON_SUCCESS_BORDER = "#5a9c69"
    BUTTON_SUCCESS_BORDER_HOVER = "#6aac79"

    BUTTON_ERROR = "#7c4a4a"            # Error button (red)
    BUTTON_ERROR_HOVER = "#9c5a5a"
    BUTTON_ERROR_PRESSED = "#6c3a3a"
    BUTTON_ERROR_BORDER = "#9c5a5a"
    BUTTON_ERROR_BORDER_HOVER = "#ac6a6a"

    # Selection colors
    SELECTION_BG = "#4682b4"            # Selection background (blue)
    SELECTION_TEXT = "#ffffff"          # Selection text

    # List/Item colors
    LIST_ITEM_BORDER = "#353535"        # List item separator
    LIST_ITEM_HOVER = "#353535"         # List item hover

    # Checkbox colors
    CHECKBOX_BORDER = "#505050"         # Checkbox border
    CHECKBOX_BORDER_HOVER = "#606060"   # Checkbox hover border
    CHECKBOX_CHECKED = "#4682b4"        # Checkbox checked background

    # Progress bar colors
    PROGRESS_BG = "#252525"             # Progress bar background
    PROGRESS_CHUNK = "#4682b4"          # Progress bar fill

    # Scrollbar colors
    SCROLLBAR_BG = "#252525"            # Scrollbar background
    SCROLLBAR_HANDLE = "#404040"        # Scrollbar handle
    SCROLLBAR_HANDLE_HOVER = "#505050"  # Scrollbar handle hover

    # Combo box colors
    COMBO_ARROW = "#a0a0a0"             # Combo box dropdown arrow

    # Tooltip colors
    TOOLTIP_BG = "#2a2a2a"              # Tooltip background
    TOOLTIP_TEXT = "#ffffff"            # Tooltip text
    TOOLTIP_BORDER = "#555555"          # Tooltip border


class LayoutSpacing:
    """Spacing constants for layouts"""
    MAIN_SPACING = 8
    MAIN_MARGINS = 12
    GROUP_SPACING = 6
    GROUP_MARGINS = (8, 12, 8, 8)
    FIELD_SPACING = 6
    MIN_INPUT_HEIGHT = 24
    MIN_PROGRESS_HEIGHT = 28


class Paths:
    """Default path constants"""
    DEFAULT_WORK_DIR = os.path.expanduser('~/archiso_work')
    DEFAULT_OUTPUT_DIR = os.path.expanduser('~/iso_output')
    CONFIG_DIR = os.path.expanduser('~/.config')
    CONFIG_FILE = os.path.join(CONFIG_DIR, 'iso_builder_gui.json')
    RELENG_PROFILE = '/usr/share/archiso/configs/releng/'
    PACMAN_CACHE = '/var/cache/pacman/pkg/'


class Messages:
    """Message constants"""
    ROOT_REQUIRED = "Error: Must run as root (use sudo)"
    BUILD_SUCCESS = "Build completed successfully!"
    BUILD_FAILED = "Build failed"
    USB_WRITE_SUCCESS = "USB write completed successfully!"
    USB_WRITE_FAILED = "USB write failed"
    USB_WRITING = "Writing to USB..."
    READY = "Ready to build"
    BUILDING = "Building..."


try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QTextEdit, QLineEdit, QFileDialog,
        QProgressBar, QGroupBox, QCheckBox, QMessageBox,
        QListWidget, QListWidgetItem, QComboBox, QDialog
    )
    from PyQt6.QtCore import QThread, pyqtSignal, Qt
    from PyQt6.QtGui import QFont, QTextCursor, QColor
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QTextEdit, QLineEdit, QFileDialog,
            QProgressBar, QGroupBox, QCheckBox, QMessageBox,
            QListWidget, QListWidgetItem, QComboBox, QDialog
        )
        from PyQt5.QtCore import QThread, pyqtSignal, Qt
        from PyQt5.QtGui import QFont, QTextCursor, QColor
        HAS_PYQT5 = True
    except ImportError:
        HAS_PYQT5 = False


# Utility functions


def run_command(
    cmd: List[str],
    check: bool = False,
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command with consistent error handling"""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True
    )


def safe_remove(path: str, emit_func=None) -> bool:
    """Safely remove a file or directory"""
    if os.path.exists(path):
        if emit_func:
            emit_func(f"  - Removing: {path}\n")
        try:
            if os.path.isdir(path):
                subprocess.run(['rm', '-rf', path], check=False)
            else:
                os.remove(path)
            return True
        except Exception:
            return False
    return False


def safe_makedirs(path: str, mode: int = 0o755) -> None:
    """Safely create directories"""
    os.makedirs(path, mode=mode, exist_ok=True)
    os.chmod(path, mode)


def get_qt_dialog_code():
    """Get the correct QDialog code constant for PyQt version"""
    try:
        from PyQt6.QtWidgets import QDialog
        return QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected
    except ImportError:
        from PyQt5.QtWidgets import QDialog
        return QDialog.Accepted, QDialog.Rejected


class ISOBuilderThread(QThread):
    """Thread for building ISO without blocking the UI"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    # Default directories to exclude from ISO
    DEFAULT_EXCLUDE_DIRS = [
        '.cache', 'cache', '.local/share/Trash',
        'Downloads', 'Downloads/*',
        'Templates', 'Public', 'Videos', 'Music',
        '.mozilla/firefox/*/cache2',
        '.config/google-chrome/*/Cache',
        '.config/chromium/*/Cache',
        'snap', '.snap',
        '.docker', 'docker',
        'VirtualBox VMs', '.VirtualBox',
        'tmp', 'temp', '.tmp',
        'node_modules', '__pycache__',
        '.npm', '.yarn', '.gradle', '.m2',
        '.steam', '.local/share/Steam',
        'go/pkg', '.cargo/registry',
    ]
    HOME_COPY_EXCLUDES = [
        '.cache',
        '.local/share/Trash',
        'Downloads',
        '.mozilla/firefox/*/cache2',
        '.config/google-chrome/*/Cache',
        '.config/chromium/*/Cache',
        '.steam',
        '.local/share/Steam',
        'node_modules',
        '.npm',
        '.yarn',
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.process = None

    def _emit(self, message: str) -> None:
        self.output_signal.emit(message)

    def _write_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)

    def _write_script(self, path: str, content: str) -> None:
        self._write_text(path, content)
        os.chmod(path, 0o755)

    def _make_rsync_excludes(self, patterns: List[str]) -> List[str]:
        return [f'--exclude={pattern}' for pattern in patterns]

    def _build_package_list(
        self,
        profile_dir: str,
        packages: List[str],
        excluded_packages: List[str]
    ) -> Tuple[str, List[str], int, set]:
        pkg_file = os.path.join(profile_dir, 'packages.x86_64')
        if not os.path.exists(pkg_file):
            self._emit(
                f"[ERROR] packages.x86_64 not found: {pkg_file}\n"
            )
            raise FileNotFoundError("packages.x86_64 not found")

        with open(pkg_file, 'r', encoding='utf-8') as f:
            base_lines = f.read().splitlines()

        base_packages = []
        for line in base_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                base_packages.append(stripped)

        base_package_set = set(base_packages)

        required_packages = {
            'mkinitcpio',
            'mkinitcpio-archiso',
            'squashfs-tools',
            'linux',
            'linux-firmware',
            'base',
        }

        excluded_set = set(excluded_packages)
        excluded_effective = excluded_set - required_packages
        excluded_ignored = excluded_set & required_packages
        if excluded_ignored:
            self._emit(
                "[WARN] Ignoring exclusions for required packages: "
                f"{', '.join(sorted(excluded_ignored))}\n"
            )

        base_lines_filtered = []
        for line in base_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                if stripped in excluded_effective:
                    continue
            base_lines_filtered.append(line)

        custom_packages = [
            pkg for pkg in packages
            if pkg.strip() and pkg not in excluded_effective
        ]
        custom_packages = [
            pkg for pkg in custom_packages
            if pkg not in base_package_set
        ]
        custom_packages = sorted(set(custom_packages))

        required_missing = sorted(
            required_packages -
            (set(custom_packages) | base_package_set)
        )
        if required_missing:
            self._emit(
                "[INFO] Adding required packages missing from base list: "
                f"{', '.join(required_missing)}\n"
            )

        with open(pkg_file, 'w', encoding='utf-8', newline='') as f:
            if base_lines_filtered:
                f.write("\n".join(base_lines_filtered).rstrip() + "\n")
            if required_missing or custom_packages:
                f.write("\n# Added from current system\n")
                for pkg in required_missing:
                    f.write(f"{pkg}\n")
                for pkg in custom_packages:
                    f.write(f"{pkg}\n")

        with open(pkg_file, 'r', encoding='utf-8') as f:
            pkg_lines = [
                line.strip() for line in f.readlines()
                if line.strip() and not line.strip().startswith('#')
            ]
        pkg_count = len(pkg_lines)
        return pkg_file, pkg_lines, pkg_count, required_packages

    def _write_user_setup_script(
        self,
        airootfs: str,
        iso_username: str,
        user_password: str,
        root_password: str,
        source_user: str = ""
    ) -> None:
        setup_path = os.path.join(airootfs, 'root', 'setup_user.sh')
        lines = [
            "#!/bin/bash",
            "# User setup script for ISO",
            f'USERNAME="{iso_username}"',
            f'USER_PASSWORD="{user_password}"',
            f'ROOT_PASSWORD="{root_password}"',
        ]
        if source_user:
            lines.append(f'SOURCE_USER="{source_user}"')
        lines += [
            "",
            "# Set root password",
            'echo "root:$ROOT_PASSWORD" | chpasswd',
            "",
            "# Create user if it doesn't exist",
            'if ! id -u "$USERNAME" &>/dev/null; then',
            '    useradd -m -s /bin/bash "$USERNAME"',
            '    echo "$USERNAME:$USER_PASSWORD" | chpasswd',
            "    # Add to wheel group for sudo",
            '    usermod -aG wheel "$USERNAME"',
            "fi",
            "",
        ]
        if source_user:
            lines.append('echo "User $USERNAME configured from $SOURCE_USER"')
        else:
            lines.append('echo "User $USERNAME created with blank template"')
        self._write_script(setup_path, "\n".join(lines) + "\n")

    def _write_restore_script(self, airootfs: str, iso_username: str) -> None:
        restore_path = os.path.join(airootfs, 'root', 'restore_user_home.sh')
        content = f"""#!/bin/bash
# Restore user home directory in live environment
USERNAME="{iso_username}"
SOURCE_DIR="/etc/skel/user_{iso_username}"
DEST_HOME="/home/$USERNAME"

if [ -d "$SOURCE_DIR" ] && [ -d "$DEST_HOME" ]; then
    rsync -a "$SOURCE_DIR/" "$DEST_HOME/"
    chown -R "$USERNAME:$USERNAME" "$DEST_HOME"
    echo "User home directory restored for $USERNAME"
fi
"""
        self._write_script(restore_path, content)

    # NEW: this is what actually makes the built ISO boot into GNOME
    def _write_customize_airootfs(self, airootfs: str, iso_username: str) -> None:
        customize_path = os.path.join(airootfs, 'root', 'customize_airootfs.sh')
        content = f"""#!/bin/bash
set -euo pipefail

echo "[customize_airootfs] running..."

# 1) Create user and set passwords (your script)
if [[ -x /root/setup_user.sh ]]; then
  /root/setup_user.sh
fi

# 2) Populate home from saved template (if present)
SRC="/etc/skel/user_{iso_username}"
DST="/home/{iso_username}"
if [[ -d "$SRC" ]]; then
  mkdir -p "$DST"
  rsync -a "$SRC/" "$DST/" || true
  chown -R "{iso_username}:{iso_username}" "$DST" || true
fi

# 3) Enable sudo for wheel
sed -i 's/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers || true

# 4) Networking
systemctl enable NetworkManager.service || true

# 5) GNOME Display Manager + graphical boot
if pacman -Qq gdm &>/dev/null; then
  systemctl enable gdm.service || true

  # Optional: autologin directly into GNOME
  mkdir -p /etc/gdm
  cat > /etc/gdm/custom.conf <<EOF
[daemon]
AutomaticLoginEnable=True
AutomaticLogin={iso_username}

[security]

[xdmcp]

[chooser]

[debug]
EOF
fi

# Ensure we boot to graphical target by default
ln -sf /usr/lib/systemd/system/graphical.target /etc/systemd/system/default.target || true

echo "[customize_airootfs] done."
"""
        self._write_script(customize_path, content)

    def run(self):
        """Run the ISO build process"""
        try:
            # Check if running as root
            if os.geteuid() != 0:
                self.finished_signal.emit(False, Messages.ROOT_REQUIRED)
                return

            work_dir = self.config['work_dir']
            output_dir = self.config['output_dir']
            profile_dir = os.path.join(work_dir, 'profile')
            iso_name = self.config['iso_name']
            iso_label = self.config['iso_label']

            # Thorough cleanup of previous build to avoid conflicts
            self._emit(
                "[INFO] Cleaning up previous build directories and files...\n"
            )
            safe_remove(work_dir, self._emit)
            safe_remove(output_dir, self._emit)

            # Clean up any leftover ISO files in output directory parent
            output_parent = os.path.dirname(output_dir) or output_dir
            if os.path.exists(output_parent):
                iso_files = list(Path(output_parent).glob('*.iso'))
                for iso_file in iso_files:
                    if iso_file.name.startswith(iso_name):
                        safe_remove(str(iso_file), self._emit)

            # Create fresh directories with proper permissions
            safe_makedirs(work_dir)
            safe_makedirs(output_dir)

            self._emit(
                "[INFO] Cleanup complete. Starting fresh build.\n"
            )
            self.progress_signal.emit(10)

            # Check/install archiso
            self._emit("[INFO] Checking for archiso...\n")
            result = run_command(['pacman', '-Q', 'archiso'])
            if result.returncode != 0:
                self._emit("[WARN] Installing archiso...\n")
                run_command(
                    ['pacman', '-Sy', '--noconfirm', 'archiso'], check=True
                )
            self.progress_signal.emit(20)

            # Copy releng profile (ensure clean copy)
            self._emit(
                "[INFO] Copying archiso releng profile...\n"
            )
            # Remove profile directory if it exists to ensure clean copy
            if os.path.exists(profile_dir):
                subprocess.run(['rm', '-rf', profile_dir], check=False)

            # Verify source profile exists
            source_profile = '/usr/share/archiso/configs/releng/'
            if not os.path.exists(source_profile):
                self._emit(
                    f"[ERROR] Source profile not found: {source_profile}\n"
                )
                raise FileNotFoundError(
                    f"Source profile not found: {source_profile}"
                )

            # Copy profile preserving all attributes
            subprocess.run(
                ['cp', '-a', source_profile, profile_dir], check=True
            )

            # Verify critical files exist
            critical_files = [
                'profiledef.sh',
                'pacman.conf',
                'airootfs',
            ]
            for critical_file in critical_files:
                file_path = os.path.join(profile_dir, critical_file)
                if not os.path.exists(file_path):
                    self._emit(
                        f"[ERROR] Critical file missing: {critical_file}\n"
                    )
                    raise FileNotFoundError(
                        f"Critical file missing: {critical_file}"
                    )

            # Ensure profile directory has correct permissions
            run_command(['chmod', '-R', '755', profile_dir], check=False)

            # Copy current system's pacman.conf to include custom repos
            include_custom = self.config.get('include_custom_repos', True)
            if include_custom:
                self._emit(
                    "[INFO] Copying system pacman.conf "
                    "(includes custom repos)...\n"
                )
                pacman_conf_dest = os.path.join(profile_dir, 'pacman.conf')
                run_command(
                    ['cp', '/etc/pacman.conf', pacman_conf_dest], check=True
                )

                # Setup local repository for AUR packages
                self._emit(
                    "[INFO] Setting up local repository for AUR packages...\n"
                )
                local_repo_dir = os.path.join(
                    profile_dir, 'airootfs', 'opt', 'local-repo'
                )
                safe_makedirs(local_repo_dir)

            self.progress_signal.emit(30)

            # Generate package list
            self._emit(
                "[INFO] Generating package list from current system...\n"
            )
            result = run_command(['pacman', '-Qqe'], check=True)
            all_packages = result.stdout.strip().split('\n')

            # Filter packages based on configuration
            include_custom = self.config.get('include_custom_repos', True)

            if include_custom:
                self._emit(
                    "[INFO] Including all packages "
                    "(official + custom repos + AUR)\n"
                )

                # Separate packages by source
                repo_packages = []
                aur_packages = []

                for pkg in all_packages:
                    if not pkg.strip():
                        continue

                    # Check if package is in official/custom repos
                    result = subprocess.run(
                        ['pacman', '-Si', pkg],
                        capture_output=True, text=True
                    )

                    if result.returncode == 0:
                        repo_packages.append(pkg)
                    else:
                        aur_packages.append(pkg)

                # Copy AUR package files to local repo
                successfully_copied_aur = []
                failed_aur_packages = []

                if aur_packages:
                    self._emit(
                        f"[INFO] Copying {len(aur_packages)} AUR packages "
                        "to local repository...\n"
                    )
                    local_repo_dir = os.path.join(
                        profile_dir, 'airootfs', 'opt', 'local-repo'
                    )

                    for pkg in aur_packages:
                        # Get package file from cache
                        result = subprocess.run(
                            ['pacman', '-Ql', pkg],
                            capture_output=True, text=True
                        )

                        if result.returncode == 0:
                            # Try to find the package file in cache
                            pkg_pattern = f"{pkg}-*.pkg.tar.*"
                            pkg_files = list(
                                Path('/var/cache/pacman/pkg/').glob(
                                    pkg_pattern
                                )
                            )

                            if pkg_files:
                                # Copy most recent package file
                                pkg_file = sorted(
                                    pkg_files,
                                    key=lambda p: p.stat().st_mtime
                                )[-1]
                                self._emit(
                                    f"  - Copying {pkg_file.name}\n"
                                )
                                subprocess.run(
                                    ['cp', str(pkg_file), local_repo_dir],
                                    check=False
                                )
                                successfully_copied_aur.append(pkg)
                            else:
                                self._emit(
                                    f"  - [WARN] Package file not found in "
                                    f"cache: {pkg} "
                                    "(will be excluded from ISO)\n"
                                )
                                failed_aur_packages.append(pkg)

                    # Create repository database only if we have packages
                    pkg_files = list(Path(local_repo_dir).glob('*.pkg.tar.*'))
                    if pkg_files:
                        self._emit(
                            "[INFO] Creating local repository database...\n"
                        )
                        repo_db = os.path.join(
                            local_repo_dir, 'local-repo.db.tar.gz'
                        )
                        subprocess.run(
                            ['repo-add', repo_db] +
                            [str(f) for f in pkg_files],
                            check=False
                        )

                        # Add local repo to pacman.conf
                        pacman_conf = os.path.join(profile_dir, 'pacman.conf')
                        with open(pacman_conf, 'a') as f:
                            f.write("\n[local-repo]\n")
                            f.write("SigLevel = Optional TrustAll\n")
                            f.write("Server = file:///opt/local-repo\n")
                    elif aur_packages:
                        self._emit(
                            "[WARN] No AUR package files were successfully "
                            "copied to local repository\n"
                        )

                if failed_aur_packages:
                    self._emit(
                        f"[INFO] Excluding {len(failed_aur_packages)} AUR "
                        "packages that couldn't be found:\n"
                    )
                    for pkg in failed_aur_packages:
                        self._emit(f"  - {pkg}\n")

                excluded_packages = set(
                    self.config.get('excluded_packages', [])
                )
                if excluded_packages:
                    repo_packages = [
                        pkg for pkg in repo_packages
                        if pkg not in excluded_packages
                    ]
                    successfully_copied_aur = [
                        pkg for pkg in successfully_copied_aur
                        if pkg not in excluded_packages
                    ]
                    self._emit(
                        f"[INFO] Excluding {len(excluded_packages)} "
                        "user-specified packages\n"
                    )

                packages = repo_packages + successfully_copied_aur
                self._emit(
                    f"[INFO] Final package list: {len(repo_packages)} repo "
                    f"packages + {len(successfully_copied_aur)} AUR packages "
                    f"= {len(packages)} total\n"
                )
            else:
                self._emit(
                    "[INFO] Filtering packages (official repos only)...\n"
                )
                packages = []
                aur_packages = []
                distro_packages = []

                for pkg in all_packages:
                    if not pkg.strip():
                        continue

                    # Check package repository
                    result = subprocess.run(
                        ['pacman', '-Si', pkg],
                        capture_output=True, text=True
                    )

                    if result.returncode == 0:
                        # Package exists in sync databases (official repos)
                        packages.append(pkg)
                    else:
                        # Check if it's a distro-specific package
                        distro_prefixes = [
                            'cachyos-', 'garuda-', 'endeavour-', 'manjaro-'
                        ]
                        if any(prefix in pkg for prefix in distro_prefixes):
                            distro_packages.append(pkg)
                        else:
                            aur_packages.append(pkg)

                if aur_packages:
                    self._emit(
                        f"[WARN] Skipping {len(aur_packages)} AUR packages\n"
                    )
                if distro_packages:
                    self._emit(
                        f"[WARN] Skipping {len(distro_packages)} "
                        "distro-specific packages\n"
                    )

            # NEW: ensure minimal GNOME + display manager stack exists
            # (If you already have GNOME installed, this does nothing.)
            excluded_packages = set(self.config.get('excluded_packages', []))
            gui_must = [
                "xorg-server",
                "gnome-shell",
                "gnome-session",
                "gdm",
                "networkmanager",
                "mesa",
            ]
            added_gui = []
            for must in gui_must:
                if must in excluded_packages:
                    self._emit(
                        f"[WARN] GUI-required package '{must}' is excluded. "
                        "Live GNOME may not start.\n"
                    )
                    continue
                if must not in packages and must not in all_packages:
                    packages.append(must)
                    added_gui.append(must)
            if added_gui:
                self._emit(
                    "[INFO] Added GUI packages to support GNOME live session: "
                    f"{', '.join(added_gui)}\n"
                )

            excluded_packages_list = self.config.get('excluded_packages', [])
            pkg_file, pkg_lines, pkg_count, required_packages = (
                self._build_package_list(
                    profile_dir,
                    packages,
                    excluded_packages_list
                )
            )

            missing_critical = []
            for crit_pkg in required_packages:
                if crit_pkg not in pkg_lines:
                    missing_critical.append(crit_pkg)

            if missing_critical:
                missing_str = ', '.join(missing_critical)
                self._emit(
                    f"[ERROR] Missing critical packages: {missing_str}\n"
                )
                raise ValueError(
                    f"Package list missing critical packages: {missing_str}"
                )

            if pkg_count < 10:
                self._emit(
                    f"[WARN] Package list is very small ({pkg_count} "
                    "packages). This may cause boot issues.\n"
                )

            self._emit(
                f"[INFO] Package list created with {pkg_count} packages\n"
            )
            self._emit(f"[INFO] Package list file: {pkg_file}\n")
            self.progress_signal.emit(40)

            # Setup directory exclusions for rsync
            exclude_dirs = self.config.get('exclude_dirs', [])
            if exclude_dirs:
                self._emit(
                    f"[INFO] Excluding {len(exclude_dirs)} directory "
                    "patterns...\n"
                )
                for excl in exclude_dirs:
                    self._emit(f"  - {excl}\n")

            # Customize airootfs (airootfs contains customization files
            # that get copied into the built rootfs)
            self._emit(
                "[INFO] Customizing live system root filesystem...\n"
            )
            airootfs = os.path.join(profile_dir, 'airootfs')
            os.makedirs(os.path.join(airootfs, 'etc'), exist_ok=True)

            # Copy NetworkManager config (if exists)
            if os.path.isdir('/etc/NetworkManager'):
                nm_dir = os.path.join(airootfs, 'etc', 'NetworkManager')
                os.makedirs(nm_dir, exist_ok=True)
                subprocess.run(
                    ['cp', '-r', '/etc/NetworkManager/.', nm_dir],
                    stderr=subprocess.DEVNULL, check=False
                )

            # Set hostname
            self._write_text(
                os.path.join(airootfs, 'etc', 'hostname'),
                "archiso-live\n"
            )

            # Configure user account
            user_config = self.config.get('user_config', {})
            iso_username = user_config.get('iso_username', 'archuser')
            user_password = user_config.get('user_password', 'archuser')
            root_password = user_config.get('root_password', 'root')
            copy_from_user = user_config.get('copy_from_user', None)
            use_blank_template = user_config.get('use_blank_template', True)

            if not use_blank_template and copy_from_user:
                self._emit(
                    f"[INFO] Configuring user from: {copy_from_user}\n"
                )
                source_home = os.path.expanduser(f'~{copy_from_user}')
                if not os.path.exists(source_home):
                    self._emit(
                        f"[WARN] Home directory not found: {source_home}\n"
                    )
                    self._emit(
                        "[INFO] Falling back to blank template\n"
                    )
                    use_blank_template = True
                else:
                    self._write_user_setup_script(
                        airootfs,
                        iso_username,
                        user_password,
                        root_password,
                        copy_from_user
                    )

                    dest_home = os.path.join(
                        airootfs, 'etc', 'skel', f'user_{iso_username}'
                    )
                    os.makedirs(dest_home, exist_ok=True)

                    exclude_patterns = self._make_rsync_excludes(
                        self.HOME_COPY_EXCLUDES
                    )

                    self._emit(
                        f"[INFO] Copying home directory from "
                        f"{source_home}...\n"
                    )
                    rsync_cmd = (
                        ['rsync', '-a', '--info=progress2'] +
                        exclude_patterns +
                        [f'{source_home}/', f'{dest_home}/']
                    )
                    result = subprocess.run(
                        rsync_cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        self._emit(
                            "[INFO] Home directory copied successfully\n"
                        )
                    else:
                        self._emit(
                            "[WARN] Some files may not have been copied\n"
                        )

                    self._write_restore_script(airootfs, iso_username)

            if use_blank_template:
                self._emit(
                    f"[INFO] Creating blank user template: {iso_username}\n"
                )
                self._write_user_setup_script(
                    airootfs,
                    iso_username,
                    user_password,
                    root_password
                )

            # NEW: mkarchiso executes customize_airootfs.sh during build
            # This ensures user exists + gdm enabled + graphical target set
            self._write_customize_airootfs(airootfs, iso_username)

            # Write pkg list into ISO for installer to use
            self._write_text(
                os.path.join(airootfs, "root", "pkglist.txt"),
                "\n".join(pkg_lines) + "\n"
            )

            # Create installer script (UEFI)
            os.makedirs(os.path.join(airootfs, 'root'), exist_ok=True)
            install_script = os.path.join(airootfs, 'root', 'install.sh')
            self._write_script(install_script, f"""#!/bin/bash
set -euo pipefail

# Custom Arch installer (UEFI, GPT, EFI+root)
# WARNING: this wipes the selected disk.

ISO_USER="{iso_username}"
USER_PASSWORD="{user_password}"
ROOT_PASSWORD="{root_password}"
HOSTNAME="arch-custom"
TIMEZONE="America/Denver"
LOCALE="en_US.UTF-8"

PKGLIST="/root/pkglist.txt"

echo "========================================"
echo "  Custom Arch Installer (UEFI, GPT)"
echo "========================================"
echo
lsblk -dpno NAME,SIZE,MODEL | sed 's/^/  /'
echo
read -r -p "Install to which disk (e.g. /dev/nvme0n1 or /dev/sda)? " DISK
if [[ ! -b "$DISK" ]]; then
  echo "ERROR: $DISK is not a block device"
  exit 1
fi

echo
echo "ABOUT TO WIPE: $DISK"
read -r -p "Type WIPE to confirm: " CONF
if [[ "$CONF" != "WIPE" ]]; then
  echo "Cancelled."
  exit 0
fi

# Basic sanity: require UEFI for systemd-boot path
if [[ ! -d /sys/firmware/efi/efivars ]]; then
  echo "ERROR: This script expects UEFI boot (no /sys/firmware/efi)."
  echo "If you need BIOS/GRUB support, modify bootloader section."
  exit 1
fi

echo "[1/8] Partitioning..."
sgdisk --zap-all "$DISK"
sgdisk -n 1:0:+512M -t 1:ef00 -c 1:"EFI" "$DISK"
sgdisk -n 2:0:0      -t 2:8300 -c 2:"ROOT" "$DISK"
partprobe "$DISK"
sleep 2

# Handle nvme/mmc partition naming
EFI_PART="${{DISK}}1"
ROOT_PART="${{DISK}}2"
if [[ "$DISK" =~ nvme|mmcblk ]]; then
  EFI_PART="${{DISK}}p1"
  ROOT_PART="${{DISK}}p2"
fi

echo "[2/8] Formatting..."
mkfs.fat -F32 "$EFI_PART"
mkfs.ext4 -F "$ROOT_PART"

echo "[3/8] Mounting..."
mount "$ROOT_PART" /mnt
mkdir -p /mnt/boot
mount "$EFI_PART" /mnt/boot

echo "[4/8] Installing base system..."
if [[ ! -f "$PKGLIST" ]]; then
  echo "WARN: $PKGLIST not found; installing minimal base only."
  pacstrap -K /mnt base linux linux-firmware networkmanager
else
  # Use current live pacman.conf (includes local-repo if you built it)
  pacstrap -K -C /etc/pacman.conf /mnt $(grep -v '^#' "$PKGLIST" | xargs)
fi

echo "[5/8] fstab..."
genfstab -U /mnt >> /mnt/etc/fstab

echo "[6/8] System config (chroot)..."
arch-chroot /mnt /bin/bash -euo pipefail <<CHROOT
echo "root:${{ROOT_PASSWORD}}" | chpasswd

ln -sf "/usr/share/zoneinfo/${{TIMEZONE}}" /etc/localtime
hwclock --systohc

sed -i "s/^#${{LOCALE}}/${{LOCALE}}/" /etc/locale.gen || true
locale-gen
echo "LANG=${{LOCALE}}" > /etc/locale.conf

echo "${{HOSTNAME}}" > /etc/hostname
cat > /etc/hosts <<EOF
127.0.0.1   localhost
::1         localhost
127.0.1.1   ${{HOSTNAME}}.localdomain ${{HOSTNAME}}
EOF

# User
useradd -m -s /bin/bash "${{ISO_USER}}" || true
echo "${{ISO_USER}}:${{USER_PASSWORD}}" | chpasswd
usermod -aG wheel "${{ISO_USER}}"
sed -i 's/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers || true

# Services
systemctl enable NetworkManager.service || true
if pacman -Qq gdm &>/dev/null; then
  systemctl enable gdm.service || true
  mkdir -p /etc/gdm
  cat > /etc/gdm/custom.conf <<EOF
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=${{ISO_USER}}
EOF
fi

# Bootloader: systemd-boot
bootctl install
ROOT_UUID=\\$(blkid -s UUID -o value "{'{'}ROOT_PART{'}'}")
cat > /boot/loader/loader.conf <<EOF
default arch
timeout 3
editor  0
EOF

cat > /boot/loader/entries/arch.conf <<EOF
title   Arch Linux (Custom)
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=\\${{ROOT_UUID}} rw
EOF
CHROOT

echo "[7/8] Done. Unmounting..."
umount -R /mnt

echo "[8/8] Installation complete."
echo "Reboot when ready."
""")
            self.progress_signal.emit(50)

            # Create custom build hook to exclude directories
            if exclude_dirs:
                self._emit(
                    "[INFO] Creating custom build hook for exclusions...\n"
                )
                hooks_dir = os.path.join(
                    profile_dir, 'airootfs', 'etc', 'initcpio', 'hooks'
                )
                os.makedirs(hooks_dir, exist_ok=True)

                exclude_file = os.path.join(profile_dir, 'exclude_dirs.txt')
                exclude_text = "\n".join(exclude_dirs).rstrip() + "\n"
                self._write_text(exclude_file, exclude_text)

            # Customize profiledef.sh - preserve original and only update
            # what we need
            self._emit(
                "[INFO] Customizing profile definition...\n"
            )
            profiledef = os.path.join(profile_dir, 'profiledef.sh')
            original_profiledef = (
                '/usr/share/archiso/configs/releng/profiledef.sh'
            )

            if not os.path.exists(profiledef):
                self._emit(
                    "[ERROR] profiledef.sh not found in profile!\n"
                )
                raise FileNotFoundError("profiledef.sh not found")

            if os.path.exists(original_profiledef):
                with open(original_profiledef, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                with open(profiledef, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            updated_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('iso_name='):
                    updated_lines.append(f'iso_name="{iso_name}"\n')
                elif stripped.startswith('iso_label='):
                    updated_lines.append(f'iso_label="{iso_label}"\n')
                elif stripped.startswith('iso_publisher='):
                    updated_lines.append('iso_publisher="Custom Arch Linux"\n')
                elif stripped.startswith('iso_application='):
                    updated_lines.append(
                        'iso_application="Custom Arch Linux Live/Install"\n'
                    )
                elif stripped.startswith('pacman_conf='):
                    updated_lines.append('pacman_conf="pacman.conf"\n')
                else:
                    updated_lines.append(line)

            with open(profiledef, 'w', encoding='utf-8', newline='') as f:
                f.writelines(updated_lines)

            os.chmod(profiledef, 0o755)

            if (not os.path.exists(profiledef) or
                    os.path.getsize(profiledef) == 0):
                self._emit(
                    "[ERROR] Failed to write profiledef.sh!\n"
                )
                raise IOError("profiledef.sh write failed")
            self.progress_signal.emit(60)

            # Build the ISO
            self._emit(
                "[INFO] Building ISO (this will take a while)...\n"
            )
            self._emit(
                "[INFO] Note: Some mkinitcpio and GRUB errors during "
                "package installation are expected and non-fatal.\n"
            )
            self._emit("=" * 60 + "\n")

            build_dir = os.path.join(work_dir, 'build')
            self.process = subprocess.Popen(
                [
                    'mkarchiso', '-v', '-w', build_dir, '-o',
                    output_dir, profile_dir
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            error_detected = False
            non_fatal_patterns = [
                "/boot/grub/grub.cfg.new: no such file or directory",
                "running in chroot",
                "skipped: running in chroot",
                ("errors were encountered during the build. "
                 "the image may not be complete"),
            ]

            for line in self.process.stdout:
                self._emit(line)
                line_lower = line.lower()

                is_non_fatal = any(
                    pattern in line_lower for pattern in non_fatal_patterns
                )

                if not is_non_fatal and any(
                    keyword in line_lower for keyword in
                    ['error:', 'failed', 'fatal:', 'cannot', 'unable']
                ):
                    if 'warning' not in line_lower:
                        error_detected = True
                        self._emit(f"[ERROR DETECTED] {line}")

                if ('squashfs' in line_lower and
                        ('creating' in line_lower or 'created' in line_lower)):
                    self.progress_signal.emit(80)

                elif 'iso' in line_lower and 'creating' in line_lower:
                    self.progress_signal.emit(90)
                elif 'packages' in line_lower and 'installing' in line_lower:
                    self.progress_signal.emit(50)
                elif 'building' in line_lower and 'airootfs' in line_lower:
                    self.progress_signal.emit(60)

            self.process.wait()

            self.progress_signal.emit(100)
            iso_files = list(Path(output_dir).glob('*.iso'))

            if iso_files:
                iso_file = iso_files[0]
                size = iso_file.stat().st_size / (1024**3)
                self._emit("\n" + "=" * 60 + "\n")
                if self.process.returncode == 0:
                    self._emit("[SUCCESS] ISO build completed!\n")
                else:
                    self._emit(
                        "[WARNING] Build completed with warnings/errors, "
                        "but ISO was created.\n"
                    )
                self._emit(f"[INFO] ISO created: {iso_file}\n")
                self._emit(f"[INFO] Size: {size:.2f} GB\n")

                self._emit(
                    "\n[INFO] Verifying build artifacts...\n"
                )
                squashfs_found = False

                squashfs_files = list(Path(build_dir).rglob('*.squashfs'))
                if not squashfs_files:
                    arch_dir = os.path.join(output_dir, 'arch')
                    if os.path.exists(arch_dir):
                        squashfs_files = list(
                            Path(arch_dir).rglob('*.squashfs')
                        )

                if squashfs_files:
                    squashfs_size = (
                        squashfs_files[0].stat().st_size / (1024**3)
                    )
                    self._emit(
                        f"[INFO] Squashfs found in build dir: "
                        f"{squashfs_files[0]} ({squashfs_size:.2f} GB)\n"
                    )
                    squashfs_found = True

                    if squashfs_size < 0.1:
                        self._emit(
                            "[WARN] Squashfs file is very small - may be "
                            "corrupted or empty!\n"
                        )
                else:
                    self._emit(
                        "[INFO] Squashfs not found in build directory. "
                        "Checking ISO contents...\n"
                    )
                    if size > 1.0:
                        self._emit(
                            "[INFO] ISO size is reasonable. Squashfs is "
                            "likely embedded in the ISO (normal behavior).\n"
                        )
                        squashfs_found = True
                    else:
                        self._emit(
                            "[WARN] ISO size is suspiciously small. "
                            "Squashfs may be missing.\n"
                        )

                self._emit("[INFO] Verifying ISO structure...\n")
                try:
                    result = run_command(['file', str(iso_file)], check=False)
                    if result.returncode == 0:
                        self._emit(
                            f"[INFO] ISO file type: "
                            f"{result.stdout.strip()}\n"
                        )
                        is_valid = (
                            'ISO 9660' in result.stdout or
                            'bootable' in result.stdout.lower()
                        )
                        if is_valid:
                            self._emit(
                                "[INFO] ISO appears to be a valid bootable "
                                "image.\n"
                            )
                except Exception:
                    pass

                if not squashfs_found and size < 1.0:
                    self._emit(
                        "[ERROR] Build verification failed: ISO is too small "
                        "and squashfs not found.\n"
                    )
                    if error_detected:
                        self._emit(
                            "[ERROR] Errors were detected in mkarchiso output "
                            "(see above)\n"
                        )
                    self.finished_signal.emit(
                        False, "ISO verification failed - may not boot"
                    )
                    return

                self.finished_signal.emit(True, str(iso_file))
            else:
                if self.process.returncode == 0:
                    self._emit(
                        "\n[ERROR] Build process completed but ISO file "
                        "not found!\n"
                    )
                    self._emit(
                        f"[ERROR] Check build directory: {build_dir}\n"
                    )
                    self._emit(
                        f"[ERROR] Check output directory: {output_dir}\n"
                    )
                    self.finished_signal.emit(
                        False, "ISO file not found in output directory"
                    )
                else:
                    self._emit(
                        f"\n[ERROR] ISO build failed! "
                        f"(exit code: {self.process.returncode})\n"
                    )
                    self.finished_signal.emit(
                        False,
                        f"Build process failed with exit code "
                        f"{self.process.returncode}"
                    )

        except Exception as e:
            self._emit(f"\n[ERROR] {str(e)}\n")
            self.finished_signal.emit(False, str(e))

    def stop(self):
        """Stop the build process"""
        if self.process:
            self.process.terminate()


class USBWriterThread(QThread):
    """Thread for writing ISO to USB drive without blocking the UI"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, iso_path, device):
        super().__init__()
        self.iso_path = iso_path
        self.device = device
        self.process = None

    def _emit(self, message: str) -> None:
        self.output_signal.emit(message)

    def run(self):
        """Write ISO to USB device"""
        try:
            if os.geteuid() != 0:
                self.finished_signal.emit(
                    False,
                    "Error: Must run as root (use sudo) to write to USB"
                )
                return

            if not os.path.exists(self.device):
                self.finished_signal.emit(
                    False, f"Error: Device {self.device} does not exist"
                )
                return

            iso_size = os.path.getsize(self.iso_path)
            iso_size_gb = iso_size / (1024**3)

            self._emit(
                f"\n[INFO] Writing ISO to USB device: {self.device}\n"
            )
            self._emit(
                f"[INFO] ISO size: {iso_size_gb:.2f} GB\n"
            )
            self._emit(
                f"[WARN] This will erase all data on {self.device}!\n"
            )
            self._emit(
                "[INFO] Writing... (this may take several minutes)\n"
            )
            self.progress_signal.emit(10)

            self._emit(
                "[INFO] Unmounting device partitions...\n"
            )
            result = run_command(
                ['umount', '-f', self.device + '*'], check=False
            )
            if result.returncode != 0:
                for part_num in range(1, 10):
                    part = f"{self.device}{part_num}"
                    if os.path.exists(part):
                        run_command(['umount', '-f', part], check=False)

            self.progress_signal.emit(20)

            self._emit(
                f"[INFO] Writing ISO to {self.device}...\n"
            )
            self.process = subprocess.Popen(
                [
                    'dd', f'if={self.iso_path}', f'of={self.device}',
                    'bs=4M', 'status=progress', 'oflag=sync'
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in self.process.stdout:
                self._emit(line)
                if 'records in' in line or 'records out' in line:
                    self.progress_signal.emit(60)
                elif 'copied' in line.lower():
                    self.progress_signal.emit(80)

            self.process.wait()

            if self.process.returncode == 0:
                self.progress_signal.emit(100)
                self._emit(
                    "\n[SUCCESS] ISO written to USB device successfully!\n"
                )
                self._emit(f"[INFO] Device: {self.device}\n")
                self._emit(
                    "[INFO] You can now boot from this USB drive.\n"
                )
                self.finished_signal.emit(
                    True, f"ISO written to {self.device}"
                )
            else:
                self._emit(
                    "\n[ERROR] Failed to write ISO to USB device!\n"
                )
                self.finished_signal.emit(False, "USB write process failed")

        except Exception as e:
            self._emit(f"\n[ERROR] {str(e)}\n")
            self.finished_signal.emit(False, str(e))

    def stop(self):
        """Stop the write process"""
        if self.process:
            self.process.terminate()


class ExclusionsDialog(QDialog):
    """Dialog for managing directory exclusions"""

    def __init__(self, parent, exclude_items):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('Directory Exclusions')
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Info label
        info_label = QLabel(
            'Select directories/patterns to exclude from the ISO '
            '(reduces size):'
        )
        layout.addWidget(info_label)

        # Exclusions list
        self.exclude_list = QListWidget()
        self.exclude_list.setMinimumHeight(300)

        # Add items (exclude_items can be dict or list)
        if isinstance(exclude_items, dict):
            for excl_dir, checked in exclude_items.items():
                item = QListWidgetItem(excl_dir)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                state = (Qt.CheckState.Checked if checked
                         else Qt.CheckState.Unchecked)
                item.setCheckState(state)
                self.exclude_list.addItem(item)
        else:
            for excl_dir in exclude_items:
                item = QListWidgetItem(excl_dir)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.exclude_list.addItem(item)

        layout.addWidget(self.exclude_list)

        # Buttons for managing exclusions
        btn_layout = QHBoxLayout()

        add_btn = QPushButton('Add Custom...')
        add_btn.clicked.connect(self.add_custom_exclusion)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton('Remove Selected')
        remove_btn.clicked.connect(self.remove_exclusion)
        btn_layout.addWidget(remove_btn)

        select_all_btn = QPushButton('Select All')
        select_all_btn.clicked.connect(self.select_all_exclusions)
        btn_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton('Deselect All')
        deselect_all_btn.clicked.connect(self.deselect_all_exclusions)
        btn_layout.addWidget(deselect_all_btn)

        layout.addLayout(btn_layout)

        # Dialog buttons
        dialog_btn_layout = QHBoxLayout()
        dialog_btn_layout.addStretch()

        ok_btn = QPushButton('OK')
        ok_btn.clicked.connect(self.accept)
        dialog_btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_layout.addWidget(cancel_btn)

        layout.addLayout(dialog_btn_layout)

    def add_custom_exclusion(self):
        """Add a custom directory exclusion pattern"""
        try:
            from PyQt6.QtWidgets import QInputDialog
        except ImportError:
            from PyQt5.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            self,
            'Add Custom Exclusion',
            'Enter directory pattern to exclude '
            '(e.g., ".cache", "Downloads/*"):'
        )
        if ok and text.strip():
            # Check if it already exists
            for i in range(self.exclude_list.count()):
                if self.exclude_list.item(i).text() == text.strip():
                    QMessageBox.warning(
                        self, 'Duplicate',
                        'This exclusion pattern already exists.'
                    )
                    return

            item = QListWidgetItem(text.strip())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.exclude_list.addItem(item)

    def remove_exclusion(self):
        """Remove selected exclusion"""
        current_row = self.exclude_list.currentRow()
        if current_row >= 0:
            self.exclude_list.takeItem(current_row)

    def select_all_exclusions(self):
        """Check all exclusion items"""
        for i in range(self.exclude_list.count()):
            self.exclude_list.item(i).setCheckState(Qt.CheckState.Checked)

    def deselect_all_exclusions(self):
        """Uncheck all exclusion items"""
        for i in range(self.exclude_list.count()):
            self.exclude_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def get_selected_exclusions(self):
        """Get list of checked exclusion patterns"""
        exclusions = []
        for i in range(self.exclude_list.count()):
            item = self.exclude_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                exclusions.append(item.text())
        return exclusions

    def get_all_exclusions(self):
        """Get all exclusion patterns as dict {pattern: checked}"""
        exclusions = {}
        for i in range(self.exclude_list.count()):
            item = self.exclude_list.item(i)
            checked = (
                item.checkState() == Qt.CheckState.Checked
            )
            exclusions[item.text()] = checked
        return exclusions


class PackageLoaderThread(QThread):
    """Thread for loading packages without blocking the UI"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list, set)

    def run(self):
        """Load all packages from the system and identify AUR packages"""
        all_packages = []
        aur_packages = set()
        try:
            # Get all installed packages
            self.progress_signal.emit("Loading package list...")
            result = run_command(['pacman', '-Qqe'], check=True)
            package_names = [
                pkg.strip() for pkg in result.stdout.strip().split('\n')
                if pkg.strip()
            ]
            total = len(package_names)
            self.progress_signal.emit(
                f"Checking {total} packages for AUR status..."
            )

            for idx, pkg in enumerate(package_names):
                # Update progress every 50 packages
                if idx % 50 == 0:
                    self.progress_signal.emit(
                        f"Checking packages... ({idx}/{total})"
                    )

                # Check if package is in official/custom repos
                result = subprocess.run(
                    ['pacman', '-Si', pkg],
                    capture_output=True, text=True
                )

                if result.returncode == 0:
                    # Package is in repos
                    all_packages.append({
                        'name': pkg,
                        'is_aur': False
                    })
                else:
                    # Package is likely AUR
                    all_packages.append({
                        'name': pkg,
                        'is_aur': True
                    })
                    aur_packages.add(pkg)

            # Sort packages: AUR first, then alphabetically
            all_packages.sort(
                key=lambda x: (not x['is_aur'], x['name'].lower())
            )
            self.progress_signal.emit("Package loading complete!")
            self.finished_signal.emit(all_packages, aur_packages)
        except Exception as e:
            self.progress_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit([], set())


class PackageSelectionDialog(QDialog):
    """Dialog for managing package exclusions"""

    def __init__(self, parent, excluded_packages=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('Package Selection')
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Info label
        info_label = QLabel(
            'Select packages to exclude from the ISO. '
            'AUR packages are highlighted.'
        )
        layout.addWidget(info_label)

        # Loading status label
        self.loading_label = QLabel('Loading packages...')
        self.loading_label.setStyleSheet(
            f'QLabel {{ color: {Colors.INFO}; font-weight: 600; }}'
        )
        layout.addWidget(self.loading_label)

        # Search/filter box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Search:'))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            'Filter packages by name...'
        )
        self.search_input.textChanged.connect(self.filter_packages)
        self.search_input.setEnabled(False)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        self.package_list = QListWidget()
        self.package_list.setMinimumHeight(400)
        layout.addWidget(self.package_list)

        self.all_packages = []
        self.aur_packages = set()
        self.excluded_packages = excluded_packages or []

        self.loader_thread = None
        self.start_loading_packages()

        btn_layout = QHBoxLayout()

        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.clicked.connect(self.select_all_packages)
        self.select_all_btn.setEnabled(False)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('Deselect All')
        self.deselect_all_btn.clicked.connect(self.deselect_all_packages)
        self.deselect_all_btn.setEnabled(False)
        btn_layout.addWidget(self.deselect_all_btn)

        self.select_aur_btn = QPushButton('Select All AUR')
        self.select_aur_btn.clicked.connect(self.select_all_aur)
        self.select_aur_btn.setEnabled(False)
        btn_layout.addWidget(self.select_aur_btn)

        self.deselect_aur_btn = QPushButton('Deselect All AUR')
        self.deselect_aur_btn.clicked.connect(self.deselect_all_aur)
        self.deselect_aur_btn.setEnabled(False)
        btn_layout.addWidget(self.deselect_aur_btn)

        layout.addLayout(btn_layout)

        self.status_label = QLabel('')
        layout.addWidget(self.status_label)

        dialog_btn_layout = QHBoxLayout()
        dialog_btn_layout.addStretch()

        self.ok_btn = QPushButton('OK')
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        dialog_btn_layout.addWidget(self.ok_btn)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_layout.addWidget(cancel_btn)

        layout.addLayout(dialog_btn_layout)

    def start_loading_packages(self):
        """Start loading packages in a background thread"""
        self.loader_thread = PackageLoaderThread()
        self.loader_thread.progress_signal.connect(self.on_loading_progress)
        self.loader_thread.finished_signal.connect(self.on_loading_finished)
        self.loader_thread.start()

    def on_loading_progress(self, message):
        """Update loading progress message"""
        self.loading_label.setText(message)

    def on_loading_finished(self, all_packages, aur_packages):
        """Handle package loading completion"""
        self.all_packages = all_packages
        self.aur_packages = aur_packages

        if not all_packages:
            self.loading_label.setText(
                "Error: Failed to load packages"
            )
            self.loading_label.setStyleSheet(
                f'QLabel {{ color: {Colors.ERROR}; font-weight: 600; }}'
            )
            return

        # Hide loading label
        self.loading_label.hide()

        # Enable UI elements
        self.search_input.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)
        self.select_aur_btn.setEnabled(True)
        self.deselect_aur_btn.setEnabled(True)
        self.ok_btn.setEnabled(True)

        # Populate list
        self.populate_list()

        # Set initial exclusions
        if self.excluded_packages:
            for pkg in self.excluded_packages:
                for i in range(self.package_list.count()):
                    item = self.package_list.item(i)
                    if item.text() == pkg:
                        item.setCheckState(Qt.CheckState.Checked)
                        break

        self.update_status()

    def closeEvent(self, event):
        """Clean up thread when dialog is closed"""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.terminate()
            self.loader_thread.wait()
        event.accept()

    def populate_list(self, filter_text=''):
        """Populate the package list with packages"""
        self.package_list.clear()
        filter_lower = filter_text.lower()

        for pkg_info in self.all_packages:
            pkg_name = pkg_info['name']
            if filter_text and filter_lower not in pkg_name.lower():
                continue

            item = QListWidgetItem(pkg_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

            # Highlight AUR packages
            if pkg_info['is_aur']:
                item.setForeground(QColor(Colors.INFO))
                item.setToolTip('AUR package')

            self.package_list.addItem(item)

    def filter_packages(self, text):
        """Filter packages based on search text"""
        self.populate_list(text)
        self.update_status()

    def select_all_packages(self):
        """Check all packages"""
        for i in range(self.package_list.count()):
            self.package_list.item(i).setCheckState(
                Qt.CheckState.Checked
            )
        self.update_status()

    def deselect_all_packages(self):
        """Uncheck all packages"""
        for i in range(self.package_list.count()):
            self.package_list.item(i).setCheckState(
                Qt.CheckState.Unchecked
            )
        self.update_status()

    def select_all_aur(self):
        """Check all AUR packages"""
        for i in range(self.package_list.count()):
            item = self.package_list.item(i)
            if item.text() in self.aur_packages:
                item.setCheckState(Qt.CheckState.Checked)
        self.update_status()

    def deselect_all_aur(self):
        """Uncheck all AUR packages"""
        for i in range(self.package_list.count()):
            item = self.package_list.item(i)
            if item.text() in self.aur_packages:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.update_status()

    def update_status(self):
        """Update status label with package counts"""
        total = self.package_list.count()
        excluded = sum(
            1 for i in range(self.package_list.count())
            if self.package_list.item(i).checkState() ==
            Qt.CheckState.Checked
        )
        aur_excluded = sum(
            1 for i in range(self.package_list.count())
            if (self.package_list.item(i).checkState() ==
                Qt.CheckState.Checked and
                self.package_list.item(i).text() in self.aur_packages)
        )
        self.status_label.setText(
            f'Total packages: {total} | '
            f'Excluded: {excluded} ({aur_excluded} AUR)'
        )

    def get_excluded_packages(self):
        """Get list of checked (excluded) packages"""
        excluded = []
        for i in range(self.package_list.count()):
            item = self.package_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                excluded.append(item.text())
        return excluded


class ISOBuilderGUI(QMainWindow):
    """Main GUI window for ISO builder"""

    CONFIG_FILE = Paths.CONFIG_FILE

    def __init__(self):
        super().__init__()
        self.builder_thread = None
        self.usb_writer_thread = None
        self.last_iso_path = None
        self.load_settings()
        self.init_ui()

    # Helper methods for DRY
    def set_status(self, text: str, color: str = None) -> None:
        """Set status label text and optional color"""
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(
                f'QLabel {{ color: {color}; font-weight: 600; }}'
            )

    def create_group_layout(
        self, spacing: int = None, margins: Tuple = None
    ) -> QVBoxLayout:
        """Create a standardized group box layout"""
        layout = QVBoxLayout()
        layout.setSpacing(spacing or LayoutSpacing.GROUP_SPACING)
        if margins:
            layout.setContentsMargins(*margins)
        else:
            layout.setContentsMargins(*LayoutSpacing.GROUP_MARGINS)
        return layout

    def create_field_layout(self, spacing: int = None) -> QHBoxLayout:
        """Create a standardized field layout"""
        layout = QHBoxLayout()
        layout.setSpacing(spacing or LayoutSpacing.FIELD_SPACING)
        return layout

    def create_input_field(
        self, default_value: str = "", min_height: int = None
    ) -> QLineEdit:
        """Create a standardized input field"""
        field = QLineEdit(default_value)
        field.setMinimumHeight(min_height or LayoutSpacing.MIN_INPUT_HEIGHT)
        return field

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('Arch Linux ISO Builder')
        self.setMinimumSize(900, 850)
        # Set initial size larger than minimum for better initial
        # appearance
        self.resize(900, 950)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(LayoutSpacing.MAIN_SPACING * 2)
        main_layout.setContentsMargins(
            LayoutSpacing.MAIN_MARGINS,
            LayoutSpacing.MAIN_MARGINS,
            LayoutSpacing.MAIN_MARGINS,
            LayoutSpacing.MAIN_MARGINS
        )

        # Configuration Group
        config_group = QGroupBox('Configuration')
        config_layout = self.create_group_layout()

        # ISO Name
        iso_name_layout = self.create_field_layout()
        iso_name_layout.addWidget(QLabel('ISO Name:'))
        self.iso_name_input = self.create_input_field('custom-arch-live')
        iso_name_layout.addWidget(self.iso_name_input)
        config_layout.addLayout(iso_name_layout)

        # Include custom repo packages
        self.include_custom_repos = QCheckBox(
            'Include custom repository packages (AUR, etc.)'
        )
        self.include_custom_repos.setChecked(True)
        self.include_custom_repos.setContentsMargins(0, 3, 0, 3)
        config_layout.addWidget(self.include_custom_repos)

        # Work Directory
        work_dir_layout = self.create_field_layout()
        work_dir_layout.addWidget(QLabel('Work Directory:'))
        self.work_dir_input = self.create_input_field(
            self.settings.get('work_dir', Paths.DEFAULT_WORK_DIR)
        )
        self.work_dir_input.textChanged.connect(self.save_settings)
        work_dir_layout.addWidget(self.work_dir_input)
        work_dir_btn = QPushButton('Browse...')
        work_dir_btn.clicked.connect(self.browse_work_dir)
        work_dir_layout.addWidget(work_dir_btn)
        config_layout.addLayout(work_dir_layout)

        # Output Directory
        output_dir_layout = self.create_field_layout()
        output_dir_layout.addWidget(QLabel('Output Directory:'))
        self.output_dir_input = self.create_input_field(
            self.settings.get('output_dir', Paths.DEFAULT_OUTPUT_DIR)
        )
        self.output_dir_input.textChanged.connect(self.save_settings)
        output_dir_layout.addWidget(self.output_dir_input)
        output_dir_btn = QPushButton('Browse...')
        output_dir_btn.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(output_dir_btn)
        config_layout.addLayout(output_dir_layout)

        # Directory Exclusions and Package Selection Buttons
        buttons_layout = QHBoxLayout()
        exclude_btn = QPushButton(
            'Configure Directory Exclusions...'
        )
        exclude_btn.clicked.connect(self.show_exclusions_dialog)
        buttons_layout.addWidget(exclude_btn)

        package_btn = QPushButton('Select Packages to Exclude...')
        package_btn.clicked.connect(self.show_package_selection_dialog)
        buttons_layout.addWidget(package_btn)

        buttons_layout.addStretch()
        config_layout.addLayout(buttons_layout)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # User Configuration - Separate Group
        user_group = QGroupBox('User Configuration')
        user_config_layout = self.create_group_layout(spacing=10)

        # User template option
        self.user_template_blank = QCheckBox(
            'Create blank user template (default)'
        )
        self.user_template_blank.setChecked(
            self.settings.get('user_template_blank', True)
        )
        self.user_template_blank.stateChanged.connect(
            self.on_user_template_changed
        )
        self.user_template_blank.stateChanged.connect(self.save_settings)
        user_config_layout.addWidget(self.user_template_blank)

        # Copy from user option
        copy_user_layout = QHBoxLayout()
        self.user_template_copy = QCheckBox('Copy home from user:')
        self.user_template_copy.setChecked(
            self.settings.get('user_template_copy', False)
        )
        self.user_template_copy.stateChanged.connect(
            self.on_user_template_changed
        )
        self.user_template_copy.stateChanged.connect(self.save_settings)
        copy_user_layout.addWidget(self.user_template_copy)

        # User selection combo
        self.user_source_combo = QComboBox()
        self.user_source_combo.setMinimumWidth(200)
        self.user_source_combo.setEnabled(False)
        self.populate_user_list()
        copy_user_layout.addWidget(self.user_source_combo)

        # Refresh users button
        refresh_users_btn = QPushButton('Refresh')
        refresh_users_btn.clicked.connect(self.populate_user_list)
        refresh_users_btn.setEnabled(False)
        self.refresh_users_btn = refresh_users_btn
        copy_user_layout.addWidget(refresh_users_btn)

        copy_user_layout.addStretch()
        user_config_layout.addLayout(copy_user_layout)

        # Username, User Password, and Root Password in 3 columns
        credentials_layout = QHBoxLayout()
        credentials_layout.setSpacing(LayoutSpacing.FIELD_SPACING)

        # ISO username column
        username_col = QVBoxLayout()
        username_col.addWidget(QLabel('ISO Username:'))
        self.iso_username_input = self.create_input_field('archuser')
        self.iso_username_input.setText(
            self.settings.get('iso_username', 'archuser')
        )
        self.iso_username_input.textChanged.connect(self.save_settings)
        self.iso_username_input.setEnabled(False)
        username_col.addWidget(self.iso_username_input)
        credentials_layout.addLayout(username_col)

        # User password column
        user_password_col = QVBoxLayout()
        user_password_col.addWidget(QLabel('User Password:'))
        self.user_password_input = QLineEdit()
        if HAS_PYQT6:
            self.user_password_input.setEchoMode(
                QLineEdit.EchoMode.Password
            )
        else:
            self.user_password_input.setEchoMode(QLineEdit.Password)
        self.user_password_input.setMinimumHeight(
            LayoutSpacing.MIN_INPUT_HEIGHT
        )
        self.user_password_input.setText(
            self.settings.get('user_password', 'archuser')
        )
        self.user_password_input.textChanged.connect(self.save_settings)
        user_password_col.addWidget(self.user_password_input)
        credentials_layout.addLayout(user_password_col)

        # Root password column
        root_password_col = QVBoxLayout()
        root_password_col.addWidget(QLabel('Root Password:'))
        self.root_password_input = QLineEdit()
        if HAS_PYQT6:
            self.root_password_input.setEchoMode(
                QLineEdit.EchoMode.Password
            )
        else:
            self.root_password_input.setEchoMode(QLineEdit.Password)
        self.root_password_input.setMinimumHeight(
            LayoutSpacing.MIN_INPUT_HEIGHT
        )
        self.root_password_input.setText(
            self.settings.get('root_password', 'root')
        )
        self.root_password_input.textChanged.connect(self.save_settings)
        root_password_col.addWidget(self.root_password_input)
        credentials_layout.addLayout(root_password_col)

        user_config_layout.addLayout(credentials_layout)

        # Update user template widget states based on settings
        # This ensures widgets are enabled/disabled correctly on startup
        if self.user_template_copy.isChecked():
            self.on_user_template_changed(
                Qt.CheckState.Checked.value if HAS_PYQT6 else 2
            )
        else:
            # Ensure blank template widgets are in correct state
            if not self.user_template_blank.isChecked():
                self.user_template_blank.setChecked(True)

        user_group.setLayout(user_config_layout)
        main_layout.addWidget(user_group)

        # USB Write Group
        usb_group = QGroupBox('Write to USB Drive (Optional)')
        usb_layout = self.create_group_layout()

        self.write_to_usb = QCheckBox(
            'Write ISO to USB drive after build completes'
        )
        self.write_to_usb.setChecked(self.settings.get('write_to_usb', False))
        self.write_to_usb.stateChanged.connect(self.on_usb_write_toggled)
        self.write_to_usb.stateChanged.connect(self.save_settings)
        usb_layout.addWidget(self.write_to_usb)

        # USB Device Selection
        usb_device_layout = QHBoxLayout()
        usb_device_layout.setSpacing(10)
        usb_device_layout.addWidget(QLabel('USB Device:'))
        self.usb_device_combo = QComboBox()
        self.usb_device_combo.setMinimumWidth(300)
        self.usb_device_combo.setMinimumHeight(32)
        usb_device_layout.addWidget(self.usb_device_combo)

        refresh_usb_btn = QPushButton('Refresh')
        refresh_usb_btn.clicked.connect(self.refresh_usb_devices)
        usb_device_layout.addWidget(refresh_usb_btn)

        usb_layout.addLayout(usb_device_layout)

        usb_warning = QLabel(
            '⚠️  WARNING: This will erase all data on the selected USB '
            'device!'
        )
        usb_warning.setStyleSheet(
            f'QLabel {{ color: {Colors.WARNING}; font-weight: 600; }}'
        )
        usb_layout.addWidget(usb_warning)

        usb_group.setLayout(usb_layout)
        main_layout.addWidget(usb_group)

        # Store refresh button reference for later
        self.refresh_usb_btn = refresh_usb_btn

        # Load USB devices
        self.refresh_usb_devices()

        # Update widget states based on checkbox settings
        # This ensures widgets are enabled/disabled correctly on startup
        if self.write_to_usb.isChecked():
            self.on_usb_write_toggled(
                Qt.CheckState.Checked.value if HAS_PYQT6 else 2
            )
        else:
            self.usb_device_combo.setEnabled(False)
            self.refresh_usb_btn.setEnabled(False)

        # Initialize exclusions list (will be managed in dialog)
        # Store as dict: {pattern: checked}
        self.exclude_list_items = {}
        for excl_dir in ISOBuilderThread.DEFAULT_EXCLUDE_DIRS:
            self.exclude_list_items[excl_dir] = True

        # Initialize excluded packages list
        self.excluded_packages = self.settings.get('excluded_packages', [])

        # Progress Group
        progress_group = QGroupBox('Build Progress')
        progress_layout = self.create_group_layout(spacing=6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(LayoutSpacing.MIN_PROGRESS_HEIGHT)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(Messages.READY)
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # Output Log
        log_group = QGroupBox('Build Log')
        log_layout = self.create_group_layout(spacing=0)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont('Monospace', 8))
        log_layout.addWidget(self.log_output)

        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.clear_btn = QPushButton('Clear Log')
        self.clear_btn.clicked.connect(self.log_output.clear)
        button_layout.addWidget(self.clear_btn)

        self.stop_btn = QPushButton('Stop Build')
        self.stop_btn.setObjectName('stopButton')
        self.stop_btn.clicked.connect(self.stop_build)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        self.build_btn = QPushButton('Build ISO')
        self.build_btn.setObjectName('buildButton')
        self.build_btn.clicked.connect(self.start_build)
        # Button enabled state will be set based on root check below
        button_layout.addWidget(self.build_btn)

        main_layout.addLayout(button_layout)

        # Check if running as root
        is_root = os.geteuid() == 0
        if not is_root:
            warning = QLabel(
                '⚠️  Warning: This application must be run with sudo '
                'privileges'
            )
            warning.setStyleSheet(
                f'QLabel {{ color: {Colors.WARNING}; font-weight: 600; }}'
            )
            warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.insertWidget(1, warning)
            self.build_btn.setEnabled(False)
            # Log the issue
            import getpass
            current_user = getpass.getuser()
            self.log_output.append(
                f"[INFO] Running as user: {current_user} "
                f"(UID: {os.geteuid()})\n"
            )
            self.log_output.append(
                "[INFO] Please run with: sudo ./make_arch_iso_gui.py\n"
            )
        else:
            # Explicitly enable button when running as root
            self.build_btn.setEnabled(True)
            self.log_output.append(
                "[INFO] Running as root - Build ISO button enabled\n"
            )

    def load_settings(self):
        """Load persisted settings from config file"""
        self.settings = {}
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    self.settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.settings = {}

    def save_settings(self):
        """Save current settings to config file"""
        try:
            config_dir = os.path.dirname(self.CONFIG_FILE)
            os.makedirs(config_dir, exist_ok=True)

            self.settings['work_dir'] = self.work_dir_input.text()
            self.settings['output_dir'] = self.output_dir_input.text()
            self.settings['write_to_usb'] = self.write_to_usb.isChecked()
            self.settings['excluded_packages'] = getattr(
                self, 'excluded_packages', []
            )
            self.settings['user_template_blank'] = (
                self.user_template_blank.isChecked()
            )
            self.settings['user_template_copy'] = (
                self.user_template_copy.isChecked()
            )
            self.settings['iso_username'] = self.iso_username_input.text()
            self.settings['user_password'] = self.user_password_input.text()
            self.settings['root_password'] = self.root_password_input.text()
            if self.user_source_combo.currentData():
                self.settings['source_user'] = (
                    self.user_source_combo.currentData()
                )

            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError:
            pass  # Fail silently if we can't save settings

    def browse_work_dir(self):
        """Browse for work directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 'Select Work Directory'
        )
        if dir_path:
            self.work_dir_input.setText(dir_path)

    def browse_output_dir(self):
        """Browse for output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 'Select Output Directory'
        )
        if dir_path:
            self.output_dir_input.setText(dir_path)

    def get_usb_devices(self):
        """Detect available USB block devices"""
        devices = []
        try:
            # Use lsblk to find USB devices
            result = run_command(
                ['lsblk', '-d', '-n', '-o', 'NAME,TYPE,SIZE,MODEL'],
                check=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    dev_type = parts[1] if len(parts) > 1 else ''
                    # Check if it's a disk (not a partition)
                    if dev_type == 'disk':
                        # Check if it's removable (USB)
                        device_path = f"/dev/{name}"
                        try:
                            # Check if device is removable
                            removable_path = f"/sys/block/{name}/removable"
                            if os.path.exists(removable_path):
                                with open(removable_path, 'r') as f:
                                    if f.read().strip() == '1':
                                        # Get size and model if available
                                        size = (
                                            parts[2]
                                            if len(parts) > 2
                                            else 'Unknown'
                                        )
                                        model = (' '.join(parts[3:])
                                                 if len(parts) > 3
                                                 else 'USB Device')
                                        devices.append({
                                            'path': device_path,
                                            'name': name,
                                            'size': size,
                                            'model': model
                                        })
                        except (IOError, OSError):
                            pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: check /dev/sd* and /dev/nvme* devices
            for device_path in Path('/dev').glob('sd[a-z]'):
                if device_path.is_block_device():
                    devices.append({
                        'path': str(device_path),
                        'name': device_path.name,
                        'size': 'Unknown',
                        'model': 'USB Device'
                    })
            for device_path in Path('/dev').glob('nvme[0-9]n[0-9]'):
                if device_path.is_block_device():
                    devices.append({
                        'path': str(device_path),
                        'name': device_path.name,
                        'size': 'Unknown',
                        'model': 'USB Device'
                    })

        return devices

    def refresh_usb_devices(self):
        """Refresh the list of USB devices"""
        self.usb_device_combo.clear()
        devices = self.get_usb_devices()

        if not devices:
            self.usb_device_combo.addItem('No USB devices found', None)
            return

        for device in devices:
            display_text = (
                f"{device['path']} - {device['model']} ({device['size']})"
            )
            self.usb_device_combo.addItem(display_text, device['path'])

    def populate_user_list(self):
        """Populate the user combo box with system users"""
        self.user_source_combo.clear()
        try:
            # Get all users with home directories
            result = run_command(['getent', 'passwd'], check=False)
            if result.returncode == 0:
                users = []
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    parts = line.split(':')
                    if len(parts) >= 6:
                        username = parts[0]
                        uid = int(parts[2])
                        home_dir = parts[5]
                        # Only include regular users (UID >= 1000)
                        # with home dirs
                        if (uid >= 1000 and home_dir and
                                os.path.exists(home_dir) and
                                os.path.isdir(home_dir)):
                            users.append(username)

                users.sort()
                for user in users:
                    self.user_source_combo.addItem(user, user)

                # Restore previously selected user if exists
                saved_user = self.settings.get('source_user', '')
                if saved_user:
                    index = self.user_source_combo.findData(saved_user)
                    if index >= 0:
                        self.user_source_combo.setCurrentIndex(index)
            else:
                self.user_source_combo.addItem('No users found', None)
        except Exception as e:
            self.user_source_combo.addItem('Error loading users', None)
            self.log_output.append(
                f"[WARN] Failed to load users: {str(e)}\n"
            )

    def on_user_template_changed(self, state):
        """Handle user template option changes"""
        checked = (
            state == Qt.CheckState.Checked.value if HAS_PYQT6 else state == 2
        )

        sender = self.sender()
        if sender == self.user_template_blank or (
                sender is None and self.user_template_blank.isChecked()):
            if checked:
                self.user_template_copy.setChecked(False)
                self.user_source_combo.setEnabled(False)
                self.refresh_users_btn.setEnabled(False)
                self.iso_username_input.setEnabled(False)
        elif sender == self.user_template_copy or (
                sender is None and self.user_template_copy.isChecked()):
            if checked:
                self.user_template_blank.setChecked(False)
                self.user_source_combo.setEnabled(True)
                self.refresh_users_btn.setEnabled(True)
                self.iso_username_input.setEnabled(True)
            else:
                self.user_source_combo.setEnabled(False)
                self.refresh_users_btn.setEnabled(False)
                self.iso_username_input.setEnabled(False)

    def on_usb_write_toggled(self, state):
        """Enable/disable USB device selection based on checkbox"""
        enabled = (
            state == Qt.CheckState.Checked.value if HAS_PYQT6 else state == 2
        )
        self.usb_device_combo.setEnabled(enabled)
        if hasattr(self, 'refresh_usb_btn'):
            self.refresh_usb_btn.setEnabled(enabled)
        else:
            for widget in self.findChildren(QPushButton):
                if widget.text() == 'Refresh':
                    widget.setEnabled(enabled)
                    break
        if enabled and self.usb_device_combo.count() == 0:
            self.refresh_usb_devices()
        elif enabled:
            self.refresh_usb_devices()

    def show_exclusions_dialog(self):
        """Show the directory exclusions dialog"""
        dialog = ExclusionsDialog(self, self.exclude_list_items)
        accepted, _ = get_qt_dialog_code()
        result = dialog.exec()

        if result == accepted:
            self.exclude_list_items = dialog.get_all_exclusions()

    def show_package_selection_dialog(self):
        """Show the package selection dialog"""
        dialog = PackageSelectionDialog(self, self.excluded_packages)
        accepted, _ = get_qt_dialog_code()
        result = dialog.exec()

        if result == accepted:
            self.excluded_packages = dialog.get_excluded_packages()
            self.settings['excluded_packages'] = self.excluded_packages
            self.save_settings()

    def get_selected_exclusions(self):
        """Get list of checked exclusion patterns"""
        return [
            pattern for pattern, checked in self.exclude_list_items.items()
            if checked
        ]

    def check_root(self) -> bool:
        """Check if running as root, show error if not"""
        if os.geteuid() != 0:
            QMessageBox.critical(self, 'Error', Messages.ROOT_REQUIRED)
            return False
        return True

    def find_existing_iso(self, output_dir, iso_name):
        """Find existing ISO files matching the name pattern"""
        if not os.path.exists(output_dir):
            return None

        iso_files = list(Path(output_dir).glob(f'{iso_name}*.iso'))
        if not iso_files:
            return None

        # Sort by modification time, most recent first
        iso_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        most_recent = iso_files[0]

        # Check if ISO is recent (within last 24 hours)
        import time
        current_time = time.time()
        iso_age = current_time - most_recent.stat().st_mtime
        hours_old = iso_age / 3600

        # Consider ISO "recent" if less than 24 hours old
        if hours_old < 24:
            return most_recent
        return None

    def start_build(self):
        """Start the ISO build process"""
        if not self.check_root():
            return

        date_str = subprocess.check_output(
            ['date', '+%Y%m'], text=True
        ).strip()

        user_config = {
            'iso_username': self.iso_username_input.text(),
            'user_password': self.user_password_input.text(),
            'root_password': self.root_password_input.text(),
            'use_blank_template': self.user_template_blank.isChecked(),
            'copy_from_user': None
        }
        if self.user_template_copy.isChecked():
            user_config['copy_from_user'] = (
                self.user_source_combo.currentData()
            )

        output_dir = self.output_dir_input.text()
        iso_name = self.iso_name_input.text()

        # Check for existing ISO
        existing_iso = self.find_existing_iso(output_dir, iso_name)
        if existing_iso:
            # Prompt user
            iso_size = existing_iso.stat().st_size / (1024**3)
            import time
            iso_age_hours = (
                (time.time() - existing_iso.stat().st_mtime) / 3600
            )
            reply = QMessageBox.question(
                self,
                'Existing ISO Found',
                f'Found an existing ISO file:\n\n'
                f'File: {existing_iso.name}\n'
                f'Size: {iso_size:.2f} GB\n'
                f'Age: {iso_age_hours:.1f} hours old\n\n'
                f'Do you want to use this existing ISO or rebuild?',
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            if reply == QMessageBox.StandardButton.Yes:
                # Use existing ISO - skip build and go straight to USB write
                # or completion
                self.log_output.clear()
                self.append_log(
                    f"[INFO] Using existing ISO: {existing_iso}\n"
                )
                self.append_log(
                    "[INFO] Skipping build process.\n"
                )
                self.progress_bar.setValue(100)
                self.build_btn.setEnabled(False)
                self.stop_btn.setEnabled(False)

                # Simulate build completion with existing ISO
                # This will handle USB write if enabled
                self.last_iso_path = str(existing_iso)
                self.build_finished(True, str(existing_iso))
                return

        # Proceed with normal build
        config = {
            'work_dir': self.work_dir_input.text(),
            'output_dir': output_dir,
            'iso_name': iso_name,
            'iso_label': f"ARCH_CUSTOM_{date_str}",
            'exclude_dirs': self.get_selected_exclusions(),
            'excluded_packages': self.excluded_packages,
            'include_custom_repos': self.include_custom_repos.isChecked(),
            'user_config': user_config
        }

        # Update UI
        self.build_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.set_status(Messages.BUILDING)
        self.log_output.clear()

        # Start builder thread
        self.builder_thread = ISOBuilderThread(config)
        self.builder_thread.output_signal.connect(self.append_log)
        self.builder_thread.progress_signal.connect(self.update_progress)
        self.builder_thread.finished_signal.connect(self.build_finished)
        self.builder_thread.start()

    def stop_build(self):
        """Stop the build process"""
        if self.builder_thread:
            self.builder_thread.stop()
            self.append_log("\n[INFO] Build stopped by user\n")
            self.build_finished(False, "Stopped by user")

    def append_log(self, text):
        """Append text to the log output"""
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        self.log_output.insertPlainText(text)
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)

    def update_progress(self, value):
        """Update the progress bar"""
        self.progress_bar.setValue(value)

    def build_finished(self, success, message):
        """Handle build completion"""
        self.build_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self.last_iso_path = message
            self.set_status(Messages.BUILD_SUCCESS, Colors.SUCCESS)

            # Check if USB write is enabled - automatically proceed
            # without confirmation
            if self.write_to_usb.isChecked():
                # Get selected USB device
                device_path = self.usb_device_combo.currentData()

                if not device_path:
                    # Only show error if USB device is invalid
                    QMessageBox.warning(
                        self,
                        'Invalid USB Device',
                        'ISO created successfully, but the selected USB '
                        'device is invalid.\n\n'
                        f'ISO Location: {message}\n\n'
                        'Please select a valid USB device and try again.'
                    )
                    return

                # Automatically start USB write without confirmation
                self.start_usb_write(message, device_path)
            else:
                # Only show completion message if USB write is not enabled
                QMessageBox.information(
                    self,
                    'Build Complete',
                    f'ISO created successfully!\n\nLocation: {message}\n\n'
                    'You can now write it to a USB drive or test it in a VM.'
                )
        else:
            self.set_status(Messages.BUILD_FAILED, Colors.ERROR)
            QMessageBox.critical(
                self, 'Build Failed', f'Build failed: {message}'
            )

    def start_usb_write(self, iso_path, device_path):
        """Start writing ISO to USB device"""
        self.set_status(Messages.USB_WRITING, Colors.INFO)
        self.build_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # Start USB writer thread
        self.usb_writer_thread = USBWriterThread(iso_path, device_path)
        self.usb_writer_thread.output_signal.connect(self.append_log)
        self.usb_writer_thread.progress_signal.connect(self.update_progress)
        self.usb_writer_thread.finished_signal.connect(self.usb_write_finished)
        self.usb_writer_thread.start()

    def usb_write_finished(self, success, message):
        """Handle USB write completion"""
        self.build_btn.setEnabled(True)

        if success:
            self.set_status(Messages.USB_WRITE_SUCCESS, Colors.SUCCESS)
            # Show final completion message with ISO location and USB
            # write success
            iso_location = self.last_iso_path or "Unknown"
            QMessageBox.information(
                self,
                'Process Complete',
                f'ISO created and written to USB drive successfully!\n\n'
                f'ISO Location: {iso_location}\n'
                f'USB Device: {message}\n\n'
                'You can now boot from this USB drive.'
            )
        else:
            self.set_status(Messages.USB_WRITE_FAILED, Colors.ERROR)
            # Show error with ISO location in case user wants to manually
            # write it
            iso_location = self.last_iso_path or "Unknown"
            QMessageBox.critical(
                self,
                'USB Write Failed',
                f'Failed to write ISO to USB device.\n\n'
                f'Error: {message}\n\n'
                f'ISO Location: {iso_location}\n\n'
                'You can manually write the ISO to a USB drive using dd '
                'or another tool.'
            )


def main():
    """Main entry point"""
    if not HAS_PYQT6 and not HAS_PYQT5:
        print("Error: PyQt6 or PyQt5 is required")
        print("\nInstall with:")
        print("  sudo pacman -S python-pyqt6")
        print("  or")
        print("  sudo pacman -S python-pyqt5")
        print("  or")
        print("  pip install PyQt6")
        sys.exit(1)

    # Set Qt to use dark theme if available (Qt 6.5+)
    if HAS_PYQT6:
        from PyQt6.QtCore import Qt
        try:
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except AttributeError:
            pass

    app = QApplication(sys.argv)

    # Enable dark mode via environment or Qt attribute
    if HAS_PYQT6:
        try:
            # Try to use native dark mode (Qt 6.5+)
            app.setStyleSheet("")
            os.environ['QT_QPA_PLATFORM'] = os.environ.get(
                'QT_QPA_PLATFORM', 'xcb'
            )
        except (AttributeError, KeyError, OSError):
            pass

    # Apply dark theme
    app.setStyle('Fusion')

    dark_palette = app.palette() if HAS_PYQT6 else app.palette()
    if HAS_PYQT6:
        from PyQt6.QtGui import QPalette, QColor
        from PyQt6.QtCore import Qt
    else:
        from PyQt5.QtGui import QPalette, QColor
        from PyQt5.QtCore import Qt

    # Modern dark theme colors - clean and professional
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(
        QPalette.ColorRole.WindowText, QColor(240, 240, 240)
    )
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(
        QPalette.ColorRole.AlternateBase, QColor(35, 35, 35)
    )
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(20, 20, 20))
    dark_palette.setColor(
        QPalette.ColorRole.ToolTipText, QColor(240, 240, 240)
    )
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    dark_palette.setColor(
        QPalette.ColorRole.ButtonText, QColor(240, 240, 240)
    )
    dark_palette.setColor(
        QPalette.ColorRole.BrightText, QColor(255, 100, 100)
    )
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(100, 150, 255))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(70, 130, 200))
    dark_palette.setColor(
        QPalette.ColorRole.HighlightedText, QColor(255, 255, 255)
    )

    # Disabled colors for better visual feedback
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
        QColor(120, 120, 120)
    )
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
        QColor(120, 120, 120)
    )
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
        QColor(120, 120, 120)
    )
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base,
        QColor(30, 30, 30)
    )
    dark_palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button,
        QColor(30, 30, 30)
    )

    app.setPalette(dark_palette)

    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: {Colors.BG_PRIMARY};
        }}
        QToolTip {{
            color: {Colors.TOOLTIP_TEXT};
            background-color: {Colors.TOOLTIP_BG};
            border: 1px solid {Colors.TOOLTIP_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QGroupBox {{
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 6px;
            margin-top: 16px;
            padding-top: 12px;
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            background-color: {Colors.BG_TERTIARY};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            background-color: {Colors.BG_TERTIARY};
            padding: 0 8px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border-left: 1px solid {Colors.BORDER_DEFAULT};
            border-top: 1px solid {Colors.BORDER_DEFAULT};
            border-right: 1px solid {Colors.BORDER_DEFAULT};
            padding-top: 6px;
        }}
        QPushButton {{
            background-color: {Colors.BG_BUTTON};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_HOVER};
            border-radius: 4px;
            padding: 4px 12px;
            font-weight: 500;
            min-height: 16px;
        }}
        QPushButton:hover {{
            background-color: {Colors.BG_BUTTON_HOVER};
            border: 1px solid {Colors.BORDER_ACTIVE};
        }}
        QPushButton:pressed {{
            background-color: {Colors.BG_BUTTON_PRESSED};
            border: 1px solid {Colors.BORDER_DEFAULT};
        }}
        QPushButton:focus {{
            border: 1px solid {Colors.BORDER_FOCUS};
            outline: none;
        }}
        QPushButton#buildButton {{
            background-color: {Colors.BUTTON_SUCCESS};
            border: 1px solid {Colors.BUTTON_SUCCESS_BORDER};
            font-weight: 600;
            padding: 5px 12px;
        }}
        QPushButton#buildButton:hover {{
            background-color: {Colors.BUTTON_SUCCESS_HOVER};
            border: 1px solid {Colors.BUTTON_SUCCESS_BORDER_HOVER};
        }}
        QPushButton#buildButton:pressed {{
            background-color: {Colors.BUTTON_SUCCESS_PRESSED};
            border: 1px solid {Colors.BUTTON_SUCCESS_BORDER};
        }}
        QPushButton#buildButton:disabled {{
            background-color: {Colors.BG_DISABLED};
            color: {Colors.TEXT_DISABLED};
            border: 1px dashed {Colors.BORDER_DISABLED};
            opacity: 0.6;
        }}
        QPushButton#stopButton {{
            background-color: {Colors.BUTTON_ERROR};
            border: 1px solid {Colors.BUTTON_ERROR_BORDER};
            font-weight: 600;
            padding: 5px 12px;
        }}
        QPushButton#stopButton:hover {{
            background-color: {Colors.BUTTON_ERROR_HOVER};
            border: 1px solid {Colors.BUTTON_ERROR_BORDER_HOVER};
        }}
        QPushButton#stopButton:pressed {{
            background-color: {Colors.BUTTON_ERROR_PRESSED};
            border: 1px solid {Colors.BUTTON_ERROR_BORDER};
        }}
        QLineEdit {{
            background-color: {Colors.BG_SECONDARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
        }}
        QLineEdit:focus {{
            border: 1px solid {Colors.BORDER_FOCUS};
            background-color: {Colors.BG_TERTIARY};
        }}
        QLineEdit:hover {{
            border: 1px solid {Colors.BORDER_HOVER};
        }}
        QComboBox {{
            background-color: {Colors.BG_SECONDARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px;
            padding: 4px 8px;
            min-width: 120px;
        }}
        QComboBox:hover {{
            border: 1px solid {Colors.BORDER_HOVER};
            background-color: {Colors.BG_TERTIARY};
        }}
        QComboBox:focus {{
            border: 1px solid {Colors.BORDER_FOCUS};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
            background-color: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {Colors.COMBO_ARROW};
            width: 0;
            height: 0;
            margin-right: 6px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
        }}
        QListWidget {{
            background-color: {Colors.BG_SECONDARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px;
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
        }}
        QListWidget::item {{
            padding: 3px;
            border-bottom: 1px solid {Colors.LIST_ITEM_BORDER};
        }}
        QListWidget::item:hover {{
            background-color: {Colors.LIST_ITEM_HOVER};
        }}
        QListWidget::item:selected {{
            background-color: {Colors.SELECTION_BG};
            color: {Colors.SELECTION_TEXT};
        }}
        QCheckBox {{
            color: {Colors.TEXT_PRIMARY};
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {Colors.CHECKBOX_BORDER};
            border-radius: 3px;
            background-color: {Colors.BG_SECONDARY};
        }}
        QCheckBox::indicator:hover {{
            border: 2px solid {Colors.CHECKBOX_BORDER_HOVER};
            background-color: {Colors.BG_TERTIARY};
        }}
        QCheckBox::indicator:checked {{
            background-color: {Colors.CHECKBOX_CHECKED};
            border: 2px solid {Colors.CHECKBOX_CHECKED};
            image: none;
        }}
        QLabel {{
            color: {Colors.TEXT_PRIMARY};
        }}
        QProgressBar {{
            background-color: {Colors.PROGRESS_BG};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px;
            text-align: center;
            color: {Colors.TEXT_PRIMARY};
            height: 16px;
        }}
        QProgressBar::chunk {{
            background-color: {Colors.PROGRESS_CHUNK};
            border-radius: 3px;
        }}
        QTextEdit {{
            background-color: {Colors.BG_DARKEST};
            color: {Colors.TEXT_SECONDARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 4px;
            selection-background-color: {Colors.SELECTION_BG};
            selection-color: {Colors.SELECTION_TEXT};
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        }}
        QScrollBar:vertical {{
            background-color: {Colors.SCROLLBAR_BG};
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: {Colors.SCROLLBAR_HANDLE};
            border-radius: 6px;
            border: 2px solid {Colors.SCROLLBAR_BG};
            min-height: 16px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {Colors.SCROLLBAR_HANDLE_HOVER};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background-color: {Colors.SCROLLBAR_BG};
            height: 12px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {Colors.SCROLLBAR_HANDLE};
            border-radius: 6px;
            border: 2px solid {Colors.SCROLLBAR_BG};
            min-width: 16px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {Colors.SCROLLBAR_HANDLE_HOVER};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QComboBox:disabled {{
            background-color: {Colors.BG_DISABLED};
            color: {Colors.TEXT_DISABLED};
            border: 1px dashed {Colors.BORDER_DISABLED};
            opacity: 0.6;
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_DISABLED};
            color: {Colors.TEXT_DISABLED};
            border: 1px dashed {Colors.BORDER_DISABLED};
            opacity: 0.6;
        }}
        QLineEdit:disabled {{
            background-color: {Colors.BG_DISABLED};
            color: {Colors.TEXT_DISABLED};
            border: 1px dashed {Colors.BORDER_DISABLED};
            opacity: 0.6;
        }}
        QListWidget:disabled {{
            background-color: {Colors.BG_DISABLED};
            color: {Colors.TEXT_DISABLED};
            border: 1px dashed {Colors.BORDER_DISABLED};
            opacity: 0.6;
        }}
        QCheckBox:disabled {{
            color: {Colors.TEXT_DISABLED};
            opacity: 0.6;
        }}
        QLabel:disabled {{
            color: {Colors.TEXT_DISABLED};
            opacity: 0.6;
        }}
    """)

    window = ISOBuilderGUI()
    window.show()
    sys.exit(app.exec() if HAS_PYQT6 else app.exec_())


if __name__ == '__main__':
    main()
