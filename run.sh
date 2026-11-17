#!/bin/bash

# 1. Verificam daca fisierul .env exista
if [ ! -f .env ]; then
    echo "======================================================================"
    echo " [NECESSARY ACTION] .env file is missing."
    echo " Copying .env.example -^> .env..."
    cp .env.example .env
    echo ""
    echo " Please open the .env file from the root,"
    echo " add your key to GEMINI_API_KEY, save file and run it again."
    echo "======================================================================"
    exit 1
fi

# 2. Verificam daca exista mediul virtual. Daca nu, il cream.
if [ ! -f .venv/bin/python ]; then
    echo "======================================================================"
    echo " [SETUP] First run detected. Creating virtual environment..."
    echo "======================================================================"
    python3 -m venv .venv
    
    echo " [SETUP] Installing requirements.txt dependencies..."
    .venv/bin/pip install -r requirements.txt
    echo "======================================================================"
fi

# 3. Rulam aplicatia folosind Python-ul din venv si pasam argumentele ("$@")
.venv/bin/python -m src.main "$@"