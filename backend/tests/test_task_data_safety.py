from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models import Task, User
from app.routers import sessions as sessions_router
from app.routers import tasks as tasks_router
from app.routers.morning import CarryAction, MorningComplete, complete
from app.schemas import TaskUpdate


class DummyQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return list(self.rows)


class DummySession:
    def __init__(self, rows):
        self.rows = list(rows)

    def query(self, model):
        return DummyQuery(self.rows)


def test_task_update_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TaskUpdate(status="vanished")


def test_soft_deleted_tasks_are_hidden_from_day_cap():
    user = User(id=1, username="owner", password_hash="x", approved_at=datetime.utcnow())
    old = Task(
        id=1,
        user_id=1,
        title="deleted",
        day_date=date(2026, 5, 15),
        deleted_at=datetime.utcnow(),
    )
    db = DummySession([old])

    tasks_router._enforce_day_caps(
        db,
        user,
        date(2026, 5, 15),
        is_frog_target=False,
    )


class FakeMorningQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)

    def count(self):
        return len([row for row in self.rows if getattr(row, "deleted_at", None) is None])


class FakeMorningDb:
    def __init__(self, rows):
        self.rows = rows
        self.deleted = []
        self.committed = False

    def query(self, model):
        return FakeMorningQuery(self.rows)

    def add(self, row):
        self.rows.append(row)

    def flush(self):
        pass

    def delete(self, row):
        self.deleted.append(row)

    def rollback(self):
        pass

    def commit(self):
        self.committed = True


def test_morning_stale_drop_marks_deleted_instead_of_hard_delete():
    stale = Task(
        id=7,
        user_id=1,
        title="stale",
        day_date=None,
        created_at=datetime.utcnow() - timedelta(days=45),
    )
    user = User(id=1, username="owner", password_hash="x", approved_at=datetime.utcnow())
    db = FakeMorningDb([stale])

    complete(
        MorningComplete(
            today_date=date(2026, 5, 15),
            frog_title="do first",
            dropped_stale_ids=[7],
            yesterday_actions=[],
        ),
        user=user,
        db=db,
    )

    assert db.deleted == []
    assert stale.deleted_at is not None
    assert db.committed is True


class FakeSessionDb:
    def __init__(self, rows, task):
        self.rows = rows
        self.task = task

    def query(self, model):
        return DummyQuery(self.rows)

    def get(self, model, id):
        return self.task if self.task.id == id else None


def test_session_summaries_use_supplied_local_day():
    task = Task(id=1, user_id=1, title="frog", is_frog=True)
    row = type(
        "SessionRow",
        (),
        {
            "task_id": 1,
            "started_at": datetime(2026, 5, 15, 3, 30),
            "ended_at": datetime(2026, 5, 15, 4, 0),
        },
    )()
    user = User(id=1, username="owner", password_hash="x", approved_at=datetime.utcnow())
    db = FakeSessionDb([row], task)

    out = sessions_router.today_summary(
        start=datetime(2026, 5, 15, 0, 0),
        end=datetime(2026, 5, 16, 0, 0),
        user=user,
        db=db,
    )

    assert out["total_seconds"] == 1800
