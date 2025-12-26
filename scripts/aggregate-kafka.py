#!/usr/bin/env python3
"""
Aggregate per-domain kafka-request.yaml files into a single catalog.

Merges all kafka-request.yaml files from domains/<domain>/<env>/ into a unified
kafka-catalog.yaml for visibility and cross-domain validation.

Usage:
    python aggregate-kafka.py --env <environment> --output-dir <output-dir>

Example:
    python aggregate-kafka.py --env dev --output-dir catalogs
    # Produces: catalogs/dev/kafka-catalog.yaml
"""

import os
import sys
import yaml
import argparse
from pathlib import Path

def aggregate_kafka_resources(environment, output_dir):
    """
    Aggregate kafka-request.yaml files from all domains for a given environment.
    
    Args:
        environment: Environment name (dev, test, qa, prod)
        output_dir: Output directory for aggregated catalog
    
    Returns:
        aggregated_data: Dict with all topics, schemas, and access_config
    """
    domains_dir = Path("domains")
    
    if not domains_dir.exists():
        print(f"Error: domains/ directory not found")
        sys.exit(1)
    
    # Collect all kafka-request.yaml files
    kafka_files = list(domains_dir.glob(f"*/{environment}/kafka-request.yaml"))
    
    if not kafka_files:
        print(f"Warning: No kafka-request.yaml files found in domains/*/{environment}/")
        # Still create empty catalog structure
        aggregated = {
            "topics": [],
            "schemas": [],
            "access_config": [],
            "domains": []
        }
    else:
        aggregated = {
            "topics": [],
            "schemas": [],
            "access_config": [],
            "domains": []
        }
        
        for kafka_file in sorted(kafka_files):
            domain_name = kafka_file.parent.parent.name
            print(f"Processing domain: {domain_name} ({kafka_file})")
            
            try:
                with open(kafka_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                # Track domain
                aggregated["domains"].append(domain_name)
                
                # Aggregate topics with domain prefix for clarity
                for topic in data.get("topics", []):
                    topic_with_metadata = {
                        **topic,
                        "_domain": domain_name
                    }
                    aggregated["topics"].append(topic_with_metadata)
                
                # Aggregate schemas with domain tracking
                for schema in data.get("schemas", []):
                    schema_with_metadata = {
                        **schema,
                        "_domain": domain_name
                    }
                    aggregated["schemas"].append(schema_with_metadata)
                
                # Aggregate access_config with domain tracking
                for access in data.get("access_config", []):
                    access_with_metadata = {
                        **access,
                        "_domain": domain_name
                    }
                    aggregated["access_config"].append(access_with_metadata)
            
            except yaml.YAMLError as e:
                print(f"Error parsing {kafka_file}: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"Error processing {kafka_file}: {e}")
                sys.exit(1)
    
    # Create output directory
    env_output_dir = Path(output_dir) / environment
    env_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write aggregated catalog
    catalog_file = env_output_dir / "kafka-catalog.yaml"
    try:
        with open(catalog_file, 'w') as f:
            yaml.dump(aggregated, f, default_flow_style=False, sort_keys=False)
        print(f"✓ Aggregated catalog written to: {catalog_file}")
    except Exception as e:
        print(f"Error writing catalog to {catalog_file}: {e}")
        sys.exit(1)
    
    return aggregated

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate per-domain kafka-request.yaml files into a unified catalog"
    )
    parser.add_argument("--env", required=True, help="Environment name (dev, test, qa, prod)")
    parser.add_argument("--output-dir", default="catalogs", help="Output directory for aggregated catalog")
    
    args = parser.parse_args()
    
    aggregate_kafka_resources(args.env, args.output_dir)

if __name__ == "__main__":
    main()
