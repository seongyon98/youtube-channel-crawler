import re


def extract_contact_info(text):
    """채널 설명에서 연락처 정보 추출"""
    if not text:
        return {'email': '', 'phone': '', 'kakao': '', 'other_links': []}

    contact_info = {'email': '', 'phone': '', 'kakao': '', 'other_links': []}

    # 이메일
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if emails:
        contact_info['email'] = emails[0]

    # 전화번호 (개인 휴대폰 번호만)
    phone_patterns = [
        r'010[-\s]?\d{4}[-\s]?\d{4}',
        r'\+82[-\s]?10[-\s]?\d{4}[-\s]?\d{4}'
    ]
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        if matches:
            contact_info['phone'] = matches[0]
            break

    # 카카오톡 ID
    kakao_patterns = [
        r'카카오[톡]?[:\s]+([a-zA-Z0-9_-]+)',
        r'kakao[talk]?[:\s]+([a-zA-Z0-9_-]+)',
    ]
    for pattern in kakao_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            contact_info['kakao'] = matches[0]
            break

    # 기타 연락 링크 (유튜브·소셜미디어 제외)
    urls = re.findall(r'https?://[^\s<>"\)]+|www\.[^\s<>"\)]+', text)
    exclude_domains = ['youtube.com', 'youtu.be', 'instagram.com', 'twitter.com', 'facebook.com', 'x.com']
    contact_urls = [u for u in urls if not any(d in u.lower() for d in exclude_domains)]
    contact_info['other_links'] = contact_urls[:3]

    return contact_info
