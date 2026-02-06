import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

DB_FILE = "agents_db.json"

class AgentDatabase:
    def __init__(self):
        self.db_file = DB_FILE
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        if not os.path.exists(self.db_file):
            initial_data = {
                "agents": {},
                "interactions": []
            }
            with open(self.db_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def _read_db(self) -> Dict:
        with open(self.db_file, 'r') as f:
            return json.load(f)
    
    def _write_db(self, data: Dict):
        with open(self.db_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def register_agent(self, agent_id: str, metadata: Dict) -> Dict:
        db = self._read_db()
        
        if agent_id in db["agents"]:
            return {"error": "Agent already registered", "agent_id": agent_id}
        
        db["agents"][agent_id] = {
            "agent_id": agent_id,
            "registered_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
            "reputation_score": 50,  # Start neutral
            "trust_level": "new",
            "total_interactions": 0,
            "successful_interactions": 0,
            "failed_interactions": 0,
            "average_response_time": 0.0,
            "uptime_percentage": 100.0,
            "last_seen": datetime.utcnow().isoformat()
        }
        
        self._write_db(db)
        return db["agents"][agent_id]
    
    async def get_agent(self, agent_id: str) -> Optional[Dict]:
        db = self._read_db()
        return db["agents"].get(agent_id)
    
    async def record_interaction(
        self, 
        agent_id: str, 
        success: bool, 
        response_time: float = 0.0,
        details: Optional[Dict] = None
    ) -> Dict:
        db = self._read_db()
        
        if agent_id not in db["agents"]:
            return {"error": "Agent not registered"}
        
        # Record interaction
        interaction = {
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "response_time": response_time,
            "details": details or {}
        }
        db["interactions"].append(interaction)
        
        # Update agent stats
        agent = db["agents"][agent_id]
        agent["total_interactions"] += 1
        
        if success:
            agent["successful_interactions"] += 1
        else:
            agent["failed_interactions"] += 1
        
        # Update average response time
        if response_time > 0:
            total_time = agent["average_response_time"] * (agent["total_interactions"] - 1)
            agent["average_response_time"] = (total_time + response_time) / agent["total_interactions"]
        
        # Calculate reputation score (0-100)
        success_rate = agent["successful_interactions"] / agent["total_interactions"]
        agent["reputation_score"] = self._calculate_reputation(agent, success_rate)
        
        # Update trust level
        agent["trust_level"] = self._calculate_trust_level(agent)
        
        agent["last_seen"] = datetime.utcnow().isoformat()
        
        self._write_db(db)
        return agent
    
    def _calculate_reputation(self, agent: Dict, success_rate: float) -> int:
        base_score = success_rate * 70  # 70 points for success rate
        
        # Bonus for volume (up to 20 points)
        interaction_bonus = min(agent["total_interactions"] / 100, 1.0) * 20
        
        # Penalty for slow response (up to -10 points)
        response_penalty = 0
        if agent["average_response_time"] > 5.0:
            response_penalty = min((agent["average_response_time"] - 5.0) / 5.0, 1.0) * 10
        
        # Bonus for uptime (up to 10 points)
        uptime_bonus = (agent["uptime_percentage"] / 100) * 10
        
        score = base_score + interaction_bonus - response_penalty + uptime_bonus
        return max(0, min(100, int(score)))
    
    def _calculate_trust_level(self, agent: Dict) -> str:
        score = agent["reputation_score"]
        interactions = agent["total_interactions"]
        
        if interactions < 10:
            return "new"
        elif score >= 80 and interactions >= 100:
            return "verified"
        elif score >= 60:
            return "trusted"
        elif score >= 40:
            return "moderate"
        else:
            return "flagged"
    
    async def get_all_agents(self) -> List[Dict]:
        db = self._read_db()
        return list(db["agents"].values())
    
    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        agents = await self.get_all_agents()
        sorted_agents = sorted(agents, key=lambda x: x["reputation_score"], reverse=True)
        return sorted_agents[:limit]

# Global database instance
db = AgentDatabase()
