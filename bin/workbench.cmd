@echo off
rem TEMU 工作台（独立版）：一键启动 → 自动打开浏览器
start "" http://127.0.0.1:3790
node "%~dp0..\plugin\temu-panel\server.mjs" --port 3790
