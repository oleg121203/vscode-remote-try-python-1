
#!/bin/bash
set -e

# Глобальные переменные
DISPLAY_NUM=":1"
VNC_GEOMETRY="1920x1080"
VNC_DEPTH="24"

# Функции управления зависимостями
check_dependencies() {
    echo "Проверка зависимостей..."
    REQUIRED_PKGS="xfce4 xfce4-terminal tigervnc-standalone-server novnc websockify openbox"
    for pkg in $REQUIRED_PKGS; do
        if ! dpkg -l | grep -q "^ii.*$pkg"; then
            echo "Установка $pkg..."
            sudo apt-get update && sudo apt-get install -y $pkg
        fi
    done
}

# Функции управления X11
setup_x11() {
    echo "Настройка X11..."
    sudo mkdir -p /tmp/.X11-unix
    sudo chmod 1777 /tmp/.X11-unix
    sudo chown root:root /tmp/.X11-unix
    
    # Очистка старых сокетов
    sudo rm -f /tmp/.X11-unix/X*
    
    # Настройка авторизации
    touch ~/.Xauthority
    xauth generate $DISPLAY_NUM . trusted
}

# Функции управления VNC
setup_vnc() {
    echo "Настройка VNC..."
    mkdir -p ~/.vnc
    
    # Настройка пароля VNC
    echo "${VNC_PASSWORD:-vncpass123}" | vncpasswd -f > ~/.vnc/passwd
    chmod 600 ~/.vnc/passwd
    
    # Создание конфигурации VNC
    cat > ~/.vnc/config << EOF
geometry=$VNC_GEOMETRY
depth=$VNC_DEPTH
EOF

    # Создание скрипта запуска
    cat > ~/.vnc/xstartup << EOF
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
export XDG_CURRENT_DESKTOP="XFCE"
export DISPLAY=$DISPLAY_NUM

xrdb ~/.Xresources
openbox-session &
startxfce4 &
EOF
    chmod +x ~/.vnc/xstartup
}

# Функции управления сервисами
start_services() {
    # Остановка существующих процессов
    pkill -f "vncserver" || true
    pkill -f "websockify" || true
    
    # Запуск VNC сервера
    vncserver $DISPLAY_NUM -geometry $VNC_GEOMETRY -depth $VNC_DEPTH -localhost no \
        -SecurityTypes VncAuth \
        -PasswordFile ~/.vnc/passwd \
        -xstartup ~/.vnc/xstartup
    
    # Запуск noVNC
    websockify -D --web=/usr/share/novnc/ 6080 localhost:5901
}

# Функции мониторинга
check_status() {
    echo "=== Статус сервисов ==="
    echo "DISPLAY=$DISPLAY"
    
    if pgrep -f "vncserver" > /dev/null; then
        echo "VNC сервер: АКТИВЕН"
    else
        echo "VNC сервер: НЕАКТИВЕН"
    fi
    
    if pgrep -f "websockify" > /dev/null; then
        echo "noVNC: АКТИВЕН"
    else
        echo "noVNC: НЕАКТИВЕН"
    fi
    
    if [ -e "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ]; then
        echo "X11 сокет: СУЩЕСТВУЕТ"
    else
        echo "X11 сокет: ОТСУТСТВУЕТ"
    fi
}

# Основная логика
case "${1:-start}" in
    start)
        check_dependencies
        setup_x11
        setup_vnc
        start_services
        check_status
        echo "VNC доступен на порту 5901"
        echo "noVNC интерфейс доступен на http://localhost:6080"
        ;;
    stop)
        pkill -f "vncserver" || true
        pkill -f "websockify" || true
        echo "Сервисы остановлены"
        ;;
    status)
        check_status
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    *)
        echo "Использование: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac