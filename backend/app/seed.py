"""
Seed script: inserts demo users if they don't already exist.
Run with: python -m app.seed  (from the backend/ directory)
"""
from app.models.database import SessionLocal, User, UserRole
from app.core.security import hash_password


DEMO_USERS = [
    {
        "email": "admin@aegis.edu",
        "name": "admin",
        "role": UserRole.admin,
        "password": "admin123",
    },
    {
        "email": "teacher@aegis.edu",
        "name": "prof_sarah",
        "role": UserRole.teacher,
        "password": "teacher123",
    },
    {
        "email": "reviewer@aegis.edu",
        "name": "reviewer_john",
        "role": UserRole.reviewer,
        "password": "reviewer123",
    },
]


def seed():
    db = SessionLocal()
    try:
        for u in DEMO_USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"  [skip] {u['email']} already exists")
                continue
            user = User(
                email=u["email"],
                name=u["name"],
                role=u["role"],
                password=hash_password(u["password"]),
            )
            db.add(user)
            print(f"  [+] created {u['email']} ({u['role'].value})")
        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding demo users...")
    seed()
