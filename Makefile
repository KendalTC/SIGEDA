COMPOSE=docker compose -f infra/docker/compose.yml
BACKEND=$(COMPOSE) exec backend python src/manage.py

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

start:
	$(COMPOSE) start

stop:
	$(COMPOSE) stop

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec backend bash

db:
	$(COMPOSE) exec postgres psql -U sigeda -d sigeda

migrate:
	$(BACKEND) migrate

makemigrations:
	$(BACKEND) makemigrations

check:
	$(BACKEND) check

test:
	$(BACKEND) test --buffer apps.accounts apps.core apps.configuration apps.documents apps.abonados apps.bitacora apps.respaldos

test-sigeda:
	$(BACKEND) test --buffer apps.abonados apps.bitacora apps.respaldos apps.accounts.tests_sigeda apps.documents.tests_sigeda apps.configuration.tests_sigeda

test-accounts:
	$(BACKEND) test --buffer apps.accounts

test-core:
	$(BACKEND) test --buffer apps.core

test-configuration:
	$(BACKEND) test --buffer apps.configuration

test-documents:
	$(BACKEND) test --buffer apps.documents

run:
	$(BACKEND) runserver 0.0.0.0:8000
release:
	./scripts/build-offline-release.sh
