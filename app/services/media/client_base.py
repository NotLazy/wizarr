#
# Media client abstraction & registry
# ----------------------------------
# Historically Wizarr stored the admin media-server credentials (URL & API key)
# in the generic Settings table.  We migrated these credentials to the new
# `MediaServer` table so Wizarr can manage several servers at once.  The base
# MediaClient now prefers to read credentials from a `MediaServer` row and only
# falls back to legacy Settings keys when no matching MediaServer exists (e.g.
# fresh installs that haven't yet completed the migration).

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import requests

from app.extensions import db
from app.models import MediaServer, Settings, User
from app.services.notifications import notify

if TYPE_CHECKING:
    from app.services.media.user_details import MediaUserDetails

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

# Holds mapping of server_type -> MediaClient subclass
CLIENTS: dict[str, type[MediaClient]] = {}


def register_media_client(name: str):
    """Decorator to register a MediaClient under a given *server_type* name.

    We additionally annotate the class with the attribute ``_server_type`` so
    instances can later resolve the corresponding ``MediaServer`` row without
    external knowledge.
    """

    def decorator(cls):
        cls._server_type = name  # type: ignore[attr-defined]
        CLIENTS[name] = cls
        return cls

    return decorator


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class MediaClient(ABC):
    """Common helper wrapper around third-party media-server SDKs.

    On initialisation we attempt the following resolution order for
    ``url`` and ``token``:

    1. *Explicit* ``media_server`` row, if provided.
    2. First ``MediaServer`` record with a ``server_type`` matching the class.
    3. Legacy ``Settings`` keys (``server_url`` / ``api_key``) for backwards
       compatibility – these will be removed in a future release.
    """

    url: str | None
    token: str | None

    # NOTE: keep *url_key* & *token_key* keyword arguments so older subclass
    # calls (e.g. super().__init__(url_key="server_url")) continue to work.

    def __init__(
        self,
        media_server: MediaServer | None = None,
        *,
        url_key: str = "server_url",
        token_key: str = "api_key",
    ) -> None:
        # ------------------------------------------------------------------
        # 1. Direct MediaServer row supplied
        # ------------------------------------------------------------------
        if media_server is not None:
            self._attach_server_row(media_server)
            return

        # ------------------------------------------------------------------
        # 2. Lookup matching MediaServer by server_type (if available)
        # ------------------------------------------------------------------
        server_type = getattr(self.__class__, "_server_type", None)
        if server_type:
            row = (
                db.session.query(MediaServer).filter_by(server_type=server_type).first()
            )
            if row is not None:
                self._attach_server_row(row)
                return

        # ------------------------------------------------------------------
        # 3. Legacy Settings fallback
        # ------------------------------------------------------------------
        # When falling back we *do not* set ``server_row`` nor ``server_id`` –
        # callers relying on those attributes should migrate to supply a
        # MediaServer.

        self.url = db.session.query(Settings.value).filter_by(key=url_key).scalar()
        self.token = db.session.query(Settings.value).filter_by(key=token_key).scalar()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _attach_server_row(self, row: MediaServer) -> None:
        """Populate instance attributes from a MediaServer row."""
        self.server_row: MediaServer = row
        self.server_id: int = row.id  # type: ignore[attr-defined]
        self.url = row.url  # type: ignore[attr-defined]
        self.token = row.api_key  # type: ignore[attr-defined]

    def generate_image_proxy_url(self, image_url: str) -> str:
        """
        Generate a secure proxy URL for an image.

        Args:
            image_url: The raw image URL from the media server

        Returns:
            Secure proxy URL with opaque token: /image-proxy?token=xxx
        """
        from urllib.parse import quote_plus

        from app.services.image_proxy import ImageProxyService

        # Generate opaque token for this URL
        token = ImageProxyService.generate_token(image_url, server_id=self.server_id)

        # Return proxy URL with token
        return f"/image-proxy?token={quote_plus(token)}"

    def _create_user_with_identity_linking(self, user_kwargs: dict) -> User:
        """Create a User record with intelligent identity linking based on invitation type.

        This helper implements the correct identity linking logic:

        - **Limited invitations**: Always link users with the same code (same person across servers)
        - **Unlimited invitations**: Only link users with same code AND same email (same person across servers)

        This prevents the bug where different people using the same unlimited invite
        would get incorrectly linked, while still allowing the same person to be
        properly linked across multiple servers.

        Args:
            user_kwargs: Dictionary of User model attributes

        Returns:
            User: The created User record with identity_id set if applicable
        """
        code = user_kwargs.get("code")
        email = user_kwargs.get("email")

        # Check if this is part of a multi-server invitation
        if code:
            from app.models import Invitation
            from app.services.media.service import EMAIL_RE

            invitation = Invitation.query.filter_by(code=code).first()

            if invitation:
                if not invitation.unlimited:
                    # LIMITED invites: Always link users with same code (same person across servers)
                    existing_user = User.query.filter_by(code=code).first()
                    if existing_user and existing_user.identity_id:
                        user_kwargs["identity_id"] = existing_user.identity_id
                else:
                    # UNLIMITED invites: Only link if same email (same person across servers)
                    # Different emails = different people, should remain separate
                    if email and EMAIL_RE.fullmatch(email):
                        existing_user = User.query.filter_by(
                            code=code, email=email
                        ).first()
                        if existing_user and existing_user.identity_id:
                            user_kwargs["identity_id"] = existing_user.identity_id

        # Clean up any expired user records for this email address
        if email:
            from app.services.expiry import cleanup_expired_user_by_email

            cleanup_expired_user_by_email(email)

        new_user = User(**user_kwargs)
        db.session.add(new_user)
        return new_user

    @abstractmethod
    def libraries(self):
        raise NotImplementedError

    @abstractmethod
    def create_user(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def update_user(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def disable_user(self, user_id: str) -> bool:
        """Disable a user account on the media server.

        Args:
            user_id: The user's ID on the media server

        Returns:
            bool: True if the user was successfully disabled, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def delete_user(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def get_user(self, *args, **kwargs):
        raise NotImplementedError

    def get_user_details(self, user_identifier: str | int) -> MediaUserDetails:
        """Get detailed user information in standardized format.

        Args:
            user_identifier: User ID, email, or username depending on server type

        Returns:
            MediaUserDetails: Standardized user details with libraries and policies

        Note:
            Default implementation delegates to get_user() for backward compatibility.
            Media clients should override this method to return MediaUserDetails directly.
        """
        from app.services.media.user_details import MediaUserDetails

        # Fallback: use existing get_user and attempt basic conversion
        raw_details = self.get_user(user_identifier)

        return MediaUserDetails(
            user_id=str(user_identifier),
            username=raw_details.get("username", "Unknown"),
            email=raw_details.get("email"),
            raw_policies=raw_details,
        )

    def _cache_user_metadata_batch(self, users: list[User]) -> None:
        """Cache metadata for a batch of users to improve performance.

        This method fetches detailed metadata for each user and caches it in the database
        to avoid repeated API calls when viewing user details.

        Args:
            users: List of User objects to cache metadata for
        """
        if not users:
            return

        cached_count = 0
        for user in users:
            try:
                # Determine the appropriate user identifier for this server type
                user_identifier = self._get_user_identifier_for_details(user)
                if not user_identifier:
                    continue

                # Get detailed metadata from the server
                details = self.get_user_details(user_identifier)

                # Update the standardized metadata columns in the User record
                user.update_standardized_metadata(details)
                cached_count += 1

            except Exception as e:
                import logging

                logging.warning(
                    f"Failed to cache metadata for user {user.username}: {e}"
                )
                continue

        if cached_count > 0:
            try:
                db.session.commit()
                import logging

                logging.info(f"Cached metadata for {cached_count} users")
            except Exception as e:
                import logging

                logging.error(f"Failed to commit metadata cache: {e}")
                db.session.rollback()

    def _get_user_identifier_for_details(self, user: User) -> str | int | None:
        """Get the appropriate identifier to use for get_user_details() calls.

        Different server types use different identifiers (token, email, username).
        Subclasses should override this method to return the correct identifier.

        Args:
            user: User record

        Returns:
            Identifier to use for get_user_details(), or None if unavailable
        """
        # Default implementation uses token (works for most servers)
        return user.token if user.token else None

    @abstractmethod
    def list_users(self, *args, **kwargs):
        """Return a list of users for this media server. Subclasses must implement."""
        raise NotImplementedError

    @abstractmethod
    def now_playing(self):
        """Return a list of currently playing sessions for this media server.

        Returns:
            list: A list of session dictionaries with standardized keys including:
                - user_name: Name of the user currently playing
                - media_title: Title of the media being played
                - media_type: Type of media (movie, episode, track, etc.)
                - progress: Playback progress (0.0 to 1.0)
                - state: Playback state (playing, paused, buffering, stopped)
                - session_id: Unique identifier for the session
        """
        raise NotImplementedError

    def get_recent_items(
        self, library_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """Get recently added items from the media server.

        Args:
            library_id: Optional library ID to filter by
            limit: Maximum number of items to return

        Returns:
            list: A list of recently added items with standardized keys:
                - title: Title of the media item
                - year: Release year (if available)
                - thumb: Thumbnail URL (if available)
                - type: Media type (movie, episode, track, etc.)
                - added_at: Unix timestamp when item was added
        """
        # Default implementation returns empty list
        # Subclasses should override this method
        return []

    @abstractmethod
    def statistics(self):
        """Return comprehensive server statistics including library counts, user activity, etc.

        Note: This method may trigger user synchronization and database writes.
        For health monitoring without database impact, use get_readonly_statistics() instead.

        Returns:
            dict: A dictionary containing:
                - library_stats: Library breakdown with counts per type
                - user_stats: User activity and count information
                - server_stats: Server health and performance metrics
                - content_stats: Content consumption and popular items
        """
        raise NotImplementedError

    def get_user_count(self) -> int:
        """Get lightweight user count without triggering full user sync.

        This method should provide a fast user count for health monitoring
        without the overhead of syncing user policies or metadata.

        Returns:
            int: Number of users on the server
        """
        # Default implementation uses existing statistics() but subclasses should override
        try:
            stats = self.statistics()
            return stats.get("user_stats", {}).get("total_users", 0)
        except Exception:
            return 0

    def get_server_info(self) -> dict:
        """Get lightweight server information without triggering user sync.

        This method should provide basic server health info for monitoring
        without the overhead of full user synchronization.

        Returns:
            dict: Basic server information (version, status, etc.)
        """
        # Default implementation uses existing statistics() but subclasses should override
        try:
            stats = self.statistics()
            return {
                "version": stats.get("server_stats", {}).get("version", "Unknown"),
                "transcoding_sessions": stats.get("server_stats", {}).get(
                    "transcoding_sessions", 0
                ),
                "active_sessions": stats.get("user_stats", {}).get(
                    "active_sessions", 0
                ),
            }
        except Exception:
            return {
                "version": "Unknown",
                "transcoding_sessions": 0,
                "active_sessions": 0,
            }

    def get_readonly_statistics(self) -> dict:
        """Get lightweight statistics for health monitoring without database writes.

        This method provides essential server statistics for health cards
        without triggering heavy user synchronization that can cause database locks.
        Subclasses should override this to provide efficient readonly access.

        Returns:
            dict: Lightweight statistics with user count and server info
        """
        return {
            "user_stats": {
                "total_users": self.get_user_count(),
                "active_sessions": 0,  # Will be populated by subclass overrides
            },
            "server_stats": self.get_server_info(),
            "library_stats": {},  # Minimal for health cards
            "content_stats": {},  # Minimal for health cards
        }

    def join(self, username: str, password: str, confirm: str, code: str):
        """Process user invitation for this media server.

        This is a template method that handles notifications after successful user creation.
        Subclasses should implement _do_join() instead of overriding this method.

        Args:
            username: Username for the new account
            password: Password for the new account
            confirm: Password confirmation
            code: Invitation code being used

        Returns:
            tuple: (success: bool, message: str)
        """
        # Call the concrete implementation
        success, message = self._do_join(username, password, confirm, code)

        # Send notification on successful join
        if success:
            try:
                notify(
                    "New User",
                    f"User {username} has joined your server! 🎉",
                    tags="tada",
                    event_type="user_joined",
                )
            except Exception as e:
                logging.warning(f"Failed to send join notification: {e}")

        return success, message

    @abstractmethod
    def _do_join(
        self, username: str, password: str, confirm: str, code: str
    ):
        """Process user invitation for this media server (implementation method).

        This method should be implemented by subclasses to handle the actual user creation logic.
        Notifications are handled automatically by the public join() method.

        Args:
            username: Username for the new account
            password: Password for the new account
            confirm: Password confirmation
            code: Invitation code being used

        Returns:
            tuple: (success: bool, message: str)
        """
        raise NotImplementedError

    @abstractmethod
    def scan_libraries(self, url: str | None = None, token: str | None = None):
        """Scan available libraries on this media server.

        Args:
            url: Optional server URL override
            token: Optional API token override

        Returns:
            dict: Library name -> library ID mapping
        """
        raise NotImplementedError

    def invite_home(
        self, email: str, sections: list[str], allow_sync: bool, allow_channels: bool
    ):
        """Invite a user to the home server (if supported).

        Args:
            email: Email address of the user to invite
            sections: List of library sections to grant access to
            allow_sync: Whether to allow syncing
            allow_channels: Whether to allow channel access
        """
        raise NotImplementedError("invite_home not implemented for this server type")

    def invite_friend(
        self, email: str, sections: list[str], allow_sync: bool, allow_channels: bool
    ):
        """Invite a user as a friend (if supported).

        Args:
            email: Email address of the user to invite
            sections: List of library sections to grant access to
            allow_sync: Whether to allow syncing
            allow_channels: Whether to allow channel access
        """
        raise NotImplementedError("invite_friend not implemented for this server type")


# ---------------------------------------------------------------------------
# Shared helpers for simple REST JSON backends
# ---------------------------------------------------------------------------


class RestApiMixin(MediaClient):
    """Mixin that adds minimal HTTP helpers for JSON-based REST APIs.

    Subclasses only need to implement ``_headers`` if they require
    authentication headers beyond the defaults.  The mixin centralises
    logging, error handling and URL joining so individual back-ends can keep
    their method bodies small and readable.
    """

    # ------------------------------------------------------------------
    # Customisation hooks
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:  # noqa: D401
        """Return default headers for every request (override as needed)."""
        return {
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Thin wrappers around ``requests`` so subclasses never import it
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs):
        """Make HTTP request with consistent error handling and logging."""
        if self.url is None:
            raise ValueError("Media server URL is not configured")

        url = f"{self.url.rstrip('/')}{path}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}

        logging.info("%s %s", method.upper(), url)
        try:
            response = requests.request(
                method, url, headers=headers, timeout=10, **kwargs
            )
            logging.info("→ %s", response.status_code)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.error("Request failed: %s", e)
            raise

    # Convenience helpers ------------------------------------------------

    def get(self, path: str, **kwargs):
        """Make GET request to API endpoint."""
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        """Make POST request to API endpoint."""
        return self._request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs):
        """Make PATCH request to API endpoint."""
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        """Make DELETE request to API endpoint."""
        return self._request("DELETE", path, **kwargs)

    def put(self, path: str, **kwargs):
        """Make PUT request to API endpoint."""
        return self._request("PUT", path, **kwargs)
