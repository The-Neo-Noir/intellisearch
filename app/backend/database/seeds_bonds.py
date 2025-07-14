from db import init_db
from models import Bond

init_db()
#
# Use this to insert some canned data
#
#
sample_bonds = [
    Bond(issuer="Tata Capital", coupon=8.5, maturity_year=2027, rating="AA+", segment="PSU", location="Mumbai"),
    Bond(issuer="HDFC Ltd", coupon=7.75, maturity_year=2026, rating="AAA", segment="Corporate", location="Delhi"),
    Bond(issuer="Rural Electrification Corp", coupon=8.0, maturity_year=2029, rating="AA", segment="PSU", location="Bangalore"),
    Bond(issuer="L&T Finance", coupon=9.2, maturity_year=2025, rating="A+", segment="Corporate", location="Chennai"),
    Bond(issuer="NABARD", coupon=7.5, maturity_year=2028, rating="AAA", segment="PSU", location="Hyderabad"),
]

for bond in sample_bonds:
    bond.save()

print("✅ Sample bonds inserted into MongoDB.")
