@echo off
if "%REPLYMIND_MODE%"=="" set REPLYMIND_MODE=demo
echo ReplyMind console -^> http://127.0.0.1:8000  (mode: %REPLYMIND_MODE%)
python -m uvicorn app.review.webapp:app --reload
