from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import bcrypt
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "tssss"

conn = psycopg2.connect(
    dbname="finaldb",
    user="postgres",
    password="20041015R",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

cur.execute(
    """
CREATE TABLE IF NOT EXISTS cars (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    engine_volume FLOAT NOT NULL,
    fuel_consumption FLOAT NOT NULL,
    trunk_volume FLOAT NOT NULL,
    rental_price FLOAT NOT NULL,
    car_class VARCHAR(255) NOT NULL,
    available BOOLEAN NOT NULL,
    user_id INTEGER REFERENCES users(id),
    car_photos varchar(255)
);
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        surname VARCHAR(255) NOT NULL,
        age int not null,
        phone VARCHAR(11) not null,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(255) DEFAULT 'user'
    )
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS rentals (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        car_id INTEGER REFERENCES cars(id)
    )
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS comments (
        id SERIAL PRIMARY KEY,
        comments TEXT NOT NULL,
        username VARCHAR(255),
        car_id INT,
        FOREIGN KEY (username) REFERENCES users(username),
        FOREIGN KEY (car_id) REFERENCES cars(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
conn.commit()

def is_logged_in():
    return "user_id" in session

def is_admin():
    if is_logged_in():
        cur.execute("SELECT role FROM users WHERE username = %s", (session["user_id"],))
        role = cur.fetchone()
        if role and role[0] == "admin":
            return True
    return False
@app.route("/")
def index():
    if is_logged_in():
        cur.execute("SELECT * FROM cars WHERE available = TRUE")
        cars = cur.fetchall()
        front_image = []
        for car in cars:
            photos = car[10].split(',')

            for photo in photos:
                cleaned_photo = photo.strip('{}')
                print(photo)
                if 'front' in cleaned_photo.lower():
                    front_image.append(cleaned_photo)
                    break
        return render_template("index.html",front_images=front_image, cars=cars, user_is_authenticated=is_logged_in(), user_is_admin=is_admin())
    else:
        return redirect(url_for("login"))


@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        name = request.form["name"]
        surname = request.form["surname"]
        age = request.form["age"]
        phone = request.form["phone"]
        password = request.form["password"]

        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            error_message = "A user with the same name already exists."
            return render_template("register.html", error_message=error_message)

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        role = "user"

        cur.execute("INSERT INTO users (username, name, surname, age, phone, password, role) VALUES (%s, %s, %s, %s, %s, %s, %s)", (username, name, surname, age, phone, hashed_password.decode("utf-8"), role))
        conn.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        stored_password = cur.fetchone()

        if stored_password and bcrypt.checkpw(password.encode("utf-8"), stored_password[0].encode("utf-8")):
            session["user_id"] = username
            return redirect(url_for("index"))
        else:
            error_message = "User does not exist or invalid password."
            return render_template("login.html", error_message=error_message)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

@app.route("/admin")
def admin():
    if is_admin():
        cur.execute("SELECT * FROM cars")
        cars = cur.fetchall()
        return render_template("admin.html", cars=cars)
    else:
        return redirect(url_for("index"))


@app.route("/profile")
def profile():
    if is_logged_in():
        username = session["user_id"]

        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = cur.fetchone()

        return render_template("profile.html", users=user_data)
    else:
        return redirect(url_for("login"))

UPLOAD_FOLDER = 'static/car_photos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/add", methods=["POST"])
def add_car():
    if request.method == "POST":
        if not is_admin():
            return redirect(url_for("admin"))

        brand = request.form["brand"]
        model = request.form["model"]
        engine_volume = float(request.form["engine_volume"])
        fuel_consumption = float(request.form["fuel_consumption"])
        trunk_volume = float(request.form["trunk_volume"])
        rental_price = float(request.form["rental_price"])
        car_class = request.form["car_class"]

        photos = []
        if 'car_photos' in request.files:
            files = request.files.getlist('car_photos')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    photos.append(filename)

        cur.execute("""
            INSERT INTO cars (brand, model, engine_volume, fuel_consumption, trunk_volume, rental_price, car_class, available, car_photos)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
        """, (brand, model, engine_volume, fuel_consumption, trunk_volume, rental_price, car_class, photos))
        conn.commit()

    return redirect(url_for("admin"))

@app.route("/delete/<int:car_id>")
def delete_car(car_id):
    if not is_admin():
        return redirect(url_for("admin"))

    cur.execute("DELETE FROM comments WHERE car_id = %s", (car_id,))
    cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
    conn.commit()
    return redirect(url_for("admin"))

@app.route("/car/<int:car_id>", methods=["GET", "POST"])
def car_details(car_id):
    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
    car = cur.fetchone()

    if is_logged_in() and request.method == 'POST':
        comments = request.form['comment']
        username = session["user_id"]

        cur.execute('INSERT INTO comments (comments, username, car_id, created_at) VALUES (%s, %s, %s, NOW())', (comments, username, car_id))
        conn.commit()
        flash('Comment created successfully!', 'success')
        return redirect(url_for('car_details', car_id=car_id))

    cur.execute('''
            SELECT comments.id, comments.comments, comments.username, users.username, comments.created_at
            FROM comments
            LEFT JOIN users ON comments.username = users.username
            WHERE comments.car_id = %s
        ''', (car_id,))
    comments = cur.fetchall()

    if car:
        return render_template("car_details.html", car=car, comments=comments)
    else:
        return "Car not found", 404


@app.route("/search", methods=["GET", "POST"])
def search_cars():
    if request.method == "POST":
        search_query = request.form["search_query"]

        cur.execute("SELECT * FROM cars WHERE brand ILIKE %s and available = %s", (f"%{search_query}%", True))
        cars = cur.fetchall()
        print(cars)
        return render_template("search_results.html", cars=cars, search_query=search_query)

    return render_template("search.html")

@app.route("/sort/<parameter>")
def sort_cars(parameter):
    if parameter in ["name", "price", "year"]:
        cur.execute(f"SELECT * FROM cars ORDER BY {parameter}")
        cars = cur.fetchall()
        return render_template("sorted_cars.html", cars=cars, sort_parameter=parameter)
    else:
        return redirect(url_for("index"))

@app.route("/economy")
def view_economy_cars():
    cur.execute("SELECT * FROM cars WHERE car_class = 'economy' AND available = TRUE")
    cars = cur.fetchall()

    return render_template("car_class.html", cars=cars, car_class="economy", user_is_authenticated=is_logged_in(), user_is_admin=is_admin())

@app.route("/comfort")
def view_comfort_cars():
    cur.execute("SELECT * FROM cars WHERE car_class = 'comfort' AND available = TRUE")
    cars = cur.fetchall()

    return render_template("car_class.html", cars=cars, car_class="comfort", user_is_authenticated=is_logged_in(), user_is_admin=is_admin())

@app.route("/business")
def view_business_cars():
    cur.execute("SELECT * FROM cars WHERE car_class = 'business' AND available = TRUE")
    cars = cur.fetchall()
    return render_template("car_class.html", cars=cars, car_class="business", user_is_authenticated=is_logged_in(), user_is_admin=is_admin())

@app.route("/premium")
def view_premium_cars():
    cur.execute("SELECT * FROM cars WHERE car_class = 'premium' AND available = TRUE")
    cars = cur.fetchall()
    return render_template("car_class.html", cars=cars, car_class="premium", user_is_authenticated=is_logged_in(), user_is_admin=is_admin())


@app.route("/rentals")
def rentals():
    if is_admin():
        cur.execute("""
                    SELECT 
                        cars.id AS car_id,
                        cars.brand,
                        cars.model,
                        cars.engine_volume,
                        cars.fuel_consumption,
                        cars.trunk_volume,
                        cars.rental_price,
                        cars.car_class,
                        cars.available,
                        users.username AS renter_username
                    FROM cars
                    LEFT JOIN 
                        rentals ON cars.id = rentals.car_id
                    LEFT JOIN 
                        users ON rentals.user_id = users.id;
                """)
        rental_info = cur.fetchall()
        return render_template("rentals.html", rental_info=rental_info)
    else:
        return redirect(url_for("index"))

@app.route("/return/<int:car_id>")
def return_car(car_id):
    if not is_admin():
        return redirect(url_for("index"))

    cur.execute("DELETE FROM rentals WHERE car_id = %s", (car_id,))
    cur.execute("UPDATE cars SET available = TRUE WHERE id = %s", (car_id,))
    conn.commit()
    return redirect(url_for("rentals"))

@app.route("/rented-cars")
def rented_cars():
    if is_logged_in():
        username = session["user_id"]
        cur.execute("SELECT cars.brand FROM cars JOIN rentals ON cars.id = rentals.car_id JOIN users ON users.id = rentals.user_id WHERE users.username = %s", (username,))
        rented_cars = cur.fetchall()
        return render_template("rented_cars.html", rented_cars=rented_cars, username=username)
    else:
        return redirect(url_for("login"))

@app.route("/rent/<int:car_id>")
def rent(car_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    username = session["user_id"]
    cur.execute("INSERT INTO rentals (user_id, car_id) VALUES ((SELECT id FROM users WHERE username = %s), %s)", (username, car_id))
    cur.execute("UPDATE cars SET available = FALSE WHERE id = %s", (car_id,))
    conn.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
