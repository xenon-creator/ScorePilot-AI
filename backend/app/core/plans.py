import os

PLANS = {
    "free": {
        "name": "Free",
        "price_inr": 0,
        "papers_limit": 5,
        "features": [
            "5 papers per month",
            "AI scoring (MCQ + Short answer)",
            "Basic analytics",
            "Email support"
        ],
        "razorpay_plan_id": None
    },
    "starter": {
        "name": "Starter",
        "price_inr": 999,
        "papers_limit": 200,
        "features": [
            "200 papers per month",
            "AI scoring (all types)",
            "Full analytics dashboard",
            "Export CSV + PDF",
            "Priority support",
            "Multi-language OCR"
        ],
        "razorpay_plan_id": os.getenv("RAZORPAY_STARTER_PLAN_ID", "")
    },
    "pro": {
        "name": "Pro",
        "price_inr": 2499,
        "papers_limit": 999999,
        "features": [
            "Unlimited papers",
            "Everything in Starter",
            "Bulk upload (50 papers at once)",
            "Student performance tracking",
            "Custom branding",
            "Dedicated support",
            "API access"
        ],
        "razorpay_plan_id": os.getenv("RAZORPAY_PRO_PLAN_ID", "")
    }
}

PLAN_LIMITS = {
    "free": 5,
    "starter": 200,
    "pro": 999999
}
