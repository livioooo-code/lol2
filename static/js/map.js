let map;
let markers = [];
let routePolylines = [];
let trafficUpdateTimer;
let lastTrafficUpdateTime = 0;

function initMap() {
    // Initialize map
    map = L.map('map').setView([52.2297, 21.0122], 13); // Default view of Warsaw
    
    // Add the base tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Add geolocation functionality
    if (navigator.geolocation) {
        // Add a simple button for geolocation
        const locateControl = L.control({position: 'topright'});
        
        locateControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            div.innerHTML = '<a href="#" title="Show me where I am" role="button" aria-label="Show me where I am" class="leaflet-control-locate"><i class="fa fa-location-arrow" style="padding: 5px; display: block;"></i></a>';
            
            div.onclick = function() {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        
                        // Move map to user's location
                        map.setView([lat, lon], 15);
                        
                        // Add a marker
                        L.marker([lat, lon], {
                            icon: L.divIcon({
                                className: 'current-location-marker',
                                html: '<i class="fas fa-map-marker-alt"></i>',
                                iconSize: [25, 25],
                                iconAnchor: [12, 25]
                            })
                        }).addTo(map).bindPopup("You are here").openPopup();
                    },
                    function(error) {
                        console.error("Geolocation error:", error);
                        alert("Could not get your location. Please check your location permissions.");
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 5000,
                        maximumAge: 0
                    }
                );
                return false;
            };
            
            return div;
        };
        
        locateControl.addTo(map);
    }
    
    // Set up automatic traffic updates
    setupTrafficUpdates();
}

function setupTrafficUpdates() {
    // Check for traffic updates every 30 seconds
    trafficUpdateTimer = setInterval(checkTrafficUpdates, 30000);
    
    // Also attach event listener for page visibility
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // Page is visible again, check for traffic updates if it's been more than 2 minutes
            const timeSinceLastUpdate = (Date.now() - lastTrafficUpdateTime) / 1000;
            if (timeSinceLastUpdate > 120) { // 2 minutes
                checkTrafficUpdates();
            }
        }
    });
    
    // Initial check
    setTimeout(checkTrafficUpdates, 5000); // Check after 5 seconds initially
}

function checkTrafficUpdates() {
    // Don't check too frequently
    const now = Date.now();
    if ((now - lastTrafficUpdateTime) / 1000 < 30) { // Minimum 30 seconds between checks
        return;
    }
    
    lastTrafficUpdateTime = now;
    
    // Make AJAX request to get updated route information
    fetch('/get_route?check_traffic=true')
        .then(response => response.json())
        .then(data => {
            if (data && data.has_traffic_update) {
                // Show notification about traffic update
                showTrafficUpdateNotification(data.traffic_update_reason);
                
                // Update the displayed route with new traffic information
                displayRoute(data);
            }
        })
        .catch(error => console.error('Error checking for traffic updates:', error));
}

function showTrafficUpdateNotification(reason) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'alert alert-warning alert-dismissible fade show';
    notification.innerHTML = `
        <i class="fas fa-traffic-light me-2"></i>
        <strong>Traffic Update:</strong> ${reason}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to page
    document.querySelector('.container').prepend(notification);
    
    // Auto remove after 10 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 500);
    }, 10000);
    
    // Play a notification sound
    playNotificationSound();
}

function playNotificationSound() {
    // Create and play a simple notification sound
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioContext.currentTime); // A5
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.3);
    } catch (e) {
        console.log('Audio notification not supported');
    }
}

function displayRoute(routeData) {
    // Clear existing markers and polyline
    clearMap();
    
    if (!routeData || !routeData.coordinates || routeData.coordinates.length === 0) {
        console.error('No valid route data provided');
        return;
    }
    
    // Extract coordinates
    const coordinates = routeData.coordinates;
    
    // Create markers for each point
    coordinates.forEach((coord, index) => {
        // Skip the last point if it's the same as the first (return to start)
        if (index === coordinates.length - 1 && 
            coord[0] === coordinates[0][0] && 
            coord[1] === coordinates[0][1]) {
            return;
        }
        
        let markerIcon;
        let markerLabel = index === 0 ? 'Start' : `${index}`;
        
        // If we have location details, use them for better markers and popups
        if (routeData.location_details && routeData.location_details[index]) {
            const locationDetail = routeData.location_details[index];
            const category = locationDetail.category || 'home';
            markerIcon = getCategoryIcon(category);
            
            // Create popup content with estimated arrival time if available
            let popupContent = `
                <div class="location-popup">
                    <h6>${locationDetail.street} ${locationDetail.number}</h6>
                    <div>${locationDetail.city}</div>
                    <div class="location-category ${category}">${getCategoryName(category)}</div>
            `;
            
            // Add estimated arrival time if available
            if (locationDetail.estimated_arrival) {
                popupContent += `
                    <div class="mt-2">
                        <i class="fas fa-clock me-1"></i> Estimated arrival: <strong>${locationDetail.estimated_arrival}</strong>
                    </div>
                `;
            }
            
            // Add time window if available
            if (locationDetail.time_window_start && locationDetail.time_window_end) {
                popupContent += `
                    <div class="time-window">
                        <i class="fas fa-hourglass-half me-1"></i>
                        Window: ${locationDetail.time_window_start} - ${locationDetail.time_window_end}
                    </div>
                `;
            }
            
            popupContent += `</div>`;
            
            // Add a marker
            const marker = L.marker([coord[1], coord[0]], {
                icon: markerIcon,
                title: `Stop ${index}`
            }).addTo(map).bindPopup(popupContent);
            
            markers.push(marker);
        } else if (routeData.addresses && routeData.addresses[index]) {
            // Simplified version when we only have addresses
            const address = routeData.addresses[index];
            
            // Default icon
            markerIcon = L.divIcon({
                className: 'map-marker',
                html: markerLabel,
                iconSize: [30, 30],
                iconAnchor: [15, 15]
            });
            
            // Create popup content
            let popupContent = `
                <div class="location-popup">
                    <div>${address}</div>
                </div>
            `;
            
            // Add a marker
            const marker = L.marker([coord[1], coord[0]], {
                icon: markerIcon,
                title: `Stop ${index}`
            }).addTo(map).bindPopup(popupContent);
            
            markers.push(marker);
        } else {
            // Fallback when we don't have any additional information
            markerIcon = L.divIcon({
                className: 'map-marker',
                html: markerLabel,
                iconSize: [30, 30],
                iconAnchor: [15, 15]
            });
            
            const marker = L.marker([coord[1], coord[0]], {
                icon: markerIcon,
                title: `Stop ${index}`
            }).addTo(map);
            
            markers.push(marker);
        }
    });
    
    // Create polylines for the route segments with traffic colors if available
    // Sprawdzamy, czy mamy segmenty na głównym poziomie obiektu trasy (nowa struktura)
    let segments = routeData.segments;
    
    // Jeśli nie, sprawdzamy czy są w route_details (stara struktura)
    if (!segments && routeData.route_details && routeData.route_details.segments) {
        segments = routeData.route_details.segments;
    }
    
    // Dodajmy więcej informacji o segmentach
    console.log("Wszystkie dane trasy:", routeData);
    
    // Jeśli znaleziono segmenty, rysujemy je z kolorami zależnymi od ruchu
    if (segments && segments.length > 0) {
        console.log("Rysowanie segmentów z kolorami ruchu:", segments);
        
        // Draw each segment separately with its traffic color
        for (const segment of segments) {
            // Get route data for this segment
            let segmentPoints = [];
            
            if (segment.geometry && Array.isArray(segment.geometry)) {
                console.log(`Segment [${segment.start_idx}-${segment.end_idx}] geometria:`, segment.geometry);
                
                // Sprawdzamy, czy mamy pełną geometrię (wszystkie punkty pośrednie)
                if (segment.geometry.length > 2) {
                    console.log(`Segment ma ${segment.geometry.length} punktów geometrycznych - rysujemy precyzyjną trasę`, segment.geometry);
                    // Konwertujemy wszystkie punkty z [lon, lat] na [lat, lon]
                    segmentPoints = segment.geometry.map(coord => {
                        console.log("Przetwarzanie punktu geometrii:", coord);
                        return [coord[1], coord[0]];
                    });
                    console.log("Punkty po konwersji:", segmentPoints);
                } else {
                    console.log("Segment ma tylko początki i koniec - linia prosta");
                    // Tylko punkty początkowy i końcowy - linia prosta
                    segmentPoints = segment.geometry.map(coord => [coord[1], coord[0]]);
                }
            } else {
                console.error("Brak danych geometrycznych dla segmentu");
                return;
            }
            
            // Determine color based on traffic level
            let segmentColor = '#0d6efd'; // Default blue
            let weight = 5;
            
            if (segment.traffic_color) {
                switch (segment.traffic_color) {
                    case 'green':
                        segmentColor = '#198754'; // Free flowing
                        break;
                    case 'yellow':
                        segmentColor = '#ffc107'; // Light traffic
                        break;
                    case 'orange':
                        segmentColor = '#fd7e14'; // Moderate traffic
                        break;
                    case 'red':
                        segmentColor = '#dc3545'; // Heavy traffic
                        weight = 6; // Make red segments thicker
                        break;
                }
            }
            
            // Create polyline for this segment
            const segmentPolyline = L.polyline(segmentPoints, {
                color: segmentColor,
                weight: weight,
                opacity: 0.8
            }).addTo(map);
            
            // Add popup with traffic information
            if (segment.traffic_level !== undefined) {
                let trafficStatus = 'Unknown';
                let delayText = '';
                
                // Determine traffic status text
                switch (segment.traffic_level) {
                    case 0:
                        trafficStatus = 'Free flowing traffic';
                        break;
                    case 1:
                        trafficStatus = 'Light traffic';
                        break;
                    case 2:
                        trafficStatus = 'Moderate traffic';
                        break;
                    case 3:
                        trafficStatus = 'Heavy traffic';
                        break;
                }
                
                // Add delay information if there is any
                if (segment.traffic_delay > 0) {
                    const delayMinutes = Math.round(segment.traffic_delay / 60);
                    delayText = `<div class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>+${delayMinutes} min delay</div>`;
                }
                
                segmentPolyline.bindPopup(`
                    <div>
                        <strong>${trafficStatus}</strong>
                        ${delayText}
                    </div>
                `);
            }
            
            routePolylines.push(segmentPolyline);
        }
    } else {
        // Fallback to simple route drawing if no segments with traffic info
        const routePoints = coordinates.map(coord => [coord[1], coord[0]]);
        const routePolyline = L.polyline(routePoints, {
            color: '#0d6efd',
            weight: 5,
            opacity: 0.7
        }).addTo(map);
        
        routePolylines.push(routePolyline);
    }
    
    // Fit the map bounds to show all markers
    if (routePolylines.length > 0) {
        // Create a feature group with all polylines
        const featureGroup = L.featureGroup(routePolylines);
        map.fitBounds(featureGroup.getBounds(), {
            padding: [50, 50]
        });
    }
    
    // Show route summary
    updateRouteSummary(routeData);
    
    // Show the navigation button and export options
    document.getElementById('start-navigation-btn').classList.remove('d-none');
    document.getElementById('export-options').classList.remove('d-none');
    
    // Store route data in session storage for the navigation button
    sessionStorage.setItem('routeData', JSON.stringify(routeData));
}

function startNavigation() {
    // Get user's current location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(position => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const currentLocation = [lat, lon];
            
            // Get the first stop coordinates (assuming it's routeData.coordinates[0])
            // But first convert the coordinates to [lat, lon] format from [lon, lat]
            const routeData = JSON.parse(sessionStorage.getItem('routeData') || '{}');
            if (!routeData || !routeData.coordinates || routeData.coordinates.length === 0) {
                console.error('No valid route data found');
                return;
            }
            
            const firstStop = [routeData.coordinates[0][1], routeData.coordinates[0][0]];
            
            // Open Google Maps with directions
            const googleMapsUrl = `https://www.google.com/maps/dir/?api=1&origin=${currentLocation.join(',')}&destination=${firstStop.join(',')}&travelmode=driving`;
            window.open(googleMapsUrl, '_blank');
        }, error => {
            console.error('Geolocation error:', error);
            alert('Could not get your current location. Please enable location services and try again.');
        }, {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        });
    } else {
        alert('Geolocation is not supported by your browser.');
    }
}

function clearMap() {
    // Remove existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    // Remove existing polylines
    routePolylines.forEach(polyline => map.removeLayer(polyline));
    routePolylines = [];
    
    // Hide route summary
    document.getElementById('route-summary').classList.add('d-none');
    
    // Hide navigation button and export options
    document.getElementById('start-navigation-btn').classList.add('d-none');
    document.getElementById('export-options').classList.add('d-none');
}

function updateRouteSummary(routeData) {
    const summaryElement = document.getElementById('route-summary');
    if (!summaryElement) return;
    
    if (!routeData) {
        summaryElement.classList.add('d-none');
        return;
    }
    
    // Prepare traffic delay information if available
    let trafficDelayHtml = '';
    if (routeData.traffic_delay_text && routeData.has_traffic_data) {
        const delayClass = routeData.traffic_delay_text.includes("No delays") ? "text-success" : "text-danger";
        trafficDelayHtml = `
            <div class="mt-2 ${delayClass}">
                <i class="fas fa-car me-1"></i> ${routeData.traffic_delay_text}
            </div>
        `;
    }
    
    // Create traffic status indicator
    let trafficStatusHtml = '';
    if (routeData.traffic_conditions && routeData.traffic_conditions.length > 0) {
        // Count traffic levels
        const trafficCounts = {0: 0, 1: 0, 2: 0, 3: 0};
        let totalSegments = 0;
        
        routeData.traffic_conditions.forEach(condition => {
            if (condition.level !== undefined) {
                trafficCounts[condition.level]++;
                totalSegments++;
            }
        });
        
        // Create traffic status badges
        trafficStatusHtml = '<div class="d-flex gap-2 mt-2">';
        
        if (trafficCounts[0] > 0) {
            const percent = Math.round((trafficCounts[0] / totalSegments) * 100);
            trafficStatusHtml += `<span class="badge bg-success">${percent}% Free flowing</span>`;
        }
        
        if (trafficCounts[1] > 0) {
            const percent = Math.round((trafficCounts[1] / totalSegments) * 100);
            trafficStatusHtml += `<span class="badge bg-warning text-dark">${percent}% Light traffic</span>`;
        }
        
        if (trafficCounts[2] > 0) {
            const percent = Math.round((trafficCounts[2] / totalSegments) * 100);
            trafficStatusHtml += `<span class="badge" style="background-color: #fd7e14;">${percent}% Moderate</span>`;
        }
        
        if (trafficCounts[3] > 0) {
            const percent = Math.round((trafficCounts[3] / totalSegments) * 100);
            trafficStatusHtml += `<span class="badge bg-danger">${percent}% Heavy traffic</span>`;
        }
        
        trafficStatusHtml += '</div>';
    }
    
    // Create summary content
    let content = `
        <div class="card mb-4">
            <div class="card-header bg-success text-white">
                <h5 class="mb-0"><i class="fas fa-route me-2"></i>Optimized Route</h5>
            </div>
            <div class="card-body">
                <div class="row mb-3">
                    <div class="col-6">
                        <div class="d-flex align-items-center">
                            <div class="fs-1 me-2 text-primary">
                                <i class="fas fa-road"></i>
                            </div>
                            <div>
                                <div class="fs-4">${routeData.total_distance} km</div>
                                <div class="text-muted">Total Distance</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="d-flex align-items-center">
                            <div class="fs-1 me-2 text-info">
                                <i class="fas fa-clock"></i>
                            </div>
                            <div>
                                <div class="fs-4">${routeData.total_time}</div>
                                <div class="text-muted">Estimated Time</div>
                                ${trafficDelayHtml}
                            </div>
                        </div>
                    </div>
                </div>
                
                ${trafficStatusHtml}
                
                <h6 class="mt-3"><i class="fas fa-list-ol me-2"></i>Route Order:</h6>
                <ol class="list-group list-group-numbered">
    `;
    
    // Add each stop to the list
    const addresses = routeData.addresses || [];
    addresses.forEach((address, index) => {
        // Skip the last point if it's returning to start
        if (index === addresses.length - 1 && 
            index > 0 && 
            address === addresses[0]) {
            return;
        }
        
        // Check if we have detailed location information
        let category = 'home';
        let badge = '';
        let estimatedArrival = '';
        
        if (routeData.location_details && routeData.location_details[index]) {
            const locationDetail = routeData.location_details[index];
            category = locationDetail.category || 'home';
            
            // Add time window if available
            const timeStart = locationDetail.time_window_start;
            const timeEnd = locationDetail.time_window_end;
            
            if (timeStart && timeEnd) {
                badge = `<span class="badge bg-secondary ms-2">
                    <i class="far fa-clock me-1"></i>${timeStart} - ${timeEnd}
                </span>`;
            }
            
            // Add estimated arrival if available
            if (locationDetail.estimated_arrival) {
                estimatedArrival = `
                    <div class="small text-info mt-1">
                        <i class="fas fa-clock me-1"></i>ETA: ${locationDetail.estimated_arrival}
                    </div>
                `;
            }
        }
        
        // Add to list
        content += `
            <li class="list-group-item d-flex justify-content-between align-items-start">
                <div class="ms-2 me-auto">
                    <div>
                        <span class="location-category ${category}">${getCategoryName(category)}</span>
                        ${badge}
                    </div>
                    <div class="text-muted">${address}</div>
                    ${estimatedArrival}
                </div>
            </li>
        `;
    });
    
    content += `
                </ol>
                
                <div class="mt-3 d-flex justify-content-end">
                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="checkTrafficUpdates()">
                        <i class="fas fa-sync-alt me-1"></i>Check for Traffic Updates
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Update the summary element
    summaryElement.innerHTML = content;
    summaryElement.classList.remove('d-none');
    
    // Show save route form
    document.getElementById('save-route-form').classList.remove('d-none');
}

function getCategoryIcon(category) {
    let iconClass;
    let colorClass;
    
    switch (category) {
        case 'home':
            iconClass = 'fa-home';
            colorClass = 'home';
            break;
        case 'office':
            iconClass = 'fa-building';
            colorClass = 'office';
            break;
        case 'business':
            iconClass = 'fa-briefcase';
            colorClass = 'business';
            break;
        case 'pickup_point':
            iconClass = 'fa-box';
            colorClass = 'pickup_point';
            break;
        default:
            iconClass = 'fa-map-marker-alt';
            colorClass = 'other';
    }
    
    return L.divIcon({
        className: `map-marker ${colorClass}`,
        html: `<i class="fas ${iconClass}"></i>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
}

function getCategoryName(category) {
    switch (category) {
        case 'home':
            return 'Home';
        case 'office':
            return 'Office';
        case 'business':
            return 'Business';
        case 'pickup_point':
            return 'Pickup Point';
        default:
            return 'Other';
    }
}
