from sqlmodel import Session, select
from db.session import engine
from models.user import User

def check_users():
    with Session(engine) as session:
        statement = select(User)
        users = session.exec(statement).all()
        print(f"Found {len(users)} users in DB:")
        for u in users:
            print(f" - Username: '{u.username}' | Email: '{u.email}' | Hash Start: {u.password_hash[:10]}...")

if __name__ == "__main__":
    check_users()
