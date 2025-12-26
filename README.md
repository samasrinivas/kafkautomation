
# Kafka Self-Service Automation Platform

Domain-based GitOps for Confluent Kafka: domains declare topics, schemas, service accounts, and ACLs in YAML; CI aggregates and validates; CD applies with serialization and cross-domain conflict prevention.

---

## How It Works (end-to-end)

1) **Author intent**: Each domain owns `domains/<domain>/<env>/kafka-request.yaml` (+ optional `schemas/`).
2) **PR → CI (`kafka-plan.yml`)**
   - Lint YAML; check environment lock (`catalogs/<env>/.lock`).
   - Aggregate all domain files → `catalogs/<env>/kafka-catalog.yaml` + `schemas-catalog.json` (temp).
   - Validate conflicts vs deployed catalogs (main): duplicate topics, schema subjects, service account names.
   - Parse aggregated catalog → `terraform/terraform.tfvars.json` (env vars only).
   - Terraform init/validate/plan; post plan to PR.
3) **Merge → CD (`kafka-apply.yml`)**
   - Acquire lock (`catalogs/<env>/.lock`, committed to main).
   - Re-aggregate, re-validate conflicts, parse.
   - Terraform plan & apply (topics with prevent_destroy, schemas, service accounts, API keys, ACLs).
   - Store API keys as environment-scoped GitHub secrets.
   - Commit updated catalogs (`catalogs/<env>/kafka-catalog.yaml`, `schemas-catalog.json`) and release lock.
4) **State isolation**: `s3://$TF_BUCKET_STATE/terraform/<domain>/<env>/data-streaming-platform.tfstate`.

---

## Repository Layout

```
domains/
  <domain>/<env>/kafka-request.yaml
  <domain>/<env>/schemas/*.avsc

catalogs/                  # Aggregated, committed snapshots per env
  dev|test|qa|prod/
    kafka-catalog.yaml     # Generated from all domains (per env)
    schemas-catalog.json   # Generated schema metadata (per env)
    .lock                  # Deployment lock (per env)

scripts/
  aggregate-kafka.py       # Merge domain YAML → kafka-catalog.yaml
  aggregate-schemas.py     # Collect schemas → schemas-catalog.json
  validate-conflicts.py    # Cross-domain duplicate detection
  parser.py                # Aggregated catalog → tfvars.json

.github/workflows/
  kafka-plan.yml           # CI (PR)
  kafka-apply.yml          # CD (main)

terraform/                # Confluent resources and provider config
templates/kafka-request.yaml
README.md (this file)
```

---

## Getting Started (domain teams)

1) **Scaffold**
```bash
mkdir -p domains/my-team/dev/schemas
mkdir -p domains/my-team/test/schemas
mkdir -p domains/my-team/qa/schemas
mkdir -p domains/my-team/prod/schemas
cp templates/kafka-request.yaml domains/my-team/dev/
```

2) **Edit** `domains/my-team/dev/kafka-request.yaml`
```yaml
service_name: my-team
description: Domain-owned resources

topics:
  - name: my-events
    partitions: 3
    replication_factor: 3
    config:
      retention.ms: 604800000

schemas:
  - subject: my-events-value
    schema_file: domains/my-team/dev/schemas/my-events.avsc

access_config:
  - name: my-team-api           # Use domain prefix
    description: API producer
    role: DeveloperRead
    topics: [my-events]
```

3) **(Optional) Add schema** `domains/my-team/dev/schemas/my-events.avsc`
```json
{
  "type": "record",
  "name": "MyEvents",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "timestamp", "type": "long"}
  ]
}
```

4) **Open PR** (feature branch) → CI runs plan and conflict checks.

5) **Merge to main** → CD applies and updates catalogs; lock auto-released.

---

## Required GitHub Configuration

**Repository Secrets (shared):**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

**Repository Variables (shared):**
- `AWS_REGION`
- `TF_BUCKET_STATE`

**Environment Variables (per env: dev/test/qa/prod):**
- `ORGANIZATION_ID`, `ENVIRONMENT_ID`, `KAFKA_CLUSTER_ID`, `REST_ENDPOINT`, `SCHEMA_REGISTRY_ID`

**Environment Secrets (per env):**
- `CONFLUENT_API_KEY`, `CONFLUENT_API_SECRET`
- `KAFKA_API_KEY`, `KAFKA_API_SECRET`
- Optional Schema Registry: `SCHEMA_REGISTRY_API_KEY`, `SCHEMA_REGISTRY_API_SECRET`, `SCHEMA_REGISTRY_REST_ENDPOINT`

Workflows will fail fast with clear messages if any are missing.

---

## CI/CD Workflows (summary)

### CI – `kafka-plan.yml` (PR)
- Detect env from path `domains/<domain>/<env>/...`.
- Fail if `catalogs/<env>/.lock` exists.
- Lint all domain `kafka-request.yaml` files for that env.
- Aggregate → `catalogs/<env>/kafka-catalog.yaml` (temp) + `schemas-catalog.json`.
- Validate conflicts vs deployed catalogs from main.
- Parse aggregated catalog → `terraform/terraform.tfvars.json`.
- Terraform init/validate/plan; post plan to PR.

### CD – `kafka-apply.yml` (main)
- Acquire env lock (`catalogs/<env>/.lock`, committed).
- Aggregate + validate conflicts (fresh).
- Parse → tfvars; terraform plan/apply.
- On success: commit updated catalogs, delete lock, push.
- On failure: delete lock, push (so others can proceed).

---

## Aggregation & Conflict Detection

- `aggregate-kafka.py`: merges all domain YAMLs for an env; tags entries with `_domain`.
- `aggregate-schemas.py`: collects all `.avsc` files; records domain and path.
- `validate-conflicts.py`: fails if duplicate topic names, schema subjects, or service account names across domains (branch vs deployed catalogs).

---

## Lock Mechanism (per env)

- Lock file: `catalogs/<env>/.lock` (committed).
- CI: if lock exists → fail PR with message; no plan runs.
- CD: creates lock before apply; removes on success or failure.
- Prevents concurrent deployments to same environment; manual removal only if stuck.

---

## Parser (`scripts/parser.py`)

- Input: aggregated `catalogs/<env>/kafka-catalog.yaml`.
- Output: `terraform/terraform.tfvars.json`.
- Strictly uses environment variables (no YAML metadata for org/env/cluster endpoints).
- Validates schema paths, topic references, required env vars.

Required env vars (must be set in GitHub Environment):
- `ORGANIZATION_ID`, `ENVIRONMENT_ID`, `KAFKA_CLUSTER_ID`, `REST_ENDPOINT`
- If schemas present: `SCHEMA_REGISTRY_ID`, `SCHEMA_REGISTRY_API_KEY`, `SCHEMA_REGISTRY_API_SECRET`, `SCHEMA_REGISTRY_REST_ENDPOINT`

---

## Terraform Highlights

- State per domain+env: `terraform/<domain>/<env>/...` (S3 backend via `TF_BUCKET_STATE`).
- Topics use `prevent_destroy` lifecycle to avoid accidental deletes.
- Service accounts + Kafka API keys created; secrets stored as environment-scoped GitHub secrets via provisioner.
- ACLs generated from `access_config` (one SA, multiple topics → multiple ACLs).

Secret naming (env-scoped):
- `CONFLUENT_<SA>_API_KEY`, `CONFLUENT_<SA>_API_SECRET` (uppercased, hyphens → underscores).

---

## Naming Conventions

- Service accounts: prefix with domain (`payment-api`, `order-processor`).
- Topics/Schemas: prefer domain-prefixed names to avoid collisions (`payment-events`).

---

## Catalogs (committed snapshots)

- Location: `catalogs/<env>/kafka-catalog.yaml` and `schemas-catalog.json`.
- Updated only after successful CD apply.
- Enable auditability and cross-domain visibility.

---

## Migration Notes (old → new)

- Old structure `projects/<project>/<env>/` is replaced by `domains/<domain>/<env>/`.
- If old folders exist, migrate or delete; new workflows watch `domains/**` paths.
- Terraform state keys remain per domain; old state can coexist until cleaned.

---

## Troubleshooting

- **Env locked:** Wait for current deployment; lock is auto-released on finish. If stuck, remove `.lock` in `catalogs/<env>/` on main.
- **Conflict detected:** Rename with domain prefix or coordinate with owning domain; validator shows offending names/domains.
- **Missing vars/secrets:** Workflows print which env secret/var is missing; add to GitHub Environment or repo secrets/vars.
- **Schema file not found:** Ensure path includes domain/env (`domains/<domain>/<env>/schemas/...`).
- **Unexpected deletes in plan:** Stop; check state key and definitions; topics are protected with `prevent_destroy`.

---

## Quick Validation Plan

1) Create test domain `domains/test-team/dev/` with one topic + SA.
2) Open PR → ensure CI passes (aggregation, conflict check, plan posted).
3) Merge → ensure CD acquires lock, applies, updates catalogs, releases lock.
4) Try second PR during deploy → CI should fail on lock; re-run after lock release.
5) Test conflict: two domains define same topic → CI should fail with clear message.

---

## Developer Workflow (domains)

1) Create a branch.
2) Create domain folders: `domains/<domain>/dev|test|qa|prod/` (include `schemas/` if needed).
3) Copy `templates/kafka-request.yaml` into the target env folder; edit topics, schemas (optional), access_config.
4) Add `.avsc` files under `domains/<domain>/<env>/schemas/` and reference via `schema_file`.
5) Open a PR touching one environment; CI will lint, aggregate, validate conflicts, and plan.
6) Merge to main; CD will acquire the env lock, apply, update catalogs, and release the lock.

## Technical Details

- Parser command: `python scripts/parser.py catalogs/<env>/kafka-catalog.yaml terraform/terraform.tfvars.json` (invoked by workflows). Uses only environment variables for Confluent metadata.
- Terraform state key: `s3://$TF_BUCKET_STATE/terraform/<domain>/<env>/data-streaming-platform.tfstate`.
- Topics use `prevent_destroy`; avoid destructive changes without coordination.
- `access_config` entries → 1 service account + 1 ACL per referenced topic; API keys stored as environment-scoped secrets: `CONFLUENT_<UPPER_NAME>_API_KEY` / `_API_SECRET`.
- CI/CD detects environment from the path `domains/<domain>/<env>/...`; lock file prevents concurrent applies per environment.

## Secrets & Variables (GitHub)

- Repo secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- Repo vars: `AWS_REGION`, `TF_BUCKET_STATE`.
- Environment vars (per env): `ORGANIZATION_ID`, `ENVIRONMENT_ID`, `KAFKA_CLUSTER_ID`, `REST_ENDPOINT`, `SCHEMA_REGISTRY_ID` (required when schemas are used).
- Environment secrets (per env): `CONFLUENT_API_KEY`, `CONFLUENT_API_SECRET`, `KAFKA_API_KEY`, `KAFKA_API_SECRET`; optional schema registry keys if needed.

## Signals to Watch

- CI fails fast if lock exists, env vars/secrets are missing, or conflicts detected (duplicate topic/subject/service account).
- CD always cleans up the lock (success or failure) and commits updated catalogs on success.

## Status

Domain-based workflows are the source of truth; legacy `projects/` and separate docs have been removed.
