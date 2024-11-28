#!/bin/bash
set -e

# Setup VNC
mkdir -p ~/.vnc
echo "${VNC_PASSWORD:-password}" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Kill existing VNC sessions
vncserver -kill :1 2>/dev/null || true

# Setup runtime directory
mkdir -p /tmp/runtime-vscode
sudo chmod 700 /tmp/runtime-vscode

# Start VNC server with specific geometry
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no

# Start noVNC
pkill -f "websockify" || true
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

# Wait for services to start
sleep 2

export DISPLAY=:1
mkdir -p /tmp/runtime-vscode
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901