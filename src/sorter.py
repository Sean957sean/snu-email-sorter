import imaplib
import email
import re
import base64
from email.header import decode_header
from collections import Counter
from typing import Optional

# ── 상수 ──────────────────────────────────────────────────────────────────────

LABEL_PREFIX       = "메일분류"
FREQUENT_THRESHOLD = 3   # 이 횟수 이상 → 자주 오는 발신자

# 고정 폴더 5개
FOLDER_PERSONAL = f"{LABEL_PREFIX}/⭐ 개인"
FOLDER_ACADEMIC = f"{LABEL_PREFIX}/📚 학사"
FOLDER_SCHOLAR  = f"{LABEL_PREFIX}/💰 장학"
FOLDER_EVENT    = f"{LABEL_PREFIX}/🎉 행사"
FOLDER_ETC      = f"{LABEL_PREFIX}/기타"

# 카테고리 키워드 매핑 (대괄호 안 내용 or 제목 전체에서 검색)
CATEGORY_KEYWORDS = {
    FOLDER_ACADEMIC: [
        "학사", "수업", "강의", "교과", "수강", "시험", "과제", "성적",
        "졸업", "논문", "학점", "강좌", "교수", "세미나", "콜로키움",
    ],
    FOLDER_SCHOLAR: [
        "장학", "등록금", "학비", "장학금", "생활비", "지원금", "재정",
    ],
    FOLDER_EVENT: [
        "행사", "모집", "공모", "대외활동", "채용", "인턴", "설명회",
        "공연", "전시", "축제", "동아리", "특강", "워크숍", "hackathon",
        "해커톤", "경진대회", "대회",
    ],
}

BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
EMAIL_PATTERN   = re.compile(r"[\w.+-]+@[\w.-]+")


# ── 문자열 디코딩 ──────────────────────────────────────────────────────────────

def decode_str(raw) -> str:
    """RFC 2047 인코딩된 헤더 문자열을 사람이 읽을 수 있게 디코딩합니다."""
    if raw is None:
        return ""
    parts = decode_header(raw)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def extract_email_addr(raw: str) -> str:
    m = EMAIL_PATTERN.search(raw)
    return m.group(0).lower() if m else ""


def match_folder(subject: str) -> Optional[str]:
    """
    제목에서 폴더를 결정합니다.
    1) 대괄호 안 텍스트를 키워드와 비교
    2) 없으면 제목 전체를 키워드와 비교
    3) 매칭 없으면 None 반환
    """
    # 대괄호 안 내용 추출 (없으면 빈 문자열)
    bracket_match = BRACKET_PATTERN.search(subject)
    bracket_text  = bracket_match.group(1).strip() if bracket_match else ""
    subject_lower = subject.lower()

    for folder, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            # 대괄호 안에서 먼저 검색, 없으면 제목 전체에서 검색
            if kw_lower in bracket_text.lower() or kw_lower in subject_lower:
                return folder

    # 대괄호는 있지만 키워드 매핑이 안 된 경우 → 기타 (단체 메일로 판단)
    if bracket_text:
        return FOLDER_ETC

    return None  # 대괄호 자체가 없음 → 개인 메일 판단으로 넘어감


# ── IMAP Modified UTF-7 인코딩 (RFC 3501) ────────────────────────────────────

def imap_encode(folder: str) -> str:
    """
    한글·이모지 등 non-ASCII 문자를 포함한 폴더명을
    IMAP Modified UTF-7 형식으로 인코딩합니다.
    imaplib은 ASCII만 처리하므로 IMAP 명령 전달 전 반드시 변환 필요.

    예) '메일분류/⭐ 개인'  →  '&wMTBkMHE-/&2D3e7SA-&qZXrjA-'
    """
    result = []
    buf = []

    def flush():
        if buf:
            encoded = base64.b64encode(
                "".join(buf).encode("utf-16-be")
            ).rstrip(b"=").decode("ascii")
            result.append(f"&{encoded}-")
            buf.clear()

    for ch in folder:
        if "\x20" <= ch <= "\x7e" and ch != "&":
            flush()
            result.append(ch)
        elif ch == "&":
            flush()
            result.append("&-")
        else:
            buf.append(ch)

    flush()
    return "".join(result)


# ── IMAP 폴더 관리 ────────────────────────────────────────────────────────────

def ensure_folder(mail: imaplib.IMAP4_SSL, folder: str):
    """폴더가 없으면 생성합니다. Gmail IMAP에서는 라벨로 동작합니다."""
    encoded = imap_encode(folder)
    # 이미 존재하는 폴더 목록 조회
    _, data = mail.list()
    existing = b"".join(d for d in (data or []) if d)
    if encoded.encode() not in existing:
        mail.create(f'"{encoded}"')
        print(f"    [+] 폴더 생성: {folder}")


def move_message(mail: imaplib.IMAP4_SSL, uid: bytes, folder: str):
    """메시지를 지정 폴더로 복사 후 원본에서 삭제(= 이동)합니다."""
    encoded = imap_encode(folder)
    mail.uid("COPY", uid, f'"{encoded}"')
    mail.uid("STORE", uid, "+FLAGS", "\\Deleted")


# ── 발신자 빈도 분석 ──────────────────────────────────────────────────────────

def build_sender_frequency(mail: imaplib.IMAP4_SSL, sample_size: int = 300) -> Counter:
    """
    받은편지함 최근 sample_size 개를 기준으로 발신자 빈도를 집계합니다.
    헤더만 가져오므로 빠릅니다.
    """
    counter: Counter = Counter()
    mail.select("INBOX", readonly=True)
    _, data = mail.search(None, "ALL")
    all_ids = data[0].split()

    # 최신 순으로 sample_size 개
    target_ids = all_ids[-sample_size:] if len(all_ids) > sample_size else all_ids
    print(f"  발신자 빈도 분석 중 ({len(target_ids)}개)...", end="", flush=True)

    for msg_id in target_ids:
        _, header_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
        raw = header_data[0][1] if header_data and header_data[0] else b""
        msg = email.message_from_bytes(raw)
        addr = extract_email_addr(decode_str(msg.get("From", "")))
        if addr:
            counter[addr] += 1

    print(f" 완료")
    return counter


# ── 분류 규칙 ─────────────────────────────────────────────────────────────────

def classify(subject: str, sender_addr: str, to_field: str, freq: Counter) -> str:
    """
    분류 우선순위:
      1. 제목 키워드 매칭  →  학사 / 장학 / 행사 / 기타(대괄호 있지만 매핑 안됨)
      2. 대괄호 없음
           처음 오는 발신자 or 1:1 수신  →  개인
           자주 오는 발신자              →  기타
    """
    matched = match_folder(subject)
    if matched:
        return matched

    # 대괄호 없는 메일 → 개인 여부 판단
    is_new_sender = freq[sender_addr] <= 1
    is_one_to_one = "," not in to_field
    if is_new_sender or is_one_to_one:
        return FOLDER_PERSONAL

    return FOLDER_ETC


# ── 메인 정렬 ─────────────────────────────────────────────────────────────────

def sort_inbox(mail: imaplib.IMAP4_SSL, max_emails: int = 200, dry_run: bool = False):
    stats: Counter = Counter()
    folder_cache: set = set()

    # 1) 발신자 빈도 분석 (정렬 대상과 동일한 수 기준)
    freq = build_sender_frequency(mail, sample_size=max_emails)

    # 2) INBOX 열기
    mail.select("INBOX")
    _, data = mail.search(None, "ALL")
    all_ids = data[0].split()

    # 최신 순 max_emails 개
    target_ids = all_ids[-max_emails:] if len(all_ids) > max_emails else all_ids
    total = len(target_ids)
    print(f"\n  총 {total}개 메시지 처리 시작")
    print(f"\n  {'번호':<8} {'분류':<38} 제목")
    print(f"  {'-'*7}  {'-'*37}  {'-'*45}")

    for i, msg_id in enumerate(reversed(target_ids), 1):  # 최신부터
        # 헤더만 가져오기 (빠름)
        _, header_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO)])")
        raw = header_data[0][1] if header_data and header_data[0] else b""
        msg = email.message_from_bytes(raw)

        subject     = decode_str(msg.get("Subject", "(제목 없음)"))
        sender_raw  = decode_str(msg.get("From",    ""))
        to_field    = decode_str(msg.get("To",      ""))
        sender_addr = extract_email_addr(sender_raw)

        target = classify(subject, sender_addr, to_field, freq)
        stats[target] += 1

        prefix = "[DRY]" if dry_run else f"{i:>4}/{total}"
        print(f"  {prefix}  {target:<38}  {subject[:45]}")

        if not dry_run:
            # 폴더 생성 (캐시해서 중복 생성 방지)
            if target not in folder_cache:
                ensure_folder(mail, target)
                folder_cache.add(target)
            move_message(mail, msg_id, target)

    # 3) 삭제 플래그 반영 (이동 완료)
    if not dry_run:
        mail.expunge()

    # 4) 결과 요약
    print("\n" + "=" * 60)
    print("  정렬 결과 요약")
    print("=" * 60)
    for label, count in sorted(stats.items()):
        bar = "█" * min(count, 25)
        print(f"  {label:<42} {count:>4}개  {bar}")
    print(f"\n  총 {sum(stats.values())}개 메일 처리 {'(DRY RUN — 변경 없음)' if dry_run else '완료 ✓'}")
