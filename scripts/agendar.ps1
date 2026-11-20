# Cria (ou recria) a tarefa "MyWhoosh2Garmin" no Agendador de Tarefas do Windows.
# Roda main.py a cada 15 min, como o seu usuário, só quando você está logado:
# o token do Garmin e a senha no Credential Manager pertencem ao seu perfil.
#
#   powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1 -IntervaloMinutos 30
#   powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1 -Remover

param(
    [int]$IntervaloMinutos = 15,
    [switch]$Remover
)

$ErrorActionPreference = 'Stop'
$Nome = 'MyWhoosh2Garmin'

if ($Remover) {
    Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
    Write-Output "Tarefa '$Nome' removida."
    return
}

$Projeto = Split-Path -Parent $PSScriptRoot
# pythonw: sem janela de console piscando a cada execução. O log vai para sync.log.
$Python = Join-Path $Projeto 'venv\Scripts\pythonw.exe'
if (-not (Test-Path $Python)) { throw "Não achei $Python. Crie o venv antes (veja o README)." }

$Acao = New-ScheduledTaskAction -Execute $Python -Argument '"main.py"' -WorkingDirectory $Projeto
$Gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMinutos)
# Também ao fazer logon, para pegar o treino feito com o PC desligado.
$Logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Config = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Nome -Action $Acao -Trigger @($Gatilho, $Logon) `
    -Settings $Config -Principal $Principal -Force | Out-Null

Write-Output "Tarefa '$Nome' criada: a cada $IntervaloMinutos min e no logon."
Write-Output "Testar agora:  Start-ScheduledTask -TaskName $Nome ; depois veja sync.log"
