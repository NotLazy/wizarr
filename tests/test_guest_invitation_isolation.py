"""Tests for guest invitation isolation functionality."""

import pytest
from app.extensions import db
from app.models import AdminAccount, Invitation, MediaServer
from app.services.invites import create_invite


def test_guest_can_only_see_own_invitations(client, app):
    """Test that guest users can only see invitations they created."""
    with app.app_context():
        # Create two guest accounts
        guest1 = AdminAccount(username="guest1_unique", role="guest")
        guest1.set_password("Password123")
        
        guest2 = AdminAccount(username="guest2_unique", role="guest")
        guest2.set_password("Password123")
        
        db.session.add(guest1)
        db.session.add(guest2)
        db.session.commit()
        
        # Create a test server
        server = MediaServer(
            name="Test Server",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Login as guest1 and create an invitation
        resp = client.post("/login", data={"username": "guest1_unique", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Create invitation by guest1
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week",
            "code": "GUEST1123"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Logout guest1
        client.get("/logout")
        
        # Login as guest2 and create another invitation
        resp = client.post("/login", data={"username": "guest2_unique", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week", 
            "code": "GUEST2123"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Check that guest2 can only see their own invitation
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        content = resp.get_data(as_text=True)
        assert "GUEST2123" in content
        assert "GUEST1123" not in content


def test_admin_can_see_all_invitations(client, app):
    """Test that admin users can see all invitations."""
    with app.app_context():
        # Create one admin and one guest
        admin = AdminAccount(username="admin_unique", role="admin")
        admin.set_password("Password123")
        
        guest = AdminAccount(username="guest_unique", role="guest")
        guest.set_password("Password123")
        
        db.session.add(admin)
        db.session.add(guest)
        db.session.commit()
        
        # Create a test server
        server = MediaServer(
            name="Test Server",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Login as guest and create an invitation
        resp = client.post("/login", data={"username": "guest_unique", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week",
            "code": "GUEST456"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Logout guest
        client.get("/logout")
        
        # Login as admin and create another invitation
        resp = client.post("/login", data={"username": "admin_unique", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week",
            "code": "ADMIN456"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Check that admin can see all invitations
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        content = resp.get_data(as_text=True)
        assert "ADMIN456" in content
        assert "GUEST456" in content


def test_guest_can_only_delete_own_invitations(client, app):
    """Test that guest users can only delete invitations they created."""
    with app.app_context():
        # Create two guest accounts
        guest1 = AdminAccount(username="guest1_del", role="guest")
        guest1.set_password("Password123")
        
        guest2 = AdminAccount(username="guest2_del", role="guest")
        guest2.set_password("Password123")
        
        db.session.add(guest1)
        db.session.add(guest2)
        db.session.commit()
        
        # Create a test server
        server = MediaServer(
            name="Test Server",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Login as guest1 and create an invitation
        resp = client.post("/login", data={"username": "guest1_del", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week",
            "code": "DEL123"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Logout guest1
        client.get("/logout")
        
        # Login as guest2 and create another invitation
        resp = client.post("/login", data={"username": "guest2_del", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        form_data = {
            "server_ids": [str(server.id)],
            "expires": "week",
            "code": "DEL456"
        }
        resp = client.post("/invite", data=form_data, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Try to delete guest1's invitation (should fail silently)
        resp = client.post("/invite/table?delete=DEL123", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Verify that guest1's invitation still exists
        inv1 = Invitation.query.filter_by(code="DEL123").first()
        assert inv1 is not None
        
        # Delete guest2's own invitation (should work)
        resp = client.post("/invite/table?delete=DEL456", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Verify that guest2's invitation was deleted
        inv2 = Invitation.query.filter_by(code="DEL456").first()
        assert inv2 is None


def test_admin_can_see_all_invitations(client, app):
    """Test that admin users can see all invitations."""
    with app.app_context():
        # Create two admin accounts (one admin, one guest)
        admin = AdminAccount(username="admin_see_invites_user", role="admin")
        admin.set_password("Password123")
        
        guest = AdminAccount(username="guest_see_invites_user", role="guest")
        guest.set_password("Password123")
        
        db.session.add(admin)
        db.session.add(guest)
        db.session.commit()
        
        # Create a test server
        server = MediaServer(
            name="Test Server",
            server_type="jellyfin", 
            url="http://localhost:8096",
            api_key="test_key"
        )
        db.session.add(server)
        db.session.commit()
        
        # Create invitations: one by admin, one by guest
        admin_invite = Invitation(
            code="ADMIN_SEE_123",
            created_by_id=admin.id,
            expires=None,
            unlimited=True
        )
        
        guest_invite = Invitation(
            code="GUEST_SEE_123",
            created_by_id=guest.id,
            expires=None,
            unlimited=True
        )
        
        db.session.add(admin_invite)
        db.session.add(guest_invite)
        db.session.commit()
        
        # Login as admin
        resp = client.post("/login", data={"username": "admin_see_invites_user", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Get invitation table as admin
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Admin should see all invitations
        content = resp.get_data(as_text=True)
        assert "GUEST_SEE_123" in content
        assert "ADMIN_SEE_123" in content


def test_guest_can_only_delete_own_invitations(client, app):
    """Test that guest users can only delete invitations they created."""
    with app.app_context():
        # Create two admin accounts (one admin, one guest)
        admin = AdminAccount(username="admin_delete_invites_user", role="admin")
        admin.set_password("Password123")
        
        guest = AdminAccount(username="guest_delete_invites_user", role="guest")
        guest.set_password("Password123")
        
        db.session.add(admin)
        db.session.add(guest)
        db.session.commit()
        
        # Create a test server
        server = MediaServer(
            name="Test Server",
            server_type="jellyfin",
            url="http://localhost:8096", 
            api_key="test_key"
        )
        db.session.add(server)
        db.session.commit()
        
        # Create invitations: one by admin, one by guest
        from datetime import datetime, timezone
        
        admin_invite = Invitation(
            code="ADMIN_DEL_123",
            created_by_id=admin.id,
            expires=None,
            unlimited=True,
            used=False,
            created=datetime.now(timezone.utc)
        )
        
        guest_invite = Invitation(
            code="GUEST_DEL_123",
            created_by_id=guest.id,
            expires=None,
            unlimited=True,
            used=False,
            created=datetime.now(timezone.utc)
        )
        
        db.session.add(admin_invite)
        db.session.add(guest_invite)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_delete_invites_user", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Try to delete admin's invitation (should be ignored)
        resp = client.post("/invite/table?delete=ADMIN_DEL_123", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Verify admin's invitation still exists
        admin_invite_check = Invitation.query.filter_by(code="ADMIN_DEL_123").first()
        assert admin_invite_check is not None
        
        # Delete guest's own invitation (should work)
        resp = client.post("/invite/table?delete=GUEST_DEL_123", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Verify guest's invitation was deleted
        guest_invite_check = Invitation.query.filter_by(code="GUEST_DEL_123").first()
        assert guest_invite_check is None