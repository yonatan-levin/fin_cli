
class Fundamental_Params:

    PE = ["fa_pe", {'': 'Any', 'low': 'Low (<15)', 'profitable': 'Profitable (>0)', 'high': 'High (>50)', 'u5': 'Under 5', 'u10': 'Under 10', 'u15': 'Under 15', 'u20': 'Under 20', 'u25': 'Under 25', 'u30': 'Under 30', 'u35': 'Under 35', 'u40': 'Under 40',
                    'u45': 'Under 45', 'u50': 'Under 50', 'o5': 'Over 5', 'o10': 'Over 10', 'o15': 'Over 15', 'o20': 'Over 20', 'o25': 'Over 25', 'o30': 'Over 30', 'o35': 'Over 35', 'o40': 'Over 40', 'o45': 'Over 45', 'o50': 'Over 50', 'frange': 'Custom (Elite only)'}]

    FORWARD_PE = ["fa_fpe", {'': 'Any', 'low': 'Low (<15)', 'profitable': 'Profitable (>0)', 'high': 'High (>50)', 'u5': 'Under 5', 'u10': 'Under 10', 'u15': 'Under 15', 'u20': 'Under 20', 'u25': 'Under 25', 'u30': 'Under 30', 'u35': 'Under 35', 'u40': 'Under 40',
                              'u45': 'Under 45', 'u50': 'Under 50', 'o5': 'Over 5', 'o10': 'Over 10', 'o15': 'Over 15', 'o20': 'Over 20', 'o25': 'Over 25', 'o30': 'Over 30', 'o35': 'Over 35', 'o40': 'Over 40', 'o45': 'Over 45', 'o50': 'Over 50', 'frange': 'Custom (Elite only)'}]

    PEG = ["fa_peg", {'': 'Any', 'low': 'Low (<1)', 'high': 'High (>2)', 'u1': 'Under 1', 'u2': 'Under 2',
                                'u3': 'Under 3', 'o1': 'Over 1', 'o2': 'Over 2', 'o3': 'Over 3', 'frange': 'Custom (Elite only)'}]

    PRICE_SALES = ["fa_ps", {'': 'Any', 'low': 'Low (<1)', 'high': 'High (>10)', 'u1': 'Under 1', 'u2': 'Under 2', 'u3': 'Under 3', 'u4': 'Under 4', 'u5': 'Under 5', 'u6': 'Under 6', 'u7': 'Under 7', 'u8': 'Under 8', 'u9': 'Under 9',
                             'u10': 'Under 10', 'o1': 'Over 1', 'o2': 'Over 2', 'o3': 'Over 3', 'o4': 'Over 4', 'o5': 'Over 5', 'o6': 'Over 6', 'o7': 'Over 7', 'o8': 'Over 8', 'o9': 'Over 9', 'o10': 'Over 10', 'frange': 'Custom (Elite only)'}]

    PRICE_BOOKS = ["fa_pb", {'': 'Any', 'low': 'Low (<1)', 'high': 'High (>5)', 'u1': 'Under 1', 'u2': 'Under 2', 'u3': 'Under 3', 'u4': 'Under 4', 'u5': 'Under 5', 'u6': 'Under 6', 'u7': 'Under 7', 'u8': 'Under 8', 'u9': 'Under 9',
                              'u10': 'Under 10', 'o1': 'Over 1', 'o2': 'Over 2', 'o3': 'Over 3', 'o4': 'Over 4', 'o5': 'Over 5', 'o6': 'Over 6', 'o7': 'Over 7', 'o8': 'Over 8', 'o9': 'Over 9', 'o10': 'Over 10', 'frange': 'Custom (Elite only)'}]

    PRICE_TO_CASH = ["fa_pc", {'': 'Any', 'low': 'Low (<3)', 'high': 'High (>50)', 'u1': 'Under 1', 'u2': 'Under 2', 'u3': 'Under 3', 'u4': 'Under 4', 'u5': 'Under 5', 'u6': 'Under 6', 'u7': 'Under 7', 'u8': 'Under 8', 'u9': 'Under 9', 'u10': 'Under 10', 'o1': 'Over 1',
                                'o2': 'Over 2', 'o3': 'Over 3', 'o4': 'Over 4', 'o5': 'Over 5', 'o6': 'Over 6', 'o7': 'Over 7', 'o8': 'Over 8', 'o9': 'Over 9', 'o10': 'Over 10', 'o20': 'Over 20', 'o30': 'Over 30', 'o40': 'Over 40', 'o50': 'Over 50', 'frange': 'Custom (Elite only)'}]

    PRICE_TO_FREE_CASH_FLOW = ["fa_pfcf", {'': 'Any', 'low': 'Low (<15)', 'high': 'High (>50)', 'u5': 'Under 5', 'u10': 'Under 10', 'u15': 'Under 15', 'u20': 'Under 20', 'u25': 'Under 25', 'u30': 'Under 30', 'u35': 'Under 35', 'u40': 'Under 40', 'u45': 'Under 45', 'u50': 'Under 50', 'u60': 'Under 60', 'u70': 'Under 70', 'u80': 'Under 80',
                                            'u90': 'Under 90', 'u100': 'Under 100', 'o5': 'Over 5', 'o10': 'Over 10', 'o15': 'Over 15', 'o20': 'Over 20', 'o25': 'Over 25', 'o30': 'Over 30', 'o35': 'Over 35', 'o40': 'Over 40', 'o45': 'Over 45', 'o50': 'Over 50', 'o60': 'Over 60', 'o70': 'Over 70', 'o80': 'Over 80', 'o90': 'Over 90', 'o100': 'Over 100', 'frange': 'Custom (Elite only)'}]

    EPS_GROWTH = ["fa_epsyoy", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                 'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    EPS_GROWTH_NEXT_YEAR = ["fa_epsyoy1", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                            'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    EPS_PAST_5_YEARS = ["fa_eps5years", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                          'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    EPS_GROWTH_NEXT_5_YEARS = ["fa_estltgrowth", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (<10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                                  'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    SALES_GROWTH_PAST_5_YEARS = ["fa_sales5years", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                                     'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    EPS_GROWTH_QTR_OVER_QTR = ["fa_epsqoq", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                              'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    SALES_GROWTH_QTR_OVER_QTR = ["fa_salesqoq", {'': 'Any', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'poslow': 'Positive Low (0-10%)', 'high': 'High (>25%)', 'u5': 'Under 5%', 'u10': 'Under 10%', 'u15': 'Under 15%',
                                                  'u20': 'Under 20%', 'u25': 'Under 25%', 'u30': 'Under 30%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'frange': 'Custom (Elite only)'}]

    ROA = ["fa_roa", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'verypos': 'Very Positive (>15%)', 'veryneg': 'Very Negative (<-15%)', 'u-50': 'Under -50%', 'u-45': 'Under -45%', 'u-40': 'Under -40%', 'u-35': 'Under -35%', 'u-30': 'Under -30%', 'u-25': 'Under -25%', 'u-20': 'Under -20%',
                       'u-15': 'Under -15%', 'u-10': 'Under -10%', 'u-5': 'Under -5%', 'o5': 'Over +5%', 'o10': 'Over +10%', 'o15': 'Over +15%', 'o20': 'Over +20%', 'o25': 'Over +25%', 'o30': 'Over +30%', 'o35': 'Over +35%', 'o40': 'Over +40%', 'o45': 'Over +45%', 'o50': 'Over +50%', 'frange': 'Custom (Elite only)'}]

    ROE = ["fa_roe", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'verypos': 'Very Positive (>30%)', 'veryneg': 'Very Negative (<-15%)', 'u-50': 'Under -50%', 'u-45': 'Under -45%', 'u-40': 'Under -40%', 'u-35': 'Under -35%', 'u-30': 'Under -30%', 'u-25': 'Under -25%', 'u-20': 'Under -20%',
                       'u-15': 'Under -15%', 'u-10': 'Under -10%', 'u-5': 'Under -5%', 'o5': 'Over +5%', 'o10': 'Over +10%', 'o15': 'Over +15%', 'o20': 'Over +20%', 'o25': 'Over +25%', 'o30': 'Over +30%', 'o35': 'Over +35%', 'o40': 'Over +40%', 'o45': 'Over +45%', 'o50': 'Over +50%', 'frange': 'Custom (Elite only)'}]

    ROI = ["fa_roi", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'verypos': 'Very Positive (>25%)', 'veryneg': 'Very Negative (<-10%)', 'u-50': 'Under -50%', 'u-45': 'Under -45%', 'u-40': 'Under -40%', 'u-35': 'Under -35%', 'u-30': 'Under -30%', 'u-25': 'Under -25%', 'u-20': 'Under -20%',
                       'u-15': 'Under -15%', 'u-10': 'Under -10%', 'u-5': 'Under -5%', 'o5': 'Over +5%', 'o10': 'Over +10%', 'o15': 'Over +15%', 'o20': 'Over +20%', 'o25': 'Over +25%', 'o30': 'Over +30%', 'o35': 'Over +35%', 'o40': 'Over +40%', 'o45': 'Over +45%', 'o50': 'Over +50%', 'frange': 'Custom (Elite only)'}]

    CURRENT_RATIO = ["fa_curratio", {'': 'Any', 'high': 'High (>3)', 'low': 'Low (<1)', 'u1': 'Under 1', 'u0.5': 'Under 0.5', 'o0.5': 'Over 0.5', 'o1': 'Over 1',
                                      'o1.5': 'Over 1.5', 'o2': 'Over 2', 'o3': 'Over 3', 'o4': 'Over 4', 'o5': 'Over 5', 'o10': 'Over 10', 'frange': 'Custom (Elite only)'}]

    QUICK_RATIO = ["fa_quickratio", {'': 'Any', 'high': 'High (>3)', 'low': 'Low (<0.5)', 'u1': 'Under 1', 'u0.5': 'Under 0.5', 'o0.5': 'Over 0.5',
                                      'o1': 'Over 1', 'o1.5': 'Over 1.5', 'o2': 'Over 2', 'o3': 'Over 3', 'o4': 'Over 4', 'o5': 'Over 5', 'o10': 'Over 10', 'frange': 'Custom (Elite only)'}]

    LT_Debt_TO_Equity = ["fa_ltdebteq", {'': 'Any', 'high': 'High (>0.5)', 'low': 'Low (<0.1)', 'u1': 'Under 1', 'u0.9': 'Under 0.9', 'u0.8': 'Under 0.8', 'u0.7': 'Under 0.7', 'u0.6': 'Under 0.6', 'u0.5': 'Under 0.5', 'u0.4': 'Under 0.4', 'u0.3': 'Under 0.3', 'u0.2': 'Under 0.2',
                                          'u0.1': 'Under 0.1', 'o0.1': 'Over 0.1', 'o0.2': 'Over 0.2', 'o0.3': 'Over 0.3', 'o0.4': 'Over 0.4', 'o0.5': 'Over 0.5', 'o0.6': 'Over 0.6', 'o0.7': 'Over 0.7', 'o0.8': 'Over 0.8', 'o0.9': 'Over 0.9', 'o1': 'Over 1', 'frange': 'Custom (Elite only)'}]

    Debt_TO_Equity = ["fa_debteq", {'': 'Any', 'high': 'High (>0.5)', 'low': 'Low (<0.1)', 'u1': 'Under 1', 'u0.9': 'Under 0.9', 'u0.8': 'Under 0.8', 'u0.7': 'Under 0.7', 'u0.6': 'Under 0.6', 'u0.5': 'Under 0.5', 'u0.4': 'Under 0.4', 'u0.3': 'Under 0.3', 'u0.2': 'Under 0.2',
                                     'u0.1': 'Under 0.1', 'o0.1': 'Over 0.1', 'o0.2': 'Over 0.2', 'o0.3': 'Over 0.3', 'o0.4': 'Over 0.4', 'o0.5': 'Over 0.5', 'o0.6': 'Over 0.6', 'o0.7': 'Over 0.7', 'o0.8': 'Over 0.8', 'o0.9': 'Over 0.9', 'o1': 'Over 1', 'frange': 'Custom (Elite only)'}]

    Gross_Margin = ["fa_grossmargin", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'high': 'High (>50%)', 'u90': 'Under 90%', 'u80': 'Under 80%', 'u70': 'Under 70%', 'u60': 'Under 60%', 'u50': 'Under 50%', 'u45': 'Under 45%', 'u40': 'Under 40%', 'u35': 'Under 35%', 'u30': 'Under 30%', 'u25': 'Under 25%', 'u20': 'Under 20%', 'u15': 'Under 15%', 'u10': 'Under 10%', 'u5': 'Under 5%', 'u0': 'Under 0%', 'u-10': 'Under -10%',
                                        'u-20': 'Under -20%', 'u-30': 'Under -30%', 'u-50': 'Under -50%', 'u-70': 'Under -70%', 'u-100': 'Under -100%', 'o0': 'Over 0%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'o35': 'Over 35%', 'o40': 'Over 40%', 'o45': 'Over 45%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%', 'o80': 'Over 80%', 'o90': 'Over 90%', 'frange': 'Custom (Elite only)'}]

    Operating_Margin = ["fa_opermargin", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'veryneg': 'Very Negative (<-20%)', 'high': 'High (>25%)', 'u90': 'Under 90%', 'u80': 'Under 80%', 'u70': 'Under 70%', 'u60': 'Under 60%', 'u50': 'Under 50%', 'u45': 'Under 45%', 'u40': 'Under 40%', 'u35': 'Under 35%', 'u30': 'Under 30%', 'u25': 'Under 25%', 'u20': 'Under 20%', 'u15': 'Under 15%', 'u10': 'Under 10%', 'u5': 'Under 5%', 'u0': 'Under 0%',
                                           'u-10': 'Under -10%', 'u-20': 'Under -20%', 'u-30': 'Under -30%', 'u-50': 'Under -50%', 'u-70': 'Under -70%', 'u-100': 'Under -100%', 'o0': 'Over 0%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'o35': 'Over 35%', 'o40': 'Over 40%', 'o45': 'Over 45%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%', 'o80': 'Over 80%', 'o90': 'Over 90%', 'frange': 'Custom (Elite only)'}]

    Net_Margin = ["fa_netmargin", {'': 'Any', 'pos': 'Positive (>0%)', 'neg': 'Negative (<0%)', 'veryneg': 'Very Negative (<-20%)', 'high': 'High (>20%)', 'u90': 'Under 90%', 'u80': 'Under 80%', 'u70': 'Under 70%', 'u60': 'Under 60%', 'u50': 'Under 50%', 'u45': 'Under 45%', 'u40': 'Under 40%', 'u35': 'Under 35%', 'u30': 'Under 30%', 'u25': 'Under 25%', 'u20': 'Under 20%', 'u15': 'Under 15%', 'u10': 'Under 10%', 'u5': 'Under 5%', 'u0': 'Under 0%',
                                    'u-10': 'Under -10%', 'u-20': 'Under -20%', 'u-30': 'Under -30%', 'u-50': 'Under -50%', 'u-70': 'Under -70%', 'u-100': 'Under -100%', 'o0': 'Over 0%', 'o5': 'Over 5%', 'o10': 'Over 10%', 'o15': 'Over 15%', 'o20': 'Over 20%', 'o25': 'Over 25%', 'o30': 'Over 30%', 'o35': 'Over 35%', 'o40': 'Over 40%', 'o45': 'Over 45%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%', 'o80': 'Over 80%', 'o90': 'Over 90%', 'frange': 'Custom (Elite only)'}]

    Payout_ratio = ["fa_payoutratio", {'': 'Any', 'none': 'None (0%)', 'pos': 'Positive (>0%)', 'low': 'Low (<20%)', 'high': 'High (>50%)', 'o0': 'Over 0%', 'o10': 'Over 10%', 'o20': 'Over 20%', 'o30': 'Over 30%', 'o40': 'Over 40%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%',
                                        'o80': 'Over 80%', 'o90': 'Over 90%', 'o100': 'Over 100%', 'u10': 'Under 10%', 'u20': 'Under 20%', 'u30': 'Under 30%', 'u40': 'Under 40%', 'u50': 'Under 50%', 'u60': 'Under 60%', 'u70': 'Under 70%', 'u80': 'Under 80%', 'u90': 'Under 90%', 'u100': 'Under 100%', 'frange': 'Custom (Elite only)'}]

    Insider_Ownership = ["sh_insiderown", {'': 'Any', 'low': 'Low (<5%)', 'high': 'High (>30%)', 'veryhigh': 'Very High (>50%)', 'o10': 'Over 10%', 'o20': 'Over 20%',
                                           'o30': 'Over 30%', 'o40': 'Over 40%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%', 'o80': 'Over 80%', 'o90': 'Over 90%', 'frange': 'Custom (Elite only)'}]

    Insider_Transactions = ["sh_insidertrans", {'': 'Any', 'veryneg': 'Very Negative (<20%)', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'verypos': 'Very Positive (>20%)', 'u-90': 'Under -90%', 'u-80': 'Under -80%', 'u-70': 'Under -70%', 'u-60': 'Under -60%', 'u-50': 'Under -50%', 'u-45': 'Under -45%', 'u-40': 'Under -40%', 'u-35': 'Under -35%', 'u-30': 'Under -30%', 'u-25': 'Under -25%',
                                                'u-20': 'Under -20%', 'u-15': 'Under -15%', 'u-10': 'Under -10%', 'u-5': 'Under -5%', 'o5': 'Over +5%', 'o10': 'Over +10%', 'o15': 'Over +15%', 'o20': 'Over +20%', 'o25': 'Over +25%', 'o30': 'Over +30%', 'o35': 'Over +35%', 'o40': 'Over +40%', 'o45': 'Over +45%', 'o50': 'Over +50%', 'o60': 'Over +60%', 'o70': 'Over +70%', 'o80': 'Over +80%', 'o90': 'Over +90%', 'frange': 'Custom (Elite only)'}]

    Institutional_Ownership = ["sh_instown", {'': 'Any', 'low': 'Low (<5%)', 'high': 'High (>90%)', 'u90': 'Under 90%', 'u80': 'Under 80%', 'u70': 'Under 70%', 'u60': 'Under 60%', 'u50': 'Under 50%', 'u40': 'Under 40%', 'u30': 'Under 30%',
                                              'u20': 'Under 20%', 'u10': 'Under 10%', 'o10': 'Over 10%', 'o20': 'Over 20%', 'o30': 'Over 30%', 'o40': 'Over 40%', 'o50': 'Over 50%', 'o60': 'Over 60%', 'o70': 'Over 70%', 'o80': 'Over 80%', 'o90': 'Over 90%', 'frange': 'Custom (Elite only)'}]

    Institutional_Transactions = ["sh_insttrans", {'': 'Any', 'veryneg': 'Very Negative (<20%)', 'neg': 'Negative (<0%)', 'pos': 'Positive (>0%)', 'verypos': 'Very Positive (>20%)', 'u-50': 'Under -50%', 'u-45': 'Under -45%', 'u-40': 'Under -40%', 'u-35': 'Under -35%', 'u-30': 'Under -30%', 'u-25': 'Under -25%',
                                                    'u-20': 'Under -20%', 'u-15': 'Under -15%', 'u-10': 'Under -10%', 'u-5': 'Under -5%', 'o5': 'Over +5%', 'o10': 'Over +10%', 'o15': 'Over +15%', 'o20': 'Over +20%', 'o25': 'Over +25%', 'o30': 'Over +30%', 'o35': 'Over +35%', 'o40': 'Over +40%', 'o45': 'Over +45%', 'o50': 'Over +50%', 'frange': 'Custom (Elite only)'}]
