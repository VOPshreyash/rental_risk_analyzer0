"""
app.py — FastAPI backend for Rental Agreement Risk Analyzer
Deploy to Hugging Face Spaces (Docker SDK, port 7860)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn

# ── Import engine (trains models at startup) ──────────────────────────────────
from engine import analyze_form, analyze_text

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Rental Agreement Risk Analyzer API",
    description="Pune rental agreement risk analysis using hybrid NLP (rules + ML)",
    version="1.0.0",
)

# Allow frontend (Vercel) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your Vercel URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────
class FormRequest(BaseModel):
    area:    str   = Field(..., example="kothrud")
    bhk:     int   = Field(..., ge=1, le=3, example=2)
    months:  int   = Field(11, ge=1, le=120)
    mode:    str   = Field("Fixed rent")          # "Fixed rent" | "Staged rent"
    rent:    int   = Field(..., ge=1000, example=29000)
    rent2:   int   = Field(0)
    m1:      int   = Field(6)
    dep:     int   = Field(..., ge=0, example=58000)
    deptype: str   = Field("Refundable")          # "Refundable" | "Non-refundable"
    maint:   str   = Field("licensor")            # "licensor" | "licensee"
    lock:    int   = Field(0, ge=0)
    lockwho: str   = Field("both")                # "both" | "licensee"
    esc:     float = Field(0.0, ge=0)
    fee:     int   = Field(0, ge=0)
    grace:   int   = Field(7, ge=0)
    refund:  int   = Field(0, ge=0)

class TextRequest(BaseModel):
    text:     str = Field(..., min_length=50)
    area:     str = Field(..., example="kothrud")
    bhk:      int = Field(..., ge=1, le=3, example=2)

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Rental Risk Analyzer API is running"}

@app.post("/api/analyze/form")
def analyze_form_endpoint(req: FormRequest):
    try:
        result = analyze_form(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze/text")
def analyze_text_endpoint(req: TextRequest):
    try:
        result = analyze_text(req.text, req.area, req.bhk)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
