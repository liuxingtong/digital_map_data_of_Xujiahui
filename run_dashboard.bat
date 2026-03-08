@echo off
cd /d "%~dp0"
echo 正在启动徐家汇空间规划一张图...
echo 启动后请在浏览器打开 http://localhost:8501
echo.
streamlit run streetview_dashboard.py
