"""Repository service for dependency injection and repository management."""

import logging
from typing import Optional, Any
from fastapi import Depends, Request

from ..repositories import (
    UserRepository, 
    WalletRepository, 
    AlertRepository, 
    WalletBalanceRepository
)
from ..dependencies import get_jetstream_context

logger = logging.getLogger(__name__)


class RepositoryService:
    """Service class for managing repository instances with JetStream injection."""
    
    def __init__(self, jetstream_context: Any):
        self.js = jetstream_context
        self._user_repo = None
        self._wallet_repo = None
        self._alert_repo = None
        self._wallet_balance_repo = None
    
    @property
    def user_repo(self) -> UserRepository:
        """Get User repository with JetStream context."""
        if self._user_repo is None:
            self._user_repo = UserRepository()
            self._user_repo.set_jetstream(self.js)
        return self._user_repo
    
    @property
    def wallet_repo(self) -> WalletRepository:
        """Get Wallet repository with JetStream context."""
        if self._wallet_repo is None:
            self._wallet_repo = WalletRepository()
            self._wallet_repo.set_jetstream(self.js)
        return self._wallet_repo
    
    @property
    def alert_repo(self) -> AlertRepository:
        """Get Alert repository with JetStream context."""
        if self._alert_repo is None:
            self._alert_repo = AlertRepository()
            self._alert_repo.set_jetstream(self.js)
        return self._alert_repo
    
    @property
    def wallet_balance_repo(self) -> WalletBalanceRepository:
        """Get WalletBalance repository with JetStream context."""
        if self._wallet_balance_repo is None:
            self._wallet_balance_repo = WalletBalanceRepository()
            self._wallet_balance_repo.set_jetstream(self.js)
        return self._wallet_balance_repo


# Dependency functions for FastAPI
async def get_repository_service(js: Any = Depends(get_jetstream_context)) -> RepositoryService:
    """FastAPI dependency to get repository service."""
    return RepositoryService(js)


async def get_user_repository(repo_service: RepositoryService = Depends(get_repository_service)) -> UserRepository:
    """FastAPI dependency to get User repository."""
    return repo_service.user_repo


async def get_wallet_repository(repo_service: RepositoryService = Depends(get_repository_service)) -> WalletRepository:
    """FastAPI dependency to get Wallet repository."""
    return repo_service.wallet_repo


async def get_alert_repository(repo_service: RepositoryService = Depends(get_repository_service)) -> AlertRepository:
    """FastAPI dependency to get Alert repository."""
    return repo_service.alert_repo


async def get_wallet_balance_repository(repo_service: RepositoryService = Depends(get_repository_service)) -> WalletBalanceRepository:
    """FastAPI dependency to get WalletBalance repository."""
    return repo_service.wallet_balance_repo
