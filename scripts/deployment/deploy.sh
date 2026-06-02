#!/bin/bash
# scripts/deployment/deploy.sh


# Agriculture AI Platform Deployment Script
# This script handles deployment to production/staging environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
COMPOSE_FILE="infrastructure/docker/docker-compose.yml"
ENV_FILE=".env.${ENVIRONMENT}"

echo -e "${GREEN}Deploying Agriculture AI Platform - ${ENVIRONMENT} environment${NC}"

# Check if environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Environment file $ENV_FILE not found!${NC}"
    echo "Please create $ENV_FILE with required configuration"
    exit 1
fi

# Load environment variables
set -a
source $ENV_FILE
set +a

# Backup database before deployment
echo -e "${YELLOW}Backing up database...${NC}"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
docker exec agri_postgres pg_dump -U agri_user agriculture_ai > backups/$BACKUP_FILE
echo -e "${GREEN}Database backup created: $BACKUP_FILE${NC}"

# Pull latest images
echo -e "${YELLOW}Pulling latest Docker images...${NC}"
docker-compose -f $COMPOSE_FILE pull

# Build images
echo -e "${YELLOW}Building services...${NC}"
docker-compose -f $COMPOSE_FILE build

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose -f $COMPOSE_FILE run --rm api-gateway alembic upgrade head

# Deploy services
echo -e "${YELLOW}Deploying services...${NC}"
docker-compose -f $COMPOSE_FILE up -d --remove-orphans

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check service health
services=("api-gateway" "auth-service" "ai-service" "analytics-service" "media-service" "model-registry" "sync-service")

for service in "${services[@]}"; do
    if docker ps | grep -q "agri_$service"; then
        echo -e "${GREEN}✓ $service is running${NC}"
    else
        echo -e "${RED}✗ $service failed to start${NC}"
        docker logs "agri_$service" --tail 50
        exit 1
    fi
done

# Run smoke tests
echo -e "${YELLOW}Running smoke tests...${NC}"
curl -f http://localhost:8000/health || {
    echo -e "${RED}Health check failed!${NC}"
    exit 1
}

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}Platform is available at: http://localhost:8000${NC}"
echo -e "${GREEN}API Documentation: http://localhost:8000/api/docs${NC}"
echo -e "${GREEN}Grafana: http://localhost:3000 (admin/${GRAFANA_PASSWORD:-admin})${NC}"
echo -e "${GREEN}Prometheus: http://localhost:9090${NC}"
echo -e "${GREEN}MinIO Console: http://localhost:9001 (${MINIO_ROOT_USER:-minioadmin}/${MINIO_ROOT_PASSWORD:-minioadmin123})${NC}"