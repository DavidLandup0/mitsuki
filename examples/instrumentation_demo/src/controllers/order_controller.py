from dataclasses import dataclass
from typing import Optional

from src.services.order_service import OrderService

from mitsuki.web import Consumes, GetMapping, PostMapping, RequestBody, RestController
from mitsuki.web.response import ResponseEntity


@dataclass
class CreateOrderRequest:
    user_id: int
    product_type: str
    amount: float
    region: Optional[str] = "us-east"


@RestController("/api/orders")
class OrderController:
    """
    REST API for order management.

    Automatically instrumented - demonstrates:
    - HTTP metrics collection
    - Per-endpoint performance tracking
    """

    def __init__(self, order_service: OrderService):
        self.order_service = order_service

    @PostMapping("")
    @Consumes(CreateOrderRequest)
    async def create_order(
        self, body: CreateOrderRequest = RequestBody()
    ) -> ResponseEntity:
        """
        Create a new order.

        This endpoint triggers custom metrics in OrderService:
        - orders_created counter with labels
        - revenue tracking with product type and region
        """
        order = await self.order_service.create_order(
            user_id=body.user_id,
            product_type=body.product_type,
            amount=body.amount,
            region=body.region,
        )

        return ResponseEntity.created(
            {
                "id": order.id,
                "user_id": order.user_id,
                "product_type": order.product_type,
                "amount": order.amount,
                "region": order.region,
            }
        )

    @GetMapping("")
    async def get_all_orders(self) -> ResponseEntity:
        """Get all orders. Tracked by instrumentation."""
        orders = await self.order_service.get_all_orders()
        return ResponseEntity.ok(
            [
                {
                    "id": o.id,
                    "user_id": o.user_id,
                    "product_type": o.product_type,
                    "amount": o.amount,
                    "region": o.region,
                }
                for o in orders
            ]
        )

    @GetMapping("/user/{user_id}")
    async def get_user_orders(self, user_id: int) -> ResponseEntity:
        """Get orders for a specific user."""
        orders = await self.order_service.get_user_orders(user_id)
        return ResponseEntity.ok(
            [
                {
                    "id": o.id,
                    "user_id": o.user_id,
                    "product_type": o.product_type,
                    "amount": o.amount,
                    "region": o.region,
                }
                for o in orders
            ]
        )

    @GetMapping("/revenue")
    async def get_total_revenue(self) -> ResponseEntity:
        """
        Calculate total revenue.

        Demonstrates:
        - Business logic instrumentation
        - Custom metric recording
        - Performance tracking of calculations
        """
        total = await self.order_service.calculate_total_revenue()
        return ResponseEntity.ok({"total_revenue": total, "currency": "USD"})
