"""ProjectManager.list_projects optional owner_user_id filter."""

import pytest

from app.models.project import ProjectManager


@pytest.fixture()
def isolated_projects_dir(monkeypatch, tmp_path):
    root = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(root))
    ProjectManager._ensure_projects_dir()
    yield root


def test_list_projects_no_owner_filter_returns_all(isolated_projects_dir):
    a = ProjectManager.create_project(name="A", owner_user_id="user-1")
    b = ProjectManager.create_project(name="B", owner_user_id="user-2")
    c = ProjectManager.create_project(name="C", owner_user_id=None)
    listed = ProjectManager.list_projects(limit=50)
    ids = {p.project_id for p in listed}
    assert ids == {a.project_id, b.project_id, c.project_id}


def test_list_projects_filters_by_owner_user_id(isolated_projects_dir):
    a = ProjectManager.create_project(name="A", owner_user_id="user-1")
    ProjectManager.create_project(name="B", owner_user_id="user-2")
    ProjectManager.create_project(name="C", owner_user_id=None)
    listed = ProjectManager.list_projects(limit=50, owner_user_id="user-1")
    assert [p.project_id for p in listed] == [a.project_id]


def test_list_projects_owner_filter_no_match_returns_empty(isolated_projects_dir):
    ProjectManager.create_project(name="Other", owner_user_id="user-other")
    listed = ProjectManager.list_projects(limit=50, owner_user_id="non-existent")
    assert listed == []


def test_list_projects_owner_filter_respects_limit_and_sort(isolated_projects_dir):
    p_old = ProjectManager.create_project(name="Old", owner_user_id="u")
    p_old.created_at = "2020-01-01T00:00:00"
    ProjectManager.save_project(p_old)
    p_new = ProjectManager.create_project(name="New", owner_user_id="u")
    p_new.created_at = "2025-01-01T00:00:00"
    ProjectManager.save_project(p_new)
    listed = ProjectManager.list_projects(limit=1, owner_user_id="u")
    assert len(listed) == 1
    assert listed[0].project_id == p_new.project_id
