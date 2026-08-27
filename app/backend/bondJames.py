# import QuantLib as ql
# from scipy.optimize import brentq  # optional; can replace with bisection if no scipy
#
# def bloomberg_ytm_30_360(PV, FV, settlement, maturity, issue=None, frequency=1, coupon_rate=0.0):
#     """
#     Bloomberg-style YTM for bonds using ISMA-30/360 convention.
#
#     Parameters:
#         PV: Present value (absolute price)
#         FV: Face value
#         settlement: QuantLib.Date
#         maturity: QuantLib.Date
#         issue: QuantLib.Date (required for coupon bonds)
#         frequency: coupon frequency (1=annual, 2=semiannual, etc.)
#         coupon_rate: annual coupon rate (0 for zero-coupon)
#
#     Returns:
#         YTM as decimal
#     """
#
#     dc = ql.Thirty360(ql.Thirty360.ISMA)
#
#     # Zero-coupon bond
#     if coupon_rate == 0.0:
#         T = dc.yearFraction(settlement, maturity)
#         ytm = (FV - PV) / (PV * T)  # last-period simple interest
#         return ytm
#
#     # Coupon-bearing bond
#     if issue is None:
#         raise ValueError("Issue date is required for coupon-bearing bonds")
#
#     # Build schedule
#     schedule = ql.Schedule(
#         issue,
#         maturity,
#         ql.Period(frequency),
#         ql.NullCalendar(),
#         ql.Unadjusted, ql.Unadjusted,
#         ql.DateGeneration.Backward,
#         False
#     )
#
#     dates = list(schedule)
#
#     # Count full coupon periods before settlement
#     full_periods = 0
#     for d in dates:
#         if d <= settlement:
#             full_periods += 1
#
#     T_full = full_periods - 1
#     stub_start = settlement
#     stub_end = maturity
#     T_stub = dc.yearFraction(stub_start, stub_end)
#
#     # Solver: last-period simple interest
#     def f(y):
#         return FV / ((1 + y)**T_full * (1 + y*T_stub)) - PV
#
#     ytm = brentq(f, 0.0, 1.0)
#     return ytm
#
# # -------------------------
# # Example: XS2333569056, ISMA-30/360
# # -------------------------
# PV = 99210
# FV = 100000
# settlement = ql.Date(26, 11, 2025)
# maturity = ql.Date(27, 4, 2028)
#
# ytm = bloomberg_ytm_30_360(PV, FV, settlement, maturity, coupon_rate=0.0)
# print("Zero-coupon ISMA-30/360 YTM (decimal):", ytm)
# print("Zero-coupon ISMA-30/360 YTM (%):", ytm*100)
