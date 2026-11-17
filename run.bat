@echo off
setlocal

:: 1. Verificam daca fisierul .env exista
if not exist .env (
    echo ======================================================================
    echo  [NECESSARY ACTION] .env file is missing.
    echo  Copying .env.example -^> .env...
    copy .env.example .env >nul
    echo.
    echo  Please open the .env file from the root,
    echo  add your key to GEMINI_API_KEY, save file
    echo  and run it again.
    echo ======================================================================
    pause
    exit /b 1
)

:: 2. Verificam daca exista mediul virtual. Daca nu, il cream.
if not exist .venv\Scripts\python.exe (
    echo ======================================================================
    echo  [SETUP] First run detected. Creating virtual environment...
    echo ======================================================================
    python -m venv .venv
    
    echo  [SETUP] Installing requirements.txt dependencies...
    .venv\Scripts\pip install -r requirements.txt
    echo ======================================================================
)

:: 3. Rulam aplicatia folosind Python-ul din venv si pasam argumentele (%*)
.venv\Scripts\python -m src.main %*