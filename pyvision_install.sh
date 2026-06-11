cat > install_pyvision.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# Script d'installation PyVision
# Depot : https://github.com/Awekano/PyVision
# Systeme cible : Debian 12 / Ubuntu Server
# ==========================================================

APP_NAME="${APP_NAME:-pyvision}"
SERVICE_NAME="${SERVICE_NAME:-eryma}"
APP_USER="${APP_USER:-${SUDO_USER:-${USER}}}"
APP_GROUP="$(id -gn "${APP_USER}" 2>/dev/null || echo "${APP_USER}")"
INSTALL_DIR="${INSTALL_DIR:-/home/${APP_USER}/eryma_web}"
REPO_URL="${REPO_URL:-https://github.com/Awekano/PyVision.git}"
BRANCH="${BRANCH:-main}"

DB_NAME="${DB_NAME:-eryma_db}"
DB_USER="${DB_USER:-eryma_user}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 24)}"

DOMAIN="${DOMAIN:-_}"
APP_PORT="${APP_PORT:-8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"

ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=')}"

CLOUDFLARED_TOKEN="${CLOUDFLARED_TOKEN:-}"
OVERWRITE_ENV="${OVERWRITE_ENV:-false}"

log() {
    echo -e "\n[PyVision] $*"
}

fail() {
    echo -e "\n[ERREUR] $*" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        fail "Lance ce script avec sudo : sudo ./install_pyvision.sh"
    fi
}

check_user() {
    if ! id "${APP_USER}" >/dev/null 2>&1; then
        fail "L'utilisateur ${APP_USER} n'existe pas. Cree-le ou lance avec APP_USER=<utilisateur>."
    fi
}

install_apt_dependencies() {
    log "Installation des paquets systeme"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        nginx \
        mariadb-server \
        python3 \
        python3-venv \
        python3-pip \
        python3-dev \
        build-essential \
        pkg-config \
        default-libmysqlclient-dev \
        libmariadb-dev \
        ffmpeg \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        openssl
}

install_cloudflared() {
    log "Installation de cloudflared"

    if command -v cloudflared >/dev/null 2>&1; then
        cloudflared --version || true
        log "cloudflared est deja installe"
        return 0
    fi

    local arch deb_url
    arch="$(dpkg --print-architecture)"

    case "${arch}" in
        amd64)
            deb_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
            ;;
        arm64)
            deb_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb"
            ;;
        armhf|arm)
            deb_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm.deb"
            ;;
        *)
            fail "Architecture non supportee automatiquement pour cloudflared : ${arch}"
            ;;
    esac

    curl -L --fail --show-error "${deb_url}" -o /tmp/cloudflared.deb
    apt-get install -y /tmp/cloudflared.deb
    rm -f /tmp/cloudflared.deb
    cloudflared --version || true
}

install_or_update_project() {
    log "Installation du depot PyVision dans ${INSTALL_DIR}"

    mkdir -p "$(dirname "${INSTALL_DIR}")"

    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        log "Depot deja present, mise a jour en fast-forward"
        sudo -u "${APP_USER}" git -C "${INSTALL_DIR}" fetch origin "${BRANCH}"
        sudo -u "${APP_USER}" git -C "${INSTALL_DIR}" checkout "${BRANCH}"
        sudo -u "${APP_USER}" git -C "${INSTALL_DIR}" pull --ff-only origin "${BRANCH}"
    elif [[ -e "${INSTALL_DIR}" ]]; then
        fail "${INSTALL_DIR} existe deja mais ce n'est pas un depot Git. Renomme le dossier ou choisis INSTALL_DIR."
    else
        sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
    fi

    mkdir -p "${INSTALL_DIR}/recordings"
    chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
}

install_python_dependencies() {
    log "Creation du venv Python et installation des dependances"

    sudo -u "${APP_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
    sudo -u "${APP_USER}" "${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
    sudo -u "${APP_USER}" "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
}

configure_database() {
    log "Configuration MariaDB"

    systemctl enable --now mariadb

    mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
}

create_env_file() {
    log "Creation du fichier .env"

    local env_file="${INSTALL_DIR}/.env"
    local secret_key
    secret_key="$(openssl rand -hex 32)"

    if [[ -f "${env_file}" && "${OVERWRITE_ENV}" != "true" ]]; then
        log ".env existe deja, il est conserve. Utilise OVERWRITE_ENV=true pour le regenerer."
        return 0
    fi

    if [[ -f "${env_file}" ]]; then
        cp "${env_file}" "${env_file}.bak.$(date +%Y%m%d_%H%M%S)"
    fi

    cat > "${env_file}" <<ENVEOF
# ==========================================================
# Configuration PyVision
# Modifier les valeurs avant la mise en production
# ==========================================================

SECRET_KEY=${secret_key}
DATABASE_URL=mysql+pymysql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}

# Camera IP
# Exemple Hikvision/Hanwha selon modele : rtsp://utilisateur:motdepasse@172.20.0.50:554/Streaming/Channels/101
RTSP_URL=rtsp://utilisateur:motdepasse@172.20.0.50:554/Streaming/Channels/101
RTSP_TRANSPORT=tcp
MJPEG_QUALITY=80

# Certaines parties du projet utilisent CAMERA_URL pour la detection serveur
CAMERA_URL=rtsp://utilisateur:motdepasse@172.20.0.50:554/Streaming/Channels/101
RECORDINGS_DIR=${INSTALL_DIR}/recordings
MOTION_MIN_AREA=2500
RECORD_SECONDS=15

# SMTP pour les alertes mail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=adresse@gmail.com
SMTP_PASSWORD=mot_de_passe_application
SMTP_FROM=adresse@gmail.com
ALERT_EMAIL_TO=destinataire@example.com
ENVEOF

    chown "${APP_USER}:${APP_GROUP}" "${env_file}"
    chmod 600 "${env_file}"
}

init_flask_database() {
    log "Initialisation des tables et du compte administrateur"

    local credentials_file="/home/${APP_USER}/pyvision_admin_credentials.txt"

    sudo -u "${APP_USER}" env \
        ADMIN_USERNAME="${ADMIN_USERNAME}" \
        ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
        bash -c "cd '${INSTALL_DIR}' && .venv/bin/python - <<'PY'
import os
from datetime import time
from app import create_app, db
from app.models import User, AlertSettings

app = create_app()

with app.app_context():
    db.create_all()

    username = os.environ.get('ADMIN_USERNAME', 'admin')
    password = os.environ.get('ADMIN_PASSWORD')

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, role='admin', is_active=True)
        user.set_password(password)
        db.session.add(user)
    else:
        user.role = 'admin'
        user.is_active = True

    if AlertSettings.query.first() is None:
        db.session.add(AlertSettings(enabled=True, start_time=time(22, 0), end_time=time(6, 0)))

    db.session.commit()
PY"

    cat > "${credentials_file}" <<CREDEOF
Identifiants administrateur PyVision
Utilisateur : ${ADMIN_USERNAME}
Mot de passe : ${ADMIN_PASSWORD}

Fichier genere automatiquement pendant l'installation.
Change ce mot de passe apres la premiere connexion si besoin.
CREDEOF
    chown "${APP_USER}:${APP_GROUP}" "${credentials_file}"
    chmod 600 "${credentials_file}"
}

create_systemd_service() {
    log "Creation du service systemd ${SERVICE_NAME}.service"

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SERVICEEOF
[Unit]
Description=PyVision Flask application
After=network.target mariadb.service
Wants=mariadb.service

[Service]
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/.venv/bin/gunicorn --timeout 120 --workers ${GUNICORN_WORKERS} --bind 127.0.0.1:${APP_PORT} run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
    systemctl enable --now "${SERVICE_NAME}"
}

configure_nginx() {
    log "Configuration Nginx"

    cat > "/etc/nginx/sites-available/${APP_NAME}.conf" <<NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 2G;

    location /live_feed {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINXEOF

    ln -sfn "/etc/nginx/sites-available/${APP_NAME}.conf" "/etc/nginx/sites-enabled/${APP_NAME}.conf"
    rm -f /etc/nginx/sites-enabled/default

    nginx -t
    systemctl enable --now nginx
    systemctl reload nginx
}

configure_cloudflared_service_if_token() {
    if [[ -z "${CLOUDFLARED_TOKEN}" ]]; then
        log "cloudflared est installe mais aucun tunnel n'est configure automatiquement."
        echo "Ajoute CLOUDFLARED_TOKEN=<token> avant le script ou suis CONFIGURATION_PYVISION.txt."
        return 0
    fi

    log "Installation du service cloudflared via token Cloudflare Tunnel"
    cloudflared service install "${CLOUDFLARED_TOKEN}" || true
    systemctl enable --now cloudflared || true
}

show_summary() {
    log "Installation terminee"
    echo "Projet        : ${INSTALL_DIR}"
    echo "Service       : ${SERVICE_NAME}.service"
    echo "Nginx         : /etc/nginx/sites-available/${APP_NAME}.conf"
    echo "Base MariaDB  : ${DB_NAME}"
    echo "Utilisateur DB: ${DB_USER}"
    echo "Fichier .env  : ${INSTALL_DIR}/.env"
    echo "Identifiants  : /home/${APP_USER}/pyvision_admin_credentials.txt"
    echo
    echo "Commandes utiles :"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  sudo systemctl restart ${SERVICE_NAME}"
    echo "  sudo nginx -t && sudo systemctl reload nginx"
    echo
    echo "Avant utilisation, modifie surtout RTSP_URL, CAMERA_URL, SMTP_* et ALERT_EMAIL_TO dans ${INSTALL_DIR}/.env"
}

main() {
    require_root
    check_user
    install_apt_dependencies
    install_cloudflared
    install_or_update_project
    install_python_dependencies
    configure_database
    create_env_file
    init_flask_database
    create_systemd_service
    configure_nginx
    configure_cloudflared_service_if_token
    show_summary
}

main "$@"
EOF

chmod +x install_pyvision.sh
