# ============================================================
# ChemTox Profiler - установка на Windows
# Скачивает embeddable Python, pip-библиотеки и модели ESKAPE
# Поддерживает возобновление: уже скачанное не качается повторно
# ============================================================

$ErrorActionPreference = "Stop"
$WORKDIR = $PSScriptRoot
Set-Location $WORKDIR

# --- Конфигурация ---
$PY_VERSION = "3.10.11"                                                                          # версия embeddable Python
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"     # откуда качать Python
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"                                            # официальный загрузчик pip
$ESKAPE_REPO = "https://github.com/arnolp3/The-ESKAPE-Model"                                     # репозиторий с моделями ESKAPE
$ESKAPE_LFS_BASE = "https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"     # CDN для LFS-файлов
$PATHOGENS = @("AB","BW","DKO","EF","KP","PA","SA")                                              # 7 приоритетных патогенов ESKAPE
$METHODS = @("rf","chemprop","rdkit")                                                            # 3 типа моделей для каждого патогена

# --- Вспомогательные функции ---
function Write-Step($msg) {
    # Печатает заголовок шага цветом
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Test-LFSPointer($path) {
    # Проверяет по содержимому (не по размеру), что файл - LFS-заглушка
    try {
        $info = Get-Item -LiteralPath $path -ErrorAction Stop
        if ($info.Length -gt 256) { return $false }                                              # реальный файл больше 256 байт
        if ($info.Length -eq 0) { return $false }                                                # пустой файл не заглушка
        $bytes = [IO.File]::ReadAllBytes($path)
        $text = [Text.Encoding]::UTF8.GetString($bytes)
        return $text.StartsWith("version https://git-lfs.github.com/spec/v1")                    # сигнатура LFS-пойнтера
    } catch { return $false }
}

function Get-EskapeStatus {
    # Возвращает absent / partial / complete - нужна для решения, что качать
    if (-not (Test-Path "db\models\all")) { return "absent" }

    # Проверяем наличие всех 21 папок (7 патогенов x 3 метода)
    $missing = @()
    foreach ($p in $PATHOGENS) {
        foreach ($m in $METHODS) {
            $dir = "db\models\all\${p}_${m}"
            if (-not (Test-Path $dir)) { $missing += "${p}_${m}" }
        }
    }

    # Ищем LFS-заглушки по содержимому
    $pointers = @(Get-ChildItem "db" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { Test-LFSPointer $_.FullName })

    if ($missing.Count -eq 0 -and $pointers.Count -eq 0) { return "complete" }                   # всё на месте
    return "partial"                                                                             # чего-то не хватает
}

function Invoke-LfsDownload($file) {
    # Качает один LFS-файл через media CDN и проверяет, что пришёл не пойнтер
    $rel = $file.FullName.Substring($WORKDIR.Path.Length + 1).Replace("\", "/")
    $url = "$ESKAPE_LFS_BASE/$rel"
    try {
        Invoke-WebRequest -Uri $url -OutFile $file.FullName -UseBasicParsing -ErrorAction Stop
        if (Test-LFSPointer $file.FullName) { return "still-pointer" }                           # сервер не отдал файл
        return "ok"
    } catch {
        return "error: $_"
    }
}

# --- Приветствие ---
Write-Host "=========================================="
Write-Host " ChemTox Profiler - установка"
Write-Host "=========================================="
Write-Host ""
Write-Host "ВНИМАНИЕ: первичное скачивание ESKAPE" -ForegroundColor Yellow
Write-Host "может занять НЕСКОЛЬКО ЧАСОВ." -ForegroundColor Yellow
Write-Host "При прерывании - запустите install.bat снова," -ForegroundColor Yellow
Write-Host "докачается только недостающее." -ForegroundColor Yellow
Write-Host ""

# --- Шаг 1: Python ---
if (-not (Test-Path "python\python.exe")) {
    Write-Step "Скачивание Python $PY_VERSION (~10 МБ)"
    Invoke-WebRequest -Uri $PY_URL -OutFile "python.zip" -UseBasicParsing
    Expand-Archive -Path "python.zip" -DestinationPath "python" -Force
    Remove-Item "python.zip"

    # Embeddable Python по умолчанию не подхватывает site-packages - включаем импорт site
    $pth = Get-ChildItem "python\python*._pth" | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName

    Write-Step "Установка pip"
    Invoke-WebRequest -Uri $GET_PIP_URL -OutFile "get-pip.py" -UseBasicParsing
    & ".\python\python.exe" "get-pip.py"
    Remove-Item "get-pip.py"
} else {
    Write-Step "Python уже установлен"
}

# --- Шаг 2: pip-библиотеки ---
Write-Step "Установка библиотек (2-10 минут)"
& ".\python\python.exe" -m pip install --upgrade pip
& ".\python\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install завершился с ошибкой" }

# --- Шаг 3: проверка состояния ESKAPE ---
$status = Get-EskapeStatus
Write-Step "Проверка данных ESKAPE: $status"

# --- Шаг 4: основной архив ESKAPE (если db отсутствует) ---
if ($status -eq "absent") {
    Write-Step "Скачивание ESKAPE (основной архив)"
    $tmpZip = "eskape-main.zip"
    Invoke-WebRequest -Uri "$ESKAPE_REPO/archive/refs/heads/main.zip" -OutFile $tmpZip -UseBasicParsing
    Expand-Archive -Path $tmpZip -DestinationPath "_eskape_tmp" -Force
    Remove-Item $tmpZip

    # В архиве GitHub папка db лежит внутри <repo>-main/, переносим её наверх
    $root = Get-ChildItem "_eskape_tmp" -Directory | Select-Object -First 1
    Move-Item "$($root.FullName)\db" "db" -Force
    Remove-Item "_eskape_tmp" -Recurse -Force
    $status = "partial"                                                                          # теперь нужна докачка LFS
}

# --- Шаг 5: докачка LFS-файлов (заглушек) ---
if ($status -eq "partial") {
    Write-Host "Поиск недокачанных LFS-файлов..." -ForegroundColor Yellow
    Write-Step "Докачка LFS (может занять часы)"

    $pointers = @(Get-ChildItem "db" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { Test-LFSPointer $_.FullName })
    $total = $pointers.Count
    if ($total -eq 0) {
        Write-Host "Все LFS-файлы уже на месте."
    } else {
        Write-Host "Нужно докачать: $total"
        $i = 0
        $errors = @()
        foreach ($f in $pointers) {
            $i++
            if ($i % 20 -eq 0 -or $i -eq $total) { Write-Host "  [$i/$total] $($f.Name)" }
            $res = Invoke-LfsDownload $f
            if ($res -ne "ok") {
                Write-Host "  ПРОБЛЕМА [$($f.Name)]: $res" -ForegroundColor Red
                $errors += "$($f.Name): $res"
            }
        }
        if ($errors.Count -gt 0) {
            Write-Host ""
            Write-Host "Не скачано: $($errors.Count). Повторите install.bat - докачает только проблемные." -ForegroundColor Yellow
        }
    }
} else {
    Write-Step "ESKAPE уже полностью установлен - пропуск"
}

# --- Шаг 6: финальная верификация ---
$final = Get-EskapeStatus
Write-Host ""
Write-Host "=========================================="
if ($final -eq "complete") {
    Write-Host " Готово! ESKAPE: 21/21 модель, LFS-файлы на месте" -ForegroundColor Green
    Write-Host " Запускайте launch.bat" -ForegroundColor Green
} else {
    Write-Host " Установка не завершена (ESKAPE: $final)" -ForegroundColor Yellow
    Write-Host " Повторите install.bat" -ForegroundColor Yellow
}
Write-Host "=========================================="