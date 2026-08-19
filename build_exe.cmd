@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul

set "APP_NAME=TG_Username_Hunter"
set "STAGE=.build_stage"
set "BUILD_LOG=build_exe.log"
set "SCRIPT_REV=2026-08-19-r5"

rem Internal build mode. The outer invocation launches this mode through
rem PowerShell Tee-Object so every line is visible live and saved to the log.
if /i "%~1"=="__build" goto build_internal

rem Always start a fresh build log for this run.
>"%BUILD_LOG%" echo ============================================================
>>"%BUILD_LOG%" echo TG Username Hunter - clean isolated Windows build log
>>"%BUILD_LOG%" echo Script revision: %SCRIPT_REV%
>>"%BUILD_LOG%" echo Started: %DATE% %TIME%
>>"%BUILD_LOG%" echo Working directory: %CD%
>>"%BUILD_LOG%" echo ============================================================
>>"%BUILD_LOG%" echo.

cls
echo ============================================================
echo TG Username Hunter - clean isolated Windows build
echo Script revision: %SCRIPT_REV%
echo ============================================================
echo Live output is also written to:
echo %CD%\%BUILD_LOG%
echo ============================================================
echo.

rem Run the actual build as a child CMD process. PowerShell Tee-Object mirrors
rem stdout/stderr to both this console and build_exe.log in real time.
rem Any PowerShell wrapper error is fatal and returns code 99.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; try { $root=(Get-Location).Path; $script=Join-Path -Path $root -ChildPath 'build_exe.cmd'; $log=Join-Path -Path $root -ChildPath 'build_exe.log'; $q=[char]34; $cmdline=$q + $script + $q + ' __build'; & $env:ComSpec /d /c $cmdline 2>&1 | Tee-Object -FilePath $log -Append; $rc=$LASTEXITCODE; if ($null -eq $rc) { $rc=1 }; exit [int]$rc } catch { $msg=($_ | Out-String); Write-Host $msg; try { Add-Content -LiteralPath (Join-Path -Path (Get-Location).Path -ChildPath 'build_exe.log') -Value $msg } catch {}; exit 99 }"
set "BUILD_RC=%ERRORLEVEL%"

>>"%BUILD_LOG%" echo.
>>"%BUILD_LOG%" echo ============================================================
>>"%BUILD_LOG%" echo Finished: %DATE% %TIME%
>>"%BUILD_LOG%" echo Exit code: %BUILD_RC%
>>"%BUILD_LOG%" echo ============================================================

echo.
echo ============================================================
if "%BUILD_RC%"=="0" (
    if exist "dist\%APP_NAME%.exe" (
        echo BUILD COMPLETE
        echo EXE: %CD%\dist\%APP_NAME%.exe
    ) else (
        set "BUILD_RC=98"
        echo BUILD FAILED - wrapper returned success but EXE is missing.
        echo Expected: %CD%\dist\%APP_NAME%.exe
    )
) else (
    echo BUILD FAILED - exit code %BUILD_RC%
)
echo.
echo Full build log:
echo %CD%\%BUILD_LOG%
echo ============================================================
echo.

if not "%BUILD_RC%"=="0" (
    echo Last 40 lines of build log:
    echo ------------------------------------------------------------
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "if (Test-Path -LiteralPath '%BUILD_LOG%') { Get-Content -LiteralPath '%BUILD_LOG%' -Tail 40 }"
    echo ------------------------------------------------------------
    echo.
)

echo Press any key to close this window.
pause >nul
exit /b %BUILD_RC%

:build_internal
echo ============================================================
echo TG Username Hunter - clean isolated Windows build
echo Script revision: %SCRIPT_REV%
echo ============================================================
echo.

echo [0/9] Environment diagnostics...
ver
where py 2>nul
where python 2>nul
where powershell 2>nul
echo.

rem ------------------------------------------------------------
rem 1. Find Python used only to create the virtual environment.
rem ------------------------------------------------------------
echo [1/9] Checking Python...
set "PYTHON_BOOTSTRAP="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_BOOTSTRAP=py -3"

if not defined PYTHON_BOOTSTRAP (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_BOOTSTRAP=python"
)

if not defined PYTHON_BOOTSTRAP (
    echo ERROR: Python 3 was not found in PATH.
    echo Install Python 3.10+ and run this script again.
    exit /b 10
)

%PYTHON_BOOTSTRAP% --version
if errorlevel 1 (
    echo ERROR: Python bootstrap command could not be executed.
    exit /b 11
)

rem ------------------------------------------------------------
rem 2. Create .venv once. Existing .venv is reused.
rem ------------------------------------------------------------
echo [2/9] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv...
    %PYTHON_BOOTSTRAP% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create .venv.
        exit /b 20
    )
) else (
    echo Existing .venv found.
)

rem ------------------------------------------------------------
rem 3. Activate it. All build commands below use .venv.
rem ------------------------------------------------------------
echo [3/9] Activating .venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Could not activate .venv.
    exit /b 30
)

where python
python --version
python -m pip --version

rem ------------------------------------------------------------
rem 4. Install/update dependencies inside .venv.
rem ------------------------------------------------------------
echo [4/9] Installing dependencies...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: Could not update pip/setuptools/wheel.
    exit /b 40
)

python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    exit /b 41
)

rem Save the exact installed dependency set into the build log.
echo.
echo Installed packages:
python -m pip freeze
if errorlevel 1 echo WARNING: pip freeze failed, build will continue.
echo.

rem ------------------------------------------------------------
rem 5. Full clean: remove all previous build output and staging.
rem ------------------------------------------------------------
echo [5/9] Removing previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist ".pyinstaller" rmdir /s /q ".pyinstaller"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
if exist "%APP_NAME%.spec" del /f /q "%APP_NAME%.spec"
for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"

rem ------------------------------------------------------------
rem 6. Create an isolated source stage with Python + Bootstrap frontend.
rem IMPORTANT: config.py is intentionally NEVER copied here.
rem ------------------------------------------------------------
echo [6/9] Creating secret-free build stage...
mkdir "%STAGE%"
if errorlevel 1 (
    echo ERROR: Could not create build stage.
    exit /b 60
)

copy /y "tgh.py" "%STAGE%\tgh.py"
if errorlevel 1 exit /b 61
copy /y "tgh_gui.py" "%STAGE%\tgh_gui.py"
if errorlevel 1 exit /b 62
mkdir "%STAGE%\web"
xcopy /e /i /y "web" "%STAGE%\web"
if errorlevel 1 exit /b 63

if exist "%STAGE%\config.py" (
    echo ERROR: config.py unexpectedly appeared in the build stage.
    exit /b 64
)

rem ------------------------------------------------------------
rem 7. Verify PyInstaller is importable before the long build.
rem ------------------------------------------------------------
echo [7/9] Checking PyInstaller...
python -c "import PyInstaller, sys; print('PyInstaller', PyInstaller.__version__); print('Python', sys.version)"
if errorlevel 1 (
    echo ERROR: PyInstaller could not be imported from .venv.
    exit /b 70
)

rem ------------------------------------------------------------
rem 8. Build from staged sources only.
rem ------------------------------------------------------------
echo [8/9] Building %APP_NAME%.exe from scratch...
echo Frontend data source: %CD%\%STAGE%\web
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --distpath "%CD%\dist" ^
  --workpath "%CD%\.pyinstaller\build" ^
  --specpath "%CD%\.pyinstaller" ^
  --collect-all webview ^
  --collect-submodules pyrogram ^
  --add-data "%CD%\%STAGE%\web;web" ^
  "%STAGE%\tgh_gui.py"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 80
)

rem ------------------------------------------------------------
rem 9. Verify output and clean staging.
rem ------------------------------------------------------------
echo [9/9] Verifying clean output...
if not exist "dist\%APP_NAME%.exe" (
    echo ERROR: Build finished without dist\%APP_NAME%.exe.
    exit /b 90
)

if exist "dist\config.py" (
    echo ERROR: dist\config.py must never be created by the build.
    exit /b 91
)

for %%F in ("dist\%APP_NAME%.exe") do echo EXE size: %%~zF bytes

if exist "%STAGE%" rmdir /s /q "%STAGE%"

echo.
echo ============================================================
echo BUILD COMPLETE
echo EXE: %CD%\dist\%APP_NAME%.exe
echo ============================================================
echo config.py was not used as build input and is not copied to dist.
echo On first launch the GUI starts empty unless a local config.py already exists.
exit /b 0
