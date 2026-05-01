from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
import csv
import openpyxl

# ============================
# 設定
# ============================
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

app = FastAPI()

# CORS（必要なら）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# DB 設定
# ============================
engine = create_engine("sqlite:///quiz.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ============================
# モデル
# ============================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    category = Column(String)
    level = Column(String)
    type = Column(String)
    question = Column(String)
    choices = Column(String)
    answer = Column(String)

Base.metadata.create_all(bind=engine)

# ============================
# 認証
# ============================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(lambda: None), db: Session = Depends(get_db)):
    if token is None:
        raise HTTPException(status_code=401, detail="Token required")

    try:
        payload = jwt.decode(token.replace("Bearer ", ""), SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# ============================
# API
# ============================

@app.post("/register")
def register(data: dict, db: Session = Depends(get_db)):
    username = data["username"]
    password = pwd_context.hash(data["password"])

    if db.query(User).filter(User.username == username).first():
        return {"status": "exists"}

    db.add(User(username=username, password=password))
    db.commit()
    return {"status": "ok"}

@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    username = data["username"]
    password = data["password"]

    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password):
        return {"status": "error"}

    token = create_token({"sub": username})
    return {"status": "ok", "token": token}

# ============================
# CMS：問題追加
# ============================
@app.post("/cms/add")
def add_question(data: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = Question(**data)
    db.add(q)
    db.commit()
    return {"status": "added"}

# ============================
# CMS：問題一覧
# ============================
@app.get("/cms/list")
def list_questions(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Question).all()

# ============================
# CMS：編集
# ============================
@app.post("/cms/edit")
def edit_question(data: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == data["id"]).first()
    if not q:
        return {"status": "notfound"}

    q.category = data["category"]
    q.level = data["level"]
    q.type = data["type"]
    q.question = data["question"]
    q.choices = data["choices"]
    q.answer = data["answer"]

    db.commit()
    return {"status": "edited"}

# ============================
# CMS：削除
# ============================
@app.post("/cms/delete")
def delete_question(data: dict, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == data["id"]).first()
    if q:
        db.delete(q)
        db.commit()
    return {"status": "deleted"}

# ============================
# CSV / Excel インポート
# ============================
@app.post("/cms/import")
def import_questions(file: UploadFile = File(...), current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filename = file.filename.lower()

    # CSV
    if filename.endswith(".csv"):
        content = file.file.read().decode("utf-8").splitlines()
        reader = csv.reader(content)
        next(reader)

        for row in reader:
            category, level, qtype, question, choices, answer = row
            db.add(Question(
                category=category,
                level=level,
                type=qtype,
                question=question,
                choices=choices,
                answer=answer
            ))
        db.commit()
        return {"status": "imported", "type": "csv"}

    # Excel
    elif filename.endswith(".xlsx"):
        wb = openpyxl.load_workbook(file.file)
        ws = wb.active

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue
            category, level, qtype, question, choices, answer = row
            db.add(Question(
                category=category,
                level=level,
                type=qtype,
                question=question,
                choices=choices,
                answer=answer
            ))
        db.commit()
        return {"status": "imported", "type": "excel"}

    return {"status": "error", "message": "CSV または Excel(.xlsx) のみ対応"}

# ============================
# 静的ファイル
# ============================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================
# トップページ（ここが重要）
# ============================
@app.get("/")
def root():
    return FileResponse("static/login.html")
