@echo off
chcp 65001 >nul
title Omni-Urban AI 系統啟動器
echo ===================================================
echo   啟動 Omni-Urban AI 決策平台...
echo   請勿關閉此視窗，系統將自動開啟瀏覽器。
echo ===================================================
echo.

streamlit run 0儀表板.py
echo.
pause