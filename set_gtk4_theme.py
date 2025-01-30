# flake8: noqa
# pylint: skip-file

import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

def list_themes():
    """List available themes from predefined directories."""
    theme_dirs = [os.path.expanduser("~/.themes"), "/usr/share/themes"]
    themes = []

    for theme_dir in theme_dirs:
        if os.path.isdir(theme_dir):
            themes.extend(
                theme for theme in os.listdir(theme_dir)
                if os.path.isdir(os.path.join(theme_dir, theme))
            )
    return sorted(themes)

def set_qt_theme(qt_config_file, style="gtk3"):
    """Modify or create Qt configuration files to match the selected theme."""
    qt_config_file = os.path.expanduser(qt_config_file)
    os.makedirs(os.path.dirname(qt_config_file), exist_ok=True)

    content = f"[Appearance]\nstyle={style}\n"
    try:
        if os.path.isfile(qt_config_file):
            with open(qt_config_file, 'r+') as file:
                current_content = file.read()
                new_content = current_content.replace(
                    "style=gtk2", f"style={style}"
                ).replace("style=gtk3", f"style={style}")
                file.seek(0)
                file.write(new_content)
                file.truncate()
        else:
            with open(qt_config_file, 'w') as file:
                file.write(content)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to set Qt theme: {e}")

def link_files(source_dir, target_dir):
    """Link all files from source to target, removing old files."""
    for root, _, files in os.walk(source_dir):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), source_dir)
            target_file = os.path.join(target_dir, rel_path)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)

            # Delete old file or link if it exists
            if os.path.islink(target_file) or os.path.isfile(target_file):
                os.remove(target_file)

            # Create a new symbolic link
            try:
                os.symlink(os.path.join(root, file), target_file)
            except OSError as e:
                messagebox.showerror("Error", f"Failed to link {file}: {e}")

def switch_theme(theme_name):
    """Switch to the selected theme and apply it system-wide."""
    theme_dirs = [os.path.expanduser("~/.themes"), "/usr/share/themes"]
    source_dir = next(
        (os.path.join(dir, theme_name) for dir in theme_dirs if os.path.isdir(os.path.join(dir, theme_name))),
        None
    )

    if not source_dir:
        messagebox.showerror("Error", f"Theme '{theme_name}' not found.")
        return

    target_dir = os.path.expanduser("~/.config")
    link_files(source_dir, target_dir)

    try:
        subprocess.run(["gsettings", "set", "org.gnome.shell.extensions.user-theme", "name", theme_name], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to set GNOME theme: {e}")

    set_qt_theme("~/.config/qt5ct/qt5ct.conf")
    set_qt_theme("~/.config/qt6ct/qt6ct.conf")

    os.environ["QT_QPA_PLATFORMTHEME"] = "gtk3"
    os.environ["QT_STYLE_OVERRIDE"] = "gtk3"
    messagebox.showinfo("Success", f"Theme switched to {theme_name}")

def on_select_theme():
    """Handle the theme selection and initiate the switch."""
    selected_theme = theme_var.get()
    if selected_theme:
        switch_theme(selected_theme)
    else:
        messagebox.showwarning("Warning", "Please select a theme.")

def create_gui():
    """Create the GUI for selecting and switching themes."""
    global theme_var
    root = tk.Tk()
    root.title("Switch Theme")

    ttk.Style().configure("TLabel", font=("Helvetica", 12), padding=10)
    ttk.Style().configure("TButton", font=("Helvetica", 12), padding=10)

    label = ttk.Label(root, text="Select a Theme:")
    label.pack(pady=10)

    theme_var = tk.StringVar()
    themes = list_themes()

    if not themes:
        messagebox.showerror("Error", "No themes found.")
        root.destroy()
        return

    theme_menu = ttk.Combobox(root, textvariable=theme_var, values=themes, state="readonly")
    theme_menu.pack(pady=10)

    apply_button = ttk.Button(root, text="Apply Theme", command=on_select_theme)
    apply_button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
