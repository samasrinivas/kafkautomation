Purpose
- Help contributors and AI agents quickly understand how this repo generates Terraform inputs for Confluent (Kafka) resources and where to find examples.

Big picture
- This repo converts a YAML "kafka request" (see OMNITRAC/kafka-request.yaml) into a JSON structure consumed by Terraform. The flow is:
1. Write a request YAML (topics, schemas, acls).
2. Run `scripts/parser.py` to produce a JSON object with top-level keys `topics`, `schemas`, and `acls`.
3. Provide that JSON to Terraform as variables (see `terraform/variables.tf`).

Key files (examples and patterns)
- `OMNITRAC/kafka-request.yaml` — canonical example request (topics, schemas, acls).
- `scripts/parser.py` — deterministic converter: `python scripts/parser.py <input-yaml> <output-json>`; output shape matches `variables.tf`.
- `terraform/variables.tf` — variable shapes expected by Terraform:
  - `topics`: map(object({ partitions, replication_factor, config }))
  - `schemas`: map(object({ subject, schema_file }))
  - `acls`: map(object({ principal, role, crn_pattern }))
- `terraform/main.tf` — resource patterns and important conventions:
  - `for_each` maps keyed by topic/subject/acl id (keys are meaningful names).
  - `confluent_kafka_topic` includes `lifecycle { prevent_destroy = true }` — do not remove topics lightly.
  - Schemas use `format = "AVRO"` and load schema content with `file(each.value.schema_file)`.
- `terraform/providers.tf` — provider and backend details:
  - Requires Terraform >= 1.3.0 and `confluentinc/confluent` provider (~> 2.55).
  - Remote state backend: S3 bucket `platform-engineering-terraform-state` and DynamoDB locks.
  - Sensitive credentials: `confluent_api_key` and `confluent_api_secret` are variables (do not commit secrets).
- `terraform/s3_bucket_full_access_policy.json` — example AWS policy used for the backend.

Concrete commands and examples
- Convert a request YAML to JSON:
  - `python scripts/parser.py OMNITRAC/kafka-request.yaml request.json`
  - Output `request.json` will contain `{"topics": {...}, "schemas": {...}, "acls": {...}}`.
- Use the generated JSON with Terraform:
  - Create a tfvars JSON file that matches variable names, e.g. `env.auto.tfvars.json`:
    {
      "topics": { ... },
      "schemas": { ... },
      "acls": { ... }
    }
  - Initialize and apply Terraform as usual:
    - `terraform init`
    - `terraform plan -var-file="env.auto.tfvars.json"`
    - `terraform apply -var-file="env.auto.tfvars.json"`

Project-specific conventions
- Topic keys: The parser keys `tf['topics'][t['name']]` by topic name — Terraform resources iterate `for_each = var.topics` using the topic name as the key.
- ACL keys: parser generates keys like `acl_0`, `acl_1` — Terraform iterates `for_each = var.acls` so resource names are stable per JSON ordering.
- Prevent destroy: `prevent_destroy = true` on topics means plan/apply changes must handle topic deletion explicitly.
- Schema files: `schema_file` paths in the YAML are relative paths that Terraform reads with `file()`; ensure schema files are present in repo or referenced correctly.

Integration points and infra notes
- Confluent Cloud: resources are created via the Confluent provider — you need API credentials with adequate permissions.
- Remote state: S3 + DynamoDB are used for Terraform state/locks; the `s3_bucket_full_access_policy.json` shows required S3 permissions.

What to watch for when authoring changes
- Keep the parser's output shape in sync with `variables.tf` — tests and Terraform will break if the JSON shape diverges.
- Do not commit API keys or tfvars with secrets; prefer environment variables or a secure secret backend.
- When changing topic lifecycle semantics (remove `prevent_destroy`), discuss with platform owners first.

If something is unclear
- Ask for an example of how you intend to run Terraform (CI vs local). Provide the YAML you plan to convert and the intended target environment.

Feedback
- I drafted these instructions from the repository layout and examples (see `OMNITRAC/kafka-request.yaml`, `scripts/parser.py`, and `terraform/*.tf`). Tell me which areas need more detail or concrete examples to be added.
