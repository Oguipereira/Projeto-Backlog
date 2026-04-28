@echo off
chcp 65001 > nul
echo ============================================
echo  Sistema de Gestao de Incidentes - Setup
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+ e tente novamente.
    pause
    exit /b 1
)

REM Create virtual environment if needed
if not exist "venv" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 ( echo [ERRO] Falha ao criar venv. & pause & exit /b 1 )
)

REM Activate
call venv\Scripts\activate.bat

REM Install dependencies
echo Instalando dependencias...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERRO] Falha ao instalar dependencias. & pause & exit /b 1 )

REM Init database
echo Inicializando banco de dados...
python scripts/init_db.py
if errorlevel 1 ( echo [ERRO] Falha ao inicializar banco. & pause & exit /b 1 )

REM Seed data
echo Carregando dados de exemplo...
python scripts/seed_data.py
if errorlevel 1 ( echo [AVISO] Seed nao executado. )

echo.
echo Setup concluido! Execute run.bat para iniciar o dashboard.
pause
