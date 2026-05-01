import sqlite3

# 初期問題データ
initial_questions = [
    # Python基礎・初級
    ("Python基礎", "初級", "Pythonで画面に文字を表示する関数は？",
     "print()", "echo()", "show()", "display()", 1),

    ("Python基礎", "初級", "変数に値を代入する記号は？",
     "==", "=", "=>", "->", 2),

    ("Python基礎", "初級", "リストの先頭のインデックスは？",
     "0", "1", "-1", "10", 1),

    # Python基礎・中級
    ("Python基礎", "中級", "関数を定義するキーワードは？",
     "func", "define", "def", "function", 3),

    ("Python基礎", "中級", "例外処理に使うキーワードは？",
     "try-except", "catch", "error", "exception", 1),

    # Python応用・初級
    ("Python応用", "初級", "辞書型のキーと値の組み合わせを何と呼ぶ？",
     "pair", "item", "element", "set", 2),

    ("Python応用", "初級", "タプルの特徴は？",
     "変更できる", "変更できない", "数字しか入らない", "文字列しか入らない", 2),

    # Python応用・中級
    ("Python応用", "中級", "リスト内包表記の正しい書き方は？",
     "[x for x in list]", "[for x list]", "(x in list)", "{x list}", 1),

    ("Python応用", "中級", "クラスを定義するキーワードは？",
     "object", "class", "struct", "type", 2),
]

def init_questions():
    conn = sqlite3.connect("quiz.db")
    cur = conn.cursor()

    # テーブルが無ければ作成（安全のため）
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

    # すでにデータがある場合はスキップ
    cur.execute("SELECT COUNT(*) FROM questions")
    count = cur.fetchone()[0]

    if count > 0:
        print("既に問題が登録されています。処理を終了します。")
        conn.close()
        return

    # 初期データ投入
    for q in initial_questions:
        cur.execute("""
            INSERT INTO questions
            (category, level, question, choice1, choice2, choice3, choice4, answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, q)

    conn.commit()
    conn.close()
    print("初期問題データの投入が完了しました！")

if __name__ == "__main__":
    init_questions()
