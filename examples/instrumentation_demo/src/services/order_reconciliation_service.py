from src.repositories.order_repository import OrderRepository

from mitsuki import Scheduled, Service


@Service()
class OrderReconciliationService:
    """
    Periodically checks stored orders for invalid amounts.

    As a @Scheduled task, every run is recorded in the scheduler metrics:
    executions, failures and duration. Creating an order with a non-positive
    amount makes every following run fail, which shows up on the dashboard's
    task failure panel.
    """

    def __init__(self, order_repo: OrderRepository):
        self.order_repo = order_repo

    @Scheduled(fixed_rate=10000)
    async def reconcile_orders(self):
        orders = await self.order_repo.find_all()
        invalid = [order.id for order in orders if order.amount <= 0]
        if invalid:
            raise ValueError(f"Orders with non-positive amounts: {invalid}")
