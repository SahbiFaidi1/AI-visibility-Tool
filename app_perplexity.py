from flask import Flask, render_template, jsonify, request
from perplexity_client import process_prompts_file
import json
import os
from datetime import datetime
import csv

app = Flask(__name__)

# Store the last analysis results
last_analysis_results = {
    'brands': {},
    'prompts': [],
    'sources': [],
    'timestamp': None
}

@app.route('/')
def index():
    try:
        # Load data from existing files
        with open('brand_analysis_results.json', 'r') as f:
            results = json.load(f)
        
        # Transform brands data into rankings format
        rankings = []
        for brand, data in results.get('brands', {}).items():
            rankings.append({
                'manufacturer': brand,
                'percentage': data.get('visibility', 0),
                'logo_url': f"https://logo.clearbit.com/{brand.lower()}.com"
            })
        
        # Sort rankings by percentage in descending order
        rankings.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Load sources
        sources = []
        try:
            with open('sources.csv', 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                sources = list(reader)
                print(f"Loaded {len(sources)} sources from CSV")
        except FileNotFoundError:
            print("sources.csv not found")
        
        # Load prompts and responses
        prompts_responses = []
        try:
            with open('prompts_responses.json', 'r') as f:
                prompts_responses = json.load(f)
        except FileNotFoundError:
            print("prompts_responses.json not found")
        
        # Combine all data
        data = {
            'rankings': rankings,
            'prompts_responses': prompts_responses,
            'sources': sources,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Debug: Print the data structure
        print("Data being passed to template:")
        print(f"Number of sources: {len(sources)}")
        print(f"Sample source: {sources[0] if sources else 'No sources'}")
        
        return render_template('index.html', results=data)
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return render_template('index.html', results={
            'rankings': [],
            'prompts_responses': [],
            'sources': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # Process prompts and get brand analysis
        results = process_prompts_file()
        if not results:
            return jsonify({
                'success': False,
                'error': 'Failed to process prompts'
            })
        
        # Update last analysis results
        last_analysis_results['brands'] = results.get('brands', {})
        last_analysis_results['prompts'] = results.get('prompts', [])
        last_analysis_results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'success': True,
            'data': results,
            'timestamp': last_analysis_results['timestamp']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/get_results')
def get_results():
    try:
        # Load brand analysis results
        with open('brand_analysis_results.json', 'r') as f:
            results = json.load(f)
        
        print("\nDebug: brand_analysis_results.json contents:")
        print(f"Number of prompts: {len(results.get('prompts', []))}")
        if results.get('prompts'):
            print("Sample prompt structure:")
            print(json.dumps(results['prompts'][0], indent=2))
        
        # Transform brands data into rankings format
        rankings = []
        for brand, data in results.get('brands', {}).items():
            rankings.append({
                'manufacturer': brand,
                'percentage': data.get('visibility', 0),
                'logo_url': f"https://logo.clearbit.com/{brand.lower()}.com"
            })
        
        # Sort rankings by percentage in descending order
        rankings.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Get prompts with their sources
        prompts = results.get('prompts', [])
        
        # Combine all data
        data = {
            'rankings': rankings,
            'prompts': prompts,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print("\nDebug: Data being sent to frontend:")
        print(json.dumps(data, indent=2))
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        print(f"Error in get_results: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/get_source_usage')
def get_source_usage():
    try:
        with open('source_usage_data.json', 'r') as f:
            source_data = json.load(f)
        return jsonify(source_data)
    except Exception as e:
        print(f"Error in get_source_usage: {str(e)}")
        return jsonify({
            'error': str(e),
            'domains': [],
            'counts': []
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5003)  # Using port 5003 to avoid conflict with other versions 