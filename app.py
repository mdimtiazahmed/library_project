from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import bcrypt
import os

app = Flask(__name__)
app.secret_key = 'library_secret_key_2024'

# Database Configuration
app.config['MYSQL_HOST'] = os.environ.get('MYSQLHOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQLUSER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQLPASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQLDATABASE', 'railway')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQLPORT', 3306))

mysql = MySQL(app)

# ==================== LOGIN ====================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and password == user[2]:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM books")
    total_books = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM members")
    total_members = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status='issued'")
    issued_books = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status='overdue'")
    overdue_books = cur.fetchone()[0]
    cur.close()
    return render_template('dashboard.html',
        total_books=total_books,
        total_members=total_members,
        issued_books=issued_books,
        overdue_books=overdue_books)

# ==================== BOOKS ====================
@app.route('/books')
def books():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT * FROM books 
                      WHERE title LIKE %s 
                      OR author LIKE %s 
                      OR category LIKE %s""",
                   (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM books")
    all_books = cur.fetchall()
    cur.close()
    return render_template('books.html', books=all_books, search=search)

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form['isbn']
        category = request.form['category']
        copies = request.form['copies']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO books (title, author, isbn, category, total_copies, available_copies) VALUES (%s, %s, %s, %s, %s, %s)",
            (title, author, isbn, category, copies, copies))
        mysql.connection.commit()
        cur.close()
        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    return render_template('add_book.html')

@app.route('/books/delete/<int:id>')
def delete_book(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM books WHERE book_id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Book deleted!', 'success')
    return redirect(url_for('books'))

# ==================== MEMBERS ====================
@app.route('/members')
def members():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT * FROM members 
                      WHERE name LIKE %s 
                      OR email LIKE %s 
                      OR phone LIKE %s
                      OR member_code LIKE %s""",
                   (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM members")
    all_members = cur.fetchall()
    cur.close()
    return render_template('members.html', members=all_members, search=search)

@app.route('/members/add', methods=['GET', 'POST'])
def add_member():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        expire_date = request.form['expire_date']
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM members")
        count = cur.fetchone()[0]
        member_code = f'MEM-{str(count + 1).zfill(4)}'
        cur.execute("INSERT INTO members (name, email, phone, address, member_code, membership_expire) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, email, phone, address, member_code, expire_date))
        mysql.connection.commit()
        cur.close()
        flash(f'Member added! Member ID: {member_code}', 'success')
        return redirect(url_for('members'))
    return render_template('add_member.html')

@app.route('/members/delete/<int:id>')
def delete_member(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM members WHERE member_id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Member deleted!', 'success')
    return redirect(url_for('members'))

# ==================== TRANSACTIONS ====================
@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
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

@app.route('/issue', methods=['GET', 'POST'])
def issue_book():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        book_id = request.form['book_id']
        member_id = request.form['member_id']
        due_date = request.form['due_date']

        # Check same book already issued to same member
        cur.execute("""SELECT COUNT(*) FROM transactions 
                      WHERE book_id = %s AND member_id = %s 
                      AND status = 'issued'""", (book_id, member_id))
        already_issued = cur.fetchone()[0]
        if already_issued > 0:
            flash('এই member ইতিমধ্যে এই book নিয়েছে!', 'danger')
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

@app.route('/return/<int:id>')
def return_book(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT book_id, due_date FROM transactions WHERE transaction_id = %s", (id,))
    transaction = cur.fetchone()
    book_id = transaction[0]
    due_date = transaction[1]

    from datetime import date
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
    from flask import jsonify
    search = request.args.get('q', '')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT book_id, title, author, isbn, available_copies 
                  FROM books WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s""",
               (f'%{search}%', f'%{search}%', f'%{search}%'))
    books = cur.fetchall()
    cur.close()
    result = []
    for b in books:
        result.append({
            'id': b[0],
            'title': b[1],
            'author': b[2],
            'isbn': b[3],
            'available': b[4]
        })
    from flask import jsonify
    return jsonify(result)

@app.route('/search/members')
def search_members_api():
    from flask import jsonify
    search = request.args.get('q', '')
    cur = mysql.connection.cursor()
    cur.execute("""SELECT member_id, name, member_code, membership_expire 
                  FROM members WHERE name LIKE %s OR member_code LIKE %s OR phone LIKE %s""",
               (f'%{search}%', f'%{search}%', f'%{search}%'))
    members = cur.fetchall()
    cur.close()
    result = []
    for m in members:
        result.append({
            'id': m[0],
            'name': m[1],
            'code': m[2],
            'expire': str(m[3])
        })
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)