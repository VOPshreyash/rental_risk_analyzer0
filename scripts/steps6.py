# ============================ STEP 6
md("""
## STEP 6 — Official Maharashtra Form Mode *(live demo)*

The real **Leave and License Agreement** format (Maharashtra IGR) differs from my training wording: it says *Licensor/Licensee* and *"compensation"* (not rent), puts the rent **and** the deposit in one clause (Clause 2), has **staged-rent** and **non-refundable-deposit** options, and has no lock-in, increase or late-fee clause at all.

**Upgrades in this step**
1. **Money-role detection** – decides whether each `Rs.` amount is rent or deposit from the words around it (e.g. *"Rs. 36,000 per month"* vs *"Rs. 72,000 interest free refundable deposit"*).
2. **Clause 2 composite check** – one clause, several risks: rent vs Pune market range, deposit ÷ rent, non-refundable deposit, and **staged-rent step-ups** (checked with the yearly-increase rule).
3. **Lock-in rule** (mutual vs one-sided) and a transparent **red-flag phrase lexicon** (e.g. *"without recourse to the Court"*, *"double the daily amount"*).
4. **Form splitter** for the official `1) Title:` layout.
5. **Clause titles** come from the form's own headings (Period, Rent & Deposit, Possession …), which is more reliable than guessing the type.
6. **Fill-the-form panel** — you enter the rates, the notebook writes the agreement using the official clause wording, and analyses it.
""")
code('''
import re
from pune_rules import lockin_risk

# ---------- 6a. Official clause wording (Government of Maharashtra, IGR format) + common add-ons ----------
OFFICIAL = {
 "period": "That the Licensor hereby grants to the Licensee herein a revocable leave and license, to occupy the Licensed Premises, described in Schedule hereunder written without creating any tenancy rights or any other rights, title and interest in favour of the Licensee for a period of {months} Months.",
 "deposit_pay": "That the Licensee shall pay the above mentioned deposit to the Licensor by bank transfer on signing this agreement.",
 "maint_licensor": "That the all outgoings including all rates, taxes, levies, assessment, maintenance charges, non occupancy charges, etc. in respect of the said premises shall be paid by the Licensor.",
 "maint_licensee": "That the Licensee/s herein shall bear and pay all the maintenance charges in respect of the said Licensed Premises, and other outgoings including all rates, taxes, levies, assessment, non occupancy charges, etc. in respect of the said premises shall be paid by the Licensor/s.",
 "use": "That the Licensed premises shall only be used by the Licensee for residential purpose. The Licensee shall maintain the said premises in its existing condition and damage, if any, caused to the said premises, the same shall be repaired by the Licensee at its own cost subject to normal wear and tear. The Licensee shall not do anything in the said premises which is or is likely to cause a nuisance to the other occupants of the said building or to the prejudice in any manner to the rights of Licensor in respect of said premises or shall not do any unlawful activities prohibited by State or Central Government.",
 "alteration": "That the Licensee shall not make or permit to do any alteration or addition to the construction or arrangements (internal or external) to the Licensed premises without previous consent in writing from the Licensor.",
 "no_tenancy": "That the Licensee shall not claim any tenancy right and shall not have any right to transfer, assign, and sublet or grant any license or sub-license in respect of the Licensed Premises or any part thereof and also shall not mortgage or raise any loan against the said premises.",
 "inspection": "That, the Licensor shall on reasonable notice given by the Licensor to the Licensee shall have a right of access either by himself or through authorized representative to enter, view and inspect the Licensed premises at reasonable intervals.",
 "cancellation": "That, if the Licensee commits default in regular and punctual payments of monthly compensation as herein before mentioned or commit/s breach of any of the terms, covenants and conditions of this agreement or if any legislation prohibiting the Leave and License is imposed, the Licensor shall be entitled to revoke and / or cancel the License hereby granted, by giving notice in writing of one month and the Licensee too will have the right to vacate the said premises by giving a notice in writing of one month to the Licensor as mentioned earlier.",
 "possession": "That the immediately on the expiration or termination or cancellation of this agreement the Licensee shall vacate the said premises without delay with all his goods and belongings. In the event of the Licensee failing and / or neglecting to remove himself and / or his articles from the said premises on expiry or sooner determination of this Agreement, the Licensor shall be entitled to recover damages at the rate of double the daily amount of compensation per day and or alternatively the Licensor shall be entitled to remove the Licensee and his belongings from the Licensed premises, without recourse to the Court of Law.",
 "registration": "This Agreement is to be registered and the expenditure of Stamp duty and registration fees and incidental charges, if any, shall be borne by the Licensee.",
}

def indian(n):
    s = str(int(n))
    if len(s) <= 3: return s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])

def build_agreement(area_name, bhk, months, mode, rent, rent2, m1, dep, deptype, maint,
                    lock, lockwho, esc, fee, grace, refund):
    """Writes the agreement using the official clause wording + the values typed into the form."""
    dtxt = "nonrefundable" if deptype == "Non-refundable" else "refundable"
    if mode == "Staged rent":
        rent_clause = (f"That the Licensee shall pay to the Licensor the following amount per month towards the compensation for the use of the said licensed premises. "
                       f"a) Rs. {indian(rent)} per month for the first {m1} months, b) Rs. {indian(rent2)} per month for the next {max(months-m1,1)} months. "
                       f"The amount of monthly compensation shall be payable within first five days of the concerned month of Leave and License. "
                       f"Licensee shall also pay to the Licensor Rs. {indian(dep)} interest free {dtxt} deposit, for the use of the said licensed premises.")
    else:
        rent_clause = (f"That the Licensee shall pay to the Licensor Rs. {indian(rent)} per month towards the compensation and Rs. {indian(dep)} interest free {dtxt} deposit, "
                       f"for the use of the said licensed premises. The amount of monthly compensation shall be payable within first five days of the concerned month of Leave and License.")
    items = [("Period", OFFICIAL["period"].format(months=months)), ("Rent & Deposit", rent_clause),
             ("Payment of Deposit", OFFICIAL["deposit_pay"]),
             ("Maintenance Charges", OFFICIAL["maint_licensee" if maint == "licensee" else "maint_licensor"]),
             ("Use", OFFICIAL["use"]), ("Alteration", OFFICIAL["alteration"]), ("No Tenancy", OFFICIAL["no_tenancy"]),
             ("Inspection", OFFICIAL["inspection"]), ("Cancellation", OFFICIAL["cancellation"]),
             ("Possession", OFFICIAL["possession"]), ("Registration", OFFICIAL["registration"])]
    # ---- add-ons that brokers/owners commonly insert (NOT in the official format) ----
    if lock:  items.append(("Lock-in", f"That there shall be a lock-in period of {lock} months " + ("applicable to both the Licensor and the Licensee." if lockwho == "both" else "applicable only to the Licensee, while the Licensor may terminate at any time.")))
    if esc:   items.append(("Increase", f"That the monthly compensation shall be increased by {esc:g} percent on renewal of the agreement after every eleven months."))
    if fee:   items.append(("Late Fee", f"That a late fee of Rs. {fee} per day shall be charged if the monthly compensation is not paid " + (f"within {grace} days of the due date." if grace else "from the day after the due date, with no grace period.")))
    if refund: items.append(("Deposit Refund", f"That the Licensor shall refund the deposit within {refund} days of handover of the premises."))
    body = "\\n".join(f"{i}) {t}: {txt}" for i, (t, txt) in enumerate(items, 1))
    return ("LEAVE AND LICENSE AGREEMENT\\nThis agreement is made at Pune between the Licensor and the Licensee (names withheld).\\n\\n" + body +
            f"\\n\\nSchedule: residential {bhk} BHK unit situated at {area_name}, Pune.\\nIN WITNESS WHEREOF the parties have signed.")

print(build_agreement("Kothrud", 2, 11, "Fixed rent", 36000, 0, 6, 72000, "Refundable", "licensor", 6, "both", 5, 100, 7, 30)[:700], "...")
''')
md("### 6b. Engine v2 — money roles, composite Clause-2 check, lock-in rule, red-flag lexicon")
code('''
STAGE_RE = re.compile(r"Rs\\.?\\s*([\\d,]+)\\s*per month for the (?:first|next)\\s*(\\d+)\\s*months?", re.I)
RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}
worst = lambda risks: max(risks, key=RISK_RANK.get)

RED_FLAGS = [   # (regex, explanation)  -> High
 (r"without recourse to (the )?court", "Licensor may remove the licensee without going to court"),
 (r"double (the )?(daily )?(amount|rate|rent|compensation)", "Penalty of double the daily compensation"),
 (r"sole discretion", "Decision left entirely to the Licensor"),
 (r"without (any )?(prior )?notice", "Action allowed without notice"),
 (r"forfeit|remaining rent|balance rent", "Deposit forfeited / remaining rent claimed"),
 (r"non[\\s-]?refundable", "Amount cannot be recovered"),
]
AMBER_FLAGS = [  # -> Medium
 (r"licensee\\S* herein shall bear and pay all the maintenance", "Licensee pays all maintenance (Pune norm: Licensor pays society maintenance)"),
 (r"(stamp duty|registration fee).{0,80}borne by the licensee", "Registration costs placed on the Licensee"),
]

def classify_money(clause, s, e):
    """Is this Rs. amount a monthly rent or a deposit? Uses the words around it."""
    low = clause.lower(); before = low[max(0, s - 80):s]; after = low[e:e + 45]
    m = re.search(r"(rent|compensation|licen[cs]e fee|deposit)(?:\\s+(?:is|are|of|equal to|at|fixed at|fixed|shall be|will be|be))*\\s*:?\\s*$", before)
    if m: return "deposit" if m.group(1) == "deposit" else "rent"          # 1. cue right before the amount
    m = re.search(r"per month|monthly|a month|each month|every month|deposit", after)
    if m: return "deposit" if m.group() == "deposit" else "rent"           # 2. cue right after the amount
    last = None
    for mt in re.finditer(r"deposit|rent|compensation|licen[cs]e fee|monthly", before): last = mt.group()
    return None if last is None else ("deposit" if last == "deposit" else "rent")   # 3. nearest cue before

def rule_engine_v2(clause, ctx):
    """Returns (risk, reason, family, source) or (None, None, None, None)."""
    d, low = nlp(clause), clause.lower()
    ents  = [(e.label_, e.text, e.start_char, e.end_char) for e in d.ents]
    money = [(money_value(t), s, e) for l, t, s, e in ents if l == "MONEY_AMT"]
    pcts  = [first_number(t) for l, t, s, e in ents if l == "PERCENT_VAL"]
    days  = [duration_days(t) for l, t, s, e in ents if l == "DURATION" and "day" in t.lower()]
    mons  = [duration_days(t) / 30 for l, t, s, e in ents if l == "DURATION" and "month" in t.lower()]
    area  = next((AREA_ALIASES.get(t.lower()) for l, t, s, e in ents if l == "AREA"), None) or ctx.get("area")
    bhk   = next((int(first_number(t)) for l, t, s, e in ents if l == "BHK"), None) or ctx.get("bhk")

    # 1. late fee
    if money and re.search(r"\\blate\\b|delay|overdue|due date", low) and re.search(r"per day|a day|each day|daily", low):
        grace = days[0] if days else 0
        return latefee_risk(grace, money[0][0]), f"Late fee Rs.{money[0][0]}/day with {grace}-day grace (norm: modest fee after 5-7 days)", "penalty", "Pune rule"
    # 2. yearly increase
    if pcts and re.search(r"increas|revis|escalat|hike|raise|go up|goes up", low):
        return increase_risk(pcts[0]), f"Rent rises {pcts[0]:g}% per renewal (Low <=10%, Medium <=15%, High >15%)", "rent_increase", "Pune rule"
    # 3. rent / deposit (Clause 2 of the official format)
    if "deposit" in low or re.search(r"rent|compensation|licen[cs]e fee", low):
        parts, fam = [], set()
        if "deposit" in low and days and re.search(r"refund|return", low) and not money:
            return refund_risk(days[0]), f"Deposit refunded after {days[0]} days (Pune norm: 15-30 days)", "deposit", "Pune rule"
        roles = [(v, classify_money(clause, s, e)) for v, s, e in money]
        stages = [(money_value(a), int(b)) for a, b in STAGE_RE.findall(clause)]
        rents = [v for v, r in roles if r == "rent"]; deps = [v for v, r in roles if r == "deposit"]
        rent_ref = stages[0][0] if stages else (rents[0] if rents else ctx.get("rent"))
        if (stages or rents) and area and bhk in (1, 2, 3):
            lo, hi = RENT_RANGES[area][bhk]; fam.add("rent")
            for k, r in enumerate(([x[0] for x in stages] if stages else rents[:1]), 1):
                lab = f"Stage {k} " if stages else ""
                parts.append((rent_risk(area, bhk, r), f"{lab}rent Rs.{r:,} is Rs.{max(r-lo,0):,} above the start of the Pune {area.title()} {bhk} BHK range (Rs.{lo:,}-{hi:,}); Low up to +4,000, Medium up to +7,000"))
            if stages:
                for (r1, _), (r2, _) in zip(stages, stages[1:]):
                    if r1 and r2 > r1:
                        p = (r2 - r1) / r1 * 100; parts.append((increase_risk(p), f"Staged rent steps up {p:.1f}% (norm: <=10% Low, <=15% Medium)"))
            ctx["rent"] = rent_ref
        if deps:
            fam.add("deposit"); dep = deps[0]
            if rent_ref: parts.append((deposit_risk(dep, rent_ref), f"Deposit is {dep/rent_ref:.1f}x monthly rent (Low <=2x, Medium <=3x, High >3x)"))
            if re.search(r"non[\\s-]?refundable", low): parts.append(("High", "Deposit is NON-refundable - tenant cannot recover it"))
        if parts:
            family = "rent_and_deposit" if len(fam) == 2 else fam.pop()
            return worst([p[0] for p in parts]), " | ".join(p[1] for p in parts), family, "Pune rule"
    # 4. lock-in
    if re.search(r"lock-?in", low) and mons:
        one = bool(re.search(r"only to the licensee|licensee only|licensee alone|only for the licensee|applicable only", low))
        flag = next((why for pat, why in RED_FLAGS if re.search(pat, low)), None)
        if not flag:
            return lockin_risk(mons[0], one), f"Lock-in {mons[0]:g} months, {'one-sided (Licensee only)' if one else 'mutual'} (Low <=6, Medium <=11, High >11 or one-sided)", "lockin", "Pune rule"
    # 5. red-flag / amber phrase lexicon
    for pat, why in RED_FLAGS:
        if re.search(pat, low): return "High", "Red-flag phrase: " + why, None, "Red-flag lexicon"
    for pat, why in AMBER_FLAGS:
        if re.search(pat, low): return "Medium", "Amber phrase: " + why, None, "Red-flag lexicon"
    return None, None, None, None

def hybrid_predict_v2(clause, ctx, rmodel=None):
    rmodel = rmodel or risk_model
    clean = preprocess(clause); ctype = type_model.predict([clean])[0]
    risk, reason, family, source = rule_engine_v2(clause, ctx)
    if risk is not None: return (family or ctype), risk, source, reason
    risk = rmodel.predict([clean])[0]; words = top_words(clean, risk)
    if risk == "Low": return ctype, risk, "ML (wording)", "No risky terms found - standard wording"
    return ctype, risk, "ML (wording)", "Key phrases: " + (", ".join(words) if words else "overall wording pattern")
''')
md("### 📸 6c. Regression check — did the upgrade break anything? (same 52 unseen clauses as Step 5)")
code('''
v2 = [hybrid_predict_v2(c, {}) for c in test.clause_text]
test["v2_risk"] = [p[1] for p in v2]
chk = pd.DataFrame({"Subset": ["Wording-based", "Numeric", "All clauses"],
    "Step 5 hybrid": [acc(test[~test.numeric], "hy_risk"), acc(test[test.numeric], "hy_risk"), acc(test, "hy_risk")],
    "Step 6 engine v2": [acc(test[~test.numeric], "v2_risk"), acc(test[test.numeric], "v2_risk"), acc(test, "v2_risk")]}).round(3)
display(chk)
print("Macro-F1 (risk):  Step 5 =", round(f1_score(test.risk_level, test.hy_risk, average="macro"), 3),
      " | Step 6 =", round(f1_score(test.risk_level, test.v2_risk, average="macro"), 3))
''')
md("""
### 📸 6d. Check on the REAL wording of the official form
The 10 non-numeric clauses of the official Maharashtra format, labelled by me (Low / Medium / High). ⚠️ Honest caveat: I read this form while writing the red-flag lexicon, so this is a **development check, not an independent test**. The independent test is your **classmate-labelled / real clauses** (see the optional cell in Step 5). After measuring, the official clauses are added to training for the deployed model — the usual practice of training the final model on all labelled data.
""")
code('''
official_labelled = [
 (OFFICIAL["period"].format(months=11), "Low"),   (OFFICIAL["maint_licensor"], "Low"),
 (OFFICIAL["maint_licensee"], "Medium"),          (OFFICIAL["use"], "Low"),
 (OFFICIAL["alteration"], "Low"),                 (OFFICIAL["no_tenancy"], "Low"),
 (OFFICIAL["inspection"], "Low"),                 (OFFICIAL["cancellation"], "Low"),
 (OFFICIAL["possession"], "High"),                (OFFICIAL["registration"], "Medium")]
of = pd.DataFrame(official_labelled, columns=["clause_text", "risk_level"])
of["ml_only"]  = risk_model.predict(of.clause_text.apply(preprocess))
of["engine_v2"] = [hybrid_predict_v2(c, {})[1] for c in of.clause_text]
print(f"Official clauses (n={len(of)}):  ML-only accuracy = {accuracy_score(of.risk_level, of.ml_only):.2f} | "
      f"Engine v2 accuracy = {accuracy_score(of.risk_level, of.engine_v2):.2f}")
of_show = of.assign(clause=of.clause_text.str[:70] + "...")[["clause", "risk_level", "ml_only", "engine_v2"]]
of_show.columns = ["Clause", "My label", "ML only", "Engine v2"]; display(of_show)

# Deployed model = best wording model re-trained on wording clauses + the labelled official clauses
extra = pd.DataFrame([(v, r) for t, r in official_labelled for v in make_variants(t)], columns=["clause_text", "risk_level"])
wording = train[train.label_source == "hand"][["clause_text", "risk_level"]]
alld = pd.concat([wording, extra]); alld["clean"] = alld.clause_text.apply(preprocess)
final_risk_model = build(factories[best["risk_level"]]()).fit(alld.clean, alld.risk_level)
print("Deployed risk model re-trained on", len(alld), "clauses.")
''')
md("""
### 6e. Analyser for filled official forms
`split_official()` understands the official layout (`1) Title: text`) and drops the schedule and signature block. `analyse_official()` returns the colour-coded report, an overall score and **"not stated"** warnings for protections the official format lacks.
""")
code('''
def split_official(text):
    t = re.sub(r"(\\d)\\s*/-", r"\\1", text)                       # 36,000/-  -> 36,000
    t = re.split(r"\\n\\s*(?:Schedule:|IN WITNESS)", t)[0]          # drop schedule + signatures
    t = re.sub(r"LEAVE AND LICENSE AGREEMENT", " ", t)
    t = re.sub(r"Note:\\s*The clause \\d+ will depend on your selection", " ", t)
    out = []
    for p in re.split(r"(?m)^\\s*\\d+\\)\\s*", t)[1:]:
        p = re.sub(r"\\s+", " ", p).strip()
        p = re.sub(r"\\bOR\\b\\s*$", "", p).strip()
        hm = re.match(r"^([A-Za-z &/-]+):\\s*", p)                   # heading such as 'Rent & Deposit:'
        head = hm.group(1).strip() if hm else "Clause"
        if hm: p = p[hm.end():]
        if p: out.append((head, p))
    return out

CHECKS = [("Lock-in period", r"lock-?in", "Without it either side may be able to leave or evict at will"),
          ("Yearly rent increase", r"increas|escalat|revision", "Without a cap the rent can rise by any amount on renewal"),
          ("Late-fee terms", r"late (fee|charge|payment)", "No stated grace period or penalty limit"),
          ("Deposit refund timeline", r"refund[^.]{0,60}within|within[^.]{0,40}days[^.]{0,40}refund", "Official format has no refund deadline, so the deposit can be delayed"),
          ("Electricity / water terms", r"electricity|water charge|utilit", "Unclear who pays bills and at what rate")]

def analyse_official(text, area_key, bhk):
    clauses, ctx, rows = split_official(text), {"area": area_key, "bhk": bhk}, []
    for i, (head, c) in enumerate(clauses, 1):
        ctype, risk, src, why = hybrid_predict_v2(c, ctx, final_risk_model)
        rows.append((i, head, c[:95] + ("..." if len(c) > 95 else ""), risk, src, why))
    rep = pd.DataFrame(rows, columns=["#", "Clause title", "Text", "Risk", "Decided by", "Why"])
    score, _ = risk_score(rep.Risk)
    missing = [(n, w) for n, pat, w in CHECKS if not re.search(pat, text, re.I)]
    return rep, score, missing

LAST = {}          # remembers the last analysed agreement (used by the question-search in Step 7)

def show_analysis(text, area_key, bhk):
    rep, score, missing = analyse_official(text, area_key, bhk)
    LAST.update(rep=rep, clauses=[c for h, c in split_official(text)])
    _, level = risk_score(rep.Risk)
    display(rep.style.apply(lambda col: [COL[v] for v in col], subset=["Risk"])
            .set_properties(subset=["Text", "Why"], **{"text-align": "left", "white-space": "normal"}))
    print(f"\\nOVERALL RISK SCORE: {score}/100  ->  {level} RISK   |   High: {list(rep[rep.Risk=='High']['#'])}  Medium: {list(rep[rep.Risk=='Medium']['#'])}")
    poss = rep["Clause title"].eq("Possession") & rep.Risk.eq("High")
    if poss.any():
        s2, _ = risk_score(rep.Risk.where(~poss, "Low"))
        print(f"\\nNOTE: the 'Possession' clause is FIXED wording of the official Maharashtra format (double daily damages, removal without going to court). It is flagged High in every agreement built on that format and adds 15 points; the score would be {s2} without it. Ask the owner to amend it.")
    if missing:
        print("\\nNOT STATED in this agreement:")
        for n, w in missing: print(f"  - {n}: {w}")
    return rep, score
''')
md("### 📸 6f. Three scripted scenarios (fair / borderline / risky) — also your fallback if the live form misbehaves")
code('''
SCEN = {
 "A. Fair agreement":      dict(area_name="Kothrud", bhk=2, months=11, mode="Fixed rent", rent=29000, rent2=0, m1=6, dep=58000, deptype="Refundable", maint="licensor", lock=6, lockwho="both", esc=5, fee=100, grace=7, refund=30),
 "B. Borderline":          dict(area_name="Wakad", bhk=2, months=11, mode="Fixed rent", rent=31000, rent2=0, m1=6, dep=87000, deptype="Refundable", maint="licensee", lock=8, lockwho="both", esc=8, fee=200, grace=5, refund=45),
 "C. Risky agreement":     dict(area_name="Viman Nagar", bhk=2, months=11, mode="Fixed rent", rent=55000, rent2=0, m1=6, dep=330000, deptype="Non-refundable", maint="licensee", lock=11, lockwho="licensee", esc=20, fee=1000, grace=0, refund=0),
}
KEY = {"Kothrud": "kothrud", "Wakad": "wakad", "Viman Nagar": "viman nagar"}
summary = []
for name, p in SCEN.items():
    print("\\n" + "=" * 90 + f"\\n{name}  ({p['area_name']}, {p['bhk']} BHK)\\n" + "=" * 90)
    txt = build_agreement(**p); rep, score = show_analysis(txt, KEY[p["area_name"]], p["bhk"]); summary.append((name, score))
print("\\nSUMMARY:", summary)
''')
md("""
## 🎤 LIVE DEMO — fill the form
Fill only **rates and the terms the project checks** (no names, PAN, Aadhaar or signatures — the generated agreement uses *Licensor* and *Licensee* only). Then click **Analyse agreement**.
Leave an add-on at **0** to leave it *out* of the agreement — the system then lists it under *"NOT STATED"*.

**Two things to know before you present**
- **Rent rule:** the extra is counted from the **start (lowest rent)** of the Pune range for that area and BHK — up to Rs. 4,000 above the start is Low, up to Rs. 7,000 Medium, more is High. (Kothrud 2 BHK starts at Rs. 27,000, so Rs. 29,000 is Low, Rs. 33,000 Medium, Rs. 36,000 High.)
- **Possession is always High:** Clause 10 is *fixed wording of the government format* — double daily damages and removal without going to court. It is not an option on the form, so every agreement built on it carries this flag (the report prints the score *without* it). Treat it as a finding about the official form, not a bug.
""")
code('''
import ipywidgets as wd
from IPython.display import display as _d

sty, lay = {"description_width": "230px"}, wd.Layout(width="520px")
AREA_OPTS = [("Kothrud", "kothrud"), ("Hinjewadi Phase 1", "hinjewadi phase 1"), ("Hinjewadi Phase 2/3", "hinjewadi phase 2/3"),
             ("Sus Gaon", "sus gaon"), ("Wakad", "wakad"), ("Viman Nagar", "viman nagar"), ("Baner / Balewadi", "baner/balewadi"), ("Kharadi", "kharadi")]
F = dict(
 area  = wd.Dropdown(options=AREA_OPTS, description="Area", style=sty, layout=lay),
 bhk   = wd.Dropdown(options=[1, 2, 3], value=2, description="BHK", style=sty, layout=lay),
 months= wd.IntText(value=11, description="Period (months)", style=sty, layout=lay),
 rent  = wd.IntText(value=29000, description="Monthly rent Rs.", style=sty, layout=lay),
 staged= wd.Checkbox(value=False, description="Rent changes during the period (official staged-rent option)", indent=False, layout=wd.Layout(width="620px")),
 rent2 = wd.IntText(value=32000, description="Rent after the change Rs.", style=sty, layout=wd.Layout(width="520px", display="none")),
 m1    = wd.IntText(value=6, description="Months at the first rent", style=sty, layout=wd.Layout(width="520px", display="none")),
 dep   = wd.IntText(value=58000, description="Deposit Rs.", style=sty, layout=lay),
 deptype=wd.Dropdown(options=["Refundable", "Non-refundable"], description="Deposit type", style=sty, layout=lay),
 maint = wd.Dropdown(options=[("Licensor pays all outgoings", "licensor"), ("Licensee pays maintenance", "licensee")], description="Maintenance (Clause 4)", style=sty, layout=lay),
 lock  = wd.IntText(value=0, description="ADD-ON Lock-in months (0=none)", style=sty, layout=lay),
 lockwho=wd.Dropdown(options=[("Both parties", "both"), ("Licensee only", "licensee")], description="Lock-in applies to", style=sty, layout=lay),
 esc   = wd.FloatText(value=0, description="ADD-ON Yearly increase % (0=none)", style=sty, layout=lay),
 fee   = wd.IntText(value=0, description="ADD-ON Late fee Rs./day (0=none)", style=sty, layout=lay),
 grace = wd.IntText(value=7, description="Late-fee grace days", style=sty, layout=lay),
 refund= wd.IntText(value=0, description="ADD-ON Deposit refund within days (0=none)", style=sty, layout=lay))
btn, out = wd.Button(description="Analyse agreement", button_style="primary", layout=wd.Layout(width="250px", height="38px")), wd.Output()

def on_click(_):
    with out:
        out.clear_output(wait=True)
        v = {k: f.value for k, f in F.items()}
        area_name = dict((b, a) for a, b in AREA_OPTS)[v["area"]]
        txt = build_agreement(area_name, v["bhk"], v["months"], ("Staged rent" if v["staged"] else "Fixed rent"), v["rent"], v["rent2"], v["m1"], v["dep"], v["deptype"],
                              v["maint"], v["lock"], v["lockwho"], v["esc"], v["fee"], v["grace"], v["refund"])
        print("GENERATED AGREEMENT (official clause wording)\\n" + "-" * 60); print(txt, "\\n")
        show_analysis(txt, v["area"], v["bhk"])
def _toggle_staged(change):
    for k in ("rent2", "m1"): F[k].layout.display = "" if F["staged"].value else "none"
F["staged"].observe(_toggle_staged, names="value")
btn.on_click(on_click)
_d(wd.VBox(list(F.values()) + [btn, out]))
''')
md("""
### Or paste a filled form
If you fill the official PDF text yourself, paste it below (delete the unused "OR" alternatives first), set the area and BHK, and run.
""")
code('''
pasted = """
LEAVE AND LICENSE AGREEMENT
1) Period: That the Licensor hereby grants to the Licensee a revocable leave and license for a period of 11 Months.
2) Rent & Deposit: That the Licensee shall pay to the Licensor Rs. 26,000 per month towards the compensation and Rs. 78,000 interest free refundable deposit, for the use of the said licensed premises.
3) Maintenance Charges: That the Licensee/s herein shall bear and pay all the maintenance charges in respect of the said Licensed Premises.
Schedule: ...
"""
show_analysis(pasted, "hinjewadi phase 2/3", 2);
''')
