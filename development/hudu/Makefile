.PHONY: help up down restart logs logs-app ps shell pull backup clean gen-secrets

DC := docker compose

help:
	@echo "Hudu self-hosted (Caddy-fronted) — dev stack"
	@echo ""
	@echo "Bringup:"
	@echo "  make gen-secrets   Print SECRET_KEY_BASE / PASSWORD_KEY / TWO_FACTOR_KEY (paste into .env)"
	@echo "  make up            Start db + redis + app + worker"
	@echo "  make down          Stop containers (data persists in volumes)"
	@echo "  make restart       Restart only the app container (after env changes)"
	@echo "  make logs          Tail logs for the whole stack"
	@echo "  make logs-app      Tail only the Rails app"
	@echo "  make ps            Container status"
	@echo "  make pull          Pull latest hududocker/hudu image"
	@echo "  make clean         DESTRUCTIVE — drop all volumes (wipes DB + uploads)"
	@echo ""
	@echo "Operations:"
	@echo "  make shell         Bash shell on the app container"
	@echo "  make backup        Snapshot postgres + .env to ./backups/<timestamp>/"

gen-secrets:
	@echo "# Paste these into .env:"
	@echo "SECRET_KEY_BASE=$$(openssl rand -hex 64)"
	@echo "PASSWORD_KEY=$$(openssl rand -hex 16)"
	@echo "TWO_FACTOR_KEY=$$(openssl rand -hex 16)"

up:
	$(DC) up -d
	@echo ""
	@echo "Hudu starting. First boot runs migrations — give it ~60s."
	@echo "URL:   https://$$(grep ^DOMAIN .env | cut -d= -f2)/"
	@echo "Tail:  make logs-app"

down:
	$(DC) down

restart:
	$(DC) restart app worker

logs:
	$(DC) logs -f --tail=100

logs-app:
	$(DC) logs -f --tail=100 app

ps:
	$(DC) ps

shell:
	$(DC) exec app bash

pull:
	$(DC) pull

# ── Backup / Restore ───────────────────────────────────────────────────
BACKUP_DIR := backups
TS := $(shell date -u +%Y%m%dT%H%M%SZ)

backup:
	@mkdir -p $(BACKUP_DIR)/$(TS)
	@echo "Snapshotting → $(BACKUP_DIR)/$(TS)/"
	@$(DC) exec -T db pg_dump -U "$$(grep ^DB_USERNAME .env | cut -d= -f2)" \
	    -d "$$(grep ^DB_NAME .env | cut -d= -f2)" \
	    --clean --if-exists \
	    | gzip > $(BACKUP_DIR)/$(TS)/postgres.sql.gz
	@cp .env $(BACKUP_DIR)/$(TS)/env.bak
	@chmod 600 $(BACKUP_DIR)/$(TS)/env.bak
	@echo "✓ backup complete: $(BACKUP_DIR)/$(TS)/"
	@echo "  ⚠ env.bak contains encryption keys — keep this directory secure"
	@du -sh $(BACKUP_DIR)/$(TS)/*

clean:
	@echo "WARNING: this will delete all Hudu data (postgres, uploads)."
	@echo "         If you have real data here, .env contains the only keys"
	@echo "         that can decrypt the passwords. Back up first."
	@printf "Type 'yes' to confirm: " && read confirm && [ "$$confirm" = "yes" ]
	$(DC) down -v
