$ErrorActionPreference = "Stop"
$WORKDIR = $PSScriptRoot
Set-Location $WORKDIR

$PY_VERSION = "3.10.11"
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
$ESKAPE_REPO = "https://github.com/arnolp3/The-ESKAPE-Model"
$PATHOGENS = @("AB","BW","DKO","EF","KP","PA","SA")
$METHODS = @("rf","chemprop","rdkit")

function Write-Step($msg) { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan }

function Get-EskapeStatus {
    if (-not (Test-Path "db\models\all")) { return "absent" }

    $missing = @()
    foreach ($p in $PATHOGENS) {
        foreach ($m in $METHODS) {
            $dir = "db\models\all\${p}_${m}"
            if (-not (Test-Path $dir)) { $missing += "${p}_${m}" }
        }
    }
    $placeholders = @(Get-ChildItem "db" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -lt 1000 })

    if ($missing.Count -eq 0 -and $placeholders.Count -eq 0) { return "complete" }
    return "partial"
}

Write-Host "=========================================="
Write-Host " ChemTox Profiler - установка"
Write-Host "=========================================="
Write-Host ""
Write-Host "ВНИМАНИЕ: первичное скачивание ESKAPE" -ForegroundColor Yellow
Write-Host "может занять НЕСКОЛЬКО ЧАСОВ." -ForegroundColor Yellow
Write-Host "При прерывании - запустите install.bat снова," -ForegroundColor Yellow
Write-Host "докачается только недостающее." -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path "python\python.exe")) {
    Write-Step "Скачивание Python $PY_VERSION (~10 МБ)"
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

Write-Step "Установка библиотек (2-10 минут)"
& ".\python\python.exe" -m pip install --upgrade pip
& ".\python\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install завершился с ошибкой" }

$status = Get-EskapeStatus
Write-Step "Проверка данных ESKAPE: $status"

if ($status -eq "absent") {
    Write-Step "Скачивание ESKAPE (основной архив)"
    $tmpZip = "eskape-main.zip"
    Invoke-WebRequest -Uri "$ESKAPE_REPO/archive/refs/heads/main.zip" -OutFile $tmpZip -UseBasicParsing
    Expand-Archive -Path $tmpZip -DestinationPath "_eskape_tmp" -Force
    Remove-Item $tmpZip
    $root = Get-ChildItem "_eskape_tmp" -Directory | Select-Object -First 1
    Move-Item "$($root.FullName)\db" "db" -Force
    Remove-Item "_eskape_tmp" -Recurse -Force
}

if ($status -eq "absent" -or $status -eq "partial") {
    if ($status -eq "partial") {
        Write-Host "Докачка недостающих/недокачанных файлов..." -ForegroundColor Yellow
    }
    Write-Step "Докачка LFS-файлов (может занять часы)"
    $lfsFiles = @(Get-ChildItem "db" -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -lt 1000 })
    $total = $lfsFiles.Count
    if ($total -eq 0) {
        Write-Host "Все файлы уже на месте."
    } else {
        Write-Host "Нужно докачать: $total"
        $i = 0; $errors = @()
        foreach ($f in $lfsFiles) {
            $i++
            $rel = $f.FullName.Substring($WORKDIR.Path.Length + 1).Replace("\", "/")
            $url = "https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main/$rel"
            if ($i % 20 -eq 0 -or $i -eq $total) { Write-Host "  [$i/$total] $($f.Name)" }
            try { Invoke-WebRequest -Uri $url -OutFile $f.FullName -UseBasicParsing }
            catch { Write-Host "  ОШИБКА: $($f.Name): $_" -ForegroundColor Red; $errors += $f.Name }
        }
        if ($errors.Count -gt 0) {
            Write-Host ""
            Write-Host "Не скачано: $($errors.Count). Запустите install.bat снова." -ForegroundColor Yellow
        }
    }
} else {
    Write-Step "ESKAPE уже полностью установлен - пропуск"
}

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