# ============================================================
# ChemTox Profiler - установка на Windows
# - ставит embeddable Python 3.10 и pip
# - ставит библиотеки из requirements.txt
# - проверяет 21 модель ESKAPE; если чего-то нет, восстанавливает
#   из локального The-ESKAPE-Model-main.zip или качает с GitHub
# - докачивает LFS-заглушки (если zip был "сырой")
# ============================================================

$ErrorActionPreference = "Stop"
$WORKDIR = $PSScriptRoot
Set-Location $WORKDIR

# --- Конфигурация ---
$PY_VERSION       = "3.10.11"
$PY_URL           = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
$GET_PIP_URL      = "https://bootstrap.pypa.io/get-pip.py"
$ESKAPE_REPO      = "https://github.com/arnolp3/The-ESKAPE-Model"
$ESKAPE_LFS_BASE  = "https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"
$ESKAPE_LOCAL_ZIP = "The-ESKAPE-Model-main.zip"
$DB_ROOT          = "db\models\all"
$PATHOGENS        = @("AB","BW","DKO","EF","KP","PA","SA")
$METHODS          = @("rf","chemprop","rdkit")

# --- Утилиты ---
function Write-Step($msg) { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host $msg -ForegroundColor Green }
function Write-Warn($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host $msg -ForegroundColor Red }

function Test-LFSPointer($path) {
    # Файл - LFS-заглушка, если маленький и начинается с сигнатуры git-lfs
    try {
        $info = Get-Item -LiteralPath $path -ErrorAction Stop
        if ($info.Length -gt 256) { return $false }
        if ($info.Length -eq 0) { return $false }
        $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($path))
        return $text.StartsWith("version https://git-lfs.github.com/spec/v1")
    } catch { return $false }
}

function Get-LfsPointers {
    # Список LFS-заглушек под db/
    $list = New-Object System.Collections.ArrayList
    if (-not (Test-Path "db")) { return @() }
    Get-ChildItem "db" -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        if (Test-LFSPointer $_.FullName) { [void]$list.Add($_) }
    }
    return $list.ToArray()
}

function Test-ModelDir {
    # Папка модели годна, если существует и содержит хотя бы один файл
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    $files = Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue
    return ($files.Count -gt 0)
}

function Get-MissingModels {
    # Список {P}_{M}, которых нет или они пусты (из 21)
    $missing = @()
    foreach ($p in $PATHOGENS) {
        foreach ($m in $METHODS) {
            $key = "${p}_${m}"
            if (-not (Test-ModelDir "$DB_ROOT\$key")) { $missing += $key }
        }
    }
    return $missing
}

function Test-EskapeComplete {
    # Полный ESKAPE = все 21 модели на месте + нет LFS-заглушек
    if ((Get-MissingModels).Count -gt 0) { return $false }
    if ((Get-LfsPointers).Count -gt 0) { return $false }
    return $true
}

function Expand-EskapeZip($zipPath) {
    # Распаковка с поиском db на любой глубине (устойчиво к имени корневой папки)
    Write-Step "Распаковка $zipPath"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $tmp = "_eskape_extract"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $tmp)

    $dbDir = Get-ChildItem $tmp -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -eq "db") -and (Test-Path "$($_.FullName)\models\all")
    } | Select-Object -First 1

    if (-not $dbDir) {
        Remove-Item $tmp -Recurse -Force
        throw "В архиве $zipPath не найдена папка db\models\all"
    }

    if (Test-Path "db") { Remove-Item "db" -Recurse -Force }
    Move-Item $dbDir.FullName "db"
    Remove-Item $tmp -Recurse -Force
    Write-Ok "Распаковано: db/"
}

function Invoke-EskapeDownload {
    # Скачивание свежего архива с GitHub
    $tmpZip = "eskape-main.zip"
    Write-Step "Скачивание ESKAPE с $ESKAPE_REPO (~3.5 ГБ)"
    Invoke-WebRequest -Uri "$ESKAPE_REPO/archive/refs/heads/main.zip" -OutFile $tmpZip -UseBasicParsing
    try { Expand-EskapeZip $tmpZip }
    finally { if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force } }
}

function Invoke-LfsFill {
    # Докачка LFS-заглушек через media CDN
    $pointers = Get-LfsPointers
    if ($pointers.Count -eq 0) { Write-Ok "LFS-заглушек нет"; return }
    Write-Step "Докачка LFS ($($pointers.Count) файлов)"
    $i = 0; $errors = @()
    foreach ($f in $pointers) {
        $i++
        if ($i % 20 -eq 0 -or $i -eq $pointers.Count) { Write-Host "  [$i/$($pointers.Count)] $($f.Name)" }
        $rel = $f.FullName.Substring($WORKDIR.Path.Length + 1).Replace("\", "/")
        $url = "$ESKAPE_LFS_BASE/$rel"
        try {
            Invoke-WebRequest -Uri $url -OutFile $f.FullName -UseBasicParsing -ErrorAction Stop
            if (Test-LFSPointer $f.FullName) {
                Write-Err "  ПУСТО: $($f.Name)"; $errors += $f.Name
            }
        } catch {
            Write-Err "  ОШИБКА: $($f.Name) - $_"; $errors += $f.Name
        }
    }
    if ($errors.Count -gt 0) { Write-Warn "Не скачано: $($errors.Count). Повторите install.bat." }
}

# --- Приветствие ---
Write-Host "=========================================="
Write-Host " ChemTox Profiler - установка"
Write-Host "=========================================="
Write-Host ""

# --- Шаг 1: Python ---
if (-not (Test-Path "python\python.exe")) {
    Write-Step "Скачивание Python $PY_VERSION"
    Invoke-WebRequest -Uri $PY_URL -OutFile "python.zip" -UseBasicParsing
    Expand-Archive -Path "python.zip" -DestinationPath "python" -Force
    Remove-Item "python.zip"
    $pth = Get-ChildItem "python\python*._pth" | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName
    Write-Step "Установка pip"
    Invoke-WebRequest -Uri $GET_PIP_URL -OutFile "get-pip.py" -UseBasicParsing
    & ".\python\python.exe" "get-pip.py"
    Remove-Item "get-pip.py"
} else {
    Write-Step "Python уже установлен"
}

# --- Шаг 2: библиотеки ---
Write-Step "Установка библиотек"
& ".\python\python.exe" -m pip install --upgrade pip
& ".\python\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install завершился с ошибкой" }

# --- Шаг 3: ESKAPE ---
if (Test-EskapeComplete) {
    Write-Step "ESKAPE уже полностью установлен - пропуск"
} else {
    $missing = Get-MissingModels
    $pointers = Get-LfsPointers
    Write-Step "ESKAPE неполный"
    if ($missing.Count -gt 0)  { Write-Warn "Отсутствует моделей: $($missing.Count) из 21" }
    if ($pointers.Count -gt 0) { Write-Warn "LFS-заглушек: $($pointers.Count)" }

    # Есть ли вообще db или модели не хватает - восстанавливаем архив
    if ((-not (Test-Path $DB_ROOT)) -or ($missing.Count -gt 0)) {
        if (Test-Path $ESKAPE_LOCAL_ZIP) {
            Write-Ok "Найден локальный $ESKAPE_LOCAL_ZIP - использую его"
            Expand-EskapeZip $ESKAPE_LOCAL_ZIP
        } else {
            Write-Warn "Локального архива нет - скачаю с $ESKAPE_REPO"
            Invoke-EskapeDownload
        }
    }

    # Докачиваем заглушки, если после распаковки они остались
    Invoke-LfsFill
}

# --- Финальный отчёт ---
Write-Host ""
Write-Host "=========================================="
if (Test-EskapeComplete) {
    Write-Ok " Готово! ESKAPE: 21/21 модель, LFS на месте"
    Write-Ok " Запускайте launch.bat"
} else {
    $stillMissing  = Get-MissingModels
    $stillPointers = Get-LfsPointers
    Write-Warn " Установка не завершена"
    if ($stillMissing.Count -gt 0)  { Write-Warn "  нет моделей: $($stillMissing -join ', ')" }
    if ($stillPointers.Count -gt 0) { Write-Warn "  LFS-заглушек: $($stillPointers.Count)" }
    Write-Warn " Повторите install.bat"
}
Write-Host "=========================================="