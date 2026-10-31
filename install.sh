#!/usr/bin/env bash
# ============================================================
# ChemTox Profiler - установка на Linux
# Обязательные: 7 _rf (их использует streamlit_app.py)
# Опциональные: _chemprop / _rdkit (в источнике их нет, не блокируют)
# ============================================================

set -e
cd "$(dirname "$0")"

# --- Конфигурация ---
ESKAPE_REPO="https://github.com/arnolp3/The-ESKAPE-Model"
ESKAPE_LFS_BASE="https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"
ESKAPE_LOCAL_ZIP="The-ESKAPE-Model-main.zip"
DB_ROOT="db/models/all"
PATHOGENS="AB BW DKO EF KP PA SA"
REQUIRED_METHODS="rf"
OPTIONAL_METHODS="chemprop rdkit"

# --- Утилиты ---
say_step() { echo ""; echo "=== $1 ==="; }
say_ok()   { echo "$1"; }
say_warn() { echo "!! $1"; }
say_err()  { echo "XX $1"; }

fetch() {
    local url="$1" out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 5 --retry-delay 3 -o "$out.part" "$url" || { rm -f "$out.part"; return 1; }
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$out.part" "$url" || { rm -f "$out.part"; return 1; }
    else
        say_err "Нужен curl или wget: sudo apt install curl"
        return 1
    fi
    mv -f "$out.part" "$out"
}

is_lfs_pointer() {
    [ -f "$1" ] || return 1
    local sz
    sz=$(stat -c%s "$1" 2>/dev/null || stat -f%z "$1" 2>/dev/null || echo 0)
    [ "$sz" -le 256 ] || return 1
    [ "$sz" -gt 0 ] || return 1
    head -c 60 "$1" 2>/dev/null | grep -q "^version https://git-lfs.github.com/spec/v1"
}

list_lfs_pointers() {
    [ -d "db" ] || return 0
    find db -type f 2>/dev/null | while read -r f; do
        if is_lfs_pointer "$f"; then echo "$f"; fi
    done
}

test_model_dir() {
    [ -d "$1" ] || return 1
    [ -n "$(find "$1" -type f 2>/dev/null | head -1)" ]
}

missing_models() {
    # {P}_{M} для заданного набора методов (аргумент: строка "rf" или "chemprop rdkit")
    local methods="$1"
    local missing=""
    for p in $PATHOGENS; do
        for m in $methods; do
            local key="${p}_${m}"
            test_model_dir "$DB_ROOT/$key" || missing="$missing $key"
        done
    done
    echo "$missing"
}

missing_required() { missing_models "$REQUIRED_METHODS"; }
missing_optional() { missing_models "$OPTIONAL_METHODS"; }

eskape_required_ok() {
    [ -z "$(missing_required | tr -d ' ')" ] || return 1
    [ -z "$(list_lfs_pointers)" ] || return 1
    return 0
}

expand_eskape_zip() {
    local zip="$1"
    if ! command -v unzip >/dev/null 2>&1; then
        say_err "Не найден unzip: sudo apt install unzip"
        return 1
    fi
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
    say_step "Скачивание ESKAPE с $ESKAPE_REPO (~3.5 ГБ)"
    local zip="eskape-main.zip"
    fetch "$ESKAPE_REPO/archive/refs/heads/main.zip" "$zip"
    expand_eskape_zip "$zip"
    rm -f "$zip"
}

lfs_fill() {
    local list
    list=$(list_lfs_pointers)
    if [ -z "$list" ]; then say_ok "LFS-заглушек нет"; return 0; fi
    local total; total=$(echo "$list" | wc -l)
    say_step "Докачка LFS ($total файлов)"
    local err=0
    while IFS= read -r f; do
        local rel="${f#./}"
        local url="$ESKAPE_LFS_BASE/$rel"
        echo "  $rel"
        if fetch "$url" "$f"; then
            if is_lfs_pointer "$f"; then say_err "  ПУСТО: $f"; err=$((err+1)); fi
        else
            say_err "  ОШИБКА: $f"; err=$((err+1))
        fi
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

# --- Шаг 3: обязательные (_rf) ---
if eskape_required_ok; then
    say_step "Обязательные модели ESKAPE (7 _rf) уже на месте - пропуск"
else
    req=$(missing_required); p_cnt=$(list_lfs_pointers | wc -l)
    say_step "Обязательные модели ESKAPE отсутствуют"
    [ -n "$req" ] && say_warn "Нет RF-моделей: $(echo $req | wc -w) из 7"
    [ "$p_cnt" -gt 0 ] && say_warn "LFS-заглушек: $p_cnt"

    if [ ! -d "$DB_ROOT" ] || [ -n "$req" ]; then
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

# --- Шаг 4: опциональные (_chemprop, _rdkit) ---
opt=$(missing_optional)
if [ -z "$opt" ]; then
    say_step "Опциональные модели (_chemprop/_rdkit) тоже на месте"
else
    say_step "Опциональные модели (_chemprop/_rdkit): нет $(echo $opt | wc -w) из 14"
    echo "Это норма: arnolp3/The-ESKAPE-Model содержит только _rf,"
    echo "а streamlit_app.py использует только _rf. Пропускаю."
fi

# --- Финальный отчёт ---
echo ""
echo "=========================================="
if eskape_required_ok; then
    say_ok "Готово! ESKAPE: 7/7 RF-моделей, LFS на месте"
    say_ok "Запускайте ./launch.sh"
else
    say_warn "Установка не завершена. Повторите ./install.sh"
fi
echo "=========================================="
