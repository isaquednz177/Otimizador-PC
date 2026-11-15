@echo off
setlocal
title Gerar OtimizadorPC.exe
cd /d "%~dp0"

echo ============================================================
echo   Gerar o OtimizadorPC.exe
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O Python nao foi encontrado no PATH.
    echo Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [1/4] Instalando o que falta...
python -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERRO] Nao deu para instalar. Confira a internet.
    pause
    exit /b 1
)

echo.
echo [2/4] Rodando os testes (o .exe so sai se todos passarem)...
python -m unittest discover -s tests
if errorlevel 1 (
    echo [ERRO] Algum teste falhou. O .exe NAO foi gerado.
    pause
    exit /b 1
)

echo.
echo [3/4] Apagando compilacoes antigas...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set ICONE=
if exist icone.ico set ICONE=--icon=icone.ico

echo.
echo [4/4] Compilando (de 1 a 5 minutos)...
python -m PyInstaller --onefile --windowed --uac-admin --clean --noconfirm ^
    --name OtimizadorPC --collect-data customtkinter ^
    --add-data "otimizador_pc\arte;otimizador_pc\arte" %ICONE% main.py
if errorlevel 1 (
    echo [ERRO] A compilacao falhou. Leia a mensagem do PyInstaller acima.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Pronto: dist\OtimizadorPC.exe
echo ============================================================
echo O .exe nao tem assinatura digital: o Windows pode avisar ou bloquear.
echo Se bloquear, use o executar.bat.
explorer dist
pause
