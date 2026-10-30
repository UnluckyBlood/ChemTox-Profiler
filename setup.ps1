$ErrorActionPreference = "Stop"
$WORKDIR = $PSScriptRoot
Set-Location $WORKDIR

$PY_VERSION = "3.10.11"
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
$ESKAPE_REPO = "https://github.com/arnolp3/The-ESKAPE-Model"

function Write-Step($msg) { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan }

Write-Host "=========================================="
Write-Host " ChemTox Profiler - установка"
Write-Host "=========================================="
Write-Host ""
Write-Host "ВНИМАНИЕ: скачивание моделей ESKAPE" -ForegroundColor Yellow
Write-Host "может занять НЕСКОЛЬКО ЧАСОВ." -ForegroundColor Yellow
Write-Host "Если процесс прервётся - запустите install.bat снова." -ForegroundColor Yellow
Write-Host "Уже скачанное не будет качаться повторно." -ForegroundColor Yellow
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

if (-not (Test-Path "db\models\all")) {
    Write-Step "Скачивание ESKAPE (основной архив)"
    $tmpZip = "eskape-main.zip"
    Invoke-WebRequest -Uri "$ESKAPE_REPO/archive/refs/heads/main.zip" -OutFile $tmpZip -UseBasicParsing

    Write-Step "Распаковка"
    Expand-Archive -Path $tmpZip -DestinationPath "_eskape_tmp" -Force
    Remove-Item $tmpZip

    $eskapeRoot = Get-ChildItem "_eskape_tmp" -Directory | Select-Object -First 1
    Move-Item "$($eskapeRoot.FullName)\db" "db" -Force
    Remove-Item "_eskape_tmp" -Recurse -Force

    Write-Step "Докачка LFS-файлов (может занять часы)"
    $lfsFiles = Get-ChildItem "db" -Recurse -File | Where-Object { $_.Length -lt 1000 }
    $total = $lfsFiles.Count
    Write-Host "Найдено $total файлов LFS"

    $i = 0
    $errors = @()
    foreach ($f in $lfsFiles) {
        $i++
        $rel = $f.FullName.Substring($WORKDIR.Path.Length + 1).Replace("\", "/")
        $url = "https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main/$rel"
        if ($i % 20 -eq 0 -or $i -eq $total) { Write-Host "  [$i/$total] $($f.Name)" }
        try {
            Invoke-WebRequest -Uri $url -OutFile $f.FullName -UseBasicParsing
        } catch {
            Write-Host "  ОШИБКА: $($f.Name): $_" -ForegroundColor Red
            $errors += $f.Name
        }
    }
    if ($errors.Count -gt 0) {
        Write-Host ""
        Write-Host "Не скачано: $($errors.Count) файлов." -ForegroundColor Yellow
        Write-Host "Запустите install.bat снова - докачается только пропущенное." -ForegroundColor Yellow
    }
} else {
    Write-Step "db уже на месте"
}

Write-Host ""
Write-Host "=========================================="
Write-Host " Готово! Запускайте launch.bat"
Write-Host "==========================================" -ForegroundColor Green
