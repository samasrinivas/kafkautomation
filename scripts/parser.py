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
    "acls": {}
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

for i, a in enumerate(data.get('acls', [])):
    tf['acls'][f'acl_{i}'] = {
        'principal': a['principal'],
        'role': a['role'],
        'crn_pattern': a['crn_pattern']
    }

with open(sys.argv[2],'w') as o:
    json.dump(tf, o, indent=2)
print(f'Generated {sys.argv[2]}')