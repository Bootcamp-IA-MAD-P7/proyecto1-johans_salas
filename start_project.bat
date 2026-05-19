@echo off
title Taximetro Digital

echo ========================================
echo    INICIANDO TAXIMETRO DIGITAL
echo ========================================

IF NOT EXIST venv (
    echo Creando ambiente virtual...
    py -3.10 -m venv venv
)

echo Activando ambiente virtual...
call venv\Scripts\activate

echo Actualizando pip...
python -m pip install --upgrade pip

echo Instalando dependencias necesarias...
pip install kivy==2.2.1 kivymd==1.1.1 reportlab

echo ========================================
echo      INICIANDO APLICACION
echo ========================================

python taximetro.py

pause
