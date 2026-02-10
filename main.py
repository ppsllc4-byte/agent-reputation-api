from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import os
from dotenv import load_dotenv
from datetime import datetime
from database import db
from payment import PaymentProcessor, verify_payment_token
from api_keys import api_key_manager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

app = FastAPI(
    title="Agent Reputation API",
    description="Trust and reputation scoring for AI agents",
    version="2.0.0"
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRegistration(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    contact: Optional[str] = Field(None, max_length=200)

class InteractionRecord(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    success: bool
    response_time: Optional[float] = Field(0.0, ge=0, le=300)
    details: Optional[Dict] = {}

class ReputationResponse(BaseModel):
    agent_id: str
    reputation_score: int
    trust_level: str
    total_interactions: int
    successful_interactions: int
    failed_interactions: int
    success_rate: float
    average_response_time: float
    uptime_percentage: float
    registered_at: str
    last_seen: str

@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request):
    return {
        "message": "Agent Reputation API - Credit Score for AI Agents",
        "version": "2.0.0",
        "security": "API key authentication + rate limiting enabled",
        "endpoints": {
            "register": "POST /agent/register",
            "lookup": "GET /agent/reputation/{agent_id}",
            "record": "POST /agent/interaction",
            "leaderboard": "GET /leaderboard",
            "credits": "GET /credits/check"
        }
    }

@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational",
        "version": "2.0.0",
        "security": "enabled"
    }

@app.post("/agent/register")
@limiter.limit("20/minute")
async def register_agent(request: Request, registration: AgentRegistration):
    """Register a new agent (FREE)"""
    try:
        metadata = {
            "name": registration.name,
            "description": registration.description,
            "contact": registration.contact
        }
        result = await db.register_agent(registration.agent_id, metadata)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {
            "status": "registered",
            "agent_id": registration.agent_id,
            "reputation_score": result["reputation_score"],
            "trust_level": result["trust_level"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.get("/agent/reputation/{agent_id}", response_model=ReputationResponse)
@limiter.limit("60/minute")
async def get_reputation(
    request: Request,
    agent_id: str,
    authorization: Optional[str] = Header(None)
):
    """Get reputation score (5 credits = $0.005)"""
    
    is_authorized = await verify_payment_token(authorization, cost_in_credits=5)
    
    if not is_authorized:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Payment required",
                "message": "Invalid API key or insufficient credits",
                "pricing": "$0.005 per lookup (5 credits)",
                "get_credits": "/purchase"
            }
        )
    
    try:
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        success_rate = 0.0
        if agent["total_interactions"] > 0:
            success_rate = agent["successful_interactions"] / agent["total_interactions"]
        
        return ReputationResponse(
            agent_id=agent["agent_id"],
            reputation_score=agent["reputation_score"],
            trust_level=agent["trust_level"],
            total_interactions=agent["total_interactions"],
            successful_interactions=agent["successful_interactions"],
            failed_interactions=agent["failed_interactions"],
            success_rate=round(success_rate, 2),
            average_response_time=round(agent["average_response_time"], 2),
            uptime_percentage=agent["uptime_percentage"],
            registered_at=agent["registered_at"],
            last_seen=agent["last_seen"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")

@app.post("/agent/interaction")
@limiter.limit("100/minute")
async def record_interaction(request: Request, interaction: InteractionRecord):
    """Record an interaction (FREE)"""
    try:
        result = await db.record_interaction(
            agent_id=interaction.agent_id,
            success=interaction.success,
            response_time=interaction.response_time or 0.0,
            details=interaction.details
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {
            "status": "recorded",
            "agent_id": interaction.agent_id,
            "new_reputation_score": result["reputation_score"],
            "trust_level": result["trust_level"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recording failed: {str(e)}")

@app.get("/leaderboard")
@limiter.limit("100/minute")
async def get_leaderboard(request: Request, limit: int = Query(default=10, le=50)):
    """Get top agents (FREE)"""
    try:
        leaders = await db.get_leaderboard(limit)
        return {
            "leaderboard": [
                {
                    "rank": idx + 1,
                    "agent_id": agent["agent_id"],
                    "reputation_score": agent["reputation_score"],
                    "trust_level": agent["trust_level"],
                    "total_interactions": agent["total_interactions"]
                }
                for idx, agent in enumerate(leaders)
            ],
            "total_agents": len(leaders)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leaderboard failed: {str(e)}")

@app.get("/stats")
@limiter.limit("100/minute")
async def get_stats(request: Request):
    """Platform statistics (FREE)"""
    try:
        all_agents = await db.get_all_agents()
        total_agents = len(all_agents)
        verified_agents = len([a for a in all_agents if a["trust_level"] == "verified"])
        trusted_agents = len([a for a in all_agents if a["trust_level"] in ["verified", "trusted"]])
        total_interactions = sum(a["total_interactions"] for a in all_agents)
        avg_reputation = sum(a["reputation_score"] for a in all_agents) / total_agents if total_agents > 0 else 0
        return {
            "total_agents": total_agents,
            "verified_agents": verified_agents,
            "trusted_agents": trusted_agents,
            "total_interactions": total_interactions,
            "average_reputation": round(avg_reputation, 1)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

@app.get("/credits/check")
@limiter.limit("100/minute")
async def check_credits(request: Request, authorization: Optional[str] = Header(None)):
    """Check remaining credits"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization.replace("Bearer ", "").strip()
    credits = api_key_manager.get_credits(api_key)
    if credits is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {
        "credits_remaining": credits,
        "lookups_available": credits // 5,
        "status": "active" if credits >= 5 else "low_credits"
    }

@app.post("/admin/create-api-key")
async def create_api_key(
    user_email: str,
    credits: int = 1000,
    admin_secret: str = Header(None, alias="X-Admin-Secret")
):
    """Admin: Create API key"""
    if admin_secret != os.getenv("API_SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Forbidden")
    api_key = api_key_manager.create_key(user_email, credits)
    return {
        "status": "success",
        "api_key": api_key,
        "user_email": user_email,
        "credits": credits,
        "lookups": credits // 5,
        "message": "SAVE THIS KEY!"
    }

@app.post("/purchase")
@limiter.limit("10/minute")
async def purchase_credits(request: Request, credits: int = 1000, email: Optional[str] = None):
    """Purchase reputation lookup credits"""
    if credits < 5 or credits > 100000:
        raise HTTPException(status_code=400, detail="Credits must be between 5 and 100,000")
    base_url = os.getenv("BASE_URL", "https://agent-reputation-api-production.up.railway.app")
    session = await PaymentProcessor.create_checkout_session(
        success_url=f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/payment/cancel",
        quantity=credits
    )
    return {
        "checkout_url": session['url'],
        "session_id": session['session_id'],
        "total_amount": session['amount_total'],
        "credits": credits,
        "lookups": credits // 5
    }

@app.get("/payment/success")
async def payment_success(session_id: str):
    try:
        payment_info = await PaymentProcessor.verify_session(session_id)
        user_email = payment_info['customer_email'] or 
f"user_{session_id[:8]}@stripe.customer"
        credits = payment_info['credits']
        api_key = api_key_manager.create_key(user_email, credits)
        
        return {
            "status": "success",
            "message": "SAVE THIS API KEY! It will not be shown again.",
            "api_key": api_key,
            "credits": credits,
            "lookups_available": credits // 5,
            "user_email": user_email,
            "amount_paid": f"${payment_info['amount_total']:.2f}",
            "instructions": {
                "step_1": "Copy the api_key above",
                "step_2": "Use it in Authorization header",
                "example": f"Authorization: Bearer {api_key}"
            },
            "docs": 
"https://agent-reputation-api-production.up.railway.app/docs"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing 
failed: {str(e)}")

@app.get("/payment/cancel")
async def payment_cancel():
    return {"status": "cancelled", "message": "Payment cancelled"}

@app.get("/pricing")
@limiter.limit("100/minute")
async def get_pricing(request: Request):
    return {
        "lookup_price": "$0.005 per lookup (5 credits)",
        "registration": "FREE",
        "interaction_recording": "FREE",
        "bulk_pricing": {
            "1000_credits": "$1.00 (200 lookups)",
            "10000_credits": "$10.00 (2000 lookups)",
            "100000_credits": "$100.00 (20000 lookups)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
