from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime
import csv

app = Flask(__name__)

@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/dashboard')
def dashboard():
    try:
        # Read the analysis results
        with open('results_enhanced.json', 'r') as f:
            results = json.load(f)
        
        sources = []
        try:
            with open('sources.csv', 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                sources = list(reader)
                print(f"Loaded {len(sources)} sources from CSV")
        except FileNotFoundError:
            print("sources.csv not found")

        prompts_responses = []
        try:
            with open('prompts_responses.json', 'r') as f:
                prompts_responses = json.load(f)
        except FileNotFoundError:
            print("prompts_responses.json not found")

        # Transform the data into the new format
        data = {
            'rankings': results.get('rankings', []),
            'prompts_responses': prompts_responses,
            'sources': sources,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return render_template('index.html', results=data)
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return render_template('index.html', results={
            'rankings': [],
            'prompts': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

@app.route('/get_results')
def get_results():
    try:
        with open('results_enhanced.json', 'r') as f:
            results = json.load(f)
        
        # Transform the data into the new format
        data = {
            'rankings': results.get('rankings', []),
            'prompts': results.get('prompts_responses', []),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Using port 5000 for Mistral version 