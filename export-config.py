#!/usr/bin/env python3
"""
Export existing IAM access (users/groups inline policies) into a dir-builder YAML config.

- Discovers inline group and user policies and reconstructs bucket/prefix access
- Supports exporting one bucket, a subtree (prefix), or all buckets (per-bucket files)
- infers access levels: full/write/read from policy actions

Notes/Assumptions (aligned with aws-tools):
- Group bucket/prefix policies were created as inline group policies with names like:
  s3-<bucket>-<prefix_clean> and include Resources:
    - arn:aws:s3::<tenant>:<bucket>
    - arn:aws:s3::<tenant>:<bucket>/<prefix>*
- User policies created by aws-create-user-policy are inline user policies with
  Resources of the same form; user policies grant full object access to prefixes

This script reads IAM (not bucket policies) and builds a config that dir-builder can apply.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
import subprocess

ARN_RE = re.compile(r"^arn:aws:s3::(?P<tenant>[^:]*):(?P<bucket>[^/]*)(?:/(?P<prefix>.*))?$")


@dataclass
class EntityAccess:
    entity: str
    entity_type: str  # 'user' | 'group'
    level: str        # 'read' | 'write' | 'full'


@dataclass
class Node:
    name: str
    children: Dict[str, 'Node'] = field(default_factory=dict)
    access: List[EntityAccess] = field(default_factory=list)

    def ensure_child(self, name: str) -> 'Node':
        if name not in self.children:
            self.children[name] = Node(name)
        return self.children[name]


def run_aws(cmd: List[str], profile: Optional[str]) -> dict:
    env = os.environ.copy()
    if profile:
        env['AWS_PROFILE'] = profile
    # never page
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"AWS command failed: {' '.join(cmd)}\n{res.stderr.strip() or res.stdout.strip()}")
    out = res.stdout.strip()
    return json.loads(out) if out else {}


def compute_level_from_actions(actions: List[str]) -> str:
    # Normalize
    acts = set(a.lower() for a in actions)
    if any(a in acts for a in ["s3:*", "s3:*"]):
        return 'full'
    has_put = 's3:putobject' in acts
    has_del = 's3:deleteobject' in acts
    # ListBucket indicates read scope
    has_get = 's3:getobject' in acts
    if has_put or has_del:
        return 'write'
    if has_get:
        return 'read'
    # Fallback: treat as read if ListBucket only, else full
    return 'read'


def parse_policy_resources(policy_doc: dict) -> List[Tuple[str, Optional[str]]]:
    """Return list of (bucket, prefix_or_None) from Resource entries.
    Prefix may contain trailing '/*' or '*'; return clean folder path (with trailing '/'), or None for bucket-wide.
    """
    resources = []
    statements = policy_doc.get('Statement', [])
    if isinstance(statements, dict):
        statements = [statements]
    for st in statements:
        res = st.get('Resource')
        if not res:
            continue
        if isinstance(res, str):
            res_list = [res]
        else:
            res_list = res
        for r in res_list:
            m = ARN_RE.match(r)
            if not m:
                continue
            bucket = m.group('bucket')
            prefix = m.group('prefix')
            if prefix is None:
                resources.append((bucket, None))
                continue
            # remove trailing *
            prefix = prefix.rstrip('*')
            # ensure trailing '/'
            if prefix and not prefix.endswith('/'):
                prefix += '/'
            resources.append((bucket, prefix or None))
    return resources


def get_inline_group_policies(profile: Optional[str]) -> Dict[str, List[Tuple[str, Optional[str], str]]]:
    """Return mapping: group -> list of (bucket, prefix, level) from inline group policies."""
    result: Dict[str, List[Tuple[str, Optional[str], str]]] = defaultdict(list)
    groups = run_aws(["aws", "iam", "list-groups"], profile).get('Groups', [])
    for g in groups:
        gname = g['GroupName']
        pols = run_aws(["aws", "iam", "list-group-policies", "--group-name", gname], profile).get('PolicyNames', [])
        for pname in pols:
            pd = run_aws(["aws", "iam", "get-group-policy", "--group-name", gname, "--policy-name", pname], profile)
            doc = pd.get('PolicyDocument')
            if not doc:
                continue
            # Determine level from actions in the statement
            statements = doc.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            actions: List[str] = []
            for st in statements:
                act = st.get('Action')
                if not act:
                    continue
                if isinstance(act, list):
                    actions.extend(act)
                else:
                    actions.append(act)
            level = compute_level_from_actions(actions)
            for bucket, prefix in parse_policy_resources(doc):
                # Skip wildcard and empty buckets (default list policies)
                if not bucket or bucket == '*' or bucket == '':
                    continue
                result[gname].append((bucket, prefix, level))
    return result


def get_managed_group_policies(profile: Optional[str]) -> Dict[str, List[Tuple[str, Optional[str], str]]]:
    """Return mapping: group -> list of (bucket, prefix, level) from managed policies attached to groups."""
    result: Dict[str, List[Tuple[str, Optional[str], str]]] = defaultdict(list)
    groups = run_aws(["aws", "iam", "list-groups"], profile).get('Groups', [])
    for g in groups:
        gname = g['GroupName']
        attached = run_aws(["aws", "iam", "list-attached-group-policies", "--group-name", gname], profile).get('AttachedPolicies', [])
        for pol in attached:
            pol_arn = pol['PolicyArn']
            # Get policy default version
            pol_info = run_aws(["aws", "iam", "get-policy", "--policy-arn", pol_arn], profile).get('Policy', {})
            default_version = pol_info.get('DefaultVersionId')
            if not default_version:
                continue
            pol_version = run_aws(["aws", "iam", "get-policy-version", "--policy-arn", pol_arn, "--version-id", default_version], profile)
            doc = pol_version.get('PolicyVersion', {}).get('Document')
            if not doc:
                continue
            statements = doc.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            actions: List[str] = []
            for st in statements:
                act = st.get('Action')
                if not act:
                    continue
                if isinstance(act, list):
                    actions.extend(act)
                else:
                    actions.append(act)
            level = compute_level_from_actions(actions)
            for bucket, prefix in parse_policy_resources(doc):
                if not bucket or bucket == '*' or bucket == '':
                    continue
                result[gname].append((bucket, prefix, level))
    return result


def get_inline_user_policies(profile: Optional[str]) -> Dict[str, List[Tuple[str, Optional[str], str]]]:
    """Return mapping: user -> list of (bucket, prefix, level) from inline user policies."""
    result: Dict[str, List[Tuple[str, Optional[str], str]]] = defaultdict(list)
    users = run_aws(["aws", "iam", "list-users"], profile).get('Users', [])
    for u in users:
        uname = u['UserName']
        pols = run_aws(["aws", "iam", "list-user-policies", "--user-name", uname], profile).get('PolicyNames', [])
        for pname in pols:
            pd = run_aws(["aws", "iam", "get-user-policy", "--user-name", uname, "--policy-name", pname], profile)
            doc = pd.get('PolicyDocument')
            if not doc:
                continue
            # For user policies created by our tool, actions include Get/Put/Delete => treat as write/full
            statements = doc.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            actions: List[str] = []
            for st in statements:
                act = st.get('Action')
                if not act:
                    continue
                if isinstance(act, list):
                    actions.extend(act)
                else:
                    actions.append(act)
            level = compute_level_from_actions(actions)
            for bucket, prefix in parse_policy_resources(doc):
                # Skip wildcard and empty buckets (default list policies)
                if not bucket or bucket == '*' or bucket == '':
                    continue
                result[uname].append((bucket, prefix, level))
    return result


def get_managed_user_policies(profile: Optional[str]) -> Dict[str, List[Tuple[str, Optional[str], str]]]:
    """Return mapping: user -> list of (bucket, prefix, level) from managed policies attached to users."""
    result: Dict[str, List[Tuple[str, Optional[str], str]]] = defaultdict(list)
    users = run_aws(["aws", "iam", "list-users"], profile).get('Users', [])
    for u in users:
        uname = u['UserName']
        attached = run_aws(["aws", "iam", "list-attached-user-policies", "--user-name", uname], profile).get('AttachedPolicies', [])
        for pol in attached:
            pol_arn = pol['PolicyArn']
            pol_info = run_aws(["aws", "iam", "get-policy", "--policy-arn", pol_arn], profile).get('Policy', {})
            default_version = pol_info.get('DefaultVersionId')
            if not default_version:
                continue
            pol_version = run_aws(["aws", "iam", "get-policy-version", "--policy-arn", pol_arn, "--version-id", default_version], profile)
            doc = pol_version.get('PolicyVersion', {}).get('Document')
            if not doc:
                continue
            statements = doc.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            actions: List[str] = []
            for st in statements:
                act = st.get('Action')
                if not act:
                    continue
                if isinstance(act, list):
                    actions.extend(act)
                else:
                    actions.append(act)
            level = compute_level_from_actions(actions)
            for bucket, prefix in parse_policy_resources(doc):
                if not bucket or bucket == '*' or bucket == '':
                    continue
                result[uname].append((bucket, prefix, level))
    return result


def get_bucket_policies(profile: Optional[str]) -> Dict[str, List[Tuple[str, str, Optional[str], str]]]:
    """Return mapping: bucket -> list of (entity, entity_type, prefix, level) from bucket policies.
    entity_type can be 'user', 'group', or 'principal'
    """
    result: Dict[str, List[Tuple[str, str, Optional[str], str]]] = defaultdict(list)
    # List all buckets
    try:
        buckets_result = run_aws(["aws", "s3api", "list-buckets"], profile)
        buckets = buckets_result.get('Buckets', [])
    except:
        # If list-buckets fails, return empty
        return result
    
    for bucket_info in buckets:
        bucket = bucket_info['Name']
        try:
            policy_result = run_aws(["aws", "s3api", "get-bucket-policy", "--bucket", bucket], profile)
            policy_str = policy_result.get('Policy', '')
            if not policy_str:
                continue
            doc = json.loads(policy_str)
            statements = doc.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            
            for st in statements:
                # Get actions to determine level
                act = st.get('Action')
                if not act:
                    continue
                actions = act if isinstance(act, list) else [act]
                level = compute_level_from_actions(actions)
                
                # Extract principals
                principal = st.get('Principal')
                if not principal:
                    continue
                
                # Handle different principal formats
                principals = []
                if isinstance(principal, str):
                    if principal == '*':
                        principals.append(('*', 'principal'))
                elif isinstance(principal, dict):
                    # AWS format: {"AWS": ["arn:aws:iam::account:user/name", ...]}
                    for key, value in principal.items():
                        if key == 'AWS':
                            aws_principals = value if isinstance(value, list) else [value]
                            for arn in aws_principals:
                                if isinstance(arn, str):
                                    # Parse ARN to extract user/group name
                                    if ':user/' in arn:
                                        entity_name = arn.split(':user/')[-1]
                                        principals.append((entity_name, 'user'))
                                    elif ':group/' in arn:
                                        entity_name = arn.split(':group/')[-1]
                                        principals.append((entity_name, 'group'))
                                    else:
                                        principals.append((arn, 'principal'))
                
                # Extract resources to get prefixes
                resources_list = parse_policy_resources(doc)
                for res_bucket, prefix in resources_list:
                    if res_bucket == bucket:
                        for entity_name, entity_type in principals:
                            result[bucket].append((entity_name, entity_type, prefix, level))
        except RuntimeError:
            # No bucket policy or access denied
            continue
    
    return result


def get_s3_directory_structure(bucket: str, profile: Optional[str]) -> List[str]:
    """Discover directory (prefix) structure in an S3 bucket.
    Returns list of prefixes (directory paths ending with /).
    """
    prefixes = set()
    try:
        # List objects with delimiter to get common prefixes (directories)
        result = run_aws(["aws", "s3api", "list-objects-v2", "--bucket", bucket, "--delimiter", "/"], profile)
        
        # Get top-level directories
        for prefix_obj in result.get('CommonPrefixes', []):
            prefix = prefix_obj.get('Prefix', '')
            if prefix:
                prefixes.add(prefix)
                # Recursively get subdirectories
                prefixes.update(_list_subdirectories(bucket, prefix, profile))
    except RuntimeError:
        # Bucket doesn't exist or access denied
        pass
    
    return sorted(prefixes)


def _list_subdirectories(bucket: str, prefix: str, profile: Optional[str]) -> set:
    """Recursively list subdirectories under a prefix."""
    subdirs = set()
    try:
        result = run_aws(["aws", "s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix, "--delimiter", "/"], profile)
        for prefix_obj in result.get('CommonPrefixes', []):
            subdir = prefix_obj.get('Prefix', '')
            if subdir:
                subdirs.add(subdir)
                # Recurse deeper
                subdirs.update(_list_subdirectories(bucket, subdir, profile))
    except RuntimeError:
        pass
    return subdirs


def get_group_members(profile: Optional[str]) -> Dict[str, List[str]]:
    members: Dict[str, List[str]] = defaultdict(list)
    groups = run_aws(["aws", "iam", "list-groups"], profile).get('Groups', [])
    for g in groups:
        gname = g['GroupName']
        # get-group returns users
        resp = run_aws(["aws", "iam", "get-group", "--group-name", gname], profile)
        for u in resp.get('Users', []):
            members[gname].append(u['UserName'])
    return members


def build_tree_from_access(access_map: Dict[str, Dict[str, List[EntityAccess]]]) -> Dict[str, Node]:
    """Return per-bucket root Node trees from access map where map[bucket][prefix] = [EntityAccess].
    prefix may be None (bucket-wide) or 'path/like/'.
    """
    trees: Dict[str, Node] = {}
    for bucket, pref_map in access_map.items():
        root = trees.setdefault(bucket, Node(name=""))
        for prefix, entities in pref_map.items():
            if not prefix or prefix == '/':
                # Attach to root (bucket root access)
                root.access.extend(entities)
                continue
            # Walk/create nodes for each segment
            parts = [p for p in prefix.split('/') if p]
            node = root
            for part in parts:
                node = node.ensure_child(part)
            node.access.extend(entities)
    return trees


def generate_config_for_bucket(bucket: str,
                               tree: Node,
                               groups_members: Dict[str, List[str]],
                               tenant: Optional[str]) -> dict:
    def node_to_yaml(n: Node) -> dict:
        entry: Dict[str, object] = {
            'name': n.name,
        }
        # New flexible access format
        if n.access:
            entry['access'] = [
                {
                    'entity': ea.entity,
                    'type': ea.entity_type,
                    'level': ea.level,
                }
                for ea in n.access
            ]
        if n.children:
            entry['children'] = [node_to_yaml(c) for c in n.children.values()]
        return entry

    cfg: Dict[str, object] = {
        'bucket': bucket,
        'create_bucket': False,
        'create_directories': True,
        'create_users': False,
        'create_groups': True,
    }
    if tenant:
        cfg['tenant'] = tenant

    # groups section from group memberships
    if groups_members:
        cfg['groups'] = {g: sorted(members) for g, members in groups_members.items() if members}

    cfg['directories'] = {
        'name': '',
        'children': [node_to_yaml(c) for c in tree.children.values()],
    }
    # Attach any root access to root node
    if tree.access:
        cfg['directories']['access'] = [
            {
                'entity': ea.entity,
                'type': ea.entity_type,
                'level': ea.level,
            }
            for ea in tree.access
        ]
    return cfg


def main():
    p = argparse.ArgumentParser(description="Export IAM inline policies to dir-builder YAML config")
    p.add_argument('--bucket', help='Limit export to a single bucket')
    p.add_argument('--prefix', help='Limit export to a specific prefix (requires --bucket)')
    p.add_argument('--output', '-o', help='Output file (for single bucket) or directory (for all buckets). Default: stdout for single bucket.')
    p.add_argument('--profile', help='AWS profile to use for IAM reads (default: current)')
    p.add_argument('--tenant', help='Override tenant to place in output (optional)')
    args = p.parse_args()

    # Discover access from IAM
    try:
        print("Reading inline group policies...", file=sys.stderr)
        group_pols = get_inline_group_policies(args.profile)
        print("Reading managed group policies...", file=sys.stderr)
        managed_group_pols = get_managed_group_policies(args.profile)
        print("Reading inline user policies...", file=sys.stderr)
        user_pols = get_inline_user_policies(args.profile)
        print("Reading managed user policies...", file=sys.stderr)
        managed_user_pols = get_managed_user_policies(args.profile)
        print("Reading bucket policies...", file=sys.stderr)
        bucket_pols = get_bucket_policies(args.profile)
        print("Reading group memberships...", file=sys.stderr)
        group_members = get_group_members(args.profile)
        print("Listing all buckets...", file=sys.stderr)
        all_buckets_result = run_aws(["aws", "s3api", "list-buckets"], args.profile)
        all_buckets = [b['Name'] for b in all_buckets_result.get('Buckets', [])]
    except Exception as e:
        print(f"Error while reading IAM: {e}", file=sys.stderr)
        sys.exit(1)

    # Build unified access map: bucket -> prefix -> [EntityAccess]
    access_map: Dict[str, Dict[str, List[EntityAccess]]] = defaultdict(lambda: defaultdict(list))

    # Inline group policies
    for g, entries in group_pols.items():
        for bucket, prefix, level in entries:
            if args.bucket and bucket != args.bucket:
                continue
            if args.prefix and prefix and not prefix.startswith(args.prefix.rstrip('/') + '/'):
                continue
            access_map[bucket][prefix or ''].append(EntityAccess(entity=g, entity_type='group', level=level))

    # Managed group policies
    for g, entries in managed_group_pols.items():
        for bucket, prefix, level in entries:
            if args.bucket and bucket != args.bucket:
                continue
            if args.prefix and prefix and not prefix.startswith(args.prefix.rstrip('/') + '/'):
                continue
            access_map[bucket][prefix or ''].append(EntityAccess(entity=g, entity_type='group', level=level))

    # Inline user policies
    for u, entries in user_pols.items():
        for bucket, prefix, level in entries:
            if args.bucket and bucket != args.bucket:
                continue
            if args.prefix and prefix and not prefix.startswith(args.prefix.rstrip('/') + '/'):
                continue
            access_map[bucket][prefix or ''].append(EntityAccess(entity=u, entity_type='user', level=level))

    # Managed user policies
    for u, entries in managed_user_pols.items():
        for bucket, prefix, level in entries:
            if args.bucket and bucket != args.bucket:
                continue
            if args.prefix and prefix and not prefix.startswith(args.prefix.rstrip('/') + '/'):
                continue
            access_map[bucket][prefix or ''].append(EntityAccess(entity=u, entity_type='user', level=level))

    # Bucket policies
    for bucket, entries in bucket_pols.items():
        if args.bucket and bucket != args.bucket:
            continue
        for entity, entity_type, prefix, level in entries:
            if args.prefix and prefix and not prefix.startswith(args.prefix.rstrip('/') + '/'):
                continue
            access_map[bucket][prefix or ''].append(EntityAccess(entity=entity, entity_type=entity_type, level=level))

    # Ensure all buckets are in the access_map (even if they have no policies)
    # This allows generating template configs for all buckets
    if args.bucket:
        # Single bucket mode: ensure the requested bucket is included
        if args.bucket not in access_map:
            access_map[args.bucket] = defaultdict(list)
    else:
        # All buckets mode: include every bucket
        for bucket in all_buckets:
            if bucket not in access_map:
                access_map[bucket] = defaultdict(list)

    # Discover S3 directory structure for buckets without policies
    # This populates the tree with actual directories from S3
    print("Discovering S3 directory structures...", file=sys.stderr)
    for bucket in access_map.keys():
        # Only discover structure if there are no prefix-specific policies
        if not any(prefix for prefix in access_map[bucket].keys() if prefix):
            # No prefixes in policies, discover from S3
            prefixes = get_s3_directory_structure(bucket, args.profile)
            for prefix in prefixes:
                # Add empty access list for each discovered prefix
                if prefix not in access_map[bucket]:
                    access_map[bucket][prefix] = []

    # Build trees
    trees = {bucket: tree for bucket, tree in ((b, build_tree_from_access({b: pref_map})[b]) for b, pref_map in access_map.items())}

    # Output
    output_path = Path(args.output) if args.output else None

    if args.bucket:
        tree = trees.get(args.bucket, Node(name=''))
        cfg = generate_config_for_bucket(args.bucket, tree, group_members, args.tenant)
        data = yaml.safe_dump(cfg, sort_keys=False)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(data)
            print(f"Wrote {output_path}")
        else:
            sys.stdout.write(data)
    else:
        # Multiple buckets: write per-bucket files
        if not output_path:
            print("When exporting all buckets, please specify --output <directory>", file=sys.stderr)
            sys.exit(2)
        output_path.mkdir(parents=True, exist_ok=True)
        for bucket, tree in trees.items():
            cfg = generate_config_for_bucket(bucket, tree, group_members, args.tenant)
            data = yaml.safe_dump(cfg, sort_keys=False)
            target = output_path / f"export-{bucket}.yaml"
            target.write_text(data)
            print(f"Wrote {target}")


if __name__ == '__main__':
    main()
