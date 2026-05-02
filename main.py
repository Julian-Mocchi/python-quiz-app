from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import csv
import openpyxl
import datetime

app = FastAPI()

# static フォルダ
app.mount("/static", StaticFiles(directory="static"), name="static")

# templates フォルダ
templates = Jinja2Templates(directory="templates")


# -----------------------------
# DB 初期化
# -----------------------------
def init_db():
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            xp INTEGER DEFAULT 0
        )
    """)

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            level TEXT,
            score INTEGER,
            total INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            level TEXT,
            correct INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# HTML ページ
# -----------------------------
@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("login.html", context={"request": request})


@app.get("/login.html")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", context={"request": request})


@app.get("/register.html")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", context={"request": request})


@app.get("/category.html")
def category_page(request: Request, username: str = ""):
    return templates.TemplateResponse("category.html", context={
        "request": request,
        "username": username
    })


@app.get("/level.html")
def level_page(request: Request, username: str = "", category: str = ""):
    if username == "" or category == "":
        return templates.TemplateResponse("category.html", context={"request": request})

    return templates.TemplateResponse("level.html", context={
        "request": request,
        "username": username,
        "category": category
    })


@app.get("/quiz.html")
def quiz_page(
    request: Request,
    username: str = "",
    category: str = "",
    level: str = "",
    number: int = 1
):
    if username == "" or category == "" or level == "":
        return templates.TemplateResponse("category.html", context={"request": request})

    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT id, question, choice1, choice2, choice3, choice4, answer
        FROM questions
        WHERE category=? AND level=?
    """, (category, level))

    rows = cur.fetchall()
    total = len(rows)

    if total == 0:
        conn.close()
        return templates.TemplateResponse("quiz.html", context={
            "request": request,
            "username": username,
            "category": category,
            "level": level,
            "question": None,
            "choices": [],
            "number": 0,
            "total": 0
        })

    index = number - 1
    if index >= total:
        index = total - 1

    q = rows[index]
    question_id = q[0]
    question = q[1]
    choices = [q[2], q[3], q[4], q[5]]
    correct_answer = q[6]

    conn.close()

    return templates.TemplateResponse("quiz.html", context={
        "request": request,
        "username": username,
        "category": category,
        "level": level,
        "question_id": question_id,
        "question": question,
        "choices": choices,
        "number": number,
        "total": total,
        "correct_answer": correct_answer
    })


@app.get("/mypage.html")
def mypage_page(request: Request, username: str = ""):
    if username == "":
        return templates.TemplateResponse("login.html", context={"request": request})

    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT id, xp FROM users WHERE username=?", (username,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return templates.TemplateResponse("login.html", context={"request": request})

    user_id = user[0]
    xp = user[1]

    level = xp // 100 + 1
    next_xp = (level * 100) - xp
    badges = {1: "初心者", 2: "見習い", 3: "中級者", 4: "上級者", 5: "達人"}
    badge = badges.get(level, "達人")
    xp_bar_percent = min(100, int((xp % 100) / 100 * 100))

    categories = ["Python基礎", "Python応用"]
    levels = ["初級", "中級"]

    progress_list = []
    for cat in categories:
        for lv in levels:
            cur.execute("""
                SELECT correct, total FROM progress
                WHERE user_id=? AND category=? AND level=?
            """, (user_id, cat, lv))
            row = cur.fetchone()

            if row:
                correct, total = row
            else:
                correct, total = 0, 0

            rate = int((correct / total) * 100) if total > 0 else 0

            progress_list.append({
                "category": cat,
                "level": lv,
                "correct": correct,
                "total": total,
                "rate": rate
            })

    cur.execute("""
        SELECT created_at, category, level, score, total
        FROM scores
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))
    rows = cur.fetchall()

    score_list = []
    for r in rows:
        score_list.append({
            "date": r[0],
            "category": r[1],
            "level": r[2],
            "score": r[3],
            "total": r[4]
        })

    conn.close()

    return templates.TemplateResponse("mypage.html", context={
        "request": request,
        "username": username,
        "level": level,
        "xp": xp,
        "next_xp": next_xp,
        "badge": badge,
        "xp_bar_percent": xp_bar_percent,
        "progress_list": progress_list,
        "score_list": score_list
    })


@app.get("/cms.html")
def cms_page(request: Request):
    return templates.TemplateResponse("cms.html", context={"request": request})


# -----------------------------
# API：ユーザー登録
# -----------------------------
@app.post("/api/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    exists = cur.fetchone()

    if exists:
        conn.close()
        return templates.TemplateResponse("register.html", context={
            "request": request,
            "error": "このユーザー名はすでに使われています"
        })

    cur.execute("INSERT INTO users (username, password, xp) VALUES (?, ?, 0)", (username, password))
    conn.commit()
    conn.close()

    return templates.TemplateResponse("login.html", context={
        "request": request,
        "message": "登録が完了しました。ログインしてください。"
    })


# -----------------------------
# API：ログイン
# -----------------------------
@app.post("/api/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()

    conn.close()

    if user:
        return RedirectResponse(url=f"/mypage.html?username={username}", status_code=302)
    else:
        return templates.TemplateResponse("login.html", context={
            "request": request,
            "error": "ユーザー名またはパスワードが違います"
        })


# -----------------------------
# API：CSV アップロード
# -----------------------------
@app.post("/api/upload_csv")
def upload_csv(request: Request, file: UploadFile = File(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    content = file.file.read().decode("utf-8").splitlines()
    reader = csv.reader(content)

    count = 0
    for row in reader:
        if len(row) < 8:
            continue

        category, level, question, c1, c2, c3, c4, ans = row

        cur.execute("""
            INSERT INTO questions (category, level, question, choice1, choice2, choice3, choice4, answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, level, question, c1, c2, c3, c4, int(ans)))

        count += 1

    conn.commit()
    conn.close()

    return templates.TemplateResponse("cms.html", context={
        "request": request,
        "message": f"CSV から {count} 件の問題を追加しました。"
    })


# -----------------------------
# API：Excel アップロード
# -----------------------------
@app.post("/api/upload_excel")
def upload_excel(request: Request, file: UploadFile = File(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    wb = openpyxl.load_workbook(file.file)
    ws = wb.active

    count = 0
    for row in ws.iter_rows(values_only=True):
        if row is None or len(row) < 8:
            continue

        category, level, question, c1, c2, c3, c4, ans = row

        cur.execute("""
            INSERT INTO questions (category, level, question, choice1, choice2, choice3, choice4, answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, level, question, c1, c2, c3, c4, int(ans)))

        count += 1

    conn.commit()
    conn.close()

    return templates.TemplateResponse("cms.html", context={
        "request": request,
        "message": f"Excel から {count} 件の問題を追加しました。"
    })


# -----------------------------
# API：回答処理
# -----------------------------
@app.post("/api/answer")
def answer(
    request: Request,
    username: str = Form(...),
    category: str = Form(...),
    level: str = Form(...),
    question_id: int = Form(...),
    answer: int = Form(...),
    number: int = Form(...),
    total: int = Form(...)
):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT answer FROM questions WHERE id=?", (question_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return RedirectResponse(
            url=f"/quiz.html?username={username}&category={category}&level={level}&number={number}",
            status_code=302
        )

    correct_answer = row[0]
    is_correct = (answer == correct_answer)

    cur.execute("SELECT id, xp FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    user_id = user[0]
    xp = user[1]

    if is_correct:
        xp += 10
        cur.execute("UPDATE users SET xp=? WHERE id=?", (xp, user_id))

    cur.execute("""
        SELECT id, correct, total FROM progress
        WHERE user_id=? AND category=? AND level=?
    """, (user_id, category, level))
    prog = cur.fetchone()

    if prog:
        prog_id, correct, total_q = prog
        if is_correct:
            correct += 1
        total_q += 1
        cur.execute("""
            UPDATE progress SET correct=?, total=? WHERE id=?
        """, (correct, total_q, prog_id))
    else:
        cur.execute("""
            INSERT INTO progress (user_id, category, level, correct, total)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, category, level, 1 if is_correct else 0, 1))

    conn.commit()

    if number == total:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            SELECT correct, total FROM progress
            WHERE user_id=? AND category=? AND level=?
        """, (user_id, category, level))
        p = cur.fetchone()
        correct_count = p[0]
        total_count = p[1]

        cur.execute("""
            INSERT INTO scores (user_id, category, level, score, total, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, category, level, correct_count, total_count, now))

        conn.commit()
        conn.close()

        return RedirectResponse(
            url=f"/mypage.html?username={username}",
            status_code=302
        )

    conn.close()

    next_number = number + 1
    return RedirectResponse(
        url=f"/quiz.html?username={username}&category={category}&level={level}&number={next_number}",
        status_code=302
    )


# -----------------------------
# 起動時に DB 初期化
# -----------------------------
init_db()
