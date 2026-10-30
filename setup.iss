[Setup]
AppName=ChemTox Profiler
AppVersion=1.2.0
DefaultDirName={autopf}\ChemTox Profiler
DefaultGroupName=ChemTox Profiler
UninstallDisplayIcon={app}\python\pythonw.exe
Compression=lzma2/max
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=ChemTox-Profiler-Setup
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; Excludes: "dist\*, .git\*, venv\*, __pycache__\*, *.pyc, eskape_temp\*, eskape_output\*, *.zip, *.log, install.bat, install.sh, setup.ps1"

[Icons]
Name: "{group}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\python\pythonw.exe"
Name: "{autodesktop}\ChemTox Profiler"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\python\pythonw.exe"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; Description: "Запустить ChemTox Profiler"; Flags: postinstall nowait skipifsilent