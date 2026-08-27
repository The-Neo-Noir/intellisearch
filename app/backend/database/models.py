from mongoengine import Document, StringField, FloatField, IntField, DateTimeField
from datetime import datetime


class Bond(Document):
    isin = StringField()
    currency = StringField()
    issuer = StringField()
    segment = StringField()
    coupon = FloatField()
    maturity_year = IntField()
    rating = StringField()
    yieldType= StringField()
    issuer_location = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'bonds'}

