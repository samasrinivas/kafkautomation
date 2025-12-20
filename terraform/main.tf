resource "confluent_kafka_topic" "topics" {
  for_each = var.topics
  kafka_cluster { id = var.kafka_cluster_id }
  rest_endpoint = var.rest_endpoint
  topic_name = each.key
  partitions_count = each.value.partitions
  config = each.value.config
  lifecycle { prevent_destroy = true }
}

resource "confluent_schema" "schemas" {
  for_each = var.schemas
  subject_name = each.value.subject
  format = "AVRO"
  schema = file(each.value.schema_file)
  schema_registry_cluster { id = var.schema_registry_id }
}

resource "confluent_role_binding" "acls" {
  for_each    = var.acls
  
  # Resolve principal: either use provided principal or look up service account ID
  principal   = contains(keys(each.value), "service_account_key") ? "User:${confluent_service_account.service_accounts[each.value.service_account_key].id}" : each.value.principal
  role_name   = each.value.role
  crn_pattern = each.value.crn_pattern
}

# Create service accounts
resource "confluent_service_account" "service_accounts" {
  for_each     = var.service_accounts
  display_name = each.value.display_name
  description  = each.value.description
}

# Create Kafka API keys for each service account
resource "confluent_api_key" "kafka_api_keys" {
  for_each     = var.service_accounts
  display_name = "${each.value.display_name}-kafka-key"
  description  = "Kafka API Key for ${each.value.display_name}"
  
  owner {
    id          = confluent_service_account.service_accounts[each.key].id
    api_version = confluent_service_account.service_accounts[each.key].api_version
    kind        = confluent_service_account.service_accounts[each.key].kind
  }
  
  managed_resource {
    id          = var.kafka_cluster_id
    api_version = "cmk/v2"
    kind        = "Cluster"
    
    environment {
      id = var.environment_id
    }
  }
}

# Store API keys in GitHub secrets using GitHub CLI
resource "null_resource" "store_github_secrets" {
  for_each = var.service_accounts

  triggers = {
    api_key_id = confluent_api_key.kafka_api_keys[each.key].id
  }

  provisioner "local-exec" {
    command = <<-EOT
      if [ -n "${var.github_token}" ] && [ -n "${var.github_repo_owner}" ] && [ -n "${var.github_repo_name}" ]; then
        echo "Storing secrets for ${each.value.display_name}..."
        
        # Store API Key
        echo "${confluent_api_key.kafka_api_keys[each.key].id}" | gh secret set "CONFLUENT_${upper(replace(each.key, "-", "_"))}_API_KEY" \
          --repo "${var.github_repo_owner}/${var.github_repo_name}" \
          --app actions
        
        # Store API Secret
        echo "${confluent_api_key.kafka_api_keys[each.key].secret}" | gh secret set "CONFLUENT_${upper(replace(each.key, "-", "_"))}_API_SECRET" \
          --repo "${var.github_repo_owner}/${var.github_repo_name}" \
          --app actions
        
        echo "✓ Stored secrets: CONFLUENT_${upper(replace(each.key, "-", "_"))}_API_KEY and CONFLUENT_${upper(replace(each.key, "-", "_"))}_API_SECRET"
      else
        echo "⚠️  GitHub credentials not provided, skipping secret storage for ${each.value.display_name}"
      fi
    EOT
    
    environment = {
      GH_TOKEN = var.github_token
    }
  }
}

# Output service account details
output "service_accounts" {
  value = {
    for key, sa in confluent_service_account.service_accounts : key => {
      id           = sa.id
      display_name = sa.display_name
      api_key      = confluent_api_key.kafka_api_keys[key].id
      # Secret is sensitive, will only be in state
      github_secret_key    = "CONFLUENT_${upper(replace(key, "-", "_"))}_API_KEY"
      github_secret_secret = "CONFLUENT_${upper(replace(key, "-", "_"))}_API_SECRET"
    }
  }
  description = "Service account details and GitHub secret names"
}
