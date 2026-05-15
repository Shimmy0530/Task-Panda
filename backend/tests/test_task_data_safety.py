from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth import hash_password
from app.models import Session as FocusSession, Task, User
from app.routers import sessions as sessions_router
from app.routers import tasks as tasks_router
from app.routers.morning import MorningComplete, complete
from app.schemas import TaskUpdate


def _make_user(db_session, username="owner") -> User:
    user = User(
        username=username,
        password_hash=hash_password("password-123"),
        is_admin=True,
        approved_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_session(db_session, *, user_id, task_id, started_at, ended_at):
    row = FocusSession(
        user_id=user_id,
        task_id=task_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_planned_seconds=1500,
        completed=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_task_update_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TaskUpdate(status="vanished")


def test_soft_deleted_tasks_are_hidden_from_day_cap(db_session):
    """4 visible + 1 deleted on the same day must NOT trigger the 5/day cap."""
    user = _make_user(db_session)
    target_day = date(2026, 5, 15)
    for i in range(4):
        db_session.add(Task(user_id=user.id, title=f"visible {i}", day_date=target_day))
    db_session.add(
        Task(
            user_id=user.id,
            title="deleted",
            day_date=target_day,
            deleted_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    tasks_router._enforce_day_caps(
        db_session, user, target_day, is_frog_target=False,
    )


def test_day_cap_raises_with_five_visible_tasks_even_alongside_deletes(db_session):
    """5 visible + 1 deleted: cap still raises because the dead row doesn't shield us."""
    user = _make_user(db_session)
    target_day = date(2026, 5, 15)
    for i in range(5):
        db_session.add(Task(user_id=user.id, title=f"visible {i}", day_date=target_day))
    db_session.add(
        Task(
            user_id=user.id,
            title="deleted",
            day_date=target_day,
            deleted_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        tasks_router._enforce_day_caps(
            db_session, user, target_day, is_frog_target=False,
        )
    assert exc.value.status_code == 400


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


def test_session_summaries_use_supplied_local_day(db_session):
    """Sessions outside the [start, end) window must not count toward total_seconds."""
    user = _make_user(db_session)
    task = Task(user_id=user.id, title="frog", is_frog=True)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    _make_session(
        db_session,
        user_id=user.id,
        task_id=task.id,
        started_at=datetime(2026, 5, 15, 3, 30),
        ended_at=datetime(2026, 5, 15, 4, 0),
    )
    _make_session(  # next-day UTC — outside the requested window
        db_session,
        user_id=user.id,
        task_id=task.id,
        started_at=datetime(2026, 5, 16, 1, 0),
        ended_at=datetime(2026, 5, 16, 1, 30),
    )

    out = sessions_router.today_summary(
        start=datetime(2026, 5, 15, 0, 0),
        end=datetime(2026, 5, 16, 0, 0),
        user=user,
        db=db_session,
    )

    assert out["sessions"] == 1
    assert out["total_seconds"] == 1800
    assert out["frog_seconds"] == 1800


def test_session_summary_excludes_deleted_task_time(db_session):
    """A frog deleted after a focus session is removed from both totals (UI hides → time hides)."""
    user = _make_user(db_session)
    live = Task(user_id=user.id, title="frog", is_frog=True)
    gone = Task(
        user_id=user.id,
        title="deleted-frog",
        is_frog=True,
        deleted_at=datetime.utcnow(),
    )
    db_session.add_all([live, gone])
    db_session.commit()
    db_session.refresh(live)
    db_session.refresh(gone)

    _make_session(
        db_session,
        user_id=user.id,
        task_id=live.id,
        started_at=datetime(2026, 5, 15, 3, 0),
        ended_at=datetime(2026, 5, 15, 3, 30),
    )
    _make_session(
        db_session,
        user_id=user.id,
        task_id=gone.id,
        started_at=datetime(2026, 5, 15, 4, 0),
        ended_at=datetime(2026, 5, 15, 4, 30),
    )

    out = sessions_router.today_summary(
        start=datetime(2026, 5, 15, 0, 0),
        end=datetime(2026, 5, 16, 0, 0),
        user=user,
        db=db_session,
    )

    assert out["sessions"] == 1
    assert out["total_seconds"] == 1800
    assert out["frog_seconds"] == 1800
