#!/bin/bash

# Function to check if a package is installed
check_and_install() {
    if ! dpkg -l | grep -q "$1"; then
        echo "Installing $1..."
        sudo apt update && sudo apt install -y "$1"
    else
        echo "$1 is already installed."
    fi
}

# Install necessary tools
check_and_install "gnome-tweaks"
check_and_install "qt5ct"

# Install Qogir-Dark theme
if [ ! -d "$HOME/.themes/Qogir-Dark" ]; then
    echo "Downloading and installing Qogir-Dark theme..."
    git clone https://github.com/vinceliuice/Qogir-theme.git /tmp/Qogir-theme
    cd /tmp/Qogir-theme
    ./install.sh -d
    ./install.sh -i
    cd -
    rm -rf /tmp/Qogir-theme
else
    echo "Qogir-Dark theme is already installed."
fi

# Configure GTK theme
mkdir -p ~/.config/gtk-3.0
cat > ~/.config/gtk-3.0/settings.ini <<EOL
[Settings]
gtk-theme-name=Qogir-Dark
gtk-icon-theme-name=Qogir-Dark
gtk-font-name=DejaVu Sans Mono Book 11
gtk-cursor-theme-name=Qogir-Dark
gtk-shell-theme-name=Qogir-Dark
EOL

echo "GTK theme set to Qogir-Dark."

# Configure Qt theme
mkdir -p ~/.config/qt5ct
cat > ~/.config/qt5ct/qt5ct.conf <<EOL
[Appearance]
style=Qogir-Dark
color_scheme=Qogir-Dark
icon_theme=Qogir-Dark
EOL

# Ensure environment variables are set for Qt
if ! grep -q "QT_QPA_PLATFORMTHEME=qt5ct" ~/.profile; then
    echo "export QT_QPA_PLATFORMTHEME=qt5ct" >> ~/.profile
    echo "export QT_STYLE_OVERRIDE=Qogir-Dark" >> ~/.profile
    echo "export QT_QTA_PLATFORM=x11" >> ~/.profile
    echo "Environment variables set for Qt."
else
    echo "Environment variables for Qt already set."
fi

# Adjust for GNOME 43.9 specific configuration
if [ -f /usr/bin/gsettings ]; then
    echo "Setting GNOME shell theme to Qogir-Dark..."
    gsettings set org.gnome.desktop.interface gtk-theme "Qogir-Dark"
    gsettings set org.gnome.desktop.interface icon-theme "Qogir-Dark"
    gsettings set org.gnome.desktop.interface cursor-theme "Qogir-Dark"
    gsettings set org.gnome.desktop.interface font-name "DejaVu Sans Mono Book 11"
    gsettings set org.gnome.shell.extensions.user-theme name "Qogir-Dark"
    echo "GNOME shell theme configured for Qogir-Dark."
else
    echo "gsettings not found; skipping GNOME shell theme configuration."
fi

# Prompt the user to restart their session
echo "Setup complete! Please restart your session or log out and log back in for changes to take effect."
