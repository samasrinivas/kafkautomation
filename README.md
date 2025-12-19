# Kafka Self-Service Automation Platform

## Purpose

This repo automates Confluent Kafka resource provisioning through Git, providing developers with a self-service workflow for creating topics, schemas, and ACLs across dev/test/qa/prod environments.

## Big Picture

**How it works:**
1. Create a feature branch named after your project.
2. Create project folders under `projects/<PROJECT>/<ENV>/` (dev/test/qa/prod).
3. Copy the environment template `templates/<ENV>/kafka-request.yaml` into your project folder.
4. Schemas are optional. If needed, add Avro files under `schemas/<ENV>/` and reference them in `kafka-request.yaml`; otherwise, leave the `schemas:` section commented.
5. CI runs on PR: lints YAML, converts to Terraform variables, auto-detects the environment from the file path, initializes Terraform with the per-environment backend key, and posts the plan as a PR comment.
6. On merge to `main`, CD applies the plan with environment-specific settings. If schemas were omitted, no schema resources are created.
7. Confluent resources are provisioned in the correct environment with isolated Terraform state (S3 key per environment).

**YAML → Terraform flow:**
- Author `projects/<PROJECT>/<ENV>/kafka-request.yaml` using the matching template; keep environment values unchanged.
- Store any schema files under `schemas/<ENV>/...` and reference them via `schema_file` paths; leave the `schemas:` section commented if not needed.
- `scripts/parser.py` converts YAML to JSON and validates schema file existence.
- Workflows detect environment from path and set Terraform backend `key` per environment.
- Terraform plans/applies using the generated variables to create topics, schemas, and ACLs.

## Directory Structure

```
kafkautomation/
├── templates/                    # Environment templates (reference only)
│   ├── dev/
│   │   ├── kafka-request.yaml   # DEV template - copy this
│   │   └── s3_bucket_full_access_policy.json
│   ├── test/
│   │   ├── kafka-request.yaml   # TEST template - copy this
│   │   └── s3_bucket_full_access_policy.json
│   ├── qa/
│   │   ├── kafka-request.yaml   # QA template - copy this
│   │   └── s3_bucket_full_access_policy.json
│   └── prod/
│       ├── kafka-request.yaml   # PROD template - copy this
│       └── s3_bucket_full_access_policy.json
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
    ├── ci.yml                   # Plan on PR (environment auto-detected)
    └── cd.yml                   # Apply on merge to main (auto-approved)
```

### Note on s3_bucket_full_access_policy policy files
- Purpose: environment-ready example IAM policy for Terraform state backend access reviews.
- Location: `templates/<ENV>/s3_bucket_full_access_policy.json` per environment.
- Usage: documentation/reference only; not automatically consumed by Terraform.

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
# Copy dev template to your project
cp templates/dev/kafka-request.yaml projects/my-service/dev/

# Repeat for test, qa, prod
cp templates/test/kafka-request.yaml projects/my-service/test/
cp templates/qa/kafka-request.yaml projects/my-service/qa/
cp templates/prod/kafka-request.yaml projects/my-service/prod/
```

### Step 4a: If You Don't Need a Schema (Minimal)

Edit `projects/my-service/dev/kafka-request.yaml`:
- Keep `service_name` as your service name
- Customize `topics` and `acls` for your needs
- **The `schemas:` section is COMMENTED OUT by default** — leave it commented (Terraform will skip schema creation)

Example (most services):
```yaml
service_name: "my-service"
# ... Confluent Cloud details (do NOT change) ...
topics:
  - name: "my-service-events"
    partitions: 3
    replication_factor: 3
acls:
  - principal: "User:sa-my-service"
    role: "DeveloperWrite"
    # ... (do NOT change crn_pattern) ...

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

### Step 5: Commit and Create PR
```bash
git add projects/
git add schemas/dev/my-service-schema.avsc  # (if you created one)
git commit -m "Add Kafka config for my-service"
git push -u origin my-service-kafka-setup
```

### Step 6: CI Runs Automatically
- GitHub Actions detects `projects/<PROJECT>/<ENV>/kafka-request.yaml`
- CI validates YAML, lints it, generates tfvars, and runs `terraform plan`
- Plan appears as PR comment for review

### Step 7: Merge to Main
- Merge PR to main
- CD workflow runs automatically
- Terraform applies changes to the corresponding environment
- Kafka topics, schemas, and ACLs are created in Confluent Cloud

## Important Notes

### ⚠️ Do NOT Change These Values
- `environment_id`, `kafka_cluster_id`, `rest_endpoint`, `schema_registry_id` — These are environment-specific and locked
- `crn_pattern` in ACLs — Contains environment/cluster/org details; do not modify

### ✅ You CAN Change These
- `service_name` — Use your service name
- `topics[].name`, `topics[].partitions`, `topics[].replication_factor`
- `topics[].config` — Retention, compression, etc.
- `acls[].principal`, `acls[].role` — Your service account and desired permissions
- `schemas` — Remove, add, or reference your custom schemas

### Terraform Plan vs Apply
- **CI (PR):** Shows `terraform plan` (read-only preview)
- **CD (main):** Runs `terraform apply -auto-approve` (actual infrastructure changes)

### Environment Isolation
- Dev state: `s3://platform-engineering-terraform-state/terraform/dev/...`
- Test state: `s3://platform-engineering-terraform-state/terraform/test/...`
- QA state: `s3://platform-engineering-terraform-state/terraform/qa/...`
- Prod state: `s3://platform-engineering-terraform-state/terraform/prod/...`

Each environment has its own isolated Terraform state file (no cross-environment interference).

### Multiple Environments in One Commit?
Each PR/commit should touch **one environment** (one `projects/<PROJECT>/<ENV>/kafka-request.yaml`). If you need to update multiple environments, create separate PRs per environment to maintain clean audit trails and allow environment-specific reviews.

## Key Files and Their Purpose

- `templates/*/kafka-request.yaml` — Copy these to start your project
- `schemas/*/` — Store your Avro schemas here (environment-specific)
- `schemas/*/` — Store all Avro schemas here (environment-specific). Do not place schema files under `projects/`.
- `projects/<PROJECT>/<ENV>/kafka-request.yaml` — Your actual config (becomes source of truth)
- `scripts/parser.py` — Converts YAML to JSON for Terraform (runs automatically in CI/CD)
- `terraform/main.tf` — Defines Confluent resources (for each topic, schema, ACL)
- `terraform/providers.tf` — Backend config (S3 state, environment-isolated keys)
- `.github/workflows/ci.yml` — Plan workflow (PR validation)
- `.github/workflows/cd.yml` — Apply workflow (main merge automation)

## Technical Details

### Parser (`scripts/parser.py`)
- **Purpose:** Deterministic converter from `kafka-request.yaml` to JSON for Terraform
- **Command:** `python scripts/parser.py <input-yaml> <output-json>`
- **Output shape:**
  ```json
  {
    "environment_id": "...",
    "kafka_cluster_id": "...",
    "rest_endpoint": "...",
    "schema_registry_id": "...",
    "topics": { "topic-name": { "partitions": 3, "replication_factor": 3, "config": {} } },
    "schemas": { "subject": { "subject": "...", "schema_file": "..." } },
    "acls": { "acl_0": { "principal": "...", "role": "...", "crn_pattern": "..." } }
  }
  ```
- **Validation:** Checks that all required Confluent fields are present; validates schema file existence before output

### Terraform Setup
- **Requirements:** Terraform >= 1.3.0 and `confluentinc/confluent` provider (~> 2.55)
- **Key patterns:**
  - Resources use `for_each` maps keyed by topic/subject/acl id
  - Topics include `lifecycle { prevent_destroy = true }` — do not remove topics without discussion
  - Schemas use `format = "AVRO"` and load content with `file(each.value.schema_file)`
- **Remote state:** S3 bucket `platform-engineering-terraform-state` with local lockfiles (`use_lockfile = true`); environment-isolated keys

### GitHub Actions Workflows
- **CI (`ci.yml`):** Runs on PR for any `**/kafka-request.yaml` changes
  - Validates YAML with `yamllint`
  - Detects environment from path (e.g., `<PROJECT>/dev/` → `dev`)
  - Generates tfvars and runs `terraform plan`
  - Posts plan as PR comment
- **CD (`cd.yml`):** Runs on main merge
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

## Questions?

Contact the platform team. Environment-specific cluster details are locked; request changes through the platform team if needed.