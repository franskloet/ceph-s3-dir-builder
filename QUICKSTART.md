# Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make executable (already done)
chmod +x dir-builder.py
```

## Basic Workflow

### 1. Create a configuration file

Create `my-config.yaml`:

```yaml
bucket: my-bucket
create_bucket: false
create_directories: true
create_users: false

user_groups:
  alice: admin-group
  bob: user-group

directories:
  name: ""
  children:
    - name: public
      access:
        level: read
        groups: [user-group]
    
    - name: admin
      access:
        level: full
        groups: [admin-group]
```

### 2. Preview the structure

```bash
./dir-builder.py my-config.yaml --print-tree
```

### 3. Dry run (preview commands)

```bash
./dir-builder.py my-config.yaml --dry-run
```

### 4. Apply configuration

```bash
./dir-builder.py my-config.yaml
```

## Common Scenarios

### Scenario 1: User Home Directories

```yaml
bucket: user-homes
directories:
  name: ""
  children:
    - name: alice
      access:
        level: full
        users: [alice]
    - name: bob
      access:
        level: full
        users: [bob]
```

### Scenario 2: Shared Project

```yaml
bucket: project-x
user_groups:
  alice: [team, leads]
  bob: team
  charlie: team

directories:
  name: ""
  children:
    - name: data
      access:
        level: read
        groups: [team]
    
    - name: workspace
      access:
        level: full
        groups: [team]
    
    - name: admin
      access:
        level: full
        groups: [leads]
```

### Scenario 3: Multi-level Access

```yaml
bucket: department-storage
directories:
  name: ""
  children:
    - name: department-a
      access:
        level: full
        groups: [dept-a]
      children:
        - name: public
          access:
            level: read
            groups: [everyone]
        - name: internal
          access:
            level: full
            groups: [dept-a]
```

## Command Reference

```bash
# Preview tree structure only
./dir-builder.py config.yaml --print-tree

# Dry run (see what would be executed)
./dir-builder.py config.yaml --dry-run

# Apply configuration
./dir-builder.py config.yaml

# Use custom tenant
./dir-builder.py config.yaml --tenant my_tenant

# Specify aws-tools location
./dir-builder.py config.yaml --aws-tools /path/to/aws-tools
```

## Access Levels

- `read`: View and download files
- `write`: Upload, modify, and delete files (includes read)
- `full`: All S3 operations (default)

## Tips

1. **Always start with `--dry-run`** to preview changes
2. **Use `--print-tree`** to visualize your structure before applying
3. **Set `create_users: false`** if users already exist
4. **Use groups** for common permissions to simplify management
5. **Test with a small config** first before scaling up

## Troubleshooting

**Python not found?**
```bash
python3 dir-builder.py config.yaml
```

**PyYAML not installed?**
```bash
pip install pyyaml
# or
pip3 install pyyaml
```

**aws-tools not found?**
```bash
./dir-builder.py config.yaml --aws-tools /full/path/to/aws-tools
```

**Want to see what commands will run?**
```bash
./dir-builder.py config.yaml --dry-run
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [example-simple.yaml](example-simple.yaml) for a basic example
- Check [example-research.yaml](example-research.yaml) for a complex example
- Refer to [aws-tools README](../aws-tools/README.md) for underlying commands
