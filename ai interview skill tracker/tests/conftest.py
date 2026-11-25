import pytest

from core import auth
from core import database as db


@pytest.fixture()
def fresh_db(tmp_path):
    db.set_database_url(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    db.init_db()
    auth.ensure_admin()
    yield
    db.set_database_url("sqlite:///:memory:")
