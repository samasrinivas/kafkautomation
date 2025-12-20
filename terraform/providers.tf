terraform {
  required_version = ">= 1.3.0"
  required_providers {
    confluent = {
      source  = "confluentinc/confluent"
      version = "~> 2.55"
    }
  }
  backend "s3" {
    bucket         = "platform-engineering-terraform-state"
    region         = "us-east-1"
    use_lockfile  = true
    encrypt        = true
  }
}

provider "confluent" {
  cloud_api_key    = var.confluent_api_key
  cloud_api_secret = var.confluent_api_secret
  kafka_api_key    = var.kafka_api_key
  kafka_api_secret = var.kafka_api_secret
}
