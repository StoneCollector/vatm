import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management


# Update the database initialization function to include the new field
def init_db():
    conn = sqlite3.connect('atm.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        gov_id TEXT NOT NULL UNIQUE,  -- Ensure this is unique
        balance REAL DEFAULT 0,
        dob TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        state TEXT NOT NULL,
        security_question TEXT NOT NULL,
        secanswer TEXT NOT NULL
    );''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES accounts(id)
    );''')
    conn.commit()
    conn.close()


# Call this function to initialize the database
init_db()


# Route for the index page
@app.route('/')
def index():
    return render_template('index.html')
    


# Register route for creating a new account with additional details
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        dob = request.form['dob']
        age = request.form['age']
        gender = request.form['gender']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        state = request.form['state']
        security = request.form['security_question_1']
        secanswer = request.form['answer_1']
        gov_id = request.form['gov_id']  # New field for Government ID
        initial_deposit = float(request.form['balance'])

        if not username or not password or not gov_id:
            flash('All fields are required.')
            return redirect(url_for('register'))

        # Validation to ensure unique Government ID
        conn = sqlite3.connect('atm.db')
        c = conn.cursor()

        # Check if the Government ID already exists
        c.execute('SELECT id FROM accounts WHERE gov_id = ?', (gov_id,))
        if c.fetchone():
            gid = "Government ID Already Registered. Please use a different Government ID"
            return render_template('flash.html', gid=gid)

        hashed_password = generate_password_hash(password)

        # Insert the new account into the database
        try:
            c.execute('INSERT INTO accounts (username, password, gov_id, balance, dob, age, gender, email, phone, address, state, security_question, secanswer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                      (username, password, gov_id, initial_deposit, dob, age, gender, email, phone, address, state, security, secanswer))
            conn.commit()
            accCreat = 'Account created successfully! You can now log in.'
            return render_template('flash.html', accCreat = accCreat)
        except Exception as e:
            conn.rollback()
            flash(f'Error occurred during registration: {str(e)}')
        finally:
            conn.close()

    return render_template('register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()

        # Check if the username and password match an existing account
        c.execute('SELECT id, balance FROM accounts WHERE username = ? AND password = ?', (username, password))
        user = c.fetchone()

        if user:
            session['user_id'] = user[0]
            fmessage = "Login Successfull!"
            return render_template('flash.html', fmessage=fmessage)
        else:
            loginfail = "Invalid credentials, please try again."
            return render_template('flash.html', loginfail=loginfail)

    return render_template('login.html')


# ATM route to handle checking balance, deposits, and withdrawals with custom error for underflow
@app.route('/atm', methods=['GET', 'POST'])
def atm():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('atm.db')
    c = conn.cursor()

    # Fetch the user's balance
    c.execute('SELECT balance FROM accounts WHERE id = ?', (session['user_id'],))
    balance = c.fetchone()[0]

    # Fetch recent deposit and withdrawal transactions (limit to 5 each)
    c.execute('SELECT date, amount FROM transactions WHERE user_id = ? AND type = "Deposit" ORDER BY date DESC LIMIT 5', (session['user_id'],))
    deposit_transactions = c.fetchall()

    c.execute('SELECT date, amount FROM transactions WHERE user_id = ? AND type = "Withdraw" ORDER BY date DESC LIMIT 5', (session['user_id'],))
    withdrawal_transactions = c.fetchall()

    conn.close()

    if request.method == 'POST':
        action = request.form['action']
        amount = float(request.form['amount'])

        conn = sqlite3.connect('atm.db')
        c = conn.cursor()

        # Handle deposit
        if action == 'Deposit':
            new_balance = balance + amount
            c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
            c.execute('INSERT INTO transactions (user_id, amount, type, date) VALUES (?, ?, "Deposit", datetime("now"))', (session['user_id'], amount))
            flash(f'Successfully deposited {amount}!')
        
        # Handle withdrawal with underflow error check
        elif action == 'Withdraw':
            if amount > balance:
                flash(f'Error: Insufficient funds! You tried to withdraw {amount}, but your balance is only {balance}.')
            else:
                new_balance = balance - amount
                c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
                c.execute('INSERT INTO transactions (user_id, amount, type, date) VALUES (?, ?, "Withdraw", datetime("now"))', (session['user_id'], amount))
                flash(f'Successfully withdrew {amount}!')

        conn.commit()
        conn.close()

        return redirect(url_for('atm'))

    return render_template('atm.html', balance=balance, deposit_transactions=deposit_transactions, withdrawal_transactions=withdrawal_transactions)


@app.route('/remove_account', methods=['GET', 'POST'])
def remove_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = sqlite3.connect('atm.db')
    c = conn.cursor()

    # Fetch the user's current balance
    c.execute('SELECT balance FROM accounts WHERE id = ?', (user_id,))
    balance_row = c.fetchone()
    balance = balance_row[0] if balance_row else 0

    if request.method == 'POST':
        # Get target account information from the form
        target_username = request.form['transfer_account_username']
        target_password = request.form['transfer_account_password']
        target_gov_id = request.form['transfer_account_gov_id']

        # Verify the target account credentials
        c.execute(
            'SELECT id, balance FROM accounts WHERE username = ? AND password = ? AND gov_id = ?',
            (target_username, target_password, target_gov_id)
        )
        target_account = c.fetchone()

        if not target_account:
            flash('Target account information is incorrect. Please try again.')
            conn.close()
            return redirect(url_for('remove_account'))

        target_account_id, target_balance = target_account

        # Transfer balance to the target account
        new_target_balance = target_balance + balance
        c.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_target_balance, target_account_id))

        # Delete the user’s account and associated transactions
        c.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM accounts WHERE id = ?', (user_id,))

        conn.commit()
        conn.close()

        session.pop('user_id', None)  # Log the user out after account removal
        rmessage = 'Your account has been removed and balance transferred successfully.'
        return render_template('flash.html', rmessage=rmessage)

    conn.close()
    return render_template('remove_account.html', balance=balance)


####### ONLY TESTING
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']

        # Fetch security question for given username
        conn = sqlite3.connect('atm.db')
        c = conn.cursor()
        c.execute('SELECT security_question FROM accounts WHERE username = ?', (username,))
        question = c.fetchone()
        conn.close()

        if question:
            return render_template('security_question.html', username=username, security_question=question[0])
        else:
            forgotun = 'Username Not Found.'
            return render_template('flash.html', forgotun=forgotun)

    return render_template('forgot_password.html')

@app.route('/verify_security_answer', methods=['POST'])
def verify_security_answer():
    username = request.form['username']
    security_answer = request.form['security_answer']

    conn = sqlite3.connect('atm.db')
    c = conn.cursor()
    c.execute('SELECT secanswer FROM accounts WHERE username = ?', (username,))
    answer = c.fetchone()
    

    if answer and answer[0].lower() == security_answer.lower():
        # Log in the user and redirect to dashboard
        c.execute('SELECT id FROM accounts WHERE username = ?', (username,))
        user_id = c.fetchone()[0]
        session['user_id'] = user_id
        forgotsuccess = 'Successfully Logged in using Security Question'
        return render_template('flash.html', forgotsuccess=forgotsuccess)
    else:
        forgotfail = "Incorrect answer. Please try again."
        return render_template('flash.html', forgotfail=forgotfail)

####### ONLY TESTING!!!!



# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    logoutmsg = 'You have been logged out.'
    return render_template('flash.html', logoutmsg = logoutmsg)


if __name__ == '__main__':
    app.run()
