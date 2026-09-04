"""에이전트 레지스트리 · 라우터 · 런타임 엔진 통합 테스트.

특히 '실수로 177명 전부 깨워서 API 비용 폭발' 을 코드가 막는지 확인합니다.
"""

import asyncio
import unittest
from pathlib import Path

from packages.agent_registry import AgentRegistry, AgentStatus, Role, Router
from packages.agent_registry.models import AgentProfile
from packages.shared import yamlio
from packages.shared.config import Settings, parse_env_file
from packages.shared.logging import mask_event, mask_text
from services.agent_runtime.engine import Engine

CONFIG = Path(__file__).resolve().parents[1] / "config"


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = AgentRegistry.from_config(CONFIG)

    def test_loads_many_agents(self):
        self.assertGreaterEqual(len(self.reg.all()), 100)

    def test_ids_unique(self):
        ids = [a.id for a in self.reg.all()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_active_subset_is_small(self):
        """정의는 많아도 실제로 일하는 사람은 소수여야 합니다 (§62)."""
        active = self.reg.active()
        self.assertGreaterEqual(len(active), 10)
        self.assertLessEqual(len(active), 25)

    def test_every_sector_has_lead_bull_bear(self):
        for sector in self.reg.sectors():
            roles = {a.role for a in self.reg.by_sector(sector)}
            self.assertIn(Role.SECTOR_LEAD, roles, sector)
            self.assertIn(Role.BULL_RESEARCHER, roles, sector)
            self.assertIn(Role.BEAR_RESEARCHER, roles, sector)

    def test_all_sector_agents_have_common_chart_skill(self):
        """모든 섹터 에이전트는 차트 스킬을 기본 장착합니다 (§14)."""
        for a in self.reg.all():
            if a.role in (Role.SECTOR_LEAD, Role.BULL_RESEARCHER, Role.BEAR_RESEARCHER):
                self.assertIn("common_chart_skill", a.skills, a.id)

    def test_no_real_model_name_in_profiles(self):
        """프로필에 실제 모델명을 박으면 모델 독립성이 깨집니다 (§51)."""
        allowed = {"tier_strong", "tier_mid", "tier_cheap", "code_only"}
        for a in self.reg.all():
            self.assertIn(a.model_policy.default.value, allowed, a.id)
            self.assertIn(a.model_policy.cheap_tasks.value, allowed, a.id)

    def test_bull_and_bear_have_opposite_priors(self):
        bull = self.reg.get("semiconductor_bull")
        bear = self.reg.get("semiconductor_bear")
        self.assertIsNotNone(bull)
        self.assertIsNotNone(bear)
        self.assertGreater(bull.role_prior, 0)
        self.assertLess(bear.role_prior, 0)

    def test_duplicate_id_rejected(self):
        reg = AgentRegistry()
        p = AgentProfile.parse({"id": "x", "name": "X", "department": "D",
                                "role": "SPECIALIST"})
        reg.add(p)
        with self.assertRaises(ValueError):
            reg.add(p)

    def test_bad_role_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            AgentProfile.parse({"id": "x", "name": "X", "department": "D",
                                "role": "NOT_A_ROLE"})
        self.assertIn("role", str(ctx.exception))

    def test_missing_required_field(self):
        with self.assertRaises(ValueError):
            AgentProfile.parse({"name": "X", "department": "D", "role": "CIO"})


class TestRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = AgentRegistry.from_config(CONFIG)
        cls.router = Router(cls.reg, max_agents=8)

    def test_selects_only_a_few(self):
        """★ 비용 폭발 방지의 핵심."""
        chosen = self.router.select_for_research("semiconductor")
        self.assertLessEqual(len(chosen), 8)
        self.assertLess(len(chosen), len(self.reg.all()) / 5)

    def test_selects_only_active(self):
        for a in self.router.select_for_research("semiconductor"):
            self.assertEqual(a.status, AgentStatus.ACTIVE)

    def test_includes_bull_and_bear(self):
        roles = {a.role for a in self.router.select_for_research("semiconductor")}
        self.assertIn(Role.BULL_RESEARCHER, roles)
        self.assertIn(Role.BEAR_RESEARCHER, roles)

    def test_guard_blocks_mass_wakeup(self):
        with self.assertRaises(RuntimeError):
            self.router.wake_count_guard(self.reg.all())

    def test_inactive_sector_selects_only_shared(self):
        chosen = self.router.select_for_research("quantum")
        for a in chosen:
            self.assertIsNone(a.sector)


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(config_dir=CONFIG, mock_mode=True, seed=3)

    def test_starts_clean(self):
        h = self.engine.system_health()
        self.assertTrue(h["mock_mode"])
        self.assertEqual(h["llm_calls"], 0)
        self.assertGreater(h["agents_total"], 100)

    def test_ticks_produce_events(self):
        before = self.engine.bus.total_emitted
        for _ in range(5):
            self.engine.tick()
        self.assertGreater(self.engine.bus.total_emitted, before)

    def test_every_event_carries_is_mock(self):
        """가짜 데이터를 실제처럼 보이게 하지 않습니다 (§63)."""
        for _ in range(5):
            self.engine.tick()
        for ev in self.engine.bus.recent(200):
            self.assertIn("is_mock", ev, ev)
            self.assertTrue(ev["is_mock"])

    def test_agents_actually_learn_over_ticks(self):
        for _ in range(30):
            self.engine.tick()
        learners = [
            st for st in self.engine.states.values()
            if st.profile.status == AgentStatus.ACTIVE and st.model.samples_seen > 0
        ]
        self.assertTrue(learners, "학습한 에이전트가 하나도 없습니다")
        self.assertTrue(any(st.chart_exercises > 0 for st in learners))

    def test_effective_time_excludes_idle(self):
        for _ in range(30):
            self.engine.tick()
        any_wasted = any(
            st.tracker.wasted_seconds > 0 for st in self.engine.states.values()
        )
        self.assertTrue(any_wasted, "idle/스팸이 학습시간에서 제외되지 않았습니다")
        for st in self.engine.states.values():
            d = st.tracker.to_dict()
            self.assertLessEqual(d["progress_pct"], 100.0)

    def test_registered_agents_never_run(self):
        for _ in range(20):
            self.engine.tick()
        for st in self.engine.states.values():
            if st.profile.status != AgentStatus.ACTIVE:
                self.assertEqual(st.model.samples_seen, 0, st.profile.id)
                self.assertEqual(st.sources_read, 0, st.profile.id)

    def test_health_reports_simulated_time_honestly(self):
        h = self.engine.system_health()
        self.assertEqual(h["time_scale"], "ACCELERATED_SIMULATION")

    def test_research_job_completes_and_passes_gate(self):
        async def run():
            job = self.engine.create_research_job("NVDA")
            return await self.engine.run_research(job["job_id"])

        job = asyncio.run(run())
        self.assertEqual(job["status"], "DONE")
        r = job["report"]
        self.assertIn(r["verdict"], ("BULLISH", "BEARISH", "NEUTRAL"))
        self.assertTrue(r["evidence_gate"]["passed"])
        # 리포트에 실제로 검사할 숫자가 있어야 게이트가 의미가 있습니다
        self.assertGreater(r["evidence_gate"]["checked_numbers"], 0)

    def test_evidence_ids_are_globally_unique(self):
        async def run():
            job = self.engine.create_research_job("AMD")
            return await self.engine.run_research(job["job_id"])

        job = asyncio.run(run())
        pts = job["report"]["bull_points"] + job["report"]["bear_points"]
        ids = [p["evidence_id"] for p in pts]
        self.assertEqual(len(ids), len(set(ids)))

    def test_evidence_gate_blocks_report_missing_citations(self):
        """★ 근거를 빼면 리포트가 실제로 발행되지 않아야 합니다.

        게이트가 '경고만 하고 통과'시키면 있으나 마나입니다.
        """
        original = self.engine._compose_report

        def stripped(*args, **kwargs):
            import re

            return re.sub(r"\s*\[E:[^\]]+\]", "", original(*args, **kwargs))

        self.engine._compose_report = stripped  # type: ignore[assignment]

        async def run():
            job = self.engine.create_research_job("TSM")
            return await self.engine.run_research(job["job_id"])

        job = asyncio.run(run())
        self.assertEqual(job["status"], "BLOCKED")
        self.assertTrue(job["report"]["blocked"])
        self.assertFalse(job["report"]["gate"]["passed"])
        self.assertTrue(job["report"]["gate"]["offenders"])

    def test_research_generates_contradiction_queries(self):
        """확증편향 방지가 실제로 작동하는지 (§26)."""
        async def run():
            job = self.engine.create_research_job("MRNA")
            return await self.engine.run_research(job["job_id"])

        job = asyncio.run(run())
        self.assertTrue(job["report"]["contradiction_queries"])

    def test_research_records_prediction_with_as_of(self):
        async def run():
            job = self.engine.create_research_job("XOM")
            return await self.engine.run_research(job["job_id"])

        job = asyncio.run(run())
        pid = job["report"]["prediction_id"]
        pred = self.engine.journal.predictions[pid]
        self.assertIn("as_of_index", pred.chart_state)
        self.assertTrue(pred.is_mock)

    def test_office_layout_covers_every_active_agent_home(self):
        room_ids = {r["id"] for r in self.engine.layout.get("rooms", [])}
        for st in self.engine.states.values():
            if st.profile.status == AgentStatus.ACTIVE:
                self.assertIn(st.profile.home_location, room_ids, st.profile.id)

    def test_status_locations_map_to_real_rooms(self):
        room_ids = {r["id"] for r in self.engine.layout.get("rooms", [])}
        for status, loc in self.engine.status_locations.items():
            if loc != "home":
                self.assertIn(loc, room_ids, status)

    def test_one_broken_agent_does_not_stop_the_office(self):
        victim = next(
            st for st in self.engine.states.values()
            if st.profile.status == AgentStatus.ACTIVE
        )
        victim._program = ["chart_study"]

        def boom(_st):
            raise RuntimeError("의도적 실패")

        original = self.engine._do_chart_study
        calls = {"n": 0}

        def patched(st):
            if st is victim:
                calls["n"] += 1
                boom(st)
            return original(st)

        self.engine._do_chart_study = patched  # type: ignore[assignment]
        self.engine.tick()
        self.assertGreater(calls["n"], 0)
        self.assertEqual(victim.status, "BLOCKED")
        # 다른 에이전트는 계속 일해야 합니다
        others = [
            st for st in self.engine.states.values()
            if st is not victim and st.profile.status == AgentStatus.ACTIVE
        ]
        self.assertTrue(any(st.status != "BLOCKED" for st in others))


class TestSharedUtilities(unittest.TestCase):
    def test_yaml_backend_available(self):
        self.assertIn(yamlio.BACKEND, ("pyyaml", "miniyaml"))

    def test_miniyaml_matches_pyyaml_on_config(self):
        """PyYAML 이 없는 환경에서도 설정이 똑같이 읽혀야 합니다."""
        try:
            import yaml as pyyaml
        except ImportError:
            self.skipTest("PyYAML 미설치 — 비교 대상 없음")
        from packages.shared import miniyaml

        for path in sorted(CONFIG.rglob("*.yaml")):
            src = path.read_text(encoding="utf-8")
            self.assertEqual(pyyaml.safe_load(src), miniyaml.safe_load(src), path.name)

    def test_secret_masking(self):
        self.assertNotIn("abcdef123456", mask_text("key sk-abcdef123456 end"))
        masked = mask_event({"api_key": "supersecret", "note": "ok"})
        self.assertEqual(masked["api_key"], "***")
        self.assertEqual(masked["note"], "ok")

    def test_settings_public_dict_has_no_secrets(self):
        s = Settings(anthropic_api_key="sk-should-not-appear")
        blob = repr(s.public_dict())
        self.assertNotIn("sk-should-not-appear", blob)

    def test_env_parser(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('# comment\nA=1\nB="two"\nexport C=3\nBAD\n', encoding="utf-8")
            got = parse_env_file(p)
            self.assertEqual(got, {"A": "1", "B": "two", "C": "3"})


if __name__ == "__main__":
    unittest.main()
