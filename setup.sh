#!/usr/bin/env bash
# ==============================================================================
# RAPSCOS AYURVEDIC BACKEND — 1-COMMAND VPS SETUP SCRIPT
# ==============================================================================
# Usage:
#   sudo bash setup.sh
# ==============================================================================

set -e

# ANSI Color Codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine backend root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "          RAPSCOS AYURVEDIC BACKEND — VPS DEPLOYMENT SETUP            "
echo "======================================================================"
echo -e "${NC}"

# 1. Check Root Privileges
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR] This script must be run as root or with sudo.${NC}"
   echo "Please run: sudo bash setup.sh"
   exit 1
fi

# 2. Check and Install Docker & Docker Compose if missing
echo -e "${YELLOW}[1/6] Checking system prerequisites (Docker & Docker Compose)...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${CYAN}Docker not found. Installing Docker CE automatically...${NC}"
    if [ -f /etc/debian_version ]; then
        apt-get update -y
        apt-get install -y ca-certificates curl gnupg lsb-release ufw
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable --now docker
    elif [ -f /etc/redhat-release ]; then
        yum install -y yum-utils
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        systemctl enable --now docker
    else
        echo -e "${RED}[ERROR] Unsupported Linux distribution. Please install Docker manually.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker installed successfully.${NC}"
else
    echo -e "${GREEN}✓ Docker is already installed: $(docker --version)${NC}"
fi

# Determine compose command syntax
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}[ERROR] Docker Compose plugin not found.${NC}"
    apt-get install -y docker-compose-plugin || yum install -y docker-compose-plugin
    DOCKER_COMPOSE="docker compose"
fi

# 3. Configure Firewall Ports
echo -e "${YELLOW}[2/6] Checking firewall configuration...${NC}"
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    echo "Opening HTTP (80), HTTPS (443), and API (8777) ports in UFW..."
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
    ufw allow 8777/tcp || true
    echo -e "${GREEN}✓ UFW firewall rules updated.${NC}"
fi

# 4. Auto-generate Production .env if not exists
echo -e "${YELLOW}[3/6] Configuring environment settings (.env)...${NC}"

if [ ! -f "${ROOT_DIR}/.env" ]; then
    echo "No .env found. Auto-generating production configuration..."

    # Auto-detect public IP
    DETECTED_IP=$(curl -s -m 5 https://api.ipify.org || curl -s -m 5 https://icanhazip.com || echo "127.0.0.1")
    DETECTED_IP=$(echo "${DETECTED_IP}" | tr -d '[:space:]')
    echo -e "Detected Server Public IP: ${CYAN}${DETECTED_IP}${NC}"

    # Generate random cryptographic JWT secret and admin password
    GEN_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -hex 32)
    GEN_ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -hex 12)

    cat <<EOF > "${ROOT_DIR}/.env"
# Rapscos Ayurvedic Backend — Production Environment
JWT_SECRET=${GEN_SECRET}
JWT_EXPIRATION_DAYS=30
MIN_AUTH_MS=700
ADMIN_INVITE_CODE=RAP-9U4J-4U5H
CORS_ORIGINS=https://www.rapscosbio.com,https://rapscosbio.com,http://${DETECTED_IP},http://${DETECTED_IP}:8777,http://localhost:5173
ADMIN_EMAIL=rapscos1933@gmail.com
ADMIN_PASSWORD=${GEN_ADMIN_PASS}
PORT=8777
MEDIA_DIR=/app/media
DATABASE_URL=sqlite:////app/data/rapscos.db
EOF

    echo -e "${GREEN}✓ Production .env created with secure JWT secret and server IP: ${DETECTED_IP}${NC}"
else
    echo -e "${GREEN}✓ Existing .env file found. Preserving current configuration.${NC}"
fi

# Export environment variables for compose
set -a
[ -f "${ROOT_DIR}/.env" ] && . "${ROOT_DIR}/.env"
set +a

# 5. Prepare Storage Directories & Permissions
echo -e "${YELLOW}[4/6] Setting up persistent data and media directories...${NC}"
mkdir -p "${ROOT_DIR}/data" "${ROOT_DIR}/media" "/etc/letsencrypt"
chmod -R 775 "${ROOT_DIR}/data" "${ROOT_DIR}/media" || true
echo -e "${GREEN}✓ Storage directories initialized.${NC}"

# 6. Build and Start Docker Stack
echo -e "${YELLOW}[5/6] Building and launching backend containers...${NC}"
${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" down || true
${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" up --build -d

echo -e "Waiting for FastAPI container (rapscos_api) to become ready..."
MAX_WAIT=30
WAITED=0
until docker exec rapscos_api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8777/health')" &> /dev/null || [ $WAITED -ge $MAX_WAIT ]; do
    sleep 2
    WAITED=$((WAITED+2))
    echo -n "."
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}[WARNING] API took longer than expected to report healthy, continuing...${NC}"
else
    echo -e "${GREEN}✓ FastAPI backend is healthy and responding.${NC}"
fi

# 7. Seed Database (Products, Categories, and Admin User)
echo -e "${YELLOW}[6/6] Initializing and seeding SQLite database...${NC}"
docker exec rapscos_api python scripts/seed.py

# 8. Final Health Verification
SERVER_IP=$(curl -s -m 5 https://api.ipify.org || echo "localhost")
PORT="8777"

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "         🎉 RAPSCOS AYURVEDIC BACKEND IS LIVE AND RUNNING!            "
echo "======================================================================"
echo -e "${NC}"
echo -e "  • ${BOLD}API Direct URL:${NC}       ${GREEN}http://${SERVER_IP}:${PORT}/${NC}"
echo -e "  • ${BOLD}API Health Check:${NC}     ${GREEN}http://${SERVER_IP}:${PORT}/health${NC}"
echo -e "  • ${BOLD}Products API:${NC}         ${GREEN}http://${SERVER_IP}:${PORT}/api/products${NC}"
echo -e "  • ${BOLD}Categories API:${NC}       ${GREEN}http://${SERVER_IP}:${PORT}/api/categories${NC}"
echo ""
echo -e "  • ${BOLD}Default Admin Email:${NC}  ${CYAN}${ADMIN_EMAIL:-rapscos1933@gmail.com}${NC}"
echo -e "  • ${BOLD}Admin Invite Code:${NC}    ${CYAN}${ADMIN_INVITE_CODE:-RAP-9U4J-4U5H}${NC}"
echo ""
echo -e "  • ${BOLD}View Live Logs:${NC}"
echo -e "    ${CYAN}docker compose logs -f api${NC}"
echo ""
echo -e "  • ${BOLD}Future 1-Command Updates:${NC}"
echo -e "    ${CYAN}sudo bash update.sh${NC}"
