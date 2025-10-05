"""Tests for Jellyfin authentication integration."""

import pytest
import responses
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import AdminAccount, MediaServer
from app.services.jellyfin_auth import authenticate_jellyfin_user, create_guest_account_from_jellyfin


def test_jellyfin_authentication_success(app):
    """Test successful Jellyfin authentication."""
    with app.app_context():
        # Create a test Jellyfin server
        server = MediaServer(
            name="Test Jellyfin",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Mock successful Jellyfin response
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8096/Users/AuthenticateByName",
                json={
                    "User": {
                        "Id": "test-user-id",
                        "Name": "testuser",
                        "HasPassword": True,
                        "HasConfiguredPassword": True,
                        "Policy": {}
                    },
                    "ServerId": "test-server-id",
                    "AccessToken": "test-access-token"
                },
                status=200
            )
            
            success, server_name, user_info = authenticate_jellyfin_user("testuser", "testpass")
            
            assert success is True
            assert server_name == "Test Jellyfin"
            assert user_info["id"] == "test-user-id"
            assert user_info["name"] == "testuser"


def test_jellyfin_authentication_invalid_credentials(app):
    """Test Jellyfin authentication with invalid credentials."""
    with app.app_context():
        # Create a test Jellyfin server
        server = MediaServer(
            name="Test Jellyfin",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Mock failed Jellyfin response
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8096/Users/AuthenticateByName",
                status=401
            )
            
            success, server_name, user_info = authenticate_jellyfin_user("testuser", "wrongpass")
            
            assert success is False
            assert server_name is None
            assert user_info is None


def test_create_guest_account_from_jellyfin(app):
    """Test creating a guest account from Jellyfin user info."""
    with app.app_context():
        user_info = {
            "id": "test-user-id",
            "name": "testuser",
            "server_id": "test-server-id"
        }
        
        account = create_guest_account_from_jellyfin("testuser", "Test Jellyfin", user_info)
        
        assert account.username == "testuser"
        assert account.role == "guest"
        assert account.jellyfin_server == "Test Jellyfin"
        assert account.jellyfin_user_id == "test-user-id"
        assert account.is_guest() is True
        assert account.is_admin() is False


def test_jellyfin_login_creates_guest_account(client, app):
    """Test that logging in with Jellyfin credentials creates a guest account."""
    with app.app_context():
        # Create a test Jellyfin server
        server = MediaServer(
            name="Test Jellyfin",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        db.session.commit()
        
        # Mock successful Jellyfin response
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8096/Users/AuthenticateByName",
                json={
                    "User": {
                        "Id": "test-user-id",
                        "Name": "jellyfinuser",
                        "HasPassword": True,
                        "HasConfiguredPassword": True,
                        "Policy": {}
                    },
                    "ServerId": "test-server-id",
                    "AccessToken": "test-access-token"
                },
                status=200
            )
            
            # Attempt login with Jellyfin credentials
            resp = client.post("/login", data={
                "username": "jellyfinuser",
                "password": "jellyfinpass"
            })
            
            # Should redirect on successful login
            assert resp.status_code in {302, 303}
            
            # Check that a guest account was created
            account = AdminAccount.query.filter_by(username="jellyfinuser").first()
            assert account is not None
            assert account.role == "guest"
            assert account.jellyfin_server == "Test Jellyfin"
            assert account.jellyfin_user_id == "test-user-id"


def test_existing_jellyfin_account_login(client, app):
    """Test that existing Jellyfin-linked accounts can log in."""
    with app.app_context():
        # Create a test Jellyfin server
        server = MediaServer(
            name="Test Jellyfin",
            server_type="jellyfin",
            url="http://localhost:8096",
            api_key="test_key",
            verified=True
        )
        db.session.add(server)
        
        # Create an existing Jellyfin-linked account
        account = AdminAccount(
            username="existinguser",
            role="guest",
            jellyfin_server="Test Jellyfin",
            jellyfin_user_id="existing-user-id"
        )
        account.set_password("dummy-password")  # Won't be used for auth
        db.session.add(account)
        db.session.commit()
        
        # Mock successful Jellyfin response
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8096/Users/AuthenticateByName",
                json={
                    "User": {
                        "Id": "existing-user-id",
                        "Name": "existinguser",
                        "HasPassword": True,
                        "HasConfiguredPassword": True,
                        "Policy": {}
                    },
                    "ServerId": "test-server-id",
                    "AccessToken": "test-access-token"
                },
                status=200
            )
            
            # Attempt login with Jellyfin credentials
            resp = client.post("/login", data={
                "username": "existinguser",
                "password": "jellyfinpass"
            })
            
            # Should redirect on successful login
            assert resp.status_code in {302, 303}
            
            # Account should still exist and not be duplicated
            accounts = AdminAccount.query.filter_by(username="existinguser").all()
            assert len(accounts) == 1
            assert accounts[0].jellyfin_server == "Test Jellyfin"


def test_no_jellyfin_servers_configured(app):
    """Test behavior when no Jellyfin servers are configured."""
    with app.app_context():
        # No Jellyfin servers in database
        success, server_name, user_info = authenticate_jellyfin_user("testuser", "testpass")
        
        assert success is False
        assert server_name is None
        assert user_info is None