#!/bin/bash

set -e

PROJECT_NAME="PyVision"
PROJECT_DIR="/home/enzo/eryma_web"
SERVICE_NAME="eryma"
NGINX_SITE_NAME="eryma"

DB_NAME="eryma_db"
DB_USER="eryma_user"
DB_PASSWORD="eryma_password"

APP_PORT="8000"
DOMAIN_NAME="pyvision.enzofile.fr"

echo "=========================================="
echo " Installation automatique de $PROJECT_NAME"
echo "=========================================="

echo ""
echo "[0/12] Vérification du système"

if [ "$EUID" -eq 0 ]; then
    echo "Erreur : ne lance pas ce script directement en root."
    echo "Utilise plutôt : ./install.sh"
    exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
    echo "Erreur : sudo n'est pas installé."
    echo "Installe sudo avant de relancer le script."
    exit 1
fi

if [ ! -f "run.py" ]; then
    echo "Erreur : run.py introuvable."
    echo "Lance ce script depuis le dossier du projet PyVision."
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "Erreur : requirements.txt introuvable."
    exit 1
fi

echo ""
echo "[1/12] Mise à jour de la liste des paquets"
sudo apt update

echo ""
echo "[2/12] Installation des prérequis système"
sudo apt install -y \
    git \
    curl \
    nano \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    nginx \
    mariadb-server \
    mariadb-client \
    default-libmysqlclient-dev \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1

echo ""
echo "[3/12] Préparation du dossier projet"

CURRENT_DIR="$(pwd)"

if [ "$CURRENT_DIR" != "$PROJECT_DIR" ]; then
    echo "Le projet est actuellement dans : $CURRENT_DIR"
    echo "Copie du projet vers : $PROJECT_DIR"

    sudo mkdir -p "$PROJECT_DIR"
    sudo rsync -a --exclude ".git" --exclude ".venv" "$CURRENT_DIR"/ "$PROJECT_DIR"/
    sudo chown -R "$USER":"$USER" "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

echo ""
echo "[4/12] Création de l'environnement virtuel Python"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    echo "L'environnement virtuel existe déjà."
fi

source .venv/bin/activate

echo ""
echo "[5/12] Installation des dépendances Python"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

if ! python -c "import gunicorn" >/dev/null 2>&1; then
    echo "Gunicorn absent de requirements.txt, installation..."
    pip install gunicorn
fi

echo ""
echo "[6/12] Activation et démarrage de MariaDB"
sudo systemctl enable mariadb
sudo systemctl start mariadb

echo ""
echo "[7/12] Création de la base de données et de l'utilisateur MariaDB"

sudo mysql <<EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF

echo ""
echo "[8/12] Création du fichier .env si absent"

if [ ! -f "$PROJECT_DIR/.env" ]; then
cat > "$PROJECT_DIR/.env" <<EOF
SECRET_KEY=change_me

DB_HOST=localhost
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

SQLALCHEMY_DATABASE_URI=mysql+pymysql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=example@example.com
SMTP_PASSWORD=change_me
MAIL_FROM=example@example.com
ALERT_EMAIL=client@example.com

CAMERA_RTSP_URL=rtsp://user:password@192.168.1.50:554/stream1
EOF
    echo "Fichier .env créé."
else
    echo "Le fichier .env existe déjà, il n'a pas été modifié."
fi

echo ""
echo "[9/12] Création des dossiers nécessaires"

mkdir -p "$PROJECT_DIR/recordings"
mkdir -p "$PROJECT_DIR/app/static/downloads"

chmod 755 "$PROJECT_DIR/recordings"
chmod 755 "$PROJECT_DIR/app/static/downloads"

echo ""
echo "[10/12] Création du service systemd"

sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Application PyVision Flask avec Gunicorn
After=network.target mariadb.service

[Service]
User=$USER
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn -w 3 -b 127.0.0.1:$APP_PORT run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "[11/12] Configuration de Nginx"

sudo tee /etc/nginx/sites-available/$NGINX_SITE_NAME > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME _;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $PROJECT_DIR/app/static/;
    }

    location /recordings/ {
        alias $PROJECT_DIR/recordings/;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$NGINX_SITE_NAME /etc/nginx/sites-enabled/$NGINX_SITE_NAME

if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm -f /etc/nginx/sites-enabled/default
fi

echo ""
echo "[12/12] Redémarrage des services"

sudo nginx -t

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
sudo systemctl restart nginx

echo ""
echo "=========================================="
echo " Installation terminée avec succès"
echo "=========================================="
echo ""
echo "Commandes utiles :"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo "  sudo nginx -t"
echo "  sudo systemctl restart $SERVICE_NAME"
echo ""
echo "Configuration à modifier si besoin :"
echo "  nano $PROJECT_DIR/.env"
echo ""
echo "Accès local :"
echo "  http://IP_DU_SERVEUR"
echo ""
echo "Accès domaine :"
echo "  http://$DOMAIN_NAME"
echo ""
