#!/usr/bin/env python3
"""Validate this repository's skill metadata and local documentation links."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    errors = []
    source = (root / 'SKILL.md').read_text(encoding='utf-8')
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', source, re.DOTALL)
    if not match:
        return ['SKILL.md: missing YAML frontmatter']
    front = yaml.safe_load(match.group(1))
    if not isinstance(front, dict):
        return ['SKILL.md: frontmatter must be a mapping']
    if front.get('name') != 'pdf-mrc-compression':
        errors.append('SKILL.md: unexpected skill name')
    description = front.get('description')
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        errors.append('SKILL.md: description must be a nonempty string of at most 1024 characters')
    if set(front) - {'name', 'description', 'license', 'allowed-tools', 'metadata'}:
        errors.append('SKILL.md: unsupported frontmatter fields')
    metadata = yaml.safe_load((root / 'agents/openai.yaml').read_text(encoding='utf-8'))
    interface = metadata.get('interface', {})
    for key in ('display_name', 'short_description', 'default_prompt'):
        if not isinstance(interface.get(key), str) or not interface[key].strip():
            errors.append(f'agents/openai.yaml: missing {key}')
    if not 25 <= len(interface.get('short_description', '')) <= 64:
        errors.append('agents/openai.yaml: short_description must contain 25–64 characters')
    if '$pdf-mrc-compression' not in interface.get('default_prompt', ''):
        errors.append('agents/openai.yaml: default_prompt must invoke the skill')
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        errors.append('VERSION: expected MAJOR.MINOR.PATCH')
    documents = list(root.glob('*.md')) + list((root / 'references').glob('*.md'))
    for path in documents:
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                errors.append(f'{path.relative_to(root)}: broken or external local link: {target}')
        if re.search(r'/Users/[^\s)]+|/Volumes/[^\n]+', text):
            errors.append(f'{path.relative_to(root)}: personal machine path')
    return errors


def main():
    try:
        errors = validate()
    except (OSError, ValueError, yaml.YAMLError) as error:
        errors = [str(error)]
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Skill metadata, version, and local documentation links are valid.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
