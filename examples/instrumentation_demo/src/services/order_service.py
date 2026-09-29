from typing import List

from src.domain import Order
from src.repositories.order_repository import OrderRepository

from mitsuki import Service
from mitsuki.core.instrumentation import InstrumentationProvider

# Label values must come from a small, fixed set: every distinct value creates
# a separate time series in Prometheus. Anything outside the set is reported
# as "other".
PRODUCT_TYPES = {"digital", "physical"}
REGIONS = {"us-east", "us-west", "eu-west", "ap-south"}


def _bounded(value: str, allowed: set) -> str:
    return value if value in allowed else "other"


@Service()
class OrderService:
    """
    Order business logic, recording custom metrics alongside the automatic
    component metrics:

    - orders_created_total: a business metric, by product type and region
    - database_writes_total: write operations, by table and operation
    - database_rows_returned_total: rows read, by table and query
    - database_full_scan_total: full table scans, by table
    - expensive_aggregation_total: resource-intensive aggregations
    """

    def __init__(
        self, order_repo: OrderRepository, instrumentation: InstrumentationProvider
    ):
        self.order_repo = order_repo
        self.instrumentation = instrumentation

    async def create_order(
        self, user_id: int, product_type: str, amount: float, region: str = "us-east"
    ) -> Order:
        order = Order(
            user_id=user_id, product_type=product_type, amount=amount, region=region
        )
        saved_order = await self.order_repo.save(order)

        self.instrumentation.record_metric(
            metric_name="orders_created_total",
            value=1,
            labels={
                "product_type": _bounded(product_type, PRODUCT_TYPES),
                "region": _bounded(region, REGIONS),
            },
        )
        self.instrumentation.record_metric(
            metric_name="database_writes_total",
            value=1,
            labels={"table": "orders", "operation": "insert"},
        )

        return saved_order

    async def get_user_orders(self, user_id: int) -> List[Order]:
        orders = await self.order_repo.find_by_user_id(user_id)

        self.instrumentation.record_metric(
            metric_name="database_rows_returned_total",
            value=len(orders),
            labels={"table": "orders", "query": "by_user_id"},
        )

        return orders

    async def get_all_orders(self) -> List[Order]:
        orders = await self.order_repo.find_all()

        self.instrumentation.record_metric(
            metric_name="database_full_scan_total",
            value=1,
            labels={"table": "orders"},
        )
        self.instrumentation.record_metric(
            metric_name="database_rows_returned_total",
            value=len(orders),
            labels={"table": "orders", "query": "find_all"},
        )

        return orders

    async def calculate_total_revenue(self) -> float:
        orders = await self.order_repo.find_all()
        total = sum(order.amount for order in orders)

        self.instrumentation.record_metric(
            metric_name="expensive_aggregation_total",
            value=1,
            labels={"operation": "revenue_calculation"},
        )

        return total
