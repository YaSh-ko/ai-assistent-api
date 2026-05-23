#!/bin/bash
# Скрипт для запуска анализа SonarQube

# Проверка наличия SonarQube Scanner
if ! command -v sonar-scanner &> /dev/null; then
    echo "❌ SonarQube Scanner не установлен"
    echo "Установите его с https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/"
    exit 1
fi

# Переход в директорию проекта
cd "$(dirname "$0")"

# Проверка наличия токена
if [ -z "$SONARQUBE_TOKEN" ]; then
    echo "❌ Переменная окружения SONARQUBE_TOKEN не установлена"
    echo "Установите её: export SONARQUBE_TOKEN=your_token_here"
    exit 1
fi

# Проверка наличия конфигурационного файла
if [ ! -f "sonar-project.properties" ]; then
    echo "❌ Файл sonar-project.properties не найден"
    echo "Создайте его на основе sonar-project.properties.example"
    exit 1
fi

echo "🔍 Запуск анализа SonarQube..."
# Передаем токен через переменную окружения
SONARQUBE_TOKEN="$SONARQUBE_TOKEN" sonar-scanner -Dsonar.token="$SONARQUBE_TOKEN"

if [ $? -eq 0 ]; then
    echo "✅ Анализ завершен успешно!"
    echo "📊 Результаты доступны на: http://155.212.144.219"
else
    echo "❌ Ошибка при выполнении анализа"
    exit 1
fi
