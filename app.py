from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from flask_cors import CORS
import os
from datetime import date

app = Flask(__name__)
app.secret_key = 'library_secret_key_2024'

CORS(app, resources={r"/api/*": {"origins": "*"}})

# Database Configuration
app.config['MYSQL_HOST'] = os.environ.get('MYSQLHOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQLUSER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQLPASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQLDATABASE', 'railway')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQLPORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

def init_db():
    cur = mysql.connection.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50),
        password VARCHAR(100),
        role VARCHAR(20) DEFAULT 'admin'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS books (
        book_id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200),
        author VARCHAR(100),
        isbn VARCHAR(50),
        category VARCHAR(50),
        total_copies INT DEFAULT 1,
        available_copies INT DEFAULT 1,
        photo_url VARCHAR(500)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members (
        member_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        phone VARCHAR(20),
        address VARCHAR(200),
        join_date DATE DEFAULT (CURDATE()),
        status VARCHAR(20) DEFAULT 'active',
        member_code VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        membership_expire DATE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT,
        member_id INT,
        issue_date DATE DEFAULT (CURDATE()),
        due_date DATE,
        return_date DATE,
        fine_amount INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'issued'
    )""")
    cur.execute("""INSERT IGNORE INTO users (user_id, username, password, role) 
        VALUES (1, 'admin', 'admin123', 'admin')""")
    mysql.connection.commit()
    cur.close()

with app.app_context():
    try:
        init_db()
        print("DB initialized successfully!")
    except Exception as e:
        print(f"DB init error: {e}")

# ==================== PUBLIC ====================
@app.route('/')
def public():
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT * FROM books 
                      WHERE title LIKE %s OR author LIKE %s OR category LIKE %s
                      ORDER BY title""",
                   (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM books ORDER BY title")
    all_books = cur.fetchall()
    cur.close()
    return render_template('public.html', books=all_books, search=search)

# ==================== API ====================
@app.route('/api/books')
def api_books():
    search = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    cur = mysql.connection.cursor()
    query = """SELECT book_id, title, author, isbn, category,
                      total_copies, available_copies, photo_url
               FROM books WHERE 1=1"""
    params = []
    if search:
        query += " AND (title LIKE %s OR author LIKE %s OR category LIKE %s)"
        like = f"%{search}%"
        params += [like, like, like]
    if category:
        query += " AND category = %s"
        params.append(category)
    query += " ORDER BY title"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    books = [{'id': r['book_id'], 'title': r['title'], 'author': r['author'],
              'isbn': r['isbn'], 'category': r['category'],
              'total_copies': r['total_copies'],
              'available_copies': r['available_copies'],
              'photo_url': r['photo_url']} for r in rows]
    return jsonify({'count': len(books), 'books': books})

@app.route('/api/categories')
def api_categories():
    cur = mysql.connection.cursor()
    cur.execute("""SELECT DISTINCT category FROM books
                   WHERE category IS NOT NULL AND category <> ''
                   ORDER BY category""")
    categories = [r['category'] for r in cur.fetchall()]
    cur.close()
    return jsonify(categories)

# ==================== ADMIN LOGIN ====================
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and password == user['password']:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ==================== DASHBOARD ====================
@app.route('/admin/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) as count FROM books")
    total_books = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM members")
    total_members = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM transactions WHERE status='issued'")
    issued_books = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM transactions WHERE status='overdue'")
    overdue_books = cur.fetchone()['count']
    cur.close()
    return render_template('dashboard.html',
        total_books=total_books,
        total_members=total_members,
        issued_books=issued_books,
        overdue_books=overdue_books)

# ==================== BOOKS ====================
@app.route('/admin/books')
def books():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT * FROM books 
                      WHERE title LIKE %s OR author LIKE %s OR category LIKE %s""",
                   (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM books")
    all_books = cur.fetchall()
    cur.close()
    return render_template('books.html', books=all_books, search=search)

@app.route('/admin/books/add', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form['isbn']
        category = request.form['category']
        copies = request.form['copies']
        photo_url = request.form.get('photo_url', '')
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO books (title, author, isbn, category, total_copies, available_copies, photo_url) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (title, author, isbn, category, copies, copies, photo_url))
        mysql.connection.commit()
        cur.close()
        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    return render_template('add_book.html')

@app.route('/admin/books/delete/<int:id>')
def delete_book(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM books WHERE book_id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Book deleted!', 'success')
    return redirect(url_for('books'))

# ==================== MEMBERS ====================
@app.route('/admin/members')
def members():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT * FROM members 
                      WHERE name LIKE %s OR email LIKE %s 
                      OR phone LIKE %s OR member_code LIKE %s""",
                   (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM members")
    all_members = cur.fetchall()
    cur.close()
    return render_template('members.html', members=all_members, search=search)

@app.route('/admin/members/add', methods=['GET', 'POST'])
def add_member():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        expire_date = request.form['expire_date']
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) as count FROM members")
        count = cur.fetchone()['count']
        member_code = f'MEM-{str(count + 1).zfill(4)}'
        cur.execute("""INSERT INTO members (name, email, phone, address, member_code, membership_expire) 
                      VALUES (%s, %s, %s, %s, %s, %s)""",
            (name, email, phone, address, member_code, expire_date))
        mysql.connection.commit()
        cur.close()
        flash(f'Member added! Member ID: {member_code}', 'success')
        return redirect(url_for('members'))
    return render_template('add_member.html')

@app.route('/admin/members/delete/<int:id>')
def delete_member(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM members WHERE member_id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Member deleted!', 'success')
    return redirect(url_for('members'))

# ==================== TRANSACTIONS ====================
@app.route('/admin/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT t.transaction_id, b.title, m.name, m.member_code,
               t.issue_date, t.due_date, t.return_date,
               t.fine_amount, t.status
        FROM transactions t
        JOIN books b ON t.book_id = b.book_id
        JOIN members m ON t.member_id = m.member_id
        ORDER BY t.transaction_id DESC
    """)
    all_transactions = cur.fetchall()
    cur.close()
    return render_template('transactions.html', transactions=all_transactions)

@app.route('/admin/issue', methods=['GET', 'POST'])
def issue_book():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        book_id = request.form['book_id']
        member_id = request.form['member_id']
        due_date = request.form['due_date']
        cur.execute("""SELECT COUNT(*) as count FROM transactions 
                      WHERE book_id = %s AND member_id = %s 
                      AND status = 'issued'""", (book_id, member_id))
        already_issued = cur.fetchone()['count']
        if already_issued > 0:
            flash('এই member ইতিমধ্যে এই book নিয়েছে!', 'danger')
            cur.close()
            return redirect(url_for('issue_book'))
        cur.execute("INSERT INTO transactions (book_id, member_id, due_date) VALUES (%s, %s, %s)",
            (book_id, member_id, due_date))
        cur.execute("UPDATE books SET available_copies = available_copies - 1 WHERE book_id = %s", (book_id,))
        mysql.connection.commit()
        cur.close()
        flash('Book issued successfully!', 'success')
        return redirect(url_for('transactions'))
    cur.execute("SELECT book_id, title, author, isbn, available_copies FROM books")
    all_books = cur.fetchall()
    cur.execute("SELECT member_id, name, member_code, membership_expire FROM members WHERE status='active'")
    active_members = cur.fetchall()
    cur.close()
    return render_template('issue_book.html', books=all_books, members=active_members)

@app.route('/admin/return/<int:id>')
def return_book(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT book_id, due_date FROM transactions WHERE transaction_id = %s", (id,))
    transaction = cur.fetchone()
    book_id = transaction['book_id']
    due_date = transaction['due_date']
    today = date.today()
    fine = 0
    if today > due_date:
        days_late = (today - due_date).days
        fine = days_late * 5
    cur.execute("""UPDATE transactions 
                  SET return_date = %s, fine_amount = %s, status = 'returned'
                  WHERE transaction_id = %s""", (today, fine, id))
    cur.execute("UPDATE books SET available_copies = available_copies + 1 WHERE book_id = %s", (book_id,))
    mysql.connection.commit()
    cur.close()
    if fine > 0:
        flash(f'Book returned! Late fine: ৳{fine}', 'warning')
    else:
        flash('Book returned successfully! No fine.', 'success')
    return redirect(url_for('transactions'))

# ==================== SEARCH API ====================
@app.route('/search/books')
def search_books_api():
    search = request.args.get('q', '')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT book_id, title, author, isbn, available_copies 
                  FROM books WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s""",
               (f'%{search}%', f'%{search}%', f'%{search}%'))
    books = cur.fetchall()
    cur.close()
    result = [{'id': b['book_id'], 'title': b['title'], 'author': b['author'],
               'isbn': b['isbn'], 'available': b['available_copies']} for b in books]
    return jsonify(result)

@app.route('/search/members')
def search_members_api():
    search = request.args.get('q', '')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT member_id, name, member_code, membership_expire 
                  FROM members WHERE name LIKE %s OR member_code LIKE %s OR phone LIKE %s""",
               (f'%{search}%', f'%{search}%', f'%{search}%'))
    members = cur.fetchall()
    cur.close()
    result = [{'id': m['member_id'], 'name': m['name'], 'code': m['member_code'],
               'expire': str(m['membership_expire'])} for m in members]
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)