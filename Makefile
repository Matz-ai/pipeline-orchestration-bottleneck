# Sous Windows sans make : .\make.ps1 <cible>

PYTHON  ?= python
COMPOSE := docker compose
-include .env
KESTRA_PORT ?= 8080

.DEFAULT_GOAL := help
.PHONY: help up down logs ps ui shell data explore check duckdb clean

help: ## Liste les commandes disponibles
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-7s %s\n", $$1, $$2}'

up: ## Construit l'image si besoin et démarre Kestra en arrière-plan
	$(COMPOSE) up -d --build
	@echo "Kestra démarre (~1-2 min). Suivre : make logs / make ps. UI : http://localhost:$(KESTRA_PORT)"

down: ## Arrête Kestra (les flows et exécutions sont conservés)
	$(COMPOSE) down

logs: ## Suit les logs Kestra (Ctrl+C pour sortir)
	$(COMPOSE) logs -f kestra

ps: ## État du conteneur (attendre "healthy")
	$(COMPOSE) ps

ui: ## Affiche l'URL de l'UI Kestra
	@echo "http://localhost:$(KESTRA_PORT)"

shell: ## Ouvre un shell dans le conteneur Kestra
	$(COMPOSE) exec kestra bash

data: ## Télécharge les 3 .xlsx OC dans data/raw/
	$(PYTHON) scripts/download_data.py

explore: ## Profil des 3 fichiers sources (lecture seule)
	$(COMPOSE) exec kestra python /bottleneck/scripts/explore.py

check: ## Rejoue la chaîne dans DuckDB et lance les tests
	$(COMPOSE) exec kestra python /bottleneck/scripts/run_local.py

duckdb: ## Ouvre data/warehouse.duckdb dans le CLI DuckDB, en lecture seule (.quit pour sortir)
	$(COMPOSE) exec kestra duckdb -readonly -box /bottleneck/data/warehouse.duckdb

clean: ## DESTRUCTIF : arrête Kestra et supprime ses volumes (flows, historique)
	@printf "Supprimer les volumes Kestra (flows + historique d'exécutions) ? [y/N] " && read ans && [ "$$ans" = "y" ]
	$(COMPOSE) down -v
