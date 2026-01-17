#!/bin/bash

# Enable error handling
set -e

# Function to run command with error checking
run_cmd() {
    local cmd="$*"
    if ! eval "$cmd"; then
        echo "❌ Command failed: $cmd"
        return 1
    fi
    return 0
}

# Cleanup function for error handling
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "❌ Script failed! Cleaning up..."
        umount "${MOUNT_NTFS:-}" 2>/dev/null || true
        umount "${MOUNT_VFAT:-}" 2>/dev/null || true
        umount "${MOUNT_ISO:-}" 2>/dev/null || true
        echo "⚠️  Please manually check and clean up if needed."
    fi
    exit $exit_code
}

trap cleanup EXIT

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# ===============================
# Bootable Windows USB Creator
# ===============================

# --- CONFIGURATION ---
DOWNLOADS_DIR="/home/brad/Downloads"
MOUNT_ISO="/mnt/iso"
MOUNT_VFAT="/mnt/vfat"
MOUNT_NTFS="/mnt/ntfs"

# --- CHECK REQUIRED TOOLS ---
check_dependencies() {
    local missing_tools=()

    for tool in parted mkfs.vfat mkfs.ntfs rsync mount umount sync; do
        if ! command -v "$tool" &>/dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo "❌ Missing required tools: ${missing_tools[*]}"
        echo "   Please install them and try again."
        exit 1
    fi
}

check_dependencies

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

# --- FUNCTION TO SELECT BOOT MODE ---
select_boot_mode() {
    echo ""
    echo "🔧 Select boot mode:"
    echo "[1] UEFI (GPT partition table) - Recommended for modern systems"
    echo "[2] MBR (Legacy BIOS) - For older systems"
    echo ""
    read -p "Enter your choice (1 or 2): " BOOT_MODE_CHOICE

    case $BOOT_MODE_CHOICE in
        1)
            BOOT_MODE="UEFI"
            PARTITION_TABLE="gpt"
            echo "✅ Selected: UEFI (GPT)"
            ;;
        2)
            BOOT_MODE="MBR"
            PARTITION_TABLE="msdos"
            echo "✅ Selected: MBR (Legacy BIOS)"
            ;;
        *)
            echo "❌ Invalid selection! Defaulting to UEFI."
            BOOT_MODE="UEFI"
            PARTITION_TABLE="gpt"
            ;;
    esac
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

# --- SELECT BOOT MODE ---
select_boot_mode

# --- SELECT USB DEVICE ---
select_usb_device

# --- VERIFY ISO FILE ---
echo "🔍 Checking SHA256 checksum of the ISO..."
sha256sum "$ISO_PATH"

echo "✅ Ensure the checksum matches the official value!"

# --- UNMOUNT USB DEVICE (IF MOUNTED) ---
echo "  Unmounting existing USB partitions..."
# Unmount all partitions on the device (ignore errors if not mounted)
for partition in "${USB_DEVICE}"*; do
    if [ -b "$partition" ] && [ "$partition" != "$USB_DEVICE" ]; then
        umount "$partition" 2>/dev/null || true
    fi
done

# Check if device is still in use (optional check)
if command -v lsof &>/dev/null; then
    if lsof "$USB_DEVICE" 2>/dev/null | grep -q .; then
        echo "⚠️  Warning: Device may still be in use"
        echo "   Attempting to continue..."
    fi
fi

# --- FORMAT USB AND CREATE PARTITIONS ---
echo "  Formatting USB device: $USB_DEVICE"
echo "  Using $BOOT_MODE mode with $PARTITION_TABLE partition table"

# Unmount and wipe
echo "  Wiping existing partition table..."
# wipefs may fail if there's nothing to wipe, which is okay - continue anyway
set +e  # Temporarily disable exit on error for wipefs
wipefs -a "$USB_DEVICE" 2>&1
wipefs_exit=$?
set -e  # Re-enable exit on error
if [ $wipefs_exit -ne 0 ]; then
    echo "  (Note: wipefs returned error, but continuing - device may be clean)"
fi

# Create partition table
echo "  Creating $PARTITION_TABLE partition table..."
if ! parted "$USB_DEVICE" --script mklabel "$PARTITION_TABLE"; then
    echo "❌ Failed to create partition table"
    exit 1
fi

# Create partitions based on boot mode
if [ "$BOOT_MODE" = "UEFI" ]; then
    # UEFI: Create EFI System Partition (ESP) with proper type code
    echo "  Creating EFI System Partition..."
    if ! parted "$USB_DEVICE" --script mkpart BOOT fat32 0% 1GiB; then
        echo "❌ Failed to create boot partition"
        exit 1
    fi
    if ! parted "$USB_DEVICE" --script set 1 esp on; then
        echo "❌ Failed to set ESP flag"
        exit 1
    fi
    echo "✅ Created EFI System Partition (ESP) for UEFI boot"
else
    # MBR: Create boot partition and set boot flag
    echo "  Creating boot partition for MBR..."
    if ! parted "$USB_DEVICE" --script mkpart primary fat32 0% 1GiB; then
        echo "❌ Failed to create boot partition"
        exit 1
    fi
    if ! parted "$USB_DEVICE" --script set 1 boot on; then
        echo "⚠️  Warning: Failed to set boot flag (may not be critical)"
    fi
    echo "✅ Created boot partition with boot flag for MBR/BIOS"
fi

# Create install partition
echo "  Creating install partition..."
if ! parted "$USB_DEVICE" --script mkpart primary ntfs 1GiB 100%; then
    echo "❌ Failed to create install partition"
    exit 1
fi

# Wait for kernel to recognize partitions
echo "  Waiting for partitions to be recognized..."
sleep 2
partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 1

# --- VERIFY PARTITION TABLE ---
echo "  Checking partition layout..."
parted "$USB_DEVICE" unit B print

# Verify partitions exist
if [ ! -b "$BOOT_PARTITION" ] || [ ! -b "$INSTALL_PARTITION" ]; then
    echo "❌ Error: Partitions not created correctly!"
    exit 1
fi

# --- FUNCTION TO CHECK INSTALL.WIM SIZE ---
check_install_wim_size() {
    local mount_point="$1"
    local install_wim=""

    # Check for install.wim or install.esd
    if [ -f "$mount_point/sources/install.wim" ]; then
        install_wim="$mount_point/sources/install.wim"
    elif [ -f "$mount_point/sources/install.esd" ]; then
        install_wim="$mount_point/sources/install.esd"
    else
        echo "⚠️  Warning: Could not find install.wim or install.esd"
        return 0
    fi

    # Get file size in bytes
    local file_size=$(stat -c%s "$install_wim" 2>/dev/null || stat -f%z "$install_wim" 2>/dev/null)
    local size_gb=$((file_size / 1073741824))

    echo "  Install file size: ${size_gb}GB ($(basename "$install_wim"))"

    # FAT32 has 4GB file size limit
    if [ "$file_size" -gt 4294967295 ]; then
        echo "⚠️  Warning: Install file exceeds 4GB FAT32 limit!"
        echo "   The file will be copied to NTFS partition (INSTALL), which is fine."
        if [ "$BOOT_MODE" = "MBR" ]; then
            echo "   For MBR/BIOS boot, this is not a problem as boot files are on FAT32 partition."
        else
            echo "   For UEFI boot, ensure your firmware supports NTFS or use FAT32 with split WIM."
        fi
    fi

    return 0
}

# --- FUNCTION TO VERIFY BOOT FILES ---
verify_boot_files() {
    local mount_point="$1"
    local boot_ok=true

    # Check for EFI boot files (required for UEFI)
    if [ "$BOOT_MODE" = "UEFI" ]; then
        if [ ! -f "$mount_point/EFI/BOOT/bootx64.efi" ] && [ ! -f "$mount_point/EFI/Microsoft/Boot/bootmgfw.efi" ]; then
            echo "⚠️  Warning: EFI boot files not found in expected locations"
            echo "   Looking for: EFI/BOOT/bootx64.efi or EFI/Microsoft/Boot/bootmgfw.efi"
            boot_ok=false
        else
            echo "✅ EFI boot files found"
        fi
    fi

    # Check for MBR boot files (required for BIOS)
    if [ "$BOOT_MODE" = "MBR" ]; then
        if [ ! -f "$mount_point/bootmgr" ] && [ ! -f "$mount_point/boot/bootmgr" ]; then
            echo "⚠️  Warning: bootmgr not found (required for MBR/BIOS boot)"
            boot_ok=false
        else
            echo "✅ bootmgr found"
        fi
    fi

    # Check for boot.wim (required for both)
    if [ ! -f "$mount_point/sources/boot.wim" ]; then
        echo "⚠️  Warning: boot.wim not found in sources/"
        boot_ok=false
    else
        echo "✅ boot.wim found"
    fi

    if [ "$boot_ok" = false ]; then
        echo "⚠️  Some boot files are missing. The USB may not boot correctly."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# --- FUNCTION TO DETECT WINDOWS VERSION ---
detect_windows_version() {
    local mount_point="$1"
    WINDOWS_VERSION="Unknown"
    WINDOWS_BUILD=""

    # Method 1: Check sources/idwbinfo.txt (most reliable)
    if [ -f "$mount_point/sources/idwbinfo.txt" ]; then
        WINDOWS_BUILD=$(grep -i "Build" "$mount_point/sources/idwbinfo.txt" 2>/dev/null | head -1 | grep -oE '[0-9]{5}' | head -1)
        if [ -n "$WINDOWS_BUILD" ]; then
            # Windows 11 builds start from 22000
            if [ "$WINDOWS_BUILD" -ge 22000 ]; then
                WINDOWS_VERSION="Windows 11"
            else
                WINDOWS_VERSION="Windows 10"
            fi
            return 0
        fi
    fi

    # Method 2: Check install.wim using wiminfo if available
    if command -v wiminfo &>/dev/null && [ -f "$mount_point/sources/install.wim" ]; then
        WINDOWS_BUILD=$(wiminfo "$mount_point/sources/install.wim" 1 2>/dev/null | grep -i "Build" | grep -oE '[0-9]{5}' | head -1)
        if [ -n "$WINDOWS_BUILD" ]; then
            if [ "$WINDOWS_BUILD" -ge 22000 ]; then
                WINDOWS_VERSION="Windows 11"
            else
                WINDOWS_VERSION="Windows 10"
            fi
            return 0
        fi
    fi

    # Method 3: Check install.esd using wiminfo if available
    if command -v wiminfo &>/dev/null && [ -f "$mount_point/sources/install.esd" ]; then
        WINDOWS_BUILD=$(wiminfo "$mount_point/sources/install.esd" 1 2>/dev/null | grep -i "Build" | grep -oE '[0-9]{5}' | head -1)
        if [ -n "$WINDOWS_BUILD" ]; then
            if [ "$WINDOWS_BUILD" -ge 22000 ]; then
                WINDOWS_VERSION="Windows 11"
            else
                WINDOWS_VERSION="Windows 10"
            fi
            return 0
        fi
    fi

    # Method 4: Check for Windows 11 specific files/directories
    if [ -d "$mount_point/sources/Windows11" ] || [ -f "$mount_point/sources/Windows11" ]; then
        WINDOWS_VERSION="Windows 11"
        return 0
    fi

    # Method 5: Check setup.exe version info (fallback)
    if [ -f "$mount_point/setup.exe" ]; then
        # Try to extract version info from setup.exe
        local version_info=$(strings "$mount_point/setup.exe" 2>/dev/null | grep -E "10\.0\.[0-9]{5}" | head -1)
        if [ -n "$version_info" ]; then
            WINDOWS_BUILD=$(echo "$version_info" | grep -oE '[0-9]{5}' | head -1)
            if [ -n "$WINDOWS_BUILD" ] && [ "$WINDOWS_BUILD" -ge 22000 ]; then
                WINDOWS_VERSION="Windows 11"
            elif [ -n "$WINDOWS_BUILD" ]; then
                WINDOWS_VERSION="Windows 10"
            fi
        fi
    fi

    # Default fallback
    if [ "$WINDOWS_VERSION" = "Unknown" ]; then
        echo "⚠️  Could not detect Windows version, assuming Windows 10/11"
        WINDOWS_VERSION="Windows 10/11"
    fi
}

# --- MOUNT WINDOWS ISO ---
echo "  Mounting Windows ISO..."
mkdir -p "$MOUNT_ISO"
mount "$ISO_PATH" "$MOUNT_ISO"

# --- DETECT WINDOWS VERSION ---
echo "🔍 Detecting Windows version..."
detect_windows_version "$MOUNT_ISO"
if [ -n "$WINDOWS_BUILD" ]; then
    echo "✅ Detected: $WINDOWS_VERSION (Build $WINDOWS_BUILD)"
else
    echo "✅ Detected: $WINDOWS_VERSION"
fi

# --- CHECK INSTALL FILE SIZE ---
echo "🔍 Checking install file size..."
check_install_wim_size "$MOUNT_ISO"

# --- VERIFY BOOT FILES ---
echo "🔍 Verifying boot files..."
verify_boot_files "$MOUNT_ISO"

# --- FORMAT BOOT PARTITION (FAT32) ---
echo "  Formatting BOOT partition as FAT32..."
mkfs.vfat -F 32 -n BOOT "$BOOT_PARTITION"
sync
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
sync
mkdir -p "$MOUNT_NTFS"
mount "$INSTALL_PARTITION" "$MOUNT_NTFS"

# --- COPY FULL WINDOWS ISO TO NTFS PARTITION ---
echo "  Copying full Windows ISO content to INSTALL partition..."
rsync -r --progress --delete-before "$MOUNT_ISO/" "$MOUNT_NTFS/"

# --- UNMOUNT EVERYTHING ---
echo "  Syncing all data to disk..."
sync
sync  # Double sync to ensure all data is written

echo "  Unmounting partitions..."
umount "$MOUNT_NTFS" || { echo "⚠️  Warning: Failed to unmount NTFS partition"; }
umount "$MOUNT_VFAT" || { echo "⚠️  Warning: Failed to unmount FAT32 partition"; }
umount "$MOUNT_ISO" || { echo "⚠️  Warning: Failed to unmount ISO"; }
sync

# --- SAFELY REMOVE USB ---
echo "  Safely ejecting USB drive..."
udisksctl power-off -b "$USB_DEVICE"

echo "✅ Bootable $WINDOWS_VERSION USB created successfully!"
