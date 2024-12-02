
#!/bin/bash

# Остановка и удаление контейнера
docker stop $(docker ps -q --filter "label=devcontainer.local_folder=/home/dev/OLE/vscode-remote-try-python")
docker rm $(docker ps -aq --filter "label=devcontainer.local_folder=/home/dev/OLE/vscode-remote-try-python")

# Пересборка
code .