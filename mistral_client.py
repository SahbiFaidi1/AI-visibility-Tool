import os
import time
import json
from mistralai.client import MistralClient
from collections import Counter
import re
import signal
import concurrent.futures
from typing import List, Dict
import requests
from urllib.parse import quote

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Analysis took too long")

def initialize_client():
    """Initialize the Mistral AI client"""
    try:
        api_key = "LyOZOnyciBFsEiMlgxFSgmDPohaYZ5yq"
        client = MistralClient(api_key=api_key)
        # Test the connection with a simple message
        response = client.chat(
            model="mistral-small",
            messages=[{"role": "user", "content": "test"}]
        )
        return client
    except Exception as e:
        print(f"\nError initializing Mistral client: {str(e)}")
        print("Please check your API key and internet connection.")
        raise

def generate_response(client: MistralClient, prompt: str) -> str:
    """Generate a response using the Mistral AI API"""
    try:
        print(f"\nProcessing prompt: {prompt}")
        start_time = time.time()
        
        messages = [{"role": "user", "content": prompt}]
        
        response = client.chat(
            model="mistral-small",
            messages=messages,
            temperature=0.1,
            max_tokens=512
        )
        
        end_time = time.time()
        print(f"Response generated in {end_time - start_time:.2f} seconds")
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error processing prompt '{prompt}': {str(e)}")
        return ""

def process_prompts_batch(client: MistralClient, prompts: List[str]) -> List[str]:
    """Process a batch of prompts in parallel"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(generate_response, client, prompt) for prompt in prompts]
        return [future.result() for future in concurrent.futures.as_completed(futures)]

def verify_brands(client: MistralClient, potential_brands: Dict[str, int]) -> Dict[str, int]:
    """Verify if detected brands are real companies"""
    print("\nVerifying detected brands...")
    verified_brands = {}
    
    # Increased batch size for verification
    batch_size = 20
    brand_batches = [list(potential_brands.keys())[i:i + batch_size] 
                    for i in range(0, len(potential_brands), batch_size)]
    
    for batch in brand_batches:
        # Create a single prompt for the batch
        brands_list = ", ".join(batch)
        verification_prompt = f"""
        Which of these are real companies or brands? 
        List only the real brands/companies from this list: {brands_list}
        Respond with only the brand names, separated by commas.
        """
        
        try:
            response = client.chat(
                model="mistral-small",
                messages=[{"role": "user", "content": verification_prompt}],
                temperature=0.1
            )
            verified_list = [brand.strip() for brand in response.choices[0].message.content.split(',')]
            
            for brand in batch:
                if brand in verified_list:
                    verified_brands[brand] = potential_brands[brand]
                    print(f"✓ {brand} verified as a real brand")
                else:
                    print(f"✗ {brand} is not a verified brand")
        except Exception as e:
            print(f"Error verifying batch: {str(e)}")
            continue
    
    return verified_brands

def fetch_brand_logo(brand_name: str) -> str:
    """Fetch brand logo URL using Clearbit's Logo API"""
    try:
        # Clean the brand name for URL
        clean_name = brand_name.lower().replace(' ', '-').replace('&', 'and')
        
        # Construct the Clearbit logo URL
        logo_url = f"https://logo.clearbit.com/{clean_name}.com"
        
        # Verify if the logo exists by making a HEAD request
        response = requests.head(logo_url)
        if response.status_code == 200:
            return logo_url
        
        # If the .com domain doesn't work, try common TLDs
        tlds = ['.org', '.net', '.io', '.co', '.ai']
        for tld in tlds:
            logo_url = f"https://logo.clearbit.com/{clean_name}{tld}"
            response = requests.head(logo_url)
            if response.status_code == 200:
                return logo_url
        
        # If no logo found, return empty string
        return ""
    except Exception as e:
        print(f"Error fetching logo for {brand_name}: {str(e)}")
        return ""

def analyze_responses(client: MistralClient, all_responses: List[str], prompts: List[str]) -> None:
    """Send all responses to Mistral for brand analysis with weighted prominence"""
    try:
        print("\nCombining responses for analysis...")
        
        # Initialize brand prominence tracking
        brand_prominence = {}
        
        # Define weight categories for different types of prompts
        prompt_weights = {
            'top': 2.0,      # Prompts about top/best brands
            'popular': 1.8,  # Prompts about popularity
            'premium': 1.5,  # Prompts about premium/luxury
            'default': 1.0   # Default weight
        }
        
        # Process each response individually to maintain context
        for prompt, response in zip(prompts, all_responses):
            prompt_lower = prompt.lower()
            
            # Determine prompt weight based on context
            weight = prompt_weights['default']
            if any(word in prompt_lower for word in ['top', 'best']):
                weight = prompt_weights['top']
            elif any(word in prompt_lower for word in ['popular', 'common']):
                weight = prompt_weights['popular']
            elif any(word in prompt_lower for word in ['premium', 'luxury']):
                weight = prompt_weights['premium']
            
            # Patterns to identify brands with position context
            patterns = [
                r'(?:brand|company|manufacturer)\s+([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)',
                r'\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\s+(?:is|offers|provides|has|manufactures|produces|sells)',
                r'\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\'s\s+(?:products|services|offerings)'
            ]
            
            # Track position of mentions in the response
            response_lines = response.split('\n')
            for line_num, line in enumerate(response_lines):
                for pattern in patterns:
                    matches = re.finditer(pattern, line, re.MULTILINE)
                    for match in matches:
                        brand = match.group(1)
                        brand = re.sub(r'\'s$', '', brand)
                        brand = brand.strip()
                        
                        if (len(brand) > 1 and 
                            not any(word in brand.lower() for word in ['the', 'and', 'or', 'but', 'for', 'with', 'without'])):
                            
                            # Calculate position weight (earlier mentions get higher weight)
                            position_weight = 1.0 / (line_num + 1)
                            
                            # Update brand prominence
                            if brand not in brand_prominence:
                                brand_prominence[brand] = {
                                    'mentions': 0,
                                    'weighted_score': 0,
                                    'contexts': set()
                                }
                            
                            brand_prominence[brand]['mentions'] += 1
                            brand_prominence[brand]['weighted_score'] += (weight * position_weight)
                            brand_prominence[brand]['contexts'].add(prompt_lower)
        
        # Verify the detected brands
        verified_brands = {}
        potential_brands = {k: v['mentions'] for k, v in brand_prominence.items()}
        verified_brand_names = set(verify_brands(client, potential_brands).keys())
        
        for brand in verified_brand_names:
            if brand in brand_prominence:
                verified_brands[brand] = brand_prominence[brand]
        
        # Calculate prominence scores
        total_prompts = len(prompts)
        
        # Prepare the results in the new format
        results = {
            'brands': {},
            'prompts': []
        }
        
        # Add brands data
        for brand, data in verified_brands.items():
            visibility_percentage = (len(data['contexts']) / total_prompts) * 100
            results['brands'][brand] = {
                'visibility': round(visibility_percentage, 1),
                'mentions': data['mentions'],
                'context_count': len(data['contexts'])
            }
        
        # Add prompts data
        for i, (prompt, response) in enumerate(zip(prompts, all_responses)):
            # Extract detected brands for this prompt
            detected_brands = []
            for brand in verified_brands:
                if prompt.lower() in brand_prominence[brand]['contexts']:
                    detected_brands.append(brand)
            
            results['prompts'].append({
                'id': i + 1,
                'prompt': prompt,
                'response': response,
                'detected_brands': detected_brands,
                'sources': []  # Sources will be added by the source analysis
            })
        
        print("Saving results...")
        with open('brand_analysis_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print the analysis
        print("\nFinal Analysis:")
        print("---------------")
        print(f"TOTAL BRANDS: {len(verified_brands)}\n")
        print("DETAILED BRAND ANALYSIS:")
        for brand, data in verified_brands.items():
            visibility = (len(data['contexts']) / total_prompts) * 100
            print(f"\n{brand}:")
            print(f"  Mentions: {data['mentions']}")
            print(f"  Visibility: {visibility:.1f}%")
            print(f"  Contexts: {len(data['contexts'])}")
            
    except Exception as e:
        print(f"\nError in analysis: {str(e)}")
        raise

def main():
    print("\nWelcome to Mistral AI Brand Analyzer!")
    print("Reading prompts from prompts.txt file...")
    
    try:
        # Read prompts from file
        try:
            with open('prompts.txt', 'r', encoding='utf-8') as f:
                prompts = [line.strip() for line in f if line.strip()]
                print(f"Read {len(prompts)} prompts from file")
        except FileNotFoundError:
            print("\nError: prompts.txt file not found.")
            print("Please create a prompts.txt file with one prompt per line.")
            return
            
        if not prompts:
            print("\nNo prompts found in prompts.txt. Please add some prompts to the file.")
            return
            
        total_prompts = len(prompts)
        print(f"\nFound {total_prompts} prompts to process...")
        
        print("\nInitializing Mistral client...")
        client = initialize_client()
        
        # Process prompts in larger batches
        batch_size = 15  # Increased batch size
        all_responses = []
        
        for i in range(0, total_prompts, batch_size):
            batch = prompts[i:i + batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}/{(total_prompts + batch_size - 1)//batch_size}")
            print(f"Processing prompts {i+1} to {min(i+batch_size, total_prompts)}")
            
            # Process batch in parallel
            batch_responses = process_prompts_batch(client, batch)
            all_responses.extend(batch_responses)
            
            # Small delay between batches to avoid rate limiting
            if i + batch_size < total_prompts:
                time.sleep(1)  # Increased delay between batches
        
        if all_responses:
            print(f"\nSuccessfully processed {len(all_responses)} prompts")
            analyze_responses(client, all_responses, prompts)
        else:
            print("\nNo valid responses were generated. Please check your prompts and try again.")
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("Please check your API key and internet connection.")

if __name__ == "__main__":
    main() 