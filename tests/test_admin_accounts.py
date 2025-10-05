from app.extensions import db
from app.models import AdminAccount


def test_admin_account_crud(app):
    """Creating an admin account persists and password hashing works."""
    with app.app_context():
        acc = AdminAccount(username="alice", role="admin")
        acc.set_password("Secret123")
        db.session.add(acc)
        db.session.commit()

        fetched = AdminAccount.query.filter_by(username="alice").first()
        assert fetched is not None
        assert fetched.check_password("Secret123")
        assert not fetched.check_password("WrongPass")
        assert fetched.role == "admin"
        assert fetched.is_admin() is True


def test_guest_account_creation(app):
    """Creating a guest account works correctly."""
    with app.app_context():
        acc = AdminAccount(username="guest_user", role="guest")
        acc.set_password("Secret123")
        db.session.add(acc)
        db.session.commit()

        fetched = AdminAccount.query.filter_by(username="guest_user").first()
        assert fetched is not None
        assert fetched.role == "guest"
        assert fetched.is_guest() is True
        assert fetched.is_admin() is False


def test_admin_login(client, app):
    """POST /login authenticates an AdminAccount and redirects home."""
    with app.app_context():
        acc = AdminAccount(username="bob", role="admin")
        acc.set_password("Password1")
        db.session.add(acc)
        db.session.commit()

    resp = client.post("/login", data={"username": "bob", "password": "Password1"})
    # Should redirect to / on success (302 Found)
    assert resp.status_code in {302, 303}
    assert resp.headers["Location"].endswith("/")


def test_guest_login(client, app):
    """POST /login authenticates a guest account and redirects home."""
    with app.app_context():
        acc = AdminAccount(username="guest_bob", role="guest")
        acc.set_password("Password1")
        db.session.add(acc)
        db.session.commit()

    resp = client.post("/login", data={"username": "guest_bob", "password": "Password1"})
    # Should redirect to / on success (302 Found)
    assert resp.status_code in {302, 303}
    assert resp.headers["Location"].endswith("/")
