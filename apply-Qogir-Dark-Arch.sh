#!/usr/bin/env bash
set -euo pipefail

# ===== Arch Linux + GNOME 48: Qogir for user (Dark) and root (Light) =====

THEME_DARK="Qogir-Dark"
THEME_LIGHT="Qogir-Light"      # Some folks say "Qogir-Lite" — we'll fall back to that name if needed
THEME_LIGHT_ALT="Qogir-Lite"

ICON_DARK="Qogir-dark"
ICON_LIGHT="Qogir-light"

say()  { printf "\033[1;32m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[✗]\033[0m %s\n" "$*"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1; }

ensure_pkg() {
  local pkg="$1"
  if ! pacman -Qq "$pkg" &>/dev/null; then
    say "Installing ${pkg}..."
    sudo pacman -S --noconfirm --needed "$pkg"
  else
    say "${pkg} already installed."
  fi
}

install_qogir_themes() {
  local themes_dir="$1"   # usually ~/.local/share/themes or /usr/share/themes
  local icons_dir="$2"    # usually ~/.local/share/icons or /usr/share/icons

  mkdir -p "$themes_dir" "$icons_dir"

  # GTK/Shell theme
  if [ ! -d "$themes_dir/$THEME_DARK" ] || [ ! -d "$themes_dir/$THEME_LIGHT" ]; then
    say "Installing Qogir GTK theme variants (dark & light) into $themes_dir..."
    local tmp="$(mktemp -d)"
    git clone --depth=1 https://github.com/vinceliuice/Qogir-theme.git "$tmp/Qogir-theme"
    pushd "$tmp/Qogir-theme" >/dev/null
    # Install both variants locally; if that fails, try system-wide
    if ! ./install.sh -d "$themes_dir" -c dark -g >/dev/null 2>&1; then
      warn "Local dark install failed; trying system-wide"
      sudo ./install.sh -c dark -l
    fi
    if ! ./install.sh -d "$themes_dir" -c light -g >/dev/null 2>&1; then
      warn "Local light install failed; trying system-wide"
      sudo ./install.sh -c light -l
    fi
    popd >/dev/null
    rm -rf "$tmp"
  else
    say "Qogir GTK themes already present."
  fi

  # Icon theme
  if [ ! -d "$icons_dir/$ICON_DARK" ] || [ ! -d "$icons_dir/$ICON_LIGHT" ]; then
    say "Installing Qogir icon theme variants (dark & light) into $icons_dir..."
    local tmp="$(mktemp -d)"
    git clone --depth=1 https://github.com/vinceliuice/Qogir-icon-theme.git "$tmp/Qogir-icon-theme"
    pushd "$tmp/Qogir-icon-theme" >/dev/null
    if ! ./install.sh -d "$icons_dir" >/dev/null 2>&1; then
      warn "Local icon dark install failed; trying system-wide"
      sudo ./install.sh 
    fi
    if ! ./install.sh -d "$icons_dir" >/devnull 2>&1; then
      warn "Local icon light install failed; trying system-wide"
      sudo ./install.sh 
    fi
    popd >/dev/null
    rm -rf "$tmp"
  else
    say "Qogir icon themes already present."
  fi
}

write_gtk_ini() {
  local home_dir="$1" theme="$2" icon="$3" cursor="$4"
  mkdir -p "$home_dir/.config/gtk-3.0"
  cat > "$home_dir/.config/gtk-3.0/settings.ini" <<EOF
[Settings]
gtk-theme-name=${theme}
gtk-icon-theme-name=${icon}
gtk-cursor-theme-name=${cursor}
gtk-font-name=DejaVu Sans Mono Book 11
EOF
}

write_qt_ct() {
  local home_dir="$1" theme="$2" icon="$3"
  mkdir -p "$home_dir/.config/qt5ct" "$home_dir/.config/qt6ct"
  cat > "$home_dir/.config/qt5ct/qt5ct.conf" <<EOF
[Appearance]
style=${theme}
color_scheme=${theme}
icon_theme=${icon}
EOF
  cat > "$home_dir/.config/qt6ct/qt6ct.conf" <<EOF
[Appearance]
icon_theme=${icon}
EOF
}

append_profile_exports() {
  local home_dir="$1" theme="$2"
  local profile="$home_dir/.profile"
  touch "$profile"
  # Only append if not present
  grep -q 'QT_QPA_PLATFORMTHEME=' "$profile" || echo 'export QT_QPA_PLATFORMTHEME=qt5ct' >> "$profile"
  grep -q 'QT_STYLE_OVERRIDE=' "$profile"   || echo "export QT_STYLE_OVERRIDE=${theme}" >> "$profile"
  grep -q 'QT_QTA_PLATFORM=' "$profile"     || echo 'export QT_QTA_PLATFORM=x11' >> "$profile"
}

apply_gsettings_for_current_session() {
  # Only affects the *current* logged-in user session with a running D-Bus
  local theme="$1" icon="$2" cursor="$3"
  if need gsettings; then
    say "Applying GNOME settings via gsettings (current session)…"
    gsettings set org.gnome.desktop.interface gtk-theme   "$theme"  || warn "gtk-theme set failed"
    gsettings set org.gnome.desktop.interface icon-theme  "$icon"   || warn "icon-theme set failed"
    gsettings set org.gnome.desktop.interface cursor-theme "$cursor" || warn "cursor-theme set failed"
    gsettings set org.gnome.desktop.interface font-name "DejaVu Sans Mono Book 11" || true
    if gsettings list-schemas | grep -q 'org.gnome.shell.extensions.user-theme'; then
      gsettings set org.gnome.shell.extensions.user-theme name "$theme" || warn "shell theme set failed (needs User Themes extension)"
    fi
  else
    warn "gsettings not found; skipping live GNOME settings."
  fi
}

apply_for_account() {
  # $1 = home, $2 = theme (GTK), $3 = icon, $4 = cursor, $5 = account label (user/root)
  local home_dir="$1" theme="$2" icon="$3" cursor="$4" label="$5"

  say "Configuring ${label} account at ${home_dir} → GTK: ${theme}, Icons: ${icon}"
  write_gtk_ini "$home_dir" "$theme" "$icon" "$cursor"
  write_qt_ct  "$home_dir" "$theme" "$icon"
  append_profile_exports "$home_dir" "$theme"

  # Fix ownership if we wrote as root to a non-root home
  if [ "$label" = "user" ] && [ "$(id -u)" -eq 0 ]; then
    chown -R "$(logname)":"$(logname)" "$home_dir/.config" "$home_dir/.profile" 2>/dev/null || true
  fi
}

# ---- Main ----
if ! need pacman; then
  die "This script is for Arch-based systems (pacman not found)."
fi

ensure_pkg git
ensure_pkg gnome-tweaks
ensure_pkg qt5ct
ensure_pkg qt6ct

# Install themes (first try user-local, then system-wide fallback handled inside)
install_qogir_themes "$HOME/.local/share/themes" "$HOME/.local/share/icons"

# Decide names that actually exist on the system (handle Lite vs Light)
theme_light_effective="$THEME_LIGHT"
if [ ! -d "$HOME/.local/share/themes/$THEME_LIGHT" ] && [ -d "$HOME/.local/share/themes/$THEME_LIGHT_ALT" ]; then
  theme_light_effective="$THEME_LIGHT_ALT"
fi

# Apply for current user (Dark)
apply_for_account "$HOME" "$THEME_DARK" "$ICON_DARK" "Qogir" "user"
apply_gsettings_for_current_session "$THEME_DARK" "$ICON_DARK" "Qogir"

# If run as root, also apply for /root (Light)
if [ "$(id -u)" -eq 0 ]; then
  say "Running as root — applying Light theme for root."
  root_home="/root"

  # Ensure themes are available system-wide too (for root sessions that ignore ~/.local)
  install_qogir_themes "/usr/share/themes" "/usr/share/icons"

  # For root, prefer system icon cursor that matches light; fall back to Qogir
  cursor_root="Qogir"
  [ -d "/usr/share/icons/$ICON_LIGHT/cursors" ] && cursor_root="Qogir" # Qogir uses same cursor name

  apply_for_account "$root_home" "$theme_light_effective" "$ICON_LIGHT" "$cursor_root" "root"

  # Note: We don't run gsettings for root here — root typically has no GNOME session or DBus.
  # If you *do* log into a graphical session as root (not recommended), run:
  # sudo -H -u root DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" gsettings set ...
else
  say "Not running as root — root account not modified."
  echo "To theme root with ${theme_light_effective}, re-run this script with: sudo $0"
fi

say "Done. Log out/in to ensure Qt env vars are picked up."
echo "If icons look off, try switching between '${ICON_DARK}', 'Qogir', and '${ICON_LIGHT}'."
