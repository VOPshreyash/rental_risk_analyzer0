"""
engine.py — NLP engine for Rental Agreement Risk Analyzer
Loads and trains all models at import time; exposes analyze_form() and analyze_text().
"""
import os, re, sys
import pandas as pd
import numpy as np

# ── make scripts/ importable ─────────────────────────────────────────────────
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# ── NLTK setup ────────────────────────────────────────────────────────────────
import nltk
for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet"]:
    nltk.download(pkg, quiet=True)

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# ── spaCy setup ───────────────────────────────────────────────────────────────
import spacy

nlp = spacy.load("en_core_web_sm")
ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})

UNITS = ["day", "days", "month", "months", "year", "years"]
_ner_patterns = [
    {"label": "MONEY_AMT",   "pattern": [{"LOWER": {"REGEX": r"^(rs\.?|inr|₹)$"}}, {"ORTH": ".", "OP": "?"}, {"LIKE_NUM": True}]},
    {"label": "PERCENT_VAL", "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["percent", "%"]}}]},
    {"label": "DURATION",    "pattern": [{"LIKE_NUM": True, "LOWER": {"NOT_IN": ["first","second","third","fourth","fifth","next"]}, "OP": "+"}, {"LOWER": {"IN": UNITS}}]},
    {"label": "BHK",         "pattern": [{"LIKE_NUM": True}, {"LOWER": "bhk"}]},
    {"label": "BHK",         "pattern": [{"LOWER": {"REGEX": r"^\d+bhk$"}}]},
    {"label": "PARTY",       "pattern": [{"LOWER": {"IN": ["landlord","tenant","licensor","licensee"]}}]},
]
for area in ["kothrud","wakad","kharadi","baner","balewadi","hinjewadi","viman nagar","sus gaon"]:
    _ner_patterns.append({"label": "AREA", "pattern": [{"LOWER": w} for w in area.split()]})
_ner_patterns.append({"label": "AREA", "pattern": [{"LOWER": "hinjewadi"}, {"LOWER": "phase"}, {"LIKE_NUM": True}]})
ruler.add_patterns(_ner_patterns)

# ── Import rules ──────────────────────────────────────────────────────────────
from pune_rules import (
    RENT_RANGES, AREA_ALIASES,
    rent_risk, deposit_risk, increase_risk, refund_risk, latefee_risk, lockin_risk
)

# ── Preprocessing ─────────────────────────────────────────────────────────────
KEEP = {"no", "not", "nor", "never", "without", "before", "after", "only", "against"}
STOP = set(stopwords.words("english")) - KEEP
lemmatizer = WordNetLemmatizer()

def preprocess(text: str) -> str:
    t = text.lower()
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)
    t = re.sub(r"(rs\.?|inr|₹)\s*[\d,]+(\.\d+)?", " moneyamt ", t)
    t = re.sub(r"\d+(\.\d+)?\s*(percent|%)", " percentval ", t)
    t = re.sub(r"\b\d+\b", " numval ", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    tokens = word_tokenize(t)
    tokens = [w for w in tokens if w not in STOP and len(w) > 1]
    tokens = [lemmatizer.lemmatize(w, pos="v") for w in tokens]
    tokens = [lemmatizer.lemmatize(w, pos="n") for w in tokens]
    return " ".join(tokens)

# ── Value parsers ─────────────────────────────────────────────────────────────
WORDS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
         "eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,
         "fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,
         "nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,
         "sixty":60,"seventy":70,"eighty":80,"ninety":90}

def words_to_number(s):
    s = s.lower().replace("-"," ").strip()
    if re.fullmatch(r"[\d,.]+", s): return float(s.replace(",",""))
    toks = [WORDS[w] for w in s.split() if w in WORDS]
    return float(sum(toks)) if toks else None

def first_number(s):
    m = re.search(r"\d+(\.\d+)?", s)
    if m: return float(m.group())
    return words_to_number(re.sub(r"[^a-z\s-]","",s.lower()).split()[0]) if s.strip() else None

def money_value(s):
    m = re.search(r"[\d,]+(\.\d+)?", s)
    return int(float(m.group().replace(",",""))) if m else None

def duration_days(s):
    m = re.match(r"(.+?)\s*(days?|months?|years?)$", s.strip().lower())
    if not m: return 0
    n = words_to_number(m.group(1)); u = m.group(2)
    if n is None: return 0
    return int(n * (1 if u.startswith("day") else 30 if u.startswith("month") else 365))

# ── Clause splitter ───────────────────────────────────────────────────────────
ABBR = ["Rs.", "Mr.", "Ms.", "Mrs.", "Dr.", "No.", "approx.", "i.e.", "e.g."]

from nltk.tokenize import sent_tokenize

def split_clauses(text):
    parts = re.split(r"(?m)^\s*\d+[.)]\s+", text)
    header, clauses = parts[0].strip(), [p.strip() for p in parts[1:] if p.strip()]
    if clauses:
        return header, clauses
    t = text
    for a in ABBR:
        t = t.replace(a, a.replace(".", "<DOT>"))
    sents = [s.replace("<DOT>", ".").strip() for s in sent_tokenize(t)]
    return "", sents

def split_official(text):
    t = re.sub(r"(\d)\s*/-", r"\1", text)
    t = re.split(r"\n\s*(?:Schedule:|IN WITNESS)", t)[0]
    t = re.sub(r"LEAVE AND LICENSE AGREEMENT", " ", t)
    t = re.sub(r"Note:\s*The clause \d+ will depend on your selection", " ", t)
    out = []
    for p in re.split(r"(?m)^\s*\d+\)\s*", t)[1:]:
        p = re.sub(r"\s+", " ", p).strip()
        p = re.sub(r"\bOR\b\s*$", "", p).strip()
        hm = re.match(r"^([A-Za-z &/-]+):\s*", p)
        head = hm.group(1).strip() if hm else "Clause"
        if hm: p = p[hm.end():]
        if p: out.append((head, p))
    return out

# ── ML model training ─────────────────────────────────────────────────────────
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

def _build(model):
    return Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)), ("clf", model)])

def make_variants(t):
    v1 = t.replace("Tenant","Licensee").replace("Landlord","Licensor")
    v2 = t.replace("shall","will").replace("Rs. ","₹")
    v3 = t.replace("Tenant","Lessee").replace("Landlord","Owner").replace(" percent","%").replace("Rs. ","INR ")
    return list(dict.fromkeys([t, v1, v2, v3]))

print("🔧 Loading dataset and training models...")
_base = pd.read_csv(os.path.join(SCRIPTS_DIR, "clauses.csv"))
_base["group"] = range(len(_base))
_rows = [(v, r.clause_type, r.risk_level, r.group, r.label_source)
         for r in _base.itertuples() for v in make_variants(r.clause_text)]
_train = pd.DataFrame(_rows, columns=["clause_text","clause_type","risk_level","group","label_source"])
_train["clean"] = _train.clause_text.apply(preprocess)

type_model = _build(LogisticRegression(max_iter=3000, C=10)).fit(_train.clean, _train.clause_type)
_wording   = _train[_train.label_source == "hand"]
risk_model = _build(MultinomialNB(alpha=0.3)).fit(_wording.clean, _wording.risk_level)
lr_risk    = _build(LogisticRegression(max_iter=3000, C=10)).fit(_wording.clean, _wording.risk_level)
print("✅ Models ready.")

def top_words(clean, label, n=3):
    try:
        vec, clf = lr_risk.named_steps["tfidf"], lr_risk.named_steps["clf"]
        idx = list(clf.classes_).index(label)
        contrib = vec.transform([clean]).multiply(clf.coef_[idx]).toarray()[0]
        names = vec.get_feature_names_out()
        return [names[i] for i in contrib.argsort()[::-1][:n] if contrib[i] > 0]
    except Exception:
        return []

# ── Red-flag lexicon ──────────────────────────────────────────────────────────
STAGE_RE = re.compile(r"Rs\.?\s*([\d,]+)\s*per month for the (?:first|next)\s*(\d+)\s*months?", re.I)
RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}
worst = lambda risks: max(risks, key=RISK_RANK.get)

RED_FLAGS = [
    (r"without recourse to (the )?court", "Licensor may remove the licensee without going to court"),
    (r"double (the )?(daily )?(amount|rate|rent|compensation)", "Penalty of double the daily compensation"),
    (r"sole discretion", "Decision left entirely to the Licensor"),
    (r"without (any )?(prior )?notice", "Action allowed without notice"),
    (r"forfeit|remaining rent|balance rent", "Deposit forfeited / remaining rent claimed"),
    (r"non[\s-]?refundable", "Amount cannot be recovered"),
]
AMBER_FLAGS = [
    (r"licensee\S* herein shall bear and pay all the maintenance", "Licensee pays all maintenance (Pune norm: Licensor pays society maintenance)"),
    (r"(stamp duty|registration fee).{0,80}borne by the licensee", "Registration costs placed on the Licensee"),
]

NOT_STATED_CHECKS = [
    ("Lock-in period",          r"lock-?in",                            "Without it either side may be able to leave or evict at will"),
    ("Yearly rent increase",    r"increas|escalat|revision",            "Without a cap the rent can rise by any amount on renewal"),
    ("Late-fee terms",          r"late (fee|charge|payment)",           "No stated grace period or penalty limit"),
    ("Deposit refund timeline", r"refund[^.]{0,60}within|within[^.]{0,40}days[^.]{0,40}refund", "Official format has no refund deadline, so the deposit can be delayed"),
    ("Electricity / water terms", r"electricity|water charge|utilit",   "Unclear who pays bills and at what rate"),
]

def classify_money(clause, s, e):
    low = clause.lower(); before = low[max(0,s-80):s]; after = low[e:e+45]
    m = re.search(r"(rent|compensation|licen[cs]e fee|deposit)(?:\s+(?:is|are|of|equal to|at|fixed at|fixed|shall be|will be|be))*\s*:?\s*$", before)
    if m: return "deposit" if m.group(1) == "deposit" else "rent"
    m = re.search(r"per month|monthly|a month|each month|every month|deposit", after)
    if m: return "deposit" if m.group() == "deposit" else "rent"
    last = None
    for mt in re.finditer(r"deposit|rent|compensation|licen[cs]e fee|monthly", before): last = mt.group()
    return None if last is None else ("deposit" if last == "deposit" else "rent")

def rule_engine_v2(clause, ctx):
    d, low = nlp(clause), clause.lower()
    ents   = [(e.label_, e.text, e.start_char, e.end_char) for e in d.ents]
    money  = [(money_value(t), s, e) for l,t,s,e in ents if l == "MONEY_AMT"]
    pcts   = [first_number(t) for l,t,s,e in ents if l == "PERCENT_VAL"]
    days   = [duration_days(t) for l,t,s,e in ents if l == "DURATION" and "day" in t.lower()]
    mons   = [duration_days(t)/30 for l,t,s,e in ents if l == "DURATION" and "month" in t.lower()]
    area   = next((AREA_ALIASES.get(t.lower()) for l,t,s,e in ents if l == "AREA"), None) or ctx.get("area")
    bhk    = next((int(first_number(t)) for l,t,s,e in ents if l == "BHK"), None) or ctx.get("bhk")

    # 1. late fee
    if money and re.search(r"\blate\b|delay|overdue|due date", low) and re.search(r"per day|a day|each day|daily", low):
        grace = days[0] if days else 0
        return latefee_risk(grace, money[0][0]), f"Late fee Rs.{money[0][0]}/day with {grace}-day grace (norm: modest fee after 5-7 days)", "penalty", "Pune rule"
    # 2. yearly increase
    if pcts and re.search(r"increas|revis|escalat|hike|raise|go up|goes up", low):
        return increase_risk(pcts[0]), f"Rent rises {pcts[0]:g}% per renewal (Low <=10%, Medium <=15%, High >15%)", "rent_increase", "Pune rule"
    # 3. rent / deposit
    if "deposit" in low or re.search(r"rent|compensation|licen[cs]e fee", low):
        parts, fam = [], set()
        if "deposit" in low and days and re.search(r"refund|return", low) and not money:
            return refund_risk(days[0]), f"Deposit refunded after {days[0]} days (Pune norm: 15-30 days)", "deposit", "Pune rule"
        roles  = [(v, classify_money(clause, s, e)) for v,s,e in money]
        stages = [(money_value(a), int(b)) for a,b in STAGE_RE.findall(clause)]
        rents  = [v for v,r in roles if r == "rent"]; deps = [v for v,r in roles if r == "deposit"]
        rent_ref = stages[0][0] if stages else (rents[0] if rents else ctx.get("rent"))
        if (stages or rents) and area and bhk in (1,2,3):
            lo, hi = RENT_RANGES[area][bhk]; fam.add("rent")
            for k, r in enumerate(([x[0] for x in stages] if stages else rents[:1]), 1):
                lab = f"Stage {k} " if stages else ""
                parts.append((rent_risk(area, bhk, r),
                               f"{lab}rent Rs.{r:,} is Rs.{max(r-lo,0):,} above the start of the Pune {area.title()} {bhk} BHK range (Rs.{lo:,}-{hi:,}); Low up to +4,000, Medium up to +7,000"))
            if stages:
                for (r1,_),(r2,_) in zip(stages, stages[1:]):
                    if r1 and r2 > r1:
                        p = (r2-r1)/r1*100; parts.append((increase_risk(p), f"Staged rent steps up {p:.1f}% (norm: <=10% Low, <=15% Medium)"))
            ctx["rent"] = rent_ref
        if deps:
            fam.add("deposit"); dep = deps[0]
            if rent_ref: parts.append((deposit_risk(dep, rent_ref), f"Deposit is {dep/rent_ref:.1f}x monthly rent (Low <=2x, Medium <=3x, High >3x)"))
            if re.search(r"non[\s-]?refundable", low): parts.append(("High", "Deposit is NON-refundable - tenant cannot recover it"))
        if parts:
            family = "rent_and_deposit" if len(fam) == 2 else (fam.pop() if fam else "deposit")
            return worst([p[0] for p in parts]), " | ".join(p[1] for p in parts), family, "Pune rule"
    # 4. lock-in
    if re.search(r"lock-?in", low) and mons:
        one = bool(re.search(r"only to the licensee|licensee only|licensee alone|only for the licensee|applicable only", low))
        for pat, why in RED_FLAGS:
            if re.search(pat, low): return "High", "Red-flag phrase: " + why, "lockin", "Red-flag lexicon"
        return lockin_risk(mons[0], one), f"Lock-in {mons[0]:g} months, {'one-sided (Licensee only)' if one else 'mutual'} (Low <=6, Medium <=11, High >11 or one-sided)", "lockin", "Pune rule"
    # 5. red-flag / amber lexicon
    for pat, why in RED_FLAGS:
        if re.search(pat, low): return "High", "Red-flag phrase: " + why, None, "Red-flag lexicon"
    for pat, why in AMBER_FLAGS:
        if re.search(pat, low): return "Medium", "Amber phrase: " + why, None, "Red-flag lexicon"
    return None, None, None, None

def hybrid_predict(clause, ctx):
    clean = preprocess(clause)
    ctype = type_model.predict([clean])[0]
    risk, reason, family, source = rule_engine_v2(clause, ctx)
    if risk is not None:
        return (family or ctype), risk, source, reason
    risk = risk_model.predict([clean])[0]
    words = top_words(clean, risk)
    if risk == "Low":
        return ctype, risk, "ML (wording)", "No risky terms found - standard wording"
    return ctype, risk, "ML (wording)", "Key phrases: " + (", ".join(words) if words else "overall wording pattern")

def risk_score(risks):
    score = min(100, sum(15 if r == "High" else 7 if r == "Medium" else 0 for r in risks))
    return score, ("LOW" if score < 25 else "MODERATE" if score < 60 else "HIGH")

# ── Official agreement builder ────────────────────────────────────────────────
def _indian(n):
    s = str(int(n))
    if len(s) <= 3: return s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])

OFFICIAL = {
    "period": "That the Licensor hereby grants to the Licensee herein a revocable leave and license, to occupy the Licensed Premises, described in Schedule hereunder written without creating any tenancy rights or any other rights, title and interest in favour of the Licensee for a period of {months} Months.",
    "deposit_pay": "That the Licensee shall pay the above mentioned deposit to the Licensor by bank transfer on signing this agreement.",
    "maint_licensor": "That the all outgoings including all rates, taxes, levies, assessment, maintenance charges, non occupancy charges, etc. in respect of the said premises shall be paid by the Licensor.",
    "maint_licensee": "That the Licensee/s herein shall bear and pay all the maintenance charges in respect of the said Licensed Premises, and other outgoings including all rates, taxes, levies, assessment, non occupancy charges, etc. in respect of the said premises shall be paid by the Licensor/s.",
    "use": "That the Licensed premises shall only be used by the Licensee for residential purpose. The Licensee shall maintain the said premises in its existing condition and damage, if any, caused to the said premises, the same shall be repaired by the Licensee at its own cost subject to normal wear and tear.",
    "alteration": "That the Licensee shall not make or permit to do any alteration or addition to the construction or arrangements (internal or external) to the Licensed premises without previous consent in writing from the Licensor.",
    "no_tenancy": "That the Licensee shall not claim any tenancy right and shall not have any right to transfer, assign, and sublet or grant any license or sub-license in respect of the Licensed Premises or any part thereof.",
    "inspection": "That, the Licensor shall on reasonable notice given by the Licensor to the Licensee shall have a right of access either by himself or through authorized representative to enter, view and inspect the Licensed premises at reasonable intervals.",
    "cancellation": "That, if the Licensee commits default in regular and punctual payments of monthly compensation as herein before mentioned or commit/s breach of any of the terms, covenants and conditions of this agreement, the Licensor shall be entitled to revoke and / or cancel the License hereby granted, by giving notice in writing of one month and the Licensee too will have the right to vacate the said premises by giving a notice in writing of one month to the Licensor.",
    "possession": "That the immediately on the expiration or termination or cancellation of this agreement the Licensee shall vacate the said premises without delay with all his goods and belongings. In the event of the Licensee failing and / or neglecting to remove himself and / or his articles from the said premises on expiry or sooner determination of this Agreement, the Licensor shall be entitled to recover damages at the rate of double the daily amount of compensation per day and or alternatively the Licensor shall be entitled to remove the Licensee and his belongings from the Licensed premises, without recourse to the Court of Law.",
    "registration": "This Agreement is to be registered and the expenditure of Stamp duty and registration fees and incidental charges, if any, shall be borne by the Licensee.",
}

def build_agreement(area_name, bhk, months, mode, rent, rent2, m1, dep, deptype, maint,
                    lock, lockwho, esc, fee, grace, refund):
    dtxt = "nonrefundable" if deptype == "Non-refundable" else "refundable"
    if mode == "Staged rent":
        rent_clause = (f"That the Licensee shall pay to the Licensor the following amount per month towards the compensation. "
                       f"a) Rs. {_indian(rent)} per month for the first {m1} months, b) Rs. {_indian(rent2)} per month for the next {max(months-m1,1)} months. "
                       f"The amount of monthly compensation shall be payable within first five days of the concerned month of Leave and License. "
                       f"Licensee shall also pay to the Licensor Rs. {_indian(dep)} interest free {dtxt} deposit.")
    else:
        rent_clause = (f"That the Licensee shall pay to the Licensor Rs. {_indian(rent)} per month towards the compensation and Rs. {_indian(dep)} interest free {dtxt} deposit, "
                       f"for the use of the said licensed premises. The amount of monthly compensation shall be payable within first five days of the concerned month of Leave and License.")
    items = [
        ("Period",              OFFICIAL["period"].format(months=months)),
        ("Rent & Deposit",      rent_clause),
        ("Payment of Deposit",  OFFICIAL["deposit_pay"]),
        ("Maintenance Charges", OFFICIAL["maint_licensee" if maint == "licensee" else "maint_licensor"]),
        ("Use",                 OFFICIAL["use"]),
        ("Alteration",          OFFICIAL["alteration"]),
        ("No Tenancy",          OFFICIAL["no_tenancy"]),
        ("Inspection",          OFFICIAL["inspection"]),
        ("Cancellation",        OFFICIAL["cancellation"]),
        ("Possession",          OFFICIAL["possession"]),
        ("Registration",        OFFICIAL["registration"]),
    ]
    if lock:
        items.append(("Lock-in", f"That there shall be a lock-in period of {lock} months " +
                      ("applicable to both the Licensor and the Licensee." if lockwho == "both"
                       else "applicable only to the Licensee, while the Licensor may terminate at any time.")))
    if esc:
        items.append(("Increase", f"That the monthly compensation shall be increased by {esc:g} percent on renewal of the agreement after every eleven months."))
    if fee:
        items.append(("Late Fee", f"That a late fee of Rs. {fee} per day shall be charged if the monthly compensation is not paid " +
                      (f"within {grace} days of the due date." if grace else "from the day after the due date, with no grace period.")))
    if refund:
        items.append(("Deposit Refund", f"That the Licensor shall refund the deposit within {refund} days of handover of the premises."))
    body = "\n".join(f"{i}) {t}: {txt}" for i,(t,txt) in enumerate(items, 1))
    return ("LEAVE AND LICENSE AGREEMENT\nThis agreement is made at Pune between the Licensor and the Licensee (names withheld).\n\n"
            + body + f"\n\nSchedule: residential {bhk} BHK unit situated at {area_name}, Pune.\nIN WITNESS WHEREOF the parties have signed.")

# ── Main analysis function ────────────────────────────────────────────────────
def _analyse(text: str, area_key: str, bhk: int) -> dict:
    clauses = split_official(text)
    ctx, rows = {"area": area_key, "bhk": bhk}, []
    for i, (head, c) in enumerate(clauses, 1):
        ctype, risk, src, why = hybrid_predict(c, ctx)
        rows.append({"num": i, "title": head,
                     "text": c[:200] + ("..." if len(c) > 200 else ""),
                     "full_text": c,
                     "risk": risk, "decided_by": src, "why": why})
    score, level = risk_score([r["risk"] for r in rows])
    # NOT STATED checks
    not_stated = []
    for name, pat, warning in NOT_STATED_CHECKS:
        if not re.search(pat, text, re.I):
            not_stated.append({"name": name, "warning": warning})
    # Possession note
    possession_note = None
    poss_rows = [r for r in rows if r["title"] == "Possession" and r["risk"] == "High"]
    if poss_rows:
        risks_without = [("Low" if r["title"] == "Possession" else r["risk"]) for r in rows]
        s2, _ = risk_score(risks_without)
        possession_note = f"Score without the fixed Possession clause: {s2}/100"
    return {"score": score, "level": level, "clauses": rows,
            "not_stated": not_stated, "possession_note": possession_note}

def analyze_form(params: dict) -> dict:
    area_name_map = {
        "kothrud": "Kothrud", "hinjewadi phase 1": "Hinjewadi Phase 1",
        "hinjewadi phase 2/3": "Hinjewadi Phase 2/3", "sus gaon": "Sus Gaon",
        "wakad": "Wakad", "viman nagar": "Viman Nagar",
        "baner/balewadi": "Baner/Balewadi", "kharadi": "Kharadi"
    }
    area_key  = params["area"]
    area_name = area_name_map.get(area_key, area_key.title())
    text = build_agreement(
        area_name, params["bhk"], params["months"],
        params.get("mode", "Fixed rent"),
        params["rent"], params.get("rent2", 0), params.get("m1", 6),
        params["dep"], params.get("deptype", "Refundable"),
        params.get("maint", "licensor"),
        params.get("lock", 0), params.get("lockwho", "both"),
        params.get("esc", 0), params.get("fee", 0),
        params.get("grace", 7), params.get("refund", 0)
    )
    result = _analyse(text, area_key, params["bhk"])
    result["generated_agreement"] = text
    return result

def analyze_text(text: str, area_key: str, bhk: int) -> dict:
    return _analyse(text, area_key, bhk)
