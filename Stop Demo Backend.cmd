@echo off
cd /d "%~dp0"
if not exist backend\state mkdir backend\state
echo stop>backend\state\laptop-demo.stop
echo Requested backend shutdown. The public dashboard stays online.
pause
