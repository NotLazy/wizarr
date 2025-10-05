"""
Permission decorators for role-based access control.

This module provides decorators to restrict access to routes based on admin account roles.
"""

from functools import wraps
from flask import abort, current_app
from flask_login import current_user, login_required


def admin_required(f):
    """Decorator that requires admin role.
    
    Can be used in combination with @login_required or standalone (it includes login check).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First ensure user is logged in
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        
        # Check if user has admin role
        if hasattr(current_user, 'is_admin') and current_user.is_admin():
            return f(*args, **kwargs)
        
        # For legacy AdminUser (single admin), allow access
        if hasattr(current_user, 'id') and current_user.id == 'admin':
            return f(*args, **kwargs)
            
        # Deny access
        abort(403)
        
    return decorated_function


def permission_required(permission):
    """Decorator that requires a specific permission.
    
    Args:
        permission (str): The permission name to check (e.g., 'manage_users', 'create_invites')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # First ensure user is logged in
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            
            # Check if user has the required permission
            if hasattr(current_user, 'has_permission') and current_user.has_permission(permission):
                return f(*args, **kwargs)
            
            # For legacy AdminUser (single admin), allow all permissions
            if hasattr(current_user, 'id') and current_user.id == 'admin':
                return f(*args, **kwargs)
                
            # Deny access
            abort(403)
            
        return decorated_function
    return decorator


def guest_allowed(f):
    """Decorator that allows both admin and guest roles.
    
    This is for routes that guests should be able to access (like creating invites).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First ensure user is logged in
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        
        # Allow access for any authenticated admin account or legacy admin
        if hasattr(current_user, 'role') or (hasattr(current_user, 'id') and current_user.id == 'admin'):
            return f(*args, **kwargs)
            
        # Deny access
        abort(403)
        
    return decorated_function