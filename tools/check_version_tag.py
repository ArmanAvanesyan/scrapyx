#!/usr/bin/env python3
"""
Version consistency checker for scrapyx packages.

This script verifies that all packages in packages/*/pyproject.toml have
the same version as the git tag.
"""

import os
import re
import sys
from pathlib import Path


def get_version_from_pyproject(pyproject_path: Path) -> str | None:
    """Extract version from pyproject.toml file."""
    try:
        content = pyproject_path.read_text()
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
    return None


def get_git_tag_version() -> str | None:
    """Get version from git tag."""
    import subprocess
    
    # Check if running in GitHub Actions
    tag_ref = os.getenv("GITHUB_REF")
    if tag_ref:
        # Extract version from refs/tags/v1.2.3
        match = re.search(r'v?(\d+\.\d+\.\d+)', tag_ref)
        if match:
            return match.group(1)
    
    # Fallback to git command
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True
        )
        tag = result.stdout.strip()
        match = re.search(r'v?(\d+\.\d+\.\d+)', tag)
        if match:
            return match.group(1)
    except Exception:
        pass
    
    return None


def main():
    """Main entry point."""
    tag_version = get_git_tag_version()
    
    if not tag_version:
        print("Warning: Could not determine version from git tag. Skipping version check.", file=sys.stderr)
        return 0
    
    print(f"Checking version consistency against tag: {tag_version}")
    
    repo_root = Path(__file__).parent.parent
    packages_dir = repo_root / "packages"
    
    if not packages_dir.exists():
        print(f"Error: {packages_dir} does not exist", file=sys.stderr)
        return 1
    
    errors = []
    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir():
            continue
        
        pyproject_path = package_dir / "pyproject.toml"
        if not pyproject_path.exists():
            continue
        
        package_version = get_version_from_pyproject(pyproject_path)
        package_name = package_dir.name
        
        if not package_version:
            errors.append(f"{package_name}: Could not read version from pyproject.toml")
        elif package_version != tag_version:
            errors.append(
                f"{package_name}: Version mismatch - "
                f"pyproject.toml has {package_version}, tag has {tag_version}"
            )
        else:
            print(f"✓ {package_name}: {package_version}")
    
    if errors:
        print("\nVersion consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        return 1
    
    print("\n✓ All package versions are consistent with the tag.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

