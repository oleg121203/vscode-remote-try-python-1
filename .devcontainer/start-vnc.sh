#!/bin/bash
set -e

# Add error handling
trap 'echo "Error on line $LINENO"' ERR

# Ensure runtime directory exists with proper permissions
mkdir -p /tmp/runtime-vscode
sudo chmod 700 /tmp/runtime-vscode

# Kill existing processes
pkill -f "vncserver" || true
pkill -f "websockify" || true

# Setup VNC
mkdir -p ~/.vnc
echo "${VNC_PASSWORD:-password}" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Start VNC server with specific geometry
export DISPLAY=:1
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no -SecurityTypes None

# Start noVNC with proper host binding
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

# Check Ollama service
for i in {1..5}; do
    if curl -s http://172.17.0.1:11434/api/health >/dev/null; then
        echo "Ollama service is available"
        break
    fi
    echo "Attempt $i: Waiting for Ollama service..."
    sleep 2
done

# Wait for VNC server to fully start
sleep 2

echo "VNC and noVNC services started successfully"