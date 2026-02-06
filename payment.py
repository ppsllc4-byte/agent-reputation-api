import stripe
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from fastapi import HTTPException

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PRICE_PER_LOOKUP = float(os.getenv("PRICE_PER_LOOKUP", "0.005"))

class PaymentProcessor:
    @staticmethod
    async def create_checkout_session(success_url: str, cancel_url: str, quantity: int = 1) -> Dict[str, Any]:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Agent Reputation Lookups',
                            'description': 'Credits for agent reputation API lookups',
                        },
                        'unit_amount': int(PRICE_PER_LOOKUP * 100),
                    },
                    'quantity': quantity,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return {
                'session_id': session.id,
                'url': session.url,
                'amount_total': session.amount_total / 100 if session.amount_total else 0
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Checkout error: {str(e)}")

async def verify_payment_token(authorization: Optional[str]) -> bool:
    if not authorization:
        return False
    if authorization.startswith("Bearer "):
        return True
    return False
