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
  
  ; Copia o instalador do MeshAgent
  File "meshagent64.exe"
  
  ; Cria atalho para desinstalar
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Adiciona no registro para iniciar com Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "NexusAdminAgent" '"$INSTDIR\agente.exe"'
  
  ; Executa o agente silenciosamente após instalar
  ExecShell "" "$INSTDIR\agente.exe"
SectionEnd

Section "Uninstall"
  ; Mata o processo se estiver rodando
  ExecWait "taskkill /F /IM agente.exe"
  
  ; Remove do registro
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "NexusAdminAgent"
  
  Delete "$INSTDIR\agente.exe"
  Delete "$INSTDIR\meshagent64.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
