@echo off
call "%~dp0..\..\scripts\windows\start-red.bat" -VenvPath "%USERPROFILE%\redenv" -InstanceName "YOUR_INSTANCE" -Restart -RestartExitCodes 1,26
