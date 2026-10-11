@echo off
setlocal
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do (
  start "" "%%P" "%~dp0StudyClock.py"
  exit /b 0
)
for /f "delims=" %%P in ('where pyw.exe 2^>nul') do (
  start "" "%%P" "%~dp0StudyClock.py"
  exit /b 0
)
echo Python 3 is required. Install Python 3.10 or newer and try again.
pause
