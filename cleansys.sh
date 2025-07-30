#!/usr/bin/env bash
#
# clean-linux.sh — Detect distro and remove common caches, logs, and unused data
# Usage: sudo ./clean-linux.sh

set -euo pipefail

# Must be run as root
if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (e.g. sudo $0)" >&2
  exit 1
fi

echo "==> Starting system cleanup at $(date)"

##
## 0) Detect distro & set pkg manager commands
##
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO_ID=${ID,,}
  DISTRO_LIKE=${ID_LIKE:-}        # default to empty if unset
elif [[ -r /etc/lsb-release ]]; then
  # shellcheck disable=SC1091
  . /etc/lsb-release
  DISTRO_ID=${DISTRIB_ID,,}
  DISTRO_LIKE=""
elif command -v apk &>/dev/null; then
  # Alpine fallback
  DISTRO_ID="alpine"
  DISTRO_LIKE="busybox"
else
  echo "Warning: cannot detect distro, assuming Debian-like"
  DISTRO_ID="debian"
  DISTRO_LIKE=""
fi

echo "--> Detected distro: $DISTRO_ID (like: ${DISTRO_LIKE:-unknown})"

case "$DISTRO_ID" in
  debian|ubuntu|linuxmint)
    PKG_UPDATE="apt-get update -qq"
    PKG_AUTOREMOVE="apt-get -y autoremove --purge"
    PKG_AUTOCLEAN="apt-get -y autoclean"
    PKG_CLEAN="apt-get -y clean"
    ;;
  fedora)
    PKG_UPDATE="dnf -y makecache"
    PKG_AUTOREMOVE="dnf -y autoremove"
    PKG_AUTOCLEAN="dnf -y clean packages"
    PKG_CLEAN="dnf -y clean all"
    ;;
  centos|rhel)
    PKG_UPDATE="yum -y makecache"
    PKG_AUTOREMOVE="yum -y autoremove"
    PKG_AUTOCLEAN="yum -y clean packages"
    PKG_CLEAN="yum -y clean all"
    ;;
  arch)
    PKG_UPDATE="pacman -Sy"
    PKG_AUTOREMOVE="pacman -Rns \$(pacman -Qtdq || echo '')"
    PKG_AUTOCLEAN="pacman -Sc --noconfirm"
    PKG_CLEAN="pacman -Scc --noconfirm"
    ;;
  suse*|opensuse*)
    PKG_UPDATE="zypper refresh"
    PKG_AUTOREMOVE="zypper -n packages --unneeded | awk '/^i/{print \$5}' | xargs -r zypper -n rm"
    PKG_AUTOCLEAN="zypper clean --packages"
    PKG_CLEAN="zypper clean --all"
    ;;
  alpine)
    PKG_UPDATE="apk update"
    PKG_AUTOREMOVE=""  # apk handles orphans differently; skip
    PKG_AUTOCLEAN="apk cache clean"
    PKG_CLEAN=""       # same as autoclean
    ;;
  *)
    # Try to infer from ID_LIKE
    if [[ "$DISTRO_LIKE" =~ (debian|ubuntu) ]]; then
      PKG_UPDATE="apt-get update -qq"
      PKG_AUTOREMOVE="apt-get -y autoremove --purge"
      PKG_AUTOCLEAN="apt-get -y autoclean"
      PKG_CLEAN="apt-get -y clean"
    else
      echo "Unsupported distro '$DISTRO_ID'. Skipping package-manager cleanup."
      PKG_UPDATE=""
      PKG_AUTOREMOVE=""
      PKG_AUTOCLEAN=""
      PKG_CLEAN=""
    fi
    ;;
esac

##
## 1) Package‑manager housekeeping
##
if [[ -n "${PKG_UPDATE}" ]]; then
  echo "--> Running package-manager cleanup commands"
  eval "$PKG_UPDATE"
  [[ -n "$PKG_AUTOREMOVE" ]] && eval "$PKG_AUTOREMOVE"
  [[ -n "$PKG_AUTOCLEAN"  ]] && eval "$PKG_AUTOCLEAN"
  [[ -n "$PKG_CLEAN"      ]] && eval "$PKG_CLEAN"
else
  echo "--> No package-manager cleanup configured for this distro"
fi

##
## 2) Systemd journal logs (if available)
##
if command -v journalctl &>/dev/null; then
  echo "--> Vacuuming journal logs"
  journalctl --rotate
  journalctl --vacuum-time=7d
  journalctl --vacuum-size=100M
else
  echo "--> systemd journal not detected, skipping"
fi

##
## 3) Crash reports
##
echo "--> Removing crash dumps"
rm -rf /var/crash/*

##
## 4) Old archived logs
##
echo "--> Truncating and purging old logs"
find /var/log -type f -iname "*.log"    -mtime +7  -exec truncate -s 0 {} \;
find /var/log -type f \( -iname "*.gz" -o -regex ".*\.[0-9]+" \) -mtime +14 -delete

##
## 5) /tmp cleanup
##
echo "--> Cleaning /tmp (files not accessed in >7d)"
find /tmp -type f -atime +7 -delete
find /tmp -type d -empty    -delete

##
## 6) User thumbnail caches
##
echo "--> Clearing user thumbnail caches"
for d in /home/*/.cache/thumbnails; do
  [[ -d "$d" ]] && rm -rf "${d:?}"/{normal,fail,large,*.png,*.jpg}
done

##
## 7) Drop filesystem caches
##
echo "--> Dropping filesystem caches"
echo 3 > /proc/sys/vm/drop_caches

echo "==> Cleanup finished at $(date)"

