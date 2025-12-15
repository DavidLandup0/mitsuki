from typing import List

from src.domain import Order
from src.repositories.order_repository import OrderRepository

from mitsuki import Service
from mitsuki.core.instrumentation import InstrumentationProvider


@Service()
class OrderService:
    """
    Order service demonstrating practical instrumentation.

    Shows how to track real operational metrics:
    - Database query performance
    - Cache effectiveness
    - Error rates for specific operations
    - Resource-intensive operations
    """

    def __init__(
        self, order_repo: OrderRepository, instrumentation: InstrumentationProvider
    ):
        self.order_repo = order_repo
        self.instrumentation = instrumentation

    async def create_order(
        self, user_id: int, product_type: str, amount: float, region: str = "us-east"
    ) -> Order:
        """
        Create a new order.

        Custom metrics tracked:
        - Database write operations (for monitoring DB load)
        - Validation failures (track data quality issues)
        """
        order = Order(
            user_id=user_id, product_type=product_type, amount=amount, region=region
        )
        saved_order = await self.order_repo.save(order)

        # Track database write operation
        self.instrumentation.record_metric(
            metric_name="database_writes_total",
            value=1,
            labels={"table": "orders", "operation": "insert"},
        )

        return saved_order

    async def get_user_orders(self, user_id: int) -> List[Order]:
        """
        Get all orders for a user.

        Tracks:
        - Number of records returned (detect inefficient queries)
        - Cache misses (if caching is added later)
        """
        orders = await self.order_repo.find_by_user_id(user_id)

        # Track query result size to detect N+1 queries or inefficient fetches
        self.instrumentation.record_metric(
            metric_name="database_query_rows_returned",
            value=len(orders),
            labels={"table": "orders", "query_type": "by_user_id"},
        )

        return orders

    async def get_all_orders(self) -> List[Order]:
        """
        Get all orders.

        Tracks:
        - Full table scan operations (expensive!)
        - Result set size (detect when pagination is needed)
        """
        orders = await self.order_repo.find_all()

        # Track expensive full table scans
        self.instrumentation.record_metric(
            metric_name="database_full_scan_total",
            value=1,
            labels={"table": "orders"},
        )

        # Track result size to know when to add pagination
        self.instrumentation.record_metric(
            metric_name="database_query_rows_returned",
            value=len(orders),
            labels={"table": "orders", "query_type": "find_all"},
        )

        return orders

    async def calculate_total_revenue(self) -> float:
        """
        Calculate total revenue from all orders.

        This is a resource-intensive operation - track it!
        """
        orders = await self.order_repo.find_all()
        total = sum(order.amount for order in orders)

        # Track expensive aggregation operations
        self.instrumentation.record_metric(
            metric_name="expensive_aggregation_total",
            value=1,
            labels={
                "operation": "revenue_calculation",
                "records_processed": str(len(orders)),
            },
        )

        return total
