#!/usr/bin/env bash
# ============================================================
# ChemTox Profiler - установка на Linux
# - создаёт venv и ставит библиотеки из requirements.txt
# - проверяет 21 модель ESKAPE; если чего-то нет, восстанавливает
#   из локального The-ESKAPE-Model-main.zip или качает с GitHub
# - докачивает LFS-заглушки (если zip был "сырой")
# ============================================================

set -e
cd "$(dirname "$0")"

# --- Конфигурация ---
ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"
ESKAPE_LFS_BASE="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"
ESKAPE_LOCAL_ZIP="The-ESKAPE-Model-main.zip"
DB_ROOT="db/models/all"
PATHOGENS="AB BW DKO EF KP PA SA"
METHODS="rf chemprop rdkit"

# --- Утилиты ---
say_step() { echo ""; echo "=== $1 ==="; }
say_ok()   { echo "$1"; }
say_warn() { echo "!! $1"; }
say_err()  { echo "XX $1"; }

is_lfs_pointer() {
    # Файл - LFS-заглушка, если маленький и начинается с сигнатуры git-lfs
    [ -f "$1" ] || return 1
    local sz
    sz=$(stat -c%s "$1" 2>/dev/null || stat -f%z "$1" 2>/dev/null || echo 0)
    [ "$sz" -le 256 ] || return 1
    [ "$sz" -gt 0 ] || return 1
    head -c 60 "$1" 2>/dev/null | grep -q "^version https://git-lfs.github.com/spec/v1"
}

list_lfs_pointers() {
    # Все LFS-заглушки под db/
    [ -d "db" ] || return 0
    find db -type f 2>/dev/null | while read -r f; do
        is_lfs_pointer "$f" && echo "$f"
    done
}

test_model_dir() {
    # Папка модели годна, если существует и содержит хотя бы один файл
    [ -d "$1" ] || return 1
    [ -n "$(find "$1" -type f 2>/dev/null | head -1)" ]
}

missing_models() {
    # Список {P}_{M}, которых нет или они пусты (из 21)
    local missing=""
    for p in $PATHOGENS; do
        for m in $METHODS; do
            local key="${p}_${m}"
            test_model_dir "$DB_ROOT/$key" || missing="$missing $key"
        done
    done
    echo "$missing"
}

eskape_complete() {
    # Полный ESKAPE = все 21 модели на месте + нет LFS-заглушек
    [ -z "$(missing_models | tr -d ' ')" ] || return 1
    [ -z "$(list_lfs_pointers)" ] || return 1
    return 0
}

expand_eskape_zip() {
    # Распаковка с поиском db на любой глубине
    local zip="$1"
    say_step "Распаковка $zip"
    local tmp="_eskape_extract"
    rm -rf "$tmp"; mkdir -p "$tmp"
    unzip -q "$zip" -d "$tmp"
    local dbdir
    dbdir=$(find "$tmp" -type d -name db -exec test -d "{}/models/all" \; -print | head -1)
    if [ -z "$dbdir" ]; then
        rm -rf "$tmp"
        echo "В архиве $zip не найдена папка db/models/all" >&2
        return 1
    fi
    rm -rf "db"
    mv "$dbdir" "db"
    rm -rf "$tmp"
    say_ok "Распаковано: db/"
}

download_eskape() {
    # Скачивание свежего архива
    say_step "Скачивание ESKAPE с $ESKAPE_REPO (~3.5 ГБ)"
    local zip="eskape-main.zip"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --progress-bar -o "$zip" "$ESKAPE_REPO/archive/refs/heads/main.zip"
    else
        wget -O "$zip" "$ESKAPE_REPO/archive/refs/heads/main.zip"
    fi
    expand_eskape_zip "$zip"
    rm -f "$zip"
}

lfs_fill() {
    # Докачка LFS-заглушек через media CDN
    local list
    list=$(list_lfs_pointers)
    if [ -z "$list" ]; then say_ok "LFS-заглушек нет"; return 0; fi
    local total; total=$(echo "$list" | wc -l)
    say_step "Докачка LFS ($total файлов)"
    local i=0 err=0
    while IFS= read -r f; do
        i=$((i+1))
        local rel="${f#./}"
        local url="$ESKAPE_LFS_BASE/$rel"
        echo "  $rel"
        if command -v curl >/dev/null 2>&1; then
            curl -fL -o "$f" "$url" || { say_err "  ОШИБКА: $f"; err=$((err+1)); }
        else
            wget -O "$f" "$url" || { say_err "  ОШИБКА: $f"; err=$((err+1)); }
        fi
        if is_lfs_pointer "$f"; then say_err "  ПУСТО: $f"; err=$((err+1)); fi
    done <<< "$list"
    [ "$err" -eq 0 ] || say_warn "Не скачано: $err. Повторите ./install.sh"
}

# --- Приветствие ---
echo "=========================================="
echo " ChemTox Profiler - установка"
echo "=========================================="
echo ""

# --- Шаг 1: venv ---
if [ ! -f "venv/bin/python" ]; then
    say_step "Создание venv"
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

# --- Шаг 2: библиотеки ---
say_step "Установка библиотек"
./venv/bin/pip install -r requirements.txt

# --- Шаг 3: ESKAPE ---
if eskape_complete; then
    say_step "ESKAPE уже полностью установлен - пропуск"
else
    say_step "ESKAPE неполный"
    m=$(missing_models); p_cnt=$(list_lfs_pointers | wc -l)
    [ -n "$m" ] && say_warn "Отсутствует моделей: $(echo $m | wc -w) из 21"
    [ "$p_cnt" -gt 0 ] && say_warn "LFS-заглушек: $p_cnt"

    if [ ! -d "$DB_ROOT" ] || [ -n "$m" ]; then
        if [ -f "$ESKAPE_LOCAL_ZIP" ]; then
            say_ok "Найден локальный $ESKAPE_LOCAL_ZIP - использую его"
            expand_eskape_zip "$ESKAPE_LOCAL_ZIP"
        else
            say_warn "Локального архива нет - скачаю с $ESKAPE_REPO"
            download_eskape
        fi
    fi
    lfs_fill
fi

# --- Финальный отчёт ---
echo ""
echo "=========================================="
if eskape_complete; then
    say_ok "Готово! ESKAPE: 21/21 модель, LFS на месте"
    say_ok "Запускайте ./launch.sh"
else
    say_warn "Установка не завершена. Повторите ./install.sh"
fi
echo "=========================================="