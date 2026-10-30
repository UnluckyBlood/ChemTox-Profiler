#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"
ESKAPE_LFS_BASE="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"
PATHOGENS="AB BW DKO EF KP PA SA"
METHODS="rf chemprop rdkit"

is_lfs_pointer() {
    [ -f "$1" ] || return 1
    local sz
    sz=$(stat -c%s "$1" 2>/dev/null || stat -f%z "$1" 2>/dev/null || echo 0)
    [ "$sz" -le 256 ] || return 1
    [ "$sz" -gt 0 ] || return 1
    head -c 60 "$1" 2>/dev/null | grep -q "^version https://git-lfs.github.com/spec/v1"
}

eskape_status() {
    [ -d "db/models/all" ] || { echo "absent"; return; }
    local missing=0
    for p in $PATHOGENS; do
        for m in $METHODS; do
            [ -d "db/models/all/${p}_${m}" ] || missing=$((missing+1))
        done
    done
    local pointers=0
    while IFS= read -r f; do
        is_lfs_pointer "$f" && pointers=$((pointers+1))
    done < <(find db -type f 2>/dev/null)
    if [ "$missing" -eq 0 ] && [ "$pointers" -eq 0 ]; then echo "complete"; else echo "partial"; fi
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
    echo "Поиск недокачанных LFS-файлов..."
    pointers=()
    while IFS= read -r f; do
        is_lfs_pointer "$f" && pointers+=("$f")
    done < <(find db -type f 2>/dev/null)

    total=${#pointers[@]}
    echo "Нужно докачать: $total"

    for f in "${pointers[@]}"; do
        rel="${f#./}"
        url="$ESKAPE_LFS_BASE/$rel"
        echo "  $rel"
        if command -v curl >/dev/null 2>&1; then
            curl -fL -o "$f" "$url" || echo "    ОШИБКА: $f"
        else
            wget -O "$f" "$url" || echo "    ОШИБКА: $f"
        fi
        if is_lfs_pointer "$f"; then
            echo "    ПУСТО (сервер не отдал): $f"
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