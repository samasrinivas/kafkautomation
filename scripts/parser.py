import yaml, json, sys

if len(sys.argv) != 3:
    print('Usage: parser.py <input-yaml> <output-json>')
    sys.exit(1)

with open(sys.argv[1],'r') as f:
    data = yaml.safe_load(f)

tf = {"topics": {}, "schemas": {}, "acls": {}}
for t in data.get('topics', []):
    tf['topics'][t['name']] = {
        'partitions': t.get('partitions', 3),
        'replication_factor': t.get('replication_factor', 3),
        'config': t.get('config', {})
    }
for s in data.get('schemas', []):
    tf['schemas'][s['subject']] = {
        'subject': s['subject'],
        'schema_file': s['schema_file']
    }
for i, a in enumerate(data.get('acls', [])):
    tf['acls'][f'acl_{i}'] = {
        'principal': a['principal'],
        'role': a['role'],
        'crn_pattern': a['crn_pattern']
    }

with open(sys.argv[2],'w') as o:
    json.dump(tf,o,indent=2)
print(f'Generated {sys.argv[2]}')
