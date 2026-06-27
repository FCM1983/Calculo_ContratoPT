@echo off
setlocal
title Simulador Salarial Portugal 2026
cd /d "%~dp0"

set "PYTHON_CMD="

if exist "%LocalAppData%\Programs\Python\Python314\python.exe" (
  set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python314\python.exe"
)

where py >nul 2>nul
if "%PYTHON_CMD%"=="" if not errorlevel 1 (
  py -3 --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)

if "%PYTHON_CMD%"=="" (
  where python3 >nul 2>nul
  if not errorlevel 1 (
    python3 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
  )
)

if "%PYTHON_CMD%"=="" (
  echo.
  echo Python nao foi encontrado ou o comando aponta para o alias da Microsoft Store.
  echo Abrindo a versao web sem servidor agora.
  echo.
  start "" "%~dp0simulador.html"
  echo.
  echo Para usar a versao Python, instale Python 3.10 ou superior em https://www.python.org/downloads/
  echo Durante a instalacao, marque a opcao "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo Verificando servidores antigos do simulador...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 8080 -and $_.LocalPort -le 8090 } | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -like 'python*') { Stop-Process -Id $p.Id -Force } }" >nul 2>nul

echo Iniciando servidor em segundo plano com: %PYTHON_CMD%
powershell -NoProfile -ExecutionPolicy Bypass -Command "$cmd=$env:PYTHON_CMD; $out=Join-Path $pwd 'simulador_server.out.log'; $err=Join-Path $pwd 'simulador_server.err.log'; Remove-Item $out,$err -ErrorAction SilentlyContinue; if ($cmd -eq 'py -3') { Start-Process -FilePath 'py' -ArgumentList @('-3','-u','app.py') -WorkingDirectory $pwd -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err } else { Start-Process -FilePath $cmd -ArgumentList @('-u','app.py') -WorkingDirectory $pwd -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err }"
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
exit /b 0
