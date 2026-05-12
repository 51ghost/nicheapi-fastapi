from fastapi import FastAPI, Query, Header, HTTPException, Request
from supabase import create_client
import os, hashlib, json
from datetime import datetime

# Lazily initialized Supabase client
_sb = None
_INTERNAL_KEY = ""

def _get_supabase():
    global _sb
    if _sb is not None:
        return _sb
    # Strip /rest/v1/ suffix from SUPABASE_URL if present
    # The supabase client library appends it automatically
    raw_url = os.environ.get("SUPABASE_URL", "")
    raw_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not raw_url or not raw_key:
        return None
    url = raw_url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-8]
    _sb = create_client(url, raw_key)
    return _sb

_INTERNAL_KEY = os.environ.get("INTERNAL_API_KEY", "")

app = FastAPI(title="NicheAPI Scout", version="2.0.0")

def require_auth(x_api_key: str = Header(None)):
    if x_api_key != _INTERNAL_KEY:
        raise HTTPException(status_code=401,
                            detail="Invalid API key")

# ── GET /v1/ideas ─────────────────────────────────────────────
@app.get("/v1/ideas")
async def get_ideas(
    category: str = Query(None),
    min_score: int = Query(1, ge=1, le=10),
    complexity: str = Query(None),
    limit: int = Query(10, le=50),
    offset: int = 0,
    x_api_key: str = Header(None)
):
    require_auth(x_api_key)
    sb = _get_supabase()
    if not sb:
        raise HTTPException(503, "Supabase not configured")
    q = sb.table("api_ideas").select(
        "id,suggested_api_name,problem_statement,"
        "niche_category,target_audience,monetization_score,"
        "estimated_mrr_usd,build_complexity,"
        "estimated_build_hours,competitor_count,"
        "tags,upvotes,created_at"
    ).gte("monetization_score", min_score)\
     .order("monetization_score", desc=True)\
     .range(offset, offset + limit - 1)
    if category:
        q = q.eq("niche_category", category)
    if complexity:
        q = q.eq("build_complexity", complexity)
    r = q.execute()
    return {"success": True, "count": len(r.data),
            "data": r.data,
            "timestamp": datetime.utcnow().isoformat()}

# ── GET /v1/ideas/{id}/spec ────────────────────────────────────
@app.get("/v1/ideas/{idea_id}/spec")
async def get_spec(idea_id: str,
                   x_api_key: str = Header(None)):
    require_auth(x_api_key)
    sb = _get_supabase()
    if not sb:
        raise HTTPException(503, "Supabase not configured")
    try:
        r = sb.table("api_ideas")\
              .select("id,suggested_api_name,openapi_spec")\
              .eq("id", idea_id).single().execute()
    except Exception:
        raise HTTPException(404, "Idea not found")
    if not r.data:
        raise HTTPException(404, "Idea not found")
    return {"id": r.data["id"],
            "name": r.data["suggested_api_name"],
            "spec": r.data["openapi_spec"]}

# ── GET /v1/ideas/{id}/stub ────────────────────────────────────
@app.get("/v1/ideas/{idea_id}/stub")
async def get_stub(idea_id: str,
                   x_api_key: str = Header(None)):
    require_auth(x_api_key)
    sb = _get_supabase()
    if not sb:
        raise HTTPException(503, "Supabase not configured")
    try:
        r = sb.table("api_ideas")\
              .select("id,suggested_api_name,code_stub")\
              .eq("id", idea_id).single().execute()
    except Exception:
        raise HTTPException(404, "Idea not found")
    if not r.data:
        raise HTTPException(404, "Idea not found")
    return {"id": r.data["id"],
            "name": r.data["suggested_api_name"],
            "code": r.data["code_stub"]}

# ── POST /v1/ideas/{id}/upvote ─────────────────────────────────
@app.post("/v1/ideas/{idea_id}/upvote")
async def upvote(idea_id: str,
                 x_api_key: str = Header(None)):
    require_auth(x_api_key)
    sb = _get_supabase()
    if not sb:
        raise HTTPException(503, "Supabase not configured")
    r = sb.rpc("increment_upvote",
               {"row_id": idea_id}).execute()
    return {"success": True, "id": idea_id}

# ── GET /health ────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok",
            "ts": datetime.utcnow().isoformat()}
