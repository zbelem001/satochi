#!/bin/bash

# Configuration pour que la fenêtre Zenity s'affiche depuis un processus en arrière-plan
export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

# Se placer dans le bon dossier (gère les espaces dans le chemin)
cd "/home/zia/Documents/MOI/MES PROJETS DEV/satochi"

# Activer l'environnement virtuel et lancer le bot
source venv/bin/activate
python3 models/daily_swing_bot.py
