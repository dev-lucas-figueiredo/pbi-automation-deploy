@echo off
setlocal enabledelayedexpansion
title Pipeline Power BI - Deploy (GESTAO)
chcp 65001 >nul

echo.
echo =====================================================
echo  PIPELINE DE PUBLICACAO POWER BI - MODO GESTAO
echo  (1 painel por gestao / RESPONSAVEL)
echo =====================================================
echo.

REM ---- 1. Verificar ambiente virtual ----
if not exist "env\Scripts\activate.bat" (
    echo [ERRO] Ambiente virtual nao encontrado em env\
    echo Crie com: python -m venv env
    echo.
    pause
    exit /b 1
)

REM ---- 2. Verificar .env ----
if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado no diretorio atual.
    echo Crie um .env com TENANT_ID, CLIENT_ID, CLIENT_SECRET, WORKSPACE_ID.
    echo.
    pause
    exit /b 1
)

REM ---- 3. Verificar pacote Python ----
if not exist "pbi_deploy\main.py" (
    echo [ERRO] pbi_deploy\main.py nao encontrado no diretorio atual.
    echo.
    pause
    exit /b 1
)

REM ---- 4. Ativar ambiente virtual ----
echo [1/4] Ativando ambiente virtual...
call env\Scripts\activate.bat

REM ---- 5. Garantir biblioteca rich ----
echo [2/4] Verificando dependencia 'rich'...
pip show rich >nul 2>&1
if errorlevel 1 (
    echo        rich nao instalado. Instalando agora...
    pip install rich --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar rich. Verifique sua conexao.
        pause
        exit /b 1
    )
)

REM ---- 6. Instalar demais dependencias via requirements.txt ----
echo [3/4] Verificando demais dependencias...
if not exist "requirements.txt" (
    echo [ERRO] requirements.txt nao encontrado no diretorio atual.
    pause
    exit /b 1
)
pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias. Verifique requirements.txt e sua conexao.
    pause
    exit /b 1
)

REM ---- 7. Executar pipeline (modo gestao) ----
echo [4/4] Executando pipeline (modo GESTAO)...
echo.
python -m pbi_deploy.main gestao
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% equ 0 (
    echo =====================================================
    echo  PROCESSO FINALIZADO COM SUCESSO  ^(exit %EXIT_CODE%^)
    echo =====================================================
) else if %EXIT_CODE% equ 130 (
    echo =====================================================
    echo  PROCESSO INTERROMPIDO PELO USUARIO  ^(exit %EXIT_CODE%^)
    echo =====================================================
) else (
    echo =====================================================
    echo  PROCESSO FINALIZADO COM FALHAS  ^(exit %EXIT_CODE%^)
    echo  Veja a pasta logs\ para o log estruturado em JSON.
    echo =====================================================
)
echo.
pause
