"""
STEP 2: Text preprocessing with NLTK (Rental Agreement Risk Analyzer)
Pipeline: lowercase -> regex normalisation -> tokenization -> stop-word removal
          (keeping legal negations) -> stemming vs lemmatization -> cleaned text
"""
import re
import pandas as pd
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer

# ---------- Setup ----------
nltk.download("punkt", quiet=True); nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True); nltk.download("wordnet", quiet=True)

# KEY IDEA: normal stop-word lists delete words like "no", "not", "without".
# In a contract, "may evict WITHOUT notice" is very different from "may evict with notice".
# So we protect these words from removal.
KEEP = {"no", "not", "nor", "never", "without", "before", "after", "only", "against"}
STOP = set(stopwords.words("english")) - KEEP

stemmer = PorterStemmer()
lemmatizer = WordNetLemmatizer()


def normalise(text: str) -> str:
    """Regex-based cleaning. We replace values with placeholder tokens instead of
    deleting them, because 'a money amount is deducted' still carries meaning."""
    t = text.lower()                                              # 1. lowercase
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)                  # 2. remove URLs
    t = re.sub(r"(rs\.?|inr|₹)\s*[\d,]+(\.\d+)?", " moneyamt ", t)  # 3. Rs. 50,000 -> moneyamt
    t = re.sub(r"\d+(\.\d+)?\s*(percent|%)", " percentval ", t)   # 4. 5 percent -> percentval
    t = re.sub(r"\b\d+\b", " numval ", t)                         # 5. other numbers -> numval
    t = re.sub(r"[^a-z\s]", " ", t)                               # 6. remove punctuation/symbols
    t = re.sub(r"\s+", " ", t).strip()                            # 7. collapse spaces
    return t


def preprocess(text: str, use_lemma: bool = True) -> str:
    t = normalise(text)
    tokens = word_tokenize(t)                                     # tokenization
    tokens = [w for w in tokens if w not in STOP and len(w) > 1]  # stop-word removal
    if use_lemma:
        tokens = [lemmatizer.lemmatize(w, pos="v") for w in tokens]  # lemmatize as verb ("charged"->"charge")
        tokens = [lemmatizer.lemmatize(w, pos="n") for w in tokens]  # then as noun ("deductions"->"deduction")
    else:
        tokens = [stemmer.stem(w) for w in tokens]
    return " ".join(tokens)


if __name__ == "__main__":
    df = pd.read_csv("clauses.csv")
    sample = df.loc[4, "clause_text"]
    rs_clause = df.loc[0, "clause_text"]

    print("=" * 70, "\nSTAGE-BY-STAGE DEMO ON ONE CLAUSE\n", "=" * 70)
    print("ORIGINAL        :", sample)
    print("\n1. SENTENCE TOKENS:", len(sent_tokenize(sample)), "sentence(s)")
    print("   NOTE: on a clause containing 'Rs.' the sentence tokenizer finds",
          len(sent_tokenize(rs_clause)), "sentences (wrong! 'Rs.' is read as a full stop).")
    print("   -> we will fix this with a custom clause splitter in Step 3.")
    norm = normalise(sample)
    print("2. AFTER REGEX  :", norm)
    toks = word_tokenize(norm)
    print("3. WORD TOKENS  :", toks)
    no_stop = [w for w in toks if w not in STOP and len(w) > 1]
    print("4. STOP REMOVED :", no_stop)
    print("   removed words:", [w for w in toks if w in stopwords.words('english') and w not in STOP],
          "<- protected (kept)")
    print("5a. STEMMING    :", [stemmer.stem(w) for w in no_stop])
    print("5b. LEMMATIZED  :", preprocess(sample).split())

    print("\n" + "=" * 70, "\nSTEMMING vs LEMMATIZATION (why we chose lemmatization)\n", "=" * 70)
    for w in ["deductions", "charged", "terminated", "evicting", "premises", "responsibility"]:
        print(f"{w:15s} stem -> {stemmer.stem(w):12s} lemma(v) -> {lemmatizer.lemmatize(w, 'v'):12s} lemma(n) -> {lemmatizer.lemmatize(w, 'n')}")

    # Apply to the whole dataset and save
    df["clean_text"] = df["clause_text"].apply(preprocess)
    df["n_tokens_before"] = df["clause_text"].apply(lambda s: len(word_tokenize(s)))
    df["n_tokens_after"] = df["clean_text"].apply(lambda s: len(s.split()))
    df.to_csv("clauses_clean.csv", index=False)

    print("\n" + "=" * 70, "\nDATASET SUMMARY\n", "=" * 70)
    print("Clauses:", len(df))
    print("Avg tokens before: %.1f | after: %.1f" % (df.n_tokens_before.mean(), df.n_tokens_after.mean()))
    print("\nClause type counts:\n", df.clause_type.value_counts().to_string())
    print("\nRisk level counts:\n", df.risk_level.value_counts().to_string())
    print("\nSample cleaned clauses:")
    print(df[["clause_text", "clean_text"]].head(3).to_string(max_colwidth=75))
