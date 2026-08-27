# import QuantLib as ql
#
# settlement = ql.Date(28, 11, 2025)
# maturity   = ql.Date(27, 4, 2028)
#
# # Create a schedule (dummy — only for date logic; coupon rate = 0.0)
# schedule = ql.Schedule(
#     settlement,  # use settlement as start date to avoid odd first stub
#     maturity,
#     ql.Period(ql.Annual),          # frequency doesn't matter since coupon = 0
#     ql.NullCalendar(),
#     ql.Unadjusted, ql.Unadjusted,
#     ql.DateGeneration.Backward,
#     False
# )
#
# bond = ql.FixedRateBond(
#     0,
#     100000,        # face
#     schedule,
#     [0.0],         # zero coupon
#     ql.ActualActual(ql.ActualActual.ISMA)   # *** ACT/ACT ISMA here ***
# )
#
# clean = ql.BondPrice(99.21, ql.BondPrice.Clean)
#
# ytm = ql.BondFunctions.bondYield(
#     bond,
#     clean,
#     ql.ActualActual(ql.ActualActual.ISMA),  # *** also ACT/ACT here ***
#     ql.Compounded,
#     ql.Annual,
#     settlement
# )
#
# print("YTM %:", ytm * 100)
