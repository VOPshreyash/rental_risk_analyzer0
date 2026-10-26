# STEP 1 (v2): Pune-calibrated labelled dataset.
# Numeric clauses are GENERATED from templates and labelled by pune_rules.py
# (so labels always follow the rules). Qualitative clauses are hand-labelled.
import csv, random
from pune_rules import *

random.seed(42)
rows = []

def indian(n):                      # 126000 -> 1,26,000
    s = str(int(n))
    if len(s) <= 3: return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])

def mid(area, bhk):
    lo, hi = RENT_RANGES[area][bhk]; return int(round((lo + hi) / 2 / 500) * 500)

AREAS = [("Kothrud","kothrud"),("Hinjewadi Phase 1","hinjewadi phase 1"),("Hinjewadi Phase 2","hinjewadi phase 2/3"),
         ("Sus Gaon","sus gaon"),("Wakad","wakad"),("Viman Nagar","viman nagar"),("Baner","baner/balewadi"),
         ("Balewadi","baner/balewadi"),("Kharadi","kharadi")]

# ---- 1. RENT (generated, 14) ----
offsets = [-1000, 0, 1500, 2500, 3500, 4000, 4500, 5500, 6500, 7000, 7500, 9000, 12000, 15000]   # measured from the START of the range
for i, off in enumerate(offsets):
    disp, key = AREAS[i % len(AREAS)]; bhk = [1, 2, 2, 3][i % 4]
    lo, hi = RENT_RANGES[key][bhk]
    rent = int(round((lo + off) / 500) * 500)
    text = random.choice([
        f"The monthly rent for the {bhk} BHK flat at {disp} shall be Rs. {indian(rent)}, payable on or before the fifth of every month.",
        f"The Tenant agrees to pay a monthly rent of Rs. {indian(rent)} for the {bhk} BHK flat situated in {disp}."])
    rows.append((text, "rent", rent_risk(key, bhk, rent), "rule"))

# ---- 2. DEPOSIT amount (generated, 12) ----
for i, mult in enumerate([1, 1.5, 2, 2, 2.5, 3, 3, 3.5, 4, 5, 6, 10]):
    disp, key = AREAS[(i + 2) % len(AREAS)]; bhk = [2, 1, 3][i % 3]
    rent = int(round((RENT_RANGES[key][bhk][0] + 1000) / 500) * 500); dep = int(rent * mult)   # rent kept low-risk so the label reflects the deposit only
    text = f"The monthly rent for the {bhk} BHK flat at {disp} is Rs. {indian(rent)} and the Tenant shall pay a refundable security deposit of Rs. {indian(dep)}."
    rows.append((text, "deposit", deposit_risk(dep, rent), "rule"))

# ---- 3. DEPOSIT refund time (generated, 5) ----
for d in [15, 30, 45, 60, 90]:
    w = {15:"fifteen",30:"thirty",45:"forty five",60:"sixty",90:"ninety"}[d]
    rows.append((f"The security deposit shall be refunded within {w} days of handover after deducting documented damages.", "deposit", refund_risk(d), "rule"))

# ---- 4. RENT INCREASE (generated, 10) ----
for p in [5, 5, 7, 8, 10, 12, 15, 18, 20, 25]:
    rows.append((f"The rent shall be increased by {p} percent on renewal of the agreement after every eleven months.", "rent_increase", increase_risk(p), "rule"))

# ---- 5. LATE FEE (generated, 8) ----
for grace, fee in [(7,100),(5,200),(7,150),(5,400),(3,300),(2,200),(0,500),(3,1000)]:
    rows.append((f"A late fee of Rs. {fee} per day shall be charged if the rent is not paid within {grace} days of the due date." if grace
                 else f"A late fee of Rs. {fee} per day shall be charged from the day after the due date, with no grace period.",
                 "penalty", latefee_risk(grace, fee), "rule"))

# ---- 6. HAND-LABELLED qualitative clauses ----
H = []
def add(t, typ, r): H.append((t, typ, r, "hand"))
# deposit
add("The Landlord may deduct any amount from the deposit at his sole discretion without providing proof.", "deposit", "High")
add("The security deposit shall not be refunded if the Tenant leaves before completing the full term, whatever the reason.", "deposit", "High")
add("The deposit shall be refunded after deducting only documented damages, and the bills shall be shown to the Tenant.", "deposit", "Low")
add("The Landlord may retain the entire deposit as a cleaning and repainting charge irrespective of the actual condition.", "deposit", "High")
# lock-in
add("The agreement is a registered Leave and License Agreement for eleven months with a mutual lock-in of three months for both parties.", "lockin", "Low")
add("Either party may terminate during the lock-in period of six months by giving one month's written notice and paying one month's rent.", "lockin", "Low")
add("The Tenant shall not vacate during the lock-in period of eleven months, failing which the entire remaining rent becomes payable immediately.", "lockin", "High")
add("There is a lock-in period of twelve months applicable only to the Tenant, while the Landlord may terminate at any time.", "lockin", "High")
add("The lock-in period is eight months, and early exit requires payment of two months' rent as compensation.", "lockin", "Medium")
add("If the Tenant leaves within the lock-in period, the security deposit shall be forfeited and the balance rent shall be recovered.", "lockin", "High")
add("A lock-in period of six months applies to both parties, after which one month's notice is sufficient.", "lockin", "Low")
add("Early termination during the lock-in period is possible only with the written consent of the Landlord, which may be withheld.", "lockin", "Medium")
add("The tenancy is for eleven months and may be renewed by mutual written consent.", "lockin", "Low")
add("The lock-in period is nine months for the Tenant, and the Landlord has no lock-in.", "lockin", "High")
# eviction
add("The Landlord may terminate this agreement only on breach of terms, after giving a written notice of thirty days to remedy it.", "eviction", "Low")
add("Eviction shall follow due process of law, and the Tenant will be given a minimum of sixty days to vacate.", "eviction", "Low")
add("The Landlord reserves the right to evict the Tenant at any time without notice and without assigning any reason.", "eviction", "High")
add("The Tenant must vacate within seven days of receiving a notice from the Landlord, failing which belongings may be removed.", "eviction", "High")
add("The Landlord can terminate the tenancy by giving fifteen days' notice if the property is required for personal use.", "eviction", "Medium")
add("In case of non-payment of rent for two consecutive months, the Landlord may terminate the agreement after a seven day notice.", "eviction", "Medium")
add("The Landlord may enter and lock the premises immediately if the Tenant delays rent by even one day.", "eviction", "High")
add("Either party must give a written notice of one month before ending the tenancy.", "eviction", "Low")
add("On termination for personal use, the Tenant shall get thirty days' notice and the deposit shall be refunded on the same day.", "eviction", "Low")
# maintenance
add("The Landlord shall pay the society maintenance, sinking fund and corpus fund, and shall bear the cost of structural repairs.", "maintenance", "Low")
add("The Tenant shall pay the society maintenance as per the latest society bill, which the Landlord has shown to the Tenant.", "maintenance", "Medium")
add("Monthly maintenance shall be paid extra by the Tenant, as informed by the Landlord from time to time.", "maintenance", "High")
add("The Tenant shall bear the sinking fund, corpus fund and any structural repairs of the flat.", "maintenance", "High")
add("Any damage to the property, including normal wear and tear, shall be repaired at the Tenant's expense.", "maintenance", "High")
add("Clubhouse, move-in and move-out charges shall be shared equally between the Landlord and the Tenant.", "maintenance", "Medium")
add("Minor repairs caused by the Tenant shall be done at his cost, while major repairs not caused by the Tenant shall be done by the Landlord within seven days.", "maintenance", "Low")
add("The Landlord is not responsible for any repairs during the tenancy and the Tenant must not complain about defects.", "maintenance", "High")
add("Appliance servicing shall be done by the Tenant at his own cost.", "maintenance", "Medium")
add("The Tenant shall repaint the entire flat before vacating at his own cost.", "maintenance", "Medium")
# utilities
add("Electricity and metered water shall be paid by the Tenant as per the actual meter readings.", "utilities", "Low")
add("The Tenant shall pay electricity at the tariff charged by MSEDCL without any markup.", "utilities", "Low")
add("Electricity shall be charged at Rs. 15 per unit as decided by the Landlord, irrespective of the actual tariff.", "utilities", "High")
add("Gas, internet and metered water charges shall be paid by the Tenant as per actual bills.", "utilities", "Low")
add("The Tenant shall pay a fixed monthly charge of Rs. 800 for water irrespective of consumption.", "utilities", "Medium")
add("All property tax and building taxes shall be paid by the Tenant in addition to the monthly rent.", "utilities", "High")
add("The Landlord may cut off electricity and water supply if rent is delayed by any number of days.", "utilities", "High")
add("Common area electricity and lift charges shall be paid through the society maintenance borne by the Landlord.", "utilities", "Low")
add("Internet and cable charges shall be paid by the Tenant, and the Landlord shall permit the installation.", "utilities", "Low")
# penalty (qualitative)
add("The Tenant shall pay a penalty of Rs. 5,000 per day for any breach of any clause of this agreement.", "penalty", "High")
add("A penalty equal to three months' rent will be imposed if guests stay overnight without permission.", "penalty", "High")
add("The Landlord may impose fines at his discretion for noise, parking or any other issue as he deems fit.", "penalty", "High")
add("No late fee shall be charged if the rent is paid within a grace period of seven days after the due date.", "penalty", "Low")
# general / boilerplate clauses (written in my own words, not copied from any template)
add("The Licensee shall use the flat only for residential purposes and not for any business or commercial activity.", "general", "Low")
add("The Licensee shall not sublet, assign or part with possession of the flat or any part of it to any other person.", "general", "Low")
add("No structural change, drilling or alteration shall be made in the flat without the written consent of the Licensor.", "general", "Low")
add("The Licensee shall keep the premises clean and shall not cause nuisance or annoyance to the neighbours.", "general", "Low")
add("The Licensor or his representative may inspect the flat at reasonable times after giving prior notice to the Licensee.", "general", "Low")
add("The Licensee shall comply with the rules and bye-laws of the housing society.", "general", "Low")
add("The Licensee shall not store any hazardous, illegal or inflammable goods in the flat.", "general", "Low")
add("The Licensee shall hand over the flat in the same condition as received, excluding normal wear and tear.", "general", "Low")
add("The Licensee shall not keep pets without the prior permission of the Licensor and the society.", "general", "Low")
add("The Licensor confirms that he is the lawful owner of the flat and has the right to give it on leave and license.", "general", "Low")
add("This agreement shall be governed by the laws of India and the courts at Pune shall have jurisdiction.", "general", "Low")
add("The Licensor shall hand over vacant possession of the flat to the Licensee on the date of commencement.", "general", "Low")
add("The Licensee shall not allow more than the agreed number of persons to stay in the flat.", "general", "Low")
add("Overnight visitors are allowed only with the prior written permission of the Licensor, who may refuse without giving reasons.", "general", "Medium")
add("The Licensor may enter the flat at any time without informing the Licensee.", "general", "High")
add("The Licensee shall be fully liable for every loss or damage to the flat, whether or not it was caused by the Licensee.", "general", "High")
rows += H

random.shuffle(rows)
with open("clauses.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["clause_text", "clause_type", "risk_level", "label_source"]); w.writerows(rows)

import collections
print("Saved", len(rows), "clauses")
print("Types:", dict(collections.Counter(r[1] for r in rows)))
print("Risk :", dict(collections.Counter(r[2] for r in rows)))
