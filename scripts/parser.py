import yaml, json, sys, os

if len(sys.argv) != 3:
    print('Usage: parser.py <input-yaml> <output-json>')
    sys.exit(1)

with open(sys.argv[1],'r') as f:
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
    schema_file = s['schema_file']
    if not schema_file.startswith('schemas/'):
        print(f'Error: Schema file must be under schemas/: {schema_file}')
        sys.exit(1)
    if not os.path.exists(schema_file):
        print(f'Error: Schema file not found: {schema_file}')
        sys.exit(1)
    tf['schemas'][s['subject']] = {
        'subject': s['subject'],
        'schema_file': schema_file
    }

# Only add schema_registry_id if schemas are present
if data.get('schemas'):
    if not os.getenv('SCHEMA_REGISTRY_ID'):
        print("Error: SCHEMA_REGISTRY_ID environment variable is required when schemas are defined")
        sys.exit(1)
    tf['schema_registry_id'] = os.getenv('SCHEMA_REGISTRY_ID')

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