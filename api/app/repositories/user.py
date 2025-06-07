"""User repository implementation."""

import logging
from typing import Optional, Dict, Any
from ..models import User, UserInDB
from .base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repository for User entities with DuckDB storage and JetStream sync."""
    
    def __init__(self):
        super().__init__(
            model_class=UserInDB,
            table_name="users",
            jetstream_bucket="users"
        )
    
    async def _insert_to_db(self, entity: UserInDB):
        """Insert user entity to database."""
        query = """
            INSERT INTO users (
                id, email, full_name, role, is_active, 
                created_at, updated_at, hashed_password
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = [
            entity.id,
            entity.email,
            entity.full_name,
            entity.role,
            entity.is_active,
            entity.created_at,
            entity.updated_at,
            entity.hashed_password
        ]
        
        self.db_connection.execute(query, values)
        logger.debug(f"Inserted user {entity.id} into database")
    
    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email address."""
        try:
            query = "SELECT * FROM users WHERE email = ?"
            result = self.db_connection.execute(query, [email]).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.db_connection.description]
                data = dict(zip(columns, result))
                return UserInDB(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            raise
    
    async def get_public_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID without sensitive information."""
        user_in_db = await self.get_by_id(user_id)
        if user_in_db:
            # Convert to public User model (without hashed_password)
            return User(
                id=user_in_db.id,
                email=user_in_db.email,
                full_name=user_in_db.full_name,
                role=user_in_db.role,
                is_active=user_in_db.is_active,
                created_at=user_in_db.created_at,
                updated_at=user_in_db.updated_at
            )
        return None
    
    async def list_public_users(self, filters: Optional[Dict[str, Any]] = None, 
                               limit: Optional[int] = None, 
                               offset: Optional[int] = None) -> list[User]:
        """List users without sensitive information."""
        users_in_db = await self.list(filters, limit, offset)
        
        # Convert to public User models
        public_users = []
        for user_in_db in users_in_db:
            public_user = User(
                id=user_in_db.id,
                email=user_in_db.email,
                full_name=user_in_db.full_name,
                role=user_in_db.role,
                is_active=user_in_db.is_active,
                created_at=user_in_db.created_at,
                updated_at=user_in_db.updated_at
            )
            public_users.append(public_user)
        
        return public_users
    
    async def update_password(self, user_id: str, hashed_password: str) -> Optional[UserInDB]:
        """Update user password."""
        return await self.update(user_id, {"hashed_password": hashed_password})
    
    async def activate_user(self, user_id: str) -> Optional[UserInDB]:
        """Activate a user account."""
        return await self.update(user_id, {"is_active": True})
    
    async def deactivate_user(self, user_id: str) -> Optional[UserInDB]:
        """Deactivate a user account."""
        return await self.update(user_id, {"is_active": False})
    
    async def get_users_by_role(self, role: str) -> list[User]:
        """Get all users with a specific role."""
        return await self.list_public_users(filters={"role": role})
    
    async def get_active_users(self) -> list[User]:
        """Get all active users."""
        return await self.list_public_users(filters={"is_active": True})
    
    async def search_users(self, search_term: str, limit: Optional[int] = None) -> list[User]:
        """Search users by email or full name."""
        try:
            query = """
                SELECT * FROM users 
                WHERE email ILIKE ? OR full_name ILIKE ?
                ORDER BY created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            search_pattern = f"%{search_term}%"
            results = self.db_connection.execute(query, [search_pattern, search_pattern]).fetchall()
            
            # Convert results to public User models
            users = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    user_in_db = UserInDB(**data)
                    public_user = User(
                        id=user_in_db.id,
                        email=user_in_db.email,
                        full_name=user_in_db.full_name,
                        role=user_in_db.role,
                        is_active=user_in_db.is_active,
                        created_at=user_in_db.created_at,
                        updated_at=user_in_db.updated_at
                    )
                    users.append(public_user)
            
            return users
            
        except Exception as e:
            logger.error(f"Error searching users with term '{search_term}': {e}")
            raise
    
    async def email_exists(self, email: str, exclude_user_id: Optional[str] = None) -> bool:
        """Check if an email address is already in use."""
        try:
            query = "SELECT COUNT(*) FROM users WHERE email = ?"
            values = [email]
            
            if exclude_user_id:
                query += " AND id != ?"
                values.append(exclude_user_id)
            
            result = self.db_connection.execute(query, values).fetchone()
            return result[0] > 0
            
        except Exception as e:
            logger.error(f"Error checking email existence for {email}: {e}")
            raise
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics."""
        try:
            stats = {}
            
            # Total users
            total_result = self.db_connection.execute("SELECT COUNT(*) FROM users").fetchone()
            stats["total_users"] = total_result[0]
            
            # Active users
            active_result = self.db_connection.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = true"
            ).fetchone()
            stats["active_users"] = active_result[0]
            
            # Users by role
            role_results = self.db_connection.execute("""
                SELECT role, COUNT(*) as count 
                FROM users 
                GROUP BY role 
                ORDER BY count DESC
            """).fetchall()
            
            stats["users_by_role"] = {}
            for role, count in role_results:
                stats["users_by_role"][role] = count
            
            # Recent registrations (last 30 days)
            recent_result = self.db_connection.execute("""
                SELECT COUNT(*) FROM users 
                WHERE created_at >= datetime('now', '-30 days')
            """).fetchone()
            stats["recent_registrations"] = recent_result[0]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise
