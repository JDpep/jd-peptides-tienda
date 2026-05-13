#!/usr/bin/env bash
# JD Peptides — backup manual de la base Supabase (Postgres) via pg_dump.
#
# Uso:
#   1) Pull las env vars de Vercel:    vercel env pull .env.local --environment=production
#   2) Carga DATABASE_URL al shell:    set -a; source .env.local; set +a
#   3) Ejecuta:                        ./scripts/backup_supabase.sh
#
# Resultado:
#   backups/jdp_YYYY-MM-DD_HHMM.sql.gz
#
# Para automatizar diario (cron en macOS/Linux con la cuenta del usuario):
#   crontab -e
#   0 3 * * *  cd /Users/albertoamiga/Desktop/JDP/tienda && ./scripts/backup_supabase.sh >> backups/backup.log 2>&1
#
# Restore (cuidado, sobreescribe):
#   gunzip -c backups/jdp_2026-05-13_0300.sql.gz | psql "$DATABASE_URL"

set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "❌ DATABASE_URL no está configurada. Ejecuta:" >&2
    echo "   vercel env pull .env.local --environment=production" >&2
    echo "   set -a; source .env.local; set +a" >&2
    exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "❌ pg_dump no está instalado." >&2
    echo "   macOS:   brew install postgresql" >&2
    echo "   Ubuntu:  sudo apt-get install postgresql-client" >&2
    exit 1
fi

BACKUP_DIR="$(dirname "$0")/../backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y-%m-%d_%H%M)
OUTPUT="$BACKUP_DIR/jdp_${TIMESTAMP}.sql.gz"

echo "→ Backup en curso: $OUTPUT"
pg_dump "$DATABASE_URL" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    --quote-all-identifiers \
    | gzip -9 > "$OUTPUT"

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "✓ Backup completado: $OUTPUT ($SIZE)"

# Retención: conservar últimos 14 días
echo "→ Limpiando backups > 14 días"
find "$BACKUP_DIR" -name 'jdp_*.sql.gz' -mtime +14 -delete -print 2>/dev/null || true

echo "✓ Backup terminado en $(date)"
