; Inno Setup script for GCODECrunch Windows installer
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

[Setup]
AppName=GCODECrunch
AppVersion=1.0.0
AppPublisher=Greg Egan
AppURL=https://github.com/gke/GCodeCrunch
DefaultDirName={autopf}\GCODECrunch
DefaultGroupName=GCODECrunch
OutputDir=installer_output
OutputBaseFilename=GCODECrunch-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\GCODECrunch.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GCODECrunch"; Filename: "{app}\GCODECrunch.exe"
Name: "{autodesktop}\GCODECrunch"; Filename: "{app}\GCODECrunch.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\GCODECrunch.exe"; Description: "Launch GCODECrunch"; Flags: nowait postinstall skipifsilent
