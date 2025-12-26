#!/usr/bin/env python3
"""
Aggregate per-domain schema files into a single catalog.

Collects all .avsc schema files from domains/<domain>/<env>/schemas/ into a unified
schemas-catalog.json for visibility and cross-domain validation.

Usage:
    python aggregate-schemas.py --env <environment> --output-dir <output-dir>

Example:
    python aggregate-schemas.py --env dev --output-dir catalogs
    # Produces: catalogs/dev/schemas-catalog.json
"""

import os
import sys
import json
import argparse
from pathlib import Path

def aggregate_schemas(environment, output_dir):
    """
    Aggregate schema files from all domains for a given environment.
    
    Args:
        environment: Environment name (dev, test, qa, prod)
        output_dir: Output directory for aggregated catalog
    
    Returns:
        schemas_data: List of schema metadata
    """
    domains_dir = Path("domains")
    
    if not domains_dir.exists():
        print(f"Error: domains/ directory not found")
        sys.exit(1)
    
    schemas_catalog = {
        "schemas": [],
        "timestamp": None,
        "environment": environment
    }
    
    # Collect all schema files
    schema_files = list(domains_dir.glob(f"*/{environment}/schemas/*.avsc"))
    
    if schema_files:
        print(f"Found {len(schema_files)} schema files for {environment}")
    else:
        print(f"No schema files found in domains/*/{environment}/schemas/")
    
    for schema_file in sorted(schema_files):
        domain_name = schema_file.parent.parent.parent.name
        subject_name = schema_file.stem  # filename without .avsc extension
        
        print(f"Processing schema: {subject_name} from domain {domain_name}")
        
        try:
            with open(schema_file, 'r') as f:
                schema_content = f.read()
                # Validate it's valid JSON
                json.loads(schema_content)
            
            schemas_catalog["schemas"].append({
                "subject": subject_name,
                "domain": domain_name,
                "file_path": str(schema_file.relative_to(Path.cwd())),
                "file_name": schema_file.name
            })
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {schema_file}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error processing {schema_file}: {e}")
            sys.exit(1)
    
    # Create output directory
    env_output_dir = Path(output_dir) / environment
    env_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write schemas catalog
    catalog_file = env_output_dir / "schemas-catalog.json"
    try:
        with open(catalog_file, 'w') as f:
            json.dump(schemas_catalog, f, indent=2)
        print(f"✓ Schemas catalog written to: {catalog_file}")
    except Exception as e:
        print(f"Error writing schemas catalog to {catalog_file}: {e}")
        sys.exit(1)
    
    return schemas_catalog

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate per-domain schema files into a unified catalog"
    )
    parser.add_argument("--env", required=True, help="Environment name (dev, test, qa, prod)")
    parser.add_argument("--output-dir", default="catalogs", help="Output directory for aggregated catalog")
    
    args = parser.parse_args()
    
    aggregate_schemas(args.env, args.output_dir)

if __name__ == "__main__":
    main()
