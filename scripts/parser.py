import yaml, json, sys, os

if len(sys.argv) != 3:
    print('Usage: parser.py <input-yaml> <output-json>')
    sys.exit(1)

with open(sys.argv[1],'r') as f:
    data = yaml.safe_load(f)

# Extract required Confluent Cloud variables
tf = {
    "organization_id": data.get('organization_id'),
    "environment_id": data.get('environment_id'),
    "kafka_cluster_id": data.get('kafka_cluster_id'),
    "rest_endpoint": data.get('rest_endpoint'),
    "schema_registry_id": data.get('schema_registry_id'),
    "topics": {},
    "schemas": {},
    "acls": {},
    "service_accounts": {}
}

# Validate required fields
required_fields = ['organization_id', 'environment_id', 'kafka_cluster_id', 'rest_endpoint', 'schema_registry_id']
missing = [f for f in required_fields if not tf.get(f)]
if missing:
    print(f'Error: Missing required fields in YAML: {", ".join(missing)}')
    sys.exit(1)

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
            'crn_pattern': f"crn://confluent.cloud/organization={data.get('organization_id', 'unknown')}/environment={data.get('environment_id')}/cluster={data.get('kafka_cluster_id')}/topic={topic}"
        }
        tf['acls'][f'acl_{acl_counter}'] = acl_entry
        acl_counter += 1

with open(sys.argv[2],'w') as o:
    json.dump(tf, o, indent=2)
print(f'Generated {sys.argv[2]}')