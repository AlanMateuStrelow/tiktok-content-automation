@echo off
REM Sobe o painel de gestao a vista e abre o navegador.
REM Esta janela fica aberta segurando o servidor: fechar derruba o painel.
chcp 65001 >nul
cd /d "%~dp0.."
title Painel - nao feche esta janela

call :achar_python || goto :fim

echo O painel vai abrir no navegador.
echo Deixe ESTA JANELA ABERTA enquanto usar. Ctrl+C encerra.
echo.
%PY% -m content_intelligence dashboard
goto :fim

:achar_python
py -3 --version >nul 2>&1 && set "PY=py -3" && exit /b 0
python --version >nul 2>&1 && set "PY=python" && exit /b 0
echo Python nao encontrado. Rode 1-instalar.bat primeiro.
exit /b 1

:fim
echo.
pause
