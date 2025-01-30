import os
import subprocess
from pathlib import Path

# Theme names
THEME_DARK = "Qogir-Dark"
THEME_LIGHT = "Qogir-Light"

# GTK settings template
GTK_SETTINGS_TEMPLATE = """
[Settings]
gtk-theme-name={theme_name}
gtk-icon-theme-name={theme_name}
gtk-cursor-theme-name={theme_name}
"""

# QT settings template
QT_SETTINGS_TEMPLATE = """
[Appearance]
style={theme_name}
color_scheme={theme_name}
icon_theme={theme_name}
"""

def apply_gtk_theme(user_home, theme_name):
    """Apply the GTK theme by updating the settings.ini file."""
    try:
        gtk_settings_path = Path(user_home) / ".config/gtk-3.0/settings.ini"
        gtk_settings_path.parent.mkdir(parents=True, exist_ok=True)
        gtk_settings_path.write_text(GTK_SETTINGS_TEMPLATE.format(theme_name=theme_name))
        print(f"[INFO] GTK theme set to {theme_name} for {user_home}.")
    except Exception as e:
        print(f"[ERROR] Failed to apply GTK theme for {user_home}: {e}")

def apply_qt_theme(user_home, theme_name):
    """Apply the QT theme by updating the qt5ct.conf file."""
    try:
        qt_settings_path = Path(user_home) / ".config/qt5ct/qt5ct.conf"
        qt_settings_path.parent.mkdir(parents=True, exist_ok=True)
        qt_settings_path.write_text(QT_SETTINGS_TEMPLATE.format(theme_name=theme_name))

        # Update .profile to ensure QT environment variables are set
        profile_path = Path(user_home) / ".profile"
        profile_text = profile_path.read_text() if profile_path.exists() else ""
        new_exports = [
            "export QT_QPA_PLATFORMTHEME=qt5ct",
            f"export QT_STYLE_OVERRIDE={theme_name}",
            "export QT_QTA_PLATFORM=x11"
        ]
        with profile_path.open("a") as profile_file:
            for line in new_exports:
                if line not in profile_text:
                    profile_file.write(line + "\n")
        print(f"[INFO] QT theme set to {theme_name} for {user_home}.")
    except Exception as e:
        print(f"[ERROR] Failed to apply QT theme for {user_home}: {e}")

def apply_gnome_theme(theme_name):
    """Apply the GNOME Shell theme using gsettings."""
    try:
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", theme_name],
            check=True
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", theme_name],
            check=True
        )
        print(f"[INFO] GNOME shell theme set to {theme_name}.")
    except FileNotFoundError:
        print("[ERROR] gsettings command not found; skipping GNOME shell configuration.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to apply GNOME theme: {e}")

def apply_theme_for_user(user_home, theme_name):
    """Apply theme configurations for a given user."""
    print(f"[INFO] Applying theme {theme_name} for {user_home}...")
    apply_gtk_theme(user_home, theme_name)
    apply_qt_theme(user_home, theme_name)
    apply_gnome_theme(theme_name)

def main():
    current_user_home = Path.home()
    root_home = Path("/root")

    if os.geteuid() == 0:  # Run as root
        print("[INFO] Running as root. Applying themes...")
        print("[INFO] Applying Qogir-Light for the root account...")
        apply_theme_for_user(root_home, THEME_LIGHT)
    else:
        print("[INFO] Running as a regular user.")
        print("[INFO] Applying Qogir-Dark for the current user...")
        apply_theme_for_user(current_user_home, THEME_DARK)
        print("[INFO] To apply Qogir-Light for the root account, run this script as root.")

    print("[INFO] Theme application complete. Restart your session for changes to take effect.")

if __name__ == "__main__":
    main()
