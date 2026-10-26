import re, nbformat as nbf
nb = nbf.v4.new_notebook(); C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
rd = lambda f: open(f, encoding="utf-8").read()

md("""
# 🏠 Rental Agreement Risk Analyzer (Pune)
**Subject:** Natural Language Processing Lab  |  **Name:** ________  |  **Roll No.:** ________  |  **Date:** ________

**Aim:** To build an NLP system that reads a rental (Leave & License) agreement, splits it into clauses, extracts key facts (rent, deposit, notice period, area), classifies each clause and rates its **risk (Low / Medium / High)** using Pune market norms.

**How to use this notebook:** Run the cells **top to bottom** (Runtime ▸ Run all, or Shift+Enter on each cell).
Every cell marked **📸** produces output you should screenshot for your report.
""")

md("## 0. Setup\nInstalls the libraries and downloads NLTK data and the spaCy English model (~1 minute).")
code("""
!pip install -q nltk pandas matplotlib spacy ipywidgets
!python -m spacy download en_core_web_sm -q

import nltk
for r in ["punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"]:
    nltk.download(r, quiet=True)
print("Setup complete ✅")
""")

# ============================ STEP 1
md("""
## STEP 1 — Problem Statement, Pune Rules & Dataset

**Problem:** Tenants often sign rental agreements without understanding risky clauses (unfair deposit deductions, eviction without notice, huge rent hikes). This project flags such clauses automatically.

**Key idea (hybrid design):**
- *Numeric clauses* (rent, deposit, % increase, late fee) → judged by **rules calibrated to Pune market rates**.
- *Wording-based clauses* (eviction, lock-in, maintenance) → judged by an **ML classifier** (Step 4).

The cell below saves our Pune rules into one file (`pune_rules.py`) so every step uses the same numbers.
""")
code(rd("pune_rules.py").replace('"""\npune_rules.py', '"""\npune_rules.py', 1) and "%%writefile pune_rules.py\n" + rd("pune_rules.py"))
md("Now the dataset generator. Numeric clauses are **generated from templates and labelled by the rules**; qualitative clauses are **hand-labelled**.")
code("%%writefile make_dataset.py\n" + rd("make_dataset.py"))
code("!python make_dataset.py")
md("### 📸 Dataset overview")
code("""
import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv("clauses.csv")
display(df.sample(8, random_state=1))
print("Total clauses:", len(df))
display(pd.crosstab(df.clause_type, df.risk_level))

ax = pd.crosstab(df.clause_type, df.risk_level)[["Low","Medium","High"]].plot(
        kind="bar", stacked=True, color=["#4caf50","#ffc107","#e53935"], figsize=(8,4))
ax.set_title("Dataset: clause types vs risk level"); ax.set_ylabel("Number of clauses")
plt.xticks(rotation=30); plt.tight_layout(); plt.show()
""")
md("### 📸 Pune rule engine — quick tests (good for your viva)")
code("""
from pune_rules import *
print("Kothrud 2BHK (range starts 27,000): rent 29,000 ->", rent_risk("kothrud", 2, 29000))   # +2,000 above start
print("Kothrud 2BHK, rent 33,000 ->", rent_risk("kothrud", 2, 33000))   # +6,000 above start
print("Kothrud 2BHK, rent 36,000 ->", rent_risk("kothrud", 2, 36000))   # +9,000 above start
print("Deposit 72,000 on rent 36,000 (2x)   ->", deposit_risk(72000, 36000))
print("Deposit 1,26,000 on rent 36,000 (3.5x)->", deposit_risk(126000, 36000))
print("Rent increase 12% ->", increase_risk(12), "| 20% ->", increase_risk(20))
print("\\nAssumptions made:"); [print(" -", a) for a in ASSUMPTIONS];
""")

# ============================ STEP 2
s2 = rd("step2_preprocessing.py").split('if __name__')[0]
s2 = s2.split('import re', 1)[1]; s2 = "import re" + s2
md("""
## STEP 2 — Text Preprocessing with NLTK  *(Practical 1)*

Pipeline: **lowercase → regex cleaning → tokenization → stop-word removal → lemmatization**

Design choices to remember for the viva:
1. **Placeholders, not deletion** — `Rs. 50,000` → `moneyamt`; `5 percent` → `percentval`. The classifier learns "money is involved" without caring about the exact value.
2. **Protected stop-words** — *no, not, nor, never, only, before, after, against* are **kept**. "shall **not** be refunded" ≠ "shall be refunded".
3. **Lemmatization over stemming** — gives real words (`security`) instead of `secur`.
""")
code(s2)
md("### 📸 Stage-by-stage output on one clause")
code("""
from nltk.tokenize import word_tokenize, sent_tokenize
df = pd.read_csv("clauses.csv")
sample = df.loc[df.clause_text.str.contains(" not ")].iloc[0].clause_text

print("ORIGINAL        :", sample)
norm = normalise(sample);                       print("\\n1. AFTER REGEX  :", norm)
toks = word_tokenize(norm);                     print("2. WORD TOKENS  :", toks)
no_stop = [w for w in toks if w not in STOP and len(w) > 1]
print("3. STOP REMOVED :", no_stop)
print("   protected (kept) words:", [w for w in toks if w in stopwords.words('english') and w not in STOP])
print("4a. STEMMING    :", [stemmer.stem(w) for w in no_stop])
print("4b. LEMMATIZED  :", preprocess(sample).split())
""")
md("### 📸 Stemming vs Lemmatization")
code("""
words = ["deductions", "charged", "terminated", "evicting", "premises", "responsibility", "refunded"]
pd.DataFrame({
    "word": words,
    "Porter stem": [stemmer.stem(w) for w in words],
    "lemma (verb)": [lemmatizer.lemmatize(w, "v") for w in words],
    "lemma (noun)": [lemmatizer.lemmatize(w, "n") for w in words],
})
""")
md("### 📸 Apply to the whole dataset")
code("""
df["clean_text"] = df["clause_text"].apply(preprocess)
df["tokens_before"] = df["clause_text"].apply(lambda s: len(word_tokenize(s)))
df["tokens_after"]  = df["clean_text"].apply(lambda s: len(s.split()))
df.to_csv("clauses_clean.csv", index=False)

display(df[["clause_text", "clean_text"]].head(4).style.set_properties(**{"text-align": "left"}))
print(f"Average tokens per clause: {df.tokens_before.mean():.1f} → {df.tokens_after.mean():.1f} "
      f"({100*(1-df.tokens_after.mean()/df.tokens_before.mean()):.0f}% reduction)")

plt.figure(figsize=(5,3.5))
plt.bar(["Before","After"], [df.tokens_before.mean(), df.tokens_after.mean()], color=["#90a4ae","#1e88e5"])
plt.title("Avg tokens per clause"); plt.ylabel("tokens"); plt.show()
""")

# ============================ STEP 3
md("""
## STEP 3 — Clause Splitting & spaCy Analysis  *(Practical 2)*

1. **Clause splitter** – NLTK's sentence tokenizer wrongly cuts at `Rs.`; we split on clause numbers and protect abbreviations.
2. **spaCy** – tokens, POS tags, lemmas, dependencies, noun chunks, named entities.
3. **Hybrid NER** – pretrained spaCy NER + our own `EntityRuler` rules for domain entities: `MONEY_AMT, PERCENT_VAL, DURATION, AREA, BHK, PARTY`.
4. **Value parsers** – `"Rs. 1,26,000"` → `126000`, `"forty five days"` → `45`.

First, a sample agreement to analyse (you can replace this with a real one later):
""")
code("with open(\"sample_agreement.txt\", \"w\", encoding=\"utf-8\") as f:\n    f.write('''" + rd("sample_agreement.txt") + "''')\nprint(open(\"sample_agreement.txt\", encoding=\"utf-8\").read())")
s3 = rd("step3_ner.py")
s3 = s3.split("# ------------------------------------------------------------------ DEMO")[0]
parts = re.split(r"# -{20,} (\d)\. ", s3)
head = parts[0].split('import re', 1)[1]; head = "import re" + head
head = head.replace("from nltk.tokenize import sent_tokenize", "from nltk.tokenize import sent_tokenize")
sections = {parts[i]: parts[i+1] for i in range(1, len(parts), 2)}
code(head.strip())
code("# ---- Clause splitter ----\n" + sections["1"].split("\n", 1)[1])
code("# ---- spaCy pipelines: pretrained vs hybrid ----\n" + sections["2"].split("\n", 1)[1])
code("# ---- Value parsers & fact extraction ----\n" + sections["3"].split("\n", 1)[1])

md("### 📸 A. Clause splitting")
code("""
text = open("sample_agreement.txt", encoding="utf-8").read()
header, clauses = split_clauses(text)
print("Plain NLTK sent_tokenize on clause 1 ->", len(sent_tokenize(clauses[0])), "pieces  ❌ (splits at 'Rs.')")
print("Our splitter on the whole agreement   ->", len(clauses), "clauses ✅\\n")
for i, c in enumerate(clauses, 1): print(f"{i}. {c}")
print("\\nFallback (unnumbered text):", split_clauses("Rent is Rs. 30,000 per month. Deposit is Rs. 60,000. Mr. Rao is the Landlord.")[1])
""")
md("### 📸 B. Tokens, POS tags, lemmas, dependencies, noun chunks")
code("""
doc = nlp_base(clauses[4])
display(pd.DataFrame([(t.text, t.pos_, t.lemma_, t.dep_) for t in doc], columns=["Token","POS","Lemma","Dependency"]).head(14))
print("Noun chunks:", [c.text for c in doc.noun_chunks])
""")
md("### 📸 C. Named entities in the preamble (pretrained model only)")
code("""
pre = nlp_base(header.replace("LEAVE AND LICENSE AGREEMENT", "").strip())
display(pd.DataFrame([(e.text, e.label_, spacy.explain(e.label_)) for e in pre.ents], columns=["Entity","Label","Meaning"]))
print("Note: the small pretrained model makes mistakes here — one reason we add our own rules.")
""")
md("### 📸 D. Pretrained NER vs our Hybrid NER (the key result of this step)")
code("""
c = clauses[1]; print(c, "\\n")
print("Pretrained only:", [(e.text, e.label_) for e in nlp_base(c).ents])
print("Hybrid (rules) :", [(e.text, e.label_) for e in nlp(c).ents])
""")
md("### 📸 E. Entities and extracted facts for every clause")
code("""
rows = []
for i, c in enumerate(clauses, 1):
    d = nlp(c)
    ents = ", ".join(f"{e.text} [{e.label_}]" for e in d.ents if e.label_ in
                     ("MONEY_AMT","PERCENT_VAL","DURATION","AREA","BHK"))
    facts = {k: v for k, v in extract_facts(c).items() if v and k != "parties"}
    rows.append((i, c[:55] + "...", ents, facts))
pd.set_option("display.max_colwidth", 80)
pd.DataFrame(rows, columns=["#","Clause","Entities found","Extracted facts"])
""")

exec(open("steps45.py", encoding="utf-8").read())

exec(open("steps6.py", encoding="utf-8").read())

exec(open("steps7.py", encoding="utf-8").read())

md("""
## ✅ Progress so far
| Step | Status |
|---|---|
| 1. Problem, Pune rules, dataset | Done |
| 2. NLTK preprocessing | Done |
| 3. Clause splitting + spaCy NER | Done |
| 4. TF-IDF + 3-model comparison, unseen-test evaluation | Done |
| 5. Hybrid rules+ML risk engine with explanations | Done |
| 6. Official-form mode: engine v2 + live fill-the-form demo | Done |
| 7. Query-expansion clause search + evaluation (Practical 5) | Done |
| 8. Extras: missing-clause detector, translation, PDF export | *next* |
""")
nb["cells"] = C
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nbf.write(nb, "Rental_Risk_Analyzer_NLP.ipynb")
print("cells:", len(C))
