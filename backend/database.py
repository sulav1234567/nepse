"""
MongoDB Database Connection and User Management
"""

import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import Optional, Dict, Any
from datetime import datetime
from bson.objectid import ObjectId

logger = logging.getLogger("nepse-alpha")

# MongoDB connection settings
MONGODB_URL = "mongodb://localhost:27017"
DATABASE_NAME = "nepse_alpha"
USERS_COLLECTION = "users"

# Global client and database
client: Optional[MongoClient] = None
db = None


def connect_to_mongodb():
    """
    Connect to MongoDB
    """
    global client, db
    try:
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=10000)
        # Verify connection
        client.admin.command('ping')
        db = client[DATABASE_NAME]
        logger.info("✓ MongoDB connected successfully")
        
        # Create indexes for users collection
        users_collection = db[USERS_COLLECTION]
        users_collection.create_index("email", unique=True)
        users_collection.create_index("username", unique=True)
        logger.info("✓ MongoDB indexes created")
        
        return db
    except ConnectionFailure as e:
        logger.error(f"✗ Failed to connect to MongoDB: {e}")
        raise


def close_mongodb():
    """
    Close MongoDB connection
    """
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_database():
    """
    Get MongoDB database instance
    """
    if db is None:
        raise RuntimeError("Database not connected. Call connect_to_mongodb() first.")
    return db


class UserManager:
    """
    User management operations
    """
    
    @staticmethod
    def get_collection():
        """Get users collection"""
        return get_database()[USERS_COLLECTION]
    
    @staticmethod
    def create_user(email: str, username: str, hashed_password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new user
        
        Args:
            email: User email
            username: Username
            hashed_password: Hashed password
            full_name: Full name (optional)
        
        Returns:
            Created user document
        """
        collection = UserManager.get_collection()
        
        # Check if user already exists
        if collection.find_one({"email": email}):
            raise ValueError("Email already registered")
        if collection.find_one({"username": username}):
            raise ValueError("Username already taken")
        
        user_doc = {
            "email": email,
            "username": username,
            "password": hashed_password,
            "full_name": full_name,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "portfolio": [],
            "watchlist": [],
        }
        
        result = collection.insert_one(user_doc)
        user_doc["_id"] = str(result.inserted_id)
        logger.info(f"✓ User created: {email}")
        return user_doc
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email
        
        Args:
            email: User email
        
        Returns:
            User document or None
        """
        collection = UserManager.get_collection()
        user = collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID
        
        Args:
            user_id: User object ID
        
        Returns:
            User document or None
        """
        collection = UserManager.get_collection()
        try:
            user = collection.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except:
            return None
    
    @staticmethod
    def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update user data
        
        Args:
            user_id: User object ID
            update_data: Data to update
        
        Returns:
            Updated user document or None
        """
        collection = UserManager.get_collection()
        try:
            result = collection.find_one_and_update(
                {"_id": ObjectId(user_id)},
                {"$set": update_data},
                return_document=True
            )
            if result:
                result["_id"] = str(result["_id"])
            return result
        except:
            return None
    
    @staticmethod
    def add_to_watchlist(user_id: str, symbol: str) -> bool:
        """
        Add stock to user's watchlist
        
        Args:
            user_id: User object ID
            symbol: Stock symbol
        
        Returns:
            Success status
        """
        collection = UserManager.get_collection()
        try:
            collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$addToSet": {"watchlist": symbol}}
            )
            return True
        except:
            return False
    
    @staticmethod
    def remove_from_watchlist(user_id: str, symbol: str) -> bool:
        """
        Remove stock from user's watchlist
        
        Args:
            user_id: User object ID
            symbol: Stock symbol
        
        Returns:
            Success status
        """
        collection = UserManager.get_collection()
        try:
            collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$pull": {"watchlist": symbol}}
            )
            return True
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id: str) -> list:
        """
        Get user's watchlist
        
        Args:
            user_id: User object ID
        
        Returns:
            List of stock symbols
        """
        collection = UserManager.get_collection()
        try:
            user = collection.find_one({"_id": ObjectId(user_id)})
            return user.get("watchlist", []) if user else []
        except:
            return []
