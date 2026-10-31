#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -x "venv/bin/streamlit" ]; then
    echo "Установка не завершена. Запустите ./install.sh"
    exit 1
fi
if [ ! -d "db/models/all" ]; then
    echo "Модели не скачаны. Запустите ./install.sh"
    exit 1
fi
./venv/bin/streamlit run streamlit_app.py --server.headless=false --browser.gatherUsageStats=false
