from flask import Flask, render_template, request, redirect, session, jsonify
import boto3
from boto3.dynamodb.conditions import Attr
from datetime import datetime
import json
import uuid
import os

# Flask Setup
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# AWS DynamoDB Setup — using instance profile credentials
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
users_table = dynamodb.Table('travelgo_users')
bookings_table = dynamodb.Table('travelgo_bookings')

# AWS SNS Setup
sns_client = boto3.client('sns', region_name='us-east-1')
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:084828600922:TravelGoApplication:082a0b6b-e971-4d9f-9bf6-c200e7d9c81d"

def send_sns_notification(subject, message):
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"SNS error: {e}")

# Dummy seat data for demo
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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        response = users_table.get_item(Key={'email': email})
        if 'Item' in response:
            return render_template('register.html', message="User already exists.")

        users_table.put_item(Item={
            'email': email,
            'name': request.form['name'],
            'password': request.form['password']
        })
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')
        if user and user['password'] == password:
            session['user'] = email
            return redirect('/')
        return render_template('login.html', message="Invalid credentials.")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    email = session['user']
    user_response = users_table.get_item(Key={'email': email})
    user = user_response.get('Item')

    booking_response = bookings_table.scan(
        FilterExpression=Attr('user_email').eq(email)
    )
    bookings = sorted(booking_response['Items'], key=lambda x: x['booking_date'], reverse=True)

    return render_template('dashboard.html', name=user['name'], bookings=bookings)

@app.route('/cancel_booking/<booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    try:
        bookings_table.delete_item(Key={'booking_id': booking_id})
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "Booking not found"}), 404

# Booking Pages
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

@app.route('/book_service', methods=['POST'])
def book_service():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    try:
        data = request.get_json()
        data['booking_id'] = str(uuid.uuid4())
        data['user_email'] = session['user']
        data['booking_date'] = datetime.now().isoformat()
        bookings_table.put_item(Item=data)

        send_sns_notification(
            subject="New Booking Confirmed",
            message=f"Booking successful for {data['booking_type']} on {data['travel_date']}."
        )

        return jsonify({"success": True, "message": "Booking successful!"})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "Booking failed."}), 500

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
            "booking_id": str(uuid.uuid4()),
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
            "booking_date": datetime.now().isoformat()
        }

        bookings_table.put_item(Item=booking_record)

        send_sns_notification(
            subject="Seat Booking Successful",
            message=f"Seats {data['selectedSeats']} booked successfully for {data['travelDate']}."
        )

        return jsonify({"success": True, "redirect": "/dashboard"})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "message": "Failed to book seats."}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
