# Async Request Processing API

API assíncrona de processamento de solicitações usando Python · FastAPI · Kafka · MySQL · Redis.

## Arquitetura

Hexagonal (Ports & Adapters). O domínio não conhece Kafka, MySQL, Redis nem FastAPI.

```
HTTP Request
    │
    ▼
FastAPI Router (Adapter Inbound)
    │
    ▼
Use Case (Application)
    │
    ▼
Port (Protocol / Interface)
    │
    ▼
Adapter Outbound (SQLAlchemy / Kafka / Redis)
```

### Fluxo

1. `POST /requests` → persiste `PENDING` no MySQL → publica `requests.created` no Kafka → retorna 201.
2. Consumer (processo separado) consome a mensagem → aplica regra de negócio → atualiza status → invalida cache Redis.
3. `GET /requests/{id}` → Redis (cache-aside) → MySQL (em caso de miss) → 200 ou 404.

### Componentes

| Componente | Papel |
|---|---|
| FastAPI | Adapter inbound HTTP |
| Kafka | Mensageria assíncrona |
| MySQL + SQLAlchemy | Persistência via repositório |
| Redis | Cache-aside + rate limiting |
| Consumer (`consumer.py`) | Adapter inbound Kafka (processo separado) |

## Regra de negócio

| Condição | Status final |
|---|---|
| `value <= 1000` | `APPROVED` |
| `value > 1000` | `MANUAL_REVIEW` |

## Decisões e trade-offs

### Consistência Kafka: at-least-once + idempotência = efeito exactly-once

O consumer usa `enable_auto_commit=False` e commita o offset manualmente **após** a persistência no MySQL. A sequência é: processar → persistir → commit de offset. Qualquer falha no meio recai num `continue` que pula o `consumer.commit()` — a mensagem será reenviada na reinicialização.

Se o processo morrer entre atualizar o MySQL e commitar o offset, a mensagem reprocessa. A guarda `status != PENDING` em `ProcessRequestUseCase` torna o reprocessamento um no-op seguro. Esse par — at-least-once no broker + transição idempotente no domínio — entrega efeito de exactly-once sem exactly-once delivery, que tem custo de latência e requer broker específico.

### Dual-write MySQL ↔ Kafka (por que o Outbox ficou como evolução)

Persistir no MySQL e publicar no Kafka são operações em sistemas distintos — não há transação distribuída cobrindo ambas. Se o processo morrer entre o commit MySQL e o produce Kafka, a solicitação fica `PENDING` indefinidamente.

**A solução correta é o padrão Transactional Outbox**: escrever o evento numa tabela `outbox` dentro da mesma transação do domínio; um relay lê e publica no Kafka de forma assíncrona. A atomicidade MySQL garante que estado e evento nunca ficam dessincronizados.

O Outbox está listado como evolução porque aumentaria significativamente a complexidade operacional (novo processo, nova tabela, nova migration). O impacto prático é baixo quando broker e aplicação estão no mesmo host e raramente caem no meio de um produce.
### Cache Redis: cache-aside + invalidação por deleção

- **Leitura**: Redis → miss → MySQL → popula `request:{id}` com TTL de 15 min.
- **Escrita** (consumer): **invalida** a chave (DELETE), não atualiza (write-through).

Invalidar por deleção é mais seguro que write-through porque elimina a janela de dado sujo em caso de falha parcial: se o DELETE falhar, o TTL eventualmente expira e o próximo GET sempre busca o MySQL. Write-through com falha a meio deixa Redis e MySQL inconsistentes sem mecanismo de correção automática.

### Rate limiting: por que existe apesar de não ser requisito

Foi adicionado porque: (1) o endpoint `POST /requests` é o único que cria estado persistente — um loop de chamadas poderia encher o banco; (2) Redis já estava no stack, custo de implementação é baixo.

A implementação usa `pipeline(transaction=True)` com `INCR + EXPIRE` em MULTI/EXEC: a alternativa ingênua (`INCR` seguido de `EXPIRE` condicional em dois comandos) tem race condition que torna o contador imortal sob concorrência. O pipeline elimina essa janela.

**Nota**: a janela resultante é deslizante (o TTL se renova a cada requisição), não fixa. Para janela fixa estrita seria necessário um script Lua atômico. A escolha atual é suficiente para proteção contra abuso e mais simples de operar.

### Retry no consumer: sem abstração de estratégia

O consumer tem retry linear com teto (`min(attempt, MAX_BACKOFF_SECONDS)`). Não foi criada uma classe `RetryStrategy` ou decorador genérico porque existe uma única implementação com parâmetros fixos — abstrair seria YAGNI. Se o backoff precisar mudar (ex.: exponencial, jitter), a mudança é uma linha. O teto de 30s mantém o sleep bem abaixo do `max.poll.interval.ms` padrão do Kafka (300s), evitando que o consumer seja removido do grupo por inatividade durante retries.

### Credenciais: sem defaults em config

`database_url` não tem default em `Settings` (pydantic-settings). Aplicação falha na inicialização com `ValidationError` claro se `DATABASE_URL` não estiver no ambiente. Defaults com credenciais hardcoded são o primeiro grep em revisão de segurança.

## Segurança em produção

Um ambiente de produção exigiria as seguintes camadas adicionais:

**Autenticação e autorização**
- JWT com curta expiração (15 min) + refresh token rotativo. FastAPI tem integração nativa via `OAuth2PasswordBearer` e `python-jose`.
- Cada solicitação deve estar vinculada ao `customer_id` do token — hoje o campo é livre na requisição, o que permite criar solicitações em nome de qualquer cliente. O use case deve receber o `customer_id` do token, não do payload.
- Escopos: leitura (`requests:read`) e criação (`requests:write`) separados, validados via `Security(get_current_user, scopes=[...])`.

**CORS**
- `CORSMiddleware` com `allow_origins` explícito (nunca `"*"` em produção). Lista de origens permitidas via variável de ambiente.

**Rate limiting por conta, não só por IP**
- O rate limit atual é por IP de origem — insuficiente: múltiplos usuários atrás do mesmo NAT compartilham limite, e um atacante com IPs rotativos o contorna trivialmente.
- Em produção: rate limit primário por `customer_id` (extraído do JWT), com Redis `INCR` na chave `rate:{customer_id}`. IP como limite secundário de último recurso.
- Limites distintos por operação: criação (escrita) mais restrita que consulta (leitura).

**HTTPS e segurança de transporte**
- TLS terminado no load balancer (nginx/ALB). A aplicação FastAPI roda HTTP internamente na VPC.
- Headers de segurança via middleware: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`. Biblioteca `secure` ou implementação direta.

**Secrets management**
- Credenciais não em `.env` — em AWS Secrets Manager, HashiCorp Vault, ou GCP Secret Manager. A aplicação busca no startup e rotaciona sem redeploy.
- Rotação automática de credenciais de banco a cada 30 dias.

**Proteção da mensageria**
- Kafka com autenticação SASL/SCRAM e TLS entre brokers e clientes.
- ACLs por tópico: o producer da API tem permissão apenas em `requests.created`; o consumer apenas em leitura desse tópico e escrita no DLQ.
- Schema Registry com Avro ou Protobuf: valida o contrato do payload no produce e no consume, evitando mensagens malformadas chegarem ao consumer.

**Auditoria**
- Todo `POST /requests` loga `customer_id`, IP de origem, `correlation_id` e timestamp em tabela de auditoria imutável (append-only, sem UPDATE/DELETE).
- Em contexto financeiro: rastreabilidade completa de quem criou o quê e quando é requisito regulatório.

## Observabilidade: correlation ID end-to-end

Todos os logs são emitidos em JSON. O `X-Correlation-Id` gerado na borda HTTP é propagado via `ContextVar` para o payload Kafka e lido pelo consumer — o mesmo ID atravessa toda a jornada de uma solicitação.

Exemplo de rastreamento completo via `grep`:

```json
// HTTP (app) — POST /requests
{"timestamp": "2025-01-01 12:00:00", "level": "INFO", "logger": "app.main", "message": "...", "correlation_id": "a1b2c3d4-..."}

// Payload Kafka — evento publicado
{"request_id": "uuid-da-solicitacao", "correlation_id": "a1b2c3d4-..."}

// Consumer — processamento
{"timestamp": "2025-01-01 12:00:01", "level": "INFO", "logger": "__main__", "message": "request_id=... processado com sucesso", "correlation_id": "a1b2c3d4-..."}
```

Para rastrear uma solicitação end-to-end:
```bash
grep "a1b2c3d4" /var/log/app.log  # mostra HTTP + consumer numa query só
```

O cliente pode fornecer o próprio `X-Correlation-Id` no header; se ausente, a aplicação gera um UUID. O ID é retornado no header `X-Correlation-Id` da resposta.

## Health checks

```
GET /health         → liveness (processo respondendo)
GET /health/ready   → readiness (MySQL + Redis acessíveis)
```

O serviço `app` no Docker Compose usa `/health/ready` como healthcheck, garantindo que o load balancer só direciona tráfego quando as dependências estão disponíveis.

## Como executar

**Pré-requisito**: Docker e Docker Compose instalados.

```bash
cp .env.example .env
docker compose up --build
```

O Kafka pode levar ~2 min para ficar healthy — é normal ver os serviços `app` e `consumer` reiniciando enquanto aguardam. Quando todos os serviços estiverem `Up`, a API está pronta.

API: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`

### Verificando que subiu

```bash
# Deve retornar {"status": "ready"} — confirma MySQL e Redis acessíveis
curl http://localhost:8000/health/ready
```

### Exemplos curl

```bash
# 1. Criar solicitação — retorna 201 com status PENDING
curl -X POST http://localhost:8000/requests \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: meu-trace-id-123" \
  -d '{"customer_id": "123", "value": 1500.00}'

# 2. Aguardar ~1s e consultar — consumer já terá processado (MANUAL_REVIEW)
curl http://localhost:8000/requests/<id-retornado-acima>
```

O consumer processa em background; a segunda chamada mostra o status final.

## Testes

Os testes **não precisam** de Docker/MySQL/Kafka/Redis — usam SQLite em memória e fakes. Requerem Python 3.10+.

```bash
pip install -r requirements.txt

# Todos os testes com coverage
python -m pytest

# Só unitários (domínio + use cases, sem infra)
python -m pytest -m unit

# Só integração (SQLite + fakes de Kafka/Redis)
python -m pytest -m integration

# Sem coverage (mais rápido em dev)
python -m pytest -p no:cov
```

Cobertura atual: **84%** — os caminhos críticos cobertos incluem:
- Retry → FAILED → DLQ no consumer
- Offset não commitado quando `_mark_failed` falha
- Idempotência: reprocessar solicitação já finalizada é no-op
- Cache-aside: miss → MySQL → populate; hit → Redis direto

## Estrutura

```
app/
├── domain/          # Entidades, enums, regra de negócio pura
├── application/     # Use cases + ports (Protocols)
└── infrastructure/
    ├── http/        # FastAPI router, schemas, rate limiter, middleware
    ├── persistence/ # SQLAlchemy models + repositório
    ├── messaging/   # Kafka producer
    ├── cache/       # Redis adapter + cache key factory
    └── logging.py   # JSON formatter + ContextVar do correlation_id
consumer.py          # Worker Kafka (processo separado)
migrations/          # Alembic
tests/
├── fakes.py         # FakeRepo, FakePublisher, FakeCache compartilhados
├── unit/            # Domínio + use cases (sem infra)
└── integration/     # Repositório (SQLite) + e2e HTTP + consumer flow
```
