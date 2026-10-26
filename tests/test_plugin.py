"""The repo doubles as a Claude Code plugin marketplace: one plugin (plugins/zamakan) holding all four skills.
These checks keep the packaging installable and make sure installed scripts write into the user's project, never
next to themselves (the plugin cache is replaced on every update)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "zamakan"
sys.path.insert(0, str(PLUGIN / "skills" / "zamakan-core" / "scripts"))
import workspace  # noqa: E402


def test_marketplace_points_at_plugin():
    m = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    p = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    entry = m["plugins"][0]
    assert entry["name"] == p["name"] == "zamakan"
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()


def test_plugin_holds_every_skill_and_its_requirements():
    names = sorted(d.name for d in (PLUGIN / "skills").iterdir() if (d / "SKILL.md").is_file())
    assert names == ["zamakan-core", "zamakan-design-system", "zamakan-reference-scout", "zamakan-script-desk", "zamakan-shot-scout"]
    assert (PLUGIN / "requirements.txt").is_file()
    assert "plugins/zamakan/requirements.txt" in (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_plugin_skills_are_the_project_skills():
    """The skills live in .claude/skills (real folders, so cloud sessions load them); the plugin's skills/ is a link to
    them, which Claude Code resolves into real files when it installs the plugin."""
    assert not (ROOT / ".claude" / "skills").is_symlink()
    assert (PLUGIN / "skills").is_symlink()
    assert (PLUGIN / "skills").resolve() == (ROOT / ".claude" / "skills").resolve()


def test_nothing_private_inside_the_plugin():
    files = [p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    assert not [f for f in files if f.startswith(("clients/", "evals/", "library/")) or "/fixtures/" in f]


def test_project_root_is_the_users_folder_not_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ZAMAKAN_ROOT", raising=False)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    proj = home / "work" / "campaigns"
    (proj / "sub").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    assert workspace.project_root(proj / "sub") == proj / "sub"  # no marker: the folder Claude runs in
    (proj / "clients").mkdir()
    assert workspace.project_root(proj / "sub") == proj
    assert workspace.project_root(home) == home  # home itself only when that is where Claude runs


def test_agency_override_from_project(tmp_path, monkeypatch):
    monkeypatch.delenv("ZAMAKAN_AGENCY", raising=False)
    monkeypatch.setenv("ZAMAKAN_ROOT", str(tmp_path))
    assert workspace.agency()["home_country"] == "OM"
    (tmp_path / "zamakan-agency.json").write_text('{"home_country": "SA", "home_name": "Saudi Arabia"}', encoding="utf-8")
    a = workspace.agency()
    assert a["home_country"] == "SA" and a["name"] == "ZAMAKAN" and a["source"].endswith("zamakan-agency.json")


def test_installed_copy_writes_into_the_project(tmp_path):
    """Run client.py from a copy of the plugin (as Claude Code installs it) inside a fresh project."""
    import shutil
    cache = tmp_path / "cache" / "zamakan"
    shutil.copytree(PLUGIN, cache, symlinks=False, ignore=shutil.ignore_patterns("__pycache__"))
    proj = tmp_path / "proj"
    proj.mkdir()
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    env.pop("ZAMAKAN_ROOT", None)
    script = cache / "skills" / "zamakan-core" / "scripts" / "client.py"
    out = subprocess.run([sys.executable, str(script), "job", "demo", "scout-x"], cwd=proj, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert (proj / "clients" / "demo" / "jobs").is_dir()
    assert not (cache / "clients").exists()
