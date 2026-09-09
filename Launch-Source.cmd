@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 decal_cooker_gui.py %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if not errorlevel 1 (
  python decal_cooker_gui.py %*
  exit /b %errorlevel%
)
echo Python 3 was not found. Install Python 3.11 or newer with Tcl/Tk support.
pause
exit /b 1
