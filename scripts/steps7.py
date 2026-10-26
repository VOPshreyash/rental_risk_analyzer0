# ============================ STEP 7
md("""
## STEP 7 — Question Answering by Clause Search with Query Expansion  *(Practical 5)*

**Problem (vocabulary mismatch):** a tenant asks *"Who pays the light bill?"* but the agreement says *"electricity charges"*. A plain keyword/TF-IDF search finds **no shared words**, so it misses the clause. **Query expansion** adds related words (*light → electricity, power*) before searching.

**Five search variants are compared:**
| Variant | How the query is expanded |
|---|---|
| Baseline | no expansion (plain TF-IDF cosine similarity) |
| WordNet | synonyms from NLTK WordNet (general English) |
| Domain thesaurus | a small rental-law thesaurus (*landlord ↔ licensor, deposit ↔ security/advance, evict ↔ vacate/terminate …*) |
| WordNet + Domain | both |
| Domain + PRF | domain terms, then **pseudo-relevance feedback** (Rocchio): add the terms of the top-3 results and search again |

**Metrics** (24 tenant questions; a clause is *relevant* if its type matches the question's topic):
- **Precision@5** – of the top 5 results, how many are relevant
- **Recall@10** – of all relevant clauses, how many appear in the top 10
- **MRR** – 1 ÷ rank of the first relevant result (higher = the right clause comes first)

⚠️ Honest note: the questions and the thesaurus were both written by me, so the expansion gain is likely optimistic. Add **your own 10 questions** in the optional cell to test it fairly.
""")
code('''
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import wordnet as wn

# ---------- 7a. Domain thesaurus (general rental vocabulary) ----------
THES = {
 "landlord": ["licensor", "owner"], "owner": ["licensor", "landlord"], "tenant": ["licensee", "occupant"],
 "rent": ["compensation", "licence fee", "monthly"], "price": ["rent", "compensation"], "monthly": ["per month", "rent"],
 "deposit": ["security", "advance", "refundable"], "advance": ["deposit", "security"], "security": ["deposit", "refundable"],
 "return": ["refund"], "refund": ["return", "deposit"], "money": ["amount", "deposit"],
 "light": ["electricity", "power"], "power": ["electricity"], "electricity": ["power", "meter"], "water": ["metered water", "water charge"],
 "tax": ["property tax", "levy"], "bill": ["charge", "payment"],
 "evict": ["vacate", "terminate", "remove", "cancel"], "throw": ["evict", "remove", "vacate"], "leave": ["vacate", "terminate", "exit"],
 "move": ["vacate"], "lock": ["lock-in", "minimum stay", "commitment"], "minimum": ["lock-in", "commitment"], "stay": ["period", "lock-in"],
 "early": ["lock-in", "forfeit", "compensation"], "notice": ["written notice", "terminate"],
 "hike": ["increase", "revision", "escalation"], "raise": ["increase", "hike", "revise"], "increase": ["hike", "escalation"], "yearly": ["annual", "renewal"],
 "late": ["delay", "overdue", "penalty"], "delay": ["late", "fine", "penalty"], "fine": ["penalty", "late fee"], "penalty": ["fine", "late fee"],
 "repair": ["maintenance", "damage"], "damage": ["repair", "maintenance"], "painting": ["repaint", "maintenance"],
 "society": ["maintenance", "sinking fund", "corpus"], "maintenance": ["society", "repair"], "lock-in": ["minimum stay"],
}

def q_tokens(q): return preprocess(q).split()

def wordnet_expand(tokens, per_word=3):
    out = []
    for t in tokens:
        n = 0
        for syn in wn.synsets(t)[:2]:
            for l in syn.lemma_names()[:3]:
                l = l.lower()
                if "_" not in l and l != t and l not in out and n < per_word: out.append(l); n += 1
    return out

def domain_expand(tokens):
    out = []
    for t in tokens:
        for e in THES.get(t, []):
            if e not in out: out.append(e)
    return [w for e in out for w in preprocess(e).split()]

def rank_docs(question, vec, X, variant="baseline", alpha=0.5, beta=0.6):
    toks = q_tokens(question)
    q = vec.transform([" ".join(toks)]).toarray()
    exp = []
    if "wordnet" in variant: exp += wordnet_expand(toks)
    if "domain" in variant:  exp += domain_expand(toks)
    if exp: q = q + alpha * vec.transform([" ".join(exp)]).toarray()
    sims = cosine_similarity(q, X).ravel()
    if "prf" in variant:                                          # Rocchio pseudo-relevance feedback
        top = sims.argsort()[::-1][:3]
        q = q + beta * np.asarray(X[top].mean(axis=0))
        sims = cosine_similarity(q, X).ravel()
    return sims.argsort()[::-1], exp

# ---------- 7b. Evaluation set: 24 tenant questions -> relevant clause TYPE ----------
QUESTIONS = [
 ("How much do I have to pay every month for the flat?", "rent"), ("What is the monthly charge for staying in this apartment?", "rent"),
 ("How much money do I give as security and will I get it back?", "deposit"), ("When will the owner return my advance after I leave?", "deposit"),
 ("Can the owner keep my security money?", "deposit"),
 ("Can the owner raise the price next year?", "rent_increase"), ("By how much will the rent go up when I renew?", "rent_increase"),
 ("Is there a limit on yearly hikes?", "rent_increase"),
 ("What happens if I pay the rent late?", "penalty"), ("Will I be fined for delay in payment?", "penalty"),
 ("Are there any charges for breaking the rules?", "penalty"),
 ("Can I leave before the agreement ends?", "lockin"), ("What is the minimum period I must stay?", "lockin"),
 ("Do I have to pay if I move out early?", "lockin"),
 ("Can the landlord throw me out suddenly?", "eviction"), ("How much notice is needed to make me leave?", "eviction"),
 ("Can the owner lock the flat if I am late?", "eviction"),
 ("Who pays for repairs in the house?", "maintenance"), ("Do I have to pay society charges?", "maintenance"),
 ("Who bears the cost of painting and damage?", "maintenance"),
 ("Who pays the light bill?", "utilities"), ("How is water billed?", "utilities"),
 ("Do I pay property tax?", "utilities"), ("Can the owner cut off power supply?", "utilities"),
]
corpus = test.reset_index(drop=True)
vec_c = TfidfVectorizer(sublinear_tf=True).fit(corpus.clean_text)
X_c = vec_c.transform(corpus.clean_text).toarray()

def evaluate(variant, qs=QUESTIONS):
    P5, R10, RR = [], [], []
    for q, qtype in qs:
        order, _ = rank_docs(q, vec_c, X_c, variant)
        rel = (corpus.clause_type.values[order] == qtype); n_rel = (corpus.clause_type == qtype).sum()
        P5.append(rel[:5].mean()); R10.append(rel[:10].sum() / n_rel)
        RR.append(1 / (np.argmax(rel) + 1) if rel.any() else 0)
    return np.mean(P5), np.mean(R10), np.mean(RR)

VARIANTS = ["baseline", "wordnet", "domain", "wordnet+domain", "domain+prf"]
ev = pd.DataFrame([(v, *evaluate(v)) for v in VARIANTS], columns=["Variant", "Precision@5", "Recall@10", "MRR"]).round(3)
print(f"Corpus: {len(corpus)} clauses | Questions: {len(QUESTIONS)}")
display(ev)
ax = ev.set_index("Variant").plot(kind="bar", figsize=(9, 4), color=["#90a4ae", "#1e88e5", "#43a047"])
ax.set_ylim(0, 1); ax.set_title("Clause search: effect of query expansion"); plt.xticks(rotation=15); plt.tight_layout(); plt.show()
''')
md("### 📸 7c. Per-topic breakdown and worked examples")
code('''
rows = []
for qtype in sorted(set(t for _, t in QUESTIONS)):
    qs = [(q, t) for q, t in QUESTIONS if t == qtype]
    rows.append((qtype, len(qs), evaluate("baseline", qs)[2], evaluate("domain", qs)[2], evaluate("domain+prf", qs)[2]))
display(pd.DataFrame(rows, columns=["Topic", "Questions", "MRR baseline", "MRR domain", "MRR domain+PRF"]).round(3))

def show_example(question, qtype, variant):
    order, exp = rank_docs(question, vec_c, X_c, variant)
    print(f"[{variant}]  expansion terms: {exp[:12]}")
    for r, i in enumerate(order[:3], 1):
        ok = "OK " if corpus.clause_type[i] == qtype else "-- "
        print(f"   {r}. {ok}({corpus.clause_type[i]:11s}) {corpus.clause_text[i][:85]}")
for question, qtype in [QUESTIONS[20], QUESTIONS[14], QUESTIONS[3]]:
    print("\\nQUESTION:", question, f"   (relevant topic: {qtype})")
    show_example(question, qtype, "baseline"); show_example(question, qtype, "domain")
''')
md("### 📸 7d. Which questions still fail? (error analysis)")
code('''
fail = []
for q, qtype in QUESTIONS:
    order, _ = rank_docs(q, vec_c, X_c, "domain")
    first = np.argmax(corpus.clause_type.values[order] == qtype) + 1
    if first > 1: fail.append((q, qtype, first, corpus.clause_type[order[0]]))
print(f"{len(fail)} of {len(QUESTIONS)} questions do not have a relevant clause at rank 1 (domain thesaurus):")
display(pd.DataFrame(fail, columns=["Question", "Topic", "First relevant rank", "Rank-1 topic returned"]))
''')
md("""
### 7e. Ask questions about YOUR analysed agreement
The search now runs on the **clauses of the agreement you analysed** (Step 6) and shows each matching clause with its **risk colour** — so a tenant can ask *"Can the landlord throw me out suddenly?"* and immediately see Clause 10 flagged High. Run an analysis above first (the live-demo panel, or the scenario cell).
""")
code('''
def search_agreement(question, k=3, variant="domain"):
    if not LAST: print("Analyse an agreement first (Step 6 panel or scenario cell)."); return
    docs = [preprocess(c) for c in LAST["clauses"]]
    vec = TfidfVectorizer(sublinear_tf=True).fit(docs); X = vec.transform(docs).toarray()
    order, exp = rank_docs(question, vec, X, variant)
    res = LAST["rep"].iloc[order[:k]][["#", "Clause title", "Risk", "Why"]].copy()
    res.insert(1, "Matching text", [LAST["clauses"][i][:110] + "..." for i in order[:k]])
    print(f"QUESTION: {question}\\nexpanded with: {exp[:10]}")
    display(res.style.apply(lambda col: [COL[v] for v in col], subset=["Risk"])
            .set_properties(subset=["Matching text", "Why"], **{"text-align": "left", "white-space": "normal"}))

# demo on the risky scenario C
p = SCEN["C. Risky agreement"]; _ = show_analysis(build_agreement(**p), KEY[p["area_name"]], p["bhk"])
for qn in ["Can the landlord throw me out suddenly?", "Will I get my security money back?", "Who pays for the society charges?"]:
    search_agreement(qn)
''')
md("### 🎤 Live: type any question")
code('''
q_box = wd.Text(placeholder="e.g. Who pays the light bill?", description="Question", layout=wd.Layout(width="600px"))
q_btn, q_out = wd.Button(description="Search", button_style="success"), wd.Output()
def on_ask(_):
    with q_out: q_out.clear_output(wait=True); search_agreement(q_box.value)
q_btn.on_click(on_ask); _d(wd.VBox([q_box, q_btn, q_out]))
''')
md("""
### Optional: test with YOUR OWN questions (fair evaluation)
Write 10 questions the way a real tenant would ask and give the topic (`rent, deposit, rent_increase, penalty, lockin, eviction, maintenance, utilities`). Better still, let a classmate write them without seeing my thesaurus.
""")
code('''
my_questions = [
    # ("Who will fix a leaking tap?", "maintenance"),
    # ("Is the advance money returned?", "deposit"),
]
if my_questions:
    print(pd.DataFrame([(v, *evaluate(v, my_questions)) for v in VARIANTS], columns=["Variant", "Precision@5", "Recall@10", "MRR"]).round(3))
else:
    print("Add questions to my_questions above and re-run this cell.")
''')
