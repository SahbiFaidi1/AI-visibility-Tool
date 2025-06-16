from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    try:
        # Read the analysis results
        with open('results.json', 'r') as f:
            results = json.load(f)
        
        # Transform the data into the new format
        data = {
            'rankings': results.get('rankings', []),
            'prompts': results.get('prompts_responses', []),
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
        with open('results.json', 'r') as f:
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