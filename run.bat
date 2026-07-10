@echo off
title COT Analytics Dashboard
echo Starting COT Analytics Dashboard...
.venv\Scripts\streamlit.exe run app.py --server.port 8502
pause
