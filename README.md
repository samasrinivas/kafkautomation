# Kafka Self-Service Automation Platform

## Purpose

This repo automates Confluent Kafka resource provisioning through Git, providing developers with a self-service workflow for creating topics, schemas, and ACLs across dev/test/qa/prod environments.

## Big Picture

**How it works:**
1. Create a feature branch named after your project.
2. Create project folders under `projects/<PROJECT>/<ENV>/` (dev/test/qa/prod).
3. Copy the generic template `templates/kafka-request.yaml` into your project folder.
4. Schemas are optional. If needed, add Avro files under `schemas/<ENV>/` and reference them in `kafka-request.yaml`; otherwise, leave the `schemas:` section commented.
5. CI runs on PR: lints YAML, converts to Terraform variables, auto-detects the environment from the file path, initializes Terraform with the per-environment backend key, and posts the plan as a PR comment.
6. On merge to `main`, CD applies the plan with environment-specific settings. If schemas were omitted, no schema resources are created.
7. Confluent resources are provisioned in the correct environment with isolated Terraform state (S3 key per environment).

**YAML → Terraform flow:**
- Author `projects/<PROJECT>/<ENV>/kafka-request.yaml` using the template; do not add Confluent environment metadata in YAML.
- Store any schema files under `schemas/<ENV>/...` and reference them via `schema_file` paths; leave the `schemas:` section commented if not needed.
- `scripts/parser.py` converts YAML to JSON and validates schema file existence.
- Workflows detect environment from path and set Terraform backend `key` per environment.
- Terraform plans/applies using the generated variables to create topics, schemas, and ACLs.

## Directory Structure

```
kafkautomation/
├── templates/
│   ├── kafka-request.yaml        # Single generic template to copy
│   └── s3_bucket_full_access_policy.json
│
├── schemas/                      # Environment-specific schemas (optional)
│   ├── dev/
│   │   └── <SCHEMA-FILE>.avsc             # Add your schemas here
│   ├── test/
│   │   └── <SCHEMA-FILE>.avsc
│   ├── qa/
│   │   └── <SCHEMA-FILE>.avsc
│   └── prod/
│       └── <SCHEMA-FILE>.avsc
│
├── projects/                     # Developer projects (created by developers)
│   ├── <PROJECT>/
│   │   ├── dev/
│   │   │   ├── kafka-request.yaml
│   │   ├── test/
│   │   │   ├── kafka-request.yaml
│   │   ├── qa/
│   │   │   ├── kafka-request.yaml
│   │   └── prod/
│   │   │   ├── kafka-request.yaml
│   └── <ANOTHER_PROJECT>/
│
├── terraform/
│   ├── main.tf                  # Confluent resources (topics, schemas, acls)
│   ├── providers.tf             # Backend (S3 state isolation by env)
│   └── variables.tf             # Input variable shapes
│
├── scripts/
│   └── parser.py                # Converts YAML → JSON for Terraform
│
└── .github/workflows/
    ├── kafka-plan.yml           # Plan on PR (environment auto-detected)
    └── kafka-apply.yml          # Apply on merge to main (auto-approved)
```

### Note on s3_bucket_full_access_policy
- Purpose: example IAM policy for Terraform state backend access reviews.
- Location: `terraform/policies/s3_bucket_full_access_policy.json`.
- Usage: documentation/reference only; not automatically consumed by Terraform.

## Setup: GitHub Secrets

Before the first workflow run, set up API credentials in GitHub repo settings → Secrets and variables → Actions:

### 1. Control-Plane Credentials (Per-environment)

Create one **Cloud API key** per environment (owned by a service account like `kafka-terraform_runner` with `EnvironmentAdmin` role):

- `CONFLUENT_API_KEY_DEV` — Cloud API key for dev environment
- `CONFLUENT_API_SECRET_DEV` — Corresponding secret
- `CONFLUENT_API_KEY_TEST` — Cloud API key for test environment
- `CONFLUENT_API_SECRET_TEST` — Corresponding secret
- `CONFLUENT_API_KEY_QA` — Cloud API key for QA environment
- `CONFLUENT_API_SECRET_QA` — Corresponding secret
- `CONFLUENT_API_KEY_PROD` — Cloud API key for prod environment
- `CONFLUENT_API_SECRET_PROD` — Corresponding secret

**Used for:** Service account creation, role bindings, schema registry operations.

### 2. Data-Plane Credentials (Per-environment)

Create one **Kafka cluster–scoped** API key per environment (owned by a service account like `kafka-terraform_runner`):

- `KAFKA_API_KEY_DEV` — Kafka cluster API key for dev cluster (lkc-oj0vro)
- `KAFKA_API_SECRET_DEV` — Corresponding secret
- `KAFKA_API_KEY_TEST` — Kafka cluster API key for test cluster
- `KAFKA_API_SECRET_TEST` — Corresponding secret
- `KAFKA_API_KEY_QA` — Kafka cluster API key for QA cluster
- `KAFKA_API_SECRET_QA` — Corresponding secret
- `KAFKA_API_KEY_PROD` — Kafka cluster API key for prod cluster
- `KAFKA_API_SECRET_PROD` — Corresponding secret

**Used for:** Topic creation, data-plane operations.

### 3. AWS Credentials (S3 backend for Terraform state)
- `AWS_ACCESS_KEY_ID` — AWS account access key
- `AWS_SECRET_ACCESS_KEY` — AWS account secret key

### 4. GitHub Token (Auto-stored in workflows)
- `GITHUB_TOKEN` — Auto-provided by GitHub Actions (no manual setup needed); used for PR comments and secret storage.

## Setup Checklist

Before using the workflows, ensure the following are set up. The CI/CD pipelines validate these and will fail early if any are missing.

- GitHub Environments: Create `dev`, `test`, `qa`, `prod` environments.
- Environment Variables (per environment): `ORGANIZATION_ID`, `ENVIRONMENT_ID`, `KAFKA_CLUSTER_ID`, `REST_ENDPOINT`, `SCHEMA_REGISTRY_ID`.
- Environment Secrets (per environment): `CONFLUENT_API_KEY`, `CONFLUENT_API_SECRET`, `KAFKA_API_KEY`, `KAFKA_API_SECRET`.
- Repository Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- Repository Variables: `AWS_REGION` (e.g., `us-east-1`), `TF_BUCKET_STATE` (e.g., `platform-engineering-terraform-state`).

Workflows include validation steps for AWS settings (secrets and variables) and will exit with a helpful message if they’re not configured.

## Developer Workflow

### Step 1: Create a Feature Branch
```bash
git checkout -b my-service-kafka-setup
```

### Step 2: Create Project Folder Structure
```bash
mkdir -p projects/my-service/dev
mkdir -p projects/my-service/test
mkdir -p projects/my-service/qa
mkdir -p projects/my-service/prod
```

### Step 3: Copy Templates
```bash
# Copy template to your project (repeat for each env)
cp templates/kafka-request.yaml projects/my-service/dev/
cp templates/kafka-request.yaml projects/my-service/test/
cp templates/kafka-request.yaml projects/my-service/qa/
cp templates/kafka-request.yaml projects/my-service/prod/
```

### Step 4a: If You Don't Need a Schema (Minimal)

Edit `projects/my-service/dev/kafka-request.yaml`:
- Keep `service_name` as your service name
- Customize `topics` and `access_config` for your needs
- **The `schemas:` section is COMMENTED OUT by default** — leave it commented (Terraform will skip schema creation)

Example (most services):
```yaml
service_name: "my-service"
# ... Confluent Cloud details (do NOT change) ...
topics:
  - name: "my-service-events"
    partitions: 3
    replication_factor: 3

# SCHEMAS (OPTIONAL)
# If your service needs a schema:
# 1. Create an Avro schema file under schemas/dev/
# 2. Uncomment and customize the block below
# If you don't need a schema, leave this section commented.
#
# schemas:
#   - subject: "my-service-events-value"
#     schema_file: "schemas/dev/my-service-schema.avsc"
```

### Step 4b: If You Need a Schema (Optional)

1. Create your Avro schema:
   ```bash
   cat > schemas/dev/my-service-schema.avsc << 'EOF'
   {
     "type": "record",
     "name": "MyServiceEvent",
     "namespace": "com.myorg.myservice",
     "fields": [
       { "name": "id", "type": "string" },
       { "name": "timestamp", "type": { "type": "long", "logicalType": "timestamp-millis" } }
     ]
   }
   EOF
   ```

2. Reference it in your `kafka-request.yaml`:
   ```yaml
   schemas:
     - subject: "my-service-events-value"
       schema_file: "schemas/dev/my-service-schema.avsc"
   ```

3. Repeat for test, qa, prod in their respective `schemas/<ENV>/` folders.

### Step 4c: If You Need Service Accounts & ACLs (Optional)

Define service accounts with their permissions in one unified section. Each entry creates one service account + one ACL per topic.

```yaml
topics:
  - name: "payment-processed"
    partitions: 6
    replication_factor: 3
  - name: "payment-events"
    partitions: 3
    replication_factor: 3

access_config:
  - name: "payment-producer"
    description: "Producer for payment events"
    role: "DeveloperWrite"
    topics:
      - "payment-processed"
      - "payment-events"
  - name: "payment-consumer"
    description: "Consumer for payment events"
    role: "DeveloperRead"
    topics:
      - "payment-processed"
```

Terraform will automatically:
- Create service accounts from each `access_config` entry
- Generate Kafka API keys and store in GitHub secrets
- Build ACL principals from service account IDs (e.g., `User:sa-abc123def456`)
- Build crn_patterns for each topic referenced
- Apply all ACLs to the Kafka cluster

**Result:** 2 service accounts + 3 ACLs (1 producer with 2 topic permissions, 1 consumer with 1 topic permission)

API keys are stored in GitHub secrets as:
- `CONFLUENT_<SERVICE_ACCOUNT_NAME>_API_KEY` (e.g., `CONFLUENT_PAYMENT_PRODUCER_API_KEY`)
- `CONFLUENT_<SERVICE_ACCOUNT_NAME>_API_SECRET` (e.g., `CONFLUENT_PAYMENT_PRODUCER_API_SECRET`)

### Step 5: Commit and Create PR
```bash
git add projects/
git add schemas/dev/my-service-schema.avsc  # (if you created one)
git commit -m "Add Kafka config for my-service"
git push -u origin my-service-kafka-setup
```

### Step 6: CI Runs Automatically
- GitHub Actions detects `projects/<PROJECT>/<ENV>/kafka-request.yaml` or `schemas/**` changes
- CI validates YAML, lints it, generates tfvars, and runs `terraform plan`
- Plan appears as PR comment for review

### Step 7: Merge to Main
- Merge PR to main
- CD workflow runs automatically
- Terraform applies changes to the corresponding environment
- Kafka topics, schemas, and ACLs are created in Confluent Cloud
- **If service accounts were defined:** API keys are automatically generated and stored in GitHub secrets with names like `CONFLUENT_<NAME>_API_KEY` and `CONFLUENT_<NAME>_API_SECRET`

## Important Notes

### ⚠️ Parser Uses Environment Variables Only
- The parser reads Confluent metadata exclusively from GitHub Environment variables, not from YAML.
- Required environment variables (set per GitHub Environment): `ORGANIZATION_ID`, `ENVIRONMENT_ID`, `KAFKA_CLUSTER_ID`, `REST_ENDPOINT`, `SCHEMA_REGISTRY_ID`.
- YAML fields for these values are ignored.

### ✅ You CAN Change These
- `service_name` — Use your service name
- `topics[].name`, `topics[].partitions`, `topics[].replication_factor`
- `topics[].config` — Retention, compression, etc.
- `access_config[].name`, `access_config[].role`, `access_config[].topics` — Your service account permissions

### Terraform Plan vs Apply
- **CI (PR):** Shows `terraform plan` (read-only preview)
- **CD (main):** Runs `terraform apply -auto-approve` (actual infrastructure changes)

### Environment Isolation
- State key pattern: `s3://$TF_BUCKET_STATE/terraform/<PROJECT>/<ENV>/data-streaming-platform.tfstate`
- Example (project `payments`, env `dev`): `s3://$TF_BUCKET_STATE/terraform/payments/dev/data-streaming-platform.tfstate`

Each project+environment pair has its own isolated Terraform state file (no cross-project or cross-environment interference).

### Multiple Environments in One Commit?
Each PR/commit should touch **one environment** (one `projects/<PROJECT>/<ENV>/kafka-request.yaml`). If you need to update multiple environments, create separate PRs per environment to maintain clean audit trails and allow environment-specific reviews.

## Key Files and Their Purpose

- `templates/kafka-request.yaml` — Single template to copy; env/cluster IDs come from GitHub Environment variables
- `schemas/*/` — Store all Avro schemas here (environment-specific). Do not place schema files under `projects/`.
- `projects/<PROJECT>/<ENV>/kafka-request.yaml` — Your actual config (becomes source of truth)
- `scripts/parser.py` — Converts YAML to JSON for Terraform (runs automatically in CI/CD)
- `terraform/main.tf` — Defines Confluent resources (for each topic, schema, ACL)
- `terraform/providers.tf` — Backend config (S3 state, environment-isolated keys)
- `.github/workflows/kafka-plan.yml` — Plan workflow (PR validation; detects project/env from path; backend key per project+env)
- `.github/workflows/kafka-apply.yml` — Apply workflow (main merge automation; backend key per project+env)

## Technical Details

### Parser (`scripts/parser.py`)
- **Purpose:** Deterministic converter from `kafka-request.yaml` to JSON for Terraform
- **Command:** `python scripts/parser.py <input-yaml> <output-json>`
- **Key feature:** Unified `access_config` structure creates N service accounts + M ACLs
  - Each `access_config` entry generates: 1 service account + (1 ACL per topic listed)
  - Example: 2 entries with 3 topics total = 2 service accounts + 3 ACLs
- **Auto-generation:** 
  - `principals` built from service account IDs (resolved by Terraform)
  - `crn_patterns` auto-generated from topic names
- **Validation:** Ensures all referenced topics exist in the YAML

### Terraform Setup
- **Requirements:** Terraform >= 1.3.0 and `confluentinc/confluent` provider (~> 2.55)
- **Key patterns:**
  - Resources use `for_each` maps keyed by topic/subject/acl/service-account id
  - Topics include `lifecycle { prevent_destroy = true }` — do not remove topics without discussion
  - Schemas use `format = "AVRO"` and load content with `file(each.value.schema_file)`
  - Service accounts auto-generate API keys and store credentials in GitHub secrets
- **Remote state:** S3 backend configured via workflow `-backend-config` using `TF_BUCKET_STATE` and `AWS_REGION`; keys are scoped per `<PROJECT>/<ENV>`

### Secrets and Variables (GitHub Actions)
- Environment-scoped secrets (per env: dev/test/qa/prod): `CONFLUENT_API_KEY`, `CONFLUENT_API_SECRET`, `KAFKA_API_KEY`, `KAFKA_API_SECRET`
- Repository-level secrets (current): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Repository-level variables:
  - `AWS_REGION` (example: `us-east-1`)
  - `TF_BUCKET_STATE` (example: `platform-engineering-terraform-state`)
- Workflows detect `PROJECT` and `ENV` from `projects/<PROJECT>/<ENV>/kafka-request.yaml` and set backend key to `terraform/<PROJECT>/<ENV>/data-streaming-platform.tfstate`

Environment-scoped variables (set per GitHub Environment: dev/test/qa/prod):
- `ORGANIZATION_ID`
- `ENVIRONMENT_ID`
- `KAFKA_CLUSTER_ID`
- `REST_ENDPOINT`
- `SCHEMA_REGISTRY_ID`

These are mandatory for parser execution and must be defined in the GitHub Environment. Do not include these in YAML; the parser validates they are set and will error if any are missing.

### Service Account & API Key Provisioning
- **Terraform creates:**
  - `confluent_service_account` resources from YAML definitions
  - `confluent_api_key` for each service account (Kafka cluster access)
  - Automatically stores API keys in GitHub secrets via `null_resource` + GitHub CLI
- **Secret naming convention:** `CONFLUENT_<SERVICE_ACCOUNT_NAME>_API_KEY` and `CONFLUENT_<SERVICE_ACCOUNT_NAME>_API_SECRET`
- **Output:** Terraform outputs service account IDs and corresponding GitHub secret names for reference
- **Example:** Service account name `payment-producer` → secrets `CONFLUENT_PAYMENT_PRODUCER_API_KEY` and `CONFLUENT_PAYMENT_PRODUCER_API_SECRET`

### Unified Access Configuration Workflow
- **Single section:** `access_config` replaces separate `service_accounts` and `acls`
- **Developer intent:** "This service account needs this role on these topics"
- **One-to-many relationship:** 1 entry → 1 service account + N ACLs (one per topic)
- **Auto-generation:** Principals and crn_patterns generated from service account IDs and topic names
- **Flexibility:** Multiple topics per service account, multiple roles possible by creating multiple entries
- **Example:** 2 service accounts × 3 topics = 2 service accounts + 3 ACLs automatically created

### GitHub Actions Workflows
- **CI (`kafka-plan.yml`):** Runs on PR for any `**/kafka-request.yaml` or `schemas/**` changes
  - Validates YAML with `yamllint`
  - Detects environment from path (e.g., `<PROJECT>/dev/` → `dev`)
  - Generates tfvars and runs `terraform plan`
  - Posts plan as PR comment
- **CD (`kafka-apply.yml`):** Runs on main merge
  - Applies Terraform with `terraform apply -auto-approve`
  - Uploads artifact with environment name

## Troubleshooting

**PR comment shows "missing required fields":**
- Check that `environment_id`, `kafka_cluster_id`, `rest_endpoint`, `schema_registry_id` are present (they are auto-filled from templates)
- Check YAML formatting (indentation, quotes)

**Schema file not found error:**
- Verify the schema file path in `kafka-request.yaml` matches where you created it
- Ensure it's under `schemas/<ENV>/` with the correct name

**Terraform plan shows no changes:**
- Check if resources already exist in Confluent Cloud for that environment
- Verify ACL principals and roles are correct

**Want to add/remove topics without changing schema:**
- Edit `topics:` section in your kafka-request.yaml
- Leave `schemas:` unchanged or remove it entirely
- Commit and push

**Service account API keys not showing in GitHub secrets:**
- Ensure `GITHUB_TOKEN` has write permissions to secrets (it does by default in GitHub Actions)
- Check GitHub Actions workflow logs for errors during `terraform apply`
- Verify service account names are valid (alphanumeric, hyphens)
- Secrets are stored as `CONFLUENT_<UPPER_NAME>_API_KEY` and `CONFLUENT_<UPPER_NAME>_API_SECRET`

**How to use generated service account credentials:**
- After CD completes, check GitHub repository Settings → Secrets and variables → Actions
- Find your service account secrets (e.g., `CONFLUENT_PAYMENT_PRODUCER_API_KEY`)
- Reference in your workflows with `${{ secrets.CONFLUENT_PAYMENT_PRODUCER_API_KEY }}`

## Questions?

Contact the platform team. Environment-specific cluster details are locked; request changes through the platform team if needed.