.PHONY: up down rebuild logs logs-plywatch logs-producer logs-worker logs-web logs-plywatch-rabbit logs-producer-rabbit logs-worker-rabbit logs-rabbitmq ps smoke smoke-rabbit

COMPOSE = docker compose

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) down
	$(COMPOSE) up --build

logs:
	$(COMPOSE) logs -f

logs-plywatch:
	$(COMPOSE) logs -f plywatch

logs-producer:
	$(COMPOSE) logs -f producer-api

logs-worker:
	$(COMPOSE) logs -f producer-worker

logs-web:
	$(COMPOSE) logs -f web

logs-plywatch-rabbit:
	$(COMPOSE) logs -f plywatch-rabbitmq

logs-producer-rabbit:
	$(COMPOSE) logs -f producer-api-rabbitmq

logs-worker-rabbit:
	$(COMPOSE) logs -f producer-worker-rabbitmq producer-worker-slow-rabbitmq

logs-rabbitmq:
	$(COMPOSE) logs -f rabbitmq

ps:
	$(COMPOSE) ps

smoke:
	curl -sS http://127.0.0.1:8080/health
	curl -sS http://127.0.0.1:8090/healthz
	curl -sS http://127.0.0.1:4173
	curl -sS http://127.0.0.1:8080/api/overview
	curl -sS http://127.0.0.1:8080/api/tasks/?limit=10
	curl -sS http://127.0.0.1:8080/api/workers/?limit=10
	curl -sS http://127.0.0.1:8080/api/queues/?limit=10

smoke-rabbit:
	curl -sS http://127.0.0.1:8081/health
	curl -sS http://127.0.0.1:8091/healthz
	curl -sS http://127.0.0.1:8081/api/overview
	curl -sS http://127.0.0.1:8081/api/tasks/?limit=10
	curl -sS http://127.0.0.1:8081/api/workers/?limit=10
	curl -sS http://127.0.0.1:8081/api/queues/?limit=10
