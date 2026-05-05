@echo off
setlocal enabledelayedexpansion

REM Convenience launcher: install requirements if needed, then run fincli.
REM Passes any extra arguments through to `python -m fincli`.

echo Checking for Python...

:FindPythonCommand
for %%A in (python python3) do (
    where /Q %%A
    if !errorlevel! EQU 0 (
        set "PYTHON_CMD=%%A"
        goto :Found
    )
)

echo Python not found. Please install Python.
pause
exit /B 1

:Found
%PYTHON_CMD% scripts/check_requirements.py requirements.txt
if errorlevel 1 (
    echo Installing missing packages...
    %PYTHON_CMD% -m pip install -r requirements.txt
)

%PYTHON_CMD% -m fincli %*
pause
