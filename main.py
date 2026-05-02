from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import csv
import openpyxl

app = FastAPI()

# static フォルダ（CSS・音声ファイルなど）
app.mount("/static", StaticFiles(directory="static"), name="static")

# templates フォルダ（HTML）
templates = Jinja2Templates(directory="templates")


# -----------------------------
#  HTML ページルーティング（テンプレート方式）
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

@app.get("/mypage.html")
def mypage_page(request: Request, username: str = ""):
    # ★ ログイン時に username をクエリで渡す方式にする
    #   例：/mypage.html?username=taro

    if username == "":
        return templates.TemplateResponse("login.html", context={"request": request})

    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # -----------------------------
    # ① ユーザー情報取得
    # -----------------------------
    cur.execute("SELECT id, xp FROM users WHERE username=?", (username,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return templates.TemplateResponse("login.html", context={"request": request})

    user_id = user[0]
    xp = user[1]

    # -----------------------------
    # ② レベル計算（シンプル方式）
    # -----------------------------
    level = xp // 100 + 1
    next_xp = (level * 100) - xp

    # 称号
    badges = {1: "初心者", 2: "見習い", 3: "中級者", 4: "上級者", 5: "達人"}
    badge = badges.get(level, "達人")

    # XPバー（％）
    xp_bar_percent = min(100, int((xp % 100) / 100 * 100))

    # -----------------------------
    # ③ 進捗（4行固定）
    # -----------------------------
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

    # -----------------------------
    # ④ スコア履歴
    # -----------------------------
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

    # -----------------------------
    # ⑤ テンプレートへ埋め込んで返す
    # -----------------------------
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








@app.get("/level.html")
def level_page(request: Request, username: str = "", category: str = ""):

    # パラメータ不足 → カテゴリ選択へ戻す
    if username == "" or category == "":
        return templates.TemplateResponse("category.html", context={"request": request})

    return templates.TemplateResponse(
        "level.html",
        context={
            "request": request,
            "username": username,
            "category": category
        }
    )




@app.get("/cms.html")
def cms_page(request: Request):
    return templates.TemplateResponse("cms.html", context={"request": request})


# -----------------------------
#  DB 初期化（users / questions / scores / progress）
# -----------------------------
def init_db():
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # ユーザー
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            xp INTEGER DEFAULT 0
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

    # スコア履歴
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

    # 進捗（カテゴリ × レベル）
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
#  API：ユーザー登録（テンプレート方式）
# -----------------------------
@app.post("/api/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # すでに存在するユーザー名か確認
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    exists = cur.fetchone()

    if exists:
        conn.close()
        return templates.TemplateResponse("register.html", context={
            "request": request,
            "error": "このユーザー名はすでに使われています"
        })

    # 新規登録
    cur.execute("INSERT INTO users (username, password, xp) VALUES (?, ?, 0)", (username, password))
    conn.commit()
    conn.close()

    # 登録成功 → login.html に遷移
    return templates.TemplateResponse("login.html", context={
        "request": request,
        "message": "登録が完了しました。ログインしてください。"
    })




# -----------------------------
#  API：ログイン（テンプレート方式）
# -----------------------------
@app.post("/api/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()

    conn.close()

    if user:
        # ★ ログイン成功 → /mypage.html?username=◯◯ にリダイレクト
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/mypage.html?username={username}", status_code=302)
    else:
        # ★ ログイン失敗 → login.html にエラーメッセージを埋め込んで返す
        return templates.TemplateResponse("login.html", context={
            "request": request,
            "error": "ユーザー名またはパスワードが違います"
        })


# -----------------------------
#  API：CSV アップロード
# -----------------------------
@app.post("/api/upload_csv")
def upload_csv(request: Request, file: UploadFile = File(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # CSV 読み込み
    content = file.file.read().decode("utf-8").splitlines()
    reader = csv.reader(content)

    count = 0
    for row in reader:
        if len(row) < 7:
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
#  API：Excel（.xlsx）アップロード
# -----------------------------
@app.post("/api/upload_excel")
def upload_excel(request: Request, file: UploadFile = File(...)):
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # Excel 読み込み
    wb = openpyxl.load_workbook(file.file)
    ws = wb.active

    count = 0
    for row in ws.iter_rows(values_only=True):
        if row is None or len(row) < 7:
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
#  API：回答処理（採点・XP加算・進捗更新・スコア保存）
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

    # -----------------------------
    # ① 正解を取得
    # -----------------------------
    cur.execute("SELECT answer FROM questions WHERE id=?", (question_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/quiz.html?username={username}&category={category}&level={level}&number={number}",
            status_code=302
        )

    correct_answer = row[0]
    is_correct = (answer == correct_answer)

    # -----------------------------
    # ② ユーザーID取得
    # -----------------------------
    cur.execute("SELECT id, xp FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    user_id = user[0]
    xp = user[1]

    # -----------------------------
    # ③ XP加算（正解なら +10XP）
    # -----------------------------
    if is_correct:
        xp += 10
        cur.execute("UPDATE users SET xp=? WHERE id=?", (xp, user_id))

    # -----------------------------
    # ④ 進捗更新（correct / total）
    # -----------------------------
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

    # -----------------------------
    # ⑤ 最後の問題ならスコア保存 → 結果画面へ
    # -----------------------------
    if number == total:
        # スコア計算（正解数をカウント）
        cur.execute("""
            SELECT COUNT(*) FROM progress
            WHERE user_id=? AND category=? AND level=? AND correct > 0
        """, (user_id, category, level))

        # スコア保存
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 正解数を再計算
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

        # 結果画面へ
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/mypage.html?username={username}",
            status_code=302
        )

    conn.close()

    # -----------------------------
    # ⑥ 次の問題へ遷移
    # -----------------------------
    next_number = number + 1
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"/quiz.html?username={username}&category={category}&level={level}&number={next_number}",
        status_code=302
    )

  

init_db()
