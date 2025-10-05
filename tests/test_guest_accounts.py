"""Tests for role-based access control and guest account functionality."""

import pytest
from app.extensions import db
from app.models import AdminAccount


def test_guest_cannot_access_users(client, app):
    """Test that guest accounts cannot access user management."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_users_mgmt_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_users_mgmt_test", "password": "Password123"})
        assert resp.status_code in {302, 303}

        # Test blocked access to user pages
        resp = client.get("/users", headers={"HX-Request": "true"})
        assert resp.status_code == 403

        resp = client.get("/users/table")
        assert resp.status_code == 403


def test_guest_cannot_access_settings(client, app):
    """Test that guest accounts cannot access settings pages."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_settings_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()

        # Login as guest
        resp = client.post("/login", data={"username": "guest_settings_test", "password": "Password123"})
        assert resp.status_code in {302, 303}

        # Test blocked access to settings pages
        resp = client.get("/settings", headers={"HX-Request": "true"})
        assert resp.status_code == 403

        resp = client.get("/settings/table")
        assert resp.status_code == 403


def test_admin_account_roles(app):
    """Test AdminAccount role functionality."""
    with app.app_context():
        # Create admin account
        admin = AdminAccount(username="admin_role_test", role="admin")
        admin.set_password("Password123")
        
        # Create guest account
        guest = AdminAccount(username="guest_role_test", role="guest")
        guest.set_password("Password123")
        
        db.session.add(admin)
        db.session.add(guest)
        db.session.commit()
        
        # Test role methods
        assert admin.is_admin() is True
        assert admin.is_guest() is False
        assert guest.is_admin() is False
        assert guest.is_guest() is True
        
        # Test permissions
        assert admin.has_permission("manage_users") is True
        assert admin.has_permission("manage_settings") is True
        assert admin.has_permission("create_invites") is True
        
        assert guest.has_permission("manage_users") is False
        assert guest.has_permission("manage_settings") is False
        assert guest.has_permission("create_invites") is True
        assert guest.has_permission("view_invites") is True


def test_guest_can_access_invitations(client, app):
    """Test that guest accounts can access invitation pages."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_access_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_access_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Test access to invitation pages
        resp = client.get("/invites", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        resp = client.get("/invite", headers={"HX-Request": "true"})
        assert resp.status_code == 200


def test_guest_cannot_access_users(client, app):
    """Test that guest accounts cannot access user management pages."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_users_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_users_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Test blocked access to user pages
        resp = client.get("/users", headers={"HX-Request": "true"})
        assert resp.status_code == 403
        
        resp = client.get("/users/table")
        assert resp.status_code == 403


def test_guest_cannot_access_settings(client, app):
    """Test that guest accounts cannot access settings pages."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_settings_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_settings_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Test blocked access to settings pages
        resp = client.get("/settings", headers={"HX-Request": "true"})
        assert resp.status_code == 403
        
        resp = client.get("/settings/general")
        assert resp.status_code == 403


def test_guest_cannot_access_media_servers(client, app):
    """Test that guest accounts cannot access media server management."""
    with app.app_context():
        # Create guest account
        guest = AdminAccount(username="guest_media_test", role="guest")
        guest.set_password("Password123")
        db.session.add(guest)
        db.session.commit()
        
        # Login as guest
        resp = client.post("/login", data={"username": "guest_media_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Test blocked access to media server pages
        resp = client.get("/settings/servers")
        assert resp.status_code == 403
        
        resp = client.get("/settings/servers/create")
        assert resp.status_code == 403


def test_admin_has_full_access(client, app):
    """Test that admin accounts have full access to all areas."""
    with app.app_context():
        # Create admin account
        admin = AdminAccount(username="admin_full_access_test", role="admin")
        admin.set_password("Password123")
        db.session.add(admin)
        db.session.commit()
        
        # Login as admin
        resp = client.post("/login", data={"username": "admin_full_access_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Test access to all areas
        resp = client.get("/users", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        resp = client.get("/settings", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        resp = client.get("/invites", headers={"HX-Request": "true"})
        assert resp.status_code == 200


def test_create_guest_account_form(client, app):
    """Test creating a guest account through the admin interface."""
    with app.app_context():
        # Create admin account to access admin creation form
        admin = AdminAccount(username="admin_form_test", role="admin")
        admin.set_password("Password123")
        db.session.add(admin)
        db.session.commit()
        
        # Login as admin
        resp = client.post("/login", data={"username": "admin_form_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Create guest account
        resp = client.post("/settings/admins/create", data={
            "username": "new_guest",
            "password": "Password123",
            "confirm": "Password123",
            "role": "guest"
        })
        assert resp.status_code in {200, 302, 303}
        
        # Verify guest account was created with correct role
        guest = AdminAccount.query.filter_by(username="new_guest").first()
        assert guest is not None
        assert guest.role == "guest"
        assert guest.is_guest() is True


def test_legacy_admin_compatibility(app):
    """Test that legacy AdminUser still works with new permission system."""
    from app.models import AdminUser
    
    with app.app_context():
        # Create legacy admin user
        legacy_admin = AdminUser()
        
        # Test role methods exist and work correctly
        assert legacy_admin.is_admin() is True
        assert legacy_admin.is_guest() is False
        assert legacy_admin.has_permission("manage_users") is True
        assert legacy_admin.has_permission("create_invites") is True


def test_guest_invitation_isolation(client, app):
    """Test that guests can only see their own invitations."""
    from app.models import Invitation
    from app.services.invites import _generate_code
    from datetime import datetime
    
    with app.app_context():
        # Create first guest account
        guest1 = AdminAccount(username="guest_isolation1_test", role="guest")
        guest1.set_password("Password123")
        db.session.add(guest1)
        
        # Create second guest account  
        guest2 = AdminAccount(username="guest_isolation2_test", role="guest")
        guest2.set_password("Password123")
        db.session.add(guest2)
        
        # Create admin account
        admin = AdminAccount(username="admin_isolation_test", role="admin")
        admin.set_password("Password123")
        db.session.add(admin)
        
        db.session.commit()
        
        # Create invitations for each user
        invite1 = Invitation(
            code="GUEST1CODE",
            created_by_id=guest1.id,
            allow_live_tv=True,
            allow_downloads=True,
            created=datetime.now()
        )
        
        invite2 = Invitation(
            code="GUEST2CODE", 
            created_by_id=guest2.id,
            allow_live_tv=True,
            allow_downloads=True,
            created=datetime.now()
        )
        
        admin_invite = Invitation(
            code="ADMINCODE",
            created_by_id=admin.id,
            allow_live_tv=True,
            allow_downloads=True,
            created=datetime.now()
        )
        
        db.session.add_all([invite1, invite2, admin_invite])
        db.session.commit()
        
        # Login as guest1
        resp = client.post("/login", data={"username": "guest_isolation1_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Get invitation table as guest1
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Should see only guest1's invitation
        assert "GUEST1CODE" in resp.data.decode()
        assert "GUEST2CODE" not in resp.data.decode()
        assert "ADMINCODE" not in resp.data.decode()
        
        # Logout and login as guest2
        client.get("/logout")
        resp = client.post("/login", data={"username": "guest_isolation2_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Get invitation table as guest2
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Should see only guest2's invitation
        assert "GUEST2CODE" in resp.data.decode()
        assert "GUEST1CODE" not in resp.data.decode()
        assert "ADMINCODE" not in resp.data.decode()
        
        # Logout and login as admin
        client.get("/logout")
        resp = client.post("/login", data={"username": "admin_isolation_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        # Get invitation table as admin
        resp = client.post("/invite/table", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        
        # Should see all invitations
        assert "GUEST1CODE" in resp.data.decode()
        assert "GUEST2CODE" in resp.data.decode()
        assert "ADMINCODE" in resp.data.decode()


def test_home_route_role_based_views(client, app):
    """Test that /home shows dashboard for admins and invites for guests."""
    with app.app_context():
        # Create admin account
        admin = AdminAccount(username="admin_home_test", role="admin")
        admin.set_password("Password123")
        
        # Create guest account
        guest = AdminAccount(username="guest_home_test", role="guest")
        guest.set_password("Password123")
        
        db.session.add(admin)
        db.session.add(guest)
        db.session.commit()
        
        # Test admin sees home dashboard
        resp = client.post("/login", data={"username": "admin_home_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        resp = client.get("/home", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        # Check that it's the home dashboard (should contain now playing or dashboard elements)
        content = resp.data.decode()
        # The home template should be different from invites template
        assert "home.html" in str(resp) or "now-playing" in content.lower() or "dashboard" in content.lower()
        
        # Logout admin
        client.get("/logout")
        
        # Test guest sees invites page
        resp = client.post("/login", data={"username": "guest_home_test", "password": "Password123"})
        assert resp.status_code in {302, 303}
        
        resp = client.get("/home", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        # Check that it's the invites page
        content = resp.data.decode()
        # Should contain invite-related elements
        assert "invite" in content.lower() or "invitation" in content.lower()