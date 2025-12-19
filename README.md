# Kafka Self-Service Automation Platform

## Purpose

This repo automates Confluent Kafka resource provisioning through Git, providing developers with a self-service workflow for creating topics, schemas, and ACLs across dev/test/qa/prod environments.

## Big Picture

**How it works:**
1. Developer creates a feature branch named after their project
2. Developer copies environment-specific `kafka-request.yaml` from `templates/<ENV>/`
3. Developer creates a project folder under `projects/<PROJECT_NAME>/<ENV>/`
4. Developer adds their YAML config and optional Avro schemas
5. CI workflow validates and generates Terraform variables
6. CD workflow applies Terraform on main merge
7. Resources are created in Confluent Cloud (environment-isolated)

**YAML → Terraform flow:**
- Write a `kafka-request.yaml` file (topics, schemas, acls, etc.)
- Run `scripts/parser.py` to produce JSON consumed by Terraform
- Terraform applies resources using `terraform/main.tf`

## Directory Structure

```
kafkautomation/
├── templates/                    # Environment templates (reference only)
│   ├── dev/
│   │   └── kafka-request.yaml   # DEV template - copy this
│   ├── test/
│   │   └── kafka-request.yaml   # TEST template - copy this
│   ├── qa/
│   │   └── kafka-request.yaml   # QA template - copy this
│   └── prod/
│       └── kafka-request.yaml   # PROD template - copy this
│
├── schemas/                      # Environment-specific schemas (optional)
│   ├── dev/
│   │   └── .gitkeep             # Add your schemas here
│   ├── test/
│   │   └── .gitkeep
│   ├── qa/
│   │   └── .gitkeep
│   └── prod/
│       └── .gitkeep
│
├── projects/                     # Developer projects (created by developers)
│   ├── <PROJECT_NAME>/
│   │   ├── dev/
│   │   │   ├── kafka-request.yaml
│   │   │   └── (optional) custom-schema.avsc reference
│   │   ├── test/
│   │   ├── qa/
│   │   └── prod/
│   └── <ANOTHER_PROJECT>/
│
├── terraform/
│   ├── main.tf                  # Confluent resources (topics, schemas, acls)
│   ├── providers.tf             # Backend (S3 state isolation by env)
│   ├── variables.tf             # Input variable shapes
│   └── s3_bucket_full_access_policy.json
│
├── scripts/
│   └── parser.py                # Converts YAML → JSON for Terraform
│
└── .github/workflows/
    ├── ci.yml                   # Plan on PR (environment auto-detected)
    └── cd.yml                   # Apply on merge to main (auto-approved)
```

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
- **Remote state:** S3 bucket `platform-engineering-terraform-state` with DynamoDB locks; environment-isolated keys

### GitHub Actions Workflows
- **CI (`ci.yml`):** Runs on PR for any `**/kafka-request.yaml` changes
  - Validates YAML with `yamllint`
  - Detects environment from path (e.g., `templates/dev/` → `dev`)
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