#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo " ChemTox Profiler - установка"
echo "=========================================="
echo "ВНИМАНИЕ: скачивание ESKAPE может занять часы."
echo "Если прервётся - запустите ./install.sh снова."
echo ""

if [ ! -f "venv/bin/python" ]; then
    echo "Создание venv..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

echo "Установка библиотек..."
./venv/bin/pip install -r requirements.txt

if [ ! -d "db/models/all" ]; then
    echo "Скачивание ESKAPE (основной архив)..."
    ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"
    if command -v curl >/dev/null 2>&1; then
        curl -fL -o eskape-main.zip "$ESKAPE_REPO/archive/refs/heads/main.zip"
    else
        wget -O eskape-main.zip "$ESKAPE_REPO/archive/refs/heads/main.zip"
    fi
    mkdir -p _eskape_tmp
    unzip -q eskape-main.zip -d _eskape_tmp
    rm -f eskape-main.zip
    mv _eskape_tmp/*/db db
    rm -rf _eskape_tmp

    echo "Докачка LFS (может занять часы)..."
    find db -type f -size -1000c | while read -r f; do
        rel="${f#./}"
        url="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main/$rel"
        echo "  $rel"
        if command -v curl >/dev/null 2>&1; then
            curl -fL -o "$f" "$url" || echo "  ОШИБКА: $f"
        else
            wget -O "$f" "$url" || echo "  ОШИБКА: $f"
        fi
    done
fi

echo ""
echo "Готово. Запускайте ./launch.sh"
