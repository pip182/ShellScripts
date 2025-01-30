#!/bin/bash

# Define the URL
url="https://downloader.cursor.sh/linux/appImage/x64"

# Temporary filename to ensure consistent handling
temp_file="cursor_temp.AppImage"

killall -9 cursor
cd ~/.local/bin/

# Remove any existing temporary download file
rm -f "$temp_file"

# Download the latest AppImage and save it as a temporary file
if ! curl -L -o "$temp_file" "$url"; then
    echo "Download failed."
    rm -f "$temp_file"  # Cleanup temp file if the download failed
    exit 1
fi

# Ensure the file actually exists and is not empty
if [[ ! -s "$temp_file" ]]; then
    echo "Download completed but file is empty."
    rm -f "$temp_file"  # Cleanup temp file if it's empty
    exit 1
fi

# Remove the existing cursor.AppImage if it exists
rm -f cursor.AppImage

# Rename the downloaded file
mv "$temp_file" cursor.AppImage

# Make the new file executable
chmod +x cursor.AppImage

echo "Cursor AI updated successfully."
