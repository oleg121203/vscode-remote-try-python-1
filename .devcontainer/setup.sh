#!/bin/bash
set -e

# Create temp directory
mkdir -p .devcontainer/temp

# Install system packages
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    xfce4 \
    xfce4-terminal \
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

# Setup VNC config
mkdir -p ~/.vnc
cat > ~/.vnc/config << EOF
geometry=1920x1080
depth=24
EOF

cat > ~/.vnc/xstartup << EOF
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
export XDG_CURRENT_DESKTOP="XFCE"
startxfce4 &
EOF
chmod 755 ~/.vnc/xstartup

echo "export DISPLAY=:1" >> ~/.bashrc
echo "export XDG_RUNTIME_DIR=/tmp/runtime-vscode" >> ~/.bashrc

# Cleanup
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*

# Setup Python environment
echo 'export PATH="/home/vscode/.local/bin:$PATH"' >> ~/.bashrc
python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip install -r requirements.txt

# Configure Ollama
echo "Waiting for Ollama service..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:11434/api/health >/dev/null; then
        echo "Ollama service is ready"
        break
    fi
    echo "Attempt $i: Ollama service not ready, waiting..."
    sleep 2
done

# Configure git
git config --global user.email "oleg12203@gmail.com"
git config --global user.name "Oleg Kizyma"