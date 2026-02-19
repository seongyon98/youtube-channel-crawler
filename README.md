# 🎯 YouTube 채널 자동 수집기

YouTube Data API v3를 사용하여 키워드 기반으로 채널을 자동 수집하는 Python 스크립트입니다.

**완전 자동화**: 키워드 파일만 만들면 모든 채널을 자동으로 수집합니다!

## ✨ 주요 기능

### 🤖 자동화
- ✅ **키워드 파일 기반 자동 수집** - keywords.txt에 키워드만 입력하면 자동 실행
- ✅ **키워드당 50개씩 자동 수집** - 설정 변경 가능
- ✅ **중복 자동 제거** - 같은 채널은 한 번만 저장
- ✅ **부족분 자동 보충** - 목표 개수 달성까지 자동 추가 검색

### 🎯 필터링
- ✅ **한국 채널 필터링** - 국가 설정 또는 한글 포함 여부로 판단
- ✅ **연락처 필수 필터** - 연락 수단이 없는 채널 자동 제외
- ✅ **관련성순 정렬** - 신규 채널 우선 발굴

### 📧 연락처 자동 추출
- 이메일 주소
- 전화번호 (한국 형식)
- 카카오톡 ID
- 기타 링크 (블로그, 웹사이트 등)

### 💾 데이터 관리
- ✅ **검색어별 자동 파일 분리** - 각 키워드마다 별도 JSON 파일
- ✅ **업데이트 모드** - 같은 키워드로 재실행 시 새 채널만 추가
- ✅ **완전한 채널 정보** - 구독자, 동영상 수, 조회수, 설명 등

## 🚀 빠른 시작

### 1. 설치

```bash
# 필수 라이브러리 설치
pip install -r requirements.txt
```

### 2. API 키 설정

#### 2-1. YouTube Data API 키 발급

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성
3. "API 및 서비스" > "라이브러리" > "YouTube Data API v3" 활성화
4. "사용자 인증 정보" > "API 키" 생성
5. API 키 복사

#### 2-2. .env 파일 생성

프로젝트 폴더에 `.env` 파일 생성:

```
YOUTUBE_API_KEY=여기에_발급받은_API_키_입력
```

**예시:**
```
YOUTUBE_API_KEY=AIzaSyABC123def456GHI789jkl012MNO345pqr
```

### 3. 키워드 파일 생성

`keywords.txt` 파일을 만들고 수집할 키워드 입력 (한 줄에 하나씩):

```
파이썬
요리
게임
영어공부
운동
```

### 4. 실행

```bash
python youtube_channel_crawler.py
```

**끝!** 자동으로 모든 키워드를 순서대로 처리합니다.

## 📊 실행 예시

```
============================================================
🎯 YouTube 채널 자동 수집 시작
============================================================
📋 키워드 파일: keywords.txt
📊 총 키워드 수: 5개
🎯 키워드당 목표: 50개
🇰🇷 한국 채널만: 예
📧 연락처 필수: 예
📊 정렬: 관련성순
============================================================

키워드 목록:
  1. 파이썬
  2. 리더십
  3. AI 에이전트
  4. 마케팅
  5. 기획
  6. 생성형 AI

계속하려면 Enter를 누르세요... (Ctrl+C로 취소)
```

Enter를 누르면 자동으로 시작:

```
############################################################
# 진행: 1/5 - '파이썬'
############################################################

============================================================
YouTube 채널 크롤링 시작: '파이썬'
💾 저장 파일: youtube_channels_파이썬.json
🎯 목표: 새 채널 50개 수집
============================================================

[검색 1회-1/100] 채널A 정보 수집 중...
  ✓ 구독자: 1200, 동영상: 15
  ✓ 진행: 1/50개 수집 완료
  📧 연락처: 이메일: contact@example.com

[검색 1회-2/100] 채널B 정보 수집 중...
  ⊝ 연락처 없음 - 제외

... (자동 진행)

============================================================
ℹ️  중복 채널 제외: 5개
ℹ️  한국 채널 아님으로 제외: 8개
ℹ️  연락처 없음으로 제외: 12개
✓ 새로 추가된 채널: 50개
✓ 전체 채널: 50개
📧 연락 가능 채널: 50/50개 (100%)
============================================================

✅ '파이썬' 완료!
   파일: youtube_channels_파이썬.json
   수집: 50개 (전체)
```

## 📁 결과 파일

각 키워드별로 자동 생성:

```
📁 프로젝트 폴더/
  ├── .env                              ← API 키
  ├── keywords.txt                      ← 입력 키워드
  ├── youtube_channel_crawler.py        ← 메인 스크립트
  ├── requirements.txt                  ← 필수 라이브러리
  │
  ├── youtube_channels_파이썬.json     ← 결과 1
  ├── youtube_channels_요리.json       ← 결과 2
  ├── youtube_channels_게임.json       ← 결과 3
  ├── youtube_channels_영어공부.json   ← 결과 4
  └── youtube_channels_운동.json       ← 결과 5
```

## 📋 JSON 데이터 형식

```json
[
  {
    "channel_id": "UC1234567890",
    "title": "파이썬Master",
    "description": "파이썬 강의를 제공합니다.\n문의: contact@example.com",
    "custom_url": "@pythonmaster",
    "published_at": "2020-01-01T00:00:00Z",
    "country": "KR",
    "is_korean": true,
    
    "subscriber_count": "4780",
    "video_count": "120",
    "view_count": "263482",
    
    "channel_url": "https://www.youtube.com/channel/UC1234567890",
    "custom_channel_url": "https://www.youtube.com/@pythonmaster",
    
    "email": "contact@example.com",
    "phone": "010-1234-5678",
    "kakao": "pythonking",
    "other_links": "blog.naver.com/pythonmaster",
    
    "contactable": true,
    "thumbnail": "https://..."
  }
]
```

## ⚙️ 설정 변경

코드 내에서 다음 값들을 변경할 수 있습니다:

```python
# youtube_channel_crawler.py의 main() 함수에서

MAX_RESULTS_PER_KEYWORD = 50    # 키워드당 수집 개수
KOREAN_ONLY = True               # 한국 채널만 (False = 모든 국가)
ORDER = 'date'                   # 정렬: 'date'(최신순), 'relevance'(관련성), 'viewCount'(조회수)
CONTACTABLE_ONLY = True          # 연락처 필수 (False = 연락처 없어도 수집)
```

## 🔧 고급 사용법

### 여러 키워드 파일 사용

서로 다른 주제별로 키워드 파일 분리:

```python
# 코드에서 파일명 변경
KEYWORDS_FILE = 'keywords_교육.txt'
```

### 추가 수집

같은 키워드로 다시 실행하면:
- 기존 파일 자동 로드
- 중복 채널 자동 제외
- 새로운 채널만 추가

```bash
# Day 1: 50개 수집
python youtube_channel_crawler.py

# Day 2: 같은 키워드로 추가 50개 수집
python youtube_channel_crawler.py
→ 총 100개 누적!
```

### 대량 키워드 처리

```
keywords.txt (100개 키워드)
→ 자동으로 순서대로 전부 처리
→ 각각 50개씩 수집
→ 총 5,000개 채널 자동 수집!
```

## ⚠️ 주의사항

### API 할당량

- **무료 할당량**: 하루 10,000 units
- **사용량**:
  - 검색 1회: 100 units
  - 채널 정보 조회 1회: 1 unit
- **예상 소비**:
  - 키워드 1개 (50개 채널): 약 200 units
  - **하루 약 50개 키워드 처리 가능**

**권장 사항**:
- 한 번에 10-20개 키워드 처리
- 여러 날에 걸쳐 나눠서 실행

### 할당량 초과 시

에러 메시지: `quotaExceeded`

**해결 방법**:
1. 다음 날까지 대기 (자정 PST 기준 리셋)
2. Google Cloud Console에서 유료 결제 설정

### 실행 시간

- 키워드당 약 2-5분 소요
- 10개 키워드 = 약 20-50분
- 장시간 실행 시 백그라운드 실행 권장

## 🎯 필터링 기준

### 한국 채널 판정

다음 중 하나라도 해당하면 한국 채널:
- 채널 국가 설정이 "KR"
- 채널 제목에 한글 포함
- 채널 설명에 한글 포함

### 연락 가능 판정

다음 중 하나라도 있으면 연락 가능:
- 이메일 주소 (예: contact@example.com)
- 전화번호 (예: 010-1234-5678)
- 카카오톡 ID (예: 카카오톡: myid)
- 기타 링크 (예: blog.naver.com/xxx)

**모두 없으면 자동 제외!**

## 📊 통계 예시

최종 완료 후 표시되는 통계:

```
============================================================
🎉 전체 수집 완료!
============================================================

📊 최종 통계:
   처리한 키워드: 5개
   성공: 5개
   실패: 0개

📋 키워드별 결과:
------------------------------------------------------------
 1. 파이썬                 - ✅  50개 채널
    └─ 파일: youtube_channels_파이썬.json
 2. 요리                   - ✅  50개 채널
    └─ 파일: youtube_channels_요리.json
 3. 게임                   - ✅  50개 채널
    └─ 파일: youtube_channels_게임.json
 4. 영어공부               - ✅  50개 채널
    └─ 파일: youtube_channels_영어공부.json
 5. 운동                   - ✅  50개 채널
    └─ 파일: youtube_channels_운동.json

============================================================
💾 생성된 파일들:
------------------------------------------------------------
   • youtube_channels_파이썬.json
   • youtube_channels_요리.json
   • youtube_channels_게임.json
   • youtube_channels_영어공부.json
   • youtube_channels_운동.json

✨ 모든 작업이 완료되었습니다!
============================================================
```

## 🔍 트러블슈팅

### "API key not valid" 오류

- `.env` 파일이 올바른 위치에 있는지 확인
- API 키가 정확히 입력되었는지 확인
- API 키 제한 설정에서 YouTube Data API v3가 허용되어 있는지 확인

### "quotaExceeded" 오류

- API 할당량 초과
- 다음 날까지 대기하거나 키워드 개수 줄이기

### "keywords.txt 파일이 없습니다" 오류

- 프로젝트 폴더에 `keywords.txt` 파일 생성
- 파일이 없으면 자동으로 예시 파일 생성됨

### 키워드 파일이 비어있음

- `keywords.txt` 파일을 열어서 키워드 입력
- 한 줄에 하나씩 입력

### 수집 개수가 목표보다 적음

정상입니다. 다음과 같은 이유로 발생:
- 중복 채널이 많음
- 한국 채널이 적음
- 연락처가 없는 채널이 많음
- 실제 검색 결과가 적음

→ 자동으로 추가 검색하지만 최대 5회까지만 시도

## 💡 유용한 팁

### 1. 키워드 선정

**좋은 키워드 예시**:
- 파이썬 (넓은 주제)
- 요리 (넓은 주제)
- 게임 리뷰 (구체적)

**피해야 할 키워드**:
- 너무 구체적: "파이썬 3.11 비동기 프로그래밍 초급" → 결과 적음
- 너무 일반적: "영상" → 관련 없는 결과 많음

### 2. 매일 조금씩 실행

```
Day 1: keywords.txt에 10개 키워드 → 500개 채널
Day 2: keywords.txt에 다른 10개 키워드 → 500개 채널
...
Week 1: 총 3,500개 채널 수집
```

### 3. 중단 후 재시작

프로그램을 중단했다가 다시 실행해도 괜찮습니다:
- 이미 수집된 채널은 중복 제거
- 남은 키워드부터 계속 진행

### 4. 데이터 분석

JSON 파일을 Python으로 읽어서 분석:

```python
import json

with open('youtube_channels_파이썬.json', 'r', encoding='utf-8') as f:
    channels = json.load(f)

# 이메일 있는 채널만
email_channels = [ch for ch in channels if ch['email'] != 'N/A']
print(f"이메일 있음: {len(email_channels)}개")

# 구독자 1만 이상
popular = [ch for ch in channels 
           if ch['subscriber_count'] != 'N/A' 
           and int(ch['subscriber_count']) >= 10000]
print(f"구독자 1만+: {len(popular)}개")
```

## 🔒 보안 주의사항

### API 키 보호

- ✅ `.env` 파일에 저장
- ✅ `.gitignore`에 `.env` 추가
- ❌ 코드에 직접 입력 금지
- ❌ GitHub에 업로드 금지

### Git 사용 시

`.gitignore` 파일 내용:

```
# 환경 변수
.env

# 수집 결과
*.json

# Python 캐시
__pycache__/
*.pyc
```

## 📝 라이선스

이 코드는 교육 및 개인 사용 목적으로 자유롭게 사용 가능합니다.

YouTube API 사용 시 [YouTube API 서비스 약관](https://developers.google.com/youtube/terms/api-services-terms-of-service)을 준수해야 합니다.

## 🙋 문의

문제가 발생하거나 개선 제안이 있으시면 이슈를 등록해주세요.

---

**Happy Crawling! 🎉**