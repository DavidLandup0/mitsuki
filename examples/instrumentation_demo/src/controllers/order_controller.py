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

    Every request is recorded in the HTTP metrics, labelled by method, route
    template and status. Each handler is also recorded as a component call.
    """

    def __init__(self, order_service: OrderService):
        self.order_service = order_service

    @PostMapping("")
    @Consumes(CreateOrderRequest)
    async def create_order(
        self, body: CreateOrderRequest = RequestBody()
    ) -> ResponseEntity:
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
        total = await self.order_service.calculate_total_revenue()
        return ResponseEntity.ok({"total_revenue": total, "currency": "USD"})
