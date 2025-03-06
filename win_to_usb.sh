#!/bin/bash

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# ===============================
# Bootable Windows 11 USB Creator
# ===============================

# --- CONFIGURATION ---
DOWNLOADS_DIR="/home/brad/Downloads"
MOUNT_ISO="/mnt/iso"
MOUNT_VFAT="/mnt/vfat"
MOUNT_NTFS="/mnt/ntfs"

# --- FUNCTION TO SELECT WINDOWS ISO ---
select_iso() {
    echo "🔍 Searching for ISO files in $DOWNLOADS_DIR..."

    # Find ISO files and store them in an array
    IFS=$'\n' ISO_FILES=($(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.iso" | sort))

    if [ ${#ISO_FILES[@]} -eq 0 ]; then
        echo "❌ No ISO files found in $DOWNLOADS_DIR!"
        exit 1
    fi

    echo "  Available ISO files:"
    for i in "${!ISO_FILES[@]}"; do
        echo "[$i] ${ISO_FILES[$i]}"
    done

    echo ""
    read -p "Enter the number of the ISO you want to use: " ISO_INDEX

    if [[ ! $ISO_INDEX =~ ^[0-9]+$ ]] || [ $ISO_INDEX -ge ${#ISO_FILES[@]} ]; then
        echo "❌ Invalid selection!"
        exit 1
    fi

    ISO_PATH="${ISO_FILES[$ISO_INDEX]}"
    echo "✅ Selected ISO: \"$ISO_PATH\""
}

# --- FUNCTION TO SELECT USB DEVICE ---
select_usb_device() {
    echo "🔍 Detecting storage devices..."
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep "disk"

    echo ""
    read -p "Enter the USB device name (e.g., sdb, sde): " USB_DEVICE

    if [ ! -b "/dev/$USB_DEVICE" ]; then
        echo "❌ Invalid device! Please check and try again."
        exit 1
    fi

    USB_DEVICE="/dev/$USB_DEVICE"
    BOOT_PARTITION="${USB_DEVICE}1"
    INSTALL_PARTITION="${USB_DEVICE}2"

    echo "⚠ You have selected: $USB_DEVICE"
    read -p "Press Enter to continue or Ctrl+C to abort..."
}

# --- SELECT WINDOWS ISO ---
select_iso

# --- SELECT USB DEVICE ---
select_usb_device

# --- VERIFY ISO FILE ---
echo "🔍 Checking SHA256 checksum of the ISO..."
sha256sum "$ISO_PATH"

echo "✅ Ensure the checksum matches the official value!"

# --- UNMOUNT USB DEVICE (IF MOUNTED) ---
echo "  Unmounting existing USB partitions..."
umount "${USB_DEVICE}"* &>/dev/null

# --- FORMAT USB AND CREATE PARTITIONS ---
echo "  Formatting USB device: $USB_DEVICE"
wipefs -a "$USB_DEVICE"

parted "$USB_DEVICE" --script mklabel gpt
parted "$USB_DEVICE" --script mkpart BOOT fat32 0% 1GiB
parted "$USB_DEVICE" --script mkpart INSTALL ntfs 1GiB 100%

# --- VERIFY PARTITION TABLE ---
echo "  Checking partition layout..."
parted "$USB_DEVICE" unit B print

# --- MOUNT WINDOWS ISO ---
echo "  Mounting Windows 11 ISO..."
mkdir -p "$MOUNT_ISO"
mount "$ISO_PATH" "$MOUNT_ISO"

# --- FORMAT BOOT PARTITION (FAT32) ---
echo "  Formatting BOOT partition as FAT32..."
mkfs.vfat -n BOOT "$BOOT_PARTITION"
mkdir -p "$MOUNT_VFAT"
mount "$BOOT_PARTITION" "$MOUNT_VFAT"

# --- COPY WINDOWS FILES (EXCLUDING sources FOLDER) ---
echo "  Copying Windows installation files (excluding 'sources')..."
rsync -r --progress --exclude sources --delete-before "$MOUNT_ISO/" "$MOUNT_VFAT/"

# --- COPY boot.wim FILE ---
echo "📥 Copying 'boot.wim' to BOOT partition..."
mkdir -p "$MOUNT_VFAT/sources"
cp "$MOUNT_ISO/sources/boot.wim" "$MOUNT_VFAT/sources/"

# --- FORMAT INSTALL PARTITION (NTFS) ---
echo "🖴 Formatting INSTALL partition as NTFS..."
mkfs.ntfs --quick -L INSTALL "$INSTALL_PARTITION"
mkdir -p "$MOUNT_NTFS"
mount "$INSTALL_PARTITION" "$MOUNT_NTFS"

# --- COPY FULL WINDOWS ISO TO NTFS PARTITION ---
echo "  Copying full Windows ISO content to INSTALL partition..."
rsync -r --progress --delete-before "$MOUNT_ISO/" "$MOUNT_NTFS/"

# --- UNMOUNT EVERYTHING ---
echo "  Unmounting partitions..."
umount "$MOUNT_NTFS"
umount "$MOUNT_VFAT"
umount "$MOUNT_ISO"
sync

# --- SAFELY REMOVE USB ---
echo "  Safely ejecting USB drive..."
udisksctl power-off -b "$USB_DEVICE"

echo "✅ Bootable Windows 11 USB created successfully!"
