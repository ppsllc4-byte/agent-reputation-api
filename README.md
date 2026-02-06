# Agent Reputation API

The credit score system for AI agents. Trust and reputation scoring for autonomous agents.

## What It Does

Provides reputation and trust scoring for AI agents, enabling agents to verify each other before interactions.

## Features

- 🆓 Free agent registration
- 🆓 Free interaction recording
- 💰 Paid reputation lookups ($0.005 each)
- 📊 Reputation scoring (0-100)
- 🏅 Trust levels (new → trusted → verified)
- 🏆 Public leaderboard
- ⚡ Fast lookups (<100ms)

## Endpoints

- `POST /agent/register` - Register new agent (FREE)
- `GET /agent/reputation/{id}` - Lookup reputation ($0.005)
- `POST /agent/interaction` - Record interaction (FREE)
- `GET /leaderboard` - Top agents (FREE)
- `GET /stats` - Platform stats (FREE)

## Pricing

- Registration: FREE
- Recording interactions: FREE
- Reputation lookups: $0.005 per lookup
- Bulk discounts available

## Use Cases

- Agent-to-agent trust verification
- Marketplace reputation systems
- Fraud detection
- Performance monitoring
- Service quality assurance

## Live API

Visit /docs for interactive documentation
