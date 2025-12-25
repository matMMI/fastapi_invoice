"""
Database Seeder Script

Generates fake data for testing purposes using Faker.
Creates clients and quotes with various statuses (excluding SIGNED).

Usage:
    python seed_data.py --user-id <user_id> [--clients 30] [--quotes 200]

Requirements:
    pip install faker
"""

import argparse
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from faker import Faker
from sqlmodel import Session, select

from db.session import engine
from models.client import Client
from models.quote import Quote, QuoteItem
from models.enums import Currency, QuoteStatus, TaxStatus

# Initialize Faker with French locale
fake = Faker('fr_FR')

# Statuses to use (excluding SIGNED)
ALLOWED_STATUSES = [QuoteStatus.DRAFT, QuoteStatus.SENT, QuoteStatus.ACCEPTED, QuoteStatus.REJECTED]
CURRENCIES = [Currency.EUR]  # Only EUR supported

# Sample service descriptions for quotes
SERVICE_DESCRIPTIONS = [
    "Développement web - site vitrine",
    "Développement application mobile",
    "Maintenance mensuelle",
    "Hébergement annuel",
    "Création logo et charte graphique",
    "Refonte site e-commerce",
    "Intégration API",
    "Formation utilisateurs",
    "Audit SEO",
    "Rédaction contenu",
    "Community management",
    "Campagne Google Ads",
    "Développement fonctionnalité sur mesure",
    "Migration de données",
    "Support technique prioritaire",
    "Consulting stratégie digitale",
    "Design UX/UI",
    "Développement WordPress",
    "Configuration serveur",
    "Backup et sécurité",
]


def generate_quote_number(index: int) -> str:
    """Generate a unique quote number."""
    year = datetime.now().year
    return f"DEV-{year}-{str(index).zfill(4)}"


def create_clients(session: Session, user_id: str, count: int = 30) -> list[Client]:
    """Create fake clients."""
    print(f"Creating {count} clients...")
    clients = []
    
    for i in range(count):
        client = Client(
            id=str(uuid4()),
            user_id=user_id,
            name=fake.name(),
            email=fake.email(),
            company=fake.company() if random.random() > 0.3 else None,
            address=fake.address().replace('\n', ', '),
            phone=fake.phone_number() if random.random() > 0.2 else None,
            vat_number=f"FR{fake.random_number(digits=11, fix_len=True)}" if random.random() > 0.5 else None,
            created_at=fake.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        clients.append(client)
        session.add(client)
    
    session.commit()
    print(f"✓ Created {count} clients")
    return clients


def create_quotes(session: Session, user_id: str, clients: list[Client], count: int = 200) -> list[Quote]:
    """Create fake quotes with items."""
    print(f"Creating {count} quotes...")
    quotes = []
    
    # Get the max quote number to avoid conflicts
    existing_max = session.exec(
        select(Quote.quote_number).where(Quote.user_id == user_id).order_by(Quote.quote_number.desc())
    ).first()
    
    start_index = 1
    if existing_max:
        try:
            # Extract the number part from existing quote number
            parts = existing_max.split('-')
            if len(parts) == 3:
                start_index = int(parts[2]) + 1
        except (ValueError, IndexError):
            pass
    
    for i in range(count):
        client = random.choice(clients)
        status = random.choice(ALLOWED_STATUSES)
        currency = random.choice(CURRENCIES)
        
        # Create random items
        num_items = random.randint(1, 5)
        items = []
        subtotal = Decimal("0.00")
        
        for j in range(num_items):
            quantity = Decimal(str(random.randint(1, 10)))
            unit_price = Decimal(str(random.randint(50, 500) * 10))  # 500 to 5000
            item_total = quantity * unit_price
            subtotal += item_total
            
            items.append(QuoteItem(
                id=str(uuid4()),
                description=random.choice(SERVICE_DESCRIPTIONS),
                quantity=quantity,
                unit_price=unit_price,
                total=item_total,
                order=j,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
        
        # Calculate totals
        tax_rate = Decimal("20.00") if random.random() > 0.3 else Decimal("0.00")
        tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = subtotal + tax_amount
        
        # Random creation date in the past year
        created_at = fake.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.utc)
        
        # Set sent_at for non-draft quotes
        sent_at = None
        if status != QuoteStatus.DRAFT:
            sent_at = created_at + timedelta(hours=random.randint(1, 48))
        
        # Handle payment for accepted quotes
        is_paid = False
        payment_date = None
        if status == QuoteStatus.ACCEPTED and random.random() > 0.4:
            is_paid = True
            payment_date = sent_at + timedelta(days=random.randint(1, 30)) if sent_at else None
        
        quote = Quote(
            id=str(uuid4()),
            quote_number=generate_quote_number(start_index + i),
            user_id=user_id,
            client_id=client.id,
            currency=currency,
            status=status,
            tax_status=TaxStatus.FRANCHISE if tax_rate == Decimal("0.00") else TaxStatus.ASSUJETTI,
            is_paid=is_paid,
            payment_date=payment_date,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            notes=fake.text(max_nb_chars=200) if random.random() > 0.7 else None,
            payment_terms="Paiement à 30 jours" if random.random() > 0.5 else None,
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
            sent_at=sent_at,
            items=items,
        )
        
        quotes.append(quote)
        session.add(quote)
        
        # Commit in batches
        if (i + 1) % 50 == 0:
            session.commit()
            print(f"  Processed {i + 1}/{count} quotes...")
    
    session.commit()
    print(f"✓ Created {count} quotes")
    return quotes


def main():
    parser = argparse.ArgumentParser(description='Seed database with fake data')
    parser.add_argument('--user-id', required=True, help='User ID to associate data with')
    parser.add_argument('--clients', type=int, default=30, help='Number of clients to create (default: 30)')
    parser.add_argument('--quotes', type=int, default=200, help='Number of quotes to create (default: 200)')
    
    args = parser.parse_args()
    
    print(f"\n🌱 Starting database seeding...")
    print(f"   User ID: {args.user_id}")
    print(f"   Clients: {args.clients}")
    print(f"   Quotes: {args.quotes}\n")
    
    with Session(engine) as session:
        # Create clients first
        clients = create_clients(session, args.user_id, args.clients)
        
        # Then create quotes linked to those clients
        quotes = create_quotes(session, args.user_id, clients, args.quotes)
        
        # Summary
        status_counts = {}
        for q in quotes:
            status_counts[q.status.value] = status_counts.get(q.status.value, 0) + 1
        
        print(f"\n📊 Summary:")
        print(f"   Total clients: {len(clients)}")
        print(f"   Total quotes: {len(quotes)}")
        print(f"   Status breakdown:")
        for status, count in status_counts.items():
            print(f"     - {status}: {count}")
    
    print(f"\n✅ Seeding complete!\n")


if __name__ == "__main__":
    main()
