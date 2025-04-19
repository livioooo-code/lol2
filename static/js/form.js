document.addEventListener('DOMContentLoaded', function() {
    const addLocationBtn = document.getElementById('add-location-btn');
    const locationsContainer = document.getElementById('locations-container');
    const locationCountInput = document.getElementById('location_count');
    
    let locationCount = 1; // Start with 1 for the initial location
    
    function addLocationEntry() {
        locationCount++;
        
        const newLocation = document.createElement('div');
        newLocation.className = 'location-entry mb-3';
        
        // Create the location content with mobile optimizations
        const isMobile = window.innerWidth <= 768;
        
        // Basic location fields
        let locationContent = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong>Location ${locationCount}</strong>
                <span class="badge bg-secondary">${locationCount}</span>
                <button type="button" class="btn btn-sm btn-outline-danger btn-remove-location">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="mb-2">
                <label for="city_${locationCount - 1}" class="form-label">City:</label>
                <input type="text" class="form-control" id="city_${locationCount - 1}" name="city_${locationCount - 1}" required>
            </div>
            <div class="mb-2">
                <label for="street_${locationCount - 1}" class="form-label">Street:</label>
                <input type="text" class="form-control" id="street_${locationCount - 1}" name="street_${locationCount - 1}" required>
            </div>
            <div class="mb-2">
                <label for="number_${locationCount - 1}" class="form-label">Building Number:</label>
                <input type="text" class="form-control" id="number_${locationCount - 1}" name="number_${locationCount - 1}" required>
            </div>`;
        
        // Add category and time window fields
        if (isMobile) {
            // On mobile, we'll add these fields in a collapsed section
            locationContent += `
                <div class="mt-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary w-100 advanced-toggle">
                        <i class="fas fa-cog me-1"></i> Advanced Options
                    </button>
                    <div class="collapse mt-2 advanced-options">
                        <div class="category-row mb-2">
                            <label for="category_${locationCount - 1}" class="form-label">Category:</label>
                            <select class="form-select" id="category_${locationCount - 1}" name="category_${locationCount - 1}">
                                <option value="home">Home</option>
                                <option value="office">Office</option>
                                <option value="business">Business</option>
                                <option value="pickup_point">Pickup Point</option>
                                <option value="other">Other</option>
                            </select>
                        </div>
                        <div class="time-window-row mb-2">
                            <div class="row">
                                <div class="col-6">
                                    <label for="time_window_start_${locationCount - 1}" class="form-label">From:</label>
                                    <input type="time" class="form-control" id="time_window_start_${locationCount - 1}" name="time_window_start_${locationCount - 1}">
                                </div>
                                <div class="col-6">
                                    <label for="time_window_end_${locationCount - 1}" class="form-label">To:</label>
                                    <input type="time" class="form-control" id="time_window_end_${locationCount - 1}" name="time_window_end_${locationCount - 1}">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>`;
        } else {
            // On desktop, show these fields directly
            locationContent += `
                <div class="category-row mb-2">
                    <label for="category_${locationCount - 1}" class="form-label">Category:</label>
                    <select class="form-select" id="category_${locationCount - 1}" name="category_${locationCount - 1}">
                        <option value="home">Home</option>
                        <option value="office">Office</option>
                        <option value="business">Business</option>
                        <option value="pickup_point">Pickup Point</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                <div class="time-window-row mb-2">
                    <div class="row">
                        <div class="col-6">
                            <label for="time_window_start_${locationCount - 1}" class="form-label">From:</label>
                            <input type="time" class="form-control" id="time_window_start_${locationCount - 1}" name="time_window_start_${locationCount - 1}">
                        </div>
                        <div class="col-6">
                            <label for="time_window_end_${locationCount - 1}" class="form-label">To:</label>
                            <input type="time" class="form-control" id="time_window_end_${locationCount - 1}" name="time_window_end_${locationCount - 1}">
                        </div>
                    </div>
                </div>`;
        }
        
        newLocation.innerHTML = locationContent;
        locationsContainer.appendChild(newLocation);
        locationCountInput.value = locationCount;
        
        // Add event listener to the remove button
        const removeBtn = newLocation.querySelector('.btn-remove-location');
        removeBtn.addEventListener('click', function() {
            removeLocation(newLocation);
        });
        
        // Add event listener to the advanced options toggle (for mobile)
        const advancedToggle = newLocation.querySelector('.advanced-toggle');
        if (advancedToggle) {
            advancedToggle.addEventListener('click', function() {
                const advancedOptions = newLocation.querySelector('.advanced-options');
                advancedOptions.classList.toggle('show');
                
                if (advancedOptions.classList.contains('show')) {
                    advancedToggle.innerHTML = '<i class="fas fa-chevron-up me-1"></i> Hide Advanced Options';
                } else {
                    advancedToggle.innerHTML = '<i class="fas fa-cog me-1"></i> Advanced Options';
                }
            });
        }
        
        // Add mobile swipe gesture support
        if (isMobile) {
            let touchStartX = 0;
            let touchEndX = 0;
            
            newLocation.addEventListener('touchstart', function(e) {
                touchStartX = e.changedTouches[0].screenX;
            }, false);
            
            newLocation.addEventListener('touchend', function(e) {
                touchEndX = e.changedTouches[0].screenX;
                const swipeThreshold = 100; // minimum distance for swipe
                
                if (touchStartX - touchEndX > swipeThreshold) {
                    // Swiped left - show delete button
                    const deleteBtn = document.createElement('div');
                    deleteBtn.className = 'swipe-delete-btn';
                    deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                    this.appendChild(deleteBtn);
                    
                    this.classList.add('swiped');
                    
                    deleteBtn.addEventListener('click', () => {
                        removeLocation(newLocation);
                    });
                    
                    // Reset after 3 seconds
                    setTimeout(() => {
                        this.classList.remove('swiped');
                        if (this.contains(deleteBtn)) {
                            this.removeChild(deleteBtn);
                        }
                    }, 3000);
                }
            }, false);
        }
    }
    
    function removeLocation(locationElement) {
        locationElement.remove();
        locationCount--;
        locationCountInput.value = locationCount;
        
        // Update the numbers of the remaining locations
        const locationEntries = locationsContainer.querySelectorAll('.location-entry');
        locationEntries.forEach((entry, index) => {
            if (index > 0) { // Skip the first one (starting point)
                const locationNumber = index + 1;
                entry.querySelector('strong').textContent = `Location ${locationNumber}`;
                entry.querySelector('.badge').textContent = locationNumber;
            }
        });
    }
    
    // Add event listener to the "Add Location" button
    addLocationBtn.addEventListener('click', addLocationEntry);
    
    // Add advanced options toggle to the first location (for mobile)
    const firstLocation = document.querySelector('.location-entry');
    if (firstLocation && window.innerWidth <= 768) {
        // Get the category and time window rows from the first location
        const categoryRow = firstLocation.querySelector('.category-row');
        const timeWindowRow = firstLocation.querySelector('.time-window-row');
        
        if (categoryRow && timeWindowRow) {
            // Remove the d-none class to make them visible but still collapsed
            categoryRow.classList.remove('d-none');
            timeWindowRow.classList.remove('d-none');
            
            // Create a container for advanced options
            const advancedOptionsContainer = document.createElement('div');
            advancedOptionsContainer.className = 'collapse mt-2 advanced-options';
            
            // Move the rows into the container
            advancedOptionsContainer.appendChild(categoryRow);
            advancedOptionsContainer.appendChild(timeWindowRow);
            
            // Create the toggle button
            const advancedToggle = document.createElement('button');
            advancedToggle.type = 'button';
            advancedToggle.className = 'btn btn-sm btn-outline-secondary w-100 advanced-toggle';
            advancedToggle.innerHTML = '<i class="fas fa-cog me-1"></i> Advanced Options';
            
            // Add the button and container to the first location
            firstLocation.appendChild(advancedToggle);
            firstLocation.appendChild(advancedOptionsContainer);
            
            // Add event listener to the toggle button
            advancedToggle.addEventListener('click', function() {
                advancedOptionsContainer.classList.toggle('show');
                
                if (advancedOptionsContainer.classList.contains('show')) {
                    advancedToggle.innerHTML = '<i class="fas fa-chevron-up me-1"></i> Hide Advanced Options';
                } else {
                    advancedToggle.innerHTML = '<i class="fas fa-cog me-1"></i> Advanced Options';
                }
            });
            
            // Add swipe gesture support to the first location
            let touchStartX = 0;
            let touchEndX = 0;
            
            firstLocation.addEventListener('touchstart', function(e) {
                touchStartX = e.changedTouches[0].screenX;
            }, false);
            
            firstLocation.addEventListener('touchend', function(e) {
                touchEndX = e.changedTouches[0].screenX;
                const swipeThreshold = 100; // minimum distance for swipe
                
                // We don't want to allow deleting the first location with swipe
                if (touchEndX - touchStartX > swipeThreshold) {
                    // Swiped right - show advanced options
                    advancedOptionsContainer.classList.add('show');
                    advancedToggle.innerHTML = '<i class="fas fa-chevron-up me-1"></i> Hide Advanced Options';
                }
            }, false);
        }
    }
});
