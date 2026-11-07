#!/usr/bin/env bash
# Nightly database backup, kept for 14 days:  ./deploy/backup.sh
# cron (crontab -e):  30 3 * * * /opt/win/deploy/backup.sh >> /opt/win/backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
file="backups/win-$(date +%F).dump"
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U win -Fc win > "$file.tmp"
mv "$file.tmp" "$file"
find backups -name 'win-*.dump' -mtime +14 -delete
echo "$(date '+%F %T') saved $file ($(du -h "$file" | cut -f1))"
