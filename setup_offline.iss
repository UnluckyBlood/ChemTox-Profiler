[Setup]
AppName=ChemTox Profiler
AppVersion=1.2.0
DefaultDirName={autopf}\ChemTox Profiler
DefaultGroupName=ChemTox Profiler
UninstallDisplayIcon={app}\python\pythonw.exe
SetupIconFile=app.ico
Compression=lzma2/max
SolidCompression=yes
OutputDir=dist\offline
OutputBaseFilename=ChemTox-Profiler-Offline-Setup
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableDirPage=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "dist\*, .git\*, venv\*, __pycache__\*, *.pyc, eskape_temp\*, eskape_output\*, *.log, install.bat, install.sh, setup.ps1, setup_*.iss, python.zip, The-ESKAPE-Model-main.zip, eskape-main.zip, get-pip.py"

[Icons]
Name: "{group}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; Description: "Запустить ChemTox Profiler"; Flags: postinstall nowait skipifsilent