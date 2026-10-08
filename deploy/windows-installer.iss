[Setup]
AppId={{0CDA78BF-C466-4C4A-83B6-792267DC2172}
AppName=JARVIS
AppVersion=0.1.0
AppPublisher=Pablo Riego
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=JARVIS
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\artifacts
OutputBaseFilename=JARVIS-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\jarvis_app.exe

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"
Name: "startup"; Description: "Iniciar JARVIS al iniciar sesión"; Flags: unchecked

[Files]
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JARVIS"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch-windows.vbs"""; IconFilename: "{app}\jarvis_app.exe"
Name: "{autodesktop}\JARVIS"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch-windows.vbs"""; Tasks: desktopicon; IconFilename: "{app}\jarvis_app.exe"
Name: "{userstartup}\JARVIS"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch-windows.vbs"""; Tasks: startup

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch-windows.vbs"""; Description: "Iniciar JARVIS"; Flags: nowait postinstall skipifsilent
