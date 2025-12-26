
# Kafka Self-Service Automation Platform

Domain-based GitOps for Confluent Kafka: domains declare topics, schemas, service accounts, and ACLs in YAML; CI aggregates and validates; CD applies with serialization and cross-domain conflict prevention.

---

## Developer Workflow (domains)

### Step 1: Create a domain branch
```bash
git checkout -b my-domain  # Feature branch named after your domain (e.g., payment-service)
```

### Step 2: Create domain folder structure
```bash
mkdir -p domains/my-domain/dev/schemas
mkdir -p domains/my-domain/test/schemas
mkdir -p domains/my-domain/qa/schemas
mkdir -p domains/my-domain/prod/schemas
```

### Step 3: Copy template and customize for target environment
```bash
cp templates/kafka-request.yaml domains/my-domain/dev/kafka-request.yaml
```

Edit `domains/my-domain/dev/kafka-request.yaml`:
```yaml
service_name: my-domain
description: Domain-owned resources

topics:
  - name: my-events
    partitions: 3
    replication_factor: 3
    config:
      retention.ms: 604800000

schemas:
  - subject: my-events-value
    schema_file: domains/my-domain/dev/schemas/my-events.avsc

access_config:
  - name: my-domain-api           # Use domain prefix
    description: API producer
    role: DeveloperRead
    topics: [my-events]
```

### Step 4: (Optional) Add schema files
```bash
cat > domains/my-domain/dev/schemas/my-events.avsc << 'EOF'
{
  "type": "record",
  "name": "MyEvents",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "timestamp", "type": "long"}
  ]
}
EOF
```

### Step 5: Commit and push
```bash
git add domains/
git commit -m "feat: add kafka config for my-domain (dev)"
git push -u origin feature/my-domain-dev
```

### Step 6: Open PR to target branch
Open PR via GitHub UI: `feature/my-domain-dev` → `features`

### Step 7: Review plan
CI automatically:
- Lints YAML
- Checks environment lock (fails if locked)
- Aggregates all domains' configs for the env
- Validates for cross-domain conflicts
- Posts terraform plan to PR for review

### Step 8: Merge to target branch
After review and approvals:
```bash
git merge --no-ff feature/my-domain-dev
git push origin features
```

### Step 9: CD deploys automatically
CD automatically:
- Acquires lock for the environment
- Re-aggregates and re-validates
- Runs terraform apply
- Creates topics, schemas, service accounts, API keys, ACLs
- Stores API keys as environment-scoped GitHub secrets
- Commits catalogs and releases lock

### Step 10: Delete domain branch
After successful deployment:
```bash
git branch -d my-domain           # Delete local branch
git push origin --delete my-domain # Delete remote branch
```

### Best Practices
- **One environment per PR**: Each PR should touch only one environment (dev/test/qa/prod)
- **Naming conventions**: Prefix resources with domain name (e.g., `my-domain-producer`, `my-domain-events`)
- **Lock handling**: Only one environment deploys at a time; wait if locked
- **Schema paths**: Must be under `domains/<domain>/<env>/schemas/`

---

## How It Works (technical overview)

1) **Author intent**: Each domain owns `domains/<domain>/<env>/kafka-request.yaml` (+ optional `schemas/`).
2) **PR → CI (`kafka-plan.yml`)**
   - Lint YAML; check environment lock (`catalogs/<env>/.lock`).
   - Aggregate all domain files → `catalogs/<env>/kafka-catalog.yaml` + `schemas-catalog.json` (temp).
   - Validate conflicts vs deployed catalogs on base branch: duplicate topics, schema subjects, service account names.
   - Parse aggregated catalog → `terraform/terraform.tfvars.json` (env vars only).
   - Terraform init/validate/plan; post plan to PR.
3) **Merge → CD (`kafka-apply.yml`)**
   - Acquire lock (`catalogs/<env>/.lock`, committed to target branch).
   - Re-aggregate, re-validate conflicts against target branch, parse.
   - Terraform plan & apply (topics with prevent_destroy, schemas, service accounts, API keys, ACLs).
   - Store API keys as environment-scoped GitHub secrets.
   - Commit updated catalogs (`catalogs/<env>/kafka-catalog.yaml`, `schemas-catalog.json`) and release lock to target branch.
4) **State isolation**: `s3://$TF_BUCKET_STATE/terraform/<domain>/<env>/data-streaming-platform.tfstate`.

---

## Repository Layout

```
domains/
  <domain>/<env>/kafka-request.yaml       # Domain's kafka config (topics, schemas, ACLs)
  <domain>/<env>/schemas/*.avsc           # Domain's Avro schema files

catalogs/                                 # Aggregated, committed snapshots per env
  dev|test|qa|prod/
    kafka-catalog.yaml                    # Generated from all domains (per env)
    schemas-catalog.json                  # Generated schema metadata (per env)
    .lock                                 # Deployment lock (per env)

scripts/
  aggregate-kafka.py                      # Merge domain YAML → kafka-catalog.yaml
  aggregate-schemas.py                    # Collect schemas → schemas-catalog.json
  validate-conflicts.py                   # Cross-domain duplicate detection
  parser.py                               # Aggregated catalog → tfvars.json

.github/workflows/
  kafka-plan.yml                          # CI workflow (PR validation)
  kafka-apply.yml                         # CD workflow (apply on merge)

terraform/
  main.tf                                 # Confluent Kafka, Schema Registry, ACL resources
  providers.tf                            # Confluent provider + S3 backend config
  variables.tf                            # Input variables (topics, schemas, service_accounts, acls)

templates/kafka-request.yaml              # Template for domain teams to copy
README.md (this file)
```

**Terraform files detail:**
- `main.tf`: Creates topics with `prevent_destroy`, schemas, service accounts, API keys, ACLs; stores secrets in GitHub via provisioner.
- `providers.tf`: Configures Confluent provider and S3 backend for state (key per domain+env: `terraform/<domain>/<env>/...`).
- `variables.tf`: Defines input shapes for aggregated catalog (topics, schemas, acls, service_accounts) + GitHub/AWS variables.

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
- Validate conflicts vs deployed catalogs on base branch.
- Parse aggregated catalog → `terraform/terraform.tfvars.json`.
- Terraform init/validate/plan; post plan to PR.

### CD – `kafka-apply.yml` (on merge to target branch)
- Acquire env lock (`catalogs/<env>/.lock`, committed to target branch).
- Aggregate + validate conflicts against target branch (fresh).
- Parse → tfvars; terraform plan/apply.
- On success: commit updated catalogs, delete lock, push to target branch.
- On failure: delete lock, push to target branch (so others can proceed).

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

- **Env locked:** Wait for current deployment; lock is auto-released on finish. If stuck, manually remove `.lock` file in `catalogs/<env>/` from the target branch and push.
- **Conflict detected:** Rename with domain prefix or coordinate with owning domain; validator shows offending names/domains.
- **Missing vars/secrets:** Workflows print which env secret/var is missing; add to GitHub Environment or repo secrets/vars.
- **Schema file not found:** Ensure path includes domain/env (`domains/<domain>/<env>/schemas/...`).
- **Unexpected deletes in plan:** Stop; check state key and definitions; topics are protected with `prevent_destroy`.

---

## Quick Validation Plan

1) Create test domain `domains/test-team/dev/` with one topic + SA.
2) Open PR → ensure CI passes (aggregation, conflict check, plan posted).
3) Merge to target branch → ensure CD acquires lock, applies, updates catalogs, releases lock.
4) Try second PR during deploy → CI should fail on lock; re-run after lock release.
5) Test conflict: two domains define same topic → CI should fail with clear message.

---

## Developer Workflow (domains)

1) Create a branch.
2) Create domain folders: `domains/<domain>/dev|test|qa|prod/` (include `schemas/` if needed).
3) Copy `templates/kafka-request.yaml` into the target env folder; edit topics, schemas (optional), access_config.
4) Add `.avsc` files under `domains/<domain>/<env>/schemas/` and reference via `schema_file`.
5) Open a PR touching one environment; CI will lint, aggregate, validate conflicts, and plan.
6) Merge to target branch; CD will acquire the env lock, apply, update catalogs, and release the lock.

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
