[Setup]
AppName=ChemTox Profiler
AppVersion=1.2.0
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
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "dist\*, .git\*, venv\*, __pycache__\*, *.pyc, eskape_temp\*, eskape_output\*, *.log, python\*, db\*, setup_*.iss, python.zip, The-ESKAPE-Model-main.zip, eskape-main.zip, get-pip.py"

[Icons]
Name: "{group}\Установить ChemTox Profiler"; Filename: "{app}\install.bat"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\install.bat"; Description: "Скачать Python и модели ESKAPE"; Flags: postinstall nowait skipifsilent