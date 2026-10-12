"""Landing gate: a worktree code card is not `done` until landed (default
branch is the source of truth). Covers park_for_landing + land_task + the
complete_task gate under `kanban.land_required`."""
from __future__ import annotations

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture()
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    db = kb.kanban_db_path(board="default")
    kb._INITIALIZED_PATHS.discard(str(db.resolve()))
    kb.init_db()
    return home


@pytest.fixture()
def conn(kanban_home):
    c = kb.connect()
    yield c
    c.close()


def _worktree_task(c):
    return kb.create_task(c, title="t", body="b", assignee="w",
                          created_by="test", workspace_kind="worktree")


def _status(c, tid):
    return c.execute("SELECT status FROM tasks WHERE id = ?", (tid,)).fetchone()["status"]


def _landing_on(monkeypatch):
    import hermes_cli.config as cfgmod
    monkeypatch.setattr(cfgmod, "load_config",
                        lambda *a, **k: {"kanban": {"land_required": True}})


def test_gate_parks_worktree_card_when_land_required(conn, monkeypatch):
    _landing_on(monkeypatch)
    tid = _worktree_task(conn)
    kb.complete_task(conn, tid, result="done")
    assert _status(conn, tid) == "landing"
    ev = conn.execute("SELECT kind FROM task_events WHERE task_id = ? "
                      "AND kind='landing_required'", (tid,)).fetchone()
    assert ev is not None


def test_land_task_finishes(conn, monkeypatch):
    _landing_on(monkeypatch)
    tid = _worktree_task(conn)
    kb.complete_task(conn, tid, result="done")
    assert kb.land_task(conn, tid, merged_sha="abc123", actor="reviewer")
    assert _status(conn, tid) == "done"


def test_gate_off_completes_normally(conn):
    tid = _worktree_task(conn)
    kb.complete_task(conn, tid, result="done")
    assert _status(conn, tid) == "done"


def test_landed_true_bypasses_gate(conn, monkeypatch):
    _landing_on(monkeypatch)
    tid = _worktree_task(conn)
    kb.complete_task(conn, tid, result="done", landed=True)
    assert _status(conn, tid) == "done"


def test_land_task_requires_landing_state(conn):
    tid = _worktree_task(conn)
    assert kb.land_task(conn, tid) is False
