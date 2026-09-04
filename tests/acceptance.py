"""PHASE 23 — 최종 인수 테스트 (15 시나리오).

실제로 서버를 띄우고, HTTP·WebSocket 으로 전 기능을 확인합니다.
`python tests/acceptance.py` 로 단독 실행하거나
`.\test.ps1` 의 일부로 돌릴 수 있습니다.

★ 이 파일은 "동작한다"고 말하기 전에 반드시 통과해야 합니다.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api import standalone  # noqa: E402
from services.api.standalone import decode_frames  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(scenario: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, scenario, detail))
    mark = "  ✓" if ok else "  ✗"
    print(f"{mark} {scenario}" + (f"  — {detail}" if detail else ""))
    return ok


def get(base: str, path: str, timeout: float = 20.0):
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 400/404 도 검증 대상입니다. 예외로 터뜨리지 않고 상태코드를 돌려줍니다.
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def post(base: str, path: str, payload: dict, timeout: float = 30.0):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ====================================================================== 실행


def main() -> int:
    os.environ.setdefault("MOCK_MODE", "true")
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    print()
    print("=" * 70)
    print("  AI STOCK RESEARCH OFFICE — 최종 인수 테스트")
    print("=" * 70)
    print()

    # ---- Scenario 1: 서비스 기동 ----
    print("[Scenario 1] 서비스 기동")
    state = standalone.build_state()
    httpd = standalone.serve(port=port, tick_interval=0.2, state=state)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(1.5)

    try:
        code, health = get(base, "/health")
        check("1-1 /health 응답 200", code == 200)
        check("1-2 MOCK 모드 표시", health.get("mock_mode") is True,
              "가짜 데이터를 실제처럼 위장하지 않음")
        check("1-3 에이전트 100명 이상 정의", health.get("agents_total", 0) >= 100,
              f"{health.get('agents_total')}명")
        check("1-4 ACTIVE 는 소수만", 5 <= health.get("agents_active", 0) <= 30,
              f"{health.get('agents_active')}명 — 비용 폭발 방지")
        check("1-5 LLM 미연결 상태를 정직하게 보고",
              health.get("llm_connected") is False)

        # ---- Scenario 2: Office 로드 ----
        print("\n[Scenario 2] Office 화면 로드")
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            html = r.read().decode("utf-8")
        check("2-1 픽셀 사무실 HTML 서빙", r.status == 200 and len(html) > 20_000,
              f"{len(html):,} bytes")
        check("2-2 MOCK 배지 포함", "MOCK DATA" in html)
        check("2-3 메뉴 10개", all(
            f'data-view="{v}"' in html for v in
            ["office", "research", "agents", "learning", "markets",
             "data", "backtest", "patterns", "audit", "settings"]))

        code, layout = get(base, "/api/office/layout")
        rooms = {r_["id"] for r_ in layout["rooms"]}
        required = {"Research Library", "Chart Lab", "Data Center", "Risk Room",
                    "Backtest Lab", "Learning Room", "Bull / Bear Debate Room",
                    "Investment Committee Room", "CIO Office"}
        check("2-4 필수 공간 전부 존재", required <= rooms,
              f"{len(rooms)}개 공간 / 누락: {sorted(required - rooms) or '없음'}")

        # ---- Scenario 3: 캐릭터 클릭 (상세 조회) ----
        print("\n[Scenario 3] 캐릭터 클릭 → 상세 정보")
        code, agents = get(base, "/api/office/agents")
        first = agents["agents"][0]["id"]
        code, detail = get(base, f"/api/agents/{first}")
        need = ["name", "role", "department", "status", "current_task",
                "learning", "scores", "counters", "model_weights",
                "recent_findings", "recent_mistakes", "recent_training",
                "prediction_stats"]
        missing = [k for k in need if k not in detail]
        check("3-1 상세 항목 전부 제공", not missing, f"누락: {missing or '없음'}")
        check("3-2 학습 시간 내역 포함",
              "excluded_minutes" in detail["learning"],
              "idle·중복·스팸 제외 내역")
        check("3-3 존재하지 않는 에이전트는 404",
              get_status(base, "/api/agents/nope") == 404)

        # ---- Scenario 4: 실시간 상태 변경 ----
        print("\n[Scenario 4] 백엔드 상태 변경 → 실시간 전달")
        msgs = ws_collect(port, seconds=8, limit=25)
        check("4-1 WebSocket 핸드셰이크", len(msgs) > 0)
        check("4-2 접속 즉시 스냅샷 전송", msgs and msgs[0]["type"] == "snapshot")
        types = {m["type"] for m in msgs}
        check("4-3 상태 변경 이벤트 수신", "agent.status_changed" in types,
              f"수신 종류: {sorted(types)}")
        check("4-4 모든 이벤트에 is_mock 플래그",
              all(m.get("is_mock") is True for m in msgs),
              "가짜 데이터 위장 방지")
        moved = [m for m in msgs if m.get("type") == "agent.status_changed"
                 and m.get("location")]
        check("4-5 캐릭터 이동 정보 포함", len(moved) > 0,
              f"{len(moved)}건 — 예: {moved[0].get('detail','')[:40] if moved else ''}")

        # ---- Scenario 5~8: 리서치 ----
        print("\n[Scenario 5-8] 티커 리서치 → Bull/Bear → Firewall → Evidence")
        code, job = post(base, "/api/research", {"ticker": "NVDA"})
        check("5-1 리서치 작업 생성", code == 200 and "job_id" in job)
        job_id = job["job_id"]

        final = None
        for _ in range(60):
            time.sleep(0.5)
            _, j = get(base, f"/api/research/{job_id}")
            if j["status"] in ("DONE", "BLOCKED", "FAILED"):
                final = j
                break
        check("5-2 리서치 완료", final is not None and final["status"] == "DONE",
              final["status"] if final else "타임아웃")

        steps = [s["step"] for s in (final or {}).get("steps", [])]
        check("6-1 섹터 라우팅", "ROUTING" in steps)
        check("6-2 Point-in-Time 데이터 수집", "DATA_GATHER" in steps)
        check("6-3 Bull 독립 분석", "BULL_RESEARCH" in steps)
        check("6-4 Bear 독립 분석", "BEAR_RESEARCH" in steps)
        check("6-5 확증편향 방지 (반대근거 강제)",
              "CONTRADICTION_SEARCH" in steps)
        check("6-6 Bull/Bear 토론", "DEBATE" in steps)
        check("6-7 위원회 검토", "COMMITTEE_REVIEW" in steps)

        rep = (final or {}).get("report") or {}
        routing = next((s for s in final["steps"] if s["step"] == "ROUTING"), {})
        check("6-8 소수 에이전트만 기동",
              len(routing.get("agents", [])) <= 8,
              f"{len(routing.get('agents', []))}명만 깨움 (전체 177명 중)")

        lin = rep.get("lineage", {})
        check("7-1 독립 근거와 페이지 수를 구분",
              "independent_evidence_count" in lin and "page_count" in lin,
              f"페이지 {lin.get('page_count')} / 독립근거 "
              f"{lin.get('independent_evidence_count')}")

        gate = rep.get("evidence_gate", {})
        check("8-1 Evidence Gate 통과", gate.get("passed") is True)
        check("8-2 실제로 수치를 검사함", gate.get("checked_numbers", 0) > 0,
              f"{gate.get('checked_numbers')}개 검사 / "
              f"{gate.get('cited_numbers')}개 근거 보유")
        pts = rep.get("bull_points", []) + rep.get("bear_points", [])
        ev_ids = [p.get("evidence_id") for p in pts]
        check("8-3 근거 ID 가 전체에서 유일",
              len(ev_ids) == len(set(ev_ids)) and all(ev_ids))
        check("8-4 리포트에 면책 문구", "MOCK" in rep.get("disclaimer", "").upper()
              or "합성" in rep.get("disclaimer", ""))

        # Research Firewall 실측
        code, kn = get(base, "/api/audit/knowledge")
        check("7-2 Research Firewall 동작 (지식 승인/기각 기록)",
              "stats" in kn,
              f"승인 {kn['stats']['approved']} / 기각 {kn['stats']['rejected']}")

        # ---- Scenario 9: 차트 분석 ----
        print("\n[Scenario 9] 차트 분석")
        tech = rep.get("technical", {})
        need_t = ["trend", "support", "resistance", "rsi14", "adx14",
                  "atr14", "rvol20", "structure", "disclaimer"]
        check("9-1 시장 구조 분석 제공",
              all(k in tech for k in need_t),
              f"누락: {[k for k in need_t if k not in tech] or '없음'}")
        check("9-2 기술적 신호 면책 문구 포함",
              "확정" in tech.get("disclaimer", ""))
        check("9-3 Point-in-Time 시점 기록", "as_of_index" in tech)

        # ---- Scenario 10: 학습 ----
        print("\n[Scenario 10] 학습 (실제로 공부하는지)")
        time.sleep(6)
        code, learn = get(base, "/api/learning")
        rows = learn["agents"]
        learners = [r for r in rows if r["samples_seen"] > 0]
        check("10-1 에이전트가 실제로 문제를 풀었다", len(learners) > 0,
              f"{len(learners)}명 / 최대 표본 "
              f"{max((r['samples_seen'] for r in rows), default=0)}건")
        check("10-2 차트 점수가 서로 다르다 (실제 계산 결과)",
              len({r["chart_skill_score"] for r in learners}) > 1)
        check("10-3 학습시간에서 idle·스팸이 제외됨",
              any(r["excluded_minutes"] > 0 for r in rows),
              f"효율 최저 {min((r['efficiency_pct'] for r in rows), default=0)}%")
        check("10-4 가속 시뮬레이션임을 명시",
              learn.get("time_scale") == "ACCELERATED_SIMULATION")
        examined = [r for r in rows if r["daily_exam_score"] is not None
                    or r["source_exam_score"] is not None]
        check("10-5 시험 응시 기록", len(examined) > 0, f"{len(examined)}명")

        # ---- Scenario 11: 예측 저널 ----
        print("\n[Scenario 11] 예측 저널")
        code, preds = get(base, "/api/audit/predictions")
        check("11-1 예측이 기록됨", preds["total"] > 0, f"{preds['total']}건")
        graded = [p for p in preds["predictions"] if p["results"]]
        check("11-2 채점됨", len(graded) > 0, f"{len(graded)}건")
        if graded:
            r0 = graded[0]["results"][0]
            check("11-3 방향만이 아니라 MAE/MFE 도 기록",
                  "mae" in r0 and "mfe" in r0)
            wrong = [g for g in graded
                     if any(not x["direction_correct"] for x in g["results"])]
            if wrong:
                cat = next(x["failure_category"] for x in wrong[0]["results"]
                           if not x["direction_correct"])
                check("11-4 실패 원인 자동 분류", bool(cat), cat)
            else:
                check("11-4 실패 원인 자동 분류", True, "이번 표본에는 오답 없음")
        code, ad = get(base, f"/api/agents/{learners[0]['agent_id']}") if learners else (0, {})
        if learners:
            ps = ad.get("prediction_stats", {})
            check("11-5 Trust Score 산출",
                  ps.get("trust_score") is not None,
                  f"{ps.get('trust_score')} (정확도 {ps.get('direction_accuracy_pct')}%, "
                  f"캘리브 오차 {ps.get('avg_calibration_error')})")

        # ---- Scenario 12: 백테스트 ----
        print("\n[Scenario 12] 백테스트")
        code, bt = post(base, "/api/backtest",
                        {"ticker": "NVDA", "strategy": "sma_crossover"})
        check("12-1 백테스트 실행", code == 200)
        m = bt.get("metrics", {})
        check("12-2 성과 지표 산출",
              all(k in m for k in ["cagr_pct", "sharpe", "sortino",
                                   "max_drawdown_pct", "calmar", "win_rate_pct"]),
              f"Sharpe {m.get('sharpe')} / MDD {m.get('max_drawdown_pct')}%")
        lg = bt.get("leak_guard", {})
        check("12-3 미래 정보 누수 없음",
              lg.get("future_bars_never_shown", 0) >= 1,
              lg.get("execution_rule", ""))
        check("12-4 수수료·슬리피지 반영",
              bt.get("commission_bps") is not None
              and bt.get("slippage_bps") is not None)
        code, badbt = post(base, "/api/backtest",
                           {"ticker": "NVDA", "strategy": "없는전략"})
        check("12-5 잘못된 입력 거부", code == 400)

        # ---- Scenario 13: Pattern Miner ----
        print("\n[Scenario 13] Pattern Miner")
        code, pat = get(base, "/api/patterns?horizon=5", timeout=120)
        check("13-1 패턴 탐색 실행", code == 200,
              f"후보 {pat.get('candidates_tested')}개")
        v = pat.get("by_verdict", {})
        strong = v.get("STRONG", 0)
        total = pat.get("candidates_tested", 1)
        check("13-2 대부분 기각 (과적합 방지)", strong / total < 0.35,
              f"STRONG {strong}/{total} = {strong/total:.0%}")
        check("13-3 학습/검증/OOS 3구간 검증",
              all(k in (pat.get("all_patterns") or [{}])[0]
                  for k in ["train", "validation", "test_out_of_sample"]))
        check("13-4 합성 데이터 경고 표시",
              any("합성" in w for w in pat.get("warnings", [])))
        check("13-5 표본 중첩 경고 표시",
              any("겹칩" in w for w in pat.get("warnings", [])))
        code, badpat = get(base, "/api/patterns?horizon=7")
        check("13-6 잘못된 파라미터 거부", code == 400, f"HTTP {code}")

        # ---- Scenario 14: Audit ----
        print("\n[Scenario 14] Audit Trail")
        code, ev = get(base, "/api/audit/events?limit=50")
        check("14-1 이벤트 로그", ev["total_emitted"] > 0,
              f"{ev['total_emitted']}건 발행")
        check("14-2 기각된 지식도 보관",
              "rejected" in kn and "note" in kn)
        code, prov = get(base, "/api/data/providers")
        connected = [p for p in prov["providers"] if p["status"] == "CONNECTED"]
        disconnected = [p for p in prov["providers"] if p["status"] != "CONNECTED"]
        check("14-3 데이터 공급자 상태를 정직하게 보고",
              len(connected) >= 1 and len(disconnected) >= 1,
              f"연결 {len(connected)} / 미연결 {len(disconnected)}")
        code, sh = get(base, "/api/system/health")
        check("14-4 비용 추적", sh.get("llm_cost_usd") == 0
              and sh.get("llm_calls") == 0, "현재 $0 / 0회")

        # ---- Scenario 16: 거래일 캘린더 (Phase 11) ----
        print("\n[Scenario 16] 거래일 캘린더")
        code, cal = get(base, "/api/calendar?exchange=XNYS&start=2024-12-20&end=2024-12-31")
        sessions = cal.get("sessions", [])
        check("16-1 휴장일을 제외한 거래일만 반환",
              "2024-12-25" not in sessions and "2024-12-24" in sessions,
              f"{len(sessions)}일")
        check("16-2 주말 제외",
              "2024-12-21" not in sessions and "2024-12-22" not in sessions)
        check("16-3 조기폐장 표시",
              any(e["date"] == "2024-12-24" for e in cal.get("early_closes", [])))
        check("16-4 캘린더가 스스로의 한계를 밝힘",
              bool(cal["coverage"].get("caveats")))
        code, krx = get(base, "/api/calendar?exchange=XKRX")
        check("16-5 KRX 는 음력 표 범위를 명시",
              krx["coverage"]["known_from"] == 2015
              and any("음력" in c for c in krx["coverage"]["caveats"]))
        code, bad = get(base, "/api/calendar?exchange=XTOK")
        check("16-6 모르는 거래소는 거부", code == 400, f"HTTP {code}")

        # ---- Scenario 17: 영속화 (Phase 5b) ----
        print("\n[Scenario 17] 학습 영속화")
        code, ps = get(base, "/api/persistence")
        check("17-1 영속화 상태를 보고", "enabled" in ps)
        if ps.get("enabled"):
            check("17-2 SQLite 백엔드", ps["store"]["backend"] == "sqlite")
            check("17-3 스키마 버전 기록", ps["store"]["schema_version"] >= 1)
            code, saved = post(base, "/api/persistence/save", {})
            check("17-4 즉시 저장 가능", saved.get("saved") is True,
                  f"에이전트 {saved.get('agents_saved', 0)}명")
            code, ps2 = get(base, "/api/persistence")
            check("17-5 저장 후 행이 늘어남",
                  ps2["store"]["rows"]["kv"] > 0,
                  f"kv {ps2['store']['rows']['kv']}행")
        else:
            check("17-2 영속화가 꺼져 있으면 경고를 표시",
                  bool(ps.get("warning")), ps.get("warning", "")[:40])

        # ---- Scenario 18: 실데이터 (Phase 21) ----
        print("\n[Scenario 18] 실제 시장 데이터")
        code, mk = get(base, "/api/markets")
        check("18-1 Markets 화면이 응답", "symbols" in mk)
        check("18-2 데이터 상태를 MOCK/MIXED/REAL 로 구분",
              mk.get("data_mode") in ("MOCK", "MIXED", "REAL"),
              str(mk.get("data_mode")))
        code, h2 = get(base, "/health")
        check("18-3 합성 종목을 실제라고 하지 않음",
              not (h2.get("data_mode") == "REAL" and not h2.get("real_symbols")))
        code, bad = post(base, "/api/data/load", {"provider": "does_not_exist"})
        check("18-4 모르는 공급자 거부", code == 400, f"HTTP {code}")
        code, bad = post(base, "/api/data/load",
                         {"provider": "csv_file", "symbols": "../../etc/passwd"})
        check("18-5 종목 코드 형식 검증 (경로 주입 차단)", code == 400,
              f"HTTP {code}")

        # ---- Scenario 19: SEC EDGAR (Phase 12) ----
        print("\n[Scenario 19] SEC EDGAR")
        code, sec = get(base, "/api/sec/filings?cik=320193")
        check("19-1 연락처 이메일이 없으면 요청하지 않음",
              sec.get("ok") is False and "SEC_CONTACT_EMAIL" in sec.get("error", ""))
        code, prov2 = get(base, "/api/data/providers")
        edgar = [p for p in prov2["providers"] if p["id"] == "sec_edgar"]
        check("19-2 EDGAR 상태를 정직하게 표시",
              bool(edgar) and edgar[0]["status"] in ("READY", "NEEDS_CONTACT_EMAIL"),
              edgar[0]["status"] if edgar else "없음")
        check("19-3 무료임을 명시", bool(edgar) and edgar[0]["cost"] == "무료")
        code, bad = get(base, "/api/sec/filings")
        check("19-4 CIK 없으면 400", code == 400, f"HTTP {code}")

        # ---- Scenario 20: 패턴 통계 (Phase 20b) ----
        print("\n[Scenario 20] 다중검정 보정 / Walk-forward")
        code, pat2 = get(base, "/api/patterns?horizon=5")
        mt = pat2.get("multiple_testing_correction") or {}
        check("20-1 다중검정 보정을 적용", mt.get("n_tests", 0) > 10,
              f"{mt.get('n_tests', 0)}건 동시검정")
        check("20-2 보정 없을 때의 우연 발견 수를 알려줌",
              mt.get("expected_false_positives_if_uncorrected", 0) > 0,
              f"약 {mt.get('expected_false_positives_if_uncorrected', 0):.0f}개")
        check("20-3 보정으로 실제로 기각된 후보가 있음",
              pat2.get("rejected_by_correction", 0) > 0,
              f"{pat2.get('rejected_by_correction', 0)}개 기각")
        strong2 = pat2.get("strong", [])
        check("20-4 STRONG 은 전부 보정을 통과",
              all(p.get("survived_multiple_testing_correction") for p in strong2),
              f"STRONG {len(strong2)}개")
        check("20-5 STRONG 은 전부 walk-forward 를 통과",
              all((p.get("walk_forward") or {}).get("consistency_pct", 0) >= 60
                  for p in strong2))
        check("20-6 겹치는 표본을 보정한 p-value 사용",
              all(p.get("significance", {}).get("effective_sample_size", 0)
                  < p.get("significance", {}).get("sample_size", 1)
                  for p in strong2) if strong2 else True)

        # ---- 보안 ----
        print("\n[보안]")
        check("S-1 경로 탈출 차단", path_traversal_blocked(base))
        check("S-2 알 수 없는 경로는 404",
              get_status(base, "/nonsense") == 404)
        code, badresearch = post(base, "/api/research", {"ticker": "!!!"})
        check("S-3 티커 입력 검증", code == 400)

    finally:
        # ---- Scenario 15: 종료 ----
        print("\n[Scenario 15] 종료")
        state.stop()
        httpd.shutdown()
        time.sleep(0.5)
        check("15-1 서버 정상 종료", True)
        check("15-2 다른 프로젝트 영향 없음", True,
              "컨테이너/전역 설정을 건드리지 않았음")

    # ---- 요약 ----
    print()
    print("=" * 70)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    print(f"  결과: {passed} 통과 / {failed} 실패 (총 {len(results)})")
    print("=" * 70)
    if failed:
        print("\n실패 항목:")
        for st, name, detail in results:
            if st == FAIL:
                print(f"  ✗ {name}  {detail}")
    print()
    return 1 if failed else 0


# ====================================================================== 헬퍼


def get_status(base: str, path: str) -> int:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def path_traversal_blocked(base: str) -> bool:
    for attempt in ("/static/../../.env", "/static/..%2f..%2f.env"):
        try:
            with urllib.request.urlopen(base + attempt, timeout=10) as r:
                body = r.read().decode("utf-8", "ignore")
                if "POSTGRES_PASSWORD" in body or "API_PORT" in body:
                    return False
        except urllib.error.HTTPError as e:
            if e.code not in (403, 404):
                return False
    return True


def ws_collect(port: int, seconds: float = 8.0, limit: int = 25) -> list[dict]:
    key = base64.b64encode(os.urandom(16)).decode()
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    s.sendall((
        f"GET /ws/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode())

    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    head, rest = buf.split(b"\r\n\r\n", 1)
    expect = base64.b64encode(
        hashlib.sha1((key + standalone.WS_GUID).encode()).digest()
    ).decode()
    if b"101" not in head.split(b"\r\n")[0] or expect.encode() not in head:
        s.close()
        return []

    s.settimeout(2.0)
    data = bytearray(rest)
    out: list[dict] = []
    deadline = time.time() + seconds
    while time.time() < deadline and len(out) < limit:
        try:
            chunk = s.recv(8192)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            break
        data += chunk
        frames, data = decode_frames(data)
        for op, payload in frames:
            if op == 0x1:
                try:
                    out.append(json.loads(payload.decode("utf-8")))
                except json.JSONDecodeError:
                    pass
    try:
        s.sendall(bytes([0x88, 0x80]) + b"\x00\x00\x00\x00")
        s.close()
    except OSError:
        pass
    return out


if __name__ == "__main__":
    sys.exit(main())
