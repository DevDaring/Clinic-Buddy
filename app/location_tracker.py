"""
Location tracking module for login auditing.
Tracks user login location using IP geolocation and stores in append-only CSV.
"""

import os
import csv
import logging
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import Request

logger = logging.getLogger(__name__)

class LocationTracker:
    """Track and log user login locations."""
    
    def __init__(self, csv_path: str = "data/login_history.csv"):
        """
        Initialize location tracker.
        
        Args:
            csv_path: Path to login history CSV file
        """
        self.csv_path = csv_path
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Ensure login_history.csv exists with proper headers."""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'user_id',
                    'username',
                    'ip_address',
                    'country',
                    'region',
                    'city',
                    'latitude',
                    'longitude',
                    'isp',
                    'timezone'
                ])
            logger.info("Created login_history.csv")
            
            # Make file read-only for security (on Windows)
            try:
                os.chmod(self.csv_path, 0o444)  # Read-only
                logger.info("Set login_history.csv to read-only (security)")
            except Exception as e:
                logger.warning(f"Could not set file permissions: {e}")
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address
        """
        # Check for proxy headers first
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For can contain multiple IPs, take the first (client)
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _get_location_from_ip(self, ip_address: str) -> Dict[str, Any]:
        """
        Get geolocation data from IP address using free API.
        
        Args:
            ip_address: IP address to lookup
            
        Returns:
            Dictionary with location data
        """
        # Default values
        location_data = {
            'country': 'Unknown',
            'region': 'Unknown',
            'city': 'Unknown',
            'latitude': '0.0',
            'longitude': '0.0',
            'isp': 'Unknown',
            'timezone': 'Unknown'
        }
        
        # Skip for localhost/private IPs
        if ip_address in ['127.0.0.1', 'localhost', 'unknown'] or ip_address.startswith('192.168.'):
            location_data['country'] = 'Localhost'
            location_data['city'] = 'Local Machine'
            return location_data
        
        try:
            # Use ip-api.com (free, no API key needed, 45 requests/minute)
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://ip-api.com/json/{ip_address}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'success':
                        location_data = {
                            'country': data.get('country', 'Unknown'),
                            'region': data.get('regionName', 'Unknown'),
                            'city': data.get('city', 'Unknown'),
                            'latitude': str(data.get('lat', 0.0)),
                            'longitude': str(data.get('lon', 0.0)),
                            'isp': data.get('isp', 'Unknown'),
                            'timezone': data.get('timezone', 'Unknown')
                        }
                        logger.info(f"✓ Location lookup successful: {location_data['city']}, {location_data['country']}")
                    else:
                        logger.warning(f"Geolocation API returned error: {data.get('message', 'Unknown')}")
                else:
                    logger.warning(f"Geolocation API returned status {response.status_code}")
        
        except httpx.TimeoutException:
            logger.warning("Geolocation API timeout")
        except Exception as e:
            logger.error(f"Error fetching location data: {str(e)}")
        
        return location_data
    
    async def _get_location_from_gps(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Get location name from GPS coordinates using reverse geocoding.
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            
        Returns:
            Dictionary with location data
        """
        # Default values
        location_data = {
            'country': 'Unknown',
            'region': 'Unknown',
            'city': 'Unknown',
            'isp': 'GPS Location',
            'timezone': 'Unknown'
        }
        
        try:
            # Use Nominatim reverse geocoding (OpenStreetMap - free, no API key)
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Add user agent as required by Nominatim
                headers = {
                    'User-Agent': 'Clinic-Buddy Clinical Trial Simulator/1.0'
                }
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=10&addressdetails=1"
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    address = data.get('address', {})
                    
                    location_data = {
                        'country': address.get('country', 'Unknown'),
                        'region': address.get('state', address.get('region', 'Unknown')),
                        'city': address.get('city', address.get('town', address.get('village', 'Unknown'))),
                        'isp': 'GPS Location',
                        'timezone': 'Unknown'  # Nominatim doesn't provide timezone
                    }
                    logger.info(f"✓ Reverse geocoding successful: {location_data['city']}, {location_data['country']}")
                else:
                    logger.warning(f"Reverse geocoding API returned status {response.status_code}")
        
        except httpx.TimeoutException:
            logger.warning("Reverse geocoding API timeout")
        except Exception as e:
            logger.error(f"Error in reverse geocoding: {str(e)}")
        
        return location_data

    async def log_login_gps(
        self, 
        request: Request, 
        user_id: str, 
        username: str,
        gps_latitude: Optional[float] = None,
        gps_longitude: Optional[float] = None,
        gps_accuracy: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Log user login with GPS-based location data.
        
        Args:
            request: FastAPI request object
            user_id: User ID
            username: Username
            gps_latitude: GPS latitude from browser
            gps_longitude: GPS longitude from browser
            gps_accuracy: GPS accuracy in meters
            
        Returns:
            Dictionary with logged data
        """
        try:
            # Use GPS coordinates if provided
            if gps_latitude is not None and gps_longitude is not None:
                logger.info(f"📍 Login with GPS: {gps_latitude}, {gps_longitude} (accuracy: {gps_accuracy}m)")
                
                # Get location name from coordinates using reverse geocoding
                location_data = await self._get_location_from_gps(gps_latitude, gps_longitude)
                
                # Use GPS coordinates
                location_data['latitude'] = str(gps_latitude)
                location_data['longitude'] = str(gps_longitude)
                
                # Add accuracy info to ISP field
                if gps_accuracy:
                    location_data['isp'] = f"GPS Location (±{int(gps_accuracy)}m)"
                
            else:
                # Fallback: No GPS provided
                logger.warning("No GPS coordinates provided, using fallback")
                location_data = {
                    'country': 'Unknown',
                    'region': 'Unknown',
                    'city': 'GPS Denied or Unavailable',
                    'latitude': '0.0',
                    'longitude': '0.0',
                    'isp': 'No GPS Data',
                    'timezone': 'Unknown'
                }
            
            # Get IP address for reference
            ip_address = self._get_client_ip(request)
            
            # Prepare log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_entry = {
                'timestamp': timestamp,
                'user_id': user_id,
                'username': username,
                'ip_address': ip_address,
                **location_data
            }
            
            # Temporarily make file writable to append
            try:
                os.chmod(self.csv_path, 0o644)  # Read-write
            except:
                pass
            
            # Append to CSV
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'user_id', 'username', 'ip_address',
                    'country', 'region', 'city', 'latitude', 'longitude',
                    'isp', 'timezone'
                ])
                writer.writerow(log_entry)
            
            # Make file read-only again
            try:
                os.chmod(self.csv_path, 0o444)  # Read-only
            except:
                pass
            
            logger.info(f"✓ GPS login logged: {username} from {location_data['city']}, {location_data['country']}")
            
            return log_entry
            
        except Exception as e:
            logger.error(f"❌ Error logging GPS login: {str(e)}")
            logger.exception("GPS login logging error:")
            return {}

    async def log_login(
        self, 
        request: Request, 
        user_id: str, 
        username: str
    ) -> Dict[str, Any]:
        """
        Log user login with location data.
        
        Args:
            request: FastAPI request object
            user_id: User ID
            username: Username
            
        Returns:
            Dictionary with logged data
        """
        try:
            # Get IP address
            ip_address = self._get_client_ip(request)
            logger.info(f"📍 Login from IP: {ip_address}")
            
            # Get location data
            location_data = await self._get_location_from_ip(ip_address)
            
            # Prepare log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_entry = {
                'timestamp': timestamp,
                'user_id': user_id,
                'username': username,
                'ip_address': ip_address,
                **location_data
            }
            
            # Temporarily make file writable to append
            try:
                os.chmod(self.csv_path, 0o644)  # Read-write
            except:
                pass
            
            # Append to CSV
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'user_id', 'username', 'ip_address',
                    'country', 'region', 'city', 'latitude', 'longitude',
                    'isp', 'timezone'
                ])
                writer.writerow(log_entry)
            
            # Make file read-only again
            try:
                os.chmod(self.csv_path, 0o444)  # Read-only
            except:
                pass
            
            logger.info(f"✓ Login logged: {username} from {location_data['city']}, {location_data['country']}")
            
            return log_entry
            
        except Exception as e:
            logger.error(f"❌ Error logging login: {str(e)}")
            logger.exception("Login logging error:")
            return {}
    
    def get_login_history(
        self, 
        user_id: Optional[str] = None, 
        limit: int = 100
    ) -> list:
        """
        Get login history from CSV.
        
        Args:
            user_id: Filter by specific user ID (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of login records
        """
        try:
            if not os.path.exists(self.csv_path):
                return []
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                records = list(reader)
            
            # Filter by user_id if provided
            if user_id:
                records = [r for r in records if r.get('user_id') == user_id]
            
            # Return most recent first
            records.reverse()
            
            return records[:limit]
            
        except Exception as e:
            logger.error(f"Error reading login history: {str(e)}")
            return []


# Singleton instance
_location_tracker = None

def get_location_tracker() -> LocationTracker:
    """Get location tracker singleton instance."""
    global _location_tracker
    if _location_tracker is None:
        _location_tracker = LocationTracker()
    return _location_tracker
