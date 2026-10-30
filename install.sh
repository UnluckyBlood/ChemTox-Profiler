#!/usr/bin/env bash
# ============================================================
# ChemTox Profiler - установка на Linux
# Создаёт venv, ставит библиотеки, качает модели ESKAPE
# Поддерживает возобновление: уже скачанное не качается повторно
# ============================================================

set -e
cd "$(dirname "$0")"

# --- Конфигурация ---
ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"                                     # репозиторий с моделями
ESKAPE_LFS_BASE="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"     # CDN для LFS
PATHOGENS="AB BW DKO EF KP PA SA"                                                             # 7 патогенов ESKAPE
METHODS="rf chemprop rdkit"                                                                   # 3 типа моделей

# --- Вспомогательные функции ---
is_lfs_pointer() {
    # Проверяет по содержимому (не по размеру), что файл - LFS-заглушка
    [ -f "$1" ] || return 1
    local sz
    sz=$(stat -c%s "$1" 2>/dev/null || stat -f%z "$1" 2>/dev/null || echo 0)
    [ "$sz" -le 256 ] || return 1                                                             # реальный файл больше 256 байт
    [ "$sz" -gt 0 ] || return 1                                                               # пустой не заглушка
    head -c 60 "$1" 2>/dev/null | grep -q "^version https://git-lfs.github.com/spec/v1"       # сигнатура пойнтера
}

eskape_status() {
    # Возвращает absent / partial / complete
    [ -d "db/models/all" ] || { echo "absent"; return; }

    # Проверяем все 21 папки
    local missing=0
    for p in $PATHOGENS; do
        for m in $METHODS; do
            [ -d "db/models/all/${p}_${m}" ] || missing=$((missing+1))
        done
    done

    # Считаем LFS-заглушки по содержимому
    local pointers=0
    while IFS= read -r f; do
        is_lfs_pointer "$f" && pointers=$((pointers+1))
    done < <(find db -type f 2>/dev/null)

    if [ "$missing" -eq 0 ] && [ "$pointers" -eq 0 ]; then echo "complete"; else echo "partial"; fi
}

# --- Приветствие ---
echo "=========================================="
echo " ChemTox Profiler - установка"
echo "=========================================="
echo "ВНИМАНИЕ: первичное скачивание ESKAPE - часы."
echo "При прерывании перезапустите - докачается только недостающее."
echo ""

# --- Шаг 1: venv ---
if [ ! -f "venv/bin/python" ]; then
    echo "Создание venv..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

# --- Шаг 2: pip-библиотеки ---
echo "Установка библиотек..."
./venv/bin/pip install -r requirements.txt

# --- Шаг 3: проверка состояния ESKAPE ---
status=$(eskape_status)
echo "Проверка ESKAPE: $status"

# --- Шаг 4: основной архив (если db отсутствует) ---
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
    mv _eskape_tmp/*/db db                                                                   # вытаскиваем db из <repo>-main/
    rm -rf _eskape_tmp
    status="partial"                                                                         # теперь нужна докачка
fi

# --- Шаг 5: докачка LFS-заглушек ---
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
        # Проверяем, что сервер отдал файл, а не тот же пойнтер
        if is_lfs_pointer "$f"; then
            echo "    ПУСТО (сервер не отдал): $f"
        fi
    done
else
    echo "ESKAPE уже полностью установлен - пропуск"
fi

# --- Шаг 6: финальная верификация ---
final=$(eskape_status)
echo ""
if [ "$final" = "complete" ]; then
    echo "Готово. Запускайте ./launch.sh"
else
    echo "Установка не завершена ($final). Повторите ./install.sh"
    exit 1
fi