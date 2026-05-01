from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import csv
import openpyxl

app = FastAPI()

# static フォルダをマウント
app.mount("/static", StaticFiles(directory="static"), name="static")


# -----------------------------
#  HTML ページルーティング
# -----------------------------
@app.get("/")
def root():
    return FileResponse("static/login.html")

@app.get("/login.html")
def login_page():
    return FileResponse("static/login.html")

@app.get("/register.html")
def register_page():
    return FileResponse("static/register.html")

@app.get("/mypage.html")
def mypage_page():
    return FileResponse("static/mypage.html")

@app.get("/quiz.html")
def quiz_page():
    return FileResponse("static/quiz.html")

@app.get("/category.html")
def category_page():
    return FileResponse("static/category.html")

@app.get("/level.html")
def level_page():
    return FileResponse("static/level.html")

@app.get("/cms.html")
def cms_page():
    return FileResponse("static/cms.html")


# -----------------------------
#  データベース初期化
# -----------------------------
def init_db():
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # ユーザー
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # 問題
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            level TEXT,
            question TEXT,
            choice1 TEXT,
            choice2 TEXT,
            choice3 TEXT,
            choice4 TEXT,
            answer INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()


# -----------------------------
#  API：ユーザー登録
# -----------------------------
@app.post("/api/register")
def register(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return {"status": "ok"}
    except sqlite3.IntegrityError:
        return {"status": "error", "message": "ユーザー名は既に存在します"}
    finally:
        conn.close()


# -----------------------------
#  API：ログイン
# -----------------------------
@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()

    conn.close()

    if user:
        return {"status": "ok"}
    else:
        return {"status": "error", "message": "ユーザー名またはパスワードが違います"}


# -----------------------------
#  API：問題取得
# -----------------------------
@app.post("/api/get_questions")
def get_questions(category: str = Form(...), level: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM questions WHERE category=? AND level=?", (category, level))
    rows = cur.fetchall()

    conn.close()

    questions = []
    for r in rows:
        questions.append({
            "id": r[0],
            "category": r[1],
            "level": r[2],
            "question": r[3],
            "choice1": r[4],
            "choice2": r[5],
            "choice3": r[6],
            "choice4": r[7],
            "answer": r[8]
        })

    return {"status": "ok", "questions": questions}


# -----------------------------
#  API：CMS CSV/Excel アップロード
# -----------------------------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    filename = file.filename

    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # CSV
    if filename.endswith(".csv"):
        content = await file.read()
        text = content.decode("utf-8").splitlines()
        reader = csv.reader(text)

        for row in reader:
            cur.execute("""
                INSERT INTO questions (category, level, question, choice1, choice2, choice3, choice4, answer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

    # Excel
    elif filename.endswith(".xlsx"):
        wb = openpyxl.load_workbook(file.file)
        ws = wb.active

        for row in ws.iter_rows(values_only=True):
            cur.execute("""
                INSERT INTO questions (category, level, question, choice1, choice2, choice3, choice4, answer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

    conn.commit()
    conn.close()

    return {"status": "ok"}
