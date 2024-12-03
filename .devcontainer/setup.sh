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
PYTHON_VERSION="3.11"
if ! command -v python$PYTHON_VERSION &> /dev/null; then
    sudo apt-get install -y python$PYTHON_VERSION
fi

# Use specific Python version
python$PYTHON_VERSION -m pip install --upgrade pip wheel setuptools
if [ -f "requirements.txt" ]; then
    python$PYTHON_VERSION -m pip install -r requirements.txt
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

# Function to determine Ollama IP address
get_ollama_ip() {
    # Используем только 172.17.0.1, так как другие адреса не работают
    local ip="172.17.0.1"
    
    # Проверяем доступность сервиса
    local response=$(curl -s -w "%{http_code}" "http://${ip}:11434/api/status")
    local status=$?
    
    if [ $status -eq 0 ]; then
        # Сервис отвечает (даже если 404)
        echo "${ip}"
        return 0
    fi
    
    return 1
}

# Check and wait for Ollama readiness
wait_for_ollama() {
    local max_attempts=30
    local attempt=1
    local wait_time=10
    
    echo "Determining Ollama service IP address..."
    local ollama_ip=$(get_ollama_ip)
    if [ -z "${ollama_ip}" ]; then
        echo "Could not determine Ollama IP address"
        return 1
    fi
    
    echo "Found Ollama service at: ${ollama_ip}"
    export OLLAMA_HOST="${ollama_ip}"
    
    # Так как сервис отвечает, можно продолжить
    return 0
}

# Инициализация переменных окружения Ollama
export OLLAMA_HOST="172.17.0.1"
export OLLAMA_API_BASE_URL="http://172.17.0.1:11434"
export OLLAMA_API_PORT=11434

# Исправленная функция проверки подключения к API
check_ollama_connection() {
    echo "Testing Ollama API..."
    local api_url="http://${OLLAMA_HOST}:${OLLAMA_API_PORT}/api/version"
    echo "Trying to connect to: ${api_url}"
    
    local response=$(curl -s "${api_url}")
    local exit_code=$?
    
    echo "Curl exit code: ${exit_code}"
    echo "Response: ${response}"
    
    if [ ${exit_code} -eq 0 ] && [ -n "${response}" ]; then
        echo "✅ Ollama API connection successful"
        return 0
    else
        echo "❌ Failed to connect to Ollama API"
        return 1
    fi
}

# Функция проверки модели
check_model() {
    local model=$2
    echo "Checking model ${model} availability..."
    
    # Добавляем -v для подробного вывода
    local response=$(curl -v -s "${OLLAMA_API_BASE_URL}/api/show" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${model}\"}" 2>&1)
    
    echo "API Response: ${response}"
    
    if echo "${response}" | grep -q "success"; then
        return 0
    else
        return 1
    fi
}

# Функция загрузки модели
pull_model() {
    local model=$2
    echo "Pulling model: ${model}"
    
    # Добавляем -v для подробного вывода
    local response=$(curl -v -s "${OLLAMA_API_BASE_URL}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${model}\"}" 2>&1)
    
    echo "API Response: ${response}"
    
    if echo "${response}" | grep -q "success"; then
        return 0
    else
        return 1
    fi
}

# Wait for Ollama service to be ready
if ! wait_for_ollama; then
    echo "Failed to connect to Ollama service"
    exit 1
fi

# Проверка подключения к API
if ! check_ollama_connection; then
    echo "❌ Cannot proceed with model setup - Ollama API is not accessible"
    exit 1
fi

# Создаем функцию для работы с моделями
setup_ollama_models() {
    local models=("deepseek-coder-v2:latest" "nomic-embed-text:latest" "qwen2.5-coder:7b")
    
    echo -e "\n=== Pulling Ollama Models ==="
    for model in "${models[@]}"; do
        echo "Testing model: ${model}"
        if check_model "${OLLAMA_HOST}" "${model}"; then
            echo "✅ Model ${model} check successful"
        else
            echo "❌ Model ${model} check failed"
            
            echo "Attempting to pull model ${model}..."
            if pull_model "${OLLAMA_HOST}" "${model}"; then
                echo "✅ Model ${model} pulled successfully"
            else
                echo "❌ Failed to pull model ${model}"
            fi
        fi
    done
    echo -e "\n=== Model Setup Complete ==="
}

# Запускаем настройку моделей
setup_ollama_models

# Configure Ollama environment variables
{
    echo "export OLLAMA_API_HOST=${OLLAMA_HOST}"
    echo 'export OLLAMA_API_PORT=11434'
    echo "export OLLAMA_API_BASE_URL=http://${OLLAMA_HOST}:11434"
} >> ~/.bashrc

# Configure Git
git config --global user.email "oleg12203@gmail.com"
git config --global user.name "Oleg Kizyma"