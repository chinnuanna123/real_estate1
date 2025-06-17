
# 🏡 AI Home Buying Assistant

This project is an end-to-end AI-driven assistant that helps users find, evaluate, and make decisions when buying a home. It integrates property search, negotiation simulation, mortgage evaluation, legal guidance, and marketing descriptions into a conversational interface.

---

## 📁 Project Structure

```
AI home buying-copy/
├── main.py                     # FastAPI entrypoint
├── package.json               # React frontend dependency manifest
├── requirements.txt           # Python backend dependencies
├── agents/
│   └── home_buying_agent.py   # Central agent logic coordinating modules
├── data/
│   ├── preferences.json
│   ├── properties.json
│   └── selected_properties.json
├── data_ingest/
│   └── mock_scraper.py        # Fake scraper simulating property data
├── modules/
│   ├── legal_guidance.py
│   ├── marketing_description.py
│   ├── mortgage_recommendation.py
│   ├── negotiation.py
│   ├── neighborhood_insights.py
│   ├── preference_manager.py
│   ├── property_search.py
│   └── selected_properties_manager.py
├── public/
│   ├── index.html
│   └── manifest.json
├── routes/
│   └── home_buying_routes.py  # API routes for frontend-backend interaction
├── src/
│   ├── App.css
│   ├── App.tsx                # Main frontend UI in React
│   └── index.tsx
├── tools/
│   ├── google_search.py       # Web search or scraping logic
│   └── mortgage_utils.py
├── utils/
│   └── llm_connector.py       # Interface for connecting to LLMs
```

---

## ⚙️ Backend Overview

- **Framework**: FastAPI
- **Key Components**:
  - `home_buying_agent.py`: Orchestrates AI agent workflows like parsing intent, property search, and connecting with domain-specific modules.
  - Modules:
    - `negotiation.py`: Simulates buyer-seller negotiation scenarios.
    - `mortgage_recommendation.py`: Suggests suitable mortgage plans.
    - `legal_guidance.py`: Provides legal document insights and guidance.
    - `neighborhood_insights.py`: Generates neighborhood lifestyle and investment info.
    - `marketing_description.py`: Crafts ad-like descriptions of properties.
  - `mock_scraper.py`: Generates dummy property listings for testing.

---

## 💬 Frontend Overview

- **Framework**: React (TypeScript)
- **Entry Point**: `App.tsx`
- Displays chat UI, property cards, and user interactions.
- Connects to backend APIs to receive search results, insights, and agent responses.

---

## 🧠 Intelligence Layer

- Powered by an `LLMConnector` (`utils/llm_connector.py`)
- Uses chat history and context to enhance prompts.
- Prompts are domain-specific: negotiation, legal, mortgage, marketing, etc.

---

## 🔌 API Routes

Defined in `routes/home_buying_routes.py`, including:
- `/process_query`: Parse user query and return assistant response.
- `/select_property`: Track user's selected properties.
- `/selected_properties/{user_id}`: Get a user's current selected list.
- `/update_property_status`: Change status like 'shortlisted', 'visited', etc.
- `/selection_insights/{user_id}`: Provide insight into buyer preferences.

---

## 📦 Setup Instructions

1. **Backend**
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

2. **Frontend**
```bash
cd AI home buying-copy
npm install
npm start
```

---

## 👨‍💻 Author Notes

This is a modular, extensible architecture perfect for building agentic AI assistants in the real estate domain. Built using Python 3.11 and React TypeScript.

