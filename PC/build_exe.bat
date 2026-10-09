@echo off
cd /d "%~dp0"

echo ========================================
echo  Build AirFlowTrace.exe (portabile)
echo ========================================
echo Cartella: %CD%
echo.

echo === Dipendenze ===
python -m pip install -r requirements.txt
if errorlevel 1 goto :err

echo === Pulizia build precedente ===
if exist build rmdir /s /q build
if exist dist\AirFlowTrace.exe del /f dist\AirFlowTrace.exe

echo === Compilazione ===
python -m PyInstaller --noconfirm --clean AirFlowTrace.spec
if errorlevel 1 goto :err

if exist dist\AirFlowTrace.exe (
    echo.
    echo OK: dist\AirFlowTrace.exe
    dir dist\AirFlowTrace.exe
) else (
    echo ERRORE: exe non generato
    goto :err
)

pause
exit /b 0

:err
echo.
echo ERRORE durante la build. Controlla i messaggi sopra.
pause
exit /b 1
