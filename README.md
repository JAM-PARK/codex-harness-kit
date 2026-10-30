# codex-harness-kit

[Codex CLI](https://github.com/openai/codex)에서 쓰는 작업 하네스입니다. 담당자 인터뷰 → 합의 → 얇은 E2E → 검증 → 인수인계 흐름과 시간 체크포인트를 `AGENTS.md`와 Agent Skills 4개로 고정합니다.

## 구성

```
kit/
├── AGENTS.md              운영 규칙 (Codex가 작업 공간 루트에서 자동으로 읽음)
└── .agents/
    ├── setup.sh           체크포인트 계산, docs/STATE.md 생성
    ├── CHEATSHEET.md      1장 요약
    └── skills/
        ├── discovery-interview/   담당자 인터뷰
        ├── design-agreement/      합의문 · 최소 설계 · 작업 분해
        ├── verify-loop/           작업 단위 검증과 독립 리뷰
        └── handoff/               인수인계와 이해 점검
```

## 설치 (작업 공간 루트에서)

```bash
git clone --depth 1 https://github.com/JAM-PARK/codex-harness-kit /tmp/h
cp -Rn /tmp/h/kit/.agents ./                # 기존 파일은 덮어쓰지 않음
cat /tmp/h/kit/AGENTS.md >> AGENTS.md       # 없으면 새로 만들고, 있으면 끝에 덧붙임
bash .agents/setup.sh 14:00 120             # 시작 시각, 작업 시간(분), [마감 상한 HH:MM]
codex                                       # /status, /skills 확인
```

- `setup.sh`는 시작 시각과 작업 시간으로 체크포인트를 계산해 `docs/STATE.md`에 적습니다. 마감 상한을 주면 마감이 그 시각을 넘지 않게 줄이고, `STATE.md`가 이미 있으면 덮어쓰지 않습니다.
- 스킬은 `/skills`로 보거나 `$discovery-interview`처럼 부릅니다. 잡히지 않으면 "AGENTS.md와 .agents/skills/<이름>/SKILL.md를 읽고 따라"라고 요청합니다.

## 단계와 체크포인트

| 시점 | 단계 | 끝났다는 증거 |
|---|---|---|
| 15% | 요구사항 파악 · 담당자 인터뷰 | 문제 진술 1문장, 현재 수치, 제약 2개 |
| 23% | 합의 | 담당자 확인을 받은 `docs/AGREEMENT.md` |
| 45% | E2E v0 | 데모 시나리오가 끝까지 돌고 독립 리뷰 1차 완료 |
| 80% | 새 기능 금지 | 독립 리뷰 2차, SC별 실행 증거 |
| 85% | 리뷰 반영 중단 | 문서 마감과 코드 읽기, 이해 점검 |
| 마감 10분 전 | 마감 준비 | 산출물과 `git status` 확인 |
