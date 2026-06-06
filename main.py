import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

import models
import schemas
import crud
from database import engine, get_db

load_dotenv()

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", FRONTEND_URL).split(",") if origin.strip()]

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Chatbot API", lifespan=lifespan)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "BACKEND_URL": BACKEND_URL})

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"database": "ok"}
    except Exception as e:
        return {"database": "error", "details": str(e)}


@app.get("/test-ai")
async def test_ai():
    if not OPENROUTER_API_KEY:
        return {"ai": "error", "details": "OPENROUTER_API_KEY not configured"}
        
    body = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Just reply with the single word: running"}]
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json=body,
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            # Clean up the response in case the AI adds punctuation
            ai_response = data["choices"][0]["message"]["content"].strip().lower()
            return {"ai": ai_response}
    except Exception as e:
        return {"ai": "error", "details": str(e)}


@app.post("/conversations", response_model=schemas.ConversationRead)
def create_conversation(payload: schemas.ConversationCreate, db: Session = Depends(get_db)):
    return crud.create_conversation(db, payload)


@app.get("/conversations", response_model=list[schemas.ConversationRead])
def list_conversations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.list_conversations(db, skip, limit)


@app.get("/conversations/{conversation_id}", response_model=schemas.ConversationRead)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    obj = crud.get_conversation(db, conversation_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return obj


@app.patch("/conversations/{conversation_id}", response_model=schemas.ConversationRead)
def update_conversation(conversation_id: int, payload: schemas.ConversationUpdate, db: Session = Depends(get_db)):
    obj = crud.update_conversation(db, conversation_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return obj


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_conversation(db, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.post("/conversations/{conversation_id}/messages", response_model=schemas.MessageRead)
def add_message(conversation_id: int, payload: schemas.MessageCreate, db: Session = Depends(get_db)):
    conv = crud.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return crud.create_message(db, conversation_id, payload)


@app.post("/chat")
async def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    conversation_id = payload.conversation_id
    if conversation_id:
        conv = crud.get_conversation(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = [{"role": m.role, "content": m.content} for m in conv.messages]
    else:
        conv = crud.create_conversation(
            db, schemas.ConversationCreate(title=payload.message[:50], model=payload.model)
        )
        conversation_id = conv.id
        history = []

    crud.create_message(db, conversation_id, schemas.MessageCreate(role="user", content=payload.message))

    messages = history + [{"role": "user", "content": payload.message}]
    body = {"model": payload.model or "openai/gpt-4o-mini", "messages": messages}

    async with httpx.AsyncClient() as client:
        r = await client.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()

    assistant_text = data["choices"][0]["message"]["content"]
    crud.create_message(db, conversation_id, schemas.MessageCreate(role="assistant", content=assistant_text))
    return {"conversation_id": conversation_id, "response": assistant_text}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
