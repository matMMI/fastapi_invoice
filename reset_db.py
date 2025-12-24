from sqlmodel import SQLModel, Session
from db.session import engine, get_session
from models.user import User
from models.quote import Quote, QuoteItem
from models.client import Client
from models.settings import Settings
from models.auth import Session as AuthSession, Account
from models.enums import TaxStatus, QuoteStatus

import bcrypt
from core.config import settings

def reset_db():
    print("🗑️  Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    
    print("✨ Creating all tables...")
    SQLModel.metadata.create_all(engine)
    
    # Hash password using bcrypt directly (passlib incompatibility with bcrypt 5.0+)
    hashed_password = bcrypt.hashpw(
        settings.admin_password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

    print(f"🌱 Seeding Admin User: {settings.admin_email}...")
    with Session(engine) as session:
        # Create Admin user from Env
        user = User(
            email=settings.admin_email,
            username=settings.admin_username,
            name=settings.admin_name,
            password_hash=hashed_password,
            business_name="Antigravity SAS",
            siret="123 456 789 00012",
            address="10 Rue de la Paix, 75000 Paris",
            tax_status=TaxStatus.ASSUJETTI
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create Account record for Better Auth credential-based login
        account = Account(
            user_id=user.id,
            account_id=user.id,
            provider_id="credential",
            password_hash=hashed_password
        )
        session.add(account)
        
        # Create Settings
        user_settings = Settings(
            user_id=user.id,
            company_name="Antigravity SAS",
            vat_exemption_text="TVA non applicable"
        )
        session.add(user_settings)
        
        # Create Client
        client = Client(
            user_id=user.id,
            name="Client Test",
            email="client@test.com",
            address="20 Avenue de Lyon"
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        
        print(f"✅ Database reset complete. User ID: {user.id}")

if __name__ == "__main__":
    reset_db()
