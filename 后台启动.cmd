@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 在后台运行（无窗口）。找不到 pythonw 时退回 python，绝不传空参数
set "PYW="
where pythonw >nul 2>nul && set "PYW=pythonw"
if not defined PYW (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    if exist "%%~dpPpythonw.exe" set "PYW=%%~dpPpythonw.exe"
  )
)
if not defined PYW set "PYW=python"
if not defined PYW (
  echo 没有找到 Python，请先安装 Python（勾选 Add to PATH）
  pause
  exit /b 1
)
start "" "%PYW%" "%~dp0server.py"
exit /b
