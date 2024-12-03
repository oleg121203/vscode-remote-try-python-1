#!/bin/bash
set -e

# Improved error handling
trap 'echo "Error on line $LINENO. Exit code: $?"' ERR

# Create necessary directories with correct permissions
sudo mkdir -p /tmp/runtime-vscode
sudo chown vscode:vscode /tmp/runtime-vscode
sudo chmod 700 /tmp/runtime-vscode

sudo mkdir -p /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix
sudo chown root:root /tmp/.X11-unix

# Set up script permissions
echo "Setting up script permissions..."
find .devcontainer -name "*.sh" -type f -exec chmod +x {} \;

# Install system packages
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    xfce4 \
    xfce4-terminal \
    tigervnc-standalone-server \
    tigervnc-common \
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
    qtbase5-dev \
    libqt5gui5 \
    libqt5widgets5 \
    libqt5core5a \
    libqt5dbus5

# Setup VNC configuration
mkdir -p ~/.vnc
cat > ~/.vnc/config << EOF
geometry=1920x1080
depth=24
EOF

cat > ~/.vnc/xstartup << 'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
export XDG_CURRENT_DESKTOP="XFCE"
startxfce4 &
EOF
chmod 755 ~/.vnc/xstartup

# Update environment variables
{
    echo 'export DISPLAY=:1'
    echo 'export XDG_RUNTIME_DIR=/tmp/runtime-vscode'
    echo 'export PATH="/home/vscode/.local/bin:$PATH"'
} >> ~/.bashrc

# Cleanup
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*

# Setup Python environment
python3 -m pip install --upgrade pip wheel setuptools
if [ -f "requirements.txt" ]; then
    python3 -m pip install -r requirements.txt
fi

# Node.js setup
echo "Setting up Node.js..."
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs=18.18.0*
fi

# Create symlink for Node.js if needed
if [ ! -f "/usr/local/bin/node" ]; then
    sudo ln -s /usr/bin/node /usr/local/bin/node
fi

# Verify Node.js installation
bash .devcontainer/verify-node.sh

# Check Ollama service availability
echo "Checking Ollama service..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s http://172.17.0.1:11434/api/health >/dev/null; do
    echo "Waiting for Ollama service... (${RETRY_COUNT}/${MAX_RETRIES})"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "Ollama service not available after ${MAX_RETRIES} retries"
        exit 1
    fi
    sleep 2
done
echo "Ollama service is ready"

# Pull Ollama models
echo "Pulling Ollama models..."
MODELS=(
    'deepseek-coder-v2:latest'
    'nomic-embed-text:latest'
    'qwen2.5-coder:7b'
    'qwen2.5-coder:1.5b'
    'llama3.1:latest'
)

for model in "${MODELS[@]}"; do
    echo "Pulling model: $model"
    if curl --output /dev/null --silent --head --fail http://172.17.0.1:11434/api/pull; then
        curl -X POST http://172.17.0.1:11434/api/pull -d "{\"name\":\"$model\"}"
        echo "Successfully pulled $model"
    else
        echo "Failed to pull $model - API not available"
    fi
done

# Configure Ollama environment variables
{
    echo 'export OLLAMA_API_HOST=172.17.0.1'
    echo 'export OLLAMA_API_PORT=11434'
    echo 'export OLLAMA_API_BASE_URL=http://172.17.0.1:11434'
} >> ~/.bashrc

# Configure Git
git config --global user.email "oleg12203@gmail.com"
git config --global user.name "Oleg Kizyma"