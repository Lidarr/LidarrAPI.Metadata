"""
Database connection pool monitoring and metrics for debugging performance issues.
"""
import time
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from lidarrmetadata.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ConnectionMetrics:
    """Metrics for database connection usage"""
    pool_size: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connection_acquisitions: int = 0
    connection_acquisition_time: float = 0.0
    failed_acquisitions: int = 0
    slow_queries: List[Dict] = None
    
    def __post_init__(self):
        if self.slow_queries is None:
            self.slow_queries = []

class DatabaseMonitor:
    """Monitor database connection pool and query performance"""
    
    def __init__(self):
        self.connection_metrics = ConnectionMetrics()
        self.query_history = []
        self.max_query_history = 50
        self.slow_query_threshold = 5.0  # seconds
    
    def record_connection_acquisition(self, acquisition_time: float, success: bool = True):
        """Record connection acquisition metrics"""
        self.connection_metrics.connection_acquisitions += 1
        self.connection_metrics.connection_acquisition_time += acquisition_time
        
        if not success:
            self.connection_metrics.failed_acquisitions += 1
        
        # Log slow connection acquisitions
        if acquisition_time > 2.0:
            logger.warning("Slow connection acquisition", extra={
                'acquisition_time': round(acquisition_time, 4),
                'threshold': 2.0,
                'total_acquisitions': self.connection_metrics.connection_acquisitions,
                'failed_acquisitions': self.connection_metrics.failed_acquisitions
            })
    
    def record_query(self, sql: str, execution_time: float, result_count: int, success: bool = True):
        """Record query execution metrics"""
        query_data = {
            'sql_preview': sql[:100] + '...' if len(sql) > 100 else sql,
            'execution_time': execution_time,
            'result_count': result_count,
            'success': success,
            'timestamp': time.time()
        }
        
        # Add to query history
        self.query_history.append(query_data)
        if len(self.query_history) > self.max_query_history:
            self.query_history.pop(0)
        
        # Track slow queries
        if execution_time > self.slow_query_threshold:
            self.connection_metrics.slow_queries.append(query_data)
            if len(self.connection_metrics.slow_queries) > 20:
                self.connection_metrics.slow_queries.pop(0)
            
            logger.warning("Slow query detected", extra={
                'execution_time': round(execution_time, 4),
                'threshold': self.slow_query_threshold,
                'sql_preview': query_data['sql_preview'],
                'result_count': result_count
            })
    
    def update_pool_status(self, pool):
        """Update connection pool status from asyncpg pool"""
        if pool:
            try:
                self.connection_metrics.pool_size = pool.get_size()
                self.connection_metrics.active_connections = pool.get_size() - pool.get_idle_size()
                self.connection_metrics.idle_connections = pool.get_idle_size()
            except Exception as e:
                logger.debug(f"Error getting pool status: {e}")
    
    def get_metrics(self) -> Dict:
        """Get current database metrics"""
        avg_acquisition_time = 0.0
        if self.connection_metrics.connection_acquisitions > 0:
            avg_acquisition_time = (
                self.connection_metrics.connection_acquisition_time / 
                self.connection_metrics.connection_acquisitions
            )
        
        # Calculate recent query stats
        recent_queries = [q for q in self.query_history if time.time() - q['timestamp'] < 300]  # Last 5 minutes
        avg_query_time = 0.0
        if recent_queries:
            avg_query_time = sum(q['execution_time'] for q in recent_queries) / len(recent_queries)
        
        return {
            'connection_pool': {
                'pool_size': self.connection_metrics.pool_size,
                'active_connections': self.connection_metrics.active_connections,
                'idle_connections': self.connection_metrics.idle_connections,
                'utilization_percent': (
                    (self.connection_metrics.active_connections / self.connection_metrics.pool_size * 100)
                    if self.connection_metrics.pool_size > 0 else 0
                )
            },
            'connection_acquisition': {
                'total_acquisitions': self.connection_metrics.connection_acquisitions,
                'failed_acquisitions': self.connection_metrics.failed_acquisitions,
                'avg_acquisition_time': round(avg_acquisition_time, 4),
                'failure_rate_percent': (
                    (self.connection_metrics.failed_acquisitions / self.connection_metrics.connection_acquisitions * 100)
                    if self.connection_metrics.connection_acquisitions > 0 else 0
                )
            },
            'query_performance': {
                'recent_queries_count': len(recent_queries),
                'avg_query_time': round(avg_query_time, 4),
                'slow_queries_count': len(self.connection_metrics.slow_queries),
                'slow_query_threshold': self.slow_query_threshold
            },
            'slow_queries': self.connection_metrics.slow_queries[-5:],  # Last 5 slow queries
            'recent_queries': recent_queries[-10:]  # Last 10 recent queries
        }
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        self.connection_metrics = ConnectionMetrics()
        self.query_history = []

# Global database monitor instance
db_monitor = DatabaseMonitor()