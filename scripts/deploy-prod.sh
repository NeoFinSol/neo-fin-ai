#!/usr/bin/env bash
# NeoFin AI - Production Deployment Script
# Usage: ./scripts/deploy-prod.sh
#
# This script:
#   1. Validates .env file exists
#   2. Builds all Docker images
#   3. Runs database migrations
#   4. Starts all services
#   5. Shows service status

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NeoFin AI - Production Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Validate .env file
echo -e "${YELLOW}[1/5] Validating environment...${NC}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: $ENV_FILE not found!${NC}"
    echo "Please copy .env.example to .env and fill in required values."
    exit 1
fi

# Check required variables
required_vars=("POSTGRES_USER" "POSTGRES_PASSWORD" "POSTGRES_DB" "API_KEY")
for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" "$ENV_FILE"; then
        echo -e "${RED}ERROR: Required variable $var is not set in $ENV_FILE${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✓ Environment validated${NC}"
echo ""

# Step 2: Build all images
echo -e "${YELLOW}[2/5] Building Docker images...${NC}"
docker-compose -f "$COMPOSE_FILE" build --no-cache
echo -e "${GREEN}✓ Images built${NC}"
echo ""

# Step 3: Run database migrations
echo -e "${YELLOW}[3/5] Running database migrations...${NC}"
docker-compose -f "$COMPOSE_FILE" run --rm backend-migrate
echo -e "${GREEN}✓ Migrations completed${NC}"
echo ""

# Step 4: Start all services
echo -e "${YELLOW}[4/5] Starting services...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Step 5: Show status
echo -e "${YELLOW}[5/5] Service status:${NC}"
docker-compose -f "$COMPOSE_FILE" ps

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Frontend: http://localhost"
echo "Backend API: http://localhost/api/"
echo "Health check: http://localhost/system/health"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  docker-compose -f $COMPOSE_FILE logs -f"
echo ""
echo -e "${YELLOW}To stop services:${NC}"
echo "  docker-compose -f $COMPOSE_FILE down"
echo ""
echo -e "${YELLOW}To restart services:${NC}"
echo "  docker-compose -f $COMPOSE_FILE restart"
echo ""
