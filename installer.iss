; installer.iss — Inno Setup script for RamWarden.
;
; Wraps the PyInstaller one-dir build (dist\RamWarden\) into dist\RamWarden-Setup.exe.
; Everything the app needs, including the embedded CPython runtime and
; python3xx.dll, is installed to a real directory — which is the whole point:
; a zip lets Explorer "run" RamWarden.exe straight out of the archive, where
; _internal\ was never extracted and loading the Python DLL fails.
;
; Built by build_installer.py, which supplies AppVersion from main.pyw.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "RamWarden"
#define AppPublisher "Mikey"
#define AppExe "RamWarden.exe"

[Setup]
; Never change AppId — it is what lets a new setup upgrade an existing
; install in place instead of leaving two entries in Apps & Features.
AppId={{7C2F1B4A-9D3E-4A61-8F27-1E5B6C0A9D34}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}

; Per-user install, deliberately. updater.py applies updates by robocopying
; over the install directory from the running (non-elevated) app, so the app
; must live somewhere it can write. With PrivilegesRequired=lowest,
; {autopf} resolves to %LOCALAPPDATA%\Programs. It also means no UAC prompt.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; An upgrade from RamBo would otherwise keep its "RamBo" Start Menu folder. (The install folder
; is kept as it was: renaming it would strand the old copy.)
UsePreviousGroup=no

; The app is 64-bit (PyInstaller builds against the 64-bit interpreter).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=dist
OutputBaseFilename=RamWarden-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
; Without this, Apps & Features lists it as "RamWarden version 1.0.0" even though
; it already shows the version in its own column.
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Use the Restart Manager to shut down a running RamWarden before overwriting it,
; rather than failing mid-copy or demanding a reboot.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Ticked by default — the desktop icon is how most people will actually launch
; RamWarden — but it is a task rather than a fixed [Icons] entry so it can be
; unticked. Inno records the choice under the uninstall key and restores it on
; the next run, so a silent self-update honours an earlier opt-out instead of
; quietly putting the icon back.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; The entire one-dir bundle: RamWarden.exe plus _internal\ (python3xx.dll, the
; stdlib zip, psutil, Tcl/Tk, and the bundled icon/logo).
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Upgrading from RamBo (1.5.1 and earlier): its program and shortcuts would be left behind,
; pointing at an exe that no longer matches the files beside it.
Type: files; Name: "{app}\RamBo.exe"
Type: files; Name: "{autodesktop}\RamBo.lnk"
Type: filesandordirs; Name: "{autoprograms}\RamBo"

[Icons]
; A real Start Menu folder, so the uninstaller is reachable from there and not
; only from Apps & Features.
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; No `skipifsilent` — updater.py runs this installer with /SILENT and then
; exits, so this entry is what relaunches RamWarden once the update finishes.
; Adding skipifsilent back would leave the user staring at a closed app.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall

[UninstallDelete]
; Older builds self-updated by robocopying a bundle over the install directory,
; which could leave files in _internal\ that this installer has no record of.
; Clear the folder explicitly so upgrading from such a build and then
; uninstalling does not leave anything behind.
;
; Never list "{app}" itself here: unins000.exe runs from that directory, and
; deleting it out from under itself leaves an orphaned entry in Apps & Features
; pointing at an uninstaller that no longer exists.
Type: filesandordirs; Name: "{app}\_internal"
