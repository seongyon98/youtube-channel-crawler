"""
제외 명단(수동 관리) 대조 모듈

이미 메일을 발송했거나 접촉이 끝난 채널을 다시 수집하지 않도록 막습니다.
기존 중복 방지(processed_ids.json)는 channel_id 하나만 보지만,
수동으로 관리해 온 명단에는 channel_id가 거의 없고 채널명/이메일/핸들만 있는 경우가 많아
4가지 식별자를 모두 대조합니다.

명단 파일: data/excluded_channels.json
  tools/build_exclusion.py 로 생성/갱신합니다.
"""

import json
import os
import unicodedata
from urllib.parse import unquote

DATA_DIR = 'data'
EXCLUSION_FILE = os.path.join(DATA_DIR, 'excluded_channels.json')

# 값이 비어 있음을 뜻하는 표기들 (수동 관리 파일에 흔히 들어옵니다)
EMPTY_VALUES = {'', 'n/a', 'na', '-', 'none', 'null', '없음', '확인필요'}


def _is_empty(value):
    return value is None or str(value).strip().lower() in EMPTY_VALUES


def normalize_channel_id(value):
    """UCxxxx 형태의 채널 ID. 대소문자를 구분하므로 공백만 제거합니다."""
    if _is_empty(value):
        return None
    return str(value).strip()


def normalize_handle(value):
    """@핸들 정규화: 퍼센트 인코딩 해제 → @ 제거 → 소문자

    수동 명단에는 '@%EB%8F%99%ED%85%8C%ED%81%AC' 처럼
    URL 인코딩된 한글 핸들이 그대로 들어 있는 경우가 있어 반드시 디코딩합니다.
    """
    if _is_empty(value):
        return None
    text = unquote(str(value).strip())
    text = text.split('?')[0].rstrip('/')
    if '/' in text:                       # URL 형태로 들어온 경우 마지막 조각만 사용
        text = text.rsplit('/', 1)[-1]
    text = text.lstrip('@').strip().lower()
    return text or None


def normalize_email(value):
    if _is_empty(value):
        return None
    return str(value).strip().lower()


def normalize_title(value):
    """채널명 정규화: 유니코드 정규화 → 공백 전부 제거 → 소문자

    채널명은 완전일치로만 대조합니다. 부분일치를 허용하면
    '고준호' 같은 짧은 이름이 무관한 채널까지 무더기로 막아버립니다.
    """
    if _is_empty(value):
        return None
    text = unicodedata.normalize('NFKC', str(value))
    text = ''.join(text.split()).lower()
    return text or None


def parse_channel_url(value):
    """채널 URL에서 (channel_id, handle) 추출. 못 찾으면 (None, None)"""
    if _is_empty(value):
        return None, None
    url = unquote(str(value).strip()).split('?')[0].rstrip('/')
    if '/channel/' in url:
        return normalize_channel_id(url.rsplit('/channel/', 1)[-1]), None
    if '/@' in url:
        return None, normalize_handle(url.rsplit('/@', 1)[-1])
    if '/c/' in url or '/user/' in url:
        # 예전 형식(/c/, /user/)은 현재 API가 돌려주는 @핸들과 다를 수 있어
        # 참고용으로만 핸들 자리에 넣어 둡니다.
        return None, normalize_handle(url.rsplit('/', 1)[-1])
    return None, None


class ExclusionList:
    """제외 명단. 매칭되면 사유를 돌려주고, 없으면 None을 돌려줍니다."""

    def __init__(self, path=EXCLUSION_FILE, match_title=True):
        self.path = path
        self.match_title = match_title
        # 각 딕셔너리: 정규화된 키 → 명단에 적힌 원래 채널명 (로그 표시용)
        self.channel_ids = {}
        self.handles = {}
        self.emails = {}
        self.titles = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"⚠️  경고: 제외 명단 {self.path} 파일이 손상되었습니다. (무시됨: {e})")
            return
        except Exception as e:
            print(f"⚠️  경고: 제외 명단 로드 실패: {e}")
            return

        entries = data.get('entries', []) if isinstance(data, dict) else data
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            label = entry.get('label') or entry.get('title') or '(이름 없음)'

            cid = normalize_channel_id(entry.get('channel_id'))
            if cid:
                self.channel_ids[cid] = label
            for handle in entry.get('handles', []) or []:
                key = normalize_handle(handle)
                if key:
                    self.handles[key] = label
            for email in entry.get('emails', []) or []:
                key = normalize_email(email)
                if key:
                    self.emails[key] = label
            key = normalize_title(entry.get('title'))
            if key:
                self.titles[key] = label

        if self.total:
            print(
                f"🚫 제외 명단 로드 완료: {len(entries)}건 "
                f"(채널ID {len(self.channel_ids)} / 핸들 {len(self.handles)} / "
                f"이메일 {len(self.emails)} / 채널명 {len(self.titles)})"
            )

    @property
    def total(self):
        return len(self.channel_ids) + len(self.handles) + len(self.emails) + len(self.titles)

    def match_before_details(self, channel_id=None, title=None):
        """상세 조회 전 단계. 검색 결과로 알 수 있는 채널ID/채널명만 대조합니다.

        여기서 걸러내면 channels.list 호출과 AI 검수 비용을 아낄 수 있습니다.
        """
        key = normalize_channel_id(channel_id)
        if key and key in self.channel_ids:
            return '채널ID', self.channel_ids[key]

        if self.match_title:
            key = normalize_title(title)
            if key and key in self.titles:
                return '채널명', self.titles[key]
        return None

    def match_after_details(self, details):
        """상세 조회 후 단계. 핸들과 이메일까지 대조합니다.

        이메일은 채널 설명란에서 뽑아내야 알 수 있으므로 이 단계에서만 확인할 수 있고,
        수동 명단에서 가장 많이 채워져 있는 식별자이기도 합니다.
        """
        found = self.match_before_details(details.get('channel_id'), details.get('title'))
        if found:
            return found

        # 채널 주소 계열 필드를 모두 확인합니다.
        # custom_url 은 '@핸들', channel_url 은 '/channel/UC...', custom_channel_url 은 전체 주소라
        # 형태가 제각각이므로 URL 파서를 거친 뒤 핸들/채널ID 양쪽으로 대조합니다.
        for field in ('custom_url', 'custom_channel_url', 'channel_url'):
            value = details.get(field)
            if _is_empty(value):
                continue

            cid, handle = parse_channel_url(value)
            if cid and cid in self.channel_ids:
                return '채널주소', self.channel_ids[cid]
            if handle and handle in self.handles:
                return '채널주소', self.handles[handle]

            # '@example_channel' 처럼 URL이 아니라 핸들만 들어 있는 경우
            if '/' not in str(value):
                key = normalize_handle(value)
                if key and key in self.handles:
                    return '핸들', self.handles[key]

        key = normalize_email(details.get('email'))
        if key and key in self.emails:
            return '이메일', self.emails[key]
        return None
