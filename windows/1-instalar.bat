@echo off
REM Instala o projeto. Rode uma vez, depois de baixar o repositorio.
chcp 65001 >nul
cd /d "%~dp0.."
title Instalando o Content Intelligence

call :achar_python || goto :fim

echo Instalando... isso demora um pouco na primeira vez.
echo.
%PY% -m pip install -e ".[dev]"
if errorlevel 1 (
  echo.
  echo FALHOU. Copie a mensagem vermelha acima e peca ajuda.
  goto :fim
)

echo.
echo Pronto. Agora abra o arquivo  2-testar-sem-gastar.bat
goto :fim

:achar_python
REM O py.exe vem com o instalador do python.org e nao depende do PATH.
py -3 --version >nul 2>&1 && set "PY=py -3" && exit /b 0
python --version >nul 2>&1 && set "PY=python" && exit /b 0
echo Python nao encontrado.
echo Instale em https://www.python.org/downloads/ e marque
echo "Add python.exe to PATH" na primeira tela do instalador.
exit /b 1

:fim
echo.
pause
