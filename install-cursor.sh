#!/usr/bin/env bash
set -euo pipefail

# Config
INSTALL_DIR="${HOME}/.local/bin"
APPIMAGE="${INSTALL_DIR}/cursor.AppImage"
TMP="${INSTALL_DIR}/.cursor.AppImage.tmp"
ARCH="$(uname -m)"
# Optional override: CURSOR_URL="https://example.com/cursor.AppImage" ./update_cursor.sh
OVERRIDE_URL="${CURSOR_URL:-}"

mkdir -p "${INSTALL_DIR}"

# Stop running Cursor quietly
pkill -x cursor 2>/dev/null || true
pkill -f "Cursor.*AppImage" 2>/dev/null || true

# Candidate URLs, in order
URLS=()
if [[ -n "${OVERRIDE_URL}" ]]; then URLS+=("${OVERRIDE_URL}"); fi

# api2 cursor CDN (official, versioned)
if [[ "${ARCH}" == "x86_64" || "${ARCH}" == "amd64" ]]; then
  URLS+=(
    "https://api2.cursor.sh/updates/download/golden/linux-x64/cursor/1.7"
  )
elif [[ "${ARCH}" == "aarch64" || "${ARCH}" == "arm64" ]]; then
  URLS+=(
    "https://api2.cursor.sh/updates/download/golden/linux-arm64/cursor/1.7"
  )
fi

# Legacy and community fallbacks
URLS+=(
  "https://downloader.cursor.sh/linux/appImage/x64"
)

# Try to scrape the downloads page for a direct .AppImage if above fail
scrape_download_url() {
  # Grab any .AppImage link from the official downloads page
  curl -fsSL "https://cursor.com/docs/downloads" \
  | grep -Eo 'https?://[^" ]+\.AppImage' \
  | head -n1 || true
}

# Download with retries
rm -f "${TMP}"
for u in "${URLS[@]}"; do
  echo "Downloading from: $u"
  if curl -fL --retry 5 --retry-all-errors --connect-timeout 10 -o "${TMP}" "$u"; then
    if head -c 4 "${TMP}" | grep -q $'^\x7fELF'; then
      echo "Got ELF binary"
      break
    else
      echo "Not an AppImage. Trying next URL..."
      rm -f "${TMP}"
    fi
  else
    echo "Download failed from $u. Trying next URL..."
    rm -f "${TMP}"
  fi
done

if [[ ! -s "${TMP}" ]]; then
  alt="$(scrape_download_url || true)"
  if [[ -n "${alt}" ]]; then
    echo "Scraped candidate: ${alt}"
    if curl -fL --retry 5 --retry-all-errors --connect-timeout 10 -o "${TMP}" "${alt}"; then
      head -c 4 "${TMP}" | grep -q $'^\x7fELF' || { echo "Scraped file is not an AppImage"; rm -f "${TMP}"; }
    fi
  fi
fi

[[ -s "${TMP}" ]] || { echo "Download failed from all sources."; exit 1; }

mv -f "${TMP}" "${APPIMAGE}"
chmod +x "${APPIMAGE}"

# Desktop entry
DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "${DESKTOP_DIR}"
cat > "${DESKTOP_DIR}/cursor.desktop" <<'EOF'
[Desktop Entry]
Name=Cursor
Comment=AI code editor
Exec=%h/.local/bin/cursor.AppImage %U
Terminal=false
Type=Application
Categories=Development;IDE;
StartupNotify=false
MimeType=text/plain;inode/directory;
EOF

update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true

# AppImage runtime prerequisite on Ubuntu/Debian
if command -v apt >/dev/null 2>&1; then
  sudo apt-get update -y >/dev/null 2>&1 || true
  sudo apt-get install -y libfuse2t64 >/dev/null 2>&1 || true
fi

echo "Cursor installed at ${APPIMAGE}"
