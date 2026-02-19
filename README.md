# YouTube 채널 정보 크롤러

YouTube Data API v3를 사용하여 검색어로 채널을 찾고 채널 정보를 수집하는 Python 스크립트입니다.

## 📋 기능

- 검색어로 YouTube 채널 검색
- 채널 상세 정보 수집:
  - 채널명, 설명, URL
  - 구독자 수, 동영상 수, 총 조회수
  - 개설일, 국가, 커스텀 URL
  - 썸네일 이미지 URL
- JSON 및 CSV 형식으로 데이터 저장

## 🔧 설치 방법

### 1. 필수 라이브러리 설치

```bash
pip install -r requirements.txt
```

이 명령어는 다음 라이브러리들을 설치합니다:
- `google-api-python-client`: YouTube API 사용
- `python-dotenv`: 환경 변수 관리

### 2. YouTube Data API 키 발급

#### Step 1: Google Cloud Console 접속
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. Google 계정으로 로그인

#### Step 2: 프로젝트 생성
1. 상단의 프로젝트 선택 드롭다운 클릭
2. "새 프로젝트" 클릭
3. 프로젝트 이름 입력 (예: "YouTube Crawler")
4. "만들기" 클릭

#### Step 3: YouTube Data API v3 활성화
1. 좌측 메뉴에서 "API 및 서비스" > "라이브러리" 클릭
2. 검색창에 "YouTube Data API v3" 입력
3. "YouTube Data API v3" 클릭
4. "사용 설정" 클릭

#### Step 4: API 키 생성
1. 좌측 메뉴에서 "API 및 서비스" > "사용자 인증 정보" 클릭
2. 상단의 "+ 사용자 인증 정보 만들기" 클릭
3. "API 키" 선택
4. API 키가 생성되면 복사해서 안전한 곳에 보관

#### Step 5: API 키 제한 설정 (권장)
1. 생성된 API 키 옆의 편집 아이콘 클릭
2. "API 제한사항"에서 "키 제한" 선택
3. "YouTube Data API v3"만 체크
4. 저장

### 3. 환경 변수 설정 (.env 파일)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 API 키를 저장합니다:

```bash
# .env 파일 생성
YOUTUBE_API_KEY=여기에_발급받은_API_키_입력
```

**예시:**
```
YOUTUBE_API_KEY=AIzaSyABC123def456GHI789jkl012MNO345pqr
```

**⚠️ 중요:**
- `.env` 파일은 절대 Git에 업로드하지 마세요!
- `.gitignore`에 `.env`를 추가하세요

## 📖 사용 방법

### 기본 사용

```python
import os
from dotenv import load_dotenv
from youtube_channel_crawler import YouTubeChannelCrawler

# .env 파일에서 API 키 로드
load_dotenv()
API_KEY = os.getenv('YOUTUBE_API_KEY')

# 크롤러 초기화
crawler = YouTubeChannelCrawler(API_KEY)

# 채널 검색 및 정보 수집
channels = crawler.crawl('요리', max_results=5)

# JSON 파일로 저장
crawler.save_to_json(channels, 'cooking_channels.json')

# CSV 파일로 저장
crawler.save_to_csv(channels, 'cooking_channels.csv')
```

### 커맨드라인 실행

```bash
# 1. .env 파일 생성 및 API 키 입력
echo "YOUTUBE_API_KEY=your_api_key_here" > .env

# 2. 프로그램 실행
python youtube_channel_crawler.py
```

실행 후:
1. 검색어 입력 (예: "요리", "게임", "음악" 등)
2. 최대 결과 수 입력 (기본값: 10)
3. 자동으로 JSON 및 CSV 파일 생성

## 📊 출력 데이터 형식

### JSON 예시
```json
[
  {
    "channel_id": "UC1234567890",
    "title": "채널명",
    "description": "채널 설명...",
    "custom_url": "@channelname",
    "published_at": "2015-01-01T00:00:00Z",
    "country": "KR",
    "subscriber_count": "1000000",
    "video_count": "500",
    "view_count": "50000000",
    "channel_url": "https://www.youtube.com/channel/UC1234567890",
    "custom_channel_url": "https://www.youtube.com/@channelname",
    "thumbnail": "https://..."
  }
]
```

### CSV 필드
- title: 채널명
- channel_id: 채널 ID
- custom_url: 커스텀 URL
- subscriber_count: 구독자 수
- video_count: 동영상 수
- view_count: 총 조회수
- channel_url: 채널 링크
- custom_channel_url: 커스텀 채널 링크
- country: 국가
- published_at: 개설일
- description: 설명
- thumbnail: 썸네일 URL

## ⚠️ 주의사항

### API 할당량
- YouTube Data API는 하루 **10,000 units** 무료 할당량 제공
- 검색 1회: 100 units
- 채널 정보 조회 1회: 1 unit
- 예시: 검색어 1개 + 채널 10개 조회 = 110 units
  - 하루 약 90번 검색 가능

### 할당량 초과 시
- 에러 메시지: `quotaExceeded`
- 해결 방법:
  1. 다음 날까지 대기 (할당량은 매일 자정 PST 기준 리셋)
  2. Google Cloud Console에서 유료 결제 설정

### 개인정보 보호
- API 키는 절대 공개 저장소에 업로드하지 마세요
- `.gitignore`에 API 키가 포함된 파일 추가 권장

## 🔍 트러블슈팅

### "API key not valid" 오류
- API 키가 올바르게 입력되었는지 확인
- API 키 제한 설정 확인 (YouTube Data API v3 허용 여부)

### "quotaExceeded" 오류
- 일일 할당량 초과
- max_results 값을 줄이거나 다음 날 재시도

### 구독자 수가 "N/A"로 표시
- 채널 소유자가 구독자 수를 비공개로 설정한 경우

## 📝 라이선스

이 코드는 교육 및 개인 사용 목적으로 자유롭게 사용 가능합니다.

YouTube API 사용 시 [YouTube API 서비스 약관](https://developers.google.com/youtube/terms/api-services-terms-of-service)을 준수해야 합니다.
