import requests
import logging
import json
import math
import time
import random
from itertools import permutations
import config
from datetime import datetime

def geocode_address(address):
    """Convert address to coordinates using OpenRouteService Geocoding API"""
    try:
        params = {
            'api_key': config.OPENROUTE_API_KEY,
            'text': address
        }
        
        response = requests.get(config.OPENROUTE_GEOCODE_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        if data['features'] and len(data['features']) > 0:
            # Extract coordinates [longitude, latitude]
            coords = data['features'][0]['geometry']['coordinates']
            formatted_address = data['features'][0]['properties'].get('label', address)
            return {
                'coordinates': coords,
                'formatted_address': formatted_address
            }
        else:
            logging.error(f"No results found for address: {address}")
            return None
    except Exception as e:
        logging.error(f"Error geocoding address {address}: {str(e)}")
        return None

def get_distance_matrix(coordinates):
    """Get distance and duration matrix between all points using OpenRouteService API"""
    try:
        headers = {
            'Authorization': config.OPENROUTE_API_KEY,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json, application/geo+json, application/gpx+xml'
        }
        
        body = {
            'locations': coordinates,
            'metrics': ['distance', 'duration'],
            'units': 'km'
        }
        
        response = requests.post(
            config.OPENROUTE_MATRIX_URL,
            headers=headers,
            json=body
        )
        response.raise_for_status()
        
        data = response.json()
        return {
            'durations': data['durations'],
            'distances': data['distances']
        }
    except Exception as e:
        logging.error(f"Error getting distance matrix: {str(e)}")
        return None

def optimize_route(coordinates):
    """
    Optimize route using a simple TSP solver with the distance matrix
    For small number of points, we'll use brute force (permutations)
    For larger sets, we'd need a more sophisticated algorithm
    """
    try:
        if len(coordinates) <= 1:
            return coordinates, 0, 0
            
        # Get distance/duration matrix from API
        matrix = get_distance_matrix(coordinates)
        
        if not matrix:
            return None, 0, 0
            
        durations = matrix['durations']
        distances = matrix['distances']
        
        # For small number of points (<=10), use brute force approach
        if len(coordinates) <= 8:
            # Try all permutations starting with the first point
            start = 0
            min_duration = float('inf')
            best_route_indices = None
            
            # Generate all possible routes starting from the first location
            for perm in permutations(range(1, len(coordinates))):
                route = [start] + list(perm) + [start]  # Complete round trip
                
                # Calculate total duration for this route
                total_duration = 0
                for i in range(len(route) - 1):
                    from_idx = route[i]
                    to_idx = route[i + 1]
                    total_duration += durations[from_idx][to_idx]
                
                if total_duration < min_duration:
                    min_duration = total_duration
                    best_route_indices = route
        else:
            # For larger sets, use a greedy nearest neighbor approach
            start = 0
            current = start
            route_indices = [current]
            unvisited = set(range(1, len(coordinates)))
            
            while unvisited:
                # Find nearest unvisited location
                nearest = min(unvisited, key=lambda x: durations[current][x])
                route_indices.append(nearest)
                unvisited.remove(nearest)
                current = nearest
                
            # Return to start
            route_indices.append(start)
            best_route_indices = route_indices
            
            # Calculate total duration
            min_duration = 0
            for i in range(len(best_route_indices) - 1):
                from_idx = best_route_indices[i]
                to_idx = best_route_indices[i + 1]
                min_duration += durations[from_idx][to_idx]
        
        # Convert route indices to coordinates
        optimized_route = [coordinates[i] for i in best_route_indices] if best_route_indices else []
        
        # Calculate total distance
        total_distance = 0
        if best_route_indices and distances:
            for i in range(len(best_route_indices) - 1):
                from_idx = best_route_indices[i]
                to_idx = best_route_indices[i + 1]
                total_distance += distances[from_idx][to_idx]
            
        # Convert seconds to hours:minutes format
        hours = int(min_duration / 3600)
        minutes = int((min_duration % 3600) / 60)
        time_str = f"{hours}h {minutes}m"
        
        # Round distance to 1 decimal place
        distance_str = f"{total_distance:.1f}"
        
        return optimized_route, time_str, distance_str
        
    except Exception as e:
        logging.error(f"Error optimizing route: {str(e)}")
        return None, 0, 0

def get_weather(coords):
    """Get current weather conditions for a location using OpenWeatherMap API"""
    try:
        # Convert coordinates from [longitude, latitude] to [latitude, longitude]
        lat = coords[1]
        lon = coords[0]
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': config.WEATHER_API_KEY,
            'units': 'metric'  # Use metric units (Celsius, km/h)
        }
        
        response = requests.get(config.WEATHER_API_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract relevant weather information
        weather_data = {
            'condition': data['weather'][0]['main'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon'],
            'temp': round(data['main']['temp']),
            'feels_like': round(data['main']['feels_like']),
            'humidity': data['main']['humidity'],
            'wind_speed': data['wind']['speed'],
            'location_name': data['name'],
            'updated_at': datetime.now().strftime('%H:%M'),
            'icon_url': f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png"
        }
        
        # Add weather alerts if available
        if 'alerts' in data:
            weather_data['alerts'] = [{
                'event': alert['event'],
                'description': alert['description'],
                'start': datetime.fromtimestamp(alert['start']).strftime('%Y-%m-%d %H:%M'),
                'end': datetime.fromtimestamp(alert['end']).strftime('%Y-%m-%d %H:%M')
            } for alert in data['alerts']]
        else:
            weather_data['alerts'] = []
            
        return weather_data
    except Exception as e:
        logging.error(f"Error fetching weather data: {str(e)}")
        return None

def simulate_traffic_conditions(start, end):
    """
    Simulates traffic conditions based on time of day and location
    This is a placeholder for real traffic API data
    
    Returns:
        Integer traffic level (0-3)
        0 = Free flowing, 1 = Light traffic, 2 = Moderate traffic, 3 = Heavy traffic
    """
    # W prawdziwej implementacji, to zapytanie do API ruchu drogowego
    # Dla celów demonstracyjnych, symulujemy ruch na podstawie:
    # 1. Godziny
    # 2. Dnia tygodnia
    # 3. Czynnika losowego
    # 4. Długości segmentu (dłuższe segmenty mają większe prawdopodobieństwo korków)
    
    import random
    from datetime import datetime
    
    # Pobierz aktualny czas
    now = datetime.now()
    hour = now.hour
    day = now.weekday()  # 0 = Poniedziałek, 6 = Niedziela
    
    # Oblicz długość segmentu (w km)
    segment_length = calculate_distance(start, end)
    
    # Bazowy poziom ruchu oparty o porę dnia
    if hour >= 7 and hour < 10:  # Poranne godziny szczytu
        base_level = 2
    elif hour >= 16 and hour < 19:  # Popołudniowe godziny szczytu
        base_level = 2
    elif hour >= 10 and hour < 16:  # Pora południowa
        base_level = 1
    elif hour >= 19 and hour < 22:  # Wieczór
        base_level = 1
    else:  # Późna noc i wczesny poranek
        base_level = 0
        
    # Dostosuj do weekendów
    if day >= 5:  # Weekend
        base_level = max(0, base_level - 1)
        
    # Dostosuj w zależności od długości segmentu
    # Dłuższe segmenty mają większe szanse na korki
    if segment_length > 5:  # Długi segment (>5km)
        length_factor = 1
    elif segment_length > 2:  # Średni segment (2-5km)
        length_factor = 0
    else:  # Krótki segment (<2km)
        length_factor = -1
        
    # Dodaj losowość (±1 poziom), ale z większym prawdopodobieństwem wyższych poziomów dla dobrej wizualizacji
    # W celach testowych zwiększamy szansę na wyższe poziomy ruchu, aby ładnie pokazać natężenie ruchu
    random_weights = [0.1, 0.2, 0.3, 0.4]  # Większa szansa na wyższe poziomy ruchu
    adjustment = random.choices([-1, 0, 1, 2], weights=random_weights)[0]
    
    # Łącznie wszystkich czynników z limitem 0-3
    traffic_level = max(0, min(3, base_level + length_factor + adjustment))
    
    # Dodatkowe logowanie do debugowania
    logging.debug(f"Symulowany ruch: {traffic_level} (baza: {base_level}, długość: {length_factor}, losowo: {adjustment})")
    
    return traffic_level

def calculate_distance(point1, point2):
    """Calculate straight-line distance between two points in km"""
    # Earth radius in km
    R = 6371.0
    
    # Convert coordinates to radians
    lon1, lat1 = math.radians(point1[0]), math.radians(point1[1])
    lon2, lat2 = math.radians(point2[0]), math.radians(point2[1])
    
    # Differences in coordinates
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

def get_route_details(coordinates, include_traffic=True):
    """
    Get detailed route information between consecutive points
    
    Args:
        coordinates: List of longitude/latitude pairs
        include_traffic: Whether to include real-time traffic data (default: True)
    
    Returns:
        Dictionary with route segments, total distance, and duration
    """
    route_segments = []
    total_distance = 0
    total_duration = 0
    traffic_conditions = []
    traffic_delay_seconds = 0
    
    # Calculate route between each consecutive point
    for i in range(len(coordinates) - 1):
        start = coordinates[i]
        end = coordinates[i + 1]
        
        # Call OpenRouteService Directions API
        headers = {
            'Authorization': config.OPENROUTE_API_KEY,
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        # Base parameters
        body = {
            "coordinates": [[start[0], start[1]], [end[0], end[1]]],
            "instructions": True,
            "format": "json",  # Zmiana: używamy formatu JSON zamiast GeoJSON
            "geometry": True,
            "geometry_simplify": False,  # Nie upraszczaj geometrii trasy
            "preference": "recommended",  # Preferowana trasa
            "continue_straight": True,
            "radiuses": [-1, -1]  # Użyj domyślnej (maksymalnej) odległości wyszukiwania
        }
        
        try:
            response = requests.post(
                config.OPENROUTE_DIRECTIONS_URL,
                json=body, 
                headers=headers
            )
            response.raise_for_status()
            route_data = response.json()
            
            # Extract geometry from the polyline
            route_geometry = []
            if 'routes' in route_data and len(route_data['routes']) > 0:
                route = route_data['routes'][0]
                
                # Check if there's polyline encoded geometry
                if 'geometry' in route:
                    geometry_str = route['geometry']
                    # Przekształć ciąg polyline na współrzędne
                    import polyline
                    try:
                        # Próbujemy zdekodować zakodowaną geometrię, ale to może nie działać
                        # bez biblioteki polyline, więc obsługujemy błąd
                        decoded_coords = polyline.decode(geometry_str) 
                        # Zamiana [lat, lon] na [lon, lat] wymagane przez naszą aplikację
                        route_geometry = [[lon, lat] for lat, lon in decoded_coords]
                        logging.debug(f"Segment {i}: Dekodowano {len(route_geometry)} punktów z polyline")
                    except:
                        logging.error(f"Nie można zdekodować polyline, używanie punktów z segmentów")
                        # Jeśli dekodowanie się nie powiodło, spróbujmy pobrać punkty z trasy
                        if 'segments' in route and len(route['segments']) > 0:
                            segment_data = route['segments'][0]
                            # Zbierz początkowy punkt i wszystkie punkty końcowe kroków
                            route_geometry = [[start[0], start[1]]]
                            for step in segment_data.get('steps', []):
                                if 'way_points' in step and len(step['way_points']) > 1:
                                    # Dodaj tylko punkt końcowy kroku
                                    way_point_idx = step['way_points'][1]
                                    if way_point_idx < len(route_data.get('way_points', [])):
                                        point = route_data['way_points'][way_point_idx]
                                        route_geometry.append([point[0], point[1]])
                            # Dodaj punkt końcowy trasy, jeśli go nie ma
                            if route_geometry[-1] != [end[0], end[1]]:
                                route_geometry.append([end[0], end[1]])
                        else:
                            # Jeśli nie ma danych o segmentach, użyj prostej linii
                            route_geometry = [[start[0], start[1]], [end[0], end[1]]]
                
                # Jeśli nadal nie mamy geometrii, użyjmy danych z summary
                if not route_geometry:
                    route_geometry = [[start[0], start[1]], [end[0], end[1]]]
                
                # Log the number of geometry points for debugging
                logging.debug(f"Segment {i}: Używanie {len(route_geometry)} punktów geometrycznych dla trasy")
                
                # Extract traffic conditions if available
                # This is where you would parse traffic info from the API response
                # For demonstration, we'll simulate traffic conditions
                traffic_level = simulate_traffic_conditions(start, end)
                
                # Calculate simulated delay based on traffic level
                # In a real implementation, this would come from the API
                base_duration = route['summary']['duration']
                if include_traffic and traffic_level > 0:
                    # Add delay based on traffic level (0-3)
                    delay_factor = [0, 0.15, 0.3, 0.6][traffic_level]
                    traffic_delay = base_duration * delay_factor
                else:
                    traffic_delay = 0
                
                # Store the adjusted duration
                adjusted_duration = base_duration + traffic_delay
                
                # Set the color based on traffic level
                if traffic_level == 0:
                    traffic_color = 'green'  # Free flowing
                elif traffic_level == 1:
                    traffic_color = 'yellow'  # Light traffic
                elif traffic_level == 2:
                    traffic_color = 'orange'  # Moderate traffic
                else:
                    traffic_color = 'red'     # Heavy traffic
                
                # Get weather data for each destination point
                weather_data = None
                if i < len(coordinates) - 2:  # Don't get weather for the return to start
                    weather_data = get_weather(end)
                
                segment = {
                    'start_idx': i,
                    'end_idx': i + 1,
                    'distance': route['summary']['distance'] / 1000,  # Convert to km
                    'duration': adjusted_duration,  # seconds, including traffic delay
                    'base_duration': base_duration,  # seconds, without traffic
                    'traffic_delay': traffic_delay,  # seconds of delay due to traffic
                    'traffic_level': traffic_level,  # 0-3 scale
                    'traffic_color': traffic_color,  # Color to use when displaying on map
                    'geometry': route_geometry,
                    'weather': weather_data
                }
                
                # Get maneuver instructions if available
                instructions = []
                if 'segments' in route:
                    for segment_data in route['segments']:
                        for step in segment_data.get('steps', []):
                            instructions.append({
                                'instruction': step.get('instruction', ''),
                                'distance': step.get('distance', 0),
                                'duration': step.get('duration', 0)
                            })
                segment['instructions'] = instructions
                
                total_distance += segment['distance']
                total_duration += segment['duration']
                traffic_delay_seconds += traffic_delay
                traffic_conditions.append({
                    'segment': i,
                    'level': traffic_level,
                    'color': traffic_color,
                    'delay_seconds': traffic_delay
                })
                route_segments.append(segment)
            else:
                # Fall back to a simple straight line if no route data
                logging.error(f"No route data received for segment {i}")
                segment = {
                    'start_idx': i,
                    'end_idx': i + 1,
                    'distance': calculate_distance(start, end),
                    'duration': 0,  # Cannot determine duration
                    'base_duration': 0,
                    'traffic_delay': 0,
                    'traffic_level': 0,
                    'traffic_color': 'gray',
                    'geometry': [[start[0], start[1]], [end[0], end[1]]],
                    'instructions': [],
                    'weather': None
                }
                route_segments.append(segment)
        except Exception as e:
            logging.error(f"Error fetching route details: {str(e)}")
            # Fall back to a simple straight line if route can't be calculated
            segment = {
                'start_idx': i,
                'end_idx': i + 1,
                'distance': calculate_distance(start, end),
                'duration': 0,  # Cannot determine duration
                'base_duration': 0,
                'traffic_delay': 0,
                'traffic_level': 0,
                'traffic_color': 'gray',
                'geometry': [[start[0], start[1]], [end[0], end[1]]],
                'instructions': [],
                'weather': None
            }
            route_segments.append(segment)
    
    # Format total_duration as a string (e.g., "2h 30m")
    hours = int(total_duration / 3600)
    minutes = int((total_duration % 3600) / 60)
    formatted_duration = ''
    if hours > 0:
        formatted_duration += f"{hours}h "
    formatted_duration += f"{minutes}m"
    
    # Format traffic delay as a string
    delay_minutes = int(traffic_delay_seconds / 60)
    traffic_delay_text = f"+{delay_minutes}m due to traffic" if delay_minutes > 0 else "No delays"
    
    return {
        'segments': route_segments,
        'total_distance': round(total_distance, 2),
        'total_duration': formatted_duration,
        'total_duration_seconds': total_duration,
        'base_duration_seconds': total_duration - traffic_delay_seconds,
        'traffic_delay_seconds': traffic_delay_seconds,
        'traffic_delay_text': traffic_delay_text,
        'traffic_conditions': traffic_conditions,
        'has_traffic_data': include_traffic,
        'timestamp': int(time.time())
    }

def check_for_traffic_updates(route_data, threshold_percent=15):
    """
    Check if traffic conditions have changed significantly since route was created
    
    Args:
        route_data: The original route data
        threshold_percent: Percentage change threshold to trigger update
        
    Returns:
        Dictionary with update status and new route data if needed
    """
    # If no timestamp or over 10 minutes old, always update
    if 'timestamp' not in route_data or time.time() - route_data.get('timestamp', 0) > 600:
        # Make sure we have coordinates to work with
        if 'coordinates' not in route_data:
            return {
                'needs_update': False,
                'reason': 'No coordinates available to check for updates'
            }
            
        new_route = get_route_details(route_data['coordinates'])
        return {
            'needs_update': True,
            'reason': 'Route information is outdated',
            'new_route': new_route
        }
    
    # Check each segment for traffic changes
    if 'route_details' in route_data and 'segments' in route_data['route_details']:
        segments = route_data['route_details']['segments']
        coordinates = [segment['geometry'][0] for segment in segments]
    else:
        # If we don't have detailed segment information, use the original coordinates
        if 'coordinates' not in route_data:
            return {
                'needs_update': False,
                'reason': 'No route details available to check for updates'
            }
        coordinates = route_data['coordinates']
        updated_route = get_route_details(coordinates)
        return {
            'needs_update': True,
            'reason': 'Route information needs to be refreshed',
            'new_route': updated_route
        }
    
    # Get current traffic conditions
    updated_route = get_route_details(coordinates)
    
    # Compare segment durations
    duration_changes = []
    max_change_percent = 0
    changed_segment_idx = -1
    
    for i, (old_segment, new_segment) in enumerate(zip(segments, updated_route['segments'])):
        if 'duration' not in old_segment or 'duration' not in new_segment:
            continue
            
        old_duration = old_segment['duration']
        new_duration = new_segment['duration']
        
        if old_duration == 0:
            continue
            
        change_percent = abs(new_duration - old_duration) / old_duration * 100
        
        duration_changes.append({
            'segment': i,
            'old_duration': old_duration,
            'new_duration': new_duration,
            'change_percent': change_percent,
            'increased': new_duration > old_duration
        })
        
        if change_percent > max_change_percent:
            max_change_percent = change_percent
            changed_segment_idx = i
    
    # Determine if an update is needed
    needs_update = max_change_percent >= threshold_percent
    
    if needs_update and changed_segment_idx >= 0:
        old_segment = segments[changed_segment_idx] 
        new_segment = updated_route['segments'][changed_segment_idx]
        
        # Get the location names for better context
        from_location = f"point {changed_segment_idx + 1}"
        to_location = f"point {changed_segment_idx + 2}"
        
        if changed_segment_idx < len(segments) - 1 and 'weather' in segments[changed_segment_idx + 1] and segments[changed_segment_idx + 1]['weather']:
            to_location = segments[changed_segment_idx + 1]['weather']['location_name']
        
        # Create reason message
        old_minutes = int(old_segment['duration'] / 60)
        new_minutes = int(new_segment['duration'] / 60)
        diff_minutes = new_minutes - old_minutes
        
        if diff_minutes > 0:
            reason = f"Traffic increased on the route to {to_location} (+{diff_minutes} min)"
        else:
            reason = f"Traffic decreased on the route to {to_location} ({diff_minutes} min)"
    else:
        reason = "No significant traffic changes"
    
    return {
        'needs_update': needs_update,
        'reason': reason,
        'max_change_percent': max_change_percent,
        'changed_segment': changed_segment_idx if needs_update else -1,
        'duration_changes': duration_changes,
        'new_route': updated_route if needs_update else None
    }
