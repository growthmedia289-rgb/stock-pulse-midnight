@echo off
setlocal
cd /d "%~dp0"
set "STOCKPULSE_DEMO=1"
set "CONDA_CMD=conda"
if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_CMD=%USERPROFILE%\anaconda3\condabin\conda.bat"
echo PREVIEW MODE: all market data and AI replies are illustrative.
call "%CONDA_CMD%" run --no-capture-output -n stockpulse311 python app.py
pause
