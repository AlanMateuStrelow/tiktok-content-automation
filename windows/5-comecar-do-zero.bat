@echo off
REM Apaga o banco de conhecimento. Use para limpar os dados de demonstracao
REM antes de comecar a valer. Nao apaga codigo nem configuracao.
chcp 65001 >nul
cd /d "%~dp0.."
title Comecar do zero

if not exist "data\knowledge_base.db" (
  echo O banco ja esta vazio, nada a apagar.
  goto :fim
)

echo Isto APAGA todos os videos, roteiros, oportunidades e metricas do banco.
echo Nao da para desfazer.
echo.
choice /c SN /m "Apagar mesmo"
if errorlevel 2 goto :fim

del "data\knowledge_base.db"
echo.
echo Banco apagado. O painel volta a mostrar tudo zerado.

:fim
echo.
pause
