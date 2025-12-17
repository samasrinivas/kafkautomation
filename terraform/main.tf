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
  principal   = each.value.principal
  role_name   = each.value.role
  crn_pattern = each.value.crn_pattern
}
