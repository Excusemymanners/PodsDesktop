; Inno Setup script – builds dist\PodsDesktop-Setup.exe from dist\PodsDesktop.exe
#define AppVersion "0.1.0"
[Setup]
AppId={{7E1C2B6A-5C0E-4D8B-9A6F-3B2A1F0C9D11}
AppName=PodsDesktop
AppVersion={#AppVersion}
AppPublisher=Excusemymanners
AppPublisherURL=https://github.com/Excusemymanners/PodsDesktop
DefaultDirName={autopf}\PodsDesktop
DefaultGroupName=PodsDesktop
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PodsDesktop-Setup
SetupIconFile=podsdesktop.ico
UninstallDisplayIcon={app}\PodsDesktop.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start PodsDesktop when I sign in"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\PodsDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PodsDesktop"; Filename: "{app}\PodsDesktop.exe"
Name: "{autodesktop}\PodsDesktop"; Filename: "{app}\PodsDesktop.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PodsDesktop"; ValueData: """{app}\PodsDesktop.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\PodsDesktop.exe"; Parameters: "--setup"; Description: "Start PodsDesktop and run the setup assistant"; Flags: nowait postinstall skipifsilent
