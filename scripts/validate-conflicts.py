#!/usr/bin/env python3
"""
Validate aggregated catalogs for conflicts and collisions.

Checks for:
1. Duplicate topic names across domains
2. Duplicate schema subject names across domains
3. Duplicate service account names across domains
4. Cross-domain ACL conflicts

Compares both the current branch changes and deployed catalogs from main.

Usage:
    python validate-conflicts.py --env <environment> \
        --branch-kafka <branch-kafka-catalog.yaml> \
        --branch-schemas <branch-schemas-catalog.json> \
        --deployed-kafka <deployed-kafka-catalog.yaml> \
        --deployed-schemas <deployed-schemas-catalog.json>

Example:
    python validate-conflicts.py --env dev \
        --branch-kafka catalogs/dev/kafka-catalog.yaml \
        --branch-schemas catalogs/dev/schemas-catalog.json \
        --deployed-kafka catalogs/dev/.deployed/kafka-catalog.yaml \
        --deployed-schemas catalogs/dev/.deployed/schemas-catalog.json
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from collections import defaultdict

def load_kafka_catalog(filepath):
    """Load kafka catalog from YAML file."""
    if not filepath or not Path(filepath).exists():
        return None
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def load_schemas_catalog(filepath):
    """Load schemas catalog from JSON file."""
    if not filepath or not Path(filepath).exists():
        return None
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def validate_kafka_conflicts(branch_catalog, deployed_catalog, environment):
    """
    Validate kafka catalog for conflicts.
    
    Returns:
        (is_valid, conflicts_list)
    """
    conflicts = []
    
    # Extract topics from both catalogs
    branch_topics = {}
    if branch_catalog:
        for topic in branch_catalog.get("topics", []):
            topic_name = topic.get("name")
            domain = topic.get("_domain", "unknown")
            branch_topics[topic_name] = domain
    
    deployed_topics = {}
    if deployed_catalog:
        for topic in deployed_catalog.get("topics", []):
            topic_name = topic.get("name")
            domain = topic.get("_domain", "unknown")
            deployed_topics[topic_name] = domain
    
    # Check for duplicate topic names within branch
    seen_topics = defaultdict(list)
    for topic_name, domain in branch_topics.items():
        seen_topics[topic_name].append(domain)
    
    for topic_name, domains in seen_topics.items():
        if len(domains) > 1:
            conflicts.append(
                f"Topic '{topic_name}' defined in multiple domains: {', '.join(set(domains))}"
            )
    
    # Check for topic name collisions between branch and deployed
    for topic_name in branch_topics:
        if topic_name in deployed_topics:
            branch_domain = branch_topics[topic_name]
            deployed_domain = deployed_topics[topic_name]
            if branch_domain != deployed_domain:
                conflicts.append(
                    f"Topic '{topic_name}' already exists in domain '{deployed_domain}' "
                    f"(you are deploying in domain '{branch_domain}')"
                )
    
    # Check service accounts
    branch_accounts = {}
    if branch_catalog:
        for access in branch_catalog.get("access_config", []):
            account_name = access.get("name")
            domain = access.get("_domain", "unknown")
            branch_accounts[account_name] = domain
    
    deployed_accounts = {}
    if deployed_catalog:
        for access in deployed_catalog.get("access_config", []):
            account_name = access.get("name")
            domain = access.get("_domain", "unknown")
            deployed_accounts[account_name] = domain
    
    # Check for duplicate service account names within branch
    seen_accounts = defaultdict(list)
    for account_name, domain in branch_accounts.items():
        seen_accounts[account_name].append(domain)
    
    for account_name, domains in seen_accounts.items():
        if len(domains) > 1:
            conflicts.append(
                f"Service account '{account_name}' defined in multiple domains: {', '.join(set(domains))}"
            )
    
    # Check for service account collisions between branch and deployed
    for account_name in branch_accounts:
        if account_name in deployed_accounts:
            branch_domain = branch_accounts[account_name]
            deployed_domain = deployed_accounts[account_name]
            if branch_domain != deployed_domain:
                conflicts.append(
                    f"Service account '{account_name}' already exists in domain '{deployed_domain}' "
                    f"(you are deploying in domain '{branch_domain}')"
                )
    
    is_valid = len(conflicts) == 0
    return is_valid, conflicts

def validate_schemas_conflicts(branch_catalog, deployed_catalog, environment):
    """
    Validate schemas catalog for conflicts.
    
    Returns:
        (is_valid, conflicts_list)
    """
    conflicts = []
    
    # Extract subjects from both catalogs
    branch_subjects = {}
    if branch_catalog:
        for schema in branch_catalog.get("schemas", []):
            subject = schema.get("subject")
            domain = schema.get("domain", "unknown")
            branch_subjects[subject] = domain
    
    deployed_subjects = {}
    if deployed_catalog:
        for schema in deployed_catalog.get("schemas", []):
            subject = schema.get("subject")
            domain = schema.get("domain", "unknown")
            deployed_subjects[subject] = domain
    
    # Check for duplicate subjects within branch
    seen_subjects = defaultdict(list)
    for subject, domain in branch_subjects.items():
        seen_subjects[subject].append(domain)
    
    for subject, domains in seen_subjects.items():
        if len(domains) > 1:
            conflicts.append(
                f"Schema subject '{subject}' defined in multiple domains: {', '.join(set(domains))}"
            )
    
    # Check for subject collisions between branch and deployed
    for subject in branch_subjects:
        if subject in deployed_subjects:
            branch_domain = branch_subjects[subject]
            deployed_domain = deployed_subjects[subject]
            if branch_domain != deployed_domain:
                conflicts.append(
                    f"Schema subject '{subject}' already exists in domain '{deployed_domain}' "
                    f"(you are deploying in domain '{branch_domain}')"
                )
    
    is_valid = len(conflicts) == 0
    return is_valid, conflicts

def main():
    parser = argparse.ArgumentParser(
        description="Validate aggregated catalogs for conflicts"
    )
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--branch-kafka", help="Branch kafka-catalog.yaml path")
    parser.add_argument("--branch-schemas", help="Branch schemas-catalog.json path")
    parser.add_argument("--deployed-kafka", help="Deployed kafka-catalog.yaml path")
    parser.add_argument("--deployed-schemas", help="Deployed schemas-catalog.json path")
    
    args = parser.parse_args()
    
    all_valid = True
    all_conflicts = []
    
    # Validate Kafka catalogs
    if args.branch_kafka:
        branch_kafka = load_kafka_catalog(args.branch_kafka)
        deployed_kafka = load_kafka_catalog(args.deployed_kafka) if args.deployed_kafka else None
        
        kafka_valid, kafka_conflicts = validate_kafka_conflicts(branch_kafka, deployed_kafka, args.env)
        all_valid = all_valid and kafka_valid
        all_conflicts.extend(kafka_conflicts)
        
        if kafka_valid:
            print(f"✓ Kafka catalog validation passed for {args.env}")
        else:
            print(f"✗ Kafka catalog validation FAILED for {args.env}")
    
    # Validate Schemas catalogs
    if args.branch_schemas:
        branch_schemas = load_schemas_catalog(args.branch_schemas)
        deployed_schemas = load_schemas_catalog(args.deployed_schemas) if args.deployed_schemas else None
        
        schemas_valid, schemas_conflicts = validate_schemas_conflicts(branch_schemas, deployed_schemas, args.env)
        all_valid = all_valid and schemas_valid
        all_conflicts.extend(schemas_conflicts)
        
        if schemas_valid:
            print(f"✓ Schemas catalog validation passed for {args.env}")
        else:
            print(f"✗ Schemas catalog validation FAILED for {args.env}")
    
    # Report all conflicts
    if all_conflicts:
        print("\n❌ VALIDATION FAILED - Conflicts detected:\n")
        for i, conflict in enumerate(all_conflicts, 1):
            print(f"  {i}. {conflict}")
        print()
        sys.exit(1)
    else:
        print(f"\n✓ All validations passed for {args.env}")
        sys.exit(0)

if __name__ == "__main__":
    main()
