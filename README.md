# Directory Builder for Ceph S3 Storage

A Python utility for managing Ceph S3-compatible directory storage with hierarchical IAM access control. Define your directory structure and access permissions in a YAML configuration file, and automatically create IAM users, groups, and policies.

## Features

- **Tree-based directory structure**: Define nested folders with parent-child relationships
- **Flexible access control**: Link each folder to IAM users and/or groups
- **Per-entity access levels**: Different users/groups can have different access levels on the same directory
- **Access levels**: Configure `read`, `write`, or `full` access per directory
- **Tenant support**: Built-in support for Ceph tenant-aware resource ARNs
- **Dry-run mode**: Preview all changes before applying them
- **Automated IAM management**: Automatically creates users, groups, and policies using existing aws-tools
- **Export existing configs**: Reverse engineer your current IAM setup into YAML configs

## Prerequisites

- Python 3.7+
- PyYAML: `pip install pyyaml`
- AWS CLI configured
- [aws-tools](../aws-tools) installed and configured
- Ceph S3-compatible storage endpoint

## Installation

### Quick Install (Recommended)

The install script creates wrapper commands for easy use:

```bash
# User install (no root required, installs to ~/bin)
./install.sh

# System-wide install (requires root)
sudo ./install.sh

# Custom location
./install.sh /path/to/install/dir
```

After installation, you can use the tools without `.py` extension:
```bash
dir-builder config.yaml --dry-run
export-config --bucket my-bucket
```

### Manual Installation

1. Ensure aws-tools is installed:
```bash
cd /home/frans/Development/storage/aws-tools
./install.sh ~/s3/AWS
source ~/.bashrc
```

2. Install Python dependencies:
```bash
pip install pyyaml
```

3. Make scripts executable:
```bash
chmod +x dir-builder.py export-config.py
```

Then run with:
```bash
./dir-builder.py config.yaml
./export-config.py --bucket my-bucket
```

## Quick Start

1. Create a configuration file (see examples below)
2. Preview changes with dry-run:
```bash
./dir-builder.py my-config.yaml --dry-run
```
3. Apply the configuration:
```bash
./dir-builder.py my-config.yaml
```

## Configuration Format

Configuration files are written in YAML and define:
- Bucket name and settings
- Directory tree structure
- IAM access control per directory
- User-to-group mappings

### Basic Structure

```yaml
bucket: my-bucket-name
tenant: sils_mns  # Optional: defaults to $AWS_DEFAULT_TENANT
create_bucket: true
create_directories: true
create_users: false

user_groups:
  alice: [group1, group2]
  bob: group1

directories:
  name: ""  # Root
  children:
    - name: folder1
      access:
        level: full
        users: [alice]
        groups: [group1]
      children:
        - name: subfolder1
          access:
            level: read
            groups: [group2]
```

### Configuration Options

#### Top-level Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bucket` | string | *required* | S3 bucket name |
| `tenant` | string | `$AWS_DEFAULT_TENANT` or `sils_mns` | Ceph tenant name |
| `create_bucket` | boolean | `false` | Create bucket if it doesn't exist |
| `bucket_acl` | string | `private` | Bucket ACL (private, public-read, etc.) |
| `create_directories` | boolean | `false` | Create directory placeholders in S3 |
| `create_users` | boolean | `false` | Create IAM users (set to false if they exist) |
| `create_groups` | boolean | `true` | Create IAM groups (set to false if they exist) |
| `groups` | object | `{}` | Define groups with their members |
| `user_groups` | object | `{}` | Map users to groups (alternative to `groups`) |
| `user_groups` | object | `{}` | Map users to groups |

#### Directory Node Options

Each directory node in the tree can have:

| Option | Type | Description |
|--------|------|-------------|
| `name` | string | Directory name (use "" for root) |
| `access` | object | Access control configuration |
| `children` | array | Child directories |

#### Access Configuration

Access control can be configured in two formats:

**Format 1: Simple (Legacy) - Same access level for all**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | `full` | Access level: `read`, `write`, or `full` |
| `users` | array | `[]` | List of IAM users with access |
| `groups` | array | `[]` | List of IAM groups with access |

**Format 2: Flexible - Different access levels per entity**

Use a list of entity definitions:

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `entity` | string | yes | User or group name |
| `type` | string | yes | `user` or `group` |
| `level` | string | no (default: `full`) | Access level: `read`, `write`, or `full` |

### Access Levels

- **`read`**: GetObject, GetObjectVersion, ListBucket, ListBucketVersions
- **`write`**: Includes read + PutObject, DeleteObject
- **`full`**: All S3 operations (s3:*)

### Group Configuration

You can define groups in two ways:

**Method 1: Using the `groups` section (recommended)**
```yaml
groups:
  # Simple list format
  admin-group: [alice, bob]
  
  # Detailed format
  researchers:
    members: [charlie, david]
```

**Method 2: Using the `user_groups` section**
```yaml
user_groups:
  alice: [admin-group, researchers]
  bob: admin-group
```

**Note:** Both methods can be used together and complement each other.

### Flexible Per-Entity Access Levels

The new flexible format allows you to specify different access levels for different users and groups on the same directory:

```yaml
- name: shared-data
  access:
    - entity: alice
      type: user
      level: full
    - entity: bob
      type: user
      level: write
    - entity: viewers
      type: group
      level: read
```

**Result:** Alice gets full access, Bob gets write access, and the viewers group gets read-only access to the same directory.

**Backward Compatibility:** The old simple format still works:
```yaml
- name: shared-data
  access:
    level: read
    users: [alice, bob]
    groups: [viewers]
```

### Safety Notes

**Existing content is NOT overwritten:**
- Creating buckets: Only creates if bucket doesn't exist (fails if it exists)
- Creating directories: Only creates zero-byte placeholder objects with trailing slashes
- Existing files in prefixes are never touched or deleted
- This tool is safe to run multiple times - it's idempotent

## Usage Examples

### Example 1: Research Project Structure

Create a research project with different access levels:

```yaml
bucket: research-project-2025
create_bucket: true
create_directories: true
create_users: false

user_groups:
  alice: [researchers, data-team]
  bob: researchers
  charlie: data-team

directories:
  name: ""
  children:
    - name: raw-data
      access:
        level: read
        groups: [researchers]
      children:
        - name: experiments
          access:
            level: full
            users: [alice]
    
    - name: processed
      access:
        level: full
        groups: [data-team]
    
    - name: shared
      access:
        level: full
        groups: [researchers, data-team]
```

**Result:**
- `raw-data/`: All researchers can read
- `raw-data/experiments/`: Alice has full access
- `processed/`: Data team has full access
- `shared/`: All team members have full access

### Example 2: User Home Directories

```yaml
bucket: team-storage
create_directories: true

directories:
  name: ""
  children:
    - name: users
      children:
        - name: john
          access:
            level: full
            users: [john]
        - name: jane
          access:
            level: full
            users: [jane]
    
    - name: team
      access:
        level: full
        groups: [developers]
```

### Example 3: Multi-tenant Setup

```yaml
bucket: shared-storage
tenant: project_alpha

directories:
  name: ""
  children:
    - name: public
      access:
        level: read
        groups: [all-users]
    
    - name: restricted
      access:
        level: full
        users: [admin]
      children:
        - name: dept-a
          access:
            level: full
            groups: [dept-a-team]
        - name: dept-b
          access:
            level: full
            groups: [dept-b-team]
```

## Command Line Usage

### Basic Commands

```bash
# Preview changes without applying (recommended first step)
./dir-builder.py config.yaml --dry-run

# Apply configuration
./dir-builder.py config.yaml

# Use custom tenant
./dir-builder.py config.yaml --tenant my_tenant

# Specify aws-tools location
./dir-builder.py config.yaml --aws-tools /path/to/aws-tools

# Just print the directory tree
./dir-builder.py config.yaml --print-tree
```

### Command Line Options

```
usage: dir-builder.py [-h] [--aws-tools AWS_TOOLS] [--tenant TENANT]
                      [--dry-run] [--print-tree]
                      config

positional arguments:
  config                Path to YAML configuration file

optional arguments:
  -h, --help            Show help message
  --aws-tools AWS_TOOLS Path to aws-tools directory (default: ../aws-tools)
  --tenant TENANT       Ceph tenant name (default: $AWS_DEFAULT_TENANT)
  --dry-run             Preview changes without executing them
  --print-tree          Only print the directory tree and exit
```

## How It Works

The tool executes the following steps:

1. **Load Configuration**: Parse YAML and build internal tree structure
2. **Create S3 Bucket**: Create bucket if `create_bucket: true`
3. **Create Directories**: Create directory placeholders if `create_directories: true`
4. **Setup IAM Entities**: 
   - Create IAM groups using `aws-create-group`
   - Apply default policies to groups using `aws-create-group-policy`
   - Create IAM users if `create_users: true`
5. **Add Users to Groups**: Map users to groups using `aws-add-user-to-group`
6. **Apply Access Policies**:
   - For each directory node with access configuration
   - Apply group policies using `aws-add-group-bucket-policy`
   - Apply user policies using `aws-create-user-policy`

## Integration with aws-tools

This utility uses your existing aws-tools commands:

| dir-builder Function | aws-tools Command |
|---------------------|-------------------|
| Create bucket | `aws-mb.sh` |
| Create directory | `aws-md.sh` |
| Create group | `aws-create-group.sh` |
| Group default policy | `aws-create-group-policy.sh` |
| Group bucket policy | `aws-add-group-bucket-policy.sh` |
| Create user | `aws-create-user.sh` |
| User bucket policy | `aws-create-user-policy.sh` |
| Add user to group | `aws-add-user-to-group.sh` |

## Best Practices

1. **Always dry-run first**: Use `--dry-run` to preview changes
```bash
./dir-builder.py config.yaml --dry-run
```

2. **Use groups for common permissions**: Assign users to groups rather than individual user policies when possible

3. **Start with read-only**: Begin with `level: read` and grant more access as needed

4. **Hierarchical access**: Child directories can override parent access rules

5. **Version control your configs**: Keep configuration files in git

6. **Separate environments**: Use different config files for dev/staging/production

## Troubleshooting

### "aws-tools directory not found"
Ensure the `--aws-tools` path is correct:
```bash
./dir-builder.py config.yaml --aws-tools /home/frans/Development/storage/aws-tools
```

### "User already exists"
Set `create_users: false` if users already exist

### "Group already exists"
This is normal - the tool will continue and apply policies to existing groups

### "Access denied" errors
Ensure your current AWS profile has IAM permissions:
```bash
aws-whoami  # Check current profile
export AWS_PROFILE=default  # Switch to admin profile
```

### YAML parsing errors
Validate YAML syntax:
```bash
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

## Advanced Usage

### Complex Hierarchies

You can nest directories arbitrarily deep:

```yaml
directories:
  name: ""
  children:
    - name: projects
      children:
        - name: project-a
          children:
            - name: data
              children:
                - name: raw
                  access:
                    level: read
                    groups: [viewers]
                - name: processed
                  access:
                    level: full
                    groups: [analysts]
```

### Mixed User and Group Access

Combine users and groups at any level:

```yaml
- name: collaboration
  access:
    level: full
    users: [lead-researcher]
    groups: [research-team, external-partners]
```

### Per-folder Access Levels

Different folders can have different access levels:

```yaml
- name: documents
  children:
    - name: public
      access:
        level: read
        groups: [everyone]
    - name: internal
      access:
        level: write
        groups: [staff]
    - name: confidential
      access:
        level: full
        users: [admin, director]
```

## Configuration Schema

For detailed schema documentation, see the dataclasses in `dir-builder.py`:
- `AccessConfig`: Access control configuration
- `DirectoryNode`: Directory tree node structure

## Examples

See the included example files:
- `example-simple.yaml`: Basic user home directories
- `example-research.yaml`: Research project structure

## Environment Variables

- `AWS_DEFAULT_TENANT`: Default Ceph tenant (can be overridden with `--tenant`)
- `AWS_PROFILE`: AWS CLI profile to use
- `AWS_SCRIPTS_DIR`: Location of aws-tools (set by aws-aliases.sh)

## Contributing

To extend or modify dir-builder:

1. The main logic is in `DirBuilder` class
2. Tree structure is built in `_build_tree()`
3. Commands are executed via `_run_command()`
4. Add new features by adding methods and calling them in `build()`

## License

Use freely in your environment.

## See Also

- [aws-tools README](https://github.com/franskloet/aws-tools) - Underlying IAM management commands
- [Ceph RGW Documentation](https://docs.ceph.com/en/latest/radosgw/) - Ceph S3 gateway docs
