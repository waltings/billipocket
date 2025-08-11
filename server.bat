@echo off
REM Billipocket Server Management Script for Windows
REM Kasutamine: server.bat [start|stop|restart|status]

if "%1"=="start" goto start
if "%1"=="stop" goto stop  
if "%1"=="restart" goto restart
if "%1"=="status" goto status
goto help

:start
echo Käivitan Billipocket serverit...
start /min python run.py
timeout /t 3
echo ✅ Server käivitatud!
echo 🌐 URL: http://127.0.0.1:5010
echo Serveri seiskamiseks: server.bat stop
goto end

:stop
echo Peatan serveri...
taskkill /f /im python.exe 2>nul
echo ✅ Server peatatud
goto end

:restart
call :stop
timeout /t 2
call :start
goto end

:status
tasklist | findstr python.exe >nul
if %errorlevel%==0 (
    echo ✅ Server töötab
    echo 🌐 URL: http://127.0.0.1:5010
) else (
    echo ❌ Server ei tööta
)
goto end

:help
echo Billipocket Server Manager
echo =========================
echo.
echo Kasutamine: server.bat {start^|stop^|restart^|status}
echo.
echo   start   - Käivita server
echo   stop    - Peata server
echo   restart - Taaskäivita server  
echo   status  - Näita serveri olekut
echo.

:end