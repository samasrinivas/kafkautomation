import yaml, json, sys, os

if len(sys.argv) != 3:
    print('Usage: parser.py <input-yaml> <output-json>')
    sys.exit(1)

with open(sys.argv[1],'r') as f:
    data = yaml.safe_load(f)

# Extract required Confluent Cloud variables
tf = {
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
required_fields = ['environment_id', 'kafka_cluster_id', 'rest_endpoint', 'schema_registry_id']
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

# Legacy support: process separate service_accounts and acls sections if present
for sa in data.get('service_accounts', []):
    sa_key = sa['name'].lower().replace(' ', '-')
    if sa_key not in tf['service_accounts']:  # Don't overwrite from access_config
        tf['service_accounts'][sa_key] = {
            'display_name': sa['name'],
            'description': sa.get('description', f'Service account for {sa["name"]}')
        }

for i, a in enumerate(data.get('acls', [])):
    if f'acl_{i + acl_counter}' not in tf['acls']:  # Avoid collision with access_config ACLs
        acl_entry = {
            'role': a['role']
        }
        
        if 'service_account' in a:
            sa_name = a['service_account']
            sa_key = sa_name.lower().replace(' ', '-')
            if sa_key not in tf['service_accounts']:
                print(f'Error: ACL references non-existent service account: {sa_name}')
                sys.exit(1)
            acl_entry['service_account_key'] = sa_key
        elif 'principal' in a:
            acl_entry['principal'] = a['principal']
        else:
            print(f'Error: ACL must specify either "service_account" or "principal"')
            sys.exit(1)
        
        if 'topic' in a:
            topic = a['topic']
            if topic not in tf['topics']:
                print(f'Error: ACL references non-existent topic: {topic}')
                sys.exit(1)
            acl_entry['crn_pattern'] = f"crn://confluent.cloud/organization={data.get('organization_id', 'unknown')}/environment={data.get('environment_id')}/cluster={data.get('kafka_cluster_id')}/topic={topic}"
        elif 'crn_pattern' in a:
            acl_entry['crn_pattern'] = a['crn_pattern']
        else:
            print(f'Error: ACL must specify either "topic" or "crn_pattern"')
            sys.exit(1)
        
        tf['acls'][f'acl_{i + acl_counter}'] = acl_entry

with open(sys.argv[2],'w') as o:
    json.dump(tf, o, indent=2)
print(f'Generated {sys.argv[2]}')