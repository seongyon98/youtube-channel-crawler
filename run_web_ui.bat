@echo off
chcp 65001 >nul
cd /d "%~dp0"
title YouTube 채널 수집기

echo.
echo  ==========================================
echo    YouTube 채널 수집기
echo  ==========================================
echo.
echo  ※ 이 파일은 화면이 열리지 않을 때만 사용하세요.
echo     보통은 마켓플레이스의 실행 버튼만 누르면 됩니다.
echo.

where python >nul 2>nul
if errorlevel 1 goto NOPYTHON

python -c "import flask, googleapiclient, dotenv, youtube_transcript_api, openai" >nul 2>nul
if errorlevel 1 goto INSTALL
goto RUN

:INSTALL
echo  처음 실행이라 필요한 프로그램을 설치합니다.
echo  1~2분 정도 걸릴 수 있습니다. 잠시만 기다려 주세요...
echo.
python -m pip install -r requirements.txt
echo.
python -c "import flask, googleapiclient, dotenv, youtube_transcript_api, openai" >nul 2>nul
if errorlevel 1 goto INSTALLFAIL
echo  설치가 끝났습니다.
echo.
goto RUN

:RUN
python app.py
echo.
echo  프로그램이 종료되었습니다. 이 창을 닫으셔도 됩니다.
pause
exit /b

:NOPYTHON
echo  [설치 필요] 이 프로그램을 쓰려면 파이썬이 필요합니다.
echo.
echo    1. https://www.python.org/downloads/ 에서 파이썬을 내려받으세요.
echo    2. 설치 화면 맨 아래 "Add python.exe to PATH" 를 꼭 체크하세요.
echo    3. 설치가 끝나면 이 파일을 다시 실행하세요.
echo.
pause
exit /b

:INSTALLFAIL
echo.
echo  [오류] 필요한 프로그램 설치에 실패했습니다.
echo  인터넷 연결을 확인한 뒤 다시 실행해 주세요.
echo.
pause
exit /b
