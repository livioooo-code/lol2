// Initialize analytics charts and data
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize when analytics modal is shown
    document.getElementById('analyticsModal').addEventListener('shown.bs.modal', function () {
        loadAnalyticsData();
    });
});

function loadAnalyticsData() {
    fetch('/analytics/data')
        .then(response => response.json())
        .then(data => {
            updateAnalyticsDashboard(data);
        })
        .catch(error => {
            console.error('Error loading analytics data:', error);
            // Show error message
            document.getElementById('analytics-error').classList.remove('d-none');
        });
}

function updateAnalyticsDashboard(data) {
    // Update summary metrics
    document.getElementById('total-distance-value').textContent = `${data.total_distance} km`;
    document.getElementById('total-routes-value').textContent = data.total_routes;
    
    // Update charts
    updateRouteTimeChart(data.monthly_routes);
    updateCategoryDistributionChart(data.category_distribution);
}

function updateRouteTimeChart(monthlyData) {
    // Create labels and data arrays
    const labels = [];
    const values = [];
    
    // Get last 6 months
    const today = new Date();
    for (let i = 5; i >= 0; i--) {
        const month = new Date(today.getFullYear(), today.getMonth() - i, 1);
        const monthLabel = month.toLocaleString('default', { month: 'short', year: 'numeric' });
        const monthKey = month.toISOString().substring(0, 7); // YYYY-MM format
        
        labels.push(monthLabel);
        values.push(monthlyData[monthKey] || 0);
    }
    
    // Create or update chart
    const ctx = document.getElementById('routeStatsChart').getContext('2d');
    
    if (window.routeStatsChart) {
        window.routeStatsChart.data.labels = labels;
        window.routeStatsChart.data.datasets[0].data = values;
        window.routeStatsChart.update();
    } else {
        window.routeStatsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Number of Routes',
                    data: values,
                    borderColor: '#0d6efd',
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Routes Created Over Time',
                        color: '#f8f9fa'
                    },
                    legend: {
                        labels: {
                            color: '#f8f9fa'
                        }
                    }
                }
            }
        });
    }
}

function updateCategoryDistributionChart(categoryData) {
    // Format data for chart
    const categories = {
        'home': 'Home',
        'office': 'Office',
        'business': 'Business',
        'pickup_point': 'Pickup Point',
        'other': 'Other'
    };
    
    const colors = {
        'home': 'rgba(25, 135, 84, 0.7)',
        'office': 'rgba(13, 110, 253, 0.7)',
        'business': 'rgba(255, 193, 7, 0.7)',
        'pickup_point': 'rgba(111, 66, 193, 0.7)',
        'other': 'rgba(108, 117, 125, 0.7)'
    };
    
    const borderColors = {
        'home': 'rgb(25, 135, 84)',
        'office': 'rgb(13, 110, 253)',
        'business': 'rgb(255, 193, 7)',
        'pickup_point': 'rgb(111, 66, 193)',
        'other': 'rgb(108, 117, 125)'
    };
    
    const labels = [];
    const values = [];
    const backgroundColors = [];
    const borders = [];
    
    // Populate data arrays
    for (const category in categories) {
        labels.push(categories[category]);
        values.push(categoryData[category] || 0);
        backgroundColors.push(colors[category]);
        borders.push(borderColors[category]);
    }
    
    // Create or update chart
    const ctx = document.getElementById('categoryDistributionChart').getContext('2d');
    
    if (window.categoryChart) {
        window.categoryChart.data.labels = labels;
        window.categoryChart.data.datasets[0].data = values;
        window.categoryChart.update();
    } else {
        window.categoryChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: backgroundColors,
                    borderColor: borders,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Stop Categories Distribution',
                        color: '#f8f9fa'
                    },
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#f8f9fa'
                        }
                    }
                }
            }
        });
    }
}
