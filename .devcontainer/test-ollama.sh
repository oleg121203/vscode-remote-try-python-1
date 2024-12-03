#!/bin/bash
# test-ollama.sh

set -e
trap 'echo "Error on line $LINENO. Exit code: $?"' ERR

# Функция тестирования соединения
test_connection() {
    local ip=$1
    local port=$2
    echo "Testing connection to ${ip}:${port}..."
    
    curl --connect-timeout 5 --max-time 10 -v "http://${ip}:${port}/api/status"
    return $?
}

# Функция проверки модели
check_model() {
    local ip=$1
    local model=$2
    echo "Checking model ${model} availability..."
    
    curl -s "http://${ip}:11434/api/show" -d "{\"name\":\"${model}\"}"
    return $?
}

# Функция загрузки модели
pull_model() {
    local ip=$1
    local model=$2
    echo "Pulling model: ${model}"
    
    curl -s "http://${ip}:11434/api/pull" -d "{\"name\":\"${model}\"}"
    return $?
}

# Основной процесс тестирования
main() {
    local ip="172.17.0.1"
    local port="11434"
    
    echo "=== Starting Ollama Test Script ==="
    echo "Testing IP: ${ip}"
    echo "Testing Port: ${port}"
    
    # Тест 1: Проверка соединения
    echo -e "\n1. Testing connection..."
    if test_connection "${ip}" "${port}"; then
        echo "✅ Connection successful"
    else
        echo "❌ Connection failed"
        return 1
    fi
    
    # Тест 2: Проверка наличия моделей
    echo -e "\n2. Testing models..."
    local models=("deepseek-coder-v2:latest" "nomic-embed-text:latest" "qwen2.5-coder:7b")
    
    for model in "${models[@]}"; do
        echo "Testing model: ${model}"
        if check_model "${ip}" "${model}"; then
            echo "✅ Model ${model} check successful"
        else
            echo "❌ Model ${model} check failed"
            
            echo "Attempting to pull model ${model}..."
            if pull_model "${ip}" "${model}"; then
                echo "✅ Model ${model} pulled successfully"
            else
                echo "❌ Failed to pull model ${model}"
            fi
        fi
    done
    
    echo -e "\n=== Test Complete ==="
}

# Запуск скрипта
main
