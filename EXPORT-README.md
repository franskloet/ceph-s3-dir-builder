# Export Configuration from Existing IAM Setup

The `export-config.py` script reads your existing IAM inline policies and generates dir-builder YAML configuration files.

## Features

- **Reverse engineer** existing IAM access into dir-builder format
- **Export single bucket** or all buckets
- **Filter by prefix** to export subtrees
- **Infers access levels** (read/write/full) from policy actions
- **Discovers group memberships** automatically
- **Outputs flexible format** with per-entity access levels

## Usage

```bash
# Export a single bucket to stdout
./export-config.py --bucket my-bucket

# Export a single bucket to file
./export-config.py --bucket my-bucket -o my-bucket-config.yaml

# Export only a specific prefix
./export-config.py --bucket my-bucket --prefix data/experiments/ -o config.yaml

# Export all buckets to separate files in a directory
./export-config.py -o exported-configs/

# Use a specific AWS profile
./export-config.py --bucket my-bucket --profile my-profile

# Override tenant in output
./export-config.py --bucket my-bucket --tenant custom_tenant -o config.yaml
```

## How It Works

1. **Reads IAM inline policies** from groups and users
2. **Parses resource ARNs** to extract bucket and prefix information
3. **Infers access levels** from policy actions:
   - `s3:*` → `full`
   - `s3:PutObject` or `s3:DeleteObject` → `write`
   - `s3:GetObject` → `read`
4. **Builds directory tree** from prefix paths
5. **Discovers group memberships**
6. **Outputs YAML config** in the flexible per-entity format

## Examples

### Export department-storage bucket

```bash
./export-config.py --bucket department-storage -o department-storage.yaml
```

**Output:**
```yaml
bucket: department-storage
create_bucket: false
create_directories: true
create_users: false
create_groups: true
groups:
  admin-group:
  - alice
  - admin
  data-team:
  - charlie
  - david
  researchers:
  - alice
  - bob
  - charlie
directories:
  name: ''
  children:
  - name: admin
    access:
    - entity: admin-group
      type: group
      level: full
  - name: research
    access:
    - entity: researchers
      type: group
      level: full
    children:
    - name: data
      access:
      - entity: data-team
        type: group
        level: full
```

### Export all buckets

```bash
./export-config.py -o backup-configs/
```

Creates:
- `backup-configs/export-bucket1.yaml`
- `backup-configs/export-bucket2.yaml`
- `backup-configs/export-bucket3.yaml`

### Export specific prefix

```bash
./export-config.py --bucket research-project --prefix data/ -o data-only.yaml
```

Only exports access for `data/` and its subdirectories.

## What Gets Exported

### ✅ Included
- Inline group policies (created by `aws-add-group-bucket-policy`)
- Inline user policies (created by `aws-create-user-policy`)
- Group memberships
- Per-entity access levels (read/write/full)

### ❌ Not Included
- AWS managed policies (these are not bucket-specific)
- Bucket policies (separate from IAM)
- Assumed role policies
- Bucket ACLs

## Use Cases

### 1. Backup and Version Control
```bash
# Export all configurations
./export-config.py -o backups/$(date +%Y%m%d)/

# Commit to git
git add backups/
git commit -m "IAM backup $(date +%Y-%m-%d)"
```

### 2. Migrate Between Environments
```bash
# Export from production
AWS_PROFILE=prod ./export-config.py --bucket prod-data -o prod-data.yaml

# Edit for dev environment
sed 's/prod-data/dev-data/' prod-data.yaml > dev-data.yaml

# Apply to dev
AWS_PROFILE=dev ./dir-builder.py dev-data.yaml
```

### 3. Document Current Access
```bash
# Generate readable documentation
./export-config.py --bucket team-storage | tee team-storage-access.yaml
```

### 4. Clone Bucket Access Structure
```bash
# Export existing bucket
./export-config.py --bucket old-bucket -o template.yaml

# Modify for new bucket
sed 's/old-bucket/new-bucket/' template.yaml > new-bucket.yaml

# Apply to new bucket
./dir-builder.py new-bucket.yaml
```

## Limitations

- Only reads **inline policies** created by aws-tools
- Cannot infer directory structure from actual S3 objects (only from IAM)
- Access levels are inferred; edge cases may need manual review
- Does not capture policy conditions or advanced IAM features

## Requirements

- Python 3.7+
- PyYAML: `pip install pyyaml`
- AWS CLI configured with appropriate IAM read permissions
- IAM permissions needed:
  - `iam:ListGroups`
  - `iam:ListUsers`
  - `iam:GetGroup`
  - `iam:ListGroupPolicies`
  - `iam:GetGroupPolicy`
  - `iam:ListUserPolicies`
  - `iam:GetUserPolicy`

## Troubleshooting

### "AWS command failed: Access Denied"
Ensure your AWS profile has IAM read permissions.

### "No inline IAM access discovered"
The script only reads inline policies. Managed policies and bucket policies are not included.

### Access level seems wrong
The script infers levels from actions. Review the generated YAML and adjust `level` values if needed.

### Missing prefixes
If you used custom policy creation (not aws-tools), the resource ARN format may differ. Check the generated config.

## Integration with dir-builder

The exported YAML is fully compatible with dir-builder:

```bash
# Export current config
./export-config.py --bucket my-bucket -o current.yaml

# Review and modify
vim current.yaml

# Re-apply (idempotent)
./dir-builder.py current.yaml
```

This creates a full workflow:
1. **Export** current state
2. **Modify** in version control
3. **Review** changes with `--dry-run`
4. **Apply** changes
5. **Export** again to verify
