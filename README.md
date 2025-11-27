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
source ~/.bashrc  # This sets AWS_SCRIPTS_DIR environment variable
```

**Important**: The aws-tools installation sets the `AWS_SCRIPTS_DIR` environment variable, which dir-builder uses to locate aws-tools commands. After installation, verify it's set:
```bash
echo $AWS_SCRIPTS_DIR  # Should show path to aws-tools directory
```

If `AWS_SCRIPTS_DIR` is not set, you'll need to either:
- Re-source your shell config: `source ~/.bashrc`
- Or specify `--aws-tools` path manually when running dir-builder

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
./dir-builder.py config.yaml  # Uses $AWS_SCRIPTS_DIR automatically
./export-config.py --bucket my-bucket
```

## Quick Start

**Prerequisites**: Ensure aws-tools is installed and `$AWS_SCRIPTS_DIR` is set (see Installation above).

1. Create a configuration file (see examples below)
2. Preview changes with dry-run:
```bash
./dir-builder.py my-config.yaml --dry-run
```
3. Apply the configuration:
```bash
./dir-builder.py my-config.yaml
```

**Note**: If `$AWS_SCRIPTS_DIR` is not set, you'll need to specify the aws-tools location:
```bash
./dir-builder.py my-config.yaml --aws-tools /path/to/aws-tools
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
  --aws-tools AWS_TOOLS Path to aws-tools directory
                        (default: $AWS_SCRIPTS_DIR or ../aws-tools)
  --tenant TENANT       Ceph tenant name (default: $AWS_DEFAULT_TENANT)
  --dry-run             Preview changes without executing them
  --print-tree          Only print the directory tree and exit
```

#### aws-tools Path Resolution

The script locates aws-tools using the following priority:

1. **Command line argument**: `--aws-tools /path/to/aws-tools`
2. **Environment variable**: `$AWS_SCRIPTS_DIR` (set by aws-tools installation)
3. **Default relative path**: `../aws-tools`

If you've installed aws-tools using its install script, `$AWS_SCRIPTS_DIR` is automatically set and you don't need to specify `--aws-tools`.

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

## Policy Behavior: Additive vs. Replacement

### How Policies Are Applied

When you run `dir-builder` multiple times with different configuration files, the policies are applied in an **additive manner** across different prefixes, but policies for the same prefix are **replaced**.

#### Key Behavior:

1. **Each policy has a unique name** based on the bucket name and prefix:
   - Full bucket access: `s3-{bucket}-full`
   - Prefix-specific: `s3-{bucket}-{prefix}` (e.g., `s3-data-users-alice`)

2. **User and group policies are independent**:
   - Policies attached to a **user** are completely separate from policies attached to a **group**
   - You can add user-specific access without affecting existing group policies
   - IAM evaluates all applicable policies (user + all groups) and grants the union of permissions

3. **Policies are additive** when they target different prefixes:
   - Running `dir-builder` with config A creates policies for prefixes in config A
   - Running `dir-builder` with config B creates **additional** policies for prefixes in config B
   - Both sets of policies coexist on the same entity (user or group)

4. **Policies are replaced** when they target the same prefix on the same entity:
   - If config A grants group `researchers` read access to `data/experiments/`
   - Then config B grants group `researchers` full access to `data/experiments/`
   - The policy `s3-bucket-data-experiments` **on the researchers group** is replaced (not merged)
   - However, user policies for that prefix remain unaffected

#### Practical Example

If you run:
```bash
# First: Grant access to general folders
./dir-builder.py export-groups.yaml

# Second: Grant Alice additional access to her personal folder
./dir-builder.py export-groups-alice.yaml
```

The result:
- Group policies from `export-groups.yaml` remain active
- Additional policies from `export-groups-alice.yaml` are added (likely user policies for Alice)
- If both configs define access to the **same prefix for the same entity** (user or group), the second one wins
- User policies and group policies don't conflict (they're on different entities)

#### Use Cases

**Use Case 1: Incremental Access Grant (Additive)**
```bash
# Step 1: Base permissions for all groups
./dir-builder.py base-structure.yaml

# Step 2: Add special access for specific users
./dir-builder.py alice-special-access.yaml
./dir-builder.py bob-special-access.yaml
```

**Use Case 2: Multiple Users, Same Folder**
```bash
# Grant different users access to the same folder incrementally
./dir-builder.py example-policy-additive-1.yaml       # Base: researchers group gets read
./dir-builder.py example-policy-additive-2.yaml       # Alice gets write access
./dir-builder.py example-policy-additive-bob.yaml     # Bob gets write access
# Result: Alice and Bob both have write access, other researchers have read
```

**Use Case 3: One User, Multiple Folders Over Time**
```bash
# Grant a user access to different folders incrementally
./dir-builder.py example-policy-additive-2.yaml             # Alice gets experiment-2024 access
./dir-builder.py example-policy-additive-alice-archive.yaml # Alice gets archive access
# Result: Alice has access to both folders, previous access unchanged
```

**Use Case 4: Full Replacement (Re-run same config)**
```bash
# Initial setup
./dir-builder.py my-config.yaml

# Modify my-config.yaml and re-apply
./dir-builder.py my-config.yaml  # Policies for same prefixes on same entities are updated
```

#### Important Notes

- **No automatic cleanup**: Old policies are not removed unless explicitly deleted
- **Policy names are deterministic**: Same bucket + prefix + entity = same policy name
- **User/group independence is convenient**: To grant a user access to an existing folder, just specify the user - no need to re-specify existing group access
- **Use with caution**: Be aware of which prefixes and entities are defined in each config file
- **Dry-run is your friend**: Always use `--dry-run` to preview policy changes

For concrete examples demonstrating additive behavior, see:
- `example-policy-additive-1.yaml` - Base structure with group access
- `example-policy-additive-2.yaml` - Add Alice-specific access (no need to re-specify groups)
- `example-policy-additive-3.yaml` - Minimal example showing independent user/group policies
- `example-policy-additive-bob.yaml` - Grant another user access to the same folder
- `example-policy-additive-alice-archive.yaml` - Grant Alice access to another folder incrementally

### Incremental Permission Management Patterns

The additive nature of policies enables flexible permission management:

**Pattern 1: Grant Multiple Users Access to Same Folder**

When multiple users need access to the same folder, create separate configs:

```yaml
# alice-experiment-access.yaml
directories:
  name: ""
  children:
    - name: projects/experiment-2024
      access:
        users: [alice]
        level: full
```

```yaml
# bob-experiment-access.yaml
directories:
  name: ""
  children:
    - name: projects/experiment-2024
      access:
        users: [bob]
        level: full
```

Run both configs - each creates an independent user policy.

**Pattern 2: Grant One User Access to Multiple Folders**

When a user needs access to additional folders over time, create new configs:

```yaml
# alice-archive-access.yaml
directories:
  name: ""
  children:
    - name: archive
      access:
        users: [alice]
        level: full
```

This adds to Alice's existing permissions without modifying them.

**Pattern 3: Temporary Project Access**

Grant temporary access by running a config, then later remove the policy manually:

```bash
# Grant access
./dir-builder.py temp-project-alice.yaml

# Later, remove the policy
aws iam delete-user-policy --user-name alice --policy-name s3-bucket-temp-project
```

**Benefits of Incremental Configs:**
- **Audit trail**: Each permission grant is a separate file with timestamp
- **No conflicts**: Different users/folders = different policies
- **Easy rollback**: Remove specific policies without affecting others
- **Minimal updates**: Only specify what changes, not the entire structure

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

The script tries to locate aws-tools in this order:
1. `--aws-tools` argument (if provided)
2. `$AWS_SCRIPTS_DIR` environment variable
3. `../aws-tools` (default relative path)

Solutions:

**Option 1: Use the environment variable (recommended)**
```bash
# If aws-tools is installed, source the aliases file
source ~/.bashrc  # or wherever aws-aliases.sh is sourced
echo $AWS_SCRIPTS_DIR  # Should show the aws-tools path
./dir-builder.py config.yaml  # No --aws-tools needed
```

**Option 2: Specify the path explicitly**
```bash
./dir-builder.py config.yaml --aws-tools /home/frans/Development/storage/aws-tools
```

**Option 3: Set the environment variable manually**
```bash
export AWS_SCRIPTS_DIR=/home/frans/Development/storage/aws-tools
./dir-builder.py config.yaml
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

- `AWS_SCRIPTS_DIR`: Location of aws-tools directory (set by aws-tools installation)
  - Used as fallback if `--aws-tools` is not specified
  - Automatically set when you install aws-tools and source the aliases file
- `AWS_DEFAULT_TENANT`: Default Ceph tenant (can be overridden with `--tenant`)
- `AWS_PROFILE`: AWS CLI profile to use for operations

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
