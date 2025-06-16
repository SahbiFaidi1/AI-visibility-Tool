import os
from dotenv import load_dotenv
import requests
import time
import re
import json
import csv
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Set
from urllib.parse import urlparse

# Load environment variables from .env file
load_dotenv()

def extract_sources(response: str) -> List[Dict[str, str]]:
    """Extract sources from a Perplexity response"""
    sources = []
    
    # Print the response for debugging
    print("\nAnalyzing response for sources:")
    print(response[:200] + "..." if len(response) > 200 else response)
    
    # Extract URLs from the response
    url_pattern = r'https?://[^\s<>"\']+'
    urls = re.findall(url_pattern, response)
    for url in urls:
        domain = urlparse(url).netloc
        if domain and not any(s['domain'] == domain for s in sources):
            source_entry = {
                'url': url,
                'domain': domain,
                'source': domain,
                'type': 'direct_link'
            }
            sources.append(source_entry)
            print(f"Found URL: {url}")
    
    # Extract citations in the format [number]
    citation_pattern = r'\[(\d+)\]'
    citations = re.findall(citation_pattern, response)
    for citation in citations:
        if not any(s['source'] == citation for s in sources):
            source_entry = {
                'source': f"Citation {citation}",
                'url': '',
                'domain': '',
                'type': 'citation'
            }
            sources.append(source_entry)
            print(f"Found citation: {citation}")
    
    # Extract source mentions
    source_patterns = [
        r'Source[s]?:\s*(.*?)(?=\n|$)',
        r'Reference[s]?:\s*(.*?)(?=\n|$)',
        r'According to\s+(.*?)(?=[,.:])',
        r'Based on\s+(.*?)(?=[,.:])',
        r'From\s+(.*?)(?=[,.:])',
    ]
    
    for pattern in source_patterns:
        matches = re.finditer(pattern, response, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            source_text = match.group(1).strip()
            if not source_text:
                continue
                
            # Check if the source text contains a URL
            url_match = re.search(url_pattern, source_text, re.IGNORECASE)
            if url_match:
                url = url_match.group(0)
                domain = urlparse(url).netloc
                source_text = source_text.replace(url, '').strip()
            else:
                url = ''
                domain = ''
            
            # Clean up source text
            source_text = re.sub(r'[\[\]()]', '', source_text).strip()
            source_text = re.sub(r'\s+', ' ', source_text)
            
            if source_text and not any(s['source'] == source_text for s in sources):
                source_entry = {
                    'source': source_text,
                    'url': url,
                    'domain': domain,
                    'type': 'citation'
                }
                sources.append(source_entry)
                print(f"Found source mention: {source_text}")
    
    print(f"Total sources found in response: {len(sources)}")
    return sources

def get_perplexity_response(prompt: str):
    """Get response from Perplexity API for a single prompt"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        raise ValueError("Please set PERPLEXITY_API_KEY in your .env file")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. When answering questions, please provide detailed responses and ALWAYS include source citations. For each statement, cite your sources using the format 'Source: [URL or source name]'. Include multiple sources when possible. Make sure to cite specific sources for specific claims."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        print(f"\nProcessing prompt: {prompt}")
        start_time = time.time()
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        end_time = time.time()
        print(f"Response generated in {end_time - start_time:.2f} seconds")
        
        # Debug: Print raw API response
        print("\nRaw API response:")
        print(result)
        
        content = result['choices'][0]['message']['content']
        print("\nExtracted content:")
        print(content)
        
        # Extract sources from both the content and citations
        sources = []
        
        # First, add all citations from the API response
        if 'citations' in result:
            print("\nExtracting citations from API response:")
            for citation_url in result['citations']:
                domain = urlparse(citation_url).netloc
                source_entry = {
                    'url': citation_url,
                    'domain': domain,
                    'source': domain,
                    'type': 'perplexity_citation',
                    'citation_text': ''  # Will be filled if we find matching text
                }
                sources.append(source_entry)
                print(f"Found citation from API: {citation_url}")
        
        # Then extract sources from the content
        content_sources = extract_sources(content)
        
        # Try to match content sources with API citations
        for content_source in content_sources:
            if content_source['url']:
                # Check if this URL matches any API citation
                matching_source = next(
                    (s for s in sources if s['url'] == content_source['url']),
                    None
                )
                if matching_source:
                    matching_source['citation_text'] = content_source['source']
                    print(f"Matched citation text '{content_source['source']}' to URL {content_source['url']}")
                else:
                    sources.append(content_source)
            else:
                sources.append(content_source)
        
        # Deduplicate sources while preserving order
        seen = set()
        unique_sources = []
        for source in sources:
            key = (source['url'], source['source'])
            if key not in seen:
                seen.add(key)
                unique_sources.append(source)
        
        print(f"\nTotal unique sources found: {len(unique_sources)}")
        for source in unique_sources:
            print(f"- {source}")
        
        return {
            'content': content,
            'sources': unique_sources
        }
    except Exception as e:
        print(f"Error processing prompt '{prompt}': {str(e)}")
        if 'response' in locals() and hasattr(response, 'content'):
            print(f"Response content: {response.content}")
        return None

def analyze_sources(all_sources: List[Dict[str, str]]) -> None:
    """Analyze and print summary of collected sources"""
    print("\nSource Analysis:")
    print("-" * 50)
    
    # Count sources by type
    type_counts = {}
    domain_counts = {}
    prompt_sources = {}
    
    # Filter sources with URLs
    sources_with_urls = [s for s in all_sources if s['url']]
    
    for source in sources_with_urls:
        # Count by type
        source_type = source['type']
        type_counts[source_type] = type_counts.get(source_type, 0) + 1
        
        # Count by domain
        if source['domain']:
            domain_counts[source['domain']] = domain_counts.get(source['domain'], 0) + 1
        
        # Count by prompt
        prompt_id = source['prompt_id']
        if prompt_id not in prompt_sources:
            prompt_sources[prompt_id] = {
                'prompt': source['prompt'],
                'count': 0,
                'domains': set()
            }
        prompt_sources[prompt_id]['count'] += 1
        if source['domain']:
            prompt_sources[prompt_id]['domains'].add(source['domain'])
    
    # Print summary
    print(f"\nTotal sources with URLs found: {len(sources_with_urls)}")
    print("\nSources by type:")
    for source_type, count in type_counts.items():
        print(f"- {source_type}: {count}")
    
    print("\nTop domains:")
    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
    for domain, count in sorted_domains[:10]:  # Show top 10 domains
        print(f"- {domain}: {count} references")
    
    print("\nSources per prompt:")
    for prompt_id, data in sorted(prompt_sources.items()):
        print(f"\nPrompt {prompt_id}: {data['prompt']}")
        print(f"- Total sources: {data['count']}")
        if data['domains']:
            print(f"- Domains: {', '.join(sorted(data['domains']))}")
    
    # Save only sources with URLs to CSV
    csv_fields = ['prompt_id', 'prompt', 'source', 'url', 'domain', 'type', 'citation_text']
    try:
        with open('sources.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            print("\nWriting sources with URLs to CSV:")
            for source in sources_with_urls:
                row = {k: source.get(k, '') for k in csv_fields}
                writer.writerow(row)
                print(f"Wrote row: {row}")
    except Exception as e:
        print(f"Error writing CSV: {str(e)}")
    
    # Prepare data for the source usage chart
    chart_data = {
        'domains': list(domain_counts.keys()),
        'counts': list(domain_counts.values())
    }
    
    # Save chart data to a separate JSON file
    with open('source_usage_data.json', 'w') as f:
        json.dump(chart_data, f, indent=4)
    
    print("\nSource data saved to sources.csv")
    print("Source usage data saved to source_usage_data.json")

def process_prompts_file():
    """Process all prompts from prompts.txt file and store responses"""
    try:
        # Predefined prompts
        prompts = [
            "what are the top car brands in the world",
            "which car brands are the most reliable",
            "what are the best luxury car brands",
            "which car brands are known for safety",
            "what are the most affordable car brands",
            "which car brands have the best resale value"
        ]
        
        print(f"Processing {len(prompts)} prompts\n")
        total_prompts = len(prompts)
        
        # Process prompts and store responses
        responses = []
        all_mentions = []  # Store all brand mentions across all prompts
        brand_contexts = {}  # Track which prompts mention each brand
        all_sources = []  # Track all sources
        
        for i, prompt in enumerate(prompts, 1):
            response = get_perplexity_response(prompt)
            if response:
                content = response['content']
                sources = response['sources']
                
                print(f"\nProcessing sources for prompt {i}:")
                print(f"Found {len(sources)} sources")
                
                # Add sources to the global list with prompt context
                for source in sources:
                    source['prompt_id'] = i
                    source['prompt'] = prompt
                    all_sources.append(source)
                    print(f"Added source: {source}")
                
                # Extract brand mentions and continue with existing logic...
                matches = re.finditer(r'\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\b', content)
                response_mentions = []
                
                for match in matches:
                    brand = match.group(1)
                    if len(brand) > 1 and not any(word in brand.lower() for word in ['the', 'and', 'or', 'but', 'for', 'with', 'without']):
                        all_mentions.append(brand)
                        response_mentions.append(brand)
                        
                        if brand not in brand_contexts:
                            brand_contexts[brand] = set()
                        brand_contexts[brand].add(i)
                
                response_data = {
                    "id": i,
                    "prompt": prompt,
                    "response": content,
                    "detected_brands": list(set(response_mentions)),
                    "sources": sources
                }
                responses.append(response_data)
        
        print(f"\nTotal sources collected: {len(all_sources)}")
        
        # Save sources to CSV with additional debugging
        csv_fields = ['prompt_id', 'prompt', 'source', 'url', 'domain', 'type', 'citation_text']
        try:
            with open('sources.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields)
                writer.writeheader()
                print("\nWriting sources to CSV:")
                for source in all_sources:
                    row = {k: source.get(k, '') for k in csv_fields}
                    writer.writerow(row)
                    print(f"Wrote row: {row}")
        except Exception as e:
            print(f"Error writing CSV: {str(e)}")
        
        # Count total mentions for each brand
        potential_brands = {}
        for brand in all_mentions:
            potential_brands[brand] = potential_brands.get(brand, 0) + 1
        
        # Verify brands and calculate visibility percentages
        print("\nVerifying detected brands...")
        verified_brands = {}
        
        # Process brands in batches
        batch_size = 20
        brand_batches = [list(potential_brands.keys())[i:i + batch_size] 
                        for i in range(0, len(potential_brands), batch_size)]
        
        for batch in brand_batches:
            brands_list = ", ".join(batch)
            verification_prompt = f"""
            Which of these are real car companies or brands? 
            List only the real brands/companies from this list: {brands_list}
            Respond with only the brand names, separated by commas.
            """
            
            try:
                response = get_perplexity_response(verification_prompt)
                if response:
                    verified_list = [brand.strip() for brand in response['content'].split(',')]
                    
                    for brand in batch:
                        if brand in verified_list:
                            # Calculate visibility percentage based on both mentions and context
                            mentions = potential_brands[brand]
                            context_count = len(brand_contexts[brand])
                            
                            # Base visibility on context (prompts that mention the brand)
                            context_score = (context_count / total_prompts) * 100  # Max 100% from context
                            
                            # Additional score from number of mentions
                            max_mentions = max(potential_brands.values())  # Get the highest number of mentions
                            mention_score = (mentions / max_mentions) * 100  # Max 100% from mentions
                            
                            # Combine scores with equal weight
                            visibility = (context_score + mention_score) / 2
                            
                            # Ensure minimum visibility for brands mentioned in multiple contexts
                            if context_count > 1:  # Ensure minimum visibility for brands mentioned in multiple prompts
                                visibility = max(visibility, 10)  # Minimum 10% if mentioned in multiple prompts
                            
                            verified_brands[brand] = {
                                "mentions": mentions,
                                "visibility": round(visibility, 1),
                                "context_count": context_count,
                                "responses": sorted(list(brand_contexts[brand]))
                            }
                            print(f"✓ {brand} verified with {mentions} mentions in {context_count} prompts ({visibility:.1f}% visibility)")
                        else:
                            print(f"✗ {brand} is not a verified brand")
            except Exception as e:
                print(f"Error verifying batch: {str(e)}")
                continue
        
        # Save results to JSON files
        results = {
            "brands": verified_brands,
            "prompts": responses,
            "total_prompts": total_prompts,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": "perplexity"
        }
        
        with open('brand_analysis_results.json', 'w') as f:
            json.dump(results, f, indent=4)
        
        # Analyze sources
        analyze_sources(all_sources)
        
        print("\nBrand Analysis:")
        print("----------------")
        print(f"Total prompts analyzed: {total_prompts}")
        for brand, data in sorted(verified_brands.items(), key=lambda x: x[1]["visibility"], reverse=True):
            print(f"{brand}: {data['mentions']} mentions in {data['context_count']} prompts ({data['visibility']}% visibility)")
        
        return results
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    print("Starting Perplexity Brand Analysis...")
    process_prompts_file() 