"""Jellyfin authentication service for validating user credentials."""

import logging
import requests
from typing import Optional, Tuple

from app.models import MediaServer


def authenticate_jellyfin_user(username: str, password: str) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Authenticate a user against all available Jellyfin servers.
    
    Args:
        username: The username to authenticate
        password: The password to authenticate
        
    Returns:
        Tuple of (success, server_name, user_info)
        - success: Boolean indicating if authentication was successful
        - server_name: Name of the server that authenticated the user (if successful)
        - user_info: User information from Jellyfin (if successful)
    """
    # Get all Jellyfin servers
    jellyfin_servers = MediaServer.query.filter_by(server_type="jellyfin").all()
    
    if not jellyfin_servers:
        logging.warning("No Jellyfin servers configured for authentication")
        return False, None, None
    
    for server in jellyfin_servers:
        try:
            success, user_info = _authenticate_against_server(
                server.url, username, password
            )
            if success:
                return True, server.name, user_info
        except Exception as e:
            logging.warning(f"Failed to authenticate against {server.name}: {e}")
            continue
    
    return False, None, None


def _authenticate_against_server(server_url: str, username: str, password: str) -> Tuple[bool, Optional[dict]]:
    """
    Authenticate against a specific Jellyfin server.
    
    Args:
        server_url: The Jellyfin server URL
        username: The username to authenticate
        password: The password to authenticate
        
    Returns:
        Tuple of (success, user_info)
    """
    # Ensure server_url ends with proper format
    if not server_url.endswith('/'):
        server_url += '/'
    
    auth_url = f"{server_url}Users/AuthenticateByName"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Emby-Authorization": 'MediaBrowser Client="Wizarr", Device="Wizarr", DeviceId="wizarr-auth", Version="1.0.0"'
    }
    
    payload = {
        "Username": username,
        "Pw": password
    }
    
    try:
        response = requests.post(
            auth_url, 
            json=payload, 
            headers=headers, 
            timeout=10,
            verify=True
        )
        
        if response.status_code == 200:
            user_data = response.json()
            # Extract relevant user information
            user_info = {
                "id": user_data.get("User", {}).get("Id"),
                "name": user_data.get("User", {}).get("Name"),
                "has_password": user_data.get("User", {}).get("HasPassword", True),
                "has_configured_password": user_data.get("User", {}).get("HasConfiguredPassword", True),
                "server_id": user_data.get("ServerId"),
                "access_token": user_data.get("AccessToken"),
                "policy": user_data.get("User", {}).get("Policy", {})
            }
            logging.info(f"Successfully authenticated user '{username}' against Jellyfin server")
            return True, user_info
        elif response.status_code == 401:
            # Invalid credentials
            logging.debug(f"Invalid credentials for user '{username}' on Jellyfin server")
            return False, None
        else:
            logging.warning(f"Jellyfin authentication failed with status {response.status_code}: {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during Jellyfin authentication: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during Jellyfin authentication: {e}")
        raise


def create_guest_account_from_jellyfin(username: str, jellyfin_server_name: str, user_info: dict) -> 'AdminAccount':
    """
    Create a new guest account based on Jellyfin user information.
    
    Args:
        username: The username for the new account
        jellyfin_server_name: Name of the Jellyfin server that authenticated the user
        user_info: User information from Jellyfin authentication
        
    Returns:
        The created AdminAccount instance
    """
    from app.models import AdminAccount
    from app.extensions import db
    
    # Create a new guest account
    account = AdminAccount(
        username=username,
        role="guest",
        jellyfin_server=jellyfin_server_name,
        jellyfin_user_id=user_info.get("id")
    )
    
    # We don't store the actual password since we'll authenticate against Jellyfin
    # Set a random password that won't be used for local auth
    import secrets
    account.set_password(secrets.token_urlsafe(32))
    
    db.session.add(account)
    db.session.commit()
    
    logging.info(f"Created guest account for Jellyfin user '{username}' from server '{jellyfin_server_name}'")
    return account