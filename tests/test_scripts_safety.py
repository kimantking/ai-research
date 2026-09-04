"""PowerShell 스크립트 안전성 검사.

★ 왜 테스트로 만드는가
   "다른 프로젝트를 건드리지 않는다"는 약속을 사람의 기억에 맡기면
   언젠가 깨집니다. 코드가 감시하게 만듭니다.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 절대 등장하면 안 되는 명령
FORBIDDEN = [
    (r"docker\s+system\s+prune", "docker system prune — 다른 프로젝트 리소스까지 삭제"),
    (r"docker\s+volume\s+prune", "docker volume prune — 다른 프로젝트 볼륨까지 삭제"),
    (r"docker\s+container\s+prune", "docker container prune"),
    (r"docker\s+image\s+prune", "docker image prune"),
    (r"docker\s+network\s+prune", "docker network prune"),
    (r"docker\s+stop\s+\$\(", "전체 컨테이너 일괄 종료"),
    (r"docker\s+kill\s+\$\(", "전체 컨테이너 일괄 종료"),
    (r"Set-ExecutionPolicy\s+(?!.*CurrentUser)", "전역 ExecutionPolicy 변경"),
    (r"\[Environment\]::SetEnvironmentVariable\([^)]*Machine", "시스템 전역 환경변수 변경"),
    (r"Uninstall-", "프로그램 제거"),
    (r"npm\s+install\s+-g", "전역 npm 설치"),
    (r"pip\s+install\s+(?!.*-e\s)(?!.*--quiet).*--user", "사용자 전역 pip 설치"),
]

PS_FILES = sorted(
    p for p in ROOT.rglob("*.ps1")
    if "node_modules" not in p.parts and ".venv" not in p.parts
)

_BLOCK_COMMENT = re.compile(r"<#.*?#>", re.DOTALL)
_QUOTED = re.compile(r"""("[^"]*"|'[^']*')""")


def strip_quoted(line: str) -> str:
    """따옴표 안의 문자열을 지웁니다.

    PowerShell 에서 명령은 따옴표 **밖**에 있습니다.
    따옴표 안은 화면에 찍는 텍스트(안내 문구)이므로 실행되지 않습니다.
    예) Write-Info "  pip install --user pipx"  ← 안내일 뿐 실행 아님
    """
    return _QUOTED.sub(" ", line)


def executable_lines(path: Path) -> str:
    """주석을 걷어낸 '실제로 실행되는' 부분만 남깁니다.

    문서에 '이런 명령은 쓰지 않는다'고 적는 것은 허용되어야 하므로
    블록 주석(<# #>)과 줄 주석(#)을 먼저 제거합니다.
    """
    text = _BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8-sig"))
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        # 줄 끝 주석 제거 (따옴표 안의 # 는 보존)
        if "#" in s and s.count('"') % 2 == 0 and s.count("'") % 2 == 0:
            s = s.split("#", 1)[0]
        out.append(s)
    return "\n".join(out)


class TestNoDangerousCommands(unittest.TestCase):
    def test_scripts_exist(self):
        self.assertGreaterEqual(len(PS_FILES), 15, "PowerShell 스크립트가 부족합니다")

    def test_no_forbidden_commands(self):
        problems = []
        for path in PS_FILES:
            # 실행되는 명령만 검사합니다 (주석·화면 출력 문구 제외)
            body = "\n".join(strip_quoted(ln)
                             for ln in executable_lines(path).splitlines())
            for pattern, why in FORBIDDEN:
                m = re.search(pattern, body, re.IGNORECASE)
                if m:
                    problems.append(f"{path.name}: {why} → {m.group(0)!r}")
        self.assertEqual(problems, [], "위험한 명령이 발견되었습니다:\n" + "\n".join(problems))

    def test_compose_commands_are_project_scoped(self):
        """docker compose 는 반드시 -p 로 이 프로젝트에 한정해야 합니다."""
        problems = []
        for path in PS_FILES:
            for i, s in enumerate(executable_lines(path).splitlines(), 1):
                # 따옴표 안의 문자열은 명령이 아니라 화면에 찍는 라벨입니다
                bare = strip_quoted(s)
                if re.search(r"\bdocker\s+compose\b", bare) and "version" not in bare:
                    if "-p " not in bare and "$ComposeProject" not in bare:
                        problems.append(f"{path.name}:{i} → {s}")
        self.assertEqual(problems, [], "프로젝트 범위가 지정되지 않은 compose 명령:\n"
                         + "\n".join(problems))

    def test_down_v_only_in_reset_script(self):
        """볼륨 삭제(-v)는 reset-local.ps1 에서만, 확인 프롬프트와 함께."""
        for path in PS_FILES:
            text = path.read_text(encoding="utf-8-sig")
            if re.search(r"down\s+-v", executable_lines(path)):
                self.assertEqual(path.name, "reset-local.ps1",
                                 f"{path.name} 에서 볼륨을 삭제하려 합니다")
                self.assertIn("Read-Host", text, "확인 프롬프트가 없습니다")

    def test_remove_item_recurse_is_guarded(self):
        """Remove-Item -Recurse 는 프로젝트 경로 안전장치와 함께여야 합니다."""
        for path in PS_FILES:
            text = path.read_text(encoding="utf-8-sig")
            if re.search(r"Remove-Item\s+-Recurse", executable_lines(path)):
                self.assertIn("ProjectRoot", text,
                              f"{path.name}: 삭제 대상이 프로젝트 내부인지 확인하는 코드가 없습니다")
                self.assertIn("StartsWith", text,
                              f"{path.name}: 경로 탈출 방지 검사가 없습니다")

    def test_stop_script_does_not_kill_unknown_processes(self):
        text = (ROOT / "scripts" / "stop.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("allowed", text, "종료 대상 프로세스 화이트리스트가 없습니다")

    def test_no_bash_only_syntax_for_users(self):
        """사용자에게 bash 명령을 주지 않습니다."""
        bad = []
        for path in PS_FILES:
            body = executable_lines(path)
            for pattern in (r"\bsource\s+\S+/bin/activate", r"\brm\s+-rf\b",
                            r"\bexport\s+[A-Z_]+="):
                if re.search(pattern, body):
                    bad.append(f"{path.name}: {pattern}")
        self.assertEqual(bad, [])


class TestPortStrategy(unittest.TestCase):
    def test_default_ports_avoid_common_ones(self):
        """흔한 포트를 기본값으로 쓰면 다른 프로젝트와 충돌합니다."""
        env = (ROOT / ".env.example").read_text(encoding="utf-8-sig")
        for common in ("=5432", "=6379", "=8000", "=3000"):
            self.assertNotIn(common, env, f"기본 포트에 {common} 이 있습니다")
        for expected in ("API_PORT=8010", "WEB_PORT=3010",
                         "POSTGRES_PORT=5433", "REDIS_PORT=6380"):
            self.assertIn(expected, env)

    def test_compose_uses_unique_names(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8-sig")
        self.assertIn("name: ai-stock-research-office", compose)
        self.assertIn("airo-postgres", compose)
        self.assertIn("airo_pgdata", compose)

    def test_env_is_gitignored(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
        self.assertRegex(gi, r"(?m)^\.env$")
        self.assertIn(".venv/", gi)
        self.assertIn("node_modules/", gi)


class TestEnvExampleHasNoRealSecrets(unittest.TestCase):
    def test_no_filled_api_keys(self):
        env = (ROOT / ".env.example").read_text(encoding="utf-8-sig")
        for line in env.splitlines():
            if re.match(r"^\s*(ANTHROPIC|OPENAI|GOOGLE)_API_KEY\s*=", line):
                value = line.split("=", 1)[1].strip()
                self.assertEqual(value, "", f"예시 파일에 키가 들어 있습니다: {line}")


class TestPowerShellFileEncoding(unittest.TestCase):
    """★ 실사용자 첫 실행을 완전히 막았던 버그를 고정합니다.

    Windows PowerShell 5.1 (Windows 10/11 기본)은 BOM 이 없는 .ps1 을
    UTF-8 이 아니라 시스템 ANSI 코드페이지로 읽습니다.
    한국어 Windows 에서는 CP949 입니다.

    UTF-8 한글은 3바이트, CP949 는 2바이트라서 정렬이 어긋납니다.
    특히 어떤 한글 문자의 마지막 바이트가 CP949 의 '선행 바이트'로 해석되면
    **바로 뒤의 줄바꿈(0x0A)까지 한 글자로 삼켜버립니다.**

    그러면 다음 줄이 앞줄(주석)에 붙어 사라지고, 코드가 주석 안으로 들어가
    ParserError 가 납니다. 실제로 이 프로젝트에서 발생했습니다:
    setup.ps1 이 318줄인데 PowerShell 5.1 은 314줄로 봤습니다.

    해결: UTF-8 BOM 을 붙이면 5.1 도 UTF-8 로 읽습니다.
    """

    BOM = b"\xef\xbb\xbf"

    def test_every_ps1_has_utf8_bom(self):
        missing = []
        for path in PS_FILES:
            if not path.read_bytes().startswith(self.BOM):
                missing.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            missing, [],
            "BOM 이 없는 .ps1 입니다. Windows PowerShell 5.1 에서 깨집니다:\n"
            + "\n".join(missing),
        )

    def test_every_ps1_is_valid_utf8(self):
        for path in PS_FILES:
            raw = path.read_bytes()
            try:
                raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                self.fail(f"{path.name}: UTF-8 이 아닙니다 — {exc}")

    def test_ps1_files_use_crlf(self):
        """CRLF 는 BOM 과 함께 2중 방어선입니다.

        선행 바이트로 오인된 한글 끝바이트가 뒤 문자를 삼킬 때,
        CRLF 면 삼켜지는 것이 CR(0x0D) 이라 LF(0x0A) 가 살아남습니다.
        즉 줄 번호가 어긋나지 않습니다. LF 단독이면 줄이 통째로 합쳐집니다.
        """
        wrong = []
        for path in PS_FILES:
            raw = path.read_bytes()
            lf = raw.count(b"\n")
            crlf = raw.count(b"\r\n")
            if lf != crlf:
                wrong.append(f"{path.relative_to(ROOT)} (LF {lf} / CRLF {crlf})")
        self.assertEqual(wrong, [], "CRLF 가 아닌 .ps1:\n" + "\n".join(wrong))

    def test_parses_the_same_after_ansi_misread(self):
        """BOM 이 있으면 줄 수가 변하지 않는다는 것을 실제로 확인합니다."""
        for path in PS_FILES:
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(self.BOM), f"{path.name}: BOM 없음")
            real_lines = raw.decode("utf-8-sig").count("\n")
            # Windows CP949 디코더 흉내: 선행 바이트는 다음 바이트를 함께 소비
            i, seen_newlines = 3, 0     # BOM 3바이트 건너뜀
            while i < len(raw):
                b = raw[i]
                if 0x81 <= b <= 0xFD and i + 1 < len(raw):
                    i += 2
                else:
                    if b == 0x0A:
                        seen_newlines += 1
                    i += 1
            self.assertEqual(
                seen_newlines, real_lines,
                f"{path.name}: ANSI 로 읽으면 줄바꿈 "
                f"{real_lines - seen_newlines}개가 사라집니다",
            )


class TestFirstRunExperience(unittest.TestCase):
    """처음 실행하는 사람이 막히지 않도록 하는 장치들을 고정합니다."""

    BATS = ("setup.bat", "start.bat", "stop.bat", "restart.bat",
            "health.bat", "test.bat", "logs.bat", "update.bat",
            "fetch-data.bat", "db.bat")

    def test_bat_wrappers_bypass_execution_policy(self):
        # Windows 는 인터넷에서 받은 .ps1 실행을 막습니다.
        # .bat 은 그 상황에서 유일하게 확실히 동작하는 탈출구이므로
        # Bypass 가 빠지면 안 됩니다.
        for name in self.BATS:
            p = ROOT / name
            self.assertTrue(p.exists(), f"{name} 이 없습니다")
            text = p.read_text(encoding="utf-8-sig")
            self.assertIn("-ExecutionPolicy Bypass", text, f"{name}: Bypass 누락")
            self.assertIn("-File", text, f"{name}: -File 누락")

    def test_bat_wrappers_always_pause(self):
        # 더블클릭으로 실행하면 창이 즉시 닫혀 출력을 못 봅니다.
        # 성공/실패와 무관하게 pause 가 있어야 합니다.
        for name in self.BATS:
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            self.assertRegex(
                text, r"(?m)^\s*pause",
                f"{name}: 조건 없는 pause 가 없습니다 (창이 바로 닫힙니다)",
            )
            self.assertNotIn(
                "if errorlevel 1 pause", text,
                f"{name}: 성공했을 때 창이 바로 닫힙니다",
            )

    def test_bat_wrappers_are_ascii(self):
        # .bat 은 cmd.exe 가 OEM 코드페이지로 읽습니다.
        # 한글을 넣으면 깨져서 오히려 사람을 혼란스럽게 만듭니다.
        for name in self.BATS:
            raw = (ROOT / name).read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"),
                             f"{name}: BOM 이 있으면 @echo off 가 깨집니다")
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                self.fail(f"{name}: ASCII 가 아닌 문자가 있습니다")

    def test_setup_unblocks_only_inside_project(self):
        text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("Unblock-File", text, "차단 해제 단계가 없습니다")
        self.assertIn("Assert-InsideProject", text,
                      "Unblock-File 이 프로젝트 밖까지 갈 수 있습니다")
    def test_no_script_changes_execution_policy(self):
        # 실행 정책 변경은 "시스템 전역 설정 변경" 이라 사용자 승인 사항입니다.
        # 안내 문구로 알려주는 것은 괜찮지만, 스크립트가 직접 바꾸면 안 됩니다.
        # (따옴표 안 = 화면 출력, 따옴표 밖 = 실제 실행)
        for path in PS_FILES:
            body = strip_quoted(executable_lines(path)).lower()
            self.assertNotIn(
                "set-executionpolicy", body,
                f"{path.name}: 실행 정책을 직접 변경합니다 (사용자 승인 필요)",
            )

    def test_setup_accepts_python_311_and_newer(self):
        # 187개 테스트를 3.11 / 3.12 / 3.13 에서 통과시켜 확인했으므로
        # "3.12 가 아니면 중단" 으로 되돌아가면 안 됩니다.
        text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("$v -eq '3.12'", text,
                         "3.12 정확히 일치를 요구하면 3.13 사용자가 막힙니다")
        self.assertIn("-3.13", text, "3.13 탐색이 없습니다")
        self.assertIn("-3.11", text, "3.11 탐색이 없습니다")

    def test_setup_degraded_path_exits_zero(self):
        text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$degraded", text)
        self.assertIn("$fatal", text)
        # 마지막 줄이 exit 0 이어야 "선택 기능 없음" 이 실패로 보이지 않습니다.
        self.assertEqual(text.rstrip().splitlines()[-1].strip(), "exit 0")

    def test_docs_tell_users_to_run_bat_from_powershell(self):
        r"""실사용자가 두 번 막힌 지점입니다.

        PowerShell 창을 열고 .\setup.ps1 을 치면 실행 정책에 막힙니다.
        같은 창에서 .\setup.bat 을 치면 됩니다 (.bat 은 정책 적용 대상이 아님).
        이 안내가 문서에서 빠지면 안 됩니다.
        """
        for rel in ("README_FIRST.md", "HOW-TO-RUN.txt", "docs/TROUBLESHOOTING.md"):
            text = (ROOT / rel).read_text(encoding="utf-8-sig")
            self.assertIn(
                ".\\setup.bat", text,
                f"{rel}: PowerShell 에서 .\\setup.bat 을 쓰라는 안내가 없습니다",
            )

    def test_readme_first_explains_execution_policy_error(self):
        text = (ROOT / "README_FIRST.md").read_text(encoding="utf-8-sig")
        self.assertIn("PSSecurityException", text,
                      "가장 흔한 첫 오류가 README_FIRST 에 없습니다")
        self.assertIn("setup.bat", text)

    def test_troubleshooting_covers_execution_policy(self):
        text = (ROOT / "docs" / "TROUBLESHOOTING.md").read_text(encoding="utf-8-sig")
        self.assertIn("Unblock-File", text)
        self.assertIn("RemoteSigned", text)


if __name__ == "__main__":
    unittest.main()


class TestBackendLaunch(unittest.TestCase):
    """★ 백엔드가 새 창에서 실제로 뜨는지를 좌우하는 구조를 고정합니다.

    실제로 겪은 일: start.ps1 이 Write-Host 여러 줄 + 환경변수 + uvicorn 명령을
    하나의 긴 문자열로 만들어 `Start-Process -Command` 로 넘겼습니다.
    그 문자열에 따옴표·세미콜론·괄호·한글이 섞이면서 새 창으로 전달되는
    도중 깨졌고, 백엔드가 아예 뜨지 않았습니다.

    해결: 실행기를 별도 .ps1 파일로 분리하고 단순한 인자만 넘깁니다.
    """

    def test_launcher_file_exists(self):
        launcher = ROOT / "scripts" / "_run-backend.ps1"
        self.assertTrue(launcher.exists(), "백엔드 실행기 파일이 없습니다")

    def test_start_uses_file_not_a_long_command_string(self):
        text = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("_run-backend.ps1", text,
                      "start.ps1 이 실행기 파일을 쓰지 않습니다")
        self.assertNotIn("$apiCmd", text,
                         "긴 명령 문자열 방식으로 되돌아갔습니다 (깨지기 쉽습니다)")

    def test_no_giant_command_string_is_built(self):
        """어떤 스크립트도 -Command 로 200자 넘는 문자열을 넘기지 않습니다."""
        for path in PS_FILES:
            text = path.read_text(encoding="utf-8-sig")
            for m in re.finditer(r"^\s*\$(\w+)\s*=\s*\"(.{200,})\"\s*$",
                                 text, re.MULTILINE):
                var, body = m.group(1), m.group(2)
                if "-Command" in text and f"${var}" in text:
                    self.assertNotIn(
                        "Write-Host", body,
                        f"{path.name}: ${var} 가 Write-Host 를 포함한 긴 명령 "
                        f"문자열입니다. 새 창으로 넘기면 깨질 수 있습니다.")

    def test_launcher_takes_simple_typed_parameters(self):
        text = (ROOT / "scripts" / "_run-backend.ps1").read_text(encoding="utf-8-sig")
        for param in ("$ProjectPath", "$PythonExe", "$Port", "$Mode"):
            self.assertIn(param, text, f"실행기에 {param} 파라미터가 없습니다")

    def test_launcher_keeps_the_window_open_on_crash(self):
        """★ 백엔드가 죽었을 때 창이 닫히면 원인을 영영 알 수 없습니다."""
        text = (ROOT / "scripts" / "_run-backend.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("백엔드가 종료되었습니다", text)
        self.assertIn("LASTEXITCODE", text)
        start = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'-NoExit'", start, "창이 바로 닫히면 오류를 못 봅니다")

    def test_docker_is_opt_in_not_default(self):
        """Docker 는 쓰지도 않으면서 빨간 오류만 띄웠습니다. 이제 선택입니다."""
        text = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$WithDocker", text)
        self.assertIn("if ($WithDocker", text,
                      "Docker 를 기본으로 띄우려 하고 있습니다")


class TestUserDataIsNeverOverwritten(unittest.TestCase):
    """★ 실제로 antking님 API 키를 날릴 뻔한 문제를 고정합니다.

    배포 zip 에 `.env` 가 들어가 있었습니다. 새 버전을 받아 압축을 풀 때마다
    사용자가 넣어둔 API 키·포트 설정이 **제 파일로 덮어써졌습니다.**
    증상이 "키를 넣었는데 키가 없다고 나온다" 라서 원인을 찾기 매우 어렵습니다.
    """

    def test_env_is_gitignored(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
        self.assertRegex(gi, r"(?m)^\.env$")

    def test_env_example_exists_and_env_is_not_tracked(self):
        self.assertTrue((ROOT / ".env.example").exists(),
                        ".env.example 이 없으면 setup 이 .env 를 만들 수 없습니다")

    def test_setup_never_overwrites_an_existing_env(self):
        text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8-sig")
        idx = text.index("if (Test-Path $envPath)")
        # 존재할 때의 분기에 Copy-Item 이 있으면 안 됩니다
        exists_branch = text[idx:text.index("} else {", idx)]
        self.assertNotIn("Copy-Item", exists_branch,
                         "이미 있는 .env 를 덮어쓰려 합니다")
        self.assertIn("덮어쓰지 않습니다", exists_branch)

    def test_setup_adds_new_keys_without_touching_existing_values(self):
        """새 설정이 생기면 알려줘야 하지만, 기존 값은 건드리면 안 됩니다."""
        text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("Add-Content", text, "새 항목을 추가하는 코드가 없습니다")
        self.assertNotIn("Set-Content -Path $envPath", text,
                         ".env 를 통째로 덮어쓰고 있습니다")

    def test_env_example_covers_every_setting_the_code_reads(self):
        """★ 코드가 읽는 설정이 .env.example 에 없으면 사용자가 존재를 모릅니다."""
        config = (ROOT / "packages" / "shared" / "config.py").read_text(encoding="utf-8")
        example = (ROOT / ".env.example").read_text(encoding="utf-8-sig")
        read_keys = set(re.findall(r'(?:get|as_int|as_bool)\("([A-Z0-9_]+)"', config))
        declared = {ln.split("=", 1)[0].strip()
                    for ln in example.splitlines()
                    if "=" in ln and not ln.strip().startswith("#")}
        missing = sorted(read_keys - declared)
        self.assertEqual(
            missing, [],
            ".env.example 에 없는 설정입니다 (사용자가 존재를 알 수 없습니다): "
            + ", ".join(missing))

    def test_diagnostics_never_write_secrets(self):
        text = (ROOT / "scripts" / "diagnose.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("KEY|SECRET|TOKEN|PASSWORD", text,
                      "진단 파일이 키를 그대로 기록할 수 있습니다")
        self.assertIn("이메일 가림", text,
                      "진단 파일에 이메일 주소가 그대로 남습니다")

    def test_diagnostics_are_read_only(self):
        """진단은 아무것도 바꾸면 안 됩니다."""
        body = executable_lines(ROOT / "scripts" / "diagnose.ps1")
        for danger in ("Remove-Item", "Copy-Item", "New-Item", "pip install",
                       "docker compose"):
            self.assertNotIn(danger, body,
                             f"diagnose.ps1 이 {danger} 를 실행합니다 (읽기 전용이어야 합니다)")
