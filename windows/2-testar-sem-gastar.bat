@echo off
REM Roda a esteira inteira com dados de demonstracao. Nao chama a API,
REM nao gasta credito. Serve para ver o painel encher.
chcp 65001 >nul
cd /d "%~dp0.."
title Teste sem gastar credito

call :achar_python || goto :fim

echo Produzindo conteudo de DEMONSTRACAO (nao e real, nao gasta credito).
echo.
%PY% -m content_intelligence --dry-run cycle --channel finance
%PY% -m content_intelligence --dry-run cycle --channel tech_ai
echo.
echo Feito. Abra  4-painel.bat  e clique em Atualizar no navegador.
goto :fim

:achar_python
py -3 --version >nul 2>&1 && set "PY=py -3" && exit /b 0
python --version >nul 2>&1 && set "PY=python" && exit /b 0
echo Python nao encontrado. Rode 1-instalar.bat primeiro.
exit /b 1

:fim
echo.
pause
