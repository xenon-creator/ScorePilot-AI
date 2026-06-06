import razorpay
import os
import uuid
from app.models.database import Subscription, PlanType, SubscriptionStatus
from app.core.plans import PLANS, PLAN_LIMITS

# Initialize Razorpay Client gracefully
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def get_or_create_subscription(user_id: str, db) -> Subscription:
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if not sub:
        sub = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan=PlanType.free,
            status=SubscriptionStatus.trial,
            papers_used=0,
            papers_limit=5
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub

def check_usage_limit(user_id: str, db) -> dict:
    sub = get_or_create_subscription(user_id, db)
    return {
        "plan": sub.plan,
        "papers_used": sub.papers_used,
        "papers_limit": sub.papers_limit,
        "can_grade": sub.papers_used < sub.papers_limit,
        "upgrade_required": sub.papers_used >= sub.papers_limit
    }

def increment_usage(user_id: str, db):
    sub = get_or_create_subscription(user_id, db)
    sub.papers_used += 1
    db.commit()

def create_razorpay_subscription(user_id: str, plan: str,
                                  user_email: str, user_name: str,
                                  db) -> dict:
    if not client:
        raise ValueError("Payments not configured")

    plan_config = PLANS.get(plan)
    if not plan_config:
        raise ValueError(f"Invalid plan name: {plan}")

    if not plan_config.get("razorpay_plan_id"):
        return {
            "error": "plan_not_configured",
            "message": f"Upgrade to {plan} is coming soon. Email support@scorepilot.ai",
        }

    # Generate customer
    try:
        customer = client.customer.create({
            "name": user_name,
            "email": user_email
        })
    except Exception as e:
        # Customer already exists — fetch by email instead
        customers = client.customer.all({"email": user_email})
        if customers and customers.get("items"):
            customer = customers["items"][0]
        else:
            raise e

    # Generate subscription
    subscription = client.subscription.create({
        "plan_id": plan_config["razorpay_plan_id"],
        "customer_notify": 1,
        "total_count": 12,
        "notes": {"user_id": user_id}
    })

    sub = get_or_create_subscription(user_id, db)
    if not sub.razorpay_customer_id:
        sub.razorpay_customer_id = customer["id"]
    sub.razorpay_sub_id = subscription["id"]
    sub.plan = PlanType(plan)
    db.commit()

    return {
        "subscription_id": subscription["id"],
        "razorpay_key": RAZORPAY_KEY_ID,
        "plan": plan,
        "amount": plan_config["price_inr"] * 100
    }

def activate_subscription(razorpay_sub_id: str,
                           payment_id: str, db):
    sub = db.query(Subscription).filter_by(
        razorpay_sub_id=razorpay_sub_id
    ).first()
    if sub:
        plan_name = sub.plan.value
        sub.status = SubscriptionStatus.active
        sub.papers_limit = PLAN_LIMITS.get(plan_name, 5)
        db.commit()

def cancel_subscription(user_id: str, db):
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if sub:
        if client and sub.razorpay_sub_id:
            try:
                client.subscription.cancel(sub.razorpay_sub_id)
            except Exception:
                pass
        sub.status = SubscriptionStatus.cancelled
        sub.plan = PlanType.free
        sub.papers_limit = 5
        db.commit()
