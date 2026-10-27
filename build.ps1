$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n=== [1/4] Компиляция launcher.exe ===" -ForegroundColor Cyan
$csharpCode = @"
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
class Program {
    static void Main() {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(dir, @"python\python.exe");
        string script = Path.Combine(dir, @"streamlit_app.py");
        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = python;
        psi.Arguments = string.Format("-m streamlit run \"{0}\" --server.headless=true --server.port=8501", script);
        psi.CreateNoWindow = true;
        psi.UseShellExecute = false;
        Process.Start(psi);
        Thread.Sleep(3000);
        ProcessStartInfo edge = new ProcessStartInfo();
        edge.FileName = "msedge";
        edge.Arguments = "--app=http://localhost:8501";
        Process.Start(edge);
    }
}
"@
Add-Type -TypeDefinition $csharpCode -OutputType WindowsApplication -OutputAssembly "launcher.exe"
Write-Host "✅ launcher.exe готов" -ForegroundColor Green

Write-Host "`n=== [2/4] Установка Inno Setup ===" -ForegroundColor Cyan
$innoPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $innoPath)) {
    $innoInst = "$env:TEMP\innosetup.exe"
    Invoke-WebRequest -Uri "https://jrsoftware.org/download.php/is.exe" -OutFile $innoInst
    Start-Process -FilePath $innoInst -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-" -Wait
}

Write-Host "`n=== [3/4] Генерация setup.iss ===" -ForegroundColor Cyan
$issCode = @"
[Setup]
AppName=ChemTox Profiler
AppVersion=1.0
DefaultDirName={autopf}\ChemToxProfiler
DefaultGroupName=ChemTox Profiler
OutputDir=Output
OutputBaseFilename=ChemTox_Setup
Compression=lzma2/max
SolidCompression=yes
DisableProgramGroupPage=yes

[Files]
Source: "launcher.exe"; DestDir: "{app}"
Source: "streamlit_app.py"; DestDir: "{app}"
Source: "python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs
Source: "db\*"; DestDir: "{app}\db"; Flags: recursesubdirs createallsubdirs
Source: ".streamlit\*"; DestDir: "{app}\.streamlit"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\ChemTox Profiler"; Filename: "{app}\launcher.exe"
Name: "{group}\ChemTox Profiler"; Filename: "{app}\launcher.exe"

[Run]
Filename: "{app}\launcher.exe"; Description: "Запустить ChemTox Profiler"; Flags: nowait postinstall skipifsilent
"@
$issCode | Out-File -FilePath "setup.iss" -Encoding ascii

Write-Host "`n=== [4/4] Сборка setup.exe ===" -ForegroundColor Cyan
& $innoPath "setup.iss"
Write-Host "`n✅ Установщик готов: .\Output\ChemTox_Setup.exe" -ForegroundColor Green
Start-Process explorer.exe ".\Output"
