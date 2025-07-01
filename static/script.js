let visibilityChart = null;
let brandYearChart = null;
let selectedBrands = new Set(chartData.slice(0, 10).map(brand => brand.manufacturer));

var observedBrand = null;

function updateChart() {
    const filteredData = chartData.filter(item => selectedBrands.has(item.manufacturer));
    
    // Prepare data for the chart
    const labels = filteredData.map(r => r.manufacturer);
    const data = filteredData.map(r => r.percentage);
    
    const config = {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Brand Visibility',
                data: data,
                backgroundColor: '#6b47ff',
                borderColor: 'rgb(82, 146, 255)',
                borderWidth: 0,
                borderRadius: {
                    topLeft: 4,
                    topRight: 4,
                    bottomLeft: 0,
                    bottomRight: 0
                },
                barThickness: 65,
                categoryPercentage: 1.0,
                barPercentage: 0.98
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'x',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.raw}%`;
                        }
                    },
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 4
                }
            },
            onClick: function(evt, elements) {
                if (elements.length > 0) {
                    const chart = elements[0].element.$context.chart;
                    const index = elements[0].index;
                    const brand = chart.data.labels[index];
                    setObservedBrand(brand);
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 35,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        },
                        stepSize: 5,
                        font: {
                            size: 11
                        }
                    },
                    grid: {
                        display: true,
                        color: '#f0f0f0',
                        drawBorder: false
                    },
                    border: {
                        display: false
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        font: {
                            size: 13,
                            weight: '500'
                        }
                    },
                    border: {
                        display: false
                    }
                }
            },
            layout: {
                padding: {
                    left: 0,
                    right: 20,
                    top: 20,
                    bottom: 0
                }
            }
        }
    };

    if (visibilityChart) {
        visibilityChart.destroy();
    }
    visibilityChart = new Chart(document.getElementById('visibilityChart'), config);
}

function setObservedBrand(brand) {
    observedBrand = brand;
    const isBrandSelected = brand != null
    const brandYearContent = document.getElementById('brand-year-content');
    const visibilityContent = document.getElementById('visibility-content');

    brandYearContent.style.display = isBrandSelected ? 'block' : 'none';
    visibilityContent.style.display = isBrandSelected ? 'none' : 'block';

    if (isBrandSelected) {
        fillBrandSummaryInfo();
        updateBrandYearChart();
    } else {
        updateChart();
    }

    // set the background color of the brand row to purple and content color to white
    const brandRows = document.querySelectorAll('.clickable-brand-row');
    brandRows.forEach(row => {
        if (row.dataset.brand === observedBrand) {
            row.style.backgroundColor = '#4d36cc';
            row.style.color = '#fff';
        } else {
            row.style.backgroundColor = '';
            row.style.color = '';
        }
    });
}

function fillBrandSummaryInfo() {
    const brandData = chartData.find(item => item.manufacturer === observedBrand);
    if (!brandData) {
        console.error('Brand data not found for', observedBrand);
        return;
    }

    const months = getPast12Months();
    const brandYearScores = brandData.past_year_scores || [];
    const highest = Math.max(...brandYearScores);
    const lowest = Math.min(...brandYearScores);
    const highestMonth = months[brandYearScores.indexOf(highest)];
    const lowestMonth = months[brandYearScores.indexOf(lowest)];
    const highestText = highestMonth ? `${highestMonth} (${highest}%)` : 'No data available';
    const lowestText = lowestMonth ? `${lowestMonth} (${lowest}%)` : 'No data available';

    document.getElementById('brandYearName').textContent = brandData.manufacturer;
    document.getElementById('brandYearLogo').src = brandData.logo_url || `https://logo.clearbit.com/${brandData.manufacturer.toLowerCase()}.com`;
    document.getElementById('brandSummaryHighest').textContent = highestText;
    document.getElementById('brandSummaryLowest').textContent = lowestText;
    document.getElementById('brandSummaryCurrent').textContent = `${brandData.percentage}%`;
    const trendIcon = document.getElementById('brandSummaryTrendIcon');
    trendIcon.classList.remove('fa-arrow-up', 'fa-arrow-down', 'fa-minus', 'text-success', 'text-danger', 'text-secondary');
    if (brandData.recent_trend === 'increase') {
        trendIcon.classList.add('fa-arrow-up', 'text-success');
        document.getElementById('brandSummaryTrend').textContent = 'Increasing'; 
    } else if (brandData.recent_trend === 'decrease') {
        trendIcon.classList.add('fa-arrow-down', 'text-danger');
        document.getElementById('brandSummaryTrend').textContent = 'Decreasing';
    } else {
        trendIcon.classList.add('fa-minus', 'text-secondary');
        document.getElementById('brandSummaryTrend').textContent = 'No change';
    }
}

function updateBrandYearChart() {
    const brandData = chartData.find(item => item.manufacturer === observedBrand);
    if (!brandData || !Array.isArray(brandData.past_year_scores)) {
        console.error('No past year scores for', observedBrand);
        return;
    }
    // Prepare data for the line chart
    const months = getPast12Months();
    
    const scores = brandData.past_year_scores.slice(0, 12);

    const yMax = Math.max(...scores) + 3;
    const yMin = Math.max(Math.min(...scores) - 3, 0);

    const conf = {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: `${observedBrand} Visibility (%)`,
                data: scores,
                fill: false,
                borderColor: '#6b47ff',
                backgroundColor: '#6b47ff',
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#fff',
                pointBorderColor: '#6b47ff',
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.raw}% visibility`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    min: yMin,
                    max: yMax,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        },
                        stepSize: 2,
                        font: { size: 11 }
                    },
                    grid: { color: '#f0f0f0', drawBorder: false }
                },
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: { font: { size: 13, weight: '700' } }
                }
            }
        }
    }
    
    if (brandYearChart) {
        brandYearChart.destroy();
    }
    brandYearChart = new Chart(document.getElementById('brandYearChart'), conf);
}

function getPast12Months() {
    const months = [];
    const now = new Date();
    for (let i = 11; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        months.push(`${d.toLocaleString('default', { month: 'short' })} '${String(d.getFullYear()).slice(-2)}`);
    }
    return months;
}

// Initialize brand checklist
function initializeBrandChecklist() {
    const checklist = document.getElementById('brandChecklist');
    checklist.innerHTML = '';
    
    chartData.forEach(item => {
        const div = document.createElement('div');
        div.className = 'checklist-item';
        div.innerHTML = `
            <input type="checkbox" id="brand_${item.manufacturer}" 
                    value="${item.manufacturer}" 
                    ${selectedBrands.has(item.manufacturer) ? 'checked' : ''}>
            <label for="brand_${item.manufacturer}">
                ${item.manufacturer}
            </label>
        `;
        checklist.appendChild(div);

        // Add event listener directly here
        const checkbox = div.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                selectedBrands.add(this.value);
            } else {
                selectedBrands.delete(this.value);
            }
            updateChart();
        });
    });
}

// Toggle dropdown
document.getElementById('brandFilter').addEventListener('click', function(e) {
    const checklist = document.getElementById('brandChecklist');
    checklist.classList.toggle('show');
    e.stopPropagation();
});

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    const checklist = document.getElementById('brandChecklist');
    if (!e.target.closest('#brandFilter')) {
        checklist.classList.remove('show');
    }
});

// Toggle model dropdown
document.getElementById('modelFilter').addEventListener('click', function(e) {
    const checklist = document.getElementById('modelChecklist');
    checklist.classList.toggle('show');
    e.stopPropagation();
});

// Close all dropdowns when clicking outside
document.addEventListener('click', function(e) {
    const brandChecklist = document.getElementById('brandChecklist');
    const modelChecklist = document.getElementById('modelChecklist');
    if (!e.target.closest('#brandFilter')) {
        brandChecklist.classList.remove('show');
    }
    if (!e.target.closest('#modelFilter')) {
        modelChecklist.classList.remove('show');
    }
});

// Initialize the chart and checklist when the page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeBrandChecklist();
    updateChart();
    setObservedBrand(null); // Set initial state with no brand selected
    createSourceBubbles();
});

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
});

// Add animation for chevron rotation
document.addEventListener('DOMContentLoaded', function() {
    const promptRows = document.querySelectorAll('.prompt-row');
    promptRows.forEach(row => {
        row.addEventListener('click', function() {
            const icon = this.querySelector('.fa-chevron-down');
            icon.style.transform = this.getAttribute('aria-expanded') === 'true' 
                ? 'rotate(180deg)' 
                : 'rotate(0deg)';
            // If aria-expanded set the background color of the row to purple and content color to white
            if (this.getAttribute('aria-expanded') === 'true') {
                this.style.backgroundColor = '#4d36cc';
                this.style.color = '#fff';
            } else {
                this.style.backgroundColor = '';
                this.style.color = '';
            }
        });
    });
});



function updateSourceUsageChart() {
    try {
        // Get the source data from the template variable
        const sourceData = dataSources;
        
        // Check if we have valid data
        if (!sourceData || !Array.isArray(sourceData)) {
            console.error('Invalid source data format:', sourceData);
            return;
        }

        // Process the sources data to get domain counts
        const domainCounts = {};
        sourceData.forEach(source => {
            const domain = source.domain;
            if (domain) {
                domainCounts[domain] = (domainCounts[domain] || 0) + 1;
            }
        });

        // Sort domains by count in descending order
        const sortedDomains = Object.entries(domainCounts)
            .sort((a, b) => b[1] - a[1]);

        // Update the sources table
        const tableBody = document.getElementById('sourcesTableBody');
        const modalTableBody = document.getElementById('modalSourcesTableBody');
        
        if (tableBody && modalTableBody) {
            tableBody.innerHTML = '';
            modalTableBody.innerHTML = '';
            
            sortedDomains.forEach(([domain, count], index) => {
                const row = document.createElement('div');
                row.className = 'table-row';
                row.innerHTML = `
                    <div class="cell rank-cell">${index + 1}</div>
                    <div class="cell">
                        <a href="https://${domain}" target="_blank">${domain}</a>
                    </div>
                    <div class="cell text-center">${count}</div>
                `;
                
                // Add to main table (show only first 5)
                if (index < 5) {
                    tableBody.appendChild(row.cloneNode(true));
                }
                
                // Add to modal table (show all)
                modalTableBody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error updating source usage table:', error);
    }
}

// Initialize the source usage table when the page loads
document.addEventListener('DOMContentLoaded', function() {
    updateSourceUsageChart();
});

function createSourceBubbles() {
    const counts = {};
    const domains = dataSources.map(source => {
        const parts = source.domain.split('.');
        return parts[0].includes('www') ? parts[1] : parts[0];
    });
    console.log('domains:', dataSources);
    
    domains.forEach(domain => {
        counts[domain] = (counts[domain] || 0) + 1;
    });
    const total = domains.length;

    const bubbleData = Object.entries(counts).map(([domain, count]) => ({
        domain,
        percentage: Math.round((count / total) * 100)
    }));

    const top4 = bubbleData
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 8);

    function randomColor() {
        const hue = Math.floor(Math.random() * 360);
        return `hsla(${hue}, 70%, 80%, 0.6)`; // light pastel
    }

    const ctx = document.getElementById('bubbleChart').getContext('2d');
    const canvas = document.getElementById('bubbleChart');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    const scaleFactor = Math.min(width, height) / 24; 
    const bubbleLabelPlugin = {
    id: 'bubbleLabelPlugin',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;

        chart.data.datasets.forEach((dataset, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        const point = meta.data[0]; // since each dataset has one bubble

        if (!point) return;

        const { x, y } = point.getCenterPoint(); // safe, supported method

        ctx.save();
        ctx.fillStyle = '#000';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const domain = dataset.label;
        const percentage = `${dataset.data[0].r.toFixed(0)}%`;

        ctx.fillText(domain, x, y - 8);
        ctx.fillText(percentage, x, y + 8);

        ctx.restore();
        });
    }
    };

    const positions = [
    { x: 50, y: 10 },
    { x: 20, y: 20 },
    { x: 80, y: 20 },
    { x: 10, y: 50 },
    { x: 90, y: 50 },
    { x: 20, y: 80 },
    { x: 80, y: 80 },
    { x: 50, y: 90 }
    ];
    const chart = new Chart(ctx, {
    type: 'bubble',
    data: {
        datasets: top4.map((item, index) => ({
        label: item.domain,
        data: [{ ...positions[index], r: item.percentage * scaleFactor }],
        backgroundColor: randomColor(),
        borderColor: 'rgba(0,0,0,0.1)',
        borderWidth: 1
        }))
    },
    options: {
        scales: {
        x: { display: false },
        y: { display: false }
        },
        plugins: {
        legend: { display: false },
        tooltip: {
            callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.raw.r}%`
            }
        }
        }
    },
    plugins: [bubbleLabelPlugin]
    });
}

document.querySelectorAll('.clickable-brand-row').forEach(row => {
    row.addEventListener('click', () => {
        const brand = row.dataset.brand;
        if (brand === observedBrand) {
            setObservedBrand(null); // Deselect if already selected
        } else {
            setObservedBrand(brand);
        }
    });
});