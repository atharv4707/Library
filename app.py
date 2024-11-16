from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from bson.objectid import ObjectId  
from flask_sqlalchemy import SQLAlchemy  
import os
from datetime import datetime, timedelta

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')


app.config["MONGO_URI"] = "mongodb string"
mongo = PyMongo(app)
bcrypt = Bcrypt(app)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    available_copies = db.Column(db.Integer, nullable=False)


ADMIN_USERNAME = 'my'  
ADMIN_PASSWORD_HASH = bcrypt.generate_password_hash('5').decode('utf-8')  

@app.route('/')
def home():
    return render_template('home.html', title='Home')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'] 
        name = request.form['name']
        college_roll_no = request.form['college_roll_no']
        year = request.form['year']

        existing_user = mongo.db.users.find_one({'email': email})
        if existing_user:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        mongo.db.users.insert_one({
            'email': email,
            'password': hashed_password,
            'name': name,   
            'college_roll_no': college_roll_no,   
            'year': year,
            'role': 'user'
        })

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = mongo.db.users.find_one({'email': email})

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            flash('Login successful!', 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html', title='Login')      

@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' in session:
        user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            books = Book.query.all()  # Fetch all books from SQL database
            return render_template('user_dashboard.html', user=user, books=books)
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['is_admin'] = True
            return redirect(url_for('librarian_dashboard'))
        else:
            flash('Invalid admin credentials.')
    
    return render_template('admin_login.html', title='Admin Login')

@app.route('/librarian_dashboard')
def librarian_dashboard():
    if 'is_admin' in session:
        user = mongo.db.users.find_one({'role': 'admin'})
        books = Book.query.all()  # Get all books for the librarian
        return render_template('librarian_dashboard.html', user=user, books=books)
    return redirect(url_for('admin_login'))

@app.route('/add_book', methods=['POST'])
def add_book():
    if 'is_admin' in session:
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']
        available_copies = int(request.form['copies'])

        # Create a new book entry in the SQL database
        new_book = Book(title=title, author=author, genre=genre, available_copies=available_copies)
        db.session.add(new_book)
        db.session.commit()

        flash('Book added successfully!')
        return redirect(url_for('librarian_dashboard'))
    return redirect(url_for('admin_login'))

@app.route('/reserve_book/<int:book_id>', methods=['POST'])  # Make sure book_id is an integer
def reserve_book(book_id):
    if 'user_id' not in session:
        flash('You need to log in to reserve a book.')
        return redirect(url_for('login'))

    user_id = session['user_id']
    reserved_at = datetime.now()
    due_date = reserved_at + timedelta(days=30)

    # Create a new reservation in MongoDB
    mongo.db.reservations.insert_one({
        'user_id': user_id,
        'book_id': book_id,
        'reserved_at': reserved_at,
        'due_date': due_date
    })

    # Update the available copies of the book in SQL
    book = Book.query.get(book_id)
    if book and book.available_copies > 0:
        book.available_copies -= 1
        db.session.commit()
        flash('Book reserved successfully! Due date: {}'.format(due_date.strftime('%Y-%m-%d')))
    else:
        flash('No available copies for reservation.')

    return redirect(url_for('user_dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/reservations')
def view_reservations():
    
    reservations = mongo.db.reservations.find()

    
    detailed_reservations = []
    for reservation in reservations:
        
        user = mongo.db.users.find_one({'_id': ObjectId(reservation['user_id'])})
        user_name = user['name'] if user else 'Unknown User'

        
        book = Book.query.get(reservation['book_id'])
        book_title = book.title if book else 'Unknown Book'

       
        detailed_reservations.append({
            'user_name': user_name,
            'book_title': book_title,
            'reserved_at': reservation['reserved_at'],
            'due_date': reservation['due_date']
        })

    return render_template('reservations.html', reservations=detailed_reservations)



@app.route('/user_profile/<user_id>')
def user_profile(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user:
        return render_template('user_profile.html', user=user)
    else:
        flash('User not found', 'danger')
        return redirect(url_for('reservations'))




@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    # Fetch the book from the database
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        # Get data from form
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']
        copies = request.form['copies']

        # Update book details
        book.title = title
        book.author = author
        book.genre = genre
        book.available_copies = copies

        # Commit changes to the database
        db.session.commit()
        
        flash('Book details updated successfully!', 'success')
        return redirect(url_for('librarian_dashboard'))  # Redirect to the book list page

    # Render the edit template if the method is GET
    return render_template('edit_book.html', book=book)

@app.route('/books')
def book_list():
    # Fetch all books from the database
    books = Book.query.all()
    return render_template('book_list.html', books=books)

if __name__ == '__main__':
    with app.app_context():  
        db.create_all()  
    app.run(host='0.0.0.0',port=1000)





"""Case Study - Library Management System
Problem: "Create an efficient Library Management System that enhances user experience and streamlines book management."

EDIPT

Empathize: Understand users’ needs for easy book searches, seamless reservations, and effective account management. Identify challenges faced by librarians in tracking inventory and managing user interactions.

Define: Define the problem statement: "Current library systems are inefficient, leading to difficulties in managing book availability, user reservations, and overall user experience."

Ideate: Generate ideas for features that include a user-friendly interface for searching and reserving books, real-time inventory tracking, and a clear reporting dashboard for librarians.

Prototype: Create a prototype of the Library Management System that includes an intuitive user interface, easy navigation for users and librarians, and efficient backend functionalities for tracking and managing books.

Test: Test the prototype with real users and librarians, gather feedback on usability and functionality, and iterate based on findings to improve the system"""