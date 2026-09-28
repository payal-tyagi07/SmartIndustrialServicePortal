import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

EMAIL = "payaltyagi727@gmail.com"
TEST_PW = "admin123"

conn = pymysql.connect(
    host='localhost',
    user='portal_user',
    password='MySQLismine_16',      # ← your actual MySQL password
    database='smart_industrial_portal',
    cursorclass=pymysql.cursors.DictCursor,
)

with conn.cursor() as cur:
    # 1. What's actually in the DB right now?
    cur.execute("SELECT id, email, role, password_hash FROM users WHERE email=%s", (EMAIL,))
    row = cur.fetchone()
    print("=" * 60)
    print("BEFORE UPDATE")
    print("=" * 60)
    if not row:
        print(f"No user found with email {EMAIL}")
        raise SystemExit(1)
    print(f"id    = {row['id']}")
    print(f"email = {row['email']}")
    print(f"role  = {row['role']}")
    print(f"hash  = {row['password_hash'][:50]}...")

    # 2. Does the DB hash match 'admin123'?
    db_matches = check_password_hash(row['password_hash'], TEST_PW)
    print(f"\nDB hash matches '{TEST_PW}'? -> {db_matches}")

    # 3. Generate a fresh hash and verify IT works
    fresh = generate_password_hash(TEST_PW)
    fresh_check = check_password_hash(fresh, TEST_PW)
    print(f"Freshly generated hash verifies against '{TEST_PW}'? -> {fresh_check}")

    # 4. Force-update the DB with a known-good hash
    cur.execute(
        "UPDATE users SET password_hash=%s, role='admin' WHERE email=%s",
        (fresh, EMAIL),
    )
    conn.commit()
    print(f"\nUPDATE ran. Rows affected: {cur.rowcount}")

    # 5. Re-read to confirm
    cur.execute("SELECT password_hash FROM users WHERE email=%s", (EMAIL,))
    row2 = cur.fetchone()
    print(f"New hash in DB: {row2['password_hash'][:50]}...")
    print(f"New hash matches '{TEST_PW}'? -> {check_password_hash(row2['password_hash'], TEST_PW)}")

conn.close()
print("=" * 60)
print(f"Now try logging in with: {EMAIL} / {TEST_PW}")
print("=" * 60)