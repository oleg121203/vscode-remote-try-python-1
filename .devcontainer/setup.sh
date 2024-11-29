#!/bin/bash
set -e

# Add error handling
trap 'echo "Error on line $LINENO"' ERR

# Ensure X11 permissions
sudo mkdir -p /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix
sudo chown root:root /tmp/.X11-unix

# Create temp directory
mkdir -p .devcontainer/temp

# Set proper permissions for all scripts in .devcontainer
echo "Setting up script permissions..."
find .devcontainer -name "*.sh" -type f -exec chmod +x {} \;
ls -la .devcontainer/*.sh

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

# Update runtime directory permissions
sudo mkdir -p /tmp/runtime-vscode
sudo chown vscode:vscode /tmp/runtime-vscode
sudo chmod 700 /tmp/runtime-vscode

# Ensure X11 directory exists
sudo mkdir -p /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix

# Cleanup
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*

# Setup Python environment
echo 'export PATH="/home/vscode/.local/bin:$PATH"' >> ~/.bashrc
python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip install -r requirements.txt

# Node.js setup
echo "Setting up Node.js..."
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs=18.18.0*
fi

# Create symlink if needed
if [ ! -f "/usr/local/bin/node" ]; then
    sudo ln -s /usr/bin/node /usr/local/bin/node
fi

# Verify Node.js installation
bash .devcontainer/verify-node.sh

# Configure Ollama
echo "Checking Ollama service..."
until curl -s http://localhost:11434/api/health >/dev/null; do
    echo "Waiting for Ollama service..."
    sleep 2
done
echo "Ollama service is ready"

# Configure git
git config --global user.email "oleg12203@gmail.com"
git config --global user.name "Oleg Kizyma"