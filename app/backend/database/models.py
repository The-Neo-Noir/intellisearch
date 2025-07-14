from mongoengine import Document, StringField, FloatField, IntField, DateTimeField
from datetime import datetime


class Bond(Document):
    issuer = StringField()
    coupon = FloatField()
    maturity_year = IntField()
    rating = StringField()
    segment = StringField()
    location = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'bonds'}
