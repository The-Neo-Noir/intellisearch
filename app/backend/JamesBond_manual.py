# from datetime import date, timedelta
# import math
# from typing import List, Optional
#
# def year_frac_act_act(start: date, end: date) -> float:
#     """Actual/Actual (ICMA) — exact day count divided by 365 or 366 appropriately."""
#     delta = end - start
#     # Approximate using 365-day year; suitable for yield baseline
#     return delta.days / 365.0
#
# def year_frac_30_360(start: date, end: date) -> float:
#     """
#     30/360 US (or generic) convention:
#     - Each month = 30 days
#     - Each year = 360 days
#     """
#     d1, m1, y1 = start.day, start.month, start.year
#     d2, m2, y2 = end.day, end.month, end.year
#     # adjust days per convention
#     if d1 == 31:
#         d1 = 30
#     if d2 == 31 and d1 == 30:
#         d2 = 30
#     days = (y2 - y1) * 360 + (m2 - m1) * 30 + (d2 - d1)
#     return days / 360.0
#
# def year_frac_act_365(start: date, end: date) -> float:
#     delta = end - start
#     return delta.days / 365.0
#
# def year_frac_30E_360(start: date, end: date) -> float:
#     """30E/360 — Eurobond basis (each month 30 days, each year 360 days)"""
#     d1, m1, y1 = start.day, start.month, start.year
#     d2, m2, y2 = end.day, end.month, end.year
#     # per 30E/360 — if day is 31, make 30
#     d1 = min(d1, 30)
#     d2 = min(d2, 30)
#     days = (y2 - y1) * 360 + (m2 - m1) * 30 + (d2 - d1)
#     return days / 360.0
#
# def compute_ytm_zero_coupon(
#         clean_price: float,
#         redemption: float,
#         settlement: date,
#         maturity: date,
#         daycount: str = "ACT/ACT"
# ) -> float:
#     """
#     Compute YTM for a zero-coupon bond.
#     clean_price: price as % of par (e.g. 99.21) OR absolute (if you use absolute, pass redemption accordingly)
#     redemption: face value (e.g. 100000)
#     daycount: one of ["ACT/ACT", "ACT/365", "30/360", "30E/360"]
#     Returns: YTM as decimal (e.g. 0.0107 = 1.07%)
#     """
#     # If clean_price is expressed as percent-of-par, convert to absolute:
#     # E.g. clean_price = 99.21 → PV = 0.9921 * redemption
#     pv = clean_price / 100.0 * redemption
#     fv = redemption
#
#     if daycount == "ACT/ACT":
#         T = year_frac_act_act(settlement, maturity)
#     elif daycount == "ACT/365":
#         T = year_frac_act_365(settlement, maturity)
#     elif daycount == "30/360":
#         T = year_frac_30_360(settlement, maturity)
#     elif daycount == "30E/360":
#         T = year_frac_30E_360(settlement, maturity)
#     else:
#         raise ValueError(f"Unsupported daycount convention: {daycount}")
#
#     ytm = (fv / pv) ** (1.0 / T) - 1.0
#     return ytm
#
# def compute_ytm_coupon_bond(
#         clean_price: float,
#         redemption: float,
#         coupon_rate: float,
#         coupon_freq: int,
#         settlement: date,
#         maturity: date,
#         daycount: str = "ACT/ACT",
#         guess: float = 0.05,
#         tol: float = 1e-8,
#         max_iter: int = 100
# ) -> float:
#     """
#     Compute YTM for a coupon-bearing bond via numerical solver.
#     - coupon_rate: annual coupon rate (e.g. 0.05 = 5%)
#     - coupon_freq: coupons per year, e.g. 2 for semiannual, 1 for annual
#     - clean_price: price as % of par
#     - redemption: face value
#     Returns YTM as decimal (annual yield, compounded per coupon period)
#     """
#     pv = clean_price / 100.0 * redemption
#     # Generate schedule of cashflows
#     # Simple approach: assume regular coupon periods — more sophistication needed for odd first/last
#
#     # Let's approximate: compute number of periods
#     years = (maturity - settlement).days / 365.0
#     n_periods = int(round(years * coupon_freq))
#     coupon_amt = redemption * coupon_rate / coupon_freq
#
#     def price_from_yield(y):
#         price = 0.0
#         for i in range(1, n_periods + 1):
#             cf = coupon_amt
#             if i == n_periods:
#                 cf += redemption
#             price += cf / ((1 + y / coupon_freq) ** i)
#         return price
#
#     # Use simple bisection or Newton-Raphson
#     low, high = -0.99, 1.0  # -99% to +100% yields (wide bounds)
#     for _ in range(max_iter):
#         mid = (low + high) / 2.0
#         p = price_from_yield(mid)
#         if abs(p - pv) < tol:
#             return mid
#         # adjust bounds
#         if p > pv:
#             low = mid
#         else:
#             high = mid
#     # fallback
#     return mid
#
# # Example usage
# if __name__ == "__main__":
#     # Example: XS2333569056 (zero-coupon)
#     ytm = compute_ytm_zero_coupon(
#         clean_price=99.21,
#         redemption=100_000,
#         settlement=date(2025,11,28),
#         maturity=date(2028,4,27),
#         daycount="ACT/ACT"
#     )
#     print(f"YTM (annual, zero-coupon): {ytm*100:.6f}%")
