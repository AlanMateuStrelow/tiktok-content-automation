@echo off
REM A rotina do dia, de verdade: CHAMA A API E GASTA CREDITO.
REM Equivale a docs/OPERACAO.md -> "Rotina diaria".
chcp 65001 >nul
cd /d "%~dp0.."
title Rotina diaria

call :achar_python || goto :fim
call :checar_chave || goto :fim

echo ATENCAO: isto chama a API da Anthropic e GASTA CREDITO da sua conta.
echo.
choice /c SN /m "Continuar"
if errorlevel 2 goto :fim

echo.
echo [1/4] Como esta o buffer...
%PY% -m content_intelligence health
echo.
echo [2/4] Produzindo para finance...
%PY% -m content_intelligence cycle --channel finance
echo.
echo [3/4] Produzindo para tech_ai...
%PY% -m content_intelligence cycle --channel tech_ai
echo.
echo [4/4] Relatorio do dia em out\daily.md
%PY% -m content_intelligence report daily --out out/daily.md
echo.
echo Feito. Abra 4-painel.bat para ver a fila.
goto :fim

:achar_python
py -3 --version >nul 2>&1 && set "PY=py -3" && exit /b 0
python --version >nul 2>&1 && set "PY=python" && exit /b 0
echo Python nao encontrado. Rode 1-instalar.bat primeiro.
exit /b 1

:checar_chave
REM Erro claro agora vale mais que um erro de autenticacao la na frente.
if defined ANTHROPIC_API_KEY exit /b 0
if exist ".env" findstr /r /c:"^ANTHROPIC_API_KEY=..*" ".env" >nul && exit /b 0
echo Falta a chave da API.
echo.
echo   1. copie .env.example para .env
echo   2. abra o .env no Bloco de Notas
echo   3. cole a chave depois do sinal de igual em ANTHROPIC_API_KEY=
echo.
echo Sem chave, use 2-testar-sem-gastar.bat.
exit /b 1

:fim
echo.
pause
