"""
제외 명단 생성/갱신 스크립트

메일 발송이 끝난 채널 리스트(.json / .xlsx)를 읽어
data/excluded_channels.json 에 합칩니다. 기존 명단은 지우지 않고 누적합니다.

사용법:
    python tools/build_exclusion.py                          (data/exclusion_sources/ 안의 파일 전부 반영)
    python tools/build_exclusion.py "C:/경로/메일발신_리스트.json"
    python tools/build_exclusion.py 리스트1.json 리스트2.xlsx
    python tools/build_exclusion.py 리스트.json --dry-run    (파일에 쓰지 않고 결과만 확인)

새 발송 리스트는 data/exclusion_sources/ 폴더에 넣어 두세요.
원본을 프로젝트 안에 보관해 두면 다른 PC에서도 명단을 그대로 다시 만들 수 있습니다.

인식하는 열 이름 (대소문자 무시):
    채널ID   : channel_id, 채널id, 채널 id
    채널명   : title, 채널명, 채널 이름
    핸들/URL : custom_url, channel_url, custom_channel_url, 채널url, 채널 주소
    이메일   : email, 이메일, 메일
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exclusion import (  # noqa: E402
    EXCLUSION_FILE,
    normalize_channel_id,
    normalize_email,
    normalize_handle,
    normalize_title,
    parse_channel_url,
    _is_empty,
)

# 발송 리스트 원본을 보관하는 폴더. 인자 없이 실행하면 이 폴더를 통째로 읽습니다.
SOURCES_DIR = os.path.join('data', 'exclusion_sources')
SUPPORTED_EXTS = ('.json', '.xlsx', '.xlsm')

COLUMN_ALIASES = {
    'channel_id': {'channel_id', 'channelid', '채널id', '채널 id'},
    'title': {'title', 'channel_title', '채널명', '채널 이름', '이름'},
    'url': {'custom_url', 'channel_url', 'custom_channel_url', 'url', '채널url', '채널 url', '채널 주소'},
    'email': {'email', 'e-mail', '이메일', '메일', '메일주소'},
}


def _field(row, kind):
    """행에서 해당 종류의 값들을 모두 뽑아냅니다 (열 이름이 여러 개일 수 있음)."""
    values = []
    for key, value in row.items():
        if key is None:
            continue
        if str(key).strip().lower() in COLUMN_ALIASES[kind]:
            if not _is_empty(value):
                values.append(str(value).strip())
    return values


def read_source(path):
    """json 또는 xlsx 파일을 [{열이름: 값}, ...] 형태로 읽어옵니다."""
    ext = os.path.splitext(path)[1].lower()

    if ext == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get('entries') or data.get('channels') or []
        return [row for row in data if isinstance(row, dict)]

    if ext in ('.xlsx', '.xlsm'):
        try:
            import openpyxl
        except ImportError:
            print("✗ .xlsx 를 읽으려면 openpyxl 이 필요합니다:  pip install openpyxl")
            return []
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            header = [str(c).strip() if c is not None else None for c in next(rows)]
        except StopIteration:
            return []
        return [dict(zip(header, row)) for row in rows]

    print(f"✗ 지원하지 않는 형식입니다: {path}  (.json 또는 .xlsx 만 가능)")
    return []


def build_entry(row, source_name):
    """한 행을 제외 명단 항목으로 변환합니다."""
    channel_ids, handles, emails = [], [], []

    for value in _field(row, 'channel_id'):
        cid = normalize_channel_id(value)
        if cid:
            channel_ids.append(cid)

    for value in _field(row, 'url'):
        cid, handle = parse_channel_url(value)
        if cid:
            channel_ids.append(cid)
        if handle:
            handles.append(handle)
        elif '/' not in value:
            # '@example_channel' 처럼 URL이 아니라 핸들만 들어 있는 경우
            handle = normalize_handle(value)
            if handle:
                handles.append(handle)

    for value in _field(row, 'email'):
        # 한 칸에 여러 메일이 들어 있는 경우까지 분리
        for piece in str(value).replace(';', ',').replace('|', ',').split(','):
            email = normalize_email(piece)
            if email and '@' in email:
                emails.append(email)

    titles = _field(row, 'title')
    title = titles[0] if titles else None

    if not (channel_ids or handles or emails or normalize_title(title)):
        return None

    candidates = [title] + emails + handles + channel_ids
    label = next((c for c in candidates if c), '(이름 없음)')
    return {
        'label': label,
        'title': title,
        'channel_id': channel_ids[0] if channel_ids else None,
        'handles': sorted(set(handles)),
        'emails': sorted(set(emails)),
        'source': source_name,
    }


def entry_keys(entry):
    """중복 판정에 쓸 키들 (하나라도 겹치면 같은 채널로 봅니다)."""
    keys = set()
    if entry.get('channel_id'):
        keys.add(('id', entry['channel_id']))
    for handle in entry.get('handles', []):
        keys.add(('handle', normalize_handle(handle)))
    for email in entry.get('emails', []):
        keys.add(('email', normalize_email(email)))
    title = normalize_title(entry.get('title'))
    if title:
        keys.add(('title', title))
    return keys


def merge(existing, incoming):
    """기존 명단에 새 항목을 합칩니다. 식별자가 겹치면 한 항목으로 묶습니다."""
    merged = list(existing)
    index = {}
    for i, entry in enumerate(merged):
        for key in entry_keys(entry):
            index.setdefault(key, i)

    added = updated = 0
    for entry in incoming:
        hit = next((index[k] for k in entry_keys(entry) if k in index), None)
        if hit is None:
            merged.append(entry)
            for key in entry_keys(entry):
                index.setdefault(key, len(merged) - 1)
            added += 1
        else:
            target = merged[hit]
            before = json.dumps(target, ensure_ascii=False, sort_keys=True)
            target['channel_id'] = target.get('channel_id') or entry.get('channel_id')
            target['title'] = target.get('title') or entry.get('title')
            target['handles'] = sorted(set(target.get('handles', []) + entry.get('handles', [])))
            target['emails'] = sorted(set(target.get('emails', []) + entry.get('emails', [])))
            if json.dumps(target, ensure_ascii=False, sort_keys=True) != before:
                updated += 1
            for key in entry_keys(target):
                index.setdefault(key, hit)
    return merged, added, updated


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry_run = '--dry-run' in sys.argv

    if not args:
        # 인자를 주지 않으면 보관 폴더 안의 리스트를 전부 반영합니다.
        if not os.path.isdir(SOURCES_DIR):
            print(__doc__)
            print(f"✗ 원본 보관 폴더가 없습니다: {SOURCES_DIR}")
            return 1
        args = sorted(
            os.path.join(SOURCES_DIR, f)
            for f in os.listdir(SOURCES_DIR)
            if f.lower().endswith(SUPPORTED_EXTS) and not f.startswith('~$')
        )
        if not args:
            print(f"✗ {SOURCES_DIR} 폴더가 비어 있습니다. 발송 리스트(.json/.xlsx)를 넣어 주세요.")
            return 1
        print(f"📁 원본 보관 폴더에서 {len(args)}개 파일을 읽습니다: {SOURCES_DIR}")

    existing = []
    if os.path.exists(EXCLUSION_FILE):
        with open(EXCLUSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        existing = data.get('entries', []) if isinstance(data, dict) else data
        print(f"📂 기존 제외 명단: {len(existing)}건")

    incoming = []
    for path in args:
        if not os.path.exists(path):
            print(f"✗ 파일을 찾을 수 없습니다: {path}")
            continue
        source_name = os.path.splitext(os.path.basename(path))[0]
        rows = read_source(path)
        entries = [e for e in (build_entry(row, source_name) for row in rows) if e]
        skipped = len(rows) - len(entries)
        message = f"📄 {os.path.basename(path)} → {len(rows)}행 중 {len(entries)}건 인식"
        if skipped:
            message += f" (식별자 없어 제외: {skipped}건)"
        print(message)
        incoming.extend(entries)

    if not incoming:
        print("✗ 추가할 항목이 없습니다.")
        return 1

    merged, added, updated = merge(existing, incoming)

    stats = {
        'channel_id': sum(1 for e in merged if e.get('channel_id')),
        'handles': sum(1 for e in merged if e.get('handles')),
        'emails': sum(1 for e in merged if e.get('emails')),
        'titles': sum(1 for e in merged if normalize_title(e.get('title'))),
    }

    print()
    print(f"➕ 신규 추가: {added}건 / 기존 항목 정보 보강: {updated}건")
    print(f"📊 최종 명단: {len(merged)}건 "
          f"(채널ID {stats['channel_id']} / 핸들 {stats['handles']} / "
          f"이메일 {stats['emails']} / 채널명 {stats['titles']})")

    if dry_run:
        print("\n(--dry-run 이므로 파일에 쓰지 않았습니다)")
        return 0

    payload = {
        '_설명': '크롤링에서 영구 제외할 채널 명단. tools/build_exclusion.py 로 갱신합니다.',
        '_갱신일': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'entries': merged,
    }
    os.makedirs(os.path.dirname(EXCLUSION_FILE), exist_ok=True)
    with open(EXCLUSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 저장 완료: {EXCLUSION_FILE}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
