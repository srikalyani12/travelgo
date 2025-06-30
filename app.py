from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from datetime import datetime
import json

# Flask Setup
app = Flask(__name__)
app.secret_key = 'e0d15ae2faa18025f4e2a0c7dc5a7b8a830791cc83ad7538667ce14ca2ad8bc0'

# MongoDB Atlas Setup
client = MongoClient("mongodb+srv://srikalyani:Yank&2000@cluster0.vnew545.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['travel_booking_db']
users_collection = db['travelgo_users']
trains_collection = db['trains']
bookings_collection = db['bookings']


SNS_TOPIC_ARN ='arn:aws:sns:us-east-1:724772095615:TravelGoApplication:c70ea6ee-2ed2-4358-82cf-d1e7a615a268'
def send_sns_notification(subject, message):
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"SNS error: cloud not send notification- {e}")

# Dummy data placeholder for seat availability demo
dummy_bus_train_data = {
    "Hyderabad_Vijayawada_Orange Travels_08:00 AM": {
        "total_seats": 30,
        "booked_seats": ["A1", "A2"]
    },
    "Hyderabad_Vijayawada_AP Express_06:00": {
        "total_seats": 50,
        "booked_seats": ["C5", "C6"]
    }
}

# Home page
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if users_collection.find_one({"email": email}):
            return render_template('register.html', message="User already exists.")
        users_collection.insert_one({
            "email": email,
            "name": request.form['name'],
            "password": request.form['password']
        })
        return redirect('/login')  # ✅ Correct redirect to the /login route
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email})
        if user and user['password'] == password:
            session['user'] = email
            return redirect('/')
        return render_template('login.html', message="Invalid credentials.")
    return render_template('login.html')

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    email = session['user']
    user = users_collection.find_one({"email": email})
    bookings = list(bookings_collection.find({'user_email': email}).sort('booking_date', -1))
    return render_template('dashboard.html', name=user['name'], bookings=bookings)


# Cancel booking
@app.route('/cancel_booking/<booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    result = bookings_collection.delete_one({"_id": ObjectId(booking_id)})
    if result.deleted_count:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Booking not found"}), 404


# Booking pages
@app.route('/bus')
def bus_page():
    return render_template('bus.html')

@app.route('/train')
def train_page():
    return render_template('train.html')

@app.route('/flight')
def flight_page():
    return render_template('flight.html')

@app.route('/hotel')
def hotel_page():
    return render_template('hotel.html')
@app.route('/confirm_flight_details')
def confirm_flight_details():
    return render_template('confirm_flight_details.html')

@app.route('/confirm_bus_details')
def confirm_bus_details():
    return render_template('confirm_bus_details.html')

@app.route('/confirm_train_details')
def confirm_train_details():
    return render_template('confirm_train_details.html')

@app.route('/confirm_hotel_details')
def confirm_hotel_details():
    return render_template('confirm_hotel_details.html')

@app.route('/bookingpayment')
def bookingpayment():
    return render_template('bookingpayment.html')

@app.route('/bookingsuccess')
def bookingsuccess():
    return render_template('bookingsuccess.html')


# General booking API (for flights, hotels, etc.)
@app.route('/book_service', methods=['POST'])
def book_service():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    try:
        data = request.get_json()
        data['user_email'] = session['user']
        data['booking_date'] = datetime.now()
        bookings_collection.insert_one(data)
        return jsonify({"success": True, "message": "Booking successful!"})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "Booking failed."}), 500


# Select seats page (for bus/train)
@app.route('/select_seats')
def select_seats():
    if 'user' not in session:
        return redirect('/login')
    booking_type = request.args.get('bookingType')
    name = request.args.get('name')
    source = request.args.get('source')
    destination = request.args.get('destination')
    time = request.args.get('time')
    vehicle_type = request.args.get('vehicleType')
    price_per_person = float(request.args.get('price'))
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('persons'))
    journey_id = f"{source}_{destination}_{name}_{time}"
    existing_booked_seats = dummy_bus_train_data.get(journey_id, {}).get("booked_seats", [])

    return render_template('select_seats.html',
                           booking_type=booking_type,
                           name=name,
                           source=source,
                           destination=destination,
                           time=time,
                           vehicle_type=vehicle_type,
                           price_per_person=price_per_person,
                           travel_date=travel_date,
                           num_persons=num_persons,
                           booked_seats_json=json.dumps(existing_booked_seats))


# Booking selected seats
@app.route('/book_selected_seats', methods=['POST'])
def book_selected_seats():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        data = request.get_json()
        if not data.get('selectedSeats'):
            return jsonify({"success": False, "message": "No seats selected."}), 400
        if len(data['selectedSeats']) != data['numPersons']:
            return jsonify({"success": False, "message": "Seat count mismatch."}), 400

        booking_record = {
            "user_email": session['user'],
            "booking_type": data.get('bookingType'),
            "name": data.get('name'),
            "source": data.get('source'),
            "destination": data.get('destination'),
            "travel_time": data.get('time'),
            "vehicle_type": data.get('vehicleType'),
            "travel_date": data.get('travelDate'),
            "num_persons": data.get('numPersons'),
            "selected_seats": data.get('selectedSeats'),
            "price_per_person": data.get('pricePerPerson'),
            "total_price": data.get('totalPrice'),
            "booking_date": datetime.now()
        }

        bookings_collection.insert_one(booking_record)
        return jsonify({"success": True, "redirect": "/dashboard"})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "message": "Failed to book seats."}), 500


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
