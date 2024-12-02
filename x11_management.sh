
#!/bin/bash
set -e

# 1. Сначала остановим X-сервер если он запущен
sudo systemctl stop gdm.service 2>/dev/null || true
sudo systemctl stop lightdm.service 2>/dev/null || true

# 2. Проверим текущее состояние
echo "Checking current state:"
ls -la /tmp/.X11-unix
whoami

# 3. Безопасное управление директорией
if [ -d "/tmp/.X11-unix" ]; then
    # Временно изменим права для работы
    sudo chmod 1777 /tmp/.X11-unix
    
    # Если нужно очистить содержимое, но сохранить директорию
    sudo rm -f /tmp/.X11-unix/X*
else
    # Создаем директорию с правильными правами
    sudo mkdir -p /tmp/.X11-unix
    sudo chmod 1777 /tmp/.X11-unix
fi

# 4. Проверим результат
echo "Final state:"
ls -la /tmp/.X11-unix