#!/usr/bin/env bash
# 작업 공간에서: bash .agents/setup.sh [--refresh-times] <시작 HH:MM> <작업 분> [과제 마감 상한 HH:MM]
# 같은 날의 시각을 사용한다. 플랫폼 타이머가 최종 기준이며 알림은 실행하지 않는다.
set -euo pipefail

fail() { echo "[error] $*" >&2; exit 1; }
REFRESH=0
if [ "${1:-}" = --refresh-times ]; then REFRESH=1; shift; fi
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || fail "사용법: bash .agents/setup.sh [--refresh-times] <시작 HH:MM> <작업 분> [과제 마감 상한 HH:MM]"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

hhmm() { printf '%02d:%02d' "$(( $1 / 60 ))" "$(( $1 % 60 ))"; }
tomin() {
  local h m
  [[ "$1" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] || return 1
  h=$((10#${BASH_REMATCH[1]})); m=$((10#${BASH_REMATCH[2]}))
  [ "$h" -le 23 ] && [ "$m" -le 59 ] || return 1
  echo "$((h * 60 + m))"
}
S="$(tomin "$1")" || fail "시작 시각은 00:00~23:59여야 합니다: $1"
# 선행 0은 허용하되 산술 전에 길이와 범위를 제한한다.
[[ "$2" =~ ^0*([1-9][0-9]{0,3})$ ]] || fail "작업 분은 1~180의 십진수여야 합니다."
BUILD=$((10#${BASH_REMATCH[1]}))
[ "$BUILD" -le 180 ] || fail "대회 과제 작업 시간은 최대 180분입니다."
E=$((S + BUILD)); CAP_NOTE=""
if [ "$#" -eq 3 ]; then
  C="$(tomin "$3")" || fail "마감 상한은 00:00~23:59여야 합니다: $3"
  [ "$C" -gt "$S" ] || fail "마감 상한은 같은 날의 시작 시각보다 늦어야 합니다."
  if [ "$E" -gt "$C" ]; then E=$C; fi
  CAP_NOTE=" (과제 마감 상한 $(hhmm "$C"))"
fi
[ "$E" -le 1439 ] || fail "날짜를 넘는 일정은 지원하지 않습니다. 같은 날의 과제 마감 상한을 지정하세요."
D=$((E - S)); PREP=$((E - 10)); STAGE=SETUP
if [ "$PREP" -lt "$S" ]; then PREP=$S; fi
if [ "$D" -le 10 ]; then
  STAGE=WRAP
  echo "[warn] 작업 시간이 10분 이하입니다. 바로 제출 준비를 시작하세요."
fi
if [ "$D" -lt "$BUILD" ]; then echo "[warn] 마감 상한에 맞춰 작업 시간을 ${D}분으로 줄였습니다."; fi
T_START=$(hhmm "$S"); T_END=$(hhmm "$E"); T_PREP=$(hhmm "$PREP")
T15=$(hhmm $((S + D * 15 / 100))); T23=$(hhmm $((S + D * 23 / 100))); T45=$(hhmm $((S + D * 45 / 100)))
T80=$(hhmm $((S + D * 80 / 100))); T85=$(hhmm $((S + D * 85 / 100)))
PLAN="인터뷰 종료(15%) ${T15} · 합의(23%) ${T23} · E2E v0(45%) ${T45} · 새 기능 금지(80%) ${T80} · 리뷰 반영 중단(85%) ${T85} · 마감 준비 ${T_PREP} · 마감 ${T_END}"
TIME_LINE="- 작업 시간: ${T_START} ~ ${T_END}${CAP_NOTE}"
PLAN_LINE="- 체크포인트: ${PLAN}"

# 입력 검증이 끝난 뒤에만 작업 공간을 변경한다.
command -v git >/dev/null 2>&1 || fail "git이 없습니다. 제공 환경을 확인하세요."
[ ! -L docs ] && [ ! -L docs/STATE.md ] || fail "docs 또는 STATE.md가 심볼릭 링크입니다. 실제 작업 경로를 확인하세요."
if [ -e docs ] && [ ! -d docs ]; then fail "docs가 디렉터리가 아닙니다."; fi
if [ -e docs/STATE.md ] && [ ! -f docs/STATE.md ]; then fail "docs/STATE.md가 일반 파일이 아닙니다."; fi
mkdir -p docs
STATE_TMP=""
trap '[ -z "$STATE_TMP" ] || rm -f "$STATE_TMP"' EXIT
if [ -f docs/STATE.md ]; then
  for prefix in '- 작업 시간:' '- 체크포인트:'; do
    [ "$(grep -c -- "^${prefix}" docs/STATE.md || true)" -eq 1 ] || fail "STATE의 시각 항목이 없거나 중복됩니다. 기록을 보존하면서 직접 정리하세요."
  done
  if grep -Fxq -- "$TIME_LINE" docs/STATE.md && grep -Fxq -- "$PLAN_LINE" docs/STATE.md; then
    echo "[skip] 같은 일정입니다. 기존 STATE를 보존합니다."
  else
    [ "$REFRESH" -eq 1 ] || fail "STATE의 일정이 다르거나 미완성입니다. 플랫폼 시간을 확인하고 --refresh-times로 시각만 갱신하세요."
    STATE_TMP=$(mktemp docs/.STATE.XXXXXX)
    awk -v times="$TIME_LINE" -v plan="$PLAN_LINE" '
      /^- 작업 시간:/ { print times; next }
      /^- 체크포인트:/ { print plan; next }
      { print }
    ' docs/STATE.md > "$STATE_TMP"
    mv "$STATE_TMP" docs/STATE.md
    STATE_TMP=""
    echo "[ok] 시각만 갱신했습니다. 단계·작업 기록은 유지했으니 현재 단계와 다음 체크포인트를 확인하세요."
  fi
else
  STATE_TMP=$(mktemp docs/.STATE.XXXXXX)
  cat > "$STATE_TMP" <<STATE
# STATE

## 필수 산출물 (공식 과제 문서의 파일명·경로·내용을 빠짐없이 옮겨 적기)

- [ ]

## 진행

- 단계: ${STAGE}
${TIME_LINE}
${PLAN_LINE}
- 현재 작업: -
- 다음 체크포인트: -
- 막힌 점: -

## 시간 기준

- 위 일정은 과제 작업용이며 플랫폼 타이머가 우선한다. 자동 알림은 없다.
- 과제는 최대 180분, 후속 서술형은 별도 30분이며 준비 대기도 필요하다.
- 모든 단계는 14:00에 종료된다. 늦게 시작했다면 서술형·대기 시간을 남긴 과제 마감 상한을 정한다.
- 제출물 확정 후 에이전트 작업을 종료하고, 실제 서술형에는 AI를 사용하지 않는다.
STATE
  mv "$STATE_TMP" docs/STATE.md
  STATE_TMP=""
  echo "[ok] docs/STATE.md 생성"
fi
echo "  ${PLAN}"

echo "실행 환경:"
for c in git node npm npx python3 pip3 uv bun; do
  if command -v "$c" >/dev/null 2>&1; then
    version=$("$c" --version 2>&1 | head -n 1) || version="버전 확인 실패"
    printf '  %-8s %s\n' "$c" "$version"
  else
    printf '  %-8s 없음\n' "$c"
  fi
done
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -q
  echo "[ok] git init"
fi
if [ -z "$(git config user.email 2>/dev/null || true)" ] || [ -z "$(git config user.name 2>/dev/null || true)" ]; then
  echo "[warn] git 작성자 정보 미설정 — 커밋 전에 저장소 로컬 user.name / user.email을 확인하세요."
fi
echo "완료. 제공 Codex 실행 → /status, /model, /skills와 지침 로딩 확인 → 공식 과제 문서를 읽고 진행하세요."
