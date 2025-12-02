from __future__ import annotations

from typing import Optional, Union

from redis import Redis
from redis.cluster import RedisCluster

from app.core.config import settings

_redis: Optional[Union[Redis, RedisCluster]] = None


def get_redis() -> Union[Redis, RedisCluster]:
    global _redis
    if _redis is None:
        if not settings.REDIS_NODES:
            raise RuntimeError("REDIS_NODES not configured")
        
        # Parse REDIS_NODES (comma separated host:port pairs)
        nodes = []
        for n in settings.REDIS_NODES.split(","):
            host, port = n.split(":")
            nodes.append({"host": host.strip(), "port": int(port.strip())})
        
        # If only one node, use single Redis connection; otherwise use cluster
        if len(nodes) == 1:
            node = nodes[0]
            _redis = Redis(
                host=node["host"],
                port=node["port"],
                password=settings.REDIS_PASSWORD,
                decode_responses=False
            )
        else:
            _redis = RedisCluster(startup_nodes=nodes, password=settings.REDIS_PASSWORD)
    
    return _redis
