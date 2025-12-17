variable "confluent_api_key" { type = string, sensitive = true }
variable "confluent_api_secret" { type = string, sensitive = true }
variable "environment_id"     { type = string }
variable "kafka_cluster_id"   { type = string }
variable "rest_endpoint"      { type = string }
variable "schema_registry_id" { type = string }

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
    principal   = string
    role        = string
    crn_pattern = string
  }))
}
