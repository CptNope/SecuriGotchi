@echo off
setlocal
cd /d "%~dp0"
set "SECURIGOTCHI_DATA_DIR=%~dp0.securigotchi\interactive"
if not exist ".venv\Scripts\python.exe" (
  echo Install the core first: py -3.12 install.py
  pause
  exit /b 1
)
echo Wi-Fi health and device discovery on a network you own or may inspect.
echo Sends one ping per address; no port scans or security commands.
set "SG_NETWORK="
set /p "SG_NETWORK=Enter authorized private IPv4 subnet, for example 192.168.0.0/24: "
if not defined SG_NETWORK exit /b 1
rem Pass input via an environment variable so cmd never interprets it as code.
".venv\Scripts\python.exe" -c "import os,sys; from gotchi_network import validate_network; scope=str(validate_network(os.environ['SG_NETWORK'])); from gotchi_monitor import run_once; print(run_once(network=True,discover_network=scope)); from gotchi_network import overview; import json; print(json.dumps(overview(),indent=2))"
echo.
echo Refresh the dashboard network panel. This was one sample, not a background monitor.
pause
