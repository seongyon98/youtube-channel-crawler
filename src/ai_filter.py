import os
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from src.config import OPENAI_MODEL

# OpenAI API 연속 오류 감지용 카운터
_consecutive_openai_failures = 0
# 자막 조회가 '자막 없음' 이외의 이유로 실패하면 첫 1회만 알립니다.
# (라이브러리 버전이 바뀌어 자막을 전혀 못 가져오는데도 조용히 넘어가 몇 달간 몰랐던 적이 있음)
_transcript_error_reported = False

def get_video_transcript(video_id):
    """
    유튜브 영상의 한글 또는 영어 자동 생성/수동 자막을 가져옵니다.
    """
    global _transcript_error_reported
    if not video_id:
        return None
    try:
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            # youtube-transcript-api 0.x
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
            text = " ".join([item['text'] for item in transcript])
        else:
            # youtube-transcript-api 1.x: get_transcript가 없어지고 인스턴스의 fetch()를 씁니다
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=['ko', 'en'])
            text = " ".join(snippet.text for snippet in fetched)
        # 앞부분 1500자만 추출 (강의 스타일 파악에 충분하며 토큰 비용 절약)
        return text[:1500]
    except (NoTranscriptFound, TranscriptsDisabled):
        # 자막이 없는 영상은 흔하므로 조용히 썸네일 판단으로 넘어갑니다
        return None
    except Exception as e:
        if not _transcript_error_reported:
            first_line = (str(e).strip().splitlines() or [''])[0][:200]
            print(f"  ⚠️ 자막 조회 오류 - 썸네일로 대신 판단합니다 (같은 오류는 더 표시하지 않음): {type(e).__name__}: {first_line}")
            _transcript_error_reported = True
        return None

def review_channel_with_ai(channel_title, description, video_id, video_title, video_thumbnail_url, search_keyword, hashtags=None):
    """
    OpenAI API를 사용하여 교육/정보성 채널인지 판별합니다.
    검색어 관련성은 판단하지 않습니다 (사람이 2차 검수·컨택 단계에서 판단).
    search_keyword는 호출부 호환을 위해 인자로만 남겨 둡니다.
    hashtags: 검색된 영상의 제목+설명에서 추출한 해시태그 목록 (없으면 빈 리스트/None).
    """
    import os
    import time
    
    time.sleep(1.5) # API 속도 제한(TPM) 방지를 위한 기본 지연

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return True # API 키가 없으면 기본적으로 통과시킴

    client = OpenAI(api_key=api_key)
    
    transcript_text = get_video_transcript(video_id)

    # 해시태그가 없으면 '없음'으로 표기해 AI가 빈 문자열과 혼동하지 않도록 함
    hashtags = hashtags or []
    hashtags_str = ' '.join(f'#{tag}' for tag in hashtags) if hashtags else '(없음)'
    
    if transcript_text:
        # 자막이 있는 경우: 자막 기반 텍스트 분석
        prompt = f"""You are an expert YouTube channel analyst. Evaluate the following channel based on its title, description, latest video title, video hashtags, and video transcript snippet.
Objective: Determine if this channel primarily produces 'Educational, Informational, or Tech/Business Review' content made by an individual or small team creator. Do NOT judge whether it matches any particular search keyword; a human reviewer checks relevance later.

- CRITICAL FINANCE RULE: REJECT (Answer NO) any channels focused on stock/crypto trading or real-estate speculation.
- CORPORATE CHANNEL RULE: REJECT (Answer NO) any official brand/corporate channels — e.g. channels run by companies, government agencies, broadcasters, or institutions for PR/marketing purposes. These are NOT individual creator channels.
- ACCEPTABLE (Answer YES): Individual or small-team creators producing professional lectures, coding/tech tutorials, informative tech/business news, or expert knowledge sharing.
- UNACCEPTABLE (Answer NO): Corporate/brand official channels, low-effort AI TTS (Text-to-Speech) spam, generic gameplay/streaming, purely personal vlogs, mukbang, clickbait gossip.
- Use the hashtags as one more clue alongside the other fields, not as the sole basis for your decision.

Respond ONLY with YES or NO.

[Channel Title]: {channel_title}
[Channel Description]: {description}
[Latest Video Title]: {video_title}
[Video Hashtags]: {hashtags_str}
[Transcript Snippet]: {transcript_text}
"""
        messages = [
            {"role": "system", "content": "Respond ONLY with YES or NO."},
            {"role": "user", "content": prompt}
        ]
    else:
        # 자막이 없는 경우: 썸네일 이미지를 포함한 비전(Vision) 분석 Fallback
        prompt_text = f"""You are an expert YouTube channel analyst. Evaluate this channel based on its title, description, latest video title, video hashtags, and the provided video thumbnail (since there is no transcript).
Objective: Determine if this channel primarily produces 'Educational, Informational, or Tech/Business Review' content made by an individual or small team creator. Do NOT judge whether it matches any particular search keyword; a human reviewer checks relevance later.

- CRITICAL FINANCE RULE: REJECT (Answer NO) any channels focused on stock/crypto trading or real-estate speculation.
- CORPORATE CHANNEL RULE: REJECT (Answer NO) any official brand/corporate channels — e.g. channels run by companies, government agencies, broadcasters, or institutions for PR/marketing purposes. These are NOT individual creator channels.
- ACCEPTABLE (Answer YES): Individual or small-team creators producing professional lectures, coding/tech tutorials, informative tech/business news, software showcase screen captures, or a real person delivering expert knowledge.
- UNACCEPTABLE (Answer NO): Corporate/brand official channels, low-effort AI avatars/spam, generic gameplay/streaming, purely personal vlogs, mukbang, clickbait gossip.
- Use the hashtags as one more clue alongside the other fields, not as the sole basis for your decision.

Respond ONLY with YES or NO.

[Channel Title]: {channel_title}
[Channel Description]: {description}
[Latest Video Title]: {video_title}
[Video Hashtags]: {hashtags_str}
"""
        # 썸네일 URL이 없을 수도 있는 아주 희귀한 케이스 방어
        content_array = [{"type": "text", "text": prompt_text}]
        if video_thumbnail_url:
            content_array.append({
                "type": "image_url",
                "image_url": {"url": video_thumbnail_url}
            })
            
        messages = [
            {"role": "system", "content": "Respond ONLY with YES or NO."},
            {
                "role": "user",
                "content": content_array
            }
        ]
    
    global _consecutive_openai_failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0,
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().upper()
            _consecutive_openai_failures = 0  # 성공 시 실패 카운트 리셋
            return "YES" in result
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate_limit_exceeded' in err_str or 'insufficient_quota' in err_str:
                if attempt < max_retries - 1:
                    print(f"  ⏳ OpenAI API 처리량 초과 대기 중... (20초 후 재시도 {attempt+1}/{max_retries})")
                    time.sleep(20)
                    continue
            
            _consecutive_openai_failures += 1
            print(f"⚠️ OpenAI API 호출 오류 (연속 {_consecutive_openai_failures}회 실패): {e}")
            if _consecutive_openai_failures >= 3:
                print("\n🚨 [치명적 오류] OpenAI API가 연속 3회 실패했습니다. API 키, 한도, 혹은 네트워크를 점검해 주세요. 수집을 안전하게 중단하기 위해 프로그램을 종료합니다.")
                import sys
                sys.exit(1)
            
            print("  👉 일단 이번 채널은 임시로 통과 처리하고 계속 진행합니다.")
            return True
