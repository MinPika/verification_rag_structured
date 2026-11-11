"""Keeper restarts a stopped sweep while commands are pending, caps restarts, and exits when all succeeded."""

from __future__ import annotations

from vrag import monitor


def _setup(monkeypatch, tmp_path, todos):
    spawned = []
    monkeypatch.setattr(monitor.paths, "ROOT", tmp_path)
    (tmp_path / "runs" / "logs").mkdir(parents=True)
    monkeypatch.setattr(monitor, "clean_stale_networks", lambda _m: [])
    monkeypatch.setattr(monitor, "bridge_listening", lambda: True)
    monkeypatch.setattr(monitor, "sweep_alive", lambda: False)
    monkeypatch.setattr(monitor, "healthy", lambda: True)
    monkeypatch.setattr(monitor.time, "sleep", lambda _s: None)
    it = iter(todos)
    monkeypatch.setattr(monitor, "_todo", lambda: next(it))
    monkeypatch.setattr(monitor, "_spawn", lambda args, log: spawned.append(args))
    return spawned


def test_keeper_restarts_then_exits_when_done(monkeypatch, tmp_path):
    spawned = _setup(monkeypatch, tmp_path, [[(1, "a")], [(1, "a")], []])
    monitor.keep(interval=0, max_restarts=5, stale_min=15)
    assert len(spawned) == 2 and "vrag.sweep" in spawned[0]
    assert "keeper exits" in (tmp_path / "runs" / "logs" / "keeper.log").read_text()


def test_keeper_caps_restarts(monkeypatch, tmp_path):
    spawned = _setup(monkeypatch, tmp_path, [[(1, "a")]] * 10)
    monitor.keep(interval=0, max_restarts=2, stale_min=15)
    assert len(spawned) == 2


def test_keeper_survives_a_failing_poll(monkeypatch, tmp_path):
    spawned = _setup(monkeypatch, tmp_path, [[]])
    calls = {"n": 0}

    def flaky(_m):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("docker hiccup")
        return []

    monkeypatch.setattr(monitor, "clean_stale_networks", flaky)
    monitor.keep(interval=0, max_restarts=2, stale_min=15)
    assert not spawned and "poll failed: RuntimeError" in (tmp_path / "runs" / "logs" / "keeper.log").read_text()
