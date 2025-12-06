"""
Authentication module for user login and registration.
Handles user management with CSV-based storage and JWT tokens.
"""

import os
import csv
import hashlib
import logging
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

try:
    from jose import JWTError, jwt
except ImportError:
    # Fallback if jose not available
    JWTError = Exception
    jwt = None

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class UserAuth:
    """User authentication and management system."""
    
    def __init__(self, csv_path: str = "data/Users.csv"):
        """
        Initialize authentication system.
        
        Args:
            csv_path: Path to Users.csv file
        """
        self.csv_path = csv_path
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Ensure Users.csv exists with proper headers."""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['index', 'first_name', 'last_name', 'username', 'email', 'password'])
                # Add default admin user
                writer.writerow(['1', 'Admin', 'User', 'admin', 'admin@akinchan.com', self._hash_password('admin123')])
            logger.info("Created Users.csv with default admin user")
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using SHA-256.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        return self._hash_password(plain_password) == hashed_password
    
    def _get_next_index(self) -> int:
        """Get next available user index."""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                indices = [int(row['index']) for row in reader if row['index'].isdigit()]
                return max(indices, default=0) + 1
        except Exception as e:
            logger.error(f"Error getting next index: {e}")
            return 1
    
    def register_user(
        self,
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Register a new user.
        
        Args:
            first_name: User's first name
            last_name: User's last name
            username: Unique username
            email: User's email address
            password: Plain text password (will be hashed)
            
        Returns:
            Dictionary with success status and message
        """
        try:
            # Validate inputs
            if not all([first_name, last_name, username, email, password]):
                return {"success": False, "message": "All fields are required"}
            
            # Check if username or email already exists
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['username'].lower() == username.lower():
                        return {"success": False, "message": "Username already exists"}
                    if row['email'].lower() == email.lower():
                        return {"success": False, "message": "Email already exists"}
            
            # Add new user
            next_index = self._get_next_index()
            hashed_password = self._hash_password(password)
            
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([next_index, first_name, last_name, username, email, hashed_password])
            
            logger.info(f"New user registered: {username} ({email})")
            return {
                "success": True,
                "message": "Registration successful! Please login.",
                "user": {
                    "index": next_index,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                    "email": email
                }
            }
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {"success": False, "message": f"Registration failed: {str(e)}"}
    
    def authenticate_user(self, login: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with username/email and password.
        
        Args:
            login: Username or email
            password: Plain text password
            
        Returns:
            Dictionary with success status, message, user data, and JWT token
        """
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Check if login matches username or email
                    if (row['username'].lower() == login.lower() or 
                        row['email'].lower() == login.lower()):
                        
                        if self._verify_password(password, row['password']):
                            # Create JWT token
                            token = self.create_access_token(
                                data={"sub": row['username'], "email": row['email']}
                            )
                            
                            logger.info(f"User logged in: {row['username']}")
                            return {
                                "success": True,
                                "message": "Login successful",
                                "token": token,
                                "user": {
                                    "user_id": row['index'],  # Use index as user_id
                                    "index": row['index'],
                                    "first_name": row['first_name'],
                                    "last_name": row['last_name'],
                                    "username": row['username'],
                                    "email": row['email']
                                }
                            }
                        else:
                            return {"success": False, "message": "Invalid password"}
            
            return {"success": False, "message": "User not found"}
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return {"success": False, "message": f"Authentication failed: {str(e)}"}
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, str]]:
        """
        Get user details by username.
        
        Args:
            username: Username to search for
            
        Returns:
            User dictionary or None if not found
        """
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['username'].lower() == username.lower():
                        return {
                            "index": row['index'],
                            "first_name": row['first_name'],
                            "last_name": row['last_name'],
                            "username": row['username'],
                            "email": row['email']
                        }
            return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def update_user_profile(self, username: str, first_name: str, last_name: str, email: str) -> Dict[str, Any]:
        """
        Update user profile information.
        
        Args:
            username: Username of the user to update
            first_name: New first name
            last_name: New last name
            email: New email
            
        Returns:
            Dictionary with success status and message
        """
        try:
            users = []
            updated = False
            
            # Read all users
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['username'].lower() == username.lower():
                        row['first_name'] = first_name
                        row['last_name'] = last_name
                        row['email'] = email
                        updated = True
                    users.append(row)
            
            if not updated:
                return {"success": False, "message": "User not found"}
            
            # Write back all users
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['index', 'first_name', 'last_name', 'username', 'email', 'password'])
                writer.writeheader()
                writer.writerows(users)
            
            logger.info(f"User profile updated: {username}")
            return {"success": True, "message": "Profile updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            return {"success": False, "message": f"Update failed: {str(e)}"}
    
    def reset_password(self, email: str, new_password: str) -> Dict[str, Any]:
        """
        Reset user password by email.
        
        Args:
            email: User's email address
            new_password: New password (will be hashed)
            
        Returns:
            Dictionary with success status and message
        """
        try:
            users = []
            updated = False
            
            # Read all users
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['email'].lower() == email.lower():
                        row['password'] = self._hash_password(new_password)
                        updated = True
                    users.append(row)
            
            if not updated:
                return {"success": False, "message": "Email not found"}
            
            # Write back all users
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['index', 'first_name', 'last_name', 'username', 'email', 'password'])
                writer.writeheader()
                writer.writerows(users)
            
            logger.info(f"Password reset for email: {email}")
            return {"success": True, "message": "Password reset successfully"}
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return {"success": False, "message": f"Reset failed: {str(e)}"}
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time
            
        Returns:
            Encoded JWT token
        """
        if jwt is None:
            # Fallback: return a simple token if jose not available
            return f"simple_token_{data.get('sub', 'user')}_{datetime.utcnow().timestamp()}"
        
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and extract user data.
        
        Args:
            token: JWT token to verify
            
        Returns:
            User data if valid, None otherwise
        """
        if jwt is None:
            # Fallback: extract username from simple token
            if token.startswith("simple_token_"):
                parts = token.split("_")
                if len(parts) >= 3:
                    username = parts[2]
                    return self.get_user_by_username(username)
            return None
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username is None:
                return None
            return self.get_user_by_username(username)
        except JWTError:
            return None


# Singleton instance
_auth_instance = None

def get_auth() -> UserAuth:
    """Get singleton authentication instance."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = UserAuth()
    return _auth_instance
