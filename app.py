# -*- coding: utf-8 -*-
"""
YouTube 채널 수집기 - 로컬 웹 UI 서버

브라우저에서 API 키와 키워드를 설정하고, 실행하고, 결과를 내려받습니다.

[보안]
  - 서버는 127.0.0.1(내 PC)에만 바인딩되어 외부에서 접근할 수 없습니다.
  - 입력한 API 키는 이 폴더의 .env 파일에만 저장되며, 외부로 전송되지 않습니다.
  - 브라우저로 되돌려주는 키 값은 항상 마스킹 처리합니다.
"""

import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from datetime import datetime

try:
    from flask import Flask, jsonify, request, send_file, send_from_directory
except ImportError:
    # 라이브러리가 안 깔려 있으면 아래처럼 알아보기 어려운 오류만 나오므로,
    # 무엇을 해야 하는지 한국어로 알려주고 종료합니다.
    print()
    print('=' * 60)
    print('  프로그램을 시작하지 못했습니다.')
    print()
    print('  필요한 라이브러리가 설치되어 있지 않습니다.')
    print()
    print('  이 폴더에서 아래 명령을 한 번 실행해 주세요.')
    print('     pip install -r requirements.txt')
    print()
    print('  (파이썬이 설치되어 있지 않다면 먼저 python.org 에서 설치하세요.')
    print('   설치 화면의 "Add python.exe to PATH" 를 꼭 체크해야 합니다)')
    print('=' * 60)
    print()
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
KEYWORDS_DIR = os.path.join(BASE_DIR, 'keywords')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
ENV_PATH = os.path.join(BASE_DIR, '.env')

CONFIG_PATH = os.path.join(BASE_DIR, 'src', 'config.py')

# ═════════════════════════════════════════════════════════
#  ★ 포트 번호  ★
#
#    이 프로그램이 사용할 포트 번호입니다.
#
#    이 번호를 다른 프로그램이 이미 쓰고 있으면,
#    프로그램이 비어 있는 다음 번호를 스스로 찾아 실행합니다.
#    브라우저도 실제 열린 주소로 자동 연결되므로 사용자가 할 일은 없습니다.
#
#    ※ 기본 번호를 바꾸고 싶을 때만 아래 숫자를 수정하세요.
#      (그대로 써도 무방합니다)
# ═════════════════════════════════════════════════════════

PORT = 5000

# ═════════════════════════════════════════════════════════

# 접속 주소 (보통 그대로 두시면 됩니다)
#   기본값 127.0.0.1 은 "내 PC에서만 접속 가능"이라는 뜻입니다.
#   플랫폼이 환경변수로 값을 넘겨주면 그 값을 우선 사용합니다.
HOST = os.environ.get('HOST', '127.0.0.1')
try:
    PORT = int(os.environ.get('PORT', PORT))
except ValueError:
    pass
IS_LOCAL = HOST in ('127.0.0.1', 'localhost')
OPEN_BROWSER = IS_LOCAL and os.environ.get('OPEN_BROWSER', '1') != '0'

# ─────────────────────────────────────────────────────────
# 화면에서 조절할 수 있는 수집 조건
#   src/config.py 의 해당 줄만 바꿔 씁니다. (주석은 그대로 보존)
#   0 을 "제한 없음(None)" 으로 쓰는 항목은 zero_is_none 으로 표시합니다.
# ─────────────────────────────────────────────────────────
SETTING_SPEC = [
    {'key': 'USE_OPENAI_FILTER', 'type': 'bool', 'default': True, 'group': 'basic',
     'label': 'AI 정밀 검수 사용',
     'help': 'OpenAI가 영상 자막과 썸네일까지 확인해 진짜 강의 채널만 남깁니다. '
             '끄면 훨씬 빠르고 무료지만, 관련 없는 채널이 더 섞입니다.'},

    {'key': 'MAX_RESULTS_PER_KEYWORD', 'type': 'int', 'default': 100, 'group': 'basic',
     'min': 10, 'max': 200, 'step': 10, 'unit': '개',
     'label': '키워드 1개당 최대 채널 수',
     'help': '많이 잡을수록 API 사용량이 늘어 하루 한도를 빨리 씁니다. 100개를 권장합니다.'},

    {'key': 'LAST_UPLOAD_MONTHS', 'type': 'int', 'default': 6, 'group': 'basic',
     'min': 0, 'max': 24, 'step': 1, 'unit': '개월', 'zero_is_none': True,
     'label': '최근 활동 기간',
     'help': '최근 이 기간 안에 영상을 올린 채널만 가져옵니다. 짧게 잡을수록 활발한 채널만 남습니다. '
             '0으로 두면 제한하지 않습니다.'},

    {'key': 'CONTACTABLE_ONLY', 'type': 'bool', 'default': True, 'group': 'advanced',
     'label': '연락처 있는 채널만',
     'help': '이메일·전화번호·카카오톡 중 하나라도 있는 채널만 남깁니다. 끄면 결과는 늘지만 연락할 수 없는 채널이 섞입니다.'},

    {'key': 'EDUCATION_ONLY', 'type': 'bool', 'default': True, 'group': 'advanced',
     'label': '강의·교육 채널만',
     'help': '채널명과 소개글에 강의/교육 관련 표현이 있는 채널만 남깁니다.'},

    {'key': 'KOREAN_ONLY', 'type': 'bool', 'default': True, 'group': 'advanced',
     'label': '한국 채널만',
     'help': '끄면 해외 채널도 함께 수집합니다.'},

    {'key': 'CHANNEL_AGE_MONTHS', 'type': 'int', 'default': 0, 'group': 'advanced',
     'min': 0, 'max': 60, 'step': 1, 'unit': '개월', 'zero_is_none': True,
     'label': '채널 개설 기간 제한',
     'help': '최근 이 기간 안에 만들어진 채널만 가져옵니다. 신생 채널을 찾을 때 씁니다. 0이면 제한 없음.'},

    {'key': 'EXCLUDE_SHORTS', 'type': 'bool', 'default': False, 'group': 'advanced',
     'label': '쇼츠 위주 채널 제외',
     'help': '4분 미만 영상만 올리는 채널을 걸러냅니다. 켜면 API 사용량이 늘어납니다.'},

    {'key': 'ORDER', 'type': 'select', 'default': 'relevance', 'group': 'advanced',
     'options': [['relevance', '관련도순 (권장)'], ['date', '최신순'], ['viewCount', '조회수순']],
     'label': '검색 정렬 방식',
     'help': '유튜브에서 어떤 순서로 채널을 가져올지 정합니다.'},

    {'key': 'OPENAI_MODEL', 'type': 'text', 'default': 'gpt-4o', 'group': 'advanced',
     'placeholder': 'gpt-4o',
     'label': 'AI 검수 모델 이름',
     'help': 'AI 정밀 검수를 켰을 때 사용할 OpenAI 모델 이름을 직접 입력합니다. '
             '모델은 수시로 추가·중단되므로 OpenAI 문서에서 현재 쓸 수 있는 이름을 확인해 넣으세요. '
             '영문·숫자·점(.)·하이픈(-)·밑줄(_)만 쓸 수 있습니다.'},
]

app = Flask(__name__, static_folder=None)

for _d in (DATA_DIR, KEYWORDS_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)


# ─────────────────────────────────────────────────────────
# 실행 상태 (한 번에 하나만 실행)
# ─────────────────────────────────────────────────────────
class RunState:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.lines = []
        self.running = False
        self.started_at = None
        self.finished_at = None
        self.exit_code = None
        self.stopped = False
        self.progress = {'current': 0, 'total': 0, 'keyword': ''}
        self.before = {}     # 실행 전 스냅샷 {파일명: set(channel_id)}
        self.result = None   # 실행 후 집계 결과


STATE = RunState()


# ─────────────────────────────────────────────────────────
# 설정 파일 입출력
# ─────────────────────────────────────────────────────────
def mask(value):
    """API 키를 브라우저로 보낼 때 앞뒤 일부만 남기고 가립니다."""
    if not value:
        return ''
    if len(value) <= 12:
        return value[:2] + '*' * (len(value) - 2)
    return value[:6] + '*' * 10 + value[-4:]


def read_env():
    """.env 를 읽어 {키이름: 값} 으로 돌려줍니다."""
    result = {}
    if not os.path.exists(ENV_PATH):
        return result
    with io.open(ENV_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            result[k.strip()] = v.strip()
    return result


def write_env(youtube_keys, openai_key):
    """
    입력받은 키를 .env 로 저장합니다.
    크롤러가 YOUTUBE_API_KEY_1, _2 ... 형태의 번호를 인식하므로 번호를 붙여 저장합니다.
    """
    lines = ['# 이 파일은 설정 화면에서 자동으로 만들어집니다.',
             '# API 키가 그대로 들어 있으므로 외부에 공유하지 마세요.',
             '']
    for i, key in enumerate(youtube_keys, 1):
        lines.append('YOUTUBE_API_KEY_{}={}'.format(i, key))
    lines.append('')
    lines.append('OPENAI_API_KEY={}'.format(openai_key or ''))
    lines.append('')
    with io.open(ENV_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def save_keywords(groups):
    """
    키워드 목록을 그룹별로 keywords_1.txt, keywords_2.txt ... 로 저장합니다.

    그룹 하나가 API 키 하나의 담당 분량입니다.
    (크롤러가 'API 키 번호 ↔ 키워드 파일 번호'로 매칭하기 때문에 번호를 맞춰 저장합니다.)
    """
    # 기존 키워드 파일 정리 (남아 있으면 엉뚱한 키워드가 같이 돌아갑니다)
    for name in os.listdir(KEYWORDS_DIR):
        if re.match(r'^keywords_\d+\.txt$', name):
            os.remove(os.path.join(KEYWORDS_DIR, name))

    saved = []
    for i, group in enumerate(groups, 1):
        # 중복 제거 (순서 유지)
        seen = set()
        uniq = []
        for kw in group:
            if kw and kw not in seen:
                seen.add(kw)
                uniq.append(kw)
        if not uniq:
            continue
        path = os.path.join(KEYWORDS_DIR, 'keywords_{}.txt'.format(i))
        with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(uniq) + '\n')
        saved.append((i, len(uniq)))
    return saved


def load_keyword_groups():
    """
    저장된 키워드 파일들을 그룹 목록으로 돌려줍니다. (화면 표시용)
    번호가 비어 있는 자리는 빈 그룹으로 채워 API 키 번호와 자리를 맞춥니다.
    """
    found = {}
    for name in os.listdir(KEYWORDS_DIR):
        m = re.match(r'^keywords_(\d+)\.txt$', name)
        if not m:
            continue
        with io.open(os.path.join(KEYWORDS_DIR, name), 'r', encoding='utf-8-sig') as f:
            found[int(m.group(1))] = [x.strip() for x in f if x.strip()]

    if not found:
        return []
    return [found.get(i, []) for i in range(1, max(found) + 1)]


def load_youtube_keys():
    """.env 에 저장된 YouTube 키를 번호 순서대로 돌려줍니다."""
    env = read_env()
    names = [k for k in env if re.match(r'^YOUTUBE_API_KEY_\d+$', k) and env[k]]
    names.sort(key=lambda x: int(x.rsplit('_', 1)[1]))
    return [env[n] for n in names]


# ─────────────────────────────────────────────────────────
# 수집 조건 (src/config.py 읽기·쓰기)
# ─────────────────────────────────────────────────────────
def _parse_literal(raw):
    raw = raw.strip()
    if raw == 'True':
        return True
    if raw == 'False':
        return False
    if raw == 'None':
        return None
    if len(raw) >= 2 and raw[0] in '"\'':
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        return raw


def read_settings():
    """src/config.py 에서 현재 값을 읽어옵니다. (화면 표시용으로 0/None 을 정리)"""
    try:
        text = io.open(CONFIG_PATH, 'r', encoding='utf-8').read()
    except Exception:
        text = ''
    values = {}
    for spec in SETTING_SPEC:
        m = re.search(r'^' + spec['key'] + r'\s*=\s*([^#\n]+)', text, re.M)
        v = _parse_literal(m.group(1)) if m else spec['default']
        if spec.get('zero_is_none') and v is None:
            v = 0
        values[spec['key']] = v
    return values


def write_settings(values):
    """
    전달받은 값으로 src/config.py 의 해당 줄만 바꿔 씁니다.
    값 부분만 교체하고 뒤에 붙은 설명 주석은 그대로 둡니다.
    """
    text = io.open(CONFIG_PATH, 'r', encoding='utf-8').read()

    for spec in SETTING_SPEC:
        key = spec['key']
        if key not in values:
            continue
        v = values[key]

        # 값 검증 — 화면에서 이상한 값이 와도 설정 파일이 깨지지 않도록 합니다.
        if spec['type'] == 'bool':
            literal = 'True' if v else 'False'
        elif spec['type'] == 'int':
            try:
                n = int(v)
            except (TypeError, ValueError):
                n = spec['default']
            n = max(spec.get('min', 0), min(spec.get('max', n), n))
            literal = 'None' if (spec.get('zero_is_none') and n == 0) else str(n)
        elif spec['type'] == 'select':
            allowed = [o[0] for o in spec['options']]
            literal = "'{}'".format(v if v in allowed else spec['default'])
        elif spec['type'] == 'text':
            # 이 값은 config.py 안에 그대로 써지므로, 따옴표나 줄바꿈이 섞이면
            # 설정 파일이 깨집니다. 안전한 문자만 허용하고 아니면 기본값으로 되돌립니다.
            v = (v or '').strip()
            if not re.match(r'^[A-Za-z0-9._\-]{1,64}$', v):
                v = spec['default']
            literal = "'{}'".format(v)
        else:
            continue

        def _sub(mo, lit=literal):
            comment = mo.group(3) or ''
            pad = '  ' if comment else ''
            return mo.group(1) + lit + pad + comment

        text, n_sub = re.subn(
            r'^(' + key + r'\s*=\s*)([^#\n]*?)\s*(#.*)?$',
            _sub, text, count=1, flags=re.M)

    io.open(CONFIG_PATH, 'w', encoding='utf-8', newline='\n').write(text)


# ─────────────────────────────────────────────────────────
# 수집 결과 비교 (이번 실행에서 새로 늘어난 채널 찾기)
# ─────────────────────────────────────────────────────────
def snapshot_channels():
    """현재 data 폴더의 {파일명: set(channel_id)} 스냅샷."""
    snap = {}
    if not os.path.isdir(DATA_DIR):
        return snap
    for name in os.listdir(DATA_DIR):
        if not name.endswith('.json') or name.startswith('processed_ids'):
            continue
        try:
            with io.open(os.path.join(DATA_DIR, name), 'r', encoding='utf-8') as f:
                rows = json.load(f)
            if isinstance(rows, list):
                snap[name] = {r.get('channel_id') for r in rows if isinstance(r, dict)}
        except Exception:
            snap[name] = set()
    return snap


def collect_new(before):
    """실행 전 스냅샷과 비교해 새로 추가된 채널을 모읍니다."""
    after = snapshot_channels()
    files = []
    new_rows = []
    for name, ids in after.items():
        added = ids - before.get(name, set())
        if not added:
            continue
        try:
            with io.open(os.path.join(DATA_DIR, name), 'r', encoding='utf-8') as f:
                rows = json.load(f)
        except Exception:
            rows = []
        picked = [r for r in rows if isinstance(r, dict) and r.get('channel_id') in added]
        new_rows.extend(picked)
        files.append({'file': name, 'count': len(added)})
    files.sort(key=lambda x: -x['count'])
    return {'total': len(new_rows), 'files': files, 'rows': new_rows}


# ─────────────────────────────────────────────────────────
# 크롤러 실행
# ─────────────────────────────────────────────────────────
PROGRESS_RE = re.compile(r"진행:\s*(\d+)\s*/\s*(\d+)\s*-\s*'(.*)'")


def _reader(proc):
    """크롤러의 출력을 한 줄씩 읽어 화면에 보여줄 목록에 쌓습니다."""
    try:
        for raw in iter(proc.stdout.readline, ''):
            line = raw.rstrip('\r\n')
            with STATE.lock:
                STATE.lines.append(line)
                # 화면 표시용 진행률 추출
                m = PROGRESS_RE.search(line)
                if m:
                    STATE.progress = {
                        'current': int(m.group(1)),
                        'total': int(m.group(2)),
                        'keyword': m.group(3),
                    }
    except Exception as e:
        with STATE.lock:
            STATE.lines.append('[출력 읽기 오류] {}'.format(e))
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass


def _runner():
    """별도 스레드에서 크롤러를 실행하고 종료 후 결과를 집계합니다."""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'

    creationflags = 0
    if os.name == 'nt':
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    try:
        proc = subprocess.Popen(
            [sys.executable, 'youtube_channel_crawler.py', '--auto'],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )
    except Exception as e:
        with STATE.lock:
            STATE.lines.append('크롤러를 시작하지 못했습니다: {}'.format(e))
            STATE.running = False
            STATE.exit_code = -1
            STATE.finished_at = datetime.now()
        return

    with STATE.lock:
        STATE.proc = proc

    t = threading.Thread(target=_reader, args=(proc,), daemon=True)
    t.start()
    proc.wait()
    t.join(timeout=5)

    result = collect_new(STATE.before)
    # 다운로드 편의를 위해 신규 목록을 파일로도 남겨둡니다.
    try:
        out = os.path.join(LOG_DIR, 'last_new.json')
        with io.open(out, 'w', encoding='utf-8') as f:
            json.dump(result['rows'], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 키워드별 성공/실패 집계와 원인 안내.
    # 크롤러는 키가 틀려도 종료 코드 0으로 끝나기 때문에,
    # 이 검사가 없으면 사용자가 "신규 0건"만 보고 설정 오류를 눈치채지 못합니다.
    text = '\n'.join(STATE.lines)
    m_ok = re.search(r'성공:\s*(\d+)개', text)
    m_ng = re.search(r'실패:\s*(\d+)개', text)
    succeeded = int(m_ok.group(1)) if m_ok else None
    failed = int(m_ng.group(1)) if m_ng else None

    hint = ''
    if 'API key not valid' in text or 'API_KEY_INVALID' in text:
        hint = 'YouTube API 키가 올바르지 않습니다. 1단계에서 키를 다시 확인해 주세요.'
    elif 'accessNotConfigured' in text or 'has not been used in project' in text:
        hint = 'Google Cloud 프로젝트에서 YouTube Data API v3 를 "사용 설정"했는지 확인해 주세요.'
    elif 'quotaExceeded' in text or '할당량이 소진' in text:
        hint = '오늘 쓸 수 있는 API 한도를 모두 사용했습니다. 내일 다시 실행하거나 키를 추가해 주세요.'
    elif 'OPENAI' in text.upper() and 'api_key' in text.lower():
        hint = 'OpenAI API 키를 확인해 주세요. AI 검수가 필요 없다면 키를 비워두고 저장하면 됩니다.'
    elif failed:
        hint = '일부 키워드에서 오류가 발생했습니다. 위 로그를 확인해 주세요.'

    with STATE.lock:
        STATE.exit_code = proc.returncode
        STATE.running = False
        STATE.finished_at = datetime.now()
        STATE.result = {
            'total': result['total'],
            'files': result['files'],
            'succeeded': succeeded,
            'failed': failed,
            'hint': hint,
        }
        STATE.proc = None


# ─────────────────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    env = read_env()
    yt = []
    for k in sorted([k for k in env if re.match(r'^YOUTUBE_API_KEY_\d+$', k)],
                    key=lambda x: int(x.rsplit('_', 1)[1])):
        if env[k]:
            yt.append(mask(env[k]))
    return jsonify({
        'youtube_keys': yt,
        'youtube_count': len(yt),
        'openai_key': mask(env.get('OPENAI_API_KEY', '')),
        'has_openai': bool(env.get('OPENAI_API_KEY')),
        'keyword_groups': load_keyword_groups(),
    })


@app.route('/api/config', methods=['POST'])
def set_config():
    body = request.get_json(force=True, silent=True) or {}

    # 빈 칸으로 온 자리는 "기존 키를 그대로 둔다"는 뜻입니다.
    # (저장된 키는 화면에 다시 표시하지 않으므로, 키워드만 바꿀 때 키를 재입력하지 않아도 됩니다.)
    existing = load_youtube_keys()
    sent = body.get('youtube_keys', [])
    yt_keys = []
    for i, raw in enumerate(sent):
        value = (raw or '').strip()
        if value:
            yt_keys.append(value)
        elif i < len(existing):
            yt_keys.append(existing[i])

    openai_key = (body.get('openai_key') or '').strip()
    if not openai_key:
        # 마찬가지로 비워두면 기존 값을 유지합니다.
        openai_key = read_env().get('OPENAI_API_KEY', '')

    raw_groups = body.get('keyword_groups', [])
    groups = [[k.strip() for k in g if k and k.strip()] for g in raw_groups]

    if not yt_keys:
        return jsonify({'ok': False, 'message': 'YouTube API 키를 1개 이상 입력해 주세요.'}), 400
    if not any(groups):
        return jsonify({'ok': False, 'message': '키워드를 1개 이상 입력해 주세요.'}), 400

    # 키워드 그룹이 API 키보다 많으면 남는 그룹은 크롤러가 그냥 건너뜁니다.
    # 조용히 무시되면 사용자가 눈치채기 어려우므로 미리 막습니다.
    used = len([g for g in groups if g])
    if len(groups) > len(yt_keys):
        return jsonify({
            'ok': False,
            'message': '키워드 목록이 {}개인데 API 키는 {}개입니다. '
                       '목록 하나당 키 하나가 필요하니 키를 더 등록하거나 목록을 줄여 주세요.'
                       .format(len(groups), len(yt_keys)),
        }), 400

    write_env(yt_keys, openai_key)
    saved = save_keywords(groups)
    total = sum(c for _, c in saved)

    msg = 'API 키 {}개, 키워드 목록 {}개(총 {}개 키워드)를 저장했습니다.'.format(
        len(yt_keys), used, total)
    if len(yt_keys) > used:
        msg += ' (API 키 {}개는 담당 목록이 없어 이번 실행에서 쓰이지 않습니다.)'.format(
            len(yt_keys) - used)

    return jsonify({
        'ok': True,
        'message': msg,
        'files': [{'index': i, 'count': c} for i, c in saved],
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({'spec': SETTING_SPEC, 'values': read_settings()})


@app.route('/api/settings', methods=['POST'])
def post_settings():
    with STATE.lock:
        if STATE.running:
            return jsonify({'ok': False, 'message': '수집이 진행 중일 때는 조건을 바꿀 수 없습니다.'}), 409
    body = request.get_json(force=True, silent=True) or {}
    try:
        write_settings(body.get('values', {}))
    except Exception as e:
        return jsonify({'ok': False, 'message': '저장 실패: {}'.format(e)}), 500
    return jsonify({'ok': True, 'message': '수집 조건을 저장했습니다.', 'values': read_settings()})


@app.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    with STATE.lock:
        if STATE.running:
            return jsonify({'ok': False, 'message': '수집이 진행 중일 때는 조건을 바꿀 수 없습니다.'}), 409
    try:
        write_settings({s['key']: s['default'] for s in SETTING_SPEC})
    except Exception as e:
        return jsonify({'ok': False, 'message': '되돌리기 실패: {}'.format(e)}), 500
    return jsonify({'ok': True, 'message': '기본값으로 되돌렸습니다.', 'values': read_settings()})


@app.route('/api/run', methods=['POST'])
def run():
    with STATE.lock:
        if STATE.running:
            return jsonify({'ok': False, 'message': '이미 수집이 진행 중입니다.'}), 409

    env = read_env()
    if not any(re.match(r'^YOUTUBE_API_KEY_\d+$', k) and env[k] for k in env):
        return jsonify({'ok': False, 'message': 'API 키가 저장되어 있지 않습니다. 먼저 설정을 저장해 주세요.'}), 400
    if not any(load_keyword_groups()):
        return jsonify({'ok': False, 'message': '키워드가 저장되어 있지 않습니다. 먼저 설정을 저장해 주세요.'}), 400

    with STATE.lock:
        STATE.lines = []
        STATE.running = True
        STATE.stopped = False
        STATE.exit_code = None
        STATE.result = None
        STATE.started_at = datetime.now()
        STATE.finished_at = None
        STATE.progress = {'current': 0, 'total': 0, 'keyword': ''}
        STATE.before = snapshot_channels()

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/log')
def log():
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    with STATE.lock:
        lines = STATE.lines[offset:]
        elapsed = None
        if STATE.started_at:
            end = STATE.finished_at or datetime.now()
            elapsed = int((end - STATE.started_at).total_seconds())
        return jsonify({
            'lines': lines,
            'offset': offset + len(lines),
            'running': STATE.running,
            'stopped': STATE.stopped,
            'exit_code': STATE.exit_code,
            'progress': STATE.progress,
            'elapsed': elapsed,
            'result': STATE.result,
        })


@app.route('/api/stop', methods=['POST'])
def stop():
    with STATE.lock:
        proc = STATE.proc
        if not STATE.running or proc is None:
            return jsonify({'ok': False, 'message': '실행 중인 수집이 없습니다.'}), 400
        STATE.stopped = True
    try:
        proc.terminate()
    except Exception as e:
        return jsonify({'ok': False, 'message': '중단 실패: {}'.format(e)}), 500
    return jsonify({'ok': True, 'message': '중단을 요청했습니다. 지금까지 수집된 결과는 저장되어 있습니다.'})


@app.route('/api/download/all')
def download_all():
    """data 폴더의 수집 결과 전체를 ZIP으로 내려받습니다."""
    # processed_ids.json 은 내부 관리용이라 제외하고, 수집 결과만 담습니다.
    files = [n for n in os.listdir(DATA_DIR)
             if n.endswith('.json') and not n.startswith('processed_ids')]
    if not files:
        return jsonify({'ok': False, 'message': '아직 수집된 결과가 없습니다.'}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in files:
            z.write(os.path.join(DATA_DIR, n), arcname='data/' + n)
    buf.seek(0)
    name = 'youtube_channels_{}.zip'.format(datetime.now().strftime('%y%m%d_%H%M'))
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=name)


@app.route('/api/download/new')
def download_new():
    """이번 실행에서 새로 수집된 채널만 JSON으로 내려받습니다."""
    path = os.path.join(LOG_DIR, 'last_new.json')
    if not os.path.exists(path):
        return jsonify({'ok': False, 'message': '아직 수집을 실행하지 않았습니다.'}), 404
    name = 'new_channels_{}.json'.format(datetime.now().strftime('%y%m%d_%H%M'))
    return send_file(path, mimetype='application/json', as_attachment=True, download_name=name)


@app.route('/api/summary')
def summary():
    """현재 보유 중인 수집 결과 요약."""
    total = 0
    files = 0
    for n in os.listdir(DATA_DIR):
        if not n.endswith('.json') or n.startswith('processed_ids'):
            continue
        try:
            with io.open(os.path.join(DATA_DIR, n), 'r', encoding='utf-8') as f:
                rows = json.load(f)
            if isinstance(rows, list):
                total += len(rows)
                files += 1
        except Exception:
            pass
    return jsonify({'files': files, 'channels': total})


def is_port_busy(host, port):
    """이 포트를 다른 프로그램이 이미 쓰고 있는지 확인합니다."""
    import socket
    bind_host = '' if host == '0.0.0.0' else host
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((bind_host, port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def find_free_port(host, first, tries=30):
    """
    정해진 포트가 막혀 있으면 비어 있는 다른 포트를 찾아 줍니다.

    사용자가 코드를 열어 포트 번호를 고치지 않아도 되도록 하기 위한 장치입니다.
    브라우저는 실제로 열린 포트로 자동 연결되므로 사용자가 할 일은 없습니다.
    """
    for p in range(first, first + tries):
        if not is_port_busy(host, p):
            return p
    return None


def print_port_error(host, port):
    """빈 포트를 끝내 못 찾은 경우에만 나오는 안내입니다."""
    print()
    print('=' * 60)
    print('  프로그램을 시작하지 못했습니다.')
    print()
    print('  {}번부터 {}번까지 모두 다른 프로그램이 사용 중입니다.'.format(port, port + 29))
    print()
    print('  [해결 방법]')
    print('   1. 실행 중인 다른 프로그램을 닫고 다시 시도해 주세요.')
    print('   2. 그래도 안 되면 PC를 재시작한 뒤 다시 실행해 주세요.')
    print('   3. 환경 변수 PORT 로 다른 번호를 직접 지정할 수도 있습니다.')
    print('=' * 60)
    print()


def open_browser():
    time.sleep(1.0)
    try:
        webbrowser.open('http://{}:{}/'.format(HOST, PORT))
    except Exception:
        pass


if __name__ == '__main__':
    print('=' * 56)
    print(' YouTube 채널 수집기')
    print('=' * 56)

    # 쓸 포트를 먼저 확정합니다.
    # 정해진 포트가 막혀 있으면 비어 있는 포트를 알아서 찾습니다.
    # (사용자가 코드를 고칠 수 없는 환경이라, 프로그램이 스스로 해결해야 합니다)
    if is_port_busy(HOST, PORT):
        alt = find_free_port(HOST, PORT + 1)
        if alt is None:
            print_port_error(HOST, PORT)
            sys.exit(1)
        print(' {}번 포트를 다른 프로그램이 쓰고 있어 {}번으로 실행합니다.'.format(PORT, alt))
        print(' (따로 하실 일은 없습니다. 브라우저가 알아서 연결됩니다)')
        print()
        PORT = alt

    # 포트가 정해진 뒤에 안내와 브라우저 열기를 진행합니다.
    # (순서가 바뀌면 엉뚱한 주소로 브라우저가 열립니다)
    if OPEN_BROWSER:
        print(' 브라우저에서 아래 주소가 열립니다.')
        print('   http://{}:{}/'.format(HOST, PORT))
        print()
        print(' 창이 안 열리면 위 주소를 브라우저에 직접 입력하세요.')
        print(' 종료하려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.')
        threading.Thread(target=open_browser, daemon=True).start()
    else:
        print(' 서버 시작: {}:{}'.format(HOST, PORT))
    print('=' * 56)

    try:
        # 기본값은 127.0.0.1 이라 외부에서 접근할 수 없습니다.
        # 플랫폼에서 실행할 때만 환경변수 HOST 로 바인딩 주소를 바꿉니다.
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    except OSError:
        print_port_error(HOST, PORT)
        sys.exit(1)
