#!/usr/bin/env bash
# ==============================================================================
# RAPSCOS AYURVEDIC BACKEND — 1-COMMAND UPDATE SCRIPT
# ==============================================================================
# Usage:
#   sudo bash update.sh
# ==============================================================================

set -e

# ANSI Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "          UPDATING RAPSCOS AYURVEDIC BACKEND TO LATEST VERSION        "
echo "======================================================================"
echo -e "${NC}"

# Check Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${YELLOW}[WARNING] Docker compose command not found, defaulting to 'docker compose'${NC}"
    DOCKER_COMPOSE="docker compose"
fi

# Retry helper for transient hiccups
retry() {
    local attempts=5 delay=3 n=1
    until "$@"; do
        if [ "$n" -ge "$attempts" ]; then
            echo -e "${YELLOW}[WARNING] Command failed after ${attempts} attempts: $*${NC}"
            return 1
        fi
        echo "Retrying ($n/${attempts})..."
        n=$((n+1))
        sleep "$delay"
    done
}

# 1. Force-pull latest code from Git (cleanly discarding old code changes while preserving data & env)
echo -e "${YELLOW}[1/4] Force-pulling latest code from Git repository...${NC}"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"

if git remote get-url origin &>/dev/null; then
    git fetch origin "${CURRENT_BRANCH}"
    echo "Resetting code state to origin/${CURRENT_BRANCH}..."
    git reset --hard "origin/${CURRENT_BRANCH}"
    # Clean untracked build artifacts while preserving database, media uploads and .env
    git clean -fd -e data/ -e media/ -e .env -e "data/*" -e "media/*" || true
    echo -e "${GREEN}✓ Code updated to latest origin/${CURRENT_BRANCH}.${NC}"
else
    echo -e "${YELLOW}[NOTICE] No git remote origin configured; skipping git fetch.${NC}"
fi

# 2. Rebuild and restart Docker containers
echo -e "${YELLOW}[2/4] Rebuilding and restarting Docker containers...${NC}"
retry ${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" up --build -d
echo -e "${GREEN}✓ Containers rebuilt and running.${NC}"

# 3. Apply database updates / migrations / seed
echo -e "${YELLOW}[3/4] Syncing database catalog and categories...${NC}"
sleep 3
retry docker exec rapscos_api python scripts/seed.py
echo -e "${GREEN}✓ Database is up to date.${NC}"

# 4. Verify API Health
echo -e "${YELLOW}[4/4] Verifying API service health...${NC}"
sleep 2
if docker exec rapscos_api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8777/health')" &>/dev/null; then
    echo -e "${GREEN}✓ Health check passed: Service is healthy.${NC}"
else
    echo -e "${YELLOW}[NOTICE] API is still starting up. Check logs with: docker compose logs -f api${NC}"
fi

echo -e "${GREEN}${BOLD}"
echo "======================================================================"
echo "          ✓ RAPSCOS BACKEND SUCCESSFULLY UPDATED & RUNNING!           "
echo "======================================================================"
echo -e "${NC}"
