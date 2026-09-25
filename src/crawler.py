from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
import time
from datetime import datetime, timedelta, timezone

from src.filters import is_education_channel, is_korean_text, make_safe_filename, has_exclude_keyword
from src.contact import extract_contact_info
from src.ai_filter import review_channel_with_ai
from src.exclusion import ExclusionList, EXCLUSION_FILE
from src.config import (
    USE_OPENAI_FILTER, EXCLUDE_SHORTS, SEARCH_VARIANTS, INCLUDE_HASHTAG_SEARCH,
    USE_EXCLUSION_LIST, EXCLUSION_MATCH_TITLE,
    CONTACT_FROM_VIDEOS, CONTACT_VIDEO_SCAN_COUNT,
)

DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)


class YouTubeChannelCrawler:
    def __init__(self, api_key):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.processed_file = os.path.join(DATA_DIR, 'processed_ids.json')
        self.global_processed_ids = self._load_global_processed_ids()
        # 메일 발송이 끝나 다시 수집할 필요가 없는 채널 명단 (data/excluded_channels.json)
        self.exclusion = ExclusionList(match_title=EXCLUSION_MATCH_TITLE) if USE_EXCLUSION_LIST else None

    def _load_global_processed_ids(self):
        """기존 모든 결과 파일과 블랙리스트에서 이미 처리된 모든 채널 ID를 불러옴"""
        all_ids = set()
        
        # 1. 블랙리스트 로드
        if os.path.exists(self.processed_file):
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    all_ids.update(json.load(f))
            except json.JSONDecodeError as e:
                print(f"⚠️  경고: {self.processed_file} 파일이 손상되었습니다. (무시됨: {e})")
            except Exception as e:
                print(f"⚠️  경고: 블랙리스트 로드 실패: {e}")
        
        # 2. 현재 블랙리스트와 같은 네임스페이스의 결과 JSON 파일들에서 ID 추출 (키워드 간 중복 방지)
        # processed_ids_game.json → 게임 결과 파일만 스캔, processed_ids.json → 전체 스캔
        processed_ids_basename = os.path.basename(self.processed_file)
        # 제외 명단은 수집 결과 파일이 아니라 형식이 달라서 반드시 건너뜁니다.
        skip_files = {os.path.basename(EXCLUSION_FILE)}
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json') and not filename.startswith('processed_ids') and filename not in skip_files:
                try:
                    with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for item in data:
                            all_ids.add(item.get('channel_id'))
                except json.JSONDecodeError as e:
                    print(f"⚠️  경고: 결과 파일 {filename}이 손상되었습니다. (무시됨: {e})")
                except Exception as e:
                    print(f"⚠️  경고: 결과 파일 {filename} 로드 실패: {e}")
        
        if all_ids:
            print(f"📊 글로벌 중복 체크 엔진: 총 {len(all_ids)}개 채널 학습 완료 (중복 절대 방지)")
        return all_ids

    def save_processed_ids(self, new_ids):
        """새롭게 확인된(필터링/탈락 포함) ID들을 블랙리스트에 저장"""
        if not new_ids: return
        self.global_processed_ids.update(new_ids)
        try:
            # 기존 블랙리스트와 합쳐서 저장
            current_list = []
            if os.path.exists(self.processed_file):
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    current_list = json.load(f)
            
            # 중복 제거, 정렬 후 들여쓰기(indent)를 주어 저장 (Git 충돌 방지 및 RPC 에러 방지)
            final_list = sorted(list(set(current_list + list(new_ids))))
            with open(self.processed_file, 'w', encoding='utf-8') as f:
                json.dump(final_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  블랙리스트 저장 실패: {e}")

    @staticmethod
    def load_existing_data(filename):
        if not os.path.exists(filename):
            print(f"ℹ️  기존 파일 없음 - 새로 시작합니다")
            return {}

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            existing = {item['channel_id']: item for item in data}
            print(f"✓ 기존 데이터 로드: {len(existing)}개 채널")
            return existing
        except Exception as e:
            raise RuntimeError(
                    f"기존 결과 파일을 읽지 못해 작업을 중단합니다. "
                    f"파일을 확인해 주세요: {filename} / 오류: {e}"
                ) from e

    def search_videos_to_find_channels(self, search_query, max_results=10, order="relevance", page_token=None, video_duration=None):
        try:
            search_params = {
                "q": search_query,
                "type": "video",
                "part": "id,snippet",
                "maxResults": max_results,
                "order": order,
                "regionCode": "KR"
            }
            if page_token:
                search_params["pageToken"] = page_token
            if video_duration:
                search_params["videoDuration"] = video_duration  # 'short'(<4분) / 'medium'(4~20분) / 'long'(>20분)

            search_response = self.youtube.search().list(**search_params).execute()

            # 영상에서 채널 정보 추출 및 중복 제거
            unique_channels = {}
            for item in search_response.get("items", []):
                # YouTube 검색 API가 드물게 videoId 등 일부 필드가 빠진 비정상 항목을
                # 반환하는 경우가 있어, 그런 항목은 건너뛰고 나머지는 계속 처리합니다.
                try:
                    video_id = item["id"]["videoId"]
                    channel_id = item["snippet"]["channelId"]
                    if channel_id not in unique_channels:
                        unique_channels[channel_id] = {
                            "channel_id": channel_id,
                            "title": item["snippet"]["channelTitle"],
                            "latest_video_id": video_id,
                            "latest_video_title": item["snippet"]["title"],
                            "latest_video_thumb": item["snippet"]["thumbnails"].get("high", {}).get("url", "")
                        }
                except (KeyError, TypeError):
                    continue

            next_page_token = search_response.get("nextPageToken")
            order_text = {"relevance": "관련성순", "date": "최신순", "viewCount": "조회수순"}.get(order, order)
            page_info = " (추가 페이지)" if page_token else ""
            print(f"  ✓ [{search_query}] → {len(unique_channels)}개 채널 발견 ({order_text}){page_info}")

            return list(unique_channels.values()), next_page_token

        except HttpError as e:
            is_quota_error = (
                (e.resp.status == 403 and "quotaExceeded" in str(e)) or
                (e.resp.status == 429 and "rateLimitExceeded" in str(e))
            )
            print(f"✗ 영상 검색 오류 발생 [{search_query}]: {e}")
            raise

    def get_last_upload_date(self, uploads_playlist_id):
        if not uploads_playlist_id:
            return None, None, None, None
        try:
            playlist_response = self.youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=1
            ).execute()
            items = playlist_response.get('items', [])
            if items:
                snippet = items[0]['snippet']
                published_at = snippet.get('publishedAt')
                video_title = snippet.get('title')
                video_id = snippet.get('resourceId', {}).get('videoId')
                thumbnails = snippet.get('thumbnails', {})
                video_thumbnail = thumbnails.get('maxres', {}).get('url') or thumbnails.get('high', {}).get('url') or thumbnails.get('medium', {}).get('url')
                return published_at, video_id, video_title, video_thumbnail
            return None, None, None, None
        except HttpError as e:
            is_quota_error = (
                (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
            )
            if is_quota_error:
                raise e
            return None, None, None, None
        except Exception:
            return None, None, None, None

    def find_contact_in_videos(self, uploads_playlist_id, max_videos):
        """채널 설명란에 연락처가 없을 때 최근 영상 설명란에서 연락처를 찾습니다.

        채널 소개의 '이메일 주소 보기'는 API로 내려오지 않아(웹에서 CAPTCHA를 거쳐야 함),
        영상 설명란이 자동 수집으로 연락처를 얻을 수 있는 사실상 유일한 경로입니다.
        연락처를 찾으면 contact_info 딕셔너리를, 못 찾으면 None을 돌려줍니다.
        """
        if not uploads_playlist_id or max_videos <= 0:
            return None
        try:
            playlist_response = self.youtube.playlistItems().list(
                part='contentDetails',
                playlistId=uploads_playlist_id,
                maxResults=max_videos
            ).execute()
            video_ids = [
                item['contentDetails']['videoId']
                for item in playlist_response.get('items', [])
                if item.get('contentDetails', {}).get('videoId')
            ]
            if not video_ids:
                return None

            videos_response = self.youtube.videos().list(
                part='snippet',
                id=','.join(video_ids)
            ).execute()
            # 영상마다 연락처를 조금씩 나눠 적는 경우가 있어 설명란을 합쳐서 한 번에 추출합니다.
            merged_description = '\n'.join(
                (item['snippet'].get('description') or '')
                for item in videos_response.get('items', [])
            )
            if not merged_description.strip():
                return None

            contact_info = extract_contact_info(merged_description)
            if any([contact_info['email'], contact_info['phone'],
                    contact_info['kakao'], contact_info['other_links']]):
                return contact_info
            return None
        except HttpError as e:
            is_quota_error = (
                (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
            )
            if is_quota_error:
                raise e
            return None
        except Exception:
            return None

    def _build_search_variants(self, query):
        """검색 변형 목록을 생성합니다. 키워드에 '/'가 포함되어 있으면 분리하여 각각 검색합니다."""
        variants = []
        sub_queries = [s.strip() for s in query.split('/') if s.strip()] if '/' in query else [query]

        for sub in sub_queries:
            for variant in SEARCH_VARIANTS:
                key_prefix = f"base_{sub}" if len(sub_queries) > 1 else "base"
                if variant == "":
                    # 원본 키워드 따옴표 정밀 검색
                    variants.append((key_prefix, f'"{sub}"'))
                else:
                    v_key = f"{variant}_{sub}" if len(sub_queries) > 1 else variant
                    variants.append((v_key, f'"{sub}" {variant}'))
            if INCLUDE_HASHTAG_SEARCH:
                # 공백 없이 붙여서 해시태그 검색 (예: "구글 스티치" → #구글스티치)
                hashtag = sub.replace(" ", "")
                h_key = f"hashtag_{sub}" if len(sub_queries) > 1 else "hashtag"
                variants.append((h_key, f'#{hashtag}'))
        return variants

    def get_channel_details_batch(self, channel_ids):
        if not channel_ids:
            return {}

        results = {}
        # YouTube channels.list API는 id 필터 사용 시 maxResults를 허용하지 않으며,
        # 한 번에 최대 50개의 ID만 처리 가능하므로 청크로 나눠서 요청합니다.
        CHUNK_SIZE = 50
        chunks = [channel_ids[i:i + CHUNK_SIZE] for i in range(0, len(channel_ids), CHUNK_SIZE)]

        for chunk in chunks:
            try:
                channel_response = self.youtube.channels().list(
                    part='snippet,statistics,contentDetails,brandingSettings',
                    id=','.join(chunk)
                ).execute()

                for channel in channel_response.get('items', []):
                    channel_id = channel['id']
                    snippet = channel['snippet']
                    statistics = channel.get('statistics', {})
                    content_details = channel.get('contentDetails', {})
                    description = snippet.get('description', '')

                    contact_info = extract_contact_info(description)
                    is_korean = (
                        snippet.get('country') == 'KR' or
                        is_korean_text(description) or
                        is_korean_text(snippet['title'])
                    )
                    uploads_playlist_id = content_details.get('relatedPlaylists', {}).get('uploads')

                    results[channel_id] = {
                        'channel_id': channel_id,
                        'title': snippet['title'],
                        'description': description,
                        'custom_url': snippet.get('customUrl', ''),
                        'published_at': snippet.get('publishedAt', ''),
                        'last_upload_date': None,
                        'country': snippet.get('country', 'N/A'),
                        'is_korean': is_korean,
                        'subscriber_count': statistics.get('subscriberCount', 'N/A'),
                        'video_count': statistics.get('videoCount', 'N/A'),
                        'view_count': statistics.get('viewCount', 'N/A'),
                        'channel_url': f"https://www.youtube.com/channel/{channel_id}",
                        'custom_channel_url': f"https://www.youtube.com/{snippet.get('customUrl', '')}" if snippet.get('customUrl') else '',
                        'email': contact_info['email'] or 'N/A',
                        'phone': contact_info['phone'] or 'N/A',
                        'kakao': contact_info['kakao'] or 'N/A',
                        'other_links': ', '.join(contact_info['other_links']) if contact_info['other_links'] else 'N/A',
                        'contactable': any([
                            contact_info['email'],
                            contact_info['phone'],
                            contact_info['kakao'],
                            contact_info['other_links']
                        ]),
                        'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        '_uploads_playlist_id': uploads_playlist_id
                    }

            except HttpError as e:
                is_quota_error = (
                    (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                    (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
                )
                print(f"✗ 채널 정보 일괄 가져오기 실패 (청크 {len(chunk)}개): {e}")
                raise

        return results

    def crawl(self, query, max_results=10, korean_only=True, order='relevance',
              data_file=None, update_mode=True, contactable_only=True,
              channel_age_months=None, last_upload_months=None, education_only=True):

        if data_file is None:
            data_file = os.path.join(DATA_DIR, make_safe_filename(query))

        print(f"\n{'='*60}")
        print(f"YouTube 채널 크롤링 시작: '{query}'")
        print(f"💾 저장 파일: {data_file}")
        print(f"🎯 목표: 새 채널 {max_results}개 수집")
        if korean_only:    print("🇰🇷 한국 채널만 필터링")
        if contactable_only: print("📧 연락처 있는 채널만 수집")
        if education_only:   print("🎓 강의/교육 채널만 수집")
        if channel_age_months: print(f"📅 채널 개설 {channel_age_months}개월 이내만")
        if last_upload_months: print(f"🎬 최근 {last_upload_months}개월 이내 활동 채널만")
        order_text = {'relevance': '관련성순', 'date': '최신순', 'viewCount': '조회수순'}.get(order, order)
        print(f"📊 정렬: {order_text}")
        print(f"{'='*60}\n")

        existing_data = self.load_existing_data(data_file) if update_mode else {}
        existing_file_ids = set(existing_data.keys())

        new_channels = []
        # [SESSION TRACKING]: 이번 키워드 수집 세션 중 확인한 채널 기억
        current_session_ids = set() 
        # [PERSISTENT BLACKLIST]: 최종 수집 완료된 채널 + AI 검수 탈락 채널만 블랙리스트에 저장 (OpenAI API 비용 절감)
        new_blacklisted_ids = set()
        
        duplicate_count = filtered_count = no_contact_count = 0
        # 채널 설명란 대신 영상 설명란에서 연락처를 건져 살린 채널 수
        video_contact_count = 0
        old_channel_count = inactive_channel_count = non_education_count = 0
        excluded_count = 0
        search_count = 0
        max_search_attempts = 10

        duration_filters = ['medium', 'long'] if EXCLUDE_SHORTS else [None]
        search_variants = self._build_search_variants(query)
        page_tokens = {f"{key}_{dur or 'all'}": None for key, _ in search_variants for dur in duration_filters}
        has_more_pages = True

        now = datetime.now(timezone.utc)
        channel_age_cutoff = now - timedelta(days=channel_age_months * 30) if channel_age_months else None
        last_upload_cutoff = now - timedelta(days=last_upload_months * 30) if last_upload_months else None

        # API 할당량 초과 시 True로 설정됨. 이 경우에도 지금까지 수집된 new_channels는
        # 아래 "최종 결과" 처리 로직을 그대로 통과해 파일로 저장되며, 데이터가 유실되지 않음.
        quota_exceeded = False
        # 할당량 문제는 아니지만(예: 예상치 못한 API 응답 형식, 일시적 오류 등) 이 키워드의
        # 검색을 더 진행할 수 없는 경우 True로 설정됨. 이때도 지금까지 모은 결과는 저장됨.
        keyword_aborted = False

        while search_count < max_search_attempts:
            search_count += 1

            if len(new_channels) >= max_results:
                print(f"\n✅ 이번 실행 목표 달성! ({len(new_channels)}개 추가)")
                break

            needed = (max_results - len(new_channels)) * 2
            search_size = min(needed, 50)

            if search_count > 1:
                print(f"\n{'='*60}")
                print(f"📍 추가 검색 ({search_count}회차) | 현재 {len(new_channels)}개 / 목표 {max_results}개")
                print(f"{'='*60}\n")

            # 모든 검색 변형 x 영상 길이 필터로 검색하고 고유 채널 합산
            total_combos = len(search_variants) * len(duration_filters)
            print(f"\n🔍 검색 중... ({total_combos}종 조합)")
            combined_channels_map = {}
            new_page_tokens = {}
            for variant_key, variant_query in search_variants:
                for dur in duration_filters:
                    pt_key = f"{variant_key}_{dur or 'all'}"
                    pt = page_tokens.get(pt_key)
                    try:
                        v_channels, next_pt = self.search_videos_to_find_channels(
                            variant_query, max_results=search_size, order=order,
                            page_token=pt, video_duration=dur
                        )
                    except HttpError as e:
                        is_quota_error = (
                            (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                            (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
                        )
                        if is_quota_error:
                            print(f"\n🚨 API 할당량 초과 감지 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 안전하게 종료합니다.")
                            quota_exceeded = True
                            break
                        print(f"\n⚠️  검색 중 예상치 못한 API 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                        keyword_aborted = True
                        break
                    except Exception as e:
                        print(f"\n⚠️  검색 중 예상치 못한 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                        keyword_aborted = True
                        break
                    new_page_tokens[pt_key] = next_pt
                    for ch in v_channels:
                        if ch['channel_id'] not in combined_channels_map:
                            combined_channels_map[ch['channel_id']] = ch
                if quota_exceeded or keyword_aborted:
                    break
            if quota_exceeded or keyword_aborted:
                break

            page_tokens = new_page_tokens
            has_more_pages = any(t is not None for t in page_tokens.values())
            channels = list(combined_channels_map.values())
            print(f"  → 합산 {len(channels)}개 유니크 채널")

            if not channels:
                print("더 이상 검색 결과가 없습니다.")
                break

            # 중복 제거 (글로벌 수집/AI거절 블랙리스트 + 해당 키워드 결과 파일 기존 채널 + 세션 차단)
            target_channels = []
            for ch in channels:
                ch_id = ch['channel_id']
                if ch_id in self.global_processed_ids or ch_id in existing_file_ids or ch_id in current_session_ids:
                    duplicate_count += 1
                    continue

                # 제외 명단 1차 대조 (채널ID / 채널명)
                # 상세 조회 전이라 여기서 걸러내면 API 할당량과 AI 검수 비용을 아낍니다.
                hit = self.exclusion.match_before_details(ch_id, ch.get('title')) if self.exclusion else None
                if hit:
                    reason, label = hit
                    print(f"  🚫 제외 명단({reason}): {ch.get('title')} → 명단 등재명 '{label}'")
                    excluded_count += 1
                    current_session_ids.add(ch_id)
                    continue

                target_channels.append(ch)
                current_session_ids.add(ch_id)  # 실시간 차단 리스트에 추가 (즉시 기억!)

            if not target_channels:
                if not has_more_pages:
                    print("\n⚠️  더 이상 검색 결과가 없습니다.")
                    break
                continue

            print(f"\n📍 {len(target_channels)}개 신규 채널 정보 일괄 수집 중...")
            try:
                batch_details = self.get_channel_details_batch([ch['channel_id'] for ch in target_channels])
            except HttpError as e:
                is_quota_error = (
                    (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                    (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
                )
                if is_quota_error:
                    print(f"\n🚨 API 할당량 초과 감지 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 안전하게 종료합니다.")
                    quota_exceeded = True
                    break
                print(f"\n⚠️  채널 상세정보 조회 중 예상치 못한 API 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                keyword_aborted = True
                break
            except Exception as e:
                print(f"\n⚠️  채널 상세정보 조회 중 예상치 못한 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                keyword_aborted = True
                break

            for channel in target_channels:
                if len(new_channels) >= max_results:
                    break

                details = batch_details.get(channel['channel_id'])
                if not details:
                    continue

                # 0. 검색에서 얻은 영상 정보(ID, 제목, 썸네일) 추출 및 보관
                # AI 검수 시 이 원본 검색 영상을 사용합니다.
                searched_video_id = channel.get('latest_video_id')
                searched_video_title = channel.get('latest_video_title')
                searched_video_thumb = channel.get('latest_video_thumb')
                
                details.update({
                    'latest_video_id': searched_video_id,
                    'latest_video_title': searched_video_title,
                    'latest_video_thumb': searched_video_thumb
                })
                
                # 0.5 제외 명단 2차 대조 (핸들 / 이메일)
                # 이메일은 채널 설명란에서 뽑아야 알 수 있어 상세 조회 후에만 확인할 수 있고,
                # 수동 관리 명단에서 가장 많이 채워져 있는 식별자입니다.
                hit = self.exclusion.match_after_details(details) if self.exclusion else None
                if hit:
                    reason, label = hit
                    print(f"  🚫 제외 명단({reason}): {details['title']} → 명단 등재명 '{label}'")
                    excluded_count += 1
                    # 채널명 매칭은 동명이인 오탐 가능성이 있어 영구 등록하지 않고 매번 명단으로 판단합니다.
                    # 나머지(채널ID/핸들/이메일)는 확실하므로 블랙리스트에 넣어 다음 실행부터 1차에서 걸러냅니다.
                    if reason != '채널명':
                        new_blacklisted_ids.add(details['channel_id'])
                    continue

                # 1. 가벼운 필터링 (API 호출 없음)
                if korean_only and not details['is_korean']:
                    filtered_count += 1
                    continue
                if contactable_only and not details['contactable']:
                    # 채널 설명란이 비어 있어도 영상 설명란에 문의처를 적어두는 채널이 많아,
                    # 바로 탈락시키지 않고 최근 영상 설명란을 한 번 더 확인합니다.
                    video_contact = None
                    if CONTACT_FROM_VIDEOS:
                        try:
                            video_contact = self.find_contact_in_videos(
                                details.get('_uploads_playlist_id'),
                                CONTACT_VIDEO_SCAN_COUNT
                            )
                        except HttpError as e:
                            print(f"\n🚨 API 할당량 초과 감지 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 안전하게 종료합니다.")
                            quota_exceeded = True
                            break

                    if not video_contact:
                        no_contact_count += 1
                        continue

                    details['email'] = video_contact['email'] or 'N/A'
                    details['phone'] = video_contact['phone'] or 'N/A'
                    details['kakao'] = video_contact['kakao'] or 'N/A'
                    details['other_links'] = ', '.join(video_contact['other_links']) if video_contact['other_links'] else 'N/A'
                    details['contactable'] = True
                    details['contact_source'] = '영상 설명란'
                    video_contact_count += 1
                    print(f"  📧 영상 설명란에서 연락처 확보: {details['title']}")
                
                if education_only:
                    if USE_OPENAI_FILTER:
                        # 이중 안전장치: 명백한 제외 키워드(게임, 먹방 등)가 있으면 AI 검수 비용을 아끼고 즉시 탈락
                        if has_exclude_keyword(details['title'], details['description']):
                            non_education_count += 1
                            continue
                        # 명백한 제외 채널이 아니라면 설명란 검사는 생략하고 AI가 영상 자막/제목을 보고 판단하도록 기회를 줌
                        pass
                    elif not is_education_channel(details['title'], details['description']):
                        # AI 미사용 시: 기존처럼 설명란 기반 엄격한 필터링
                        non_education_count += 1
                        continue

                if channel_age_cutoff and details['published_at']:
                    try:
                        published_date = datetime.fromisoformat(details['published_at'].replace('Z', '+00:00'))
                        if published_date < channel_age_cutoff:
                            old_channel_count += 1
                            continue
                    except ValueError:
                        pass
                    except Exception as e:
                        print(f"⚠️  채널 개설일 필터 작동 중 오류 발생: {e}")

                # 2. 통과된 채널만 최근 업로드일 API 조회 및 영상 정보 가져오기 (휴면 상태 검증용)
                last_upload = details.get('last_upload_date')

                # 정보가 부족한 경우에만 추가 API 호출
                if not last_upload:
                    uploads_playlist_id = details.pop('_uploads_playlist_id', None)
                    try:
                        last_upload, actual_video_id, actual_video_title, actual_video_thumb = self.get_last_upload_date(uploads_playlist_id)
                    except HttpError as e:
                        is_quota_error = (
                            (e.resp.status == 403 and 'quotaExceeded' in str(e)) or
                            (e.resp.status == 429 and 'rateLimitExceeded' in str(e))
                        )
                        if is_quota_error:
                            print(f"\n🚨 API 할당량 초과 감지 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 안전하게 종료합니다.")
                            quota_exceeded = True
                            break
                        print(f"\n⚠️  최근 업로드일 조회 중 예상치 못한 API 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                        keyword_aborted = True
                        break
                    except Exception as e:
                        print(f"\n⚠️  최근 업로드일 조회 중 예상치 못한 오류 — 지금까지 수집된 {len(new_channels)}개 채널을 저장하고 이 키워드는 여기서 마무리합니다: {e}")
                        keyword_aborted = True
                        break
                    details['last_upload_date'] = last_upload
                    # 최종 결과 파일에는 채널의 '실제 최신 영상' 정보를 덮어써서 기록함
                    if actual_video_id:
                        details['latest_video_id'] = actual_video_id
                        details['latest_video_title'] = actual_video_title
                        details['latest_video_thumb'] = actual_video_thumb
                
                if not last_upload:
                    inactive_channel_count += 1
                    continue
                
                if last_upload_months:
                    try:
                        if datetime.fromisoformat(last_upload.replace('Z', '+00:00')) < last_upload_cutoff:
                            inactive_channel_count += 1
                            continue
                    except ValueError:
                        pass
                    except Exception as e:
                        print(f"⚠️  최근 업로드일 필터 작동 중 오류 발생: {e}")

                # 2.5 OpenAI 강력 검수
                if USE_OPENAI_FILTER:
                    print(f"  👉 [AI 검수 중] {details['title']}...")
                    # 최신 영상(일상 브이로그일 수 있음) 대신, 최초에 검색된 관련 영상(searched_video)을 분석
                    is_valid = review_channel_with_ai(
                        details['title'],
                        details['description'],
                        searched_video_id,
                        searched_video_title,
                        searched_video_thumb,
                        search_keyword=query
                    )
                    if not is_valid:
                        print(f"  ⊝ AI 검수 탈락 (실제 교육 채널 아님)")
                        non_education_count += 1
                        new_blacklisted_ids.add(details['channel_id'])  # AI 탈락 채널 블랙리스트 영구 등록
                        continue
                    else:
                        print(f"  ✅ AI 검수 통과")

                # 3. 수집 확정
                details['priority_review'] = False

                print(f"\n✓ [검색 {search_count}회] 새 채널 추가: {details['title']}")
                details['collected_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                details['search_keyword'] = query
                new_channels.append(details)
                new_blacklisted_ids.add(details['channel_id'])  # 수집 완료 채널 블랙리스트 영구 등록

                contact_methods = []
                if details['email'] != 'N/A': contact_methods.append(f"이메일: {details['email']}")
                if details['phone'] != 'N/A': contact_methods.append(f"전화: {details['phone']}")
                if details['kakao'] != 'N/A': contact_methods.append(f"카톡: {details['kakao']}")
                print(f"  📊 구독자: {details['subscriber_count']} / 동영상: {details['video_count']}")
                if contact_methods:
                    print(f"  📧 연락처: {', '.join(contact_methods)}")
                print(f"  👉 진행률: {len(new_channels)}/{max_results}개 수집 완료")

            if quota_exceeded or keyword_aborted:
                break

            if not has_more_pages:
                print("\n⚠️  더 이상 검색 결과가 없습니다.")
                break

        # 최종 결과
        print(f"\n{'='*60}")
        if duplicate_count > 0:        print(f"ℹ️  중복 채널 제외: {duplicate_count}개")
        if excluded_count > 0:         print(f"🚫 제외 명단으로 차단: {excluded_count}개")
        if filtered_count > 0:         print(f"ℹ️  한국 채널 아님으로 제외: {filtered_count}개")
        if old_channel_count > 0:      print(f"ℹ️  채널 개설 오래됨으로 제외: {old_channel_count}개")
        if inactive_channel_count > 0: print(f"ℹ️  최근 활동 없음으로 제외: {inactive_channel_count}개")
        if no_contact_count > 0:       print(f"ℹ️  연락처 없음으로 제외: {no_contact_count}개")
        if video_contact_count > 0:   print(f"📧 영상 설명란에서 연락처 확보: {video_contact_count}개")
        if non_education_count > 0:    print(f"ℹ️  강의 채널 아님으로 제외: {non_education_count}개")

        # 이번 세션에서 수집 완료된 채널 + AI가 탈락시킨 채널만 블랙리스트에 저장 (OpenAI API 비용 절감)
        self.save_processed_ids(new_blacklisted_ids)
        
        all_channels = list(existing_data.values()) + new_channels
        print(f"✓ 이번 실행에서 추가된 채널: {len(new_channels)}개")
        if len(new_channels) < max_results:
            print(f"⚠️  이번 실행 목표({max_results}개)에 미달 (부족: {max_results - len(new_channels)}개)")
        print(f"✓ JSON 파일 내 전체 누적 채널: {len(all_channels)}개 (기존: {len(existing_data)}개 + 신규: {len(new_channels)}개)")
        contactable_count = sum(1 for ch in all_channels if ch['contactable'])
        print(f"📧 연락 가능 채널: {contactable_count}/{len(all_channels)}개")
        if quota_exceeded:
            print(f"🚨 이 API 키의 할당량이 소진되어 중단되었지만, 위 결과는 정상적으로 파일에 저장됩니다.")
        if keyword_aborted:
            print(f"⚠️  예상치 못한 오류로 이 키워드의 검색을 일찍 마쳤지만, 위 결과는 정상적으로 파일에 저장됩니다.")
        print(f"{'='*60}\n")

        return all_channels, data_file, len(new_channels), quota_exceeded

    def save_to_json(self, channels, filename='youtube_channels.json'):
        processed_channels = []
        for ch in channels:
            ch_copy = ch.copy()
            if 'priority_review' not in ch_copy:
                ch_copy['priority_review'] = False

            # 정의된 일관된 키 순서
            key_order = [
                'channel_id', 'title', 'description', 'custom_url', 'published_at',
                'last_upload_date', 'country', 'is_korean', 'subscriber_count',
                'video_count', 'view_count', 'channel_url', 'custom_channel_url',
                'email', 'phone', 'kakao', 'other_links', 'contactable', 'contact_source', 'thumbnail',
                'latest_video_id', 'latest_video_title', 'latest_video_thumb',
                'collected_date', 'search_keyword', 'priority_review'
            ]

            ordered_ch = {}
            # 1. 정의된 순서대로 키 배치
            for key in key_order:
                if key in ch_copy:
                    ordered_ch[key] = ch_copy.pop(key)
                elif key == 'priority_review':
                    ordered_ch[key] = False

            # 2. 혹시나 정의되지 않은 추가 키가 있다면 중간에 삽입 (priority_review 등 trailing 키보다 앞에 오도록)
            # 단, trailing 키들인 'collected_date', 'search_keyword', 'priority_review'는 항상 맨 마지막에 오도록 보장
            trailing_keys = ['collected_date', 'search_keyword', 'priority_review']

            # trailing 키들을 임시로 뺀 상태로 남은 키들을 ordered_ch에 추가
            remaining_trailing = {}
            for tk in trailing_keys:
                if tk in ordered_ch:
                    remaining_trailing[tk] = ordered_ch.pop(tk)

            # 혹시 pop하고 남은 ch_copy의 미정의 키들 추가
            for k, v in ch_copy.items():
                ordered_ch[k] = v

            # trailing 키들을 맨 마지막에 다시 붙임
            for tk in trailing_keys:
                if tk in remaining_trailing:
                    ordered_ch[tk] = remaining_trailing[tk]
                elif tk == 'priority_review':
                    ordered_ch[tk] = False

            processed_channels.append(ordered_ch)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(processed_channels, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON 파일 저장: {filename}")