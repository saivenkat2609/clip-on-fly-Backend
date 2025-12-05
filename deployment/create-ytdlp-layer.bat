@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

echo ============================================
echo   Building AWS Lambda Custom Layer
echo   Contents: yt-dlp + Node.js
echo ============================================

REM Clean old build
IF EXIST opt rmdir /S /Q opt
IF EXIST lambda_layer.zip del lambda_layer.zip

REM Create correct directory structure
mkdir opt\bin

echo --------------------------------------------
echo   Downloading yt-dlp (Linux binary)
echo --------------------------------------------
curl -L -o opt\bin\yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp

echo --------------------------------------------
echo   Downloading Node.js Linux Binary (x64)
echo --------------------------------------------
set NODE_VERSION=v20.18.0
curl -L -o node.tar.xz https://nodejs.org/dist/%NODE_VERSION%/node-%NODE_VERSION%-linux-x64.tar.xz

echo Extracting Node.js using PowerShell...
powershell -Command "tar -xf 'node.tar.xz'"

copy node-%NODE_VERSION%-linux-x64\bin\node opt\bin\

REM Cleanup Node artifacts
rmdir /S /Q node-%NODE_VERSION%-linux-x64
del node.tar.xz

echo --------------------------------------------
echo   Creating lambda_layer.zip
echo --------------------------------------------
powershell -Command "Compress-Archive -Path 'opt' -DestinationPath 'lambda_layer.zip' -Force"

echo ============================================
echo   DONE!
echo   Upload lambda_layer.zip to AWS Lambda
echo ============================================

ENDLOCAL
pause
