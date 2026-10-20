from sqlalchemy.orm import Session
import models, schemas


def create_conversation(db: Session, obj: schemas.ConversationCreate):
    db_obj = models.Conversation(**obj.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_conversation(db: Session, conversation_id: int):
    return db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()


def list_conversations(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Conversation)
        .order_by(models.Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_conversation(db: Session, conversation_id: int, obj: schemas.ConversationUpdate):
    db_obj = get_conversation(db, conversation_id)
    if not db_obj:
        return None
    for field, value in obj.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_conversation(db: Session, conversation_id: int):
    db_obj = get_conversation(db, conversation_id)
    if not db_obj:
        return False
    db.delete(db_obj)
    db.commit()
    return True


def create_message(db: Session, conversation_id: int, obj: schemas.MessageCreate):
    db_obj = models.Message(conversation_id=conversation_id, **obj.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def list_messages(db: Session, conversation_id: int):
    return (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at)
        .all()
    )

# qa: live build-log check 1792493323
