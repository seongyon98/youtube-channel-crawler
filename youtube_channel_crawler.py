from googleapiclient.errors import HttpError
import os
import re
import sys
import io
import time
import argparse
from dotenv import load_dotenv

# Windows 터미널에서 이모지 출력 시 발생하는 cp949 인코딩 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8-sig', errors='replace')

from src.config import (
    MAX_RESULTS_PER_KEYWORD, KOREAN_ONLY, ORDER,
    CONTACTABLE_ONLY, EDUCATION_ONLY, CHANNEL_AGE_MONTHS,
    LAST_UPLOAD_MONTHS, KEYWORD_SLEEP_SECONDS, KEYWORDS_DIR,
    USE_OPENAI_FILTER, SEARCH_VARIANTS, EXCLUDE_SHORTS, INCLUDE_HASHTAG_SEARCH
)
from src.crawler import YouTubeChannelCrawler


def load_api_keys():
    """
    .env / 환경변수에서 YOUTUBE_API_KEY_1, YOUTUBE_API_KEY_2 ... 형태의 키를
    모두 찾아 번호 순으로 정렬해 반환합니다. [(1, 'key1'), (2, 'key2'), ...]
    """
    pattern = re.compile(r'^YOUTUBE_API_KEY_(\d+)$')
    found = []
    for env_name, value in os.environ.items():
        m = pattern.match(env_name)
        if m and value and value != 'YOUR_ACTUAL_API_KEY_HERE':
            found.append((int(m.group(1)), value))
    found.sort(key=lambda pair: pair[0])
    return found


def load_keywords_for_key(key_idx):
    """
    KEYWORDS_DIR 폴더에서 keywords_{key_idx}.txt 를 읽어 키워드 리스트를 반환합니다.
    파일이 없으면 예시 파일을 생성하고 None을 반환합니다 (해당 API 키는 이번 실행에서 건너뜀).
    """
    path = os.path.join(KEYWORDS_DIR, f'keywords_{key_idx}.txt')

    if not os.path.exists(path):
        os.makedirs(KEYWORDS_DIR, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write("파이썬\n업무자동화\nAI 에이전트\n")
            print(f"⚠️  {path} 파일이 없어 예시 파일을 생성했습니다. API 키 #{key_idx}는 이번 실행에서 건너뜁니다.")
        except Exception as e:
            print(f"⚠️  {path} 예시 파일 생성 실패: {e}")
        return None

    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            keywords = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"⚠️  {path} 파일 읽기 오류: {e}")
        return None

    if not keywords:
        print(f"⚠️  {path} 파일이 비어있어 API 키 #{key_idx}는 이번 실행에서 건너뜁니다.")
        return None

    return keywords


def main():
    load_dotenv()

    api_keys = load_api_keys()
    if not api_keys:
        print("⚠️  오류: API 키가 설정되지 않았습니다!")
        print("📝 .env 파일에 아래처럼 번호를 붙여 입력하세요:")
        print("   YOUTUBE_API_KEY_1=your_actual_api_key_here")
        print("   YOUTUBE_API_KEY_2=your_actual_api_key_here")
        return

    if USE_OPENAI_FILTER:
        OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        if not OPENAI_API_KEY or OPENAI_API_KEY == 'YOUR_ACTUAL_OPENAI_API_KEY_HERE':
            print("⚠️  오류: OpenAI API 키가 설정되지 않았습니다!")
            print("📝 .env 파일에 다음 내용을 추가하거나 환경 변수에 설정하세요:")
            print("   OPENAI_API_KEY=your_actual_openai_api_key_here")
            print("💡 AI 필터링을 원하지 않는다면 src/config.py에서 USE_OPENAI_FILTER = False 로 변경하세요.")
            return

    # 각 API 키 번호에 매칭되는 keywords/keywords_{n}.txt 를 준비
    key_file_pairs = []  # [(key_idx, api_key, keywords), ...]
    for key_idx, api_key in api_keys:
        keywords = load_keywords_for_key(key_idx)
        if keywords:
            key_file_pairs.append((key_idx, api_key, keywords))

    if not key_file_pairs:
        print(f"\n⚠️  실행할 (API 키, 키워드 파일) 조합이 없습니다. '{KEYWORDS_DIR}' 폴더를 확인하세요.")
        return

    total_keywords = sum(len(kw) for _, _, kw in key_file_pairs)

    print("=" * 60)
    print("🎯 YouTube 채널 자동 수집 시작")
    print("=" * 60)
    print(f"🔑 사용할 API 키: {len(key_file_pairs)}개")
    for key_idx, _, keywords in key_file_pairs:
        print(f"   - API 키 #{key_idx} ↔ {KEYWORDS_DIR}/keywords_{key_idx}.txt ({len(keywords)}개 키워드)")
    print(f"📊 전체 키워드 수(모든 API 키 합산): {total_keywords}개")
    print(f"🎯 키워드당 목표: {MAX_RESULTS_PER_KEYWORD}개")
    print(f"🇰🇷 한국 채널만: {'예' if KOREAN_ONLY else '아니오'}")
    print(f"📧 연락처 필수: {'예' if CONTACTABLE_ONLY else '아니오'}")
    print(f"🎓 강의 채널만: {'예' if EDUCATION_ONLY else '아니오'}")
    if CHANNEL_AGE_MONTHS: print(f"📅 채널 개설: {CHANNEL_AGE_MONTHS}개월 이내")
    if LAST_UPLOAD_MONTHS: print(f"🎬 최근 활동: {LAST_UPLOAD_MONTHS}개월 이내")
    print(f"📊 정렬: 관련성순")
    total_variants = len(SEARCH_VARIANTS) + (1 if INCLUDE_HASHTAG_SEARCH else 0)
    print(f"🔍 검색 변형: {total_variants}종 (원본+접미사 {len(SEARCH_VARIANTS)}개" + (" + 해시태그" if INCLUDE_HASHTAG_SEARCH else "") + ")")
    print(f"🎥 쇼츠 제외: {'예 (4분 미만 제외)' if EXCLUDE_SHORTS else '아니오'}")
    print("=" * 60)

    # [추가] 자동 모드 인자 확인
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true', help='Skip start prompt')
    args, unknown = parser.parse_known_args()

    if not args.auto:
        input("\n계속하려면 Enter를 누르세요... (Ctrl+C로 취소)")

    total_failed = 0
    results_summary = []

    # ── 바깥 루프: API 키 단위 ─────────────────────────────
    for key_idx, api_key, keywords in key_file_pairs:
        print(f"\n\n{'=' * 60}")
        print(f"🔑 API 키 #{key_idx} 사용 시작 (keywords_{key_idx}.txt, {len(keywords)}개 키워드)")
        print(f"{'=' * 60}")

        crawler = YouTubeChannelCrawler(api_key)

        # ── 안쪽 루프: 이 API 키에 매칭된 키워드 단위 ─────
        for idx, keyword in enumerate(keywords, 1):
            print(f"\n\n{'#' * 60}")
            print(f"# [API 키 #{key_idx}] 진행: {idx}/{len(keywords)} - '{keyword}'")
            print(f"{'#' * 60}\n")

            quota_exceeded = False
            try:
                channels, data_file, new_count, quota_exceeded = crawler.crawl(
                    keyword,
                    max_results=MAX_RESULTS_PER_KEYWORD,
                    korean_only=KOREAN_ONLY,
                    order=ORDER,
                    data_file=None,
                    update_mode=True,
                    contactable_only=CONTACTABLE_ONLY,
                    channel_age_months=CHANNEL_AGE_MONTHS,
                    last_upload_months=LAST_UPLOAD_MONTHS,
                    education_only=EDUCATION_ONLY
                )
                # 할당량 초과로 crawl()이 중간에 멈췄더라도, 그 시점까지 모인 channels는
                # 여기서 정상적으로 파일에 저장됩니다 (데이터 유실 없음).
                if not channels:
                    print(f"\n⚠️ '{keyword}' 검색 결과가 0건입니다. 빈 파일을 저장하지 않거나 기존 파일을 삭제합니다.")
                    if os.path.exists(data_file):
                        os.remove(data_file)
                else:
                    crawler.save_to_json(channels, data_file)

                results_summary.append({
                    'api_key': key_idx, 'keyword': keyword, 'file': data_file,
                    'total': len(channels), 'new': new_count,
                    'contactable': sum(1 for ch in channels if ch.get('contactable'))
                })
                print(f"\n✅ '{keyword}' 완료!")
                print(f"   파일: {data_file}")
                print(f"   수집: {len(channels)}개 (전체), 신규: {new_count}개")

            except HttpError as e:
                # crawl() 내부에서 할당량 오류는 이미 처리되어 정상 반환되므로,
                # 여기 걸리는 HttpError는 할당량과 무관한 예외에 대한 안전망입니다.
                print(f"\n❌ '{keyword}' 실패: {e}")
                total_failed += 1
                results_summary.append({'api_key': key_idx, 'keyword': keyword, 'file': None, 'total': 0, 'new': 0, 'contactable': 0, 'error': str(e)})
            except Exception as e:
                print(f"\n❌ '{keyword}' 실패: {e}")
                total_failed += 1
                results_summary.append({'api_key': key_idx, 'keyword': keyword, 'file': None, 'total': 0, 'new': 0, 'contactable': 0, 'error': str(e)})

            if quota_exceeded:
                print(f"\n🚨 API 키 #{key_idx} 할당량이 소진되어, 이 키의 남은 키워드는 건너뛰고 다음 API 키로 넘어갑니다. (이미 수집된 데이터는 저장 완료)")
                break

            if idx < len(keywords):
                print(f"\n⏳ 다음 키워드로 이동... ({KEYWORD_SLEEP_SECONDS}초 대기)")
                time.sleep(KEYWORD_SLEEP_SECONDS)

    # ── 최종 요약: 모든 API 키 · 모든 키워드 파일 처리가 끝난 뒤 단 한 번만 출력됨 ──
    # (run_and_sync.ps1은 이 함수가 정상 종료된 뒤에 git add/commit/push를 수행하므로,
    #  커밋/푸시는 자연히 "모든 키워드 파일을 다 돌린 뒤" 한 번만 일어납니다.)
    print("\n\n" + "=" * 60)
    print("🎉 전체 API 키 · 전체 키워드 파일 수집 완료!")
    print("=" * 60)
    print(f"\n📊 최종 통계:")
    print(f"   사용한 API 키: {len(key_file_pairs)}개")
    print(f"   처리한 키워드: {len(results_summary)}개")
    print(f"   성공: {len(results_summary) - total_failed}개")
    print(f"   실패: {total_failed}개")
    print(f"\n📋 키워드별 결과:")
    print("-" * 60)
    for i, result in enumerate(results_summary, 1):
        prefix = f"[API#{result['api_key']}] "
        if 'error' in result:
            print(f"{i:2d}. {prefix}{result['keyword']:20s} - ❌ 실패")
        else:
            print(f"{i:2d}. {prefix}{result['keyword']:20s} - ✅ {result['total']:3d}개 채널 (신규: {result['new']}개)")
            print(f"    └─ 파일: {result['file']}")
    print("\n" + "=" * 60)
    print("🎉 이번 실행에서 지정된 모든 API 키와 키워드 파일 처리가 끝났습니다.")
    print(f"⏰ 완료 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")
    print("✨ 이제 이 창을 닫으셔도 좋습니다.")
    print("=" * 60)


if __name__ == '__main__':
    main()