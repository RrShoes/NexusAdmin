!define APPNAME "NexusAdmin Agent"
!define COMPANYNAME "NexusAdmin"
!define DESCRIPTION "Agente de monitoramento para o NexusAdmin"
!define EXECUTABLE "agente.exe"

Name "${APPNAME}"
OutFile "NexusAdmin_Installer.exe"
InstallDir "$PROGRAMFILES\NexusAdmin Agent"

RequestExecutionLevel admin

Page directory
Page instfiles

Section "Instalar"
  SetOutPath "$INSTDIR"
  
  ; Copia o executável gerado pelo pyinstaller
  File "dist\agente.exe"
  
  ; Cria atalho para desinstalar
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Executa o agente silenciosamente após instalar
  ExecShell "" "$INSTDIR\agente.exe"
SectionEnd

Section "Uninstall"
  ; Mata o processo se estiver rodando
  ExecWait "taskkill /F /IM agente.exe"
  
  Delete "$INSTDIR\agente.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
