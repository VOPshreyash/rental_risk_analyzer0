"""
pune_rules.py  -  Pune rental-market rules (single source of truth)
Used by: dataset generator (labels), Step 3 (parsing) and Step 5 (risk scoring).
All figures are from the student's own market research (Pune, 2026) unless
marked ASSUMPTION.
"""

# Monthly rent ranges (Rs.) -> {area: {bhk: (min, max)}}
RENT_RANGES = {
    "kothrud":            {1: (18000, 26000), 2: (27000, 38000), 3: (38000, 55000)},
    "hinjewadi phase 1":  {1: (13000, 20000), 2: (22000, 32000), 3: (30000, 43000)},
    "hinjewadi phase 2/3":{1: (13000, 21000), 2: (23000, 35000), 3: (32000, 48000)},
    "wakad":              {1: (17000, 25000), 2: (26000, 36000), 3: (38000, 55000)},
    "viman nagar":        {1: (22000, 32000), 2: (32000, 45000), 3: (45000, 65000)},
    "baner/balewadi":     {1: (20000, 30000), 2: (32000, 45000), 3: (45000, 70000)},
    "kharadi":            {1: (18000, 28000), 2: (28000, 40000), 3: (40000, 60000)},
}
RENT_RANGES["sus gaon"] = RENT_RANGES["hinjewadi phase 2/3"]

# Words found in text -> key in RENT_RANGES
AREA_ALIASES = {
    "kothrud": "kothrud", "wakad": "wakad", "kharadi": "kharadi",
    "viman nagar": "viman nagar", "baner": "baner/balewadi", "balewadi": "baner/balewadi",
    "sus gaon": "sus gaon", "sus": "sus gaon", "susgaon": "sus gaon",
    "hinjewadi phase 1": "hinjewadi phase 1", "hinjewadi phase 2": "hinjewadi phase 2/3",
    "hinjewadi phase 3": "hinjewadi phase 2/3", "hinjewadi": "hinjewadi phase 2/3",
}

SOCIETY_MAINTENANCE = {"basic": (1500, 3000), "standard": (3000, 6000), "premium": (6000, 12000)}

def rent_risk(area_key, bhk, rent):
    lo, hi = RENT_RANGES[area_key][bhk]
    over = rent - lo
    if over <= 4000:  return "Low"
    if over <= 7000:  return "Medium"
    return "High"

def deposit_risk(deposit, rent):
    m = deposit / rent
    if m <= 2: return "Low"
    if m <= 3: return "Medium"
    return "High"

def increase_risk(pct):
    if pct <= 10: return "Low"
    if pct <= 15: return "Medium"
    return "High"

def refund_risk(days):
    if days <= 30: return "Low"
    if days <= 60: return "Medium"
    return "High"

def latefee_risk(grace_days, fee_per_day):
    if grace_days >= 5 and fee_per_day <= 200: return "Low"
    if grace_days >= 3 and fee_per_day <= 500: return "Medium"
    return "High"

def lockin_risk(months, one_sided):
    if one_sided: return "High"
    if months <= 6: return "Low"
    if months <= 11: return "Medium"
    return "High"

LANDLORD_PAYS = ["society maintenance", "sinking fund", "corpus fund", "structural repair"]
TENANT_PAYS   = ["electricity", "gas", "internet", "metered water"]
NEGOTIABLE    = ["clubhouse", "move-in", "move-out", "appliance servicing"]

ASSUMPTIONS = [
    "Rent rule (CONFIRMED by student, Reading B): extra is measured above the START (lowest rent) of the area/BHK range.",
    "Late fee: 'modest' taken as <= Rs.200/day (Low) and <= Rs.500/day (Medium).",
    "Deposit refund: > 60 days treated as High.",
    "Lock-in: <= 6 months mutual = Low; 7-11 months = Medium; one-sided or forfeiture = High.",
]
