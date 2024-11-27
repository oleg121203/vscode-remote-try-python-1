#!/bin/bash
set -e

# Setup VNC
mkdir -p ~/.vnc
echo "${VNC_PASSWORD:-password}" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Setup runtime directory
mkdir -p /tmp/runtime-vscode
sudo chmod 700 /tmp/runtime-vscode

# Start VNC server
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no

# Start noVNC
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

# Wait for services to start
sleep 2