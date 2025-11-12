# Changelog

## 2025-11-12 - Version 2.0

### Added - Flexible Per-Entity Access Levels
- **Major Feature**: New flexible access control format allowing different access levels for different users/groups on the same directory
  ```yaml
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
- Full backward compatibility with old format (legacy format still supported)
- Enhanced tree display showing per-entity access levels
- Added `example-flexible.yaml` demonstrating new capabilities

### Added - Configuration Export Tool
- **New Tool**: `export-config.py` - Reverse engineer existing IAM inline policies into YAML configs
- Export single bucket, prefix subtree, or all buckets
- Automatically infers access levels from policy actions
- Discovers group memberships
- Generates configs in the new flexible format
- Perfect for backup, documentation, and migration workflows
- See `EXPORT-README.md` for full documentation

## 2025-11-12 - Version 1.1

### Fixed
- **User creation hanging issue**: Fixed the script hanging when `create_users: true` and users already exist. The script now properly passes `AUTO_CONFIRM=1` environment variable to the subprocess, automatically creating new access keys for existing users without manual confirmation.

### Added
- **Explicit group configuration**: Added support for defining groups with their members in the configuration file using the `groups` section.
  
  ```yaml
  groups:
    admin-group: [alice, bob]
    researchers:
      members: [charlie, david]
  ```

- **Group creation control**: Added `create_groups` configuration option (default: `true`)
  - Set to `false` if groups already exist to skip group creation
  - Similar to `create_users` option

- **Safety documentation**: Added explicit documentation confirming that:
  - Existing bucket content is NOT overwritten
  - Directory creation only adds zero-byte placeholders
  - Existing files in prefixes are never touched
  - The tool is idempotent and safe to run multiple times

### Enhanced
- **Flexible group membership**: Now supports two complementary ways to define group memberships:
  1. `groups` section: Define groups and their members (recommended)
  2. `user_groups` section: Map users to groups (existing method)
  
  Both methods can be used together.

### Examples
- Added `example-groups.yaml` demonstrating explicit group definitions

### Configuration Options

New/Updated options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `create_groups` | boolean | `true` | Create IAM groups (set to false if they exist) |
| `groups` | object | `{}` | Define groups with their members |

## Initial Release

### Features
- Tree-based directory structure management
- Hierarchical IAM access control
- Integration with aws-tools
- Dry-run mode
- Support for read/write/full access levels
- Tenant-aware Ceph S3 resource ARNs
