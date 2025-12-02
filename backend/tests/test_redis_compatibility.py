"""Test Redis compatibility with single node and cluster modes."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.redis import get_redis


def test_single_node_redis():
    """Test that single Redis node is properly configured."""
    with patch("app.core.redis.settings") as mock_settings:
        with patch("app.core.redis._redis", None):
            mock_settings.REDIS_NODES = "127.0.0.1:6379"
            mock_settings.REDIS_PASSWORD = None
            
            # Reset the global _redis variable
            import app.core.redis
            app.core.redis._redis = None
            
            with patch("app.core.redis.Redis") as mock_redis_class:
                mock_redis_instance = MagicMock()
                mock_redis_class.return_value = mock_redis_instance
                
                result = get_redis()
                
                # Verify Redis was called with correct parameters
                mock_redis_class.assert_called_once_with(
                    host="127.0.0.1",
                    port=6379,
                    password=None,
                    decode_responses=False
                )
                assert result == mock_redis_instance


def test_redis_cluster():
    """Test that Redis cluster with multiple nodes is properly configured."""
    with patch("app.core.redis.settings") as mock_settings:
        with patch("app.core.redis._redis", None):
            mock_settings.REDIS_NODES = "127.0.0.1:7000,127.0.0.1:7001,127.0.0.1:7002"
            mock_settings.REDIS_PASSWORD = None
            
            # Reset the global _redis variable
            import app.core.redis
            app.core.redis._redis = None
            
            with patch("app.core.redis.RedisCluster") as mock_cluster_class:
                mock_cluster_instance = MagicMock()
                mock_cluster_class.return_value = mock_cluster_instance
                
                result = get_redis()
                
                # Verify RedisCluster was called with correct parameters
                expected_nodes = [
                    {"host": "127.0.0.1", "port": 7000},
                    {"host": "127.0.0.1", "port": 7001},
                    {"host": "127.0.0.1", "port": 7002},
                ]
                mock_cluster_class.assert_called_once_with(
                    startup_nodes=expected_nodes,
                    password=None
                )
                assert result == mock_cluster_instance


def test_redis_with_password():
    """Test that Redis password is properly passed."""
    with patch("app.core.redis.settings") as mock_settings:
        with patch("app.core.redis._redis", None):
            mock_settings.REDIS_NODES = "127.0.0.1:6379"
            mock_settings.REDIS_PASSWORD = "mypassword"
            
            # Reset the global _redis variable
            import app.core.redis
            app.core.redis._redis = None
            
            with patch("app.core.redis.Redis") as mock_redis_class:
                mock_redis_instance = MagicMock()
                mock_redis_class.return_value = mock_redis_instance
                
                result = get_redis()
                
                # Verify Redis was called with password
                mock_redis_class.assert_called_once_with(
                    host="127.0.0.1",
                    port=6379,
                    password="mypassword",
                    decode_responses=False
                )


def test_redis_not_configured():
    """Test that error is raised when REDIS_NODES is not configured."""
    with patch("app.core.redis.settings") as mock_settings:
        with patch("app.core.redis._redis", None):
            mock_settings.REDIS_NODES = None
            
            # Reset the global _redis variable
            import app.core.redis
            app.core.redis._redis = None
            
            with pytest.raises(RuntimeError, match="REDIS_NODES not configured"):
                get_redis()
