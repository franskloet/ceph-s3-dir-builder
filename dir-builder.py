#!/usr/bin/env python3
"""
Directory-based S3 IAM Management Utility
Manages Ceph S3 storage with a tree structure linking folders to IAM users/groups
"""

import yaml
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class EntityAccess:
    """Per-entity access configuration"""
    entity: str
    entity_type: str  # 'user' or 'group'
    level: str  # 'read', 'write', or 'full'


@dataclass
class AccessConfig:
    """Configuration for access permissions"""
    # Legacy format fields (for backward compatibility)
    level: str = "full"  # read, write, full
    users: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    # New format field
    entity_access: List[EntityAccess] = field(default_factory=list)


@dataclass
class DirectoryNode:
    """Represents a directory/prefix in the tree"""
    name: str
    path: str
    access: Optional[AccessConfig] = None
    children: List['DirectoryNode'] = field(default_factory=list)
    parent: Optional['DirectoryNode'] = None


class DirBuilder:
    """Main directory builder class"""
    
    def __init__(self, config_file: str, aws_tools_dir: str, tenant: str = None, dry_run: bool = False):
        self.config_file = config_file
        self.aws_tools_dir = Path(aws_tools_dir)
        self.tenant = tenant or os.environ.get('AWS_DEFAULT_TENANT', 'sils_mns')
        self.dry_run = dry_run
        self.config = None
        self.bucket_name = None
        self.root = None
        
    def load_config(self):
        """Load configuration from YAML file"""
        with open(self.config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.bucket_name = self.config.get('bucket')
        if not self.bucket_name:
            raise ValueError("Configuration must specify 'bucket' name")
        
        # Build directory tree
        self.root = self._build_tree(self.config.get('directories', {}))
        
    def _build_tree(self, dir_config: Dict, parent: DirectoryNode = None, path: str = "") -> DirectoryNode:
        """Recursively build directory tree from config"""
        name = dir_config.get('name', '')
        current_path = f"{path}{name}/" if name else path
        
        # Parse access configuration
        access = None
        if 'access' in dir_config:
            access = self._parse_access_config(dir_config['access'])
        
        node = DirectoryNode(
            name=name,
            path=current_path,
            access=access,
            parent=parent
        )
        
        # Process children
        for child_config in dir_config.get('children', []):
            child_node = self._build_tree(child_config, node, current_path)
            node.children.append(child_node)
        
        return node
    
    def _parse_access_config(self, access_cfg) -> AccessConfig:
        """Parse access configuration supporting both old and new formats"""
        access = AccessConfig()
        
        # Check if it's a list (new format)
        if isinstance(access_cfg, list):
            # New format: list of entity access definitions
            for item in access_cfg:
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid access config item: {item}")
                
                entity = item.get('entity')
                entity_type = item.get('type', 'user')  # default to user
                level = item.get('level', 'full')
                
                if not entity:
                    raise ValueError(f"Entity access config missing 'entity' field: {item}")
                
                if entity_type not in ['user', 'group']:
                    raise ValueError(f"Invalid entity type '{entity_type}', must be 'user' or 'group'")
                
                if level not in ['read', 'write', 'full']:
                    raise ValueError(f"Invalid access level '{level}', must be 'read', 'write', or 'full'")
                
                access.entity_access.append(EntityAccess(
                    entity=entity,
                    entity_type=entity_type,
                    level=level
                ))
        
        # Check if it's a dict (old format)
        elif isinstance(access_cfg, dict):
            # Old format: level + users/groups lists
            access.level = access_cfg.get('level', 'full')
            access.users = access_cfg.get('users', [])
            access.groups = access_cfg.get('groups', [])
        
        else:
            raise ValueError(f"Invalid access configuration format: {access_cfg}")
        
        return access
    
    def _run_command(self, cmd: List[str], description: str, env: Dict[str, str] = None):
        """Execute a command with proper error handling"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}🔧 {description}")
        print(f"  Command: {' '.join(cmd)}")
        
        if self.dry_run:
            return
        
        # Use provided env or default to current environment
        if env is None:
            env = os.environ.copy()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env
            )
            if result.stdout:
                print(f"  ✓ {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            # Show both stdout and stderr for better error reporting
            error_output = ""
            if e.stdout:
                error_output += e.stdout.strip()
            if e.stderr:
                if error_output:
                    error_output += "\n"
                error_output += e.stderr.strip()
            
            if error_output:
                print(f"  ✗ Error: {error_output}")
            else:
                print(f"  ✗ Error: Command failed with exit code {e.returncode}")
            
            # Check if we should continue despite the error
            combined_output = (e.stdout or "") + (e.stderr or "")
            if not self._should_continue_on_error(combined_output):
                raise
    
    def _should_continue_on_error(self, error_msg: str) -> bool:
        """Determine if we should continue on certain errors"""
        # Continue if entity already exists
        return "already exists" in error_msg.lower()
    
    def create_bucket(self):
        """Create the S3 bucket if specified"""
        if not self.config.get('create_bucket', False):
            return
        
        acl = self.config.get('bucket_acl', 'private')
        cmd = [
            str(self.aws_tools_dir / "aws-mb.sh"),
            self.bucket_name,
            acl
        ]
        self._run_command(cmd, f"Creating bucket: {self.bucket_name}")
    
    def create_directories(self):
        """Create directory structure in S3"""
        if not self.config.get('create_directories', False):
            return
        
        def create_node_dir(node: DirectoryNode):
            if node.path:  # Skip root
                cmd = [
                    str(self.aws_tools_dir / "aws-md.sh"),
                    self.bucket_name,
                    node.path
                ]
                self._run_command(cmd, f"Creating directory: {node.path}")
            
            for child in node.children:
                create_node_dir(child)
        
        create_node_dir(self.root)
    
    def setup_iam_entities(self):
        """Create all IAM users and groups defined in the tree"""
        users = set()
        groups = set()
        
        def collect_entities(node: DirectoryNode):
            if node.access:
                # Collect from old format
                users.update(node.access.users)
                groups.update(node.access.groups)
                # Collect from new format
                for entity_access in node.access.entity_access:
                    if entity_access.entity_type == 'user':
                        users.add(entity_access.entity)
                    elif entity_access.entity_type == 'group':
                        groups.add(entity_access.entity)
            for child in node.children:
                collect_entities(child)
        
        collect_entities(self.root)
        
        # Add explicitly defined groups from config
        explicit_groups = self.config.get('groups', {})
        if explicit_groups:
            groups.update(explicit_groups.keys())
            # Also collect users from group members
            for group, group_info in explicit_groups.items():
                members = group_info if isinstance(group_info, list) else group_info.get('members', [])
                users.update(members)
        
        # Add users from user_groups mapping
        user_groups = self.config.get('user_groups', {})
        if user_groups:
            users.update(user_groups.keys())
        
        # Create groups if requested
        if self.config.get('create_groups', True):  # Default to True for backward compatibility
            for group in groups:
                cmd = [str(self.aws_tools_dir / "aws-create-group.sh"), group]
                self._run_command(cmd, f"Creating group: {group}")
                
                # Apply default group policy (list buckets)
                cmd = [
                    str(self.aws_tools_dir / "aws-create-group-policy.sh"),
                    group,
                    self.tenant
                ]
                self._run_command(cmd, f"Applying default policy to group: {group}")
        
        # Create users
        for user in users:
            # Check if user should be created or just used
            if self.config.get('create_users', False):
                cmd = [str(self.aws_tools_dir / "aws-create-user.sh"), user]
                # Set AUTO_CONFIRM for non-interactive mode
                env = os.environ.copy()
                env['AUTO_CONFIRM'] = '1'
                self._run_command(cmd, f"Creating user: {user}", env=env)
    
    def apply_access_policies(self):
        """Apply access policies for all directory nodes"""
        def apply_node_policies(node: DirectoryNode):
            if node.access:
                # Apply policies from old format (legacy)
                for group in node.access.groups:
                    cmd = [
                        str(self.aws_tools_dir / "aws-add-group-bucket-policy.sh"),
                        group,
                        self.bucket_name,
                        node.path.rstrip('/') if node.path else "",
                        self.tenant,
                        node.access.level
                    ]
                    desc = f"Group '{group}' → {node.path or 'bucket root'} ({node.access.level})"
                    self._run_command(cmd, desc)
                
                for user in node.access.users:
                    prefix_arg = node.path.rstrip('/') + '/' if node.path else ""
                    cmd = [
                        str(self.aws_tools_dir / "aws-create-user-policy.sh"),
                        user,
                        self.bucket_name,
                        prefix_arg,
                        f"tenant={self.tenant}"
                    ]
                    desc = f"User '{user}' → {node.path or 'bucket root'} ({node.access.level})"
                    self._run_command(cmd, desc)
                
                # Apply policies from new format (per-entity access levels)
                for entity_access in node.access.entity_access:
                    if entity_access.entity_type == 'group':
                        cmd = [
                            str(self.aws_tools_dir / "aws-add-group-bucket-policy.sh"),
                            entity_access.entity,
                            self.bucket_name,
                            node.path.rstrip('/') if node.path else "",
                            self.tenant,
                            entity_access.level
                        ]
                        desc = f"Group '{entity_access.entity}' → {node.path or 'bucket root'} ({entity_access.level})"
                        self._run_command(cmd, desc)
                    elif entity_access.entity_type == 'user':
                        prefix_arg = node.path.rstrip('/') + '/' if node.path else ""
                        # Note: aws-create-user-policy doesn't support access levels yet
                        # For now, we'll need to use group policies for granular control
                        # or manually adjust this to support user access levels
                        cmd = [
                            str(self.aws_tools_dir / "aws-create-user-policy.sh"),
                            entity_access.entity,
                            self.bucket_name,
                            prefix_arg,
                            f"tenant={self.tenant}"
                        ]
                        desc = f"User '{entity_access.entity}' → {node.path or 'bucket root'} ({entity_access.level})"
                        self._run_command(cmd, desc)
            
            for child in node.children:
                apply_node_policies(child)
        
        apply_node_policies(self.root)
    
    def add_users_to_groups(self):
        """Add users to their respective groups based on config"""
        # Handle user_groups mapping (user -> groups)
        user_groups = self.config.get('user_groups', {})
        
        for user, groups in user_groups.items():
            if isinstance(groups, str):
                groups = [groups]
            
            for group in groups:
                cmd = [
                    str(self.aws_tools_dir / "aws-add-user-to-group.sh"),
                    user,
                    group
                ]
                self._run_command(cmd, f"Adding user '{user}' to group '{group}'")
        
        # Handle groups section (group -> users)
        groups_config = self.config.get('groups', {})
        for group, group_info in groups_config.items():
            members = group_info if isinstance(group_info, list) else group_info.get('members', [])
            
            for user in members:
                cmd = [
                    str(self.aws_tools_dir / "aws-add-user-to-group.sh"),
                    user,
                    group
                ]
                self._run_command(cmd, f"Adding user '{user}' to group '{group}'")
    
    def print_tree(self, node: DirectoryNode = None, prefix: str = "", is_last: bool = True):
        """Print the directory tree structure"""
        if node is None:
            node = self.root
            print(f"\n📦 Bucket: {self.bucket_name}")
            print(f"🔑 Tenant: {self.tenant}")
            print("=" * 60)
        
        connector = "└── " if is_last else "├── "
        if node.name:
            access_info = ""
            if node.access:
                # Display old format
                if node.access.users or node.access.groups:
                    parts = []
                    if node.access.users:
                        parts.append(f"users: {', '.join(node.access.users)}")
                    if node.access.groups:
                        parts.append(f"groups: {', '.join(node.access.groups)}")
                    if parts:
                        access_info = f" [{node.access.level}] ({'; '.join(parts)})"
                
                # Display new format (per-entity access)
                elif node.access.entity_access:
                    entity_strs = []
                    for ea in node.access.entity_access:
                        entity_strs.append(f"{ea.entity}[{ea.level}]")
                    access_info = f" ({'; '.join(entity_strs)})"
            
            print(f"{prefix}{connector}{node.name}/{access_info}")
        
        # Prepare prefix for children
        if node.name:
            extension = "    " if is_last else "│   "
            new_prefix = prefix + extension
        else:
            new_prefix = prefix
        
        for i, child in enumerate(node.children):
            is_last_child = (i == len(node.children) - 1)
            self.print_tree(child, new_prefix, is_last_child)
    
    def build(self):
        """Execute the full build process"""
        print("=" * 60)
        print("🚀 Directory-based S3 IAM Builder")
        print("=" * 60)
        
        if self.dry_run:
            print("⚠️  DRY RUN MODE - No changes will be made")
        
        self.load_config()
        self.print_tree()
        
        print("\n" + "=" * 60)
        print("📋 Execution Plan")
        print("=" * 60)
        
        # Execute build steps
        steps = [
            ("Creating S3 bucket", self.create_bucket),
            ("Creating directory structure", self.create_directories),
            ("Setting up IAM entities", self.setup_iam_entities),
            ("Adding users to groups", self.add_users_to_groups),
            ("Applying access policies", self.apply_access_policies),
        ]
        
        for step_name, step_func in steps:
            print(f"\n{'─' * 60}")
            print(f"📌 {step_name}")
            print('─' * 60)
            try:
                step_func()
            except Exception as e:
                print(f"\n❌ Failed: {e}")
                if not self.dry_run:
                    sys.exit(1)
        
        print("\n" + "=" * 60)
        print("✅ Build complete!")
        print("=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Directory-based S3 IAM management utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview changes
  %(prog)s config.yaml --dry-run
  
  # Apply configuration
  %(prog)s config.yaml
  
  # Use custom tenant
  %(prog)s config.yaml --tenant my_tenant
  
  # Specify aws-tools location
  %(prog)s config.yaml --aws-tools ~/s3/AWS
        """
    )
    
    parser.add_argument('config', help='Path to YAML configuration file')
    parser.add_argument(
        '--aws-tools',
        default=None,
        help='Path to aws-tools directory (default: $AWS_SCRIPTS_DIR or ../aws-tools)'
    )
    parser.add_argument(
        '--tenant',
        help='Ceph tenant name (default: $AWS_DEFAULT_TENANT or sils_mns)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without executing them'
    )
    parser.add_argument(
        '--print-tree',
        action='store_true',
        help='Only print the directory tree and exit'
    )
    
    args = parser.parse_args()
    
    # Resolve aws-tools path with fallback priority:
    # 1. Command line argument (--aws-tools)
    # 2. AWS_SCRIPTS_DIR environment variable
    # 3. Default relative path (../aws-tools)
    if args.aws_tools:
        aws_tools_path = Path(args.aws_tools)
    elif os.environ.get('AWS_SCRIPTS_DIR'):
        aws_tools_path = Path(os.environ['AWS_SCRIPTS_DIR'])
    else:
        aws_tools_path = Path('../aws-tools')
    
    aws_tools_path = aws_tools_path.resolve()
    
    if not aws_tools_path.exists():
        print(f"Error: aws-tools directory not found: {aws_tools_path}")
        print(f"")
        print(f"Tried:")
        if args.aws_tools:
            print(f"  --aws-tools: {args.aws_tools}")
        if os.environ.get('AWS_SCRIPTS_DIR'):
            print(f"  $AWS_SCRIPTS_DIR: {os.environ['AWS_SCRIPTS_DIR']}")
        print(f"  default: ../aws-tools")
        print(f"")
        print(f"Please specify the correct path with --aws-tools or set AWS_SCRIPTS_DIR")
        sys.exit(1)
    
    builder = DirBuilder(
        config_file=args.config,
        aws_tools_dir=str(aws_tools_path),
        tenant=args.tenant,
        dry_run=args.dry_run
    )
    
    if args.print_tree:
        builder.load_config()
        builder.print_tree()
    else:
        builder.build()


if __name__ == '__main__':
    main()
