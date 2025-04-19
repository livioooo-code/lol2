import os
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
import config
from route_optimizer import optimize_route, geocode_address, get_route_details
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_courier_nav_secret")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# Initialize the app with the extension
db.init_app(app)

@app.route('/')
def index():
    """Display the main page with the navigation form"""
    from models import Route
    # Get saved routes for display
    saved_routes = Route.query.order_by(Route.created_at.desc()).all()
    return render_template('index.html', api_key=config.OPENROUTE_API_KEY, saved_routes=saved_routes)

@app.route('/optimize', methods=['POST'])
def optimize():
    """Process the form data and optimize the route"""
    try:
        import time
        
        # Get locations from the form
        locations = []
        location_details = []
        for i in range(int(request.form.get('location_count', 0))):
            city = request.form.get(f'city_{i}', '')
            street = request.form.get(f'street_{i}', '')
            number = request.form.get(f'number_{i}', '')
            category = request.form.get(f'category_{i}', 'home')
            time_window_start = request.form.get(f'time_window_start_{i}', '')
            time_window_end = request.form.get(f'time_window_end_{i}', '')
            estimated_duration = request.form.get(f'estimated_duration_{i}', '10')
            
            if city and street and number:
                address = f"{street} {number}, {city}"
                locations.append(address)
                location_details.append({
                    'city': city,
                    'street': street,
                    'number': number,
                    'category': category,
                    'time_window_start': time_window_start,
                    'time_window_end': time_window_end,
                    'estimated_duration': estimated_duration
                })
            elif city and street:
                address = f"{street}, {city}"
                locations.append(address)
                location_details.append({
                    'city': city,
                    'street': street,
                    'number': '',
                    'category': category,
                    'time_window_start': time_window_start,
                    'time_window_end': time_window_end,
                    'estimated_duration': estimated_duration
                })
        
        if len(locations) < 2:
            flash("Please enter at least two valid locations to optimize a route.", "danger")
            return redirect(url_for('index'))

        # Geocode addresses to coordinates
        coords = []
        formatted_addresses = []
        for idx, address in enumerate(locations):
            geocode_result = geocode_address(address)
            if geocode_result and 'coordinates' in geocode_result:
                coords.append(geocode_result['coordinates'])
                formatted_addresses.append(geocode_result['formatted_address'])
                # Add coordinates to location details
                location_details[idx]['longitude'] = geocode_result['coordinates'][0]
                location_details[idx]['latitude'] = geocode_result['coordinates'][1]
                location_details[idx]['formatted_address'] = geocode_result['formatted_address']
            else:
                flash(f"Could not geocode address: {address}", "danger")
                return redirect(url_for('index'))

        # Get current location if provided
        current_lat = request.form.get('current_lat')
        current_lon = request.form.get('current_lon')
        start_location = None
        if current_lat and current_lon:
            start_location = [float(current_lon), float(current_lat)]
            
        # Optimize route with current location
        optimized_route, total_time, total_distance = optimize_route(coords, start_location)
        
        if not optimized_route:
            flash("Could not optimize route. Please try different locations.", "danger")
            return redirect(url_for('index'))

        # Get route details with real-time traffic information
        include_traffic = request.form.get('include_traffic', 'true').lower() == 'true'
        route_details = get_route_details(optimized_route, include_traffic=include_traffic)
        
        # Store in session for display
        session['optimized_route'] = {
            'coordinates': optimized_route,
            'addresses': [formatted_addresses[i] for i in range(len(formatted_addresses))],
            'total_time': route_details['total_duration'],
            'total_distance': route_details['total_distance'],
            'total_duration_seconds': route_details['total_duration_seconds'],
            'route_details': route_details,
            'location_details': location_details,
            'traffic_delay_text': route_details.get('traffic_delay_text', ''),
            'has_traffic_data': route_details.get('has_traffic_data', False),
            'traffic_conditions': route_details.get('traffic_conditions', []),
            'last_traffic_update': int(time.time())
        }
        
        flash("Route optimized successfully!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        logging.error(f"Error in optimization: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/get_route')
def get_route():
    """Return the optimized route data for AJAX requests"""
    import json
    import time
    from route_optimizer import check_for_traffic_updates
    
    route_data = session.get('optimized_route', {})
    
    # Check if we need to update for traffic changes
    if route_data and 'coordinates' in route_data:
        # Check if route is older than 2 minutes or check_traffic parameter is provided
        current_time = int(time.time())
        last_update = route_data.get('last_traffic_update', 0)
        force_check = request.args.get('check_traffic', 'false').lower() == 'true'
        
        if force_check or (current_time - last_update > 120):  # 2 minutes
            logging.debug("Checking for traffic updates...")
            traffic_update = check_for_traffic_updates(route_data)
            
            if traffic_update.get('needs_update', False):
                logging.debug(f"Traffic update needed: {traffic_update['reason']}")
                
                # Update the route with new traffic data
                new_route = traffic_update.get('new_route')
                if new_route:
                    # Update duration and traffic information
                    route_data['total_time'] = new_route['total_duration']
                    route_data['total_duration_seconds'] = new_route['total_duration_seconds']
                    route_data['traffic_delay_text'] = new_route.get('traffic_delay_text', '')
                    route_data['traffic_conditions'] = new_route.get('traffic_conditions', [])
                    route_data['route_details'] = new_route
                    route_data['last_traffic_update'] = current_time
                    route_data['has_traffic_update'] = True
                    route_data['traffic_update_reason'] = traffic_update['reason']
                    
                    # Store the updated route back in the session
                    session['optimized_route'] = route_data
            else:
                # Still update the last check timestamp
                route_data['last_traffic_update'] = current_time
                session['optimized_route'] = route_data
    
    return jsonify(route_data)

@app.route('/get_navigation')
def get_navigation():
    """Return navigation route from current location to first stop"""
    try:
        from_location = request.args.get('from', '')
        to_location = request.args.get('to', '')
        
        if not from_location or not to_location:
            return jsonify({'error': 'Missing from or to parameters'}), 400
        
        # Parse coordinates
        from_coords = [float(x) for x in from_location.split(',')]
        to_coords = [float(x) for x in to_location.split(',')]
        
        # Convert to [lon, lat] format for the API
        from_coords_api = [from_coords[1], from_coords[0]]
        to_coords_api = [to_coords[1], to_coords[0]]
        
        # Get navigation route details from OpenRouteService
        from route_optimizer import get_route_details
        route_details = get_route_details([from_coords_api, to_coords_api])
        
        if route_details and len(route_details) > 0:
            return jsonify({'route': route_details[0]})
        else:
            return jsonify({'error': 'Could not find navigation route'}), 404
    
    except Exception as e:
        logging.error(f"Error in navigation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/save_route', methods=['POST'])
def save_route():
    """Save the current route to the database"""
    try:
        from models import Route, Location
        import datetime
        
        # Get route data from session
        route_data = session.get('optimized_route')
        if not route_data:
            flash("No route to save.", "danger")
            return redirect(url_for('index'))
        
        # Get route name from form
        route_name = request.form.get('route_name', '')
        
        # Create new route
        new_route = Route(
            name=route_name,
            total_distance=float(route_data['total_distance']),
            total_time=route_data['total_time']
        )
        new_route.coordinates = route_data['coordinates']
        
        # Add locations
        location_details = route_data.get('location_details', [])
        
        # Create a mapping between addresses and location details
        details_map = {}
        if location_details:
            for detail in location_details:
                formatted_addr = detail.get('formatted_address', '')
                if formatted_addr:
                    details_map[formatted_addr] = detail
        
        for i, address in enumerate(route_data['addresses']):
            # Initialize location data
            location_data = {
                'formatted_address': address,
                'position': i
            }
            
            # Try to use stored location details if available
            if address in details_map:
                detail = details_map[address]
                location_data['city'] = detail.get('city', '')
                location_data['street'] = detail.get('street', '')
                location_data['number'] = detail.get('number', '')
                location_data['category'] = detail.get('category', 'home')
                location_data['longitude'] = detail.get('longitude')
                location_data['latitude'] = detail.get('latitude')
                
                # Convert time strings to time objects if present
                time_window_start = detail.get('time_window_start', '')
                time_window_end = detail.get('time_window_end', '')
                
                if time_window_start:
                    try:
                        location_data['time_window_start'] = datetime.datetime.strptime(time_window_start, '%H:%M').time()
                    except:
                        location_data['time_window_start'] = None
                
                if time_window_end:
                    try:
                        location_data['time_window_end'] = datetime.datetime.strptime(time_window_end, '%H:%M').time()
                    except:
                        location_data['time_window_end'] = None
                
                try:
                    location_data['estimated_duration'] = int(detail.get('estimated_duration', 10))
                except:
                    location_data['estimated_duration'] = 10
            else:
                # Fallback to parsing from the address
                parts = address.split(',')
                if len(parts) >= 2:
                    street_parts = parts[0].strip().split(' ')
                    if len(street_parts) >= 2:
                        location_data['street'] = ' '.join(street_parts[:-1])
                        location_data['number'] = street_parts[-1]
                    else:
                        location_data['street'] = parts[0].strip()
                        location_data['number'] = ''
                    
                    location_data['city'] = parts[1].strip()
                else:
                    # Fallback
                    location_data['street'] = address
                    location_data['city'] = 'Unknown'
                    location_data['number'] = ''
                    
                # Get coordinates from route data
                coords = route_data['coordinates'][i]
                location_data['longitude'] = coords[0]
                location_data['latitude'] = coords[1]
                
                # Set default category and estimated_duration
                location_data['category'] = 'home'
                location_data['estimated_duration'] = 10
            
            # Create location
            new_location = Location(**location_data)
            new_route.locations.append(new_location)
        
        # Save to database
        db.session.add(new_route)
        db.session.commit()
        
        flash("Route saved successfully!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        logging.error(f"Error saving route: {str(e)}")
        db.session.rollback()
        flash(f"Error saving route: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/load_route/<int:route_id>')
def load_route(route_id):
    """Load a saved route from the database"""
    try:
        from models import Route
        
        # Get route from database
        route = Route.query.get_or_404(route_id)
        
        # Convert to route data format
        addresses = []
        location_details = []
        
        for location in sorted(route.locations, key=lambda x: x.position):
            addresses.append(location.formatted_address)
            
            # Convert time fields to string format if they exist
            time_window_start = ''
            time_window_end = ''
            
            if location.time_window_start:
                time_window_start = location.time_window_start.strftime('%H:%M')
            
            if location.time_window_end:
                time_window_end = location.time_window_end.strftime('%H:%M')
                
            # Create location detail object
            location_detail = {
                'formatted_address': location.formatted_address,
                'city': location.city,
                'street': location.street,
                'number': location.number,
                'category': location.category,
                'longitude': location.longitude,
                'latitude': location.latitude,
                'time_window_start': time_window_start,
                'time_window_end': time_window_end,
                'estimated_duration': location.estimated_duration
            }
            
            location_details.append(location_detail)
        
        # Create route_details
        route_details = get_route_details(route.coordinates)
        
        # Store in session
        session['optimized_route'] = {
            'coordinates': route.coordinates,
            'addresses': addresses,
            'total_time': route.total_time,
            'total_distance': str(route.total_distance),
            'route_details': route_details,
            'location_details': location_details
        }
        
        flash("Route loaded successfully!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        logging.error(f"Error loading route: {str(e)}")
        flash(f"Error loading route: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/delete_route/<int:route_id>', methods=['POST'])
def delete_route(route_id):
    """Delete a saved route from the database"""
    try:
        from models import Route
        
        # Get route from database
        route = Route.query.get_or_404(route_id)
        
        # Delete from database
        db.session.delete(route)
        db.session.commit()
        
        flash("Route deleted successfully!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        logging.error(f"Error deleting route: {str(e)}")
        db.session.rollback()
        flash(f"Error deleting route: {str(e)}", "danger")
        return redirect(url_for('index'))

# Analytics endpoint
@app.route('/analytics/data')
def analytics_data():
    """Return analytics data for the dashboard"""
    try:
        from models import Route, Location
        
        # Get all routes
        routes = Route.query.all()
        
        # Calculate total distance
        total_distance = sum(route.total_distance for route in routes)
        
        # Calculate total routes
        total_routes = len(routes)
        
        # Calculate distribution of location categories
        locations = Location.query.all()
        category_counts = {}
        for location in locations:
            category = location.category or 'other'
            if category in category_counts:
                category_counts[category] += 1
            else:
                category_counts[category] = 1
        
        # Get routes by month (for time series chart)
        from sqlalchemy import func
        import datetime
        
        # Get data for the last 6 months
        six_months_ago = datetime.datetime.now() - datetime.timedelta(days=180)
        
        monthly_counts = db.session.query(
            func.strftime('%Y-%m', Route.created_at).label('month'), 
            func.count(Route.id).label('count')
        ).filter(Route.created_at >= six_months_ago).group_by('month').all()
        
        # Format into chart-friendly format
        months_data = {month: count for month, count in monthly_counts}
        
        # Return all analytics data
        return jsonify({
            'total_distance': round(total_distance, 1),
            'total_routes': total_routes,
            'category_distribution': category_counts,
            'monthly_routes': months_data
        })
    
    except Exception as e:
        logging.error(f"Error generating analytics data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ----------------- Mobile API Endpoints -----------------

def get_courier_from_api_key(api_key):
    """Helper function to get courier from API key"""
    from models import Courier
    return Courier.query.filter_by(api_key=api_key).first()

def api_key_required(f):
    """Decorator to require API key for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "API key is required"}), 401
            
        courier = get_courier_from_api_key(api_key)
        if not courier:
            return jsonify({"error": "Invalid API key"}), 401
            
        # Add courier to kwargs
        kwargs['courier'] = courier
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """API endpoint for courier login"""
    try:
        from models import Courier
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
            
        courier = Courier.query.filter_by(username=username).first()
        if not courier or not courier.check_password(password):
            return jsonify({"error": "Invalid credentials"}), 401
            
        # Return courier details with API key
        return jsonify({
            "courier": {
                "id": courier.id,
                "username": courier.username,
                "email": courier.email,
                "first_name": courier.first_name,
                "last_name": courier.last_name,
                "api_key": courier.api_key
            }
        })
        
    except Exception as e:
        logging.error(f"API login error: {str(e)}")
        return jsonify({"error": "An error occurred during login"}), 500

@app.route('/api/routes', methods=['GET'])
@api_key_required
def api_get_routes(courier):
    """API endpoint to get routes assigned to courier"""
    try:
        # Get assigned routes for courier
        assignments = courier.assigned_routes
        
        # Extract route details
        routes_data = []
        for assignment in assignments:
            route = assignment.route
            if route:
                route_data = route.to_dict()
                route_data['assignment'] = {
                    'status': assignment.status,
                    'assigned_at': assignment.assigned_at.isoformat(),
                    'started_at': assignment.started_at.isoformat() if assignment.started_at else None,
                    'completed_at': assignment.completed_at.isoformat() if assignment.completed_at else None
                }
                routes_data.append(route_data)
        
        return jsonify({"routes": routes_data})
        
    except Exception as e:
        logging.error(f"API get routes error: {str(e)}")
        return jsonify({"error": "Failed to retrieve routes"}), 500

@app.route('/api/routes/<int:route_id>', methods=['GET'])
@api_key_required
def api_get_route_details(courier, route_id):
    """API endpoint to get details for a specific route"""
    try:
        from models import Route, CourierRouteAssignment
        
        # Check if route exists and is assigned to courier
        assignment = CourierRouteAssignment.query.filter_by(
            courier_id=courier.id, 
            route_id=route_id
        ).first()
        
        if not assignment:
            return jsonify({"error": "Route not found or not assigned to courier"}), 404
            
        # Get route details
        route = Route.query.get(route_id)
        if not route:
            return jsonify({"error": "Route not found"}), 404
            
        # Return detailed route info
        route_data = route.to_dict()
        route_data['assignment'] = {
            'status': assignment.status,
            'assigned_at': assignment.assigned_at.isoformat(),
            'started_at': assignment.started_at.isoformat() if assignment.started_at else None,
            'completed_at': assignment.completed_at.isoformat() if assignment.completed_at else None
        }
        
        return jsonify({"route": route_data})
        
    except Exception as e:
        logging.error(f"API get route details error: {str(e)}")
        return jsonify({"error": "Failed to retrieve route details"}), 500

@app.route('/api/routes/<int:route_id>/start', methods=['POST'])
@api_key_required
def api_start_route(courier, route_id):
    """API endpoint to mark a route as started"""
    try:
        from models import CourierRouteAssignment
        import datetime
        
        # Check if route exists and is assigned to courier
        assignment = CourierRouteAssignment.query.filter_by(
            courier_id=courier.id, 
            route_id=route_id
        ).first()
        
        if not assignment:
            return jsonify({"error": "Route not found or not assigned to courier"}), 404
            
        # Update assignment status
        if assignment.status != 'assigned':
            return jsonify({"error": f"Route already {assignment.status}"}), 400
            
        assignment.status = 'in_progress'
        assignment.started_at = datetime.datetime.utcnow()
        
        # Save changes
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Route started successfully",
            "started_at": assignment.started_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API start route error: {str(e)}")
        return jsonify({"error": "Failed to start route"}), 500

@app.route('/api/routes/<int:route_id>/complete', methods=['POST'])
@api_key_required
def api_complete_route(courier, route_id):
    """API endpoint to mark a route as completed"""
    try:
        from models import CourierRouteAssignment
        import datetime
        
        # Check if route exists and is assigned to courier
        assignment = CourierRouteAssignment.query.filter_by(
            courier_id=courier.id, 
            route_id=route_id
        ).first()
        
        if not assignment:
            return jsonify({"error": "Route not found or not assigned to courier"}), 404
            
        # Update assignment status
        if assignment.status != 'in_progress':
            return jsonify({"error": f"Route not in progress (current status: {assignment.status})"}), 400
            
        assignment.status = 'completed'
        assignment.completed_at = datetime.datetime.utcnow()
        
        # Save changes
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Route completed successfully",
            "completed_at": assignment.completed_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API complete route error: {str(e)}")
        return jsonify({"error": "Failed to complete route"}), 500

@app.route('/api/locations/<int:location_id>/update', methods=['POST'])
@api_key_required
def api_update_location_status(courier, location_id):
    """API endpoint to update a location's status"""
    try:
        from models import Location, CourierRouteAssignment
        import datetime
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Get the location
        location = Location.query.get(location_id)
        if not location:
            return jsonify({"error": "Location not found"}), 404
            
        # Check if courier is assigned to the route
        assignment = CourierRouteAssignment.query.filter_by(
            courier_id=courier.id, 
            route_id=location.route_id
        ).first()
        
        if not assignment:
            return jsonify({"error": "Not authorized to update this location"}), 403
            
        # Update location status
        status = data.get('status')
        if status:
            if status not in ['pending', 'in_progress', 'completed', 'failed']:
                return jsonify({"error": "Invalid status"}), 400
                
            location.status = status
            
            # If completing, set completed_at timestamp
            if status == 'completed':
                location.completed_at = datetime.datetime.utcnow()
        
        # Update delivery notes if provided
        notes = data.get('delivery_notes')
        if notes is not None:  # Accept empty string
            location.delivery_notes = notes
        
        # Save changes
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Location updated successfully",
            "location": location.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"API update location error: {str(e)}")
        return jsonify({"error": "Failed to update location"}), 500

@app.route('/api/profile', methods=['GET'])
@api_key_required
def api_get_profile(courier):
    """API endpoint to get courier profile"""
    try:
        # Format profile data
        profile = {
            "id": courier.id,
            "username": courier.username,
            "email": courier.email,
            "first_name": courier.first_name,
            "last_name": courier.last_name,
            "phone": courier.phone,
            "created_at": courier.created_at.isoformat()
        }
        
        return jsonify({"courier": profile})
        
    except Exception as e:
        logging.error(f"API get profile error: {str(e)}")
        return jsonify({"error": "Failed to retrieve profile"}), 500

# ----------------- Admin Panel Routes -----------------

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    try:
        from models import Courier, Route, CourierRouteAssignment, Location
        from sqlalchemy import func
        import datetime
        
        # Get counts
        courier_count = Courier.query.count()
        route_count = Route.query.count()
        active_assignments = CourierRouteAssignment.query.filter(
            CourierRouteAssignment.status.in_(['assigned', 'in_progress'])
        ).count()
        
        # Get recent activities
        recent_assignments = CourierRouteAssignment.query.order_by(
            CourierRouteAssignment.assigned_at.desc()
        ).limit(5).all()
        
        recent_activities = []
        for assignment in recent_assignments:
            courier = Courier.query.get(assignment.courier_id)
            route = Route.query.get(assignment.route_id)
            
            if courier and route:
                courier_name = f"{courier.first_name} {courier.last_name}" if courier.first_name else courier.username
                
                activity = {
                    'timestamp': assignment.assigned_at.strftime('%Y-%m-%d %H:%M'),
                    'courier': courier_name,
                    'action': 'Assigned to route',
                    'details': f"{route.name or f'Route {route.id}'} ({len(route.locations)} stops)"
                }
                recent_activities.append(activity)
        
        # Get delivery statistics for chart
        # Last 7 days
        days = 7
        delivery_stats = {
            'labels': [],
            'completed': [],
            'failed': []
        }
        
        for i in range(days - 1, -1, -1):
            date = datetime.datetime.now().date() - datetime.timedelta(days=i)
            delivery_stats['labels'].append(date.strftime('%m-%d'))
            
            # Placeholder data - in a real app, this would be actual data from database
            delivery_stats['completed'].append(0)
            delivery_stats['failed'].append(0)
            
        # Get category distribution
        category_stats = {
            'labels': ['Home', 'Office', 'Business', 'Pickup Point', 'Other'],
            'data': []
        }
        
        # Get actual category counts
        for category in ['home', 'office', 'business', 'pickup_point', 'other']:
            count = Location.query.filter_by(category=category).count()
            category_stats['data'].append(count)
        
        return render_template('admin/index.html', 
                              courier_count=courier_count,
                              route_count=route_count,
                              active_assignments=active_assignments,
                              recent_activities=recent_activities,
                              delivery_stats=delivery_stats,
                              category_stats=category_stats)
                              
    except Exception as e:
        logging.error(f"Admin dashboard error: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/admin/couriers')
def admin_couriers():
    """Admin couriers management page"""
    try:
        from models import Courier, CourierRouteAssignment
        
        # Get all couriers with active route count
        couriers = []
        for courier in Courier.query.all():
            active_routes = CourierRouteAssignment.query.filter(
                CourierRouteAssignment.courier_id == courier.id,
                CourierRouteAssignment.status.in_(['assigned', 'in_progress'])
            ).count()
            
            courier_data = {
                'id': courier.id,
                'username': courier.username,
                'email': courier.email,
                'first_name': courier.first_name,
                'last_name': courier.last_name,
                'phone': courier.phone,
                'active_routes': active_routes
            }
            couriers.append(courier_data)
            
        return render_template('admin/couriers.html', couriers=couriers)
        
    except Exception as e:
        logging.error(f"Admin couriers error: {str(e)}")
        flash(f"Error loading couriers: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/couriers/add', methods=['POST'])
def admin_add_courier():
    """Add a new courier"""
    try:
        from models import Courier
        
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
        # Check if courier already exists
        if Courier.query.filter_by(username=username).first():
            flash(f"Courier with username '{username}' already exists", "danger")
            return redirect(url_for('admin_couriers'))
            
        if Courier.query.filter_by(email=email).first():
            flash(f"Courier with email '{email}' already exists", "danger")
            return redirect(url_for('admin_couriers'))
        
        # Create new courier
        courier = Courier(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        courier.set_password(password)
        
        db.session.add(courier)
        db.session.commit()
        
        flash(f"Courier '{username}' added successfully", "success")
        return redirect(url_for('admin_couriers'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Add courier error: {str(e)}")
        flash(f"Error adding courier: {str(e)}", "danger")
        return redirect(url_for('admin_couriers'))

@app.route('/admin/couriers/edit', methods=['POST'])
def admin_edit_courier():
    """Edit an existing courier"""
    try:
        from models import Courier
        
        courier_id = request.form.get('courier_id')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
        # Get courier
        courier = Courier.query.get(courier_id)
        if not courier:
            flash("Courier not found", "danger")
            return redirect(url_for('admin_couriers'))
            
        # Check for username/email conflicts
        username_conflict = Courier.query.filter_by(username=username).first()
        if username_conflict and username_conflict.id != int(courier_id):
            flash(f"Courier with username '{username}' already exists", "danger")
            return redirect(url_for('admin_couriers'))
            
        email_conflict = Courier.query.filter_by(email=email).first()
        if email_conflict and email_conflict.id != int(courier_id):
            flash(f"Courier with email '{email}' already exists", "danger")
            return redirect(url_for('admin_couriers'))
        
        # Update courier
        courier.username = username
        courier.email = email
        courier.first_name = first_name
        courier.last_name = last_name
        courier.phone = phone
        
        # Update password if provided
        if password:
            courier.set_password(password)
        
        db.session.commit()
        
        flash(f"Courier '{username}' updated successfully", "success")
        return redirect(url_for('admin_couriers'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Edit courier error: {str(e)}")
        flash(f"Error updating courier: {str(e)}", "danger")
        return redirect(url_for('admin_couriers'))

@app.route('/admin/couriers/<int:courier_id>/delete', methods=['POST'])
def admin_delete_courier(courier_id):
    """Delete a courier"""
    try:
        from models import Courier, CourierRouteAssignment
        
        # Check if courier has active assignments
        active_assignments = CourierRouteAssignment.query.filter(
            CourierRouteAssignment.courier_id == courier_id,
            CourierRouteAssignment.status.in_(['assigned', 'in_progress'])
        ).count()
        
        if active_assignments > 0:
            flash("Cannot delete courier with active route assignments", "danger")
            return redirect(url_for('admin_couriers'))
        
        # Get courier
        courier = Courier.query.get(courier_id)
        if not courier:
            flash("Courier not found", "danger")
            return redirect(url_for('admin_couriers'))
            
        # Delete courier
        db.session.delete(courier)
        db.session.commit()
        
        flash(f"Courier '{courier.username}' deleted successfully", "success")
        return redirect(url_for('admin_couriers'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Delete courier error: {str(e)}")
        flash(f"Error deleting courier: {str(e)}", "danger")
        return redirect(url_for('admin_couriers'))

@app.route('/admin/couriers/<int:courier_id>/regenerate-api-key')
def admin_regenerate_api_key(courier_id):
    """Regenerate API key for a courier"""
    try:
        from models import Courier
        
        # Get courier
        courier = Courier.query.get(courier_id)
        if not courier:
            flash("Courier not found", "danger")
            return redirect(url_for('admin_couriers'))
            
        # Regenerate API key
        new_key = courier.regenerate_api_key()
        db.session.commit()
        
        flash(f"API key regenerated successfully for '{courier.username}': {new_key}", "success")
        return redirect(url_for('admin_couriers'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Regenerate API key error: {str(e)}")
        flash(f"Error regenerating API key: {str(e)}", "danger")
        return redirect(url_for('admin_couriers'))

@app.route('/admin/routes')
def admin_routes():
    """Admin routes management page"""
    try:
        from models import Route
        
        # Get all routes
        routes = Route.query.order_by(Route.created_at.desc()).all()
        
        return render_template('admin/routes.html', routes=routes)
        
    except Exception as e:
        logging.error(f"Admin routes error: {str(e)}")
        flash(f"Error loading routes: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/assignments')
def admin_assignments():
    """Admin assignments management page"""
    try:
        from models import CourierRouteAssignment, Courier, Route
        
        # Get all assignments
        assignments = []
        for assignment in CourierRouteAssignment.query.order_by(CourierRouteAssignment.assigned_at.desc()).all():
            courier = Courier.query.get(assignment.courier_id)
            route = Route.query.get(assignment.route_id)
            
            if courier and route:
                courier_name = f"{courier.first_name} {courier.last_name}" if courier.first_name else courier.username
                
                assignment_data = {
                    'id': assignment.id,
                    'courier_id': courier.id,
                    'courier_name': courier_name,
                    'route_id': route.id,
                    'route_name': route.name or f'Route {route.id}',
                    'status': assignment.status,
                    'assigned_at': assignment.assigned_at.strftime('%Y-%m-%d %H:%M'),
                    'started_at': assignment.started_at.strftime('%Y-%m-%d %H:%M') if assignment.started_at else None,
                    'completed_at': assignment.completed_at.strftime('%Y-%m-%d %H:%M') if assignment.completed_at else None
                }
                assignments.append(assignment_data)
                
        # Get couriers and routes for assignment form
        couriers_list = Courier.query.all()
        routes_list = Route.query.all()
        
        return render_template('admin/assignments.html', 
                              assignments=assignments,
                              couriers_list=couriers_list,
                              routes_list=routes_list)
        
    except Exception as e:
        logging.error(f"Admin assignments error: {str(e)}")
        flash(f"Error loading assignments: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/assignments/create', methods=['POST'])
def admin_create_assignment():
    """Create a new route assignment"""
    try:
        from models import CourierRouteAssignment, Courier, Route
        
        courier_id = request.form.get('courier_id')
        route_id = request.form.get('route_id')
        
        # Check if courier and route exist
        courier = Courier.query.get(courier_id)
        route = Route.query.get(route_id)
        
        if not courier:
            flash("Courier not found", "danger")
            return redirect(url_for('admin_assignments'))
            
        if not route:
            flash("Route not found", "danger")
            return redirect(url_for('admin_assignments'))
            
        # Check if assignment already exists
        existing = CourierRouteAssignment.query.filter_by(
            courier_id=courier_id,
            route_id=route_id,
            status='assigned'
        ).first()
        
        if existing:
            flash("This route is already assigned to this courier", "warning")
            return redirect(url_for('admin_assignments'))
            
        # Create new assignment
        assignment = CourierRouteAssignment(
            courier_id=courier_id,
            route_id=route_id
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        flash(f"Route assigned to {courier.username} successfully", "success")
        return redirect(url_for('admin_assignments'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Create assignment error: {str(e)}")
        flash(f"Error creating assignment: {str(e)}", "danger")
        return redirect(url_for('admin_assignments'))

@app.route('/admin/assignments/<int:assignment_id>')
def admin_view_assignment(assignment_id):
    """View assignment details"""
    try:
        from models import CourierRouteAssignment, Courier, Route, Location
        
        # Get assignment
        assignment = CourierRouteAssignment.query.get(assignment_id)
        if not assignment:
            flash("Assignment not found", "danger")
            return redirect(url_for('admin_assignments'))
            
        # Get courier and route
        courier = Courier.query.get(assignment.courier_id)
        route = Route.query.get(assignment.route_id)
        
        if not courier or not route:
            flash("Assignment data incomplete", "danger")
            return redirect(url_for('admin_assignments'))
            
        # Get locations
        locations = Location.query.filter_by(route_id=route.id).order_by(Location.position).all()
        
        assignment_data = {
            'id': assignment.id,
            'courier': courier,
            'route': route,
            'status': assignment.status,
            'assigned_at': assignment.assigned_at,
            'started_at': assignment.started_at,
            'completed_at': assignment.completed_at,
            'locations': locations
        }
        
        return render_template('admin/view_assignment.html', assignment=assignment_data)
        
    except Exception as e:
        logging.error(f"View assignment error: {str(e)}")
        flash(f"Error loading assignment: {str(e)}", "danger")
        return redirect(url_for('admin_assignments'))

@app.route('/admin/assignments/<int:assignment_id>/cancel', methods=['POST'])
def admin_cancel_assignment(assignment_id):
    """Cancel a route assignment"""
    try:
        from models import CourierRouteAssignment
        import datetime
        
        # Get assignment
        assignment = CourierRouteAssignment.query.get(assignment_id)
        if not assignment:
            flash("Assignment not found", "danger")
            return redirect(url_for('admin_assignments'))
            
        # Check if assignment can be canceled
        if assignment.status not in ['assigned', 'in_progress']:
            flash(f"Cannot cancel assignment with status '{assignment.status}'", "danger")
            return redirect(url_for('admin_assignments'))
            
        # Cancel assignment
        assignment.status = 'canceled'
        assignment.completed_at = datetime.datetime.utcnow()
        
        db.session.commit()
        
        flash("Assignment canceled successfully", "success")
        return redirect(url_for('admin_assignments'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Cancel assignment error: {str(e)}")
        flash(f"Error canceling assignment: {str(e)}", "danger")
        return redirect(url_for('admin_assignments'))

@app.route('/admin/courier/<int:courier_id>/routes')
def admin_courier_routes(courier_id):
    """View routes assigned to a courier"""
    try:
        from models import Courier, CourierRouteAssignment, Route
        
        # Get courier
        courier = Courier.query.get(courier_id)
        if not courier:
            flash("Courier not found", "danger")
            return redirect(url_for('admin_couriers'))
            
        # Get assignments
        assignments = []
        for assignment in CourierRouteAssignment.query.filter_by(courier_id=courier_id).order_by(CourierRouteAssignment.assigned_at.desc()).all():
            route = Route.query.get(assignment.route_id)
            
            if route:
                assignment_data = {
                    'id': assignment.id,
                    'route_id': route.id,
                    'route_name': route.name or f'Route {route.id}',
                    'stops': len(route.locations),
                    'total_distance': route.total_distance,
                    'total_time': route.total_time,
                    'status': assignment.status,
                    'assigned_at': assignment.assigned_at.strftime('%Y-%m-%d %H:%M'),
                    'started_at': assignment.started_at.strftime('%Y-%m-%d %H:%M') if assignment.started_at else None,
                    'completed_at': assignment.completed_at.strftime('%Y-%m-%d %H:%M') if assignment.completed_at else None
                }
                assignments.append(assignment_data)
                
        return render_template('admin/courier_routes.html', courier=courier, assignments=assignments)
        
    except Exception as e:
        logging.error(f"Courier routes error: {str(e)}")
        flash(f"Error loading courier routes: {str(e)}", "danger")
        return redirect(url_for('admin_couriers'))

# Create database tables
with app.app_context():
    import models  # noqa: F401
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
