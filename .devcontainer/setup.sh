#!/bin/bash
set -e

# Create temp directory
mkdir -p .devcontainer/temp

# Install system packages
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    default-mysql-client \
    tigervnc-standalone-server \
    tigervnc-common \
    tigervnc-tools \
    novnc \
    websockify \
    openbox \
    x11-xserver-utils \
    xauth \
    net-tools \
    python3-venv \
    python3-dev \
    build-essential \
    fonts-liberation \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    qdbus-qt6 \
    libqt6gui6 \
    libqt6widgets6 \
    libqt6core6 \
    libqt6dbus6

# Cleanup
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*

# Setup Python environment
echo 'export PATH="/home/vscode/.local/bin:$PATH"' >> ~/.bashrc
python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip install -r requirements.txt

# Configure git
git config --global user.email "oleg12203@gmail.com"
git config --global user.name "Oleg Kizyma"