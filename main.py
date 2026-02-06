from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv
from datetime import datetime
from database import db
from payment import PaymentProcessor, verify_payment_token

load_dotenv()

app = FastAPI(
    title="Agent Reputation API",
    description="Trust and reputation scoring for AI agents - the credit score system for autonomous agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class AgentRegistration(BaseModel):
    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    contact: Optional[str] = None

class InteractionRecord(BaseModel):
    agent_id: str
    success: bool
    response_time: Optional[float] = 0.0
    details: Optional[Dict[str, Any]] = None

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

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Agent Reputation API - Credit Score for AI Agents",
        "version": "1.0.0",
        "endpoints": {
            "register": "POST /agent/register",
            "lookup": "GET /agent/reputation/{agent_id}",
            "record": "POST /agent/interaction",
            "leaderboard": "GET /leaderboard",
            "purchase": "POST /purchase",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational"
    }

@app.post("/agent/register")
async def register_agent(registration: AgentRegistration):
    """
    Register a new agent in the reputation system
    
    Free to register - builds your reputation over time
    """
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
            "trust_level": result["trust_level"],
            "message": "Agent registered successfully. Start building your reputation!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.get("/agent/reputation/{agent_id}", response_model=ReputationResponse)
async def get_reputation(
    agent_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get reputation score for an agent
    
    Requires payment: $0.005 per lookup
    
    Returns:
    - Reputation score (0-100)
    - Trust level (new, moderate, trusted, verified, flagged)
    - Interaction history
    - Performance metrics
    """
    
    # Verify payment
    is_authorized = await verify_payment_token(authorization)
    
    if not is_authorized:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Payment required",
                "message": "Agent reputation lookups require payment",
                "pricing": "$0.005 per lookup",
                "get_credits": "/purchase"
            }
        )
    
    try:
        agent = await db.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(
                status_code=404, 
                detail=f"Agent '{agent_id}' not found. Register at /agent/register"
            )
        
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
async def record_interaction(
    interaction: InteractionRecord,
    authorization: Optional[str] = Header(None)
):
    """
    Record an interaction with an agent
    
    Free for registered agents to report their own interactions
    Helps build reputation over time
    
    Args:
    - agent_id: The agent that performed the action
    - success: Whether the interaction was successful
    - response_time: How long it took (seconds)
    - details: Optional metadata about the interaction
    """
    
    # For V1, allow free interaction recording
    # In V2, might require authentication to prevent spam
    
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
            "trust_level": result["trust_level"],
            "total_interactions": result["total_interactions"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recording failed: {str(e)}")

@app.get("/leaderboard")
async def get_leaderboard(limit: int = Query(default=10, le=50)):
    """
    Get top-rated agents
    
    Free endpoint - discover the most trusted agents
    """
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
async def get_stats():
    """
    Get overall platform statistics
    
    Free endpoint
    """
    try:
        all_agents = await db.get_all_agents()
        
        total_agents = len(all_agents)
        verified_agents = len([a for a in all_agents if a["trust_level"] == "verified"])
        trusted_agents = len([a for a in all_agents if a["trust_level"] in ["verified", "trusted"]])
        total_interactions = sum(a["total_interactions"] for a in all_agents)
        
        avg_reputation = 0
        if total_agents > 0:
            avg_reputation = sum(a["reputation_score"] for a in all_agents) / total_agents
        
        return {
            "total_agents": total_agents,
            "verified_agents": verified_agents,
            "trusted_agents": trusted_agents,
            "total_interactions": total_interactions,
            "average_reputation": round(avg_reputation, 1)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

@app.post("/purchase")
async def purchase_credits(credits: int = 100, email: Optional[str] = None):
    """
    Purchase reputation lookup credits
    
    Args:
    - credits: Number of lookups to purchase (default: 100)
    - email: Optional email for receipt
    
    Returns Stripe checkout URL
    """
    if credits < 1 or credits > 10000:
        raise HTTPException(status_code=400, detail="Credits must be between 1 and 10,000")
    
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
        "price_per_lookup": 0.005,
        "message": "Complete payment at checkout_url to receive your API key"
    }

@app.get("/payment/success")
async def payment_success(session_id: str):
    return {
        "status": "success",
        "message": "Payment successful! Your API key will be sent to your email.",
        "session_id": session_id,
        "next_steps": "Check your email for your API key and usage instructions"
    }

@app.get("/payment/cancel")
async def payment_cancel():
    return {
        "status": "cancelled",
        "message": "Payment was cancelled. You can try again at /purchase"
    }

@app.get("/pricing")
async def get_pricing():
    return {
        "lookup_price": "$0.005 per reputation lookup",
        "registration": "Free",
        "interaction_recording": "Free",
        "bulk_pricing": {
            "100_lookups": "$0.50",
            "1000_lookups": "$5.00",
            "10000_lookups": "$50.00"
        },
        "payment_methods": ["stripe"],
        "api_key_required": True
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
