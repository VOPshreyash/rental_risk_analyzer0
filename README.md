# Rental Agreement Risk Analyzer (Pune) — NLP Lab Project

## What is in this folder
| Path | What it is |
|---|---|
| `Rental_Risk_Analyzer_NLP.ipynb` | **The main deliverable.** Upload to Google Colab and Run all. Self-contained (steps 0-6). |
| `PROJECT_CONTEXT.md` | Full project memory: decisions, rules, results, to-do. **Paste/upload this into a new Claude chat to continue.** |
| `scripts/` | Source code + data used to build the notebook (run from inside this folder). |
| `reference/` | Official Maharashtra IGR Leave & License form (PDF) and your lab manual. |

## How to run
1. Go to colab.research.google.com -> File -> Upload notebook -> choose `Rental_Risk_Analyzer_NLP.ipynb`.
2. Runtime -> Run all (about 2-3 minutes; first cell installs libraries).
3. Scroll to "LIVE DEMO" to fill the form.

## How to run scripts locally (optional)
```
pip install nltk pandas spacy scikit-learn matplotlib ipywidgets
python -m spacy download en_core_web_sm
cd scripts
python make_dataset.py
python step2_preprocessing.py
python step3_ner.py
python build_nb.py      # regenerates the notebook from steps45.py / steps6.py
```
