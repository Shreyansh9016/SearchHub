import argparse
import random

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.security import hash_password
from app.models import Bookmark, Document, DocumentTag, SearchEvent, Tag, User
from scripts.seed_data import TOPICS, generate_articles


def _get_or_create_user(db, name, email, password, role):
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(name=name, email=email, password_hash=hash_password(password), role=role)
        db.add(user)
        db.flush()
    return user


def main(reset: bool = False, count: int = 520):
    db = SessionLocal()
    try:
        if reset:
            for model in (SearchEvent, Bookmark, DocumentTag, Document, Tag):
                db.execute(delete(model))
            db.commit()
        elif db.scalar(select(func.count()).select_from(Document)):
            print("Documents already exist; use --reset to re-seed.")
            return

        admin = _get_or_create_user(db, "Admin", "admin@searchhub.dev", "admin12345", "admin")
        users = [_get_or_create_user(db, "Demo User", "user@searchhub.dev", "user12345", "user")]
        for i in range(1, 6):
            users.append(_get_or_create_user(db, f"Reader {i}", f"reader{i}@searchhub.dev", "reader12345", "user"))

        tags = {name: Tag(name=name) for name in TOPICS}
        db.add_all(tags.values())
        db.flush()

        docs = []
        for a in generate_articles(count):
            doc = Document(
                title=a["title"], body=a["body"], author_id=admin.id, status="indexed",
                created_at=a["created_at"], updated_at=a["created_at"],
                tags=[tags[t] for t in a["tags"]],
            )
            docs.append(doc)
        db.add_all(docs)
        db.flush()

        rng = random.Random(7)
        seen = set()
        for _ in range(150):
            user, doc = rng.choice(users), rng.choice(docs)
            if (user.id, doc.id) in seen:
                continue
            seen.add((user.id, doc.id))
            db.add(Bookmark(user_id=user.id, document_id=doc.id))
        db.commit()
        print(f"Seeded {len(docs)} documents, {len(tags)} tags, {len(users) + 1} users, {len(seen)} bookmarks.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--count", type=int, default=520)
    args = parser.parse_args()
    main(reset=args.reset, count=args.count)
