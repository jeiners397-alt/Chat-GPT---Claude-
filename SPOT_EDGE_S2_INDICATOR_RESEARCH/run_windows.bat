@echo off
REM Ejecuta SPOT EDGE S2 en Windows. Requiere Python 3.10+ instalado y en el PATH.
setlocal

cd /d "%~dp0"

if not exist venv (
    echo Creando entorno virtual...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt

echo.
echo Ejecutando investigacion de indicadores (experimento principal: 60 dias)...
python spot_indicator_research.py --lookback-days 60 %*

echo.
echo Listo. Revisa la carpeta RESULTADOS_SPOT_EDGE_S2
pause
