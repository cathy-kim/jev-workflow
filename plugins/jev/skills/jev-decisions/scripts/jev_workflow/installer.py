"""Copy the canonical skill into an explicit skills directory, reversibly.

The installer never chooses a default location, never edits runtime config
(Claude Code, Codex, Hermes or MCP client settings), never starts a server
and never enables a plugin. It prints the runtime's own registration command
as text for the operator to review. Output avoids absolute paths.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from . import VERSION
from .errors import UsageError

SKILL_NAME = 'jev-decisions'
MANIFEST = '.jev-install.json'
MANIFEST_SCHEMA = 'jev.install.v1'
_EXCLUDED_PARTS = {'__pycache__', '.DS_Store'}
LAUNCHER = f'<TARGET>/{SKILL_NAME}/scripts/jev_cli.py'

RUNTIMES = {
    'claude': {
        'suggested_targets': ['<project>/.claude/skills', '~/.claude/skills'],
        'invocation': '/jev-decisions',
        'note': 'Claude Code project/user skill. For the namespaced plugin use the marketplace instead '
                '(/jev:jev-decisions); choose one to avoid duplicates.',
        'mcp': f'claude mcp add --scope project jev-workflow -- python3 {LAUNCHER} mcp-serve',
    },
    'codex': {
        'suggested_targets': ['<repo>/.agents/skills', '~/.agents/skills'],
        'invocation': '$jev-decisions',
        'note': 'Codex scans .agents/skills; restart Codex if the skill does not appear.',
        'mcp': f'codex mcp add jev-workflow -- python3 {LAUNCHER} mcp-serve',
    },
    'hermes': {
        'suggested_targets': ['<project>/.hermes/skills', '$HERMES_HOME/skills/<category>'],
        'invocation': '/jev-decisions',
        'note': 'Project skills need `hermes skills trust` once; use the profile that $HERMES_HOME selects.',
        'mcp': f'hermes mcp add jev-workflow --command python3 --args {LAUNCHER} mcp-serve',
    },
    'generic': {
        'suggested_targets': ['<any skills directory your agent documents>'],
        'invocation': 'load <TARGET>/jev-decisions/SKILL.md by path',
        'note': 'Any skill-capable agent can read SKILL.md with its neighbouring folders.',
        'mcp': f'{{"command": "python3", "args": ["{LAUNCHER}", "mcp-serve"]}}  # any stdio MCP client',
    },
}


def skill_root():
    root = Path(__file__).resolve().parents[2]
    skill = root / 'SKILL.md'
    if not skill.is_file() or not skill.read_text(encoding='utf-8').startswith(f'---\nname: {SKILL_NAME}\n'):
        raise UsageError('installer must run from the canonical skill directory (checkout or extracted bundle)')
    return root


def source_files():
    root = skill_root()
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if set(relative.parts) & _EXCLUDED_PARTS or path.suffix == '.pyc' or \
                any(part.startswith('.') for part in relative.parts):
            continue
        if path.is_symlink():
            raise UsageError('canonical skill contains a symlink; refusing to install')
        if path.is_file():
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_target(target):
    target = Path(target).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    if target.is_symlink():
        raise UsageError('target skills directory is a symlink; pass its real path explicitly')
    if target.exists() and not target.is_dir():
        raise UsageError('target exists and is not a directory')
    resolved = target.resolve()
    root = skill_root()
    if resolved == root or root in resolved.parents or resolved in root.parents:
        raise UsageError('target must not overlap the canonical skill source')
    destination = resolved / SKILL_NAME
    if destination.is_symlink():
        raise UsageError('destination is a symlink; refusing to write through it')
    return resolved, destination


def _read_manifest(destination):
    path = destination / MANIFEST
    if path.is_symlink() or not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get('schema_version') != MANIFEST_SCHEMA \
            or not isinstance(manifest.get('files'), dict):
        return None
    return manifest


def _matches(destination, files):
    for relative, digest in files.items():
        path = destination / relative
        if path.is_symlink() or not path.is_file() or _digest(path) != digest:
            return False
    return True


def _guidance(runtime):
    spec = RUNTIMES[runtime]
    return {
        'invocation': spec['invocation'],
        'runtime_note': spec['note'],
        'suggested_targets': spec['suggested_targets'],
        'mcp_registration_example': spec['mcp'],
        'mcp_registration_note': ('not applied: review and run it yourself if you want the MCP server; it starts '
                                  'offline-only. Live mode needs explicit --enable-live --live-provider '
                                  '--max-live-requests and the provider key passed through your client env.'),
        'rollback': 'jev-workflow uninstall --target <TARGET>',
    }


def install(runtime, target, *, dry_run=False, backup=False):
    if runtime not in RUNTIMES:
        raise UsageError('runtime must be claude, codex, hermes or generic')
    resolved, destination = _check_target(target)
    files = source_files()
    plan = {'schema_version': 'jev.install_result.v1', 'runtime': runtime, 'package_version': VERSION,
            'destination_relative_to_target': SKILL_NAME, 'files': sorted(files), 'dry_run': dry_run,
            'backup_relative_to_target': None}
    plan.update(_guidance(runtime))
    if destination.exists():
        manifest = _read_manifest(destination)
        if manifest and manifest.get('files') == files and _matches(destination, files):
            return dict(plan, action='already_installed')
        if not backup:
            raise UsageError('destination already exists with different content; pass --backup to move it aside')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_path = resolved / f'{SKILL_NAME}.backup-{stamp}'
        if backup_path.exists():
            raise UsageError('backup path already exists; retry later')
        plan['backup_relative_to_target'] = backup_path.name
    plan['action'] = 'install'
    if dry_run:
        return plan
    resolved.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{SKILL_NAME}.tmp-', dir=resolved))
    try:
        root = skill_root()
        for relative in files:
            source = root / relative
            output = staging / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, output)
            if _digest(output) != files[relative]:
                raise UsageError('copy verification failed')
        manifest = {'schema_version': MANIFEST_SCHEMA, 'package_version': VERSION, 'runtime': runtime,
                    'installed_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'backup': plan['backup_relative_to_target'], 'files': files}
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.chmod(staging, 0o755)
        moved_backup = None
        if plan['backup_relative_to_target']:
            moved_backup = resolved / plan['backup_relative_to_target']
            os.replace(destination, moved_backup)
        try:
            os.replace(staging, destination)
        except BaseException:
            if moved_backup is not None and not destination.exists():
                os.replace(moved_backup, destination)  # put the previous install back
            raise
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return plan


def uninstall(target, *, dry_run=False):
    resolved, destination = _check_target(target)
    if not destination.exists():
        raise UsageError('nothing installed at the target')
    manifest = _read_manifest(destination)
    if manifest is None:
        raise UsageError('destination has no jev-workflow install manifest; refusing to remove it')
    files = manifest['files']
    if not _matches(destination, files):
        raise UsageError('installed files were modified; refusing to remove them (resolve manually)')
    expected = set(files) | {MANIFEST}
    present = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file() or p.is_symlink()}
    extra = sorted(p for p in present - expected if '__pycache__' not in p and not p.endswith('.pyc'))
    if extra:
        raise UsageError('destination contains files not created by the installer; refusing to remove them')
    backup = manifest.get('backup')
    backup_path = resolved / backup if isinstance(backup, str) and backup.startswith(f'{SKILL_NAME}.backup-') \
        and '/' not in backup else None
    result = {'schema_version': 'jev.install_result.v1', 'action': 'uninstalled', 'dry_run': dry_run,
              'restored_backup': bool(backup_path and backup_path.is_dir() and not backup_path.is_symlink())}
    if dry_run:
        return result
    shutil.rmtree(destination)
    if result['restored_backup']:
        os.replace(backup_path, destination)
    return result
