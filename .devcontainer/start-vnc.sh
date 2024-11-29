#!/bin/bash
set -e

# Cleanup previous sessions
pkill -f "vncserver" || true
pkill -f "websockify" || true
rm -rf /tmp/.X*
rm -rf ~/.Xauthority

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

# Ensure proper window manager startup
xrdb ~/.Xresources
openbox-session &
startxfce4 &
EOF
chmod +x ~/.vnc/xstartup

# Start VNC server
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no \
    -SecurityTypes VncAuth \
    -PasswordFile ~/.vnc/passwd \
    -xstartup ~/.vnc/xstartup

# Wait for VNC to start
sleep 5

# Start noVNC
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

echo "VNC server started on port 5901"
echo "noVNC interface available at http://localhost:6080"

# Keep the script running
tail -f ~/.vnc/*:1.log