import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_session(payment):
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Library payment #{payment.id}",
                    },
                    "unit_amount": int(payment.money_to_pay * 100),
                },
                "quantity": 1,
            }
        ],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )

    payment.session_url = session.url
    payment.session_id = session.id
    payment.save(update_fields=["session_url", "session_id"])

    return session

def create_payment_session(payment):
    return create_stripe_session(payment)
