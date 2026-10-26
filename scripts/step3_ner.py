"""
STEP 3: Clause splitting + spaCy analysis (tokens, POS, NER, custom entities)
 - split_clauses(): fixes the 'Rs.' sentence-splitting problem seen in Step 2
 - spaCy pretrained NER (PERSON, DATE, GPE ...) + EntityRuler for domain entities
   (MONEY_AMT, PERCENT_VAL, DURATION, AREA, BHK, PARTY)
 - value parsers: "Rs. 1,26,000" -> 126000, "forty five days" -> 45
"""
import re
import spacy
from nltk.tokenize import sent_tokenize
from pune_rules import AREA_ALIASES

# ------------------------------------------------------------------ 1. CLAUSE SPLITTER
ABBR = ["Rs.", "Mr.", "Ms.", "Mrs.", "Dr.", "No.", "approx.", "i.e.", "e.g."]

def split_clauses(text):
    """Split an agreement into clauses. Numbered clauses ('1.', '2)') are split by regex;
       otherwise fall back to sentence splitting with abbreviations protected."""
    parts = re.split(r"(?m)^\s*\d+[.)]\s+", text)       # split at line-start numbering
    header, clauses = parts[0].strip(), [p.strip() for p in parts[1:] if p.strip()]
    if clauses:
        return header, clauses
    t = text
    for a in ABBR:                                       # protect the dots
        t = t.replace(a, a.replace(".", "<DOT>"))
    sents = [s.replace("<DOT>", ".").strip() for s in sent_tokenize(t)]
    return "", sents

# ------------------------------------------------------------------ 2. spaCy PIPELINES
nlp_base = spacy.load("en_core_web_sm")                  # pretrained only
nlp = spacy.load("en_core_web_sm")                       # pretrained + our rules
ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})

UNITS = ["day", "days", "month", "months", "year", "years"]
patterns = [
    {"label": "MONEY_AMT",   "pattern": [{"LOWER": {"REGEX": r"^(rs\.?|inr|₹)$"}}, {"ORTH": ".", "OP": "?"}, {"LIKE_NUM": True}]},
    {"label": "PERCENT_VAL", "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["percent", "%"]}}]},
    {"label": "DURATION",    "pattern": [{"LIKE_NUM": True, "LOWER": {"NOT_IN": ["first", "second", "third", "fourth", "fifth", "next"]}, "OP": "+"}, {"LOWER": {"IN": UNITS}}]},
    {"label": "BHK",         "pattern": [{"LIKE_NUM": True}, {"LOWER": "bhk"}]},
    {"label": "BHK",         "pattern": [{"LOWER": {"REGEX": r"^\d+bhk$"}}]},
    {"label": "PARTY",       "pattern": [{"LOWER": {"IN": ["landlord", "tenant", "licensor", "licensee"]}}]},
]
# Pune localities (multi-word names written as token patterns)
for area in ["kothrud", "wakad", "kharadi", "baner", "balewadi", "hinjewadi", "viman nagar", "sus gaon"]:
    patterns.append({"label": "AREA", "pattern": [{"LOWER": w} for w in area.split()]})
patterns.append({"label": "AREA", "pattern": [{"LOWER": "hinjewadi"}, {"LOWER": "phase"}, {"LIKE_NUM": True}]})
ruler.add_patterns(patterns)

# ------------------------------------------------------------------ 3. VALUE PARSERS
WORDS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
         "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
         "eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,
         "eighty":80,"ninety":90}

def words_to_number(s):
    s = s.lower().replace("-", " ").strip()
    if re.fullmatch(r"[\d,\.]+", s): return float(s.replace(",", ""))
    toks = [WORDS[w] for w in s.split() if w in WORDS]
    return float(sum(toks)) if toks else None

def first_number(s):                      # "12 percent" / "10%" / "ten percent" -> number
    m = re.search(r"\d+(\.\d+)?", s)
    if m: return float(m.group())
    return words_to_number(re.sub(r"[^a-z\s-]", "", s.lower()).split()[0])

def money_value(s):                       # "Rs. 1,26,000" -> 126000
    m = re.search(r"[\d,]+(\.\d+)?", s); return int(float(m.group().replace(",", ""))) if m else None

def duration_days(s):                     # "forty five days" -> 45 ; "eleven months" -> 330
    m = re.match(r"(.+?)\s*(days?|months?|years?)$", s.strip().lower())
    n = words_to_number(m.group(1)); u = m.group(2)
    if n is None: return 0                # unparseable (e.g. ordinal words) -> ignore safely
    return int(n * (1 if u.startswith("day") else 30 if u.startswith("month") else 365))

def extract_facts(clause):
    """Return a dict of structured facts found in one clause."""
    doc = nlp(clause); f = {"money": [], "percent": [], "durations_days": [], "area": None, "bhk": None, "parties": set()}
    for e in doc.ents:
        if e.label_ == "MONEY_AMT":   f["money"].append(money_value(e.text))
        elif e.label_ == "PERCENT_VAL": f["percent"].append(first_number(e.text))
        elif e.label_ == "DURATION":  f["durations_days"].append(duration_days(e.text))
        elif e.label_ == "BHK":       f["bhk"] = int(first_number(e.text))
        elif e.label_ == "AREA":      f["area"] = AREA_ALIASES.get(e.text.lower())
        elif e.label_ == "PARTY":     f["parties"].add(e.text.lower())
    f["parties"] = sorted(f["parties"]); return f

# ------------------------------------------------------------------ DEMO
if __name__ == "__main__":
    text = open("sample_agreement.txt", encoding="utf-8").read()
    header, clauses = split_clauses(text)

    print("=" * 72, "\nA. CLAUSE SPLITTING\n" + "=" * 72)
    wrong = sent_tokenize(clauses[0])
    print("Plain NLTK sent_tokenize on clause 1 ->", len(wrong), "pieces (WRONG, split at 'Rs.')")
    print("Our splitter on whole agreement       ->", len(clauses), "clauses (correct)")
    print("Fallback test (unnumbered text):",
          split_clauses("Rent is Rs. 30,000 per month. Deposit is Rs. 60,000. Mr. Rao is the Landlord.")[1])

    print("\n" + "=" * 72, "\nB. PREAMBLE - pretrained spaCy NER (people, places, dates)\n" + "=" * 72)
    for e in nlp_base(header.replace("LEAVE AND LICENSE AGREEMENT", "").strip()).ents:
        print(f"  {e.label_:10s} {e.text}")

    print("\n" + "=" * 72, "\nC. TOKENS, POS TAGS, LEMMAS, DEPENDENCIES (clause 5)\n" + "=" * 72)
    print(f"  {'TOKEN':12s}{'POS':8s}{'LEMMA':12s}{'DEP':10s}")
    for t in nlp_base(clauses[4])[:12]:
        print(f"  {t.text:12s}{t.pos_:8s}{t.lemma_:12s}{t.dep_:10s}")
    print("  Noun chunks:", [c.text for c in nlp_base(clauses[4]).noun_chunks])

    print("\n" + "=" * 72, "\nD. PRETRAINED NER vs OUR HYBRID (clause 2)\n" + "=" * 72)
    print("  Pretrained only:", [(e.text, e.label_) for e in nlp_base(clauses[1]).ents])
    print("  Hybrid (rules) :", [(e.text, e.label_) for e in nlp(clauses[1]).ents])

    print("\n" + "=" * 72, "\nE. ENTITIES + EXTRACTED FACTS PER CLAUSE\n" + "=" * 72)
    for i, c in enumerate(clauses, 1):
        ents = [f"{e.label_}:{e.text}" for e in nlp(c).ents if e.label_ not in ("PARTY",)]
        print(f"\nClause {i}: {c[:70]}{'...' if len(c) > 70 else ''}")
        print("   entities:", ents)
        fa = extract_facts(c); print("   facts   :", {k: v for k, v in fa.items() if v})
