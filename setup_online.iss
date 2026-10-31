#include "version.iss"

[Setup]
AppId={{D965998E-9785-490D-8291-19ECA12D9F3C}
AppName=ChemTox Profiler
AppVersion={#AppVersion}
DefaultDirName={autopf}\ChemTox Profiler
DefaultGroupName=ChemTox Profiler
UninstallDisplayIcon={app}\app.ico
SetupIconFile=app.ico
OutputDir=dist\online
OutputBaseFilename=ChemTox-Profiler-Online-Setup
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableDirPage=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; Excludes: "dist\*, .git\*, venv\*, __pycache__\*, *.pyc, eskape_temp\*, eskape_output\*, *.zip, *.log, python\*, db\*, setup_*.iss, version.iss"

[Icons]
Name: "{group}\Установить ChemTox Profiler"; Filename: "{app}\install.bat"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{group}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\install.bat"; Description: "Скачать Python и модели ESKAPE"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\db"
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\eskape_output"
Type: filesandordirs; Name: "{app}\_eskape_extract"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{autoprograms}\ChemTox Profiler.lnk"
Type: files; Name: "{autodesktop}\ChemTox Profiler.lnk"
