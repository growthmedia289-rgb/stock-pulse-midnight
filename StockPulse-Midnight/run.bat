@echo off
setlocal
cd /d "%~dp0"
set "CONDA_CMD=conda"
if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_CMD=%USERPROFILE%\anaconda3\condabin\conda.bat"
echo Starting StockPulse using the stockpulse311 environment...
echo Open http://127.0.0.1:5000 after the server starts.
call "%CONDA_CMD%" run --no-capture-output -n stockpulse311 python app.py
if errorlevel 1 echo Startup failed. Read the error above and the README setup steps.
pause
