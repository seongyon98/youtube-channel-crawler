import re
from src.config import EDU_KEYWORDS, EXCLUDE_KEYWORDS


def has_exclude_keyword(title, description):
    """설명란이나 제목에 명백한 제외 키워드(게임, 먹방 등)가 있는지 확인"""
    text = (title + ' ' + description).lower()
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in text:
            return True
    return False


def is_education_channel(title, description):
    """
    강의/교육 채널인지 판단.
    포함 키워드(EDU_KEYWORDS)가 하나라도 있고,
    제외 키워드(EXCLUDE_KEYWORDS)가 없어야 True 반환.
    """
    text = (title + ' ' + description).lower()

    for keyword in EXCLUDE_KEYWORDS:
        if keyword in text:
            return False

    for keyword in EDU_KEYWORDS:
        if keyword in text:
            return True

    # 키워드가 없으면 제외
    return False


def extract_hashtags(text):
    """텍스트(영상 제목+설명)에서 #해시태그 목록을 등장 순서대로, 중복 제거하여 추출.

    유튜브 시청 화면에 노출되는 해시태그는 영상 제목/설명에 적힌 '#단어'와 동일한 소스이므로,
    별도 메타데이터(태그 필드)가 아니라 이 텍스트에서 직접 뽑는다.
    한글 해시태그(예: #파이썬강의)를 위해 가-힣(완성형)과 ㄱ-ㅎ/ㅏ-ㅣ(자모)까지 포함한다.
    """
    if not text:
        return []
    pattern = re.compile(r'#([\w가-힣ㄱ-ㅎㅏ-ㅣ]+)')
    seen = []
    for tag in pattern.findall(text):
        if tag not in seen:
            seen.append(tag)
    return seen


def is_korean_text(text):
    """한글 포함 여부 확인"""
    if not text:
        return False
    korean_pattern = re.compile('[가-힣]+')
    return bool(korean_pattern.search(text))


def make_safe_filename(query):
    """검색어로부터 안전한 파일명 생성"""
    safe_query = re.sub(r'[<>:"/\\|?*]', '', query)
    safe_query = safe_query.replace(' ', '_')
    safe_query = safe_query[:50]
    return f"youtube_channels_{safe_query}.json"
