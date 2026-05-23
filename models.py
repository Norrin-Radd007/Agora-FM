"""
AGORA FM — SQLAlchemy Models
models.py

Defines the ServiceProvider table.
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, Numeric, Text
)
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()


class ServiceProvider(Base):
    __tablename__ = "service_providers"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    company_name          = Column(String(200), nullable=False)
    address               = Column(String(400), nullable=False)
    website               = Column(String(200), nullable=False)
    email                 = Column(String(200), nullable=False)
    telephone             = Column(String(30),  nullable=False)
    main_category         = Column(String(100), nullable=False)
    subcategory           = Column(String(100), nullable=False)
    service_description   = Column(Text,        nullable=False)
    pricing_amount        = Column(Numeric(10, 2), nullable=False)
    pricing_currency      = Column(String(3),   nullable=False, default="GBP")
    pricing_billing_period= Column(String(20),  nullable=False)   # per_month | per_year
    terms_url             = Column(String(200), nullable=False)

    def __repr__(self):
        return (
            f"<ServiceProvider id={self.id} "
            f"company='{self.company_name}' "
            f"category='{self.main_category}' "
            f"subcategory='{self.subcategory}'>"
        )


def get_engine(db_url: str = "sqlite:///agora_providers.db"):
    return create_engine(db_url, echo=False)


def create_tables(engine):
    Base.metadata.create_all(engine)
