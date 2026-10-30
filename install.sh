#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"
PATHOGENS="AB BW DKO EF KP PA SA"
METHODS="rf chemprop rdkit"

eskape_status() {
    [ -d "db/models/all" ] || { echo "absent"; return; }
    local missing=0
    for p in $PATHOGENS; do
        for m in $METHODS; do
            [ -d "db/models/all/${p}_${m}" ] || missing=$((missing+1))
        done
    done
    local placeholders
    placeholders=$(find db -type f -size -1000c 2>/dev/null | wc -l)
    if [ "$missing" -eq 0 ] && [ "$placeholders" -eq 0 ]; then echo "complete"; else echo "partial"; fi
}

echo "=========================================="
echo " ChemTox Profiler - установка"
echo "=========================================="
echo "ВНИМАНИЕ: первичное скачивание ESKAPE - часы."
echo "При прерывании перезапустите - докачается только недостающее."
echo ""

if [ ! -f "venv/bin/python" ]; then
    echo "Создание venv..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

echo "Установка библиотек..."
./venv/bin/pip install -r requirements.txt

status=$(eskape_status)
echo "Проверка ESKAPE: $status"

if [ "$status" = "absent" ]; then
    echo "Скачивание основного архива..."
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
    status="partial"
fi

if [ "$status" = "partial" ]; then
    echo "Докачка LFS-файлов..."
    todo=$(find db -type f -size -1000c 2>/dev/null | wc -l)
    echo "Нужно докачать: $todo"
    find db -type f -size -1000c 2>/dev/null | while read -r f; do
        rel="${f#./}"
        url="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main/$rel"
        echo "  $rel"
        if command -v curl >/dev/null 2>&1; then
            curl -fL -o "$f" "$url" || echo "  ОШИБКА: $f"
        else
            wget -O "$f" "$url" || echo "  ОШИБКА: $f"
        fi
    done
else
    echo "ESKAPE уже полностью установлен - пропуск"
fi

final=$(eskape_status)
echo ""
if [ "$final" = "complete" ]; then
    echo "Готово. Запускайте ./launch.sh"
else
    echo "Установка не завершена ($final). Повторите ./install.sh"
    exit 1
fi