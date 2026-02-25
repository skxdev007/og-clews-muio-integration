/**
 * OG-Core Integration Controller (Simplified - No ES6 export)
 */

var OGCoreSimple = {
    Load: async function() {
        try {
            console.log('OGCore: Starting to load data...');
            
            // Fetch real OG-Core data from our API
            const response = await fetch('/og/real_data');
            console.log('OGCore: Response received', response.status);
            
            const data = await response.json();
            console.log('OGCore: Data parsed', data);
            
            if (data.status === 'success') {
                this.renderPage(data);
            } else {
                this.renderError(data.message || 'Failed to load OG-Core data');
            }
        } catch (error) {
            console.error('OGCore: Error loading data:', error);
            this.renderError('Failed to connect to OG-Core API: ' + error.message);
        }
    },
    
    renderPage: function(data) {
        console.log('OGCore: Rendering page with data');
        
        const html = `
            <div class="row">
                <div class="col-xs-12 col-sm-12 col-md-12 col-lg-12">
                    <h1 class="page-title txt-color-blueDark">
                        <i class="fa fa-line-chart fa-fw"></i> 
                        OG-Core Integration
                        <span>> Real Model Data</span>
                    </h1>
                </div>
            </div>
            
            <div class="row">
                <div class="col-sm-12">
                    <div class="well well-sm">
                        <h4><i class="fa fa-check-circle txt-color-green"></i> ${data.message}</h4>
                        <p><strong>Source:</strong> ${data.source}</p>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-sm-6 col-md-6 col-lg-3">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-calculator"></i> </span>
                            <h2>CLEWS Discount Rate</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <h1 class="txt-color-blueDark">${(data.clews_discount_rate * 100).toFixed(4)}%</h1>
                                <p>Average over 20 years</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-sm-6 col-md-6 col-lg-3">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-arrow-down txt-color-red"></i> </span>
                            <h2>Minimum Rate</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <h1 class="txt-color-red">${(data.statistics.min * 100).toFixed(4)}%</h1>
                                <p>Lowest interest rate</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-sm-6 col-md-6 col-lg-3">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-arrow-up txt-color-green"></i> </span>
                            <h2>Maximum Rate</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <h1 class="txt-color-green">${(data.statistics.max * 100).toFixed(4)}%</h1>
                                <p>Highest interest rate</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-sm-6 col-md-6 col-lg-3">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-bar-chart"></i> </span>
                            <h2>Std Deviation</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <h1 class="txt-color-blueDark">${(data.statistics.std * 100).toFixed(4)}%</h1>
                                <p>Volatility measure</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-sm-12">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-line-chart"></i> </span>
                            <h2>Interest Rates Over Time (First 30 Years)</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <div id="ogInterestRateChart" style="height: 400px;"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-sm-12">
                    <div class="jarviswidget" data-widget-colorbutton="false" data-widget-editbutton="false">
                        <header>
                            <span class="widget-icon"> <i class="fa fa-info-circle"></i> </span>
                            <h2>Economic Interpretation</h2>
                        </header>
                        <div>
                            <div class="widget-body">
                                <h4>What This Data Means for CLEWS</h4>
                                <p>The interest rates from OG-Core represent equilibrium capital market conditions. These rates are transformed into CLEWS's DiscountRate parameter, which affects energy investment decisions:</p>
                                <ul>
                                    <li><strong>Higher rates (${(data.statistics.max * 100).toFixed(2)}%)</strong> → Favor low-capital technologies (e.g., natural gas)</li>
                                    <li><strong>Lower rates (${(data.statistics.min * 100).toFixed(2)}%)</strong> → Favor high-capital investments (e.g., solar, wind)</li>
                                    <li><strong>Average rate (${(data.clews_discount_rate * 100).toFixed(2)}%)</strong> → Used as CLEWS DiscountRate parameter</li>
                                </ul>
                                <p><strong>Non-linear pattern:</strong> Notice the drop from ${(data.interest_rates[0] * 100).toFixed(2)}% to ${(data.interest_rates[7] * 100).toFixed(2)}% around year 7. This shows real transition dynamics, not mock data.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        $('#content').html(html);
        
        // Initialize widgets and create chart
        setTimeout(function() {
            OGCoreSimple.createChart(data);
        }, 100);
    },
    
    createChart: function(data) {
        console.log('OGCore: Creating chart');
        
        const years = data.interest_rates.map(function(_, i) { return i; });
        const rates = data.interest_rates.map(function(r) { return r * 100; });
        
        const trace = {
            x: years,
            y: rates,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Interest Rate',
            line: { color: '#3276B1', width: 2 },
            marker: { size: 6, color: '#3276B1' }
        };
        
        const avgLine = {
            x: [0, years.length - 1],
            y: [data.clews_discount_rate * 100, data.clews_discount_rate * 100],
            type: 'scatter',
            mode: 'lines',
            name: 'CLEWS Discount Rate (Avg)',
            line: { color: '#ED1C24', width: 2, dash: 'dash' }
        };
        
        const layout = {
            title: 'OG-Core Interest Rates (Real Data)',
            xaxis: { title: 'Year', showgrid: true },
            yaxis: { title: 'Interest Rate (%)', showgrid: true },
            hovermode: 'closest',
            showlegend: true
        };
        
        Plotly.newPlot('ogInterestRateChart', [trace, avgLine], layout, {responsive: true});
    },
    
    renderError: function(message) {
        console.log('OGCore: Rendering error:', message);
        
        const html = `
            <div class="row">
                <div class="col-xs-12">
                    <h1 class="page-title txt-color-blueDark">
                        <i class="fa fa-line-chart fa-fw"></i> 
                        OG-Core Integration
                    </h1>
                </div>
            </div>
            
            <div class="row">
                <div class="col-sm-12">
                    <div class="alert alert-danger">
                        <h4><i class="fa fa-exclamation-triangle"></i> Error</h4>
                        <p>${message}</p>
                        <p>Make sure the OG-Core API is running and real data has been extracted.</p>
                    </div>
                </div>
            </div>
        `;
        
        $('#content').html(html);
    }
};
