"""
YouTube 채널 정보 크롤러
YouTube Data API v3를 사용하여 검색어로 채널을 찾고 채널 정보를 수집합니다.
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv


class YouTubeChannelCrawler:
    def __init__(self, api_key):
        """
        YouTube Data API 클라이언트 초기화
        
        Args:
            api_key (str): YouTube Data API 키
        """
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    @staticmethod
    def load_existing_data(filename='youtube_channels.json'):
        """
        기존 JSON 파일에서 채널 데이터 로드
        
        Args:
            filename (str): JSON 파일명
        
        Returns:
            dict: {channel_id: channel_data} 형태의 딕셔너리
        """
        if not os.path.exists(filename):
            print(f"ℹ️  기존 파일 없음 - 새로 시작합니다")
            return {}
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # channel_id를 키로 하는 딕셔너리로 변환
            existing = {item['channel_id']: item for item in data}
            print(f"✓ 기존 데이터 로드: {len(existing)}개 채널")
            return existing
            
        except Exception as e:
            print(f"⚠️  기존 파일 로드 실패: {e}")
            return {}
    
    @staticmethod
    def make_safe_filename(query):
        """
        검색어를 안전한 파일명으로 변환
        
        Args:
            query (str): 검색어
        
        Returns:
            str: 안전한 파일명
        """
        # 파일명에 사용할 수 없는 문자 제거
        safe_query = re.sub(r'[<>:"/\\|?*]', '', query)
        # 공백을 언더스코어로 변환
        safe_query = safe_query.replace(' ', '_')
        # 최대 50자로 제한
        safe_query = safe_query[:50]
        
        return f"youtube_channels_{safe_query}.json"
    
    @staticmethod
    def extract_email(text):
        """
        텍스트에서 이메일 주소 추출
        
        Args:
            text (str): 검색할 텍스트
        
        Returns:
            str: 찾은 이메일 주소 또는 빈 문자열
        """
        if not text:
            return ''
        
        # 이메일 정규표현식 패턴
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # 이메일 찾기
        emails = re.findall(email_pattern, text)
        
        # 첫 번째 이메일 반환 (없으면 빈 문자열)
        return emails[0] if emails else ''
    
    @staticmethod
    def is_korean_text(text):
        """
        텍스트에 한국어가 포함되어 있는지 확인
        
        Args:
            text (str): 검색할 텍스트
        
        Returns:
            bool: 한국어 포함 여부
        """
        if not text:
            return False
        
        # 한글 유니코드 범위: AC00-D7A3
        korean_pattern = re.compile('[가-힣]+')
        
        # 한글이 있는지 확인
        return bool(korean_pattern.search(text))
    
    @staticmethod
    def extract_contact_info(text):
        """
        텍스트에서 다양한 연락처 정보 추출
        
        Args:
            text (str): 검색할 텍스트
        
        Returns:
            dict: 추출된 연락처 정보
        """
        if not text:
            return {
                'email': '',
                'phone': '',
                'kakao': '',
                'other_links': []
            }
        
        contact_info = {
            'email': '',
            'phone': '',
            'kakao': '',
            'other_links': []
        }
        
        # 이메일
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]
        
        # 전화번호 (한국)
        phone_patterns = [
            r'010[-\s]?\d{4}[-\s]?\d{4}',
            r'01[016789][-\s]?\d{3,4}[-\s]?\d{4}',
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
        
        # 기타 연락 방법 (네이버 블로그, 개인 사이트 등)
        url_pattern = r'https?://[^\s<>"\)]+|www\.[^\s<>"\)]+'
        urls = re.findall(url_pattern, text)
        # 유튜브, 소셜미디어 링크 제외하고 개인 연락 링크만
        contact_urls = []
        exclude_domains = ['youtube.com', 'youtu.be', 'instagram.com', 'twitter.com', 'facebook.com', 'x.com']
        for url in urls:
            if not any(domain in url.lower() for domain in exclude_domains):
                contact_urls.append(url)
        
        contact_info['other_links'] = contact_urls[:3]  # 최대 3개까지
        
        return contact_info
    
    def search_channels(self, query, max_results=10, order='relevance', page_token=None):
        """
        검색어로 채널 검색
        
        Args:
            query (str): 검색어
            max_results (int): 최대 결과 수 (기본값: 10)
            order (str): 정렬 방식 - 'relevance'(관련성), 'date'(최신순), 'viewCount'(조회수순)
            page_token (str): 다음 페이지 토큰 (페이지네이션용)
        
        Returns:
            tuple: (channels 리스트, next_page_token)
        """
        try:
            # 채널 타입만 검색
            search_params = {
                'q': query,
                'type': 'channel',
                'part': 'id,snippet',
                'maxResults': max_results,
                'order': order
            }
            
            if page_token:
                search_params['pageToken'] = page_token
            
            search_response = self.youtube.search().list(**search_params).execute()
            
            channels = []
            for item in search_response.get('items', []):
                channel_id = item['id']['channelId']
                channel_title = item['snippet']['title']
                channels.append({
                    'channel_id': channel_id,
                    'title': channel_title,
                    'description': item['snippet']['description']
                })
            
            next_page_token = search_response.get('nextPageToken')
            
            order_text = {
                'relevance': '관련성순',
                'date': '최신순',
                'viewCount': '조회수순'
            }.get(order, order)
            
            page_info = f" (추가 페이지)" if page_token else ""
            print(f"✓ 검색어 '{query}'로 {len(channels)}개 채널 발견 ({order_text}){page_info}")
            
            return channels, next_page_token
            
        except HttpError as e:
            print(f"✗ API 오류 발생: {e}")
            return [], None
    
    def get_channel_details(self, channel_id):
        """
        채널 상세 정보 가져오기
        
        Args:
            channel_id (str): 채널 ID
        
        Returns:
            dict: 채널 상세 정보
        """
        try:
            # 채널 정보 가져오기
            channel_response = self.youtube.channels().list(
                part='snippet,statistics,contentDetails,brandingSettings',
                id=channel_id
            ).execute()
            
            if not channel_response.get('items'):
                return None
            
            channel = channel_response['items'][0]
            
            # 채널 정보 추출
            snippet = channel['snippet']
            statistics = channel.get('statistics', {})
            branding = channel.get('brandingSettings', {})
            description = snippet.get('description', '')
            
            # 연락처 정보 추출
            contact_info = self.extract_contact_info(description)
            
            # 한국어 여부 확인
            is_korean = (
                snippet.get('country') == 'KR' or 
                self.is_korean_text(description) or 
                self.is_korean_text(snippet['title'])
            )
            
            channel_info = {
                'channel_id': channel_id,
                'title': snippet['title'],
                'description': description,
                'custom_url': snippet.get('customUrl', ''),
                'published_at': snippet['publishedAt'],
                'country': snippet.get('country', 'N/A'),
                'is_korean': is_korean,
                
                # 통계
                'subscriber_count': statistics.get('subscriberCount', 'N/A'),
                'video_count': statistics.get('videoCount', 'N/A'),
                'view_count': statistics.get('viewCount', 'N/A'),
                
                # 링크
                'channel_url': f"https://www.youtube.com/channel/{channel_id}",
                'custom_channel_url': f"https://www.youtube.com/{snippet.get('customUrl', '')}" if snippet.get('customUrl') else '',
                
                # 연락처 정보 (이메일, 전화, 카카오, 기타 링크만)
                'email': contact_info['email'] if contact_info['email'] else 'N/A',
                'phone': contact_info['phone'] if contact_info['phone'] else 'N/A',
                'kakao': contact_info['kakao'] if contact_info['kakao'] else 'N/A',
                'other_links': ', '.join(contact_info['other_links']) if contact_info['other_links'] else 'N/A',
                
                # 연락 가능 여부
                'contactable': any([
                    contact_info['email'],
                    contact_info['phone'],
                    contact_info['kakao'],
                    contact_info['other_links']
                ]),
                
                # 썸네일
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            }
            
            return channel_info
            
        except HttpError as e:
            print(f"✗ 채널 정보 가져오기 실패 ({channel_id}): {e}")
            return None
    
    def crawl(self, query, max_results=10, korean_only=True, order='relevance', 
              data_file=None, update_mode=True, contactable_only=True):
        """
        검색어로 채널을 검색하고 상세 정보 수집
        
        Args:
            query (str): 검색어
            max_results (int): 목표 수집 개수 (중복/필터링 제외 후)
            korean_only (bool): 한국 채널만 필터링 (기본값: True)
            order (str): 정렬 방식 - 'relevance'(관련성), 'date'(최신순), 'viewCount'(조회수순)
            data_file (str): 데이터를 저장/로드할 JSON 파일명 (None이면 검색어로 자동 생성)
            update_mode (bool): True면 기존 파일에 추가, False면 새로 생성
            contactable_only (bool): True면 연락처 있는 채널만 수집 (기본값: True)
        
        Returns:
            tuple: (channels 리스트, 사용된 파일명)
        """
        # 파일명 자동 생성 (지정하지 않은 경우)
        if data_file is None:
            data_file = self.make_safe_filename(query)
        
        print(f"\n{'='*60}")
        print(f"YouTube 채널 크롤링 시작: '{query}'")
        print(f"💾 저장 파일: {data_file}")
        print(f"🎯 목표: 새 채널 {max_results}개 수집")
        if korean_only:
            print("🇰🇷 한국 채널만 필터링")
        if contactable_only:
            print("📧 연락처 있는 채널만 수집")
        
        order_text = {
            'relevance': '관련성순',
            'date': '최신순',
            'viewCount': '조회수순'
        }.get(order, order)
        print(f"📊 정렬: {order_text}")
        print(f"{'='*60}\n")
        
        # 기존 데이터 로드 (update_mode일 때만)
        existing_data = {}
        if update_mode:
            existing_data = self.load_existing_data(data_file)
        
        # 수집 변수
        new_channels = []
        duplicate_count = 0
        filtered_count = 0
        no_contact_count = 0  # 연락처 없음 카운트
        page_token = None
        search_count = 0
        max_search_attempts = 10  # 최대 10번까지 추가 검색
        
        # 목표 개수를 채울 때까지 반복 검색
        while len(new_channels) < max_results and search_count < max_search_attempts:
            search_count += 1
            
            # 부족한 개수 계산 (여유있게 2배 검색)
            needed = (max_results - len(new_channels)) * 2
            search_size = min(needed, 50)  # API 제한: 최대 50개
            
            if search_count > 1:
                print(f"\n{'='*60}")
                print(f"📍 부족분 추가 검색 ({search_count}회차)")
                print(f"   현재: {len(new_channels)}개, 목표: {max_results}개")
                print(f"   추가 검색: {search_size}개")
                print(f"{'='*60}\n")
            
            # 채널 검색
            channels, next_page_token = self.search_channels(
                query, 
                max_results=search_size, 
                order=order, 
                page_token=page_token
            )
            
            if not channels:
                print("더 이상 검색 결과가 없습니다.")
                break
            
            # 다음 페이지 토큰 저장
            page_token = next_page_token
            
            # 각 채널의 상세 정보 수집
            for i, channel in enumerate(channels, 1):
                # 이미 목표 개수를 달성했으면 중단
                if len(new_channels) >= max_results:
                    print(f"\n✅ 목표 개수 달성! ({len(new_channels)}개)")
                    break
                
                channel_id = channel['channel_id']
                
                # 중복 체크
                if channel_id in existing_data:
                    print(f"\n[검색 {search_count}회-{i}/{len(channels)}] {channel['title']}")
                    print(f"  ⊝ 이미 존재하는 채널 - 건너뜀")
                    duplicate_count += 1
                    continue
                
                print(f"\n[검색 {search_count}회-{i}/{len(channels)}] {channel['title']} 정보 수집 중...")
                
                details = self.get_channel_details(channel_id)
                if details:
                    # 한국 채널 필터링
                    if korean_only and not details['is_korean']:
                        print(f"  ⊝ 한국 채널 아님 - 제외")
                        filtered_count += 1
                        continue
                    
                    # 연락처 필터링
                    if contactable_only and not details['contactable']:
                        print(f"  ⊝ 연락처 없음 - 제외")
                        no_contact_count += 1
                        continue
                    
                    new_channels.append(details)
                    
                    # 연락처 정보 출력
                    contact_methods = []
                    if details['email'] != 'N/A':
                        contact_methods.append(f"이메일: {details['email']}")
                    if details['phone'] != 'N/A':
                        contact_methods.append(f"전화: {details['phone']}")
                    if details['kakao'] != 'N/A':
                        contact_methods.append(f"카톡: {details['kakao']}")
                    if details['other_links'] != 'N/A':
                        contact_methods.append(f"링크: {details['other_links'][:50]}...")
                    
                    print(f"  ✓ 구독자: {details['subscriber_count']}, 동영상: {details['video_count']}")
                    print(f"  ✓ 진행: {len(new_channels)}/{max_results}개 수집 완료")
                    if contact_methods:
                        print(f"  📧 연락처: {', '.join(contact_methods)}")
                    else:
                        print(f"  ⚠️  연락처 정보 없음")
            
            # 다음 페이지가 없으면 중단
            if not page_token:
                print("\n⚠️  더 이상 검색 결과가 없습니다.")
                break
        
        # 최종 결과
        print(f"\n{'='*60}")
        if duplicate_count > 0:
            print(f"ℹ️  중복 채널 제외: {duplicate_count}개")
        if korean_only and filtered_count > 0:
            print(f"ℹ️  한국 채널 아님으로 제외: {filtered_count}개")
        if contactable_only and no_contact_count > 0:
            print(f"ℹ️  연락처 없음으로 제외: {no_contact_count}개")
        
        # 기존 데이터와 새 데이터 병합
        all_channels = list(existing_data.values()) + new_channels
        
        print(f"✓ 새로 추가된 채널: {len(new_channels)}개")
        if len(new_channels) < max_results:
            print(f"⚠️  목표({max_results}개)에 미달했습니다. (부족: {max_results - len(new_channels)}개)")
        print(f"✓ 전체 채널: {len(all_channels)}개")
        
        # 연락 가능 채널 통계 (모두 연락 가능하므로 100%)
        contactable_count = sum(1 for ch in all_channels if ch['contactable'])
        if contactable_only:
            print(f"📧 연락 가능 채널: {contactable_count}/{len(all_channels)}개 (100%)")
        else:
            print(f"📧 연락 가능 채널: {contactable_count}/{len(all_channels)}개")
        print(f"{'='*60}\n")
        
        return all_channels, data_file
    
    def save_to_json(self, channels, filename='youtube_channels.json'):
        """
        채널 정보를 JSON 파일로 저장
        
        Args:
            channels (list): 채널 정보 리스트
            filename (str): 파일명
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON 파일 저장: {filename}")


def main():
    """
    키워드 파일 기반 자동 수집
    """
    # .env 파일에서 환경 변수 로드
    load_dotenv()
    
    # 환경 변수에서 API 키 가져오기
    API_KEY = os.getenv('YOUTUBE_API_KEY')
    
    if not API_KEY or API_KEY == 'YOUR_ACTUAL_API_KEY_HERE':
        print("⚠️  오류: API 키가 설정되지 않았습니다!")
        print("📝 .env 파일을 생성하고 다음 내용을 입력하세요:")
        print("   YOUTUBE_API_KEY=your_actual_api_key_here")
        print("\n💡 API 키 발급 방법은 README.md를 참고하세요.")
        return
    
    # 키워드 파일 경로
    KEYWORDS_FILE = 'keywords.txt'
    
    # 키워드 파일 존재 확인
    if not os.path.exists(KEYWORDS_FILE):
        print(f"⚠️  오류: {KEYWORDS_FILE} 파일이 없습니다!")
        print("\n📝 keywords.txt 파일을 생성하고 다음과 같이 키워드를 입력하세요:")
        print("   (한 줄에 하나씩)")
        print("\n예시:")
        print("   파이썬")
        print("   요리")
        print("   게임")
        print("   영어공부")
        print("\n파일을 생성한 후 다시 실행해주세요.")
        
        # 예시 파일 자동 생성
        try:
            with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
                f.write("파이썬\n요리\n게임\n")
            print(f"\n✅ 예시 파일({KEYWORDS_FILE})을 생성했습니다!")
            print("   파일을 수정한 후 다시 실행하세요.")
        except Exception as e:
            print(f"\n❌ 파일 생성 실패: {e}")
        
        return
    
    # 키워드 파일 읽기
    try:
        with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            keywords = [line.strip() for line in f if line.strip()]
        
        if not keywords:
            print(f"⚠️  오류: {KEYWORDS_FILE} 파일이 비어있습니다!")
            print("키워드를 입력한 후 다시 실행하세요.")
            return
            
    except Exception as e:
        print(f"⚠️  파일 읽기 오류: {e}")
        return
    
    # 크롤러 초기화
    crawler = YouTubeChannelCrawler(API_KEY)
    
    # 설정
    MAX_RESULTS_PER_KEYWORD = 50  # 키워드당 50개
    KOREAN_ONLY = True
    ORDER = 'relevance'  # 관련성순
    CONTACTABLE_ONLY = True  # 연락처 있는 것만
    
    print("="*60)
    print("🎯 YouTube 채널 자동 수집 시작")
    print("="*60)
    print(f"📋 키워드 파일: {KEYWORDS_FILE}")
    print(f"📊 총 키워드 수: {len(keywords)}개")
    print(f"🎯 키워드당 목표: {MAX_RESULTS_PER_KEYWORD}개")
    print(f"🇰🇷 한국 채널만: {'예' if KOREAN_ONLY else '아니오'}")
    print(f"📧 연락처 필수: {'예' if CONTACTABLE_ONLY else '아니오'}")
    print(f"📊 정렬: 최신순")
    print("="*60)
    print("\n키워드 목록:")
    for i, keyword in enumerate(keywords, 1):
        print(f"  {i}. {keyword}")
    print("\n" + "="*60)
    
    input("\n계속하려면 Enter를 누르세요... (Ctrl+C로 취소)")
    
    # 전체 수집 통계
    total_collected = 0
    total_failed = 0
    results_summary = []
    
    # 각 키워드별로 수집
    for idx, keyword in enumerate(keywords, 1):
        print(f"\n\n{'#'*60}")
        print(f"# 진행: {idx}/{len(keywords)} - '{keyword}'")
        print(f"{'#'*60}\n")
        
        try:
            # 채널 정보 크롤링
            channels, data_file = crawler.crawl(
                keyword,
                max_results=MAX_RESULTS_PER_KEYWORD,
                korean_only=KOREAN_ONLY,
                order=ORDER,
                data_file=None,  # 자동 생성
                update_mode=True,
                contactable_only=CONTACTABLE_ONLY
            )
            
            # JSON 파일로 저장
            crawler.save_to_json(channels, data_file)
            
            # 새로 추가된 채널 수 계산 (전체에서 기존 데이터 제외)
            new_count = len([ch for ch in channels if ch.get('channel_id')])
            
            # 통계 저장
            result = {
                'keyword': keyword,
                'file': data_file,
                'total': len(channels),
                'new': new_count,
                'contactable': sum(1 for ch in channels if ch.get('contactable'))
            }
            results_summary.append(result)
            total_collected += new_count
            
            print(f"\n✅ '{keyword}' 완료!")
            print(f"   파일: {data_file}")
            print(f"   수집: {len(channels)}개 (전체)")
            
        except Exception as e:
            print(f"\n❌ '{keyword}' 실패: {e}")
            total_failed += 1
            results_summary.append({
                'keyword': keyword,
                'file': None,
                'total': 0,
                'new': 0,
                'contactable': 0,
                'error': str(e)
            })
        
        # 마지막 키워드가 아니면 잠시 대기
        if idx < len(keywords):
            print(f"\n⏳ 다음 키워드로 이동... (잠시 대기)")
            import time
            time.sleep(2)
    
    # 최종 결과 요약
    print("\n\n" + "="*60)
    print("🎉 전체 수집 완료!")
    print("="*60)
    print(f"\n📊 최종 통계:")
    print(f"   처리한 키워드: {len(keywords)}개")
    print(f"   성공: {len(keywords) - total_failed}개")
    print(f"   실패: {total_failed}개")
    
    print(f"\n📋 키워드별 결과:")
    print("-" * 60)
    for i, result in enumerate(results_summary, 1):
        if 'error' in result:
            print(f"{i:2d}. {result['keyword']:20s} - ❌ 실패")
        else:
            print(f"{i:2d}. {result['keyword']:20s} - ✅ {result['total']:3d}개 채널")
            print(f"    └─ 파일: {result['file']}")
    
    print("\n" + "="*60)
    print("💾 생성된 파일들:")
    print("-" * 60)
    for result in results_summary:
        if result['file']:
            print(f"   • {result['file']}")
    
    print("\n✨ 모든 작업이 완료되었습니다!")
    print("="*60)


if __name__ == '__main__':
    main()