#!/usr/bin/env bash
# 하네스 설치 — 작업 공간 루트에서 한 번 실행
#   bash .agents/setup.sh <시작 HH:MM> <작업 분> [마감 상한 HH:MM]
#   예) bash .agents/setup.sh 14:00 120
# 하는 일: 체크포인트 계산, docs/STATE.md 생성(이미 있으면 덮어쓰지 않음), 실행 환경과 git 확인
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

START="${1:-}"
BUILD="${2:-}"
CAP="${3:-}"

hhmm() { local t=$(( ($1 + 1440) % 1440 )); printf "%02d:%02d" $(( t / 60 )) $(( t % 60 )); }
tomin() { [[ "$1" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] && echo $(( 10#${BASH_REMATCH[1]} * 60 + 10#${BASH_REMATCH[2]} )); }

# 1) 체크포인트: 마감 = 시작 + 작업 분 (상한이 있으면 그보다 늦지 않게), 퍼센트는 실제 작업 시간 기준
S="$(tomin "$START")"
C=""
[ -n "$CAP" ] && C="$(tomin "$CAP")"
VALID=0
if [ -n "$S" ] && [[ "$BUILD" =~ ^[0-9]+$ ]] && { [ -z "$CAP" ] || [ -n "$C" ]; }; then
  E=$(( S + BUILD ))
  [ -n "$C" ] && [ "$E" -gt "$C" ] && E=$C
  D=$(( E - S ))
  if [ "$D" -gt 10 ]; then
    VALID=1
    T_START=$(hhmm "$S"); T_END=$(hhmm "$E"); T_PREP=$(hhmm $(( E - 10 )))
    T15=$(hhmm $(( S + D * 15 / 100 ))); T23=$(hhmm $(( S + D * 23 / 100 ))); T45=$(hhmm $(( S + D * 45 / 100 )))
    T80=$(hhmm $(( S + D * 80 / 100 ))); T85=$(hhmm $(( S + D * 85 / 100 )))
    [ "$D" -lt "$BUILD" ] && echo "[warn] 시작이 늦어 작업 시간을 ${D}분으로 줄였습니다 (마감 상한 ${CAP})."
  else
    echo "[warn] 마감까지 남은 시간이 10분 이하입니다. 바로 마무리하세요."
  fi
else
  echo "[warn] 사용법: bash .agents/setup.sh <시작 HH:MM> <작업 분> [마감 상한 HH:MM] — 체크포인트 계산을 건너뜁니다."
fi
CAP_NOTE=""
[ "$VALID" = 1 ] && [ -n "$C" ] && CAP_NOTE=" (마감 상한 ${CAP})"
if [ "$VALID" = 0 ]; then
  T_START="HH:MM"; T_END="HH:MM"; T_PREP="HH:MM"; T15="HH:MM"; T23="HH:MM"; T45="HH:MM"; T80="HH:MM"; T85="HH:MM"
fi

PLAN="인터뷰 종료(15%) ${T15} · 합의(23%) ${T23} · E2E v0(45%) ${T45} · 새 기능 금지(80%) ${T80} · 리뷰 반영 중단(85%) ${T85} · 마감 준비 ${T_PREP} · 마감 ${T_END}"

# 2) 작업 문서 — 이미 있으면 덮어쓰지 않는다
mkdir -p docs
if [ -f docs/STATE.md ]; then
  echo "[skip] docs/STATE.md 이미 있음 (덮어쓰지 않음). 필요하면 아래 시각을 직접 옮겨 적으세요."
else
  cat > docs/STATE.md <<STATE
# STATE

## 필수 산출물 (요구사항 문서에서 옮겨 적기)

- [ ] 
- [ ] 

## 진행

- 단계: SETUP
- 작업 시간: ${T_START} ~ ${T_END}${CAP_NOTE}
- 체크포인트: ${PLAN}
- 현재 작업: -
- 다음 체크포인트: -
- 막힌 점: -
STATE
  echo "[ok] docs/STATE.md"
fi
echo "  ${PLAN}"

# 3) 실행 환경
echo "== 실행 환경 =="
for c in git node npm npx python3 pip3 uv bun; do
  if command -v "$c" >/dev/null 2>&1; then
    printf "  %-8s %s\n" "$c" "$("$c" --version 2>&1 | head -1)"
  else
    printf "  %-8s 없음\n" "$c"
  fi
done

# 4) git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -q && echo "[ok] git init"
fi
if [ -z "$(git config user.email 2>/dev/null)" ]; then
  echo "[warn] git user.email 미설정 — 커밋 전에 git config user.name / user.email 을 설정하세요."
fi

echo
echo "완료. 다음: 커밋 → codex 실행 → /status, /skills 확인 → 요구사항 문서를 직접 읽고 DISCOVER로."
