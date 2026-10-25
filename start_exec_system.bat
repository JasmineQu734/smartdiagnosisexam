@echo off
chcp 65001 >nul
title Company Diagnosis System - Launcher
echo ============================================
echo  [1/2] exec model (port 8002)
echo  [2/2] backend   (port 8080)
echo ============================================
echo.

echo Starting exec model on port 8002 ...
start "exec-model-8002" cmd /k "cd /d D:\anaconda\LlamaFactory-main\LlamaFactory-main && set API_PORT=8002&& set API_MODEL_NAME=qwen2.5-3b-exec&& E:\conda\envs\llama311\Scripts\llamafactory-cli.exe api my_infer17.yaml"

echo Waiting 5s for model process to spawn ...
timeout /t 5 /nobreak >nul

echo Starting backend on port 8080 ...
start "backend-8080" cmd /k "cd /d E:\Intrel-Train Industrial && "C:\Program Files\Microsoft\jdk-17.0.18.8-hotspot\bin\java.exe" -Dai.exec-base-url=http://127.0.0.1:8002/v1 -Dai.exec-model=qwen2.5-3b-exec -Dai.exec-timeout-seconds=300 -jar backend\talent-training-api-0.1.0.jar"

echo.
echo Done.
echo   exec-model window: ready when you see "Uvicorn running on ... 8002" (~2 min)
echo   backend window:    ready when you see "Tomcat started on port 8080"
echo Close a window to stop that service.
echo.
pause
