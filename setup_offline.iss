#include "version.iss"

[Setup]
AppId={{D965998E-9785-490D-8291-19ECA12D9F3C}
AppName=ChemTox Profiler
AppVersion={#AppVersion}
DefaultDirName={autopf}\ChemTox Profiler
DefaultGroupName=ChemTox Profiler
UninstallDisplayIcon={app}\app.ico
SetupIconFile=app.ico
Compression=lzma2/normal
SolidCompression=no
OutputDir=dist\offline
OutputBaseFilename=ChemTox-Profiler-Offline-Setup
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableDirPage=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "dist\*, .git\*, venv\*, __pycache__\*, *.pyc, eskape_temp\*, eskape_output\*, *.log, install.bat, install.sh, setup.ps1, setup_*.iss, version.iss, python.zip, The-ESKAPE-Model-main.zip, eskape-main.zip, get-pip.py"

[Icons]
Name: "{group}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; Description: "Запустить ChemTox Profiler"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\db"
Type: filesandordirs; Name: "{app}\eskape_output"
Type: filesandordirs; Name: "{app}\__pycache__"
