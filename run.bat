@echo off
chcp 65001 > nul
echo ============================================
echo  Sistema de Gestao de Incidentes
echo ============================================
echo.

REM Instala dependencias se ainda nao foram instaladas
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias pela primeira vez...
    pip install -r requirements.txt -q
)

REM Inicializa o banco se nao existir
if not exist "data\incidents.db" (
    echo Inicializando banco de dados...
    python scripts/init_db.py
    echo Carregando dados de exemplo...
    python scripts/seed_data.py
)

echo Iniciando dashboard em http://localhost:8501
echo O navegador abrira automaticamente.
echo Pressione Ctrl+C para encerrar.
echo.

python -m streamlit run dashboard/Home.py
