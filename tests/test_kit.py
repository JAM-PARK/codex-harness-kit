"""Behavioral regressions for installation and schedule generation (stdlib only)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace with spaces'
        self.root.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')

    def run_command(self, args):
        return subprocess.run(args, cwd=self.root, env=self.env, capture_output=True,
                              text=True, timeout=20)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SetupTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        shutil.copytree(REPO / 'kit/.agents', self.root / '.agents')
        self.state = self.root / 'docs/STATE.md'

    def setup(self, *args):
        return self.run_command(['bash', str(self.root / '.agents/setup.sh'), *args])

    def test_normal_schedule(self):
        self.assert_success(self.setup('10:00', '180'))
        state = self.state.read_text()
        for text in ('10:00 ~ 13:00', '15%) 10:27', '23%) 10:41', '45%) 11:21',
                     '80%) 12:24', '85%) 12:33', '마감 준비 12:50'):
            self.assertIn(text, state)
        self.assertNotIn('HH:MM', state)

    def test_cap_shortens_schedule(self):
        self.assert_success(self.setup('10:30', '180', '13:20'))
        state = self.state.read_text()
        for text in ('10:30 ~ 13:20', '15%) 10:55', '85%) 12:54', '마감 준비 13:10'):
            self.assertIn(text, state)

    def test_decimal_leading_zeros(self):
        self.assert_success(self.setup('08:00', '0180'))
        self.assertIn('08:00 ~ 11:00', self.state.read_text())

    def test_long_work_session(self):
        self.assert_success(self.setup('09:00', '480'))
        state = self.state.read_text()
        for text in ('09:00 ~ 17:00', '15%) 10:12', '23%) 10:50',
                     '45%) 12:36', '80%) 15:24', '85%) 15:48', '마감 준비 16:50'):
            self.assertIn(text, state)

    def test_latest_same_day_end(self):
        self.assert_success(self.setup('00:00', '1439'))
        self.assertIn('00:00 ~ 23:59', self.state.read_text())

    def test_cap_keeps_long_session_in_same_day(self):
        self.assert_success(self.setup('20:00', '480', '23:00'))
        self.assertIn('20:00 ~ 23:00', self.state.read_text())

    def test_invalid_input_has_no_side_effects(self):
        cases = [(), ('10:00',), ('25:00', '180'), ('10:99', '180'),
                 ('10:00', 'oops'), ('10:00', '0'), ('10:00', '-1'), ('00:00', '1440'),
                 ('10:00', '99999999999999999999'), ('10:00', '180', '13:60'),
                 ('10:00', '180', '09:00'), ('10:00', '180', '10:00'),
                 ('10:00', '180', ''), ('23:50', '180'),
                 ('10:00', '180', '13:00', 'extra')]
        for args in cases:
            with self.subTest(args=args):
                result = self.setup(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'docs').exists())
                self.assertFalse((self.root / '.git').exists())
        # Correcting an invalid invocation must work without manual cleanup.
        self.assert_success(self.setup('10:00', '180'))

    def test_short_window_keeps_real_deadline(self):
        self.assert_success(self.setup('12:55', '5'))
        state = self.state.read_text()
        self.assertIn('단계: WRAP', state)
        self.assertIn('12:55 ~ 13:00', state)
        self.assertIn('마감 준비 12:55', state)
        self.assertNotIn('HH:MM', state)

    def test_repeat_preserves_work(self):
        self.assert_success(self.setup('10:00', '180'))
        self.state.write_text(self.state.read_text().replace('단계: SETUP', '단계: BUILD')
                              + '\n사용자의 결정과 작업 기록\n')
        before = self.state.read_bytes()
        self.assert_success(self.setup('10:00', '180'))
        self.assertEqual(self.state.read_bytes(), before)
        self.assertNotEqual(self.setup('10:30', '180', '13:20').returncode, 0)
        self.assertEqual(self.state.read_bytes(), before)

    def test_refresh_changes_only_time_fields(self):
        self.assert_success(self.setup('10:00', '180'))
        self.state.write_text(self.state.read_text().replace('단계: SETUP', '단계: BUILD')
                              + '\n사용자의 결정과 작업 기록\n')
        before = self.state.read_text().splitlines()
        self.assert_success(self.setup('--refresh-times', '10:30', '180', '13:20'))
        after = self.state.read_text().splitlines()
        self.assertEqual(len(before), len(after))
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(changed), 2)
        self.assertTrue(changed[0][0].startswith('- 작업 시간:'))
        self.assertTrue(changed[1][0].startswith('- 체크포인트:'))

    def test_legacy_placeholder_recovery(self):
        self.state.parent.mkdir()
        self.state.write_text('# STATE\n- 단계: BUILD\n- 작업 시간: HH:MM ~ HH:MM\n'
                              '- 체크포인트: HH:MM\n기존 결정\n')
        before = self.state.read_bytes()
        self.assertNotEqual(self.setup('10:00', '180').returncode, 0)
        self.assertEqual(self.state.read_bytes(), before)
        self.assert_success(self.setup('--refresh-times', '10:00', '180'))
        self.assertNotIn('HH:MM', self.state.read_text())
        self.assertIn('기존 결정', self.state.read_text())
        self.assertIn('단계: BUILD', self.state.read_text())

    def test_docs_file_is_reported_as_failure(self):
        (self.root / 'docs').write_text('preserve this')
        result = self.setup('10:00', '180')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('[ok]', result.stdout)
        self.assertEqual((self.root / 'docs').read_text(), 'preserve this')

    def test_state_directory_is_reported_as_failure(self):
        self.state.mkdir(parents=True)
        self.assertNotEqual(self.setup('10:00', '180').returncode, 0)
        self.assertTrue(self.state.is_dir())

    def test_state_symlink_is_not_followed(self):
        external = self.root / 'external.md'
        external.write_text('preserve this')
        self.state.parent.mkdir()
        self.state.symlink_to(external)
        self.assertNotEqual(self.setup('--refresh-times', '10:00', '180').returncode, 0)
        self.assertEqual(external.read_text(), 'preserve this')

    def test_malformed_state_is_not_rewritten(self):
        self.state.parent.mkdir()
        self.state.write_text('custom state without schedule fields\n')
        before = self.state.read_bytes()
        self.assertNotEqual(self.setup('--refresh-times', '10:00', '180').returncode, 0)
        self.assertEqual(self.state.read_bytes(), before)


class InstallTests(WorkspaceTest):
    def install(self):
        return self.run_command([sys.executable, str(REPO / 'install.py'), str(self.root)])

    def test_install_and_repeat_preserve_existing_instructions(self):
        agents = self.root / 'AGENTS.md'
        original = b'Existing instructions\r\nKeep this unchanged.'
        agents.write_bytes(original)
        self.assert_success(self.install())
        expected = agents.read_bytes()
        self.assertTrue(expected.startswith(original))
        self.assertEqual(expected.count(b'<!-- codex-harness-kit:begin -->'), 1)
        self.assert_success(self.install())
        self.assertEqual(agents.read_bytes(), expected)
        for source in (REPO / 'kit/.agents').rglob('*'):
            if source.is_file():
                self.assertEqual((self.root / source.relative_to(REPO / 'kit')).read_bytes(),
                                 source.read_bytes())

    def test_override_blocks_install_before_copy(self):
        override = self.root / 'AGENTS.override.md'
        override.write_text('managed policy')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse((self.root / '.agents').exists())
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertEqual(override.read_text(), 'managed policy')

    def test_conflicting_skill_blocks_all_copying(self):
        skill = self.root / '.agents/skills/verify-loop/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('existing skill')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse((self.root / '.agents/setup.sh').exists())
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertEqual(skill.read_text(), 'existing skill')

    def test_modified_installed_instructions_are_preserved(self):
        self.assert_success(self.install())
        agents = self.root / 'AGENTS.md'
        agents.write_text(agents.read_text().replace('실행 파트너', '사용자 변경 내용'))
        before = agents.read_bytes()
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(agents.read_bytes(), before)

    def test_legacy_install_is_not_duplicated(self):
        agents = self.root / 'AGENTS.md'
        agents.write_text('# AGENTS.md — 작업 운영 규칙\n기존 내용\n')
        before = agents.read_bytes()
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(agents.read_bytes(), before)
        self.assertFalse((self.root / '.agents').exists())

    def test_symlinked_skills_directory_is_not_followed(self):
        external = Path(self.temp.name) / 'external'
        external.mkdir()
        (self.root / '.agents').mkdir()
        (self.root / '.agents/skills').symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse((self.root / '.agents/setup.sh').exists())

    def test_existing_file_in_parent_path_is_preserved(self):
        (self.root / '.agents').write_text('existing file')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual((self.root / '.agents').read_text(), 'existing file')
        self.assertFalse((self.root / 'AGENTS.md').exists())

    def test_incomplete_markers_block_install(self):
        (self.root / 'AGENTS.md').write_text('<!-- codex-harness-kit:begin -->\n')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse((self.root / '.agents').exists())


if __name__ == '__main__':
    unittest.main()
