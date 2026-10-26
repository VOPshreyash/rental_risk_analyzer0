# ============================ STEP 4
md("""
## STEP 4 — Vectorization & Classification  *(Practical 3/4 → TF-IDF + ML models)*

**Goal:** teach a model to predict, for each clause, (a) its **type** (deposit, lock-in, eviction …) and (b) its **risk level** (Low / Medium / High).

**What happens here**
1. **Data augmentation** – each clause is rewritten in 3 other styles (*Licensee/Licensor*, *Lessee/Owner*, `₹` / `INR`, `%`) so the model sees varied wording. These are **synthetic**, and we say so in the report.
2. **TF-IDF with 1–2-word n-grams** – turns text into numbers. n-grams matter: *"without notice"* means something different from *"notice"* alone.
3. **Three models compared** – Naive Bayes, Logistic Regression, Linear SVM (+ a *dummy* baseline that always guesses the commonest class).
4. **Leak-proof evaluation** – `GroupKFold`: all rewrites of one clause stay in the *same* fold. Without this, the model would be tested on rewrites of clauses it already trained on and the score would be fake.
5. **A separate unseen test set** – 52 clauses written in *new wording* that never appear in training.
""")
code("""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GroupKFold, cross_validate
from sklearn.metrics import accuracy_score, f1_score, classification_report, ConfusionMatrixDisplay

# ---------- 4a. Training data = base clauses + 3 rewrites each ----------
base = pd.read_csv("clauses.csv"); base["group"] = range(len(base))

def make_variants(t):
    v1 = t.replace("Tenant", "Licensee").replace("Landlord", "Licensor")
    v2 = t.replace("shall", "will").replace("Rs. ", "₹")
    v3 = (t.replace("Tenant", "Lessee").replace("Landlord", "Owner")
            .replace(" percent", "%").replace("Rs. ", "INR "))
    return list(dict.fromkeys([t, v1, v2, v3]))          # unique, order kept

rows = [(v, r.clause_type, r.risk_level, r.group, r.label_source) for r in base.itertuples() for v in make_variants(r.clause_text)]
train = pd.DataFrame(rows, columns=["clause_text", "clause_type", "risk_level", "group", "label_source"])
train["clean_text"] = train.clause_text.apply(preprocess)
print(f"Base clauses: {len(base)}  →  training rows after augmentation: {len(train)}")
print("Wording-based (hand-labelled) rows used to train the RISK model:", (train.label_source == "hand").sum())
display(train.sample(5, random_state=3)[["clause_text", "clause_type", "risk_level"]])
""")
md("### Unseen test set (new wording, never used for training)\nNumeric clauses are labelled by the Pune rules; the rest are hand-labelled. ⚠️ I (the author) wrote and labelled these — in the report, call it a *held-out test set*, and also add real clauses in the optional cell further below.")
code("""
test_rows = []          # (text, type, risk, is_numeric)
def T(text, ctype, risk, numeric=False): test_rows.append((text, ctype, risk, numeric))

# ---- numeric clauses: risk label computed from Pune rules ----
for text, key, bhk, rent in [
    ("Licence fee for the 2BHK apartment at Wakad is fixed at ₹29,500 per month.", "wakad", 2, 29500),
    ("The Licensee shall pay INR 41,000 each month as rent for the 2 BHK unit in Kothrud.", "kothrud", 2, 41000),
    ("Monthly licence fee for the 1 BHK flat in Viman Nagar: Rs. 27,000.", "viman nagar", 1, 27000),
    ("The rent payable for the 3 BHK flat in Baner shall be ₹82,000 per month.", "baner/balewadi", 3, 82000),
    ("The Licensee agrees to a monthly rent of Rs. 26,000 for a 2 BHK in Sus Gaon.", "sus gaon", 2, 26000),
    ("The flat in Kharadi (1 BHK) shall be let at a rent of Rs. 36,000 per month.", "kharadi", 1, 36000)]:
    T(text, "rent", rent_risk(key, bhk, rent), True)

for text, rent, dep in [
    ("Against a monthly rent of Rs. 30,000, the Licensee shall deposit Rs. 60,000 as interest free refundable security.", 30000, 60000),
    ("The security deposit is Rs. 1,05,000, while the monthly rent is Rs. 35,000.", 35000, 105000),
    ("Interest-free security deposit of ₹2,50,000 shall be paid by the Licensee; the rent is ₹40,000 per month.", 40000, 250000),
    ("Licensee to pay deposit equal to Rs. 45,000 on a rent of Rs. 30,000.", 30000, 45000)]:
    T(text, "deposit", deposit_risk(dep, rent), True)

T("The Licensor shall return the deposit within 20 days after the Licensee hands over the keys.", "deposit", refund_risk(20), True)
T("Refund of the deposit will be made within ninety days from vacating the flat.", "deposit", refund_risk(90), True)

for text, p in [("Annual revision in rent shall not exceed 5%.", 5),
                ("At renewal, the licence fee will go up by ten percent.", 10),
                ("A hike of 12% in the monthly rent applies on every renewal.", 12),
                ("Rent escalation of 15 percent per annum shall apply.", 15),
                ("The Licensor may raise the rent by 20% every year.", 20),
                ("Every year the rent shall be increased by thirty percent.", 30)]:
    T(text, "rent_increase", increase_risk(p), True)

for text, grace, fee in [
    ("If rent is not received within 6 days of the due date, Rs. 150 per day is charged.", 6, 150),
    ("Delay in rent beyond 3 days attracts a fine of ₹300 per day.", 3, 300),
    ("A late charge of Rs. 1,000 per day applies immediately after the due date, no grace is given.", 0, 1000),
    ("Late payment fee is Rs. 200 per day after a grace period of five days.", 5, 200)]:
    T(text, "penalty", latefee_risk(grace, fee), True)

# ---- wording-based clauses: hand-labelled ----
for text, ctype, risk in [
 ("The Licensor can keep any part of the security deposit as he pleases, without showing bills.", "deposit", "High"),
 ("Deductions from the deposit, if any, will be supported by receipts of actual repair costs.", "deposit", "Low"),
 ("The deposit will be forfeited in full if the Licensee gives notice before the end of the agreement period.", "deposit", "High"),
 ("A fine will be levied on the Licensee whenever the Licensor feels a rule has been broken.", "penalty", "High"),
 ("If the Licensee is late with rent, no charge will apply for the first week.", "penalty", "Low"),
 ("Using the parking slot of another resident will attract a fixed fine of three months' rent.", "penalty", "High"),
 ("Neither party can end the agreement in the first four months; after that one month's notice is enough.", "lockin", "Low"),
 ("The Licensee is bound to stay for the whole eleven months and must pay all remaining rent if he leaves early.", "lockin", "High"),
 ("A ten month commitment applies to the Licensee alone; the Licensor is free to end the arrangement whenever he wants.", "lockin", "High"),
 ("Both parties agree to a minimum stay of six months, with a penalty of one month's rent for leaving early.", "lockin", "Low"),
 ("After the first seven months, either side may leave by giving thirty days' written notice.", "lockin", "Low"),
 ("The Licensee may leave early only if the Licensor agrees, and the Licensor can refuse without any reason.", "lockin", "Medium"),
 ("The Licensor shall give ninety days' written notice before asking the Licensee to vacate for any reason other than breach.", "eviction", "Low"),
 ("The Licensor may throw out the Licensee at once if rent is late, with no chance to pay.", "eviction", "High"),
 ("Termination by the Licensor needs a written notice of one month and a valid reason.", "eviction", "Low"),
 ("The Licensee must hand over the flat within two days of the Licensor's oral instruction.", "eviction", "High"),
 ("If the owner wants the flat for family use, the Licensee shall be given twenty days' notice.", "eviction", "Medium"),
 ("On repeated non-payment, the Licensor may end the licence after giving a fortnight's notice.", "eviction", "Medium"),
 ("Society dues, including sinking fund and corpus contributions, will be borne by the owner.", "maintenance", "Low"),
 ("All repair work, big or small, is the responsibility of the Licensee.", "maintenance", "High"),
 ("The Licensee pays for painting of the flat when leaving, whatever its condition.", "maintenance", "Medium"),
 ("Maintenance charges will be paid by the Licensee on production of the society's latest bill.", "maintenance", "Medium"),
 ("The owner shall fix leakage and wiring issues within a week of being informed.", "maintenance", "Low"),
 ("Charges for the clubhouse and shifting in and out will be split between both parties.", "maintenance", "Medium"),
 ("The Licensee will pay the actual electricity bill generated by the meter.", "utilities", "Low"),
 ("Power will be billed to the Licensee at a rate set by the Licensor, higher than the official tariff.", "utilities", "High"),
 ("Water charges are Rs. 1,200 monthly, fixed, however much water is used.", "utilities", "Medium"),
 ("Gas and broadband bills are the responsibility of the Licensee.", "utilities", "Low"),
 ("The Licensee shall also reimburse the owner for the annual property tax of the building.", "utilities", "High"),
 ("The Licensor may stop water and power if payment is delayed even slightly.", "utilities", "High")]:
    T(text, ctype, risk, False)

test = pd.DataFrame(test_rows, columns=["clause_text", "clause_type", "risk_level", "numeric"])
test["clean_text"] = test.clause_text.apply(preprocess)
print("Test clauses:", len(test), "| numeric:", test.numeric.sum(), "| wording-based:", (~test.numeric).sum())
display(pd.crosstab(test.clause_type, test.risk_level))
""")
md("### 📸 4b. Model comparison with 5-fold grouped cross-validation (training data only)")
code("""
def build(model):
    return Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)), ("clf", model)])

factories = {
    "Baseline (most frequent)": lambda: DummyClassifier(strategy="most_frequent"),
    "Naive Bayes":              lambda: MultinomialNB(alpha=0.3),
    "Logistic Regression":      lambda: LogisticRegression(max_iter=3000, C=10),
    "Linear SVM":               lambda: LinearSVC(C=1),
}
# The RISK model only learns from wording-based clauses ("hand"): numeric clauses are judged by Pune rules (Step 5).
TASKS = {"clause_type": ("Clause TYPE", None), "risk_level": ("RISK (wording clauses)", "hand")}
cv_rows = []
for task, (tname, src) in TASKS.items():
    data = train if src is None else train[train.label_source == src]
    for name, make in factories.items():
        r = cross_validate(build(make()), data.clean_text, data[task], groups=data.group,
                           cv=GroupKFold(n_splits=5), scoring=["accuracy", "f1_macro"])
        cv_rows.append((tname, name, r["test_accuracy"].mean(), r["test_f1_macro"].mean(), r["test_f1_macro"].std()))
cv = pd.DataFrame(cv_rows, columns=["Task", "Model", "CV Accuracy", "CV Macro-F1", "F1 std-dev"]).round(3)
display(cv)
""")
md("### 📸 4c. Final test on UNSEEN clauses (models trained on all training data)")
code("""
fitted, best, test_rows_out = {}, {}, []
def subsets(task):
    src = TASKS[task][1]
    return (train if src is None else train[train.label_source == src]), (test if src is None else test[~test.numeric])

for task, (tname, src) in TASKS.items():
    fitted[task] = {}; tr, te = subsets(task)
    for name, make in factories.items():
        m = build(make()).fit(tr.clean_text, tr[task]); fitted[task][name] = m
        p = m.predict(te.clean_text)
        test_rows_out.append((tname, name, accuracy_score(te[task], p),
                              f1_score(te[task], p, average="macro"),
                              f1_score(te[task], p, average="weighted")))
    # best real model chosen by cross-validation Macro-F1 (never by the test set)
    sub = cv[(cv.Task == tname) & (~cv.Model.str.startswith("Baseline"))]
    best[task] = sub.sort_values("CV Macro-F1", ascending=False).iloc[0].Model

res = pd.DataFrame(test_rows_out, columns=["Task", "Model", "Test Accuracy", "Test Macro-F1", "Test Weighted-F1"]).round(3)
display(res)
print("Best model chosen by cross-validation →", {TASKS[k][0]: v for k, v in best.items()})
""")
md("### 📸 4d. Precision / Recall / F1 and confusion matrices of the best models")
code("""
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for ax, (task, (tname, src)) in zip(axes, TASKS.items()):
    te = subsets(task)[1]
    labels = ["Low", "Medium", "High"] if task == "risk_level" else sorted(test[task].unique())
    pred = fitted[task][best[task]].predict(te.clean_text)
    print(f"\\n===== {tname} — {best[task]} (on {len(te)} unseen clauses) =====")
    print(classification_report(te[task], pred, labels=labels, zero_division=0))
    ConfusionMatrixDisplay.from_predictions(te[task], pred, labels=labels, ax=ax,
                                            cmap="Blues", xticks_rotation=45, colorbar=False)
    ax.set_title(f"{tname}: {best[task]}")
plt.tight_layout(); plt.show()
""")
md("""
### 📸 4e. Why ML alone is not enough for risk — the key finding
Our **ML-only baseline** is the same best model trained on *every* clause (numeric ones too) with no rules. A text model can recognise *wording* like "without notice", but it **cannot do arithmetic**: "deposit of Rs. 1,05,000 on rent of Rs. 35,000" needs a ratio (3×), and "Rs. 41,000 for a 2 BHK in Kothrud" needs the local market range. Let's measure it.
""")
code("""
ml_all = build(factories[best["risk_level"]]()).fit(train.clean_text, train.risk_level)   # ML-only baseline
test["ml_risk"] = ml_all.predict(test.clean_text)
out = pd.DataFrame({
    "Subset": ["Wording-based clauses", "Numeric clauses (rent, deposit, %, late fee)", "All clauses"],
    "Clauses": [(~test.numeric).sum(), test.numeric.sum(), len(test)],
    "ML-only risk accuracy": [
        accuracy_score(test[~test.numeric].risk_level, test[~test.numeric].ml_risk),
        accuracy_score(test[test.numeric].risk_level,  test[test.numeric].ml_risk),
        accuracy_score(test.risk_level, test.ml_risk)]}).round(3)
display(out)
""")

# ============================ STEP 5
md("""
## STEP 5 — Hybrid Risk Engine with Explanations

**Design:** for every clause
1. spaCy hybrid NER finds the facts (rent, deposit, %, days, area, BHK).
2. **If a Pune rule applies** (numbers present) → the rule decides the risk and writes the reason, e.g. *"Deposit is 3.5× the monthly rent"*.
3. **Otherwise** → the ML model decides from wording, and we show the **top words** that pushed the decision (from Logistic Regression coefficients).
4. The **clause type** comes from the rule that fired (it knows the family: rent, deposit, increase, late fee); otherwise from the ML model.
5. All clauses are combined into an **overall risk score**: each **High** clause adds 15 points and each **Medium** 7 (capped at 100). Below 25 = LOW, below 60 = MODERATE, otherwise HIGH. *(A plain average hid risky clauses among ordinary boilerplate, so I switched to this penalty score — the weights are a design choice, stated in the report.)*

`ctx` remembers the rent found in an earlier clause, so a deposit clause that says only *"deposit of Rs. 1,26,000"* can still be compared with the rent.
""")
code("""
type_model = fitted["clause_type"][best["clause_type"]]
risk_model = fitted["risk_level"][best["risk_level"]]
lr_risk    = fitted["risk_level"]["Logistic Regression"]       # used only to EXPLAIN word-based decisions

def top_words(clean, label, n=3):
    vec, clf = lr_risk.named_steps["tfidf"], lr_risk.named_steps["clf"]
    contrib = vec.transform([clean]).multiply(clf.coef_[list(clf.classes_).index(label)]).toarray()[0]
    names = vec.get_feature_names_out()
    return [names[i] for i in contrib.argsort()[::-1][:n] if contrib[i] > 0]

def rule_based_risk(clause, ctx):
    \"\"\"Returns (risk, reason, family) if a Pune rule applies, else (None, None, None).\"\"\"
    d, low = nlp(clause), clause.lower()
    ents  = [(e.label_, e.text, e.start_char) for e in d.ents]
    money = [(money_value(t), s) for l, t, s in ents if l == "MONEY_AMT"]
    pcts  = [first_number(t) for l, t, s in ents if l == "PERCENT_VAL"]
    days  = [duration_days(t) for l, t, s in ents if l == "DURATION" and "day" in t.lower()]
    area  = next((AREA_ALIASES.get(t.lower()) for l, t, s in ents if l == "AREA"), None)
    bhk   = next((int(first_number(t)) for l, t, s in ents if l == "BHK"), None)

    if "deposit" in low:                                            # --- deposit refund time
        if days and re.search(r"refund|return", low) and not money:
            return refund_risk(days[0]), f"Deposit refunded after {days[0]} days (Pune norm: 15–30 days)", "deposit"
        if money:                                                   # --- deposit vs rent
            k = low.find("deposit")
            after = [m for m, s in money if s > k]
            dep = after[0] if after else money[0][0]
            others = [m for m, s in money if m != dep]
            rent = others[0] if others else ctx.get("rent")
            if rent:
                return deposit_risk(dep, rent), f"Deposit is {dep/rent:.1f}x monthly rent (Low ≤2x, Medium ≤3x, High >3x)", "deposit"
        return None, None, None
    if pcts and re.search(r"increas|revis|escalat|hike|raise|go up|goes up", low):    # --- yearly increase
        return increase_risk(pcts[0]), f"Rent rises {pcts[0]:g}% per renewal (Low ≤10%, Medium ≤15%, High >15%)", "rent_increase"
    if money and re.search(r"\\blate\\b|delay|overdue|due date", low) and re.search(r"per day|a day|each day|daily", low):
        grace = days[0] if days else 0                              # --- late fee
        return latefee_risk(grace, money[0][0]), f"Late fee Rs.{money[0][0]}/day with {grace}-day grace (norm: modest fee after 5–7 days)", "penalty"
    if area and bhk in (1, 2, 3) and money:                         # --- rent vs market
        rent = money[0][0]; lo, hi = RENT_RANGES[area][bhk]; ctx.update(rent=rent, area=area, bhk=bhk)
        return rent_risk(area, bhk, rent), f"Rent Rs.{rent:,} is Rs.{max(rent-lo,0):,} above the start of the Pune {area.title()} {bhk} BHK range (Rs.{lo:,}–{hi:,}); Low up to +4,000, Medium up to +7,000", "rent"
    return None, None, None

def hybrid_predict(clause, ctx):
    clean = preprocess(clause)
    ctype = type_model.predict([clean])[0]
    risk, reason, family = rule_based_risk(clause, ctx)
    if risk is not None:
        return family, risk, "Pune rule", reason
    risk = risk_model.predict([clean])[0]
    words = top_words(clean, risk)
    if risk == "Low": return ctype, risk, "ML (wording)", "No risky terms found - standard wording"
    return ctype, risk, "ML (wording)", "Key phrases: " + (", ".join(words) if words else "overall wording pattern")
""")
md("### 📸 5a. Does the hybrid beat ML alone? (same unseen test set)")
code("""
preds = [hybrid_predict(c, {}) for c in test.clause_text]
test["hy_type"], test["hy_risk"], test["source"], test["reason"] = zip(*preds)

def acc(df, col): return accuracy_score(df.risk_level, df[col])
cmp_df = pd.DataFrame({
    "Subset": ["Wording-based", "Numeric", "All clauses"],
    "ML only": [acc(test[~test.numeric], "ml_risk"), acc(test[test.numeric], "ml_risk"), acc(test, "ml_risk")],
    "Hybrid (rules + ML)": [acc(test[~test.numeric], "hy_risk"), acc(test[test.numeric], "hy_risk"), acc(test, "hy_risk")]}).round(3)
display(cmp_df)
print(f"Overall risk Macro-F1:  ML only = {f1_score(test.risk_level, test.ml_risk, average='macro'):.3f}"
      f"  |  Hybrid = {f1_score(test.risk_level, test.hy_risk, average='macro'):.3f}")
ml_type = type_model.predict(test.clean_text)
print(f"Clause-TYPE accuracy:  ML only = {accuracy_score(test.clause_type, ml_type):.3f}  |  Hybrid (rule family when a rule fires) = {accuracy_score(test.clause_type, test.hy_type):.3f}")

ax = cmp_df.set_index("Subset").plot(kind="bar", figsize=(7, 4), color=["#90a4ae", "#1e88e5"])
ax.set_ylim(0, 1.05); ax.set_ylabel("Risk accuracy"); ax.set_title("ML only vs Hybrid on unseen clauses")
plt.xticks(rotation=0); plt.tight_layout(); plt.show()
""")
md("### 📸 5b. Error analysis — every clause the hybrid got wrong (use this in the report & viva)")
code("""
wrong = test[test.risk_level != test.hy_risk][["clause_text", "risk_level", "hy_risk", "source", "reason"]]
wrong.columns = ["Clause", "True risk", "Predicted", "Decided by", "Reason shown"]
pd.set_option("display.max_colwidth", 90)
print(f"{len(wrong)} of {len(test)} risk predictions wrong")
display(wrong)
""")
md("### 📸 5c. Full analysis of the sample agreement")
code("""
def risk_score(risks):
    score = min(100, sum(15 if r == "High" else 7 if r == "Medium" else 0 for r in risks))
    return score, ("LOW" if score < 25 else "MODERATE" if score < 60 else "HIGH")

def analyse_agreement(text):
    header, clauses = split_clauses(text)
    ctx, out = {}, []
    for i, c in enumerate(clauses, 1):
        ctype, risk, source, reason = hybrid_predict(c, ctx)
        out.append((i, c, ctype, risk, source, reason))
    rep = pd.DataFrame(out, columns=["#", "Clause", "Type", "Risk", "Decided by", "Why"])
    score, _ = risk_score(rep.Risk)
    return rep, score

COL = {"Low": "background-color:#c8e6c9;color:#1b1b1b;font-weight:600", "Medium": "background-color:#fff3b0;color:#1b1b1b;font-weight:600", "High": "background-color:#ffcdd2;color:#1b1b1b;font-weight:600"}
report, score = analyse_agreement(open("sample_agreement.txt", encoding="utf-8").read())
score, level = risk_score(report.Risk)
display(report.style.apply(lambda col: [COL[v] for v in col], subset=["Risk"])
        .set_properties(subset=["Clause", "Why"], **{"text-align": "left", "white-space": "normal"}))
print(f"\\nOVERALL RISK SCORE: {score}/100  →  {level} RISK")
print("High-risk clauses:", list(report[report.Risk == "High"]["#"]), "| Medium:", list(report[report.Risk == "Medium"]["#"]))
""")
md("""
### Optional (strongly recommended): test on REAL clauses
Upload a CSV named **`real_clauses.csv`** (Colab left panel ▸ 📁 Files ▸ Upload) with columns `clause_text, clause_type, risk_level`, using 20–30 clauses from real agreements (remove names). The cell below then evaluates the system on them. If you have none yet, it simply skips.
""")
code("""
import os
if os.path.exists("real_clauses.csv"):
    real = pd.read_csv("real_clauses.csv")
    preds = [hybrid_predict(c, {}) for c in real.clause_text]
    real["pred_type"], real["pred_risk"], real["source"], real["reason"] = zip(*preds)
    print(f"Real clauses: {len(real)}")
    print(f"Type accuracy: {accuracy_score(real.clause_type, real.pred_type):.3f} | "
          f"Risk accuracy: {accuracy_score(real.risk_level, real.pred_risk):.3f} | "
          f"Risk macro-F1: {f1_score(real.risk_level, real.pred_risk, average='macro'):.3f}")
    display(real[real.risk_level != real.pred_risk][["clause_text", "risk_level", "pred_risk", "reason"]])
else:
    print("real_clauses.csv not found — skipping (add it to report results on real-world text).")
""")
