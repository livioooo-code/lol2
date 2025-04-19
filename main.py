import os
import csv
import io
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, make_response
import config
from route_optimizer import optimize_route, geocode_address, get_route_details, check_for_traffic_updates

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_courier_nav_secret")

# Skip database initialization for now to focus on navigation feature

@app.route('/')
def index():
    """Display the main page with the navigation form"""
    return render_template('index.html', api_key=config.OPENROUTE_API_KEY, saved_routes=[])

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

        # Optimize route
        optimized_route, total_time, total_distance = optimize_route(coords)
        
        if not optimized_route:
            flash("Could not optimize route. Please try different locations.", "danger")
            return redirect(url_for('index'))

        # Get route details with real-time traffic information
        include_traffic = request.form.get('include_traffic', 'true').lower() == 'true'
        route_details = get_route_details(optimized_route, include_traffic=include_traffic)
        
        # Sprawdź, czy mamy geometrię tras
        for i, segment in enumerate(route_details.get('segments', [])):
            if 'geometry' in segment:
                num_points = len(segment['geometry'])
                logging.debug(f"Segment {i} ma {num_points} punktów geometrycznych")
        
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
            'last_traffic_update': int(time.time()),
            # Dodatkowo wyciągamy segmenty trasy na górny poziom dla łatwiejszego dostępu w JavaScript
            'segments': route_details.get('segments', [])
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
    import time
    
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
        route_details = get_route_details([from_coords_api, to_coords_api])
        
        if route_details and len(route_details) > 0:
            return jsonify({'route': route_details[0]})
        else:
            return jsonify({'error': 'Could not find navigation route'}), 404
    
    except Exception as e:
        logging.error(f"Error in navigation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_route')
def export_route():
    """Export route data in various formats"""
    try:
        export_format = request.args.get('format', 'json')
        route_data = session.get('optimized_route', {})
        
        if not route_data or 'coordinates' not in route_data:
            flash("No route data available to export.", "warning")
            return redirect(url_for('index'))
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'json':
            # Export as JSON
            response = make_response(jsonify(route_data))
            response.headers.set('Content-Type', 'application/json')
            response.headers.set('Content-Disposition', f'attachment; filename=route_{timestamp}.json')
            return response
            
        elif export_format == 'csv':
            # Export as CSV
            csv_data = io.StringIO()
            writer = csv.writer(csv_data)
            
            # Write header
            writer.writerow(['Stop', 'Address', 'Coordinates', 'Category', 'Time Window'])
            
            # Write data for each stop
            for i, address in enumerate(route_data.get('addresses', [])):
                # Skip the last point if it's a return to start
                if i == len(route_data.get('addresses', [])) - 1 and i > 0 and address == route_data['addresses'][0]:
                    continue
                
                coords = route_data['coordinates'][i]
                details = route_data.get('location_details', {})[i] if route_data.get('location_details') and i < len(route_data.get('location_details', {})) else {}
                
                category = details.get('category', 'home')
                time_window = f"{details.get('time_window_start', '')} - {details.get('time_window_end', '')}" if details.get('time_window_start') else ''
                
                writer.writerow([
                    i + 1,
                    address,
                    f"{coords[1]},{coords[0]}",  # Lat, Lon format
                    category,
                    time_window
                ])
            
            # Add route summary
            writer.writerow([])
            writer.writerow(['Total Distance', f"{route_data.get('total_distance', 0)} km"])
            writer.writerow(['Estimated Time', route_data.get('total_time', '')])
            if route_data.get('traffic_delay_text'):
                writer.writerow(['Traffic Info', route_data.get('traffic_delay_text', '')])
            
            response = make_response(csv_data.getvalue())
            response.headers.set('Content-Type', 'text/csv')
            response.headers.set('Content-Disposition', f'attachment; filename=route_{timestamp}.csv')
            return response
            
        elif export_format == 'gpx':
            # Export as GPX (GPS Exchange Format)
            gpx = '<?xml version="1.0" encoding="UTF-8"?>\n'
            gpx += '<gpx version="1.1" creator="CourierNavigator" xmlns="http://www.topografix.com/GPX/1/1">\n'
            
            # Add metadata
            gpx += '  <metadata>\n'
            gpx += f'    <name>Courier Route {timestamp}</name>\n'
            gpx += f'    <time>{datetime.now().isoformat()}</time>\n'
            gpx += '  </metadata>\n'
            
            # Add route
            gpx += '  <rte>\n'
            gpx += f'    <name>Route {timestamp}</name>\n'
            
            # Add route points
            for i, address in enumerate(route_data.get('addresses', [])):
                # Skip the last point if it's a return to start
                if i == len(route_data.get('addresses', [])) - 1 and i > 0 and address == route_data['addresses'][0]:
                    continue
                
                coords = route_data['coordinates'][i]
                details = route_data.get('location_details', {})[i] if route_data.get('location_details') and i < len(route_data.get('location_details', {})) else {}
                
                gpx += '    <rtept lat="{}" lon="{}">\n'.format(coords[1], coords[0])
                gpx += f'      <name>Stop {i+1}: {address}</name>\n'
                if details.get('category'):
                    gpx += f'      <type>{details.get("category")}</type>\n'
                gpx += '    </rtept>\n'
            
            # Add detailed track points if we have them
            if 'segments' in route_data and route_data['segments']:
                gpx += '  </rte>\n'
                gpx += '  <trk>\n'
                gpx += f'    <name>Detailed Route {timestamp}</name>\n'
                
                for i, segment in enumerate(route_data['segments']):
                    gpx += '    <trkseg>\n'
                    
                    if 'geometry' in segment and segment['geometry']:
                        for point in segment['geometry']:
                            gpx += '      <trkpt lat="{}" lon="{}">\n'.format(point[1], point[0])
                            gpx += '      </trkpt>\n'
                    
                    gpx += '    </trkseg>\n'
                
                gpx += '  </trk>\n'
            else:
                gpx += '  </rte>\n'
            
            gpx += '</gpx>'
            
            response = make_response(gpx)
            response.headers.set('Content-Type', 'application/gpx+xml')
            response.headers.set('Content-Disposition', f'attachment; filename=route_{timestamp}.gpx')
            return response
        
        else:
            flash(f"Unsupported export format: {export_format}", "danger")
            return redirect(url_for('index'))
            
    except Exception as e:
        logging.error(f"Error exporting route: {str(e)}")
        flash(f"Error exporting route: {str(e)}", "danger")
        return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
