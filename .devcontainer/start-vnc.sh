#!/bin/bash
set -e

# Cleanup previous sessions
pkill -f "vncserver" || true
pkill -f "websockify" || true
pkill -f "Xvfb" || true
rm -rf /tmp/.X*
rm -rf ~/.Xauthority

# Setup X11 directories and permissions
sudo mkdir -p /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix

# Setup virtual display
Xvfb :1 -screen 0 1024x768x16 &
export DISPLAY=:1
export XDG_RUNTIME_DIR=/tmp/runtime-vscode

# Setup xauth
touch ~/.Xauthority
xauth generate :1 . trusted

# Create and configure VNC directory
mkdir -p ~/.vnc
echo "${VNC_PASSWORD:-vncpass123}" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Update xstartup
cat > ~/.vnc/xstartup << EOF
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
export XDG_CURRENT_DESKTOP="XFCE"
export DISPLAY=:1

xrdb ~/.Xresources
openbox-session &
startxfce4 &
EOF
chmod +x ~/.vnc/xstartup

# Start VNC server with X11 integration
x11vnc -display :1 -auth ~/.Xauthority -forever -shared -passwd "${VNC_PASSWORD:-vncpass123}" &

# Start noVNC
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

echo "VNC server started with X11 integration"
echo "noVNC interface available at http://localhost:6080"

# Keep the script running
tail -f ~/.vnc/*:1.log