let map;
let markers = [];
let routePolylines = [];
let trafficUpdateTimer;
let lastTrafficUpdateTime = 0;

// Get current location before form submission
document.getElementById('route-form').addEventListener('submit', function(e) {
    e.preventDefault();
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                document.getElementById('current_lat').value = position.coords.latitude;
                document.getElementById('current_lon').value = position.coords.longitude;
                e.target.submit();
            },
            function(error) {
                console.error('Geolocation error:', error);
                // Submit form without location if geolocation fails
                e.target.submit();
            }
        );
    } else {
        // Submit form without location if geolocation not supported
        e.target.submit();
    }
});

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
                        let errorMsg = "Could not get your location. ";
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMsg += "Please enable location permissions in your browser settings.";
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMsg += "Location information is unavailable.";
                                break;
                            case error.TIMEOUT:
                                errorMsg += "Location request timed out.";
                                break;
                            default:
                                errorMsg += "An unknown error occurred.";
                        }
                        alert(errorMsg);
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
    // Check for traffic updates every 2 minutes
    trafficUpdateTimer = setInterval(checkTrafficUpdates, 120000);
    
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
    if ((now - lastTrafficUpdateTime) / 1000 < 120) { // Minimum 2 minutes between checks
        return;
    }
    
    // Add error handling for failed requests
    let retryCount = 0;
    const maxRetries = 3;
    
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

    // Add current location marker if available
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const currentLocation = [position.coords.latitude, position.coords.longitude];
            
            // Add special marker for current location
            L.marker(currentLocation, {
                icon: L.divIcon({
                    className: 'current-location-marker',
                    html: '<div class="start-point-marker"><i class="fas fa-location-arrow"></i><div class="start-label">Start</div></div>',
                    iconSize: [40, 40],
                    iconAnchor: [20, 40]
                })
            }).addTo(map);
        });
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
    if (routeData.route_details && routeData.route_details.segments) {
        // Draw each segment separately with its traffic color
        for (const segment of routeData.route_details.segments) {
            // Get route data for this segment
            const segmentPoints = segment.geometry.map(coord => [coord[1], coord[0]]);
            
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
    
    // Show the navigation button
    document.getElementById('start-navigation-btn').classList.remove('d-none');
    
    // Store route data in session storage for the navigation button
    sessionStorage.setItem('routeData', JSON.stringify(routeData));
}

function startNavigation() {
    // Get the route data first
    const routeData = JSON.parse(sessionStorage.getItem('routeData') || '{}');
    if (!routeData || !routeData.coordinates || routeData.coordinates.length === 0) {
        alert('Nie znaleziono ważnych danych trasy. Zoptymalizuj trasę ponownie.');
        return;
    }
    
    // Try to get user's current location, but continue with navigation even if it fails
    try {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                // Success callback
                position => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    const currentLocation = [lat, lon];
                    
                    // Get the first stop coordinates
                    const firstStop = [routeData.coordinates[0][1], routeData.coordinates[0][0]];
                    
                    // Open Google Maps with directions from current location
                    const googleMapsUrl = `https://www.google.com/maps/dir/?api=1&origin=${currentLocation.join(',')}&destination=${firstStop.join(',')}&travelmode=driving`;
                    window.open(googleMapsUrl, '_blank');
                },
                // Error callback
                error => {
                    console.error('Geolocation error:', error);
                    
                    // If we can't get current location, just navigate to the first point
                    const firstStop = [routeData.coordinates[0][1], routeData.coordinates[0][0]];
                    const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${firstStop.join(',')}`;
                    window.open(googleMapsUrl, '_blank');
                    
                    alert('Nie można uzyskać Twojej aktualnej lokalizacji. Nawigacja rozpocznie się od pierwszego punktu trasy.');
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,  // Increased timeout
                    maximumAge: 60000  // Allow cached position up to 1 minute old
                }
            );
        } else {
            // If geolocation is not supported, just navigate to the first point
            const firstStop = [routeData.coordinates[0][1], routeData.coordinates[0][0]];
            const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${firstStop.join(',')}`;
            window.open(googleMapsUrl, '_blank');
            
            alert('Twoja przeglądarka nie obsługuje geolokalizacji. Nawigacja rozpocznie się od pierwszego punktu trasy.');
        }
    } catch (e) {
        console.error('Navigation error:', e);
        alert('Wystąpił błąd podczas uruchamiania nawigacji. Spróbuj ponownie.');
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
    
    // Hide navigation button
    document.getElementById('start-navigation-btn').classList.add('d-none');
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
