; 조화의영약_4종 레시피 설치 스크립트 (build.bat 가 /DAppVersion=... 으로 호출)
#ifndef AppVersion
  #define AppVersion "3.0.0"
#endif
#define AppName "조화의영약_4종 레시피"
#define AppExe "HarmonyElixirRecipe.exe"

[Setup]
AppId={{B7C1E3A2-5D4F-4C8E-9A61-2F7D8E0B1C34}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher=Lbeskind
DefaultDirName={autopf}\HarmonyElixirRecipe
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=HarmonyElixirSetup
SetupIconFile=icons\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; 앱이 켜져 있으면 설치 전에 종료를 안내 (앱의 단일 실행 뮤텍스와 같은 이름)
AppMutex=HarmonyElixirRecipe_SingleInstance
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#ifexist AddBackslash(CompilerPath) + "Languages\Korean.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\HarmonyElixirRecipe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; 일반 설치: 마지막 화면의 '실행' 체크박스 / 자동 업데이트(silent): 설치 후 바로 재실행
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: WizardSilent
