@echo off
REM Abre o Otimizador PC pelo Python, sem janela preta.
REM Este e o jeito recomendado: o .exe nao tem assinatura digital, e o
REM Controle de Aplicativos Inteligente do Windows 11 costuma bloquea-lo.
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo O Python nao foi encontrado. Instale em https://www.python.org/downloads/
    echo e marque "Add python.exe to PATH" na instalacao.
    pause
    exit /b 1
)

python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Instalando o customtkinter, so na primeira vez...
    python -m pip install -r requirements.txt
)

start "" pythonw "%~dp0main.py"
