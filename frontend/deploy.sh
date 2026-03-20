#!/bin/bash
# Deploy front.agentsapp.integration-ai.ru
# Static SPA — served by nginx, no Node.js server needed
# Run on server: sudo bash /opt/app-agent/frontforbackagent/deploy.sh
set -e
cd /opt/app-agent/frontforbackagent
DOMAIN=front.agentsapp.integration-ai.ru
SITES_AV="/etc/nginx/sites-available/$DOMAIN"
SITES_EN="/etc/nginx/sites-enabled/$DOMAIN"

echo "[1/7] npm install..."
npm ci 2>/dev/null || npm install

echo "[2/7] nuxt generate (static SPA build)..."
NODE_ENV=production npm run build

echo "[3/7] apt: nginx, certbot..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

echo "[4/7] /var/www/certbot..."
mkdir -p /var/www/certbot

echo "[5/7] nginx: HTTP config (for certbot)..."
cp deploy/nginx-http.conf "$SITES_AV"
ln -sf "$SITES_AV" "$SITES_EN"
nginx -t && systemctl reload nginx

echo "[6/7] certbot: SSL for $DOMAIN..."
certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" \
  --non-interactive --agree-tos --email admin@integration-ai.ru

echo "[7/7] nginx: HTTPS config..."
cp deploy/nginx-https.conf "$SITES_AV"
nginx -t && systemctl reload nginx

echo "[8] ufw: 80, 443..."
ufw allow 80
ufw allow 443
ufw status | head -5

echo ""
echo "Done. Open https://$DOMAIN/"
echo "Static SPA served by nginx — no Node.js process needed."
