#!/bin/bash

set -e

PROJECT_DIR="/home/enzo/eryma_web"
SERVICE_NAME="eryma"

echo "=========================================="
echo " Désinstallation du projet PyVision / Eryma"
echo "=========================================="

echo "[1/5] Arrêt du service"
sudo systemctl stop $SERVICE_NAME || true
sudo systemctl disable $SERVICE_NAME || true

echo "[2/5] Suppression du service systemd"
sudo rm -f /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload

echo "[3/5] Suppression de la configuration Nginx"
sudo rm -f /etc/nginx/sites-enabled/eryma
sudo rm -f /etc/nginx/sites-available/eryma
sudo nginx -t
sudo systemctl restart nginx

echo "[4/5] Conservation du dossier projet"
echo "Le dossier $PROJECT_DIR n'est pas supprimé automatiquement pour éviter la perte des vidéos et du code."

echo "[5/5] Fin"
echo "Désinstallation terminée."
