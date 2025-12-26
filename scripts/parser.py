import yaml, json, sys, os
from pathlib import Path

if len(sys.argv) != 3:
    print('Usage: parser.py <input-yaml> <output-json>')
    print('       where input-yaml can be a domain-specific file or aggregated catalog')
    sys.exit(1)

input_file = sys.argv[1]
with open(input_file, 'r') as f:
    data = yaml.safe_load(f)

"""
Resolve required Confluent Cloud metadata strictly from environment variables.
The parser no longer reads these values from YAML; they must be provided via
environment variables in the workflow/job environment.
"""

# Required environment variables
required_env_vars = [
    'ORGANIZATION_ID',
    'ENVIRONMENT_ID',
    'KAFKA_CLUSTER_ID',
    'REST_ENDPOINT'
]

missing_envs = [var for var in required_env_vars if not os.getenv(var)]
if missing_envs:
    print(f"Error: Missing required environment variables: {', '.join(missing_envs)}")
    sys.exit(1)

# Extract required Confluent Cloud variables from environment only
tf = {
    "organization_id": os.getenv('ORGANIZATION_ID'),
    "environment_id": os.getenv('ENVIRONMENT_ID'),
    "kafka_cluster_id": os.getenv('KAFKA_CLUSTER_ID'),
    "rest_endpoint": os.getenv('REST_ENDPOINT'),
    "topics": {},
    "schemas": {},
    "acls": {},
    "service_accounts": {}
}

for t in data.get('topics', []):
    tf['topics'][t['name']] = {
        'partitions': t.get('partitions', 3),
        'replication_factor': t.get('replication_factor', 3),
        'config': t.get('config', {})
    }

for s in data.get('schemas', []):
    schema_file = s.get('schema_file') or s.get('file_path')
    if not schema_file:
        print(f'Error: Schema entry missing schema_file or file_path: {s}')
        sys.exit(1)
    # Handle both relative paths and aggregated catalog entries
    if schema_file and not os.path.exists(schema_file):
        print(f'Warning: Schema file not found: {schema_file}')
        # For aggregated catalogs, we may not have direct access to the file
        # in the terraform context, so we skip file existence check
    tf['schemas'][s['subject']] = {
        'subject': s['subject'],
        'schema_file': schema_file
    }

# Only add schema registry attributes if schemas are present
if data.get('schemas'):
    required_sr_vars = ['SCHEMA_REGISTRY_ID', 'SCHEMA_REGISTRY_API_KEY', 'SCHEMA_REGISTRY_API_SECRET', 'SCHEMA_REGISTRY_REST_ENDPOINT']
    missing_sr_vars = [var for var in required_sr_vars if not os.getenv(var)]
    if missing_sr_vars:
        print(f"Error: Missing required schema registry environment variables: {', '.join(missing_sr_vars)}")
        sys.exit(1)
    tf['schema_registry_id'] = os.getenv('SCHEMA_REGISTRY_ID')
    tf['schema_registry_api_key'] = os.getenv('SCHEMA_REGISTRY_API_KEY')
    tf['schema_registry_api_secret'] = os.getenv('SCHEMA_REGISTRY_API_SECRET')
    tf['schema_registry_rest_endpoint'] = os.getenv('SCHEMA_REGISTRY_REST_ENDPOINT')

# Process access_config: creates both service_accounts and acls from unified structure
acl_counter = 0
for ac in data.get('access_config', []):
    sa_name = ac['name']
    sa_key = sa_name.lower().replace(' ', '-')
    
    # Create service account
    tf['service_accounts'][sa_key] = {
        'display_name': sa_name,
        'description': ac.get('description', f'Service account for {sa_name}')
    }
    
    # Create ACL for each topic
    for topic in ac.get('topics', []):
        if topic not in tf['topics']:
            print(f'Error: access_config entry "{sa_name}" references non-existent topic: {topic}')
            sys.exit(1)
        
        acl_entry = {
            'role': ac['role'],
            'service_account_key': sa_key,
            'crn_pattern': f"crn://confluent.cloud/organization={tf['organization_id']}/environment={tf['environment_id']}/cluster={tf['kafka_cluster_id']}/topic={topic}"
        }
        tf['acls'][f'acl_{acl_counter}'] = acl_entry
        acl_counter += 1

with open(sys.argv[2],'w') as o:
    json.dump(tf, o, indent=2)
print(f'Generated {sys.argv[2]}')