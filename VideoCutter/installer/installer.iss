[Setup]
AppName=VideoCutter
AppVersion=1.0
DefaultDirName={autopf}\VideoCutter
DefaultGroupName=VideoCutter
OutputDir=.
OutputBaseFilename=VideoCutter_Installer
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\VideoCutter\VideoCutter.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\VideoCutter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VideoCutter"; Filename: "{app}\VideoCutter.exe"
Name: "{group}\{cm:UninstallProgram,VideoCutter}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VideoCutter"; Filename: "{app}\VideoCutter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoCutter.exe"; Description: "{cm:LaunchProgram,VideoCutter}"; Flags: nowait postinstall skipifsilent
