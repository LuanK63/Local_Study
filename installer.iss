; Inno Setup Script for Local Study RAG Agent
; Run in Inno Setup Compiler to build the installer

#define AppName "Local Study RAG Agent"
#define AppVersion "1.0.0"
#define AppPublisher "Study Agent"
#define AppExeName "LocalStudyRAGAgent.exe"
#define AppInstallDir "{autopf}\LocalStudyRAGAgent"

[Setup]
AppId={{8F3A2D1E-4B5C-4D6E-8F7A-9B0C1D2E3F4A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={#AppInstallDir}
DefaultGroupName={#AppName}
OutputBaseFilename=LocalStudyRAGAgent_Setup
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=dist\installer
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequiredOverridesAllowed=dialog
ChangesEnvironment=yes

[Languages]
Name: "vietnamese"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo icon trên Desktop"; GroupDescription: "Tùy chọn thêm:"

[Files]
; Main app (built by PyInstaller --onedir)
Source: "dist\LocalStudyRAGAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ollama installer
Source: "dist\bundle\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

; Portable GCC/G++ (winlibs.com portable)
Source: "dist\bundle\gcc\*"; DestDir: "{app}\gcc"; Flags: ignoreversion recursesubdirs createallsubdirs

; Pre-downloaded Ollama model files
; Models stored in: %USERPROFILE%\.ollama\models\
Source: "dist\bundle\models\*"; DestDir: "{userdocs}\..\{userappdata}\..\{userappdata}\..\AppData\Local\Programs\Ollama\models"; \
  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Gỡ cài đặt"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Install Ollama silently
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/S"; StatusMsg: "Đang cài đặt Ollama AI Runtime..."; Flags: waituntilterminated

; Pull models if not already bundled
Filename: "ollama"; Parameters: "pull qwen2.5-coder:7b"; \
  StatusMsg: "Đang kiểm tra model AI (bỏ qua nếu đã có)..."; \
  Flags: waituntilterminated runhidden skipifdoesntexist

Filename: "ollama"; Parameters: "pull nomic-embed-text"; \
  StatusMsg: "Đang kiểm tra embedding model..."; \
  Flags: waituntilterminated runhidden skipifdoesntexist

; Launch app after install
Filename: "{app}\{#AppExeName}"; Description: "Chạy {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop Ollama service on uninstall
Filename: "ollama"; Parameters: "stop"; Flags: runhidden skipifdoesntexist waituntilterminated

[Messages]
WelcomeLabel1=Chào mừng đến với [name]
WelcomeLabel2=Trợ lý học tập AI chạy hoàn toàn offline.%n%nBấm Tiếp để cài đặt.
