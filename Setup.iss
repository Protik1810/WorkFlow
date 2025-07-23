; Inno Setup Script for WORKFLOW Application

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={{C1D4A6E8-3C7F-4B0A-B879-C727B42D9842}
AppName=WORKFLOW
AppVersion=2.0.0
AppPublisher=Protik Das
DefaultDirName={autopf}\WORKFLOW
DefaultGroupName=WORKFLOW
OutputDir=D:\update\Output
OutputBaseFilename=WORKFLOW_Setup_v2.0.0
SetupIconFile=D:\update\installation.ico


; Allows 64-bit mode on x64 systems, otherwise stays in 32-bit mode
ArchitecturesInstallIn64BitMode=x64
; Allows the installer to run on both 32-bit and 64-bit Windows
ArchitecturesAllowed=x86 x64


WizardImageFile=D:\update\logob.bmp 
WizardSmallImageFile=D:\update\logo .bmp


Compression=lzma
SolidCompression=yes
WizardStyle=modern

; This shows your Terms and Conditions and requires acceptance.
LicenseFile=D:\update\TERMS.md

; ADDED: This line ensures the directory selection page is shown to the user.
DisableDirPage=no

; ADDED: This line shows the selected path on the final confirmation page.
AlwaysShowDirOnReadyPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; This packages all files from your PyInstaller output folder.
Source: "D:\update\dist\WorkflowApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; This version relies on the icon embedded in WorkflowApp.exe
Name: "{group}\WORKFLOW"; Filename: "{app}\WorkflowApp.exe"
Name: "{group}\{cm:UninstallProgram,WORKFLOW}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\WORKFLOW"; Filename: "{app}\WorkflowApp.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WorkflowApp.exe"; Description: "{cm:LaunchProgram,WORKFLOW}"; Flags: nowait postinstall skipifsilent
