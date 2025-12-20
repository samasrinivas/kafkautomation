
variable "confluent_api_key" {
  type      = string
  sensitive = true
}

variable "confluent_api_secret" {
  type      = string
  sensitive = true
}

variable "organization_id" {
  type = string
}

variable "environment_id" {
  type = string
}


variable "kafka_cluster_id" {
  type = string
}

variable "rest_endpoint" {
  type = string
}

variable "schema_registry_id" {
  type = string
}

variable "topics" {
  type = map(object({
    partitions          = number
    replication_factor  = number
    config              = map(string)
  }))
}

variable "schemas" {
  type = map(object({
    subject     = string
    schema_file = string
  }))
}

variable "acls" {
  type = map(object({
    role                = string
    crn_pattern         = string
    service_account_key = string
  }))
  default     = {}
  description = "ACLs generated from access_config entries. Parser creates one ACL per topic per access_config entry."
}

variable "service_accounts" {
  type = map(object({
    display_name = string
    description  = string
  }))
  default = {}
}

variable "github_repo_owner" {
  type        = string
  description = "GitHub repository owner for storing secrets"
  default     = ""
}

variable "github_repo_name" {
  type        = string
  description = "GitHub repository name for storing secrets"
  default     = ""
}

variable "github_token" {
  type        = string
  sensitive   = true
  description = "GitHub PAT with repo scope for creating secrets"
  default     = ""
}
