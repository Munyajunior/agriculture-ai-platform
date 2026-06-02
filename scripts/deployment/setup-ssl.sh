#!/bin/bash

# scripts/deployment/setup-ssl.sh


# SSL Certificate Setup Script using Let's Encrypt

set -e

DOMAIN=${1:-yourdomain.com}
EMAIL=${2:-admin@$DOMAIN}

echo "Setting up SSL certificates for $DOMAIN"

# Install certbot
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Stop nginx if running
docker-compose -f infrastructure/docker/docker-compose.yml stop nginx

# Obtain SSL certificate
certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email

# Copy certificates to nginx ssl directory
mkdir -p infrastructure/docker/nginx/ssl
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem infrastructure/docker/nginx/ssl/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem infrastructure/docker/nginx/ssl/

# Set up auto-renewal
(crontab -l 2>/dev/null; echo "0 0 1 * * certbot renew --quiet && docker-compose -f infrastructure/docker/docker-compose.yml restart nginx") | crontab -

echo "SSL certificates installed successfully!"