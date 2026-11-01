#!/usr/bin/env python3
"""Install the kit without replacing existing project instructions or skills."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

BEGIN = '<!-- codex-harness-kit:begin -->'
END = '<!-- codex-harness-kit:end -->'


def install(target):
    source = Path(__file__).resolve().parent / 'kit'
    target = target.resolve(strict=True)
    if not target.is_dir():
        raise ValueError('설치 대상은 기존 작업 디렉터리여야 합니다.')

    override = target / 'AGENTS.override.md'
    if override.exists() or override.is_symlink():
        raise ValueError('AGENTS.override.md가 있습니다. 실제 적용 지침과 충돌을 직접 확인하세요. 관리 지침을 자동 수정하지 않습니다.')

    def check_path(path):
        current = path
        while current != target:
            if current.is_symlink():
                raise ValueError(f'심볼릭 링크 경로에는 설치하지 않습니다: {current}')
            if current.exists() and current != path and not current.is_dir():
                raise ValueError(f'상위 경로가 디렉터리가 아닙니다: {current}')
            current = current.parent
        if path.exists() and not path.is_file():
            raise ValueError(f'일반 파일이 아닌 대상과 충돌합니다: {path}')

    agents = target / 'AGENTS.md'
    check_path(agents)
    original = agents.read_bytes().decode('utf-8') if agents.exists() else ''
    block = f'{BEGIN}\n{(source / "AGENTS.md").read_text(encoding="utf-8").rstrip()}\n{END}'
    if BEGIN in original or END in original:
        if original.count(BEGIN) != 1 or original.count(END) != 1:
            raise ValueError('기존 하네스 블록이 중복되거나 불완전합니다. 직접 병합하세요.')
        start = original.index(BEGIN)
        finish = original.index(END) + len(END)
        if original[start:finish] != block:
            raise ValueError('기존 하네스 지침이 다릅니다. 변경 내용을 검토해 직접 병합하세요.')
        updated = original
    else:
        if '# AGENTS.md — 작업 운영 규칙' in original:
            raise ValueError('표시 없는 구버전 하네스가 있습니다. 기존 지침을 보존하며 직접 병합하세요.')
        updated = original + ('\n\n' if original else '') + block + '\n'

    copies = []
    for path in sorted((source / '.agents').rglob('*')):
        if not path.is_file():
            continue
        dest = target / path.relative_to(source)
        check_path(dest)
        if dest.exists():
            if dest.read_bytes() != path.read_bytes():
                raise ValueError(f'기존 파일과 내용이 다릅니다. 덮어쓰지 않습니다: {dest}')
        else:
            copies.append((path, dest))

    # Detect all known conflicts before copying any file. A failed I/O returns nonzero;
    # rerunning safely fills missing files without appending a second instructions block.
    for path, dest in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    if updated != original:
        fd, name = tempfile.mkstemp(prefix='.AGENTS.', dir=target)
        temp = Path(name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(updated)
            if agents.exists():
                shutil.copymode(agents, temp)
            temp.replace(agents)
        finally:
            temp.unlink(missing_ok=True)
    print(f'[ok] 설치 확인: {target} (새 파일 {len(copies)}개, 중복 지침 없음)')
    print('Codex를 작업 루트에서 시작해 로딩된 지침·스킬과 기존 규칙의 충돌을 확인하세요.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, help='설치할 작업 공간 루트')
    args = parser.parse_args()
    try:
        install(args.workspace)
    except (OSError, ValueError) as error:
        parser.exit(1, f'[error] {error}\n')


if __name__ == '__main__':
    main()
