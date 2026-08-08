# LLM Persona Treatment-Recommendation 평가 웹앱

여러 평가자(reader)가 각자 배정된 시나리오에 대해, 3개 모델(GPT/Claude/Gemini) × 6개 persona = 18개 답변을
5개 항목(1–3점)으로 평가하고, 결과가 Google Sheet 한 곳에 모이도록 만든 정적 웹앱입니다.

- 서버 불필요 (정적 파일 호스팅만 하면 됨)
- 결과 저장은 Google Apps Script Web App을 통해 Google Sheet에 append
- 평가자별 진행 상황은 브라우저 `localStorage`에 저장되어, 여러 세션에 걸쳐 이어서 할 수 있음
- 18개 답변의 노출 순서는 (평가자, 케이스)별로 랜덤이지만 고정 시드로 재현되어, 새로고침해도 순서가 안 바뀜
- 기본값은 **블라인드 평가**: 평가 화면에서는 어느 모델/persona의 답변인지 보이지 않음 (저장되는 데이터에는 당연히 포함됨)

## 1. 폴더 구조

```
webapp/
  index.html         # 화면 구조
  style.css
  app.js              # 모든 로직 + CONFIG (여기서 대부분 커스터마이즈)
  data/
    cases.sample.json        # 샘플 시나리오 2개 (테스트용) — 실데이터로 교체
    assignments.sample.json  # 샘플 평가자 배정 3명 — 실배정으로 교체
  apps-script/
    Code.gs           # Google Sheet에 저장하는 백엔드 (Apps Script)
```

## 2. 로컬에서 먼저 테스트하기

`fetch`로 JSON을 읽기 때문에 `file://`로 열면 브라우저가 막습니다. 반드시 로컬 서버로 열어야 합니다.

```bash
cd webapp
python -m http.server 8080
```

브라우저에서 `http://localhost:8080` 접속 → 평가자 선택(`김OO`/`이OO`/`박OO` 중 하나) → 시작하기 →
시나리오 목록에서 `case_001` 열어서 18개 답변을 다 채워보고 Save까지 눌러보세요.
(아직 `SHEETS_WEBHOOK_URL`을 설정하지 않았다면 "로컬에만 저장되었습니다" 메시지가 뜨는 게 정상입니다 —
브라우저를 닫아도 진행 상황은 `localStorage`에 남아 있습니다.)

## 3. 실데이터 준비 (`data/cases.json`)

**현재 `data/cases.json`은 `Case example.xlsx`(2개 케이스)로부터 자동 생성되어 이미 적용되어 있습니다.**
226개 케이스가 담긴 최종 xlsx가 준비되면 아래 스크립트로 다시 생성하면 됩니다:

```bash
cd webapp
python scripts/convert_cases.py "path/to/전체_케이스.xlsx" data/cases.json
```

- 입력 xlsx는 `Case example.xlsx`와 동일한 컬럼 구조(`case_no, case_scenario, case_answer, model, persona, recommendation`)여야 합니다.
- `case_no`/`case_scenario`/`case_answer`는 각 케이스의 첫 행에만 채워져 있고 나머지 17행은 비어 있어도 됩니다(엑셀 병합 셀 형태) — 스크립트가 자동으로 forward-fill 합니다.
- `model`은 `gpt/claude/gemini`(대소문자 무관) → `GPT/Claude/Gemini`로 자동 변환됩니다.
- `persona`는 고정 6개 라벨(`constrain, secure, lit_low, lit_high, soc_low, soc_high`)이어야 하며, 케이스당 정확히 18행(3 모델 × 6 persona)이 아니거나 라벨 오탈자가 있으면 실행 후 **WARNING**으로 출력됩니다 — 반드시 warning 없는 상태로 만들고 배포하세요.
- 실행 후 `python scripts/convert_cases.py ...` 출력의 `WARNINGS` 섹션을 꼭 확인하세요 (빈 텍스트, 18개가 아닌 답변 수, 중복 model/persona 조합 등을 잡아줍니다).

수동으로 JSON을 작성해야 한다면 아래 스키마를 따르면 됩니다 (`data/cases.sample.json` 참고):

```jsonc
{
  "models": ["GPT", "Claude", "Gemini"],
  "personas": ["constrain", "secure", "lit_low", "lit_high",
               "soc_low", "soc_high"],
  "cases": [
    {
      "id": "case_001",           // 고유 ID (필수, 유일해야 함)
      "source": "MedQA",          // 참고용, 자유
      "description": "...",       // 시나리오 (상단 고정 표시)
      "ground_truth": "...",      // 정답 (상단 고정 표시)
      "answers": [                // 정확히 18개 (model×persona 전 조합)
        { "model": "GPT", "persona": "constrain", "text": "..." },
        // ... 총 18개
      ]
    }
    // ... 총 226개 case
  ]
}
```

주의:
- `answers` 배열은 반드시 18개(3 models × 6 personas 전 조합)여야 합니다. 개수가 다르면 콘솔에 경고가 뜹니다.
- `id`는 Sheet에 그대로 저장되니 사람이 알아보기 쉬운 값(`case_001` 등)을 권장합니다.

## 4. 평가자 배정 준비 (`data/assignments.json`)

**현재 `data/assignments.json`에 샘플 평가자 3명(`eval_kim`/`eval_lee`/`eval_park`)이 `case_001`,
`case_002`에 배정되어 있습니다.** 226개 케이스와 실제 평가자 명단이 확정되면 이 파일을 그 내용으로 교체하세요.

```jsonc
{
  "evaluators": {
    "evaluator_id_1": { "name": "표시용 이름", "case_ids": ["case_001", "case_007", "..."] },
    "evaluator_id_2": { "name": "...", "case_ids": ["..."] }
  }
}
```

- 평가자별로 배정할 `case_ids` 목록을 자유롭게 구성하면 됩니다 (전량 배정도, 일부만 배정도 가능).
- 신뢰도(inter-rater reliability) 확인을 위해 일부 케이스를 2명 이상에게 겹쳐서 배정하는 것을 권장합니다.
- 완성 후 `data/assignments.json`으로 저장하고 `app.js`의 `CONFIG.ASSIGNMENTS_URL`을 `"data/assignments.json"`으로 변경하세요.
- 로그인 화면에 비밀번호는 없습니다(내부용 도구 전제). 필요하면 evaluator_id 자체를 짐작하기 어려운 문자열로 만드세요.

## 5. Google Sheets 백엔드 배포

1. 새 Google Sheet 생성.
2. 확장 프로그램 > Apps Script.
3. 기본 코드를 지우고 `apps-script/Code.gs` 내용을 붙여넣기.
4. (권장) 프로젝트 설정 > 스크립트 속성에 `SECRET_TOKEN` 키로 임의의 문자열 값 추가.
   → `app.js`의 `CONFIG.SHARED_SECRET`에 동일한 값을 넣으세요. (완전한 인증은 아니지만 URL만 아는 사람의 무단 제출을 막아줍니다.)
5. 배포 > 새 배포 > 유형: 웹 앱
   - 실행 계정: 나
   - 액세스 권한: **모든 사용자** (Google 로그인 없이 evaluator 브라우저에서 POST해야 하므로 필요합니다)
6. 배포 후 나오는 **웹 앱 URL**을 복사해서 `app.js`의 `CONFIG.SHEETS_WEBHOOK_URL`에 붙여넣기.
7. `Code.gs`를 수정할 때마다 "배포 관리 > 편집 > 새 버전"으로 재배포해야 반영됩니다.

시트에는 `Ratings`라는 탭이 자동 생성되고, 한 번 제출할 때마다 18개 행(모델×persona 조합별 1행)이 추가됩니다.
컬럼: `server_timestamp, evaluator_id, evaluator_name, case_id, model, persona, display_order_index, medical_appropriateness, treatment_intensity, urgency_estimation, care_setting, harmfulness, submitted_at`

→ 이후 Google Sheets에서 피벗 테이블로 `model` × `persona`별 평균/분포를 바로 집계할 수 있습니다.

## 6. 정적 사이트 호스팅

`webapp/` 폴더 전체(단, `apps-script/`는 배포 대상 아님, `Code.gs`는 Apps Script 쪽에만 있으면 됨)를
GitHub Pages, Netlify, Vercel, 사내 웹서버 등 아무 정적 호스팅에 업로드하면 됩니다. 평가자들에게 그 URL만 공유하면 됩니다.

## 7. 커스터마이즈 포인트 (`app.js` 상단 `CONFIG`)

- `SHOW_MODEL_PERSONA`: `true`로 바꾸면 평가 화면에 모델/persona가 그대로 노출됨 (기본은 블라인드).
- `CRITERIA`: 5개 평가 항목의 라벨/설명 문구를 자유롭게 수정 가능 (1/2/3점 의미는 연구팀 rubric에 맞게 다시 쓰는 것을 권장).
- `SHEETS_WEBHOOK_URL`, `SHARED_SECRET`: 위 5단계에서 얻은 값.

## 8. 평가자 사용 흐름

1. 로그인 화면에서 본인 ID 선택 → 시작하기
2. **최초 로그인 시에만** 평가 안내 화면(3페이지: 시나리오/LLM 답변/평가 목적 → 평가 항목 5가지 → 가상 예시로 채점 연습)이 뜸 → "평가 시작하기" 클릭 시 다시 안 뜨고 바로 대시보드로 이동 (브라우저 `localStorage`에 평가자별로 기억됨). 대시보드의 "평가 안내 다시보기" 버튼으로 언제든 다시 볼 수 있음
3. 대시보드에서 배정된 케이스 중 하나 선택 (미시작/진행중/제출완료 표시됨)
4. 상단 고정된 시나리오+정답을 보며, 아래 답변 1개씩 5개 항목 평가
5. 18개 답변 진행 상황은 상단 그리드에서 바로 확인/이동 가능 (완료된 답변은 초록색)
6. 다음(Next)으로 넘어가며 계속 평가, 중간에 브라우저를 닫아도 다음 접속 시 이어서 가능
7. 18개를 모두 채우면 Save(전체 저장) 버튼이 활성화 → 클릭 시 Google Sheet로 전송하고 자동으로 다음 미완료 케이스로 이동
8. 배정된 케이스를 모두 마치면 대시보드로 돌아감

## 9. 다음 단계 (별도 작업)

이 웹앱은 **평가 도구**만 다룹니다. MedQA/KorMedQA 기반 226개 시나리오 생성과, GPT/Claude/Gemini API를 6개
persona 프롬프트로 호출해 18개 답변을 만드는 **데이터 생성 파이프라인**은 별도 작업입니다. 진행하시려면
OpenAI/Google/Anthropic API 키와 MedQA/KorMedQA 데이터셋 접근 방법을 알려주세요.
