"""Tests for User model and UserRepository."""

import pytest
import uuid
from datetime import datetime

from app.models import User, UserInDB
from app.repositories import UserRepository


class TestUserModel:
    """Test User and UserInDB model validation."""
    
    def test_user_model_creation(self):
        """Test creating a User model with valid data."""
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "user",
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": None
        }
        
        user = User(**user_data)
        
        assert user.id == user_data["id"]
        assert user.email == user_data["email"]
        assert user.full_name == user_data["full_name"]
        assert user.role == user_data["role"]
        assert user.is_active == user_data["is_active"]
    
    def test_user_in_db_model_creation(self):
        """Test creating a UserInDB model with valid data."""
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "user",
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": None,
            "hashed_password": "$2b$12$example_hashed_password"
        }
        
        user = UserInDB(**user_data)
        
        assert user.id == user_data["id"]
        assert user.email == user_data["email"]
        assert user.hashed_password == user_data["hashed_password"]
    
    def test_user_model_validation_invalid_email(self):
        """Test User model validation with invalid email."""
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "invalid-email",
            "full_name": "Test User",
            "role": "user",
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        
        with pytest.raises(ValueError):
            User(**user_data)
    
    def test_user_model_default_values(self):
        """Test User model default values."""
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "full_name": "Test User"
        }
        
        user = User(**user_data)
        
        assert user.role == "user"  # Default role
        assert user.is_active is True  # Default active status


class TestUserRepository:
    """Test UserRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, user_repository: UserRepository):
        """Test creating a new user."""
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        created_user = await user_repository.create(user_data)
        
        assert created_user.id == user_data.id
        assert created_user.email == user_data.email
        assert created_user.full_name == user_data.full_name
        assert created_user.hashed_password == user_data.hashed_password
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, user_repository: UserRepository):
        """Test retrieving a user by ID."""
        # Create a user first
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        created_user = await user_repository.create(user_data)
        
        # Retrieve the user
        retrieved_user = await user_repository.get_by_id(created_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == created_user.email
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_repository: UserRepository):
        """Test retrieving a non-existent user."""
        non_existent_id = str(uuid.uuid4())
        
        retrieved_user = await user_repository.get_by_id(non_existent_id)
        
        assert retrieved_user is None
    
    @pytest.mark.asyncio
    async def test_get_user_by_email(self, user_repository: UserRepository):
        """Test retrieving a user by email."""
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        created_user = await user_repository.create(user_data)
        
        # Retrieve by email
        retrieved_user = await user_repository.get_by_email(created_user.email)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == created_user.email
    
    @pytest.mark.asyncio
    async def test_update_user(self, user_repository: UserRepository):
        """Test updating a user."""
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        created_user = await user_repository.create(user_data)
        
        # Update the user
        updates = {
            "full_name": "Updated Test User",
            "role": "admin"
        }
        
        updated_user = await user_repository.update(created_user.id, updates)
        
        assert updated_user is not None
        assert updated_user.full_name == "Updated Test User"
        assert updated_user.role == "admin"
        assert updated_user.email == created_user.email  # Unchanged
    
    @pytest.mark.asyncio
    async def test_delete_user(self, user_repository: UserRepository):
        """Test deleting a user."""
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        created_user = await user_repository.create(user_data)
        
        # Delete the user
        deleted = await user_repository.delete(created_user.id)
        
        assert deleted is True
        
        # Verify user is deleted
        retrieved_user = await user_repository.get_by_id(created_user.id)
        assert retrieved_user is None
    
    @pytest.mark.asyncio
    async def test_list_users(self, user_repository: UserRepository):
        """Test listing users."""
        # Create multiple users
        users_data = []
        for i in range(3):
            user_data = UserInDB(
                id=str(uuid.uuid4()),
                email=f"test{i}@example.com",
                full_name=f"Test User {i}",
                role="user",
                is_active=True,
                created_at=datetime.now().isoformat(),
                hashed_password="$2b$12$example_hashed_password"
            )
            users_data.append(await user_repository.create(user_data))
        
        # List all users
        all_users = await user_repository.list()
        
        assert len(all_users) >= 3
        
        # Check that our created users are in the list
        created_ids = {user.id for user in users_data}
        retrieved_ids = {user.id for user in all_users}
        
        assert created_ids.issubset(retrieved_ids)
    
    @pytest.mark.asyncio
    async def test_list_users_with_filters(self, user_repository: UserRepository):
        """Test listing users with filters."""
        # Create users with different roles
        admin_user = UserInDB(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            full_name="Admin User",
            role="admin",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        regular_user = UserInDB(
            id=str(uuid.uuid4()),
            email="user@example.com",
            full_name="Regular User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        await user_repository.create(admin_user)
        await user_repository.create(regular_user)
        
        # Filter by role
        admin_users = await user_repository.list(filters={"role": "admin"})
        
        assert len(admin_users) >= 1
        assert all(user.role == "admin" for user in admin_users)
    
    @pytest.mark.asyncio
    async def test_email_exists(self, user_repository: UserRepository):
        """Test checking if email exists."""
        user_data = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="$2b$12$example_hashed_password"
        )
        
        await user_repository.create(user_data)
        
        # Check existing email
        exists = await user_repository.email_exists("test@example.com")
        assert exists is True
        
        # Check non-existing email
        not_exists = await user_repository.email_exists("nonexistent@example.com")
        assert not_exists is False
    
    @pytest.mark.asyncio
    async def test_get_user_stats(self, user_repository: UserRepository):
        """Test getting user statistics."""
        # Create some test users
        for i in range(2):
            user_data = UserInDB(
                id=str(uuid.uuid4()),
                email=f"test{i}@example.com",
                full_name=f"Test User {i}",
                role="user" if i == 0 else "admin",
                is_active=True,
                created_at=datetime.now().isoformat(),
                hashed_password="$2b$12$example_hashed_password"
            )
            await user_repository.create(user_data)
        
        stats = await user_repository.get_user_stats()
        
        assert "total_users" in stats
        assert "active_users" in stats
        assert "users_by_role" in stats
        assert stats["total_users"] >= 2
        assert stats["active_users"] >= 2
