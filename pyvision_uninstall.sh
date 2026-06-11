cat > uninstall_pyvision.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# Script de desinstallation PyVision
# Par defaut, il supprime les services Nginx/systemd PyVision
# mais conserve le dossier projet, la BDD et cloudflared.
# ==========================================================

APP_NAME="${APP_NAME:-pyvision}"
SERVICE_NAME="${SERVICE_NAME:-eryma}"
APP_USER="${APP_USER:-${SUDO_USER:-${USER}}}"
INSTALL_DIR="${INSTALL_DIR:-/home/${APP_USER}/eryma_web}"
DB_NAME="${DB_NAME:-eryma_db}"
DB_USER="${DB_USER:-eryma_user}"

PURGE_DATA="${PURGE_DATA:-false}"
PURGE_DATABASE="${PURGE_DATABASE:-false}"
PURGE_PACKAGES="${PURGE_PACKAGES:-false}"
REMOVE_CLOUDFLARED="${REMOVE_CLOUDFLARED:-false}"

log() {
    echo -e "\n[PyVision] $*"
}

fail() {
    echo -e "\n[ERREUR] $*" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        fail "Lance ce script avec sudo : sudo ./uninstall_pyvision.sh"
    fi
}

remove_pyvision_service() {
    log "Arret et suppression du service ${SERVICE_NAME}.service"

    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
}

remove_nginx_config() {
    log "Suppression de la configuration Nginx PyVision"

    rm -f "/etc/nginx/sites-enabled/${APP_NAME}.conf"
    rm -f "/etc/nginx/sites-available/${APP_NAME}.conf"

    if command -v nginx >/dev/null 2>&1; then
        nginx -t && systemctl reload nginx || true
    fi
}

remove_project_data_if_requested() {
    if [[ "${PURGE_DATA}" != "true" ]]; then
        log "Dossier projet conserve : ${INSTALL_DIR}"
        echo "Pour le supprimer : sudo PURGE_DATA=true ./uninstall_pyvision.sh"
        return 0
    fi

    log "Suppression du dossier projet : ${INSTALL_DIR}"
    rm -rf "${INSTALL_DIR}"
}

remove_database_if_requested() {
    if [[ "${PURGE_DATABASE}" != "true" ]]; then
        log "Base MariaDB conservee : ${DB_NAME}"
        echo "Pour supprimer la BDD : sudo PURGE_DATABASE=true ./uninstall_pyvision.sh"
        return 0
    fi

    log "Suppression de la base MariaDB et de l'utilisateur"
    if command -v mysql >/dev/null 2>&1; then
        mysql <<SQL
DROP DATABASE IF EXISTS \`${DB_NAME}\`;
DROP USER IF EXISTS '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
    fi
}

remove_cloudflared_if_requested() {
    if [[ "${REMOVE_CLOUDFLARED}" != "true" ]]; then
        log "cloudflared conserve"
        echo "Pour supprimer cloudflared : sudo REMOVE_CLOUDFLARED=true ./uninstall_pyvision.sh"
        return 0
    fi

    log "Suppression du service et du paquet cloudflared"
    systemctl stop cloudflared 2>/dev/null || true
    systemctl disable cloudflared 2>/dev/null || true

    if command -v cloudflared >/dev/null 2>&1; then
        cloudflared service uninstall 2>/dev/null || true
    fi

    apt-get purge -y cloudflared || true
    rm -rf /etc/cloudflared
}

remove_packages_if_requested() {
    if [[ "${PURGE_PACKAGES}" != "true" ]]; then
        log "Paquets systeme conserves"
        echo "Pour supprimer les paquets installes : sudo PURGE_PACKAGES=true ./uninstall_pyvision.sh"
        return 0
    fi

    log "Suppression des paquets systeme principaux"
    apt-get purge -y nginx mariadb-server || true
    apt-get autoremove -y || true
}

show_summary() {
    log "Desinstallation terminee"
    echo "Services PyVision et configuration Nginx retires."
    echo "Dossier projet supprime : ${PURGE_DATA}"
    echo "Base de donnees supprimee : ${PURGE_DATABASE}"
    echo "cloudflared supprime : ${REMOVE_CLOUDFLARED}"
    echo "Paquets systeme supprimes : ${PURGE_PACKAGES}"
}

main() {
    require_root
    remove_pyvision_service
    remove_nginx_config
    remove_project_data_if_requested
    remove_database_if_requested
    remove_cloudflared_if_requested
    remove_packages_if_requested
    show_summary
}

main "$@"
EOF

chmod +x uninstall_pyvision.sh
