import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Dict, List, Optional

def scrape_amazon_india(search_query, min_price, max_price, n: int = 20) -> List[Dict]:
    """
    Scrape Amazon India for products based on search query and price range.
    
    Args:
        search_query (str): Product to search for
        min_price : Minimum price in INR
        max_price : Maximum price in INR
        n (int): Number of products to return
        
    Returns:
        List[Dict]: List of product dictionaries with details
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    if min_price is None:
        min_price= 0
    else:
        min_price = min_price * 100
    if max_price is None:
        max_price= None
    else:
        max_price = max_price * 100
    
    base_url = "https://www.amazon.in/s"
    params = {
        'k': search_query,
        'rh': f'p_36:{min_price * 100}-{max_price * 100}',  # Convert to paisa (Amazon's price filter)
        'ref': 'sr_nr_p_36_5'
    }
    
    try:
        print(f"Making request to Amazon with params: {params}")
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()
        
        # Debug information
        print(f"Response status code: {response.status_code}")
        print(f"URL after redirection: {response.url}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check if we're being blocked or redirected to a captcha
        if "Sorry, we just need to make sure you're not a robot" in soup.text:
            print("Amazon is showing a captcha page. Try changing the User-Agent or use a proxy.")
            return []
        
        products = []
        product_containers = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        # Debug information
        print(f"Found {len(product_containers)} product containers")
        
        if not product_containers:
            # Try alternative container identifiers
            print("Trying alternative product container identifiers...")
            product_containers = soup.find_all('div', {'data-asin': re.compile(r'.+')})
            print(f"Found {len(product_containers)} products with alternative method")
        
        for i, container in enumerate(product_containers[:n]):
            try:
                print(f"Processing product {i+1}/{min(n, len(product_containers))}")
                product = {}
                
                # Enhanced title extraction
                def extract_title():
                    # Try multiple title element patterns
                    title_patterns = [
                        # Pattern 1: Standard product title span
                        ('span', {'class': 'a-text-normal'}),
                        # Pattern 2: H2 heading containing the title
                        ('h2', {'class': 'a-size-mini'}),
                        # Pattern 3: Product title in link text
                        ('a', {'class': 'a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal'}),
                        # Pattern 4: Alternate title class
                        ('span', {'class': 'a-size-medium a-color-base a-text-normal'}),
                        # Pattern 5: Title in product description
                        ('span', {'class': 'a-size-base-plus a-color-base a-text-normal'})
                    ]
                    
                    for tag, attrs in title_patterns:
                        title_elem = container.find(tag, attrs)
                        if title_elem and title_elem.text.strip():
                            # Clean and normalize the title
                            title = title_elem.text.strip()
                            # Remove multiple spaces
                            title = ' '.join(title.split())
                            # Remove unwanted characters
                            title = title.replace('\u200b', '')  # Remove zero-width space
                            # Truncate excessively long titles
                            if len(title) > 200:
                                title = title[:197] + '...'
                            return title
                    
                    # If no title found through patterns, try h2 tag directly
                    h2_elem = container.find('h2')
                    if h2_elem:
                        return h2_elem.text.strip()
                    
                    # Try searching within all nested a tags
                    a_tags = container.find_all('a')
                    for a in a_tags:
                        if a.text and len(a.text.strip()) > 10:  # Likely a title if text is substantial
                            return a.text.strip()
                    
                    return 'N/A'
                
                product['title'] = extract_title()
                print(f"Title: {product['title']}")
                
                # Skip product if no valid title found
                if product['title'] == 'N/A':
                    print("Skipping product due to missing title")
                    continue
                
                # Extract ASIN (Amazon Standard Identification Number)
                product['asin'] = container.get('data-asin', 'N/A')
                
                # Link extraction
                link_elem = container.find('a', {'class': 'a-link-normal s-no-outline'})
                if not link_elem:
                    link_elem = container.find('a', {'class': 'a-link-normal'})
                
                if link_elem and 'href' in link_elem.attrs:
                    href = link_elem['href']
                    product['link'] = f"https://www.amazon.in{href}" if href.startswith('/') else href
                else:
                    # Try to find any a tag that might contain the product link
                    a_tags = container.find_all('a')
                    for a in a_tags:
                        if 'href' in a.attrs and '/dp/' in a['href']:
                            href = a['href']
                            product['link'] = f"https://www.amazon.in{href}" if href.startswith('/') else href
                            break
                    else:
                        product['link'] = f"https://www.amazon.in/dp/{product['asin']}" if product['asin'] != 'N/A' else 'N/A'
                
                print(f"Link: {product.get('link', 'Not found')}")
                
                # Fixed price extraction to handle "M.R.P:" text
                def extract_price():
                    # First attempt with standard price element
                    price_elem = container.find('span', {'class': 'a-price-whole'})
                    
                    # If not found, try alternative price elements
                    if not price_elem:
                        price_elem = container.find('span', {'class': 'a-offscreen'})
                    
                    if not price_elem:
                        # Try to find any element that might contain price
                        price_patterns = container.find_all(string=re.compile(r'₹|Rs\.|\d+,\d+'))
                        for pattern in price_patterns:
                            if '₹' in pattern or 'Rs.' in pattern:
                                price_elem = pattern
                                break
                    
                    if not price_elem:
                        print("No price element found")
                        return 0
                    
                    # Get the price text
                    if hasattr(price_elem, 'text'):
                        price_text = price_elem.text.strip()
                    else:
                        price_text = str(price_elem).strip()
                    
                    print(f"Raw price text: {price_text}")
                    
                    # Extract price using regex
                    price_match = re.search(r'(?:₹|Rs\.)?[,\d]+(?:\.\d+)?', price_text)
                    if price_match:
                        price_text = price_match.group(0)
                    
                    # Remove currency symbols and non-numeric characters
                    price_text = re.sub(r'[^\d,.]', '', price_text)
                    
                    # Handle empty string after cleaning
                    if not price_text:
                        print("Empty price text after cleaning")
                        return 0
                    
                    # Convert cleaned price to integer
                    try:
                        # Handle potential decimal prices
                        if '.' in price_text:
                            return int(float(price_text.replace(',', '')))
                        else:
                            return int(price_text.replace(',', ''))
                    except ValueError as e:
                        print(f"Error converting price: {e}")
                        return 0
                
                product['currency'] = '₹'
                product['price'] = extract_price()
                print(f"Extracted price: {product['price']}")
                
                # Rating extraction
                rating_elem = container.find('span', {'class': 'a-icon-alt'})
                if rating_elem and rating_elem.text:
                    try:
                        # Try to extract rating with regex
                        rating_match = re.search(r'(\d+(\.\d+)?)', rating_elem.text)
                        if rating_match:
                            product['rating'] = float(rating_match.group(1))
                        else:
                            product['rating'] = 0
                    except Exception as e:
                        print(f"Error extracting rating: {e}")
                        product['rating'] = 0
                else:
                    product['rating'] = 0
                
                # Reviews extraction
                reviews_elem = container.find('span', {'class': 'a-size-base s-underline-text'})
                if not reviews_elem:
                    reviews_elem = container.find('span', {'class': 'a-size-base'})
                
                if reviews_elem and reviews_elem.text:
                    try:
                        # Extract only digits from the reviews count
                        reviews_match = re.search(r'(\d+[,\d]*)', reviews_elem.text)
                        if reviews_match:
                            product['reviews'] = int(reviews_match.group(1).replace(',', ''))
                        else:
                            product['reviews'] = 0
                    except Exception as e:
                        print(f"Error extracting reviews: {e}")
                        product['reviews'] = 0
                else:
                    product['reviews'] = 0
                
                # Image extraction
                img_elem = container.find('img', {'class': 's-image'})
                if not img_elem:
                    img_elem = container.find('img')
                
                product['featured_image'] = img_elem['src'] if img_elem and 'src' in img_elem.attrs else 'N/A'
                
                # Prime badge
                prime_elem = container.find('i', {'class': 'a-icon-prime'})
                product['is_prime'] = bool(prime_elem)
                
                # Bestseller badge
                bestseller_elem = container.find('span', {'class': 'a-badge-label'})
                product['is_best_seller'] = bool(bestseller_elem and 'Bestseller' in bestseller_elem.text) if bestseller_elem else False
                
                # Amazon's Choice badge
                amazons_choice = container.find('span', {'class': 'a-badge-label'})
                product['is_amazon_choice'] = bool(amazons_choice and "Amazon's Choice" in amazons_choice.text) if amazons_choice else False
                
                products.append(product)
                print(f"Successfully added product to results")
                
            except Exception as e:
                print(f"Error processing product: {str(e)}")
                continue
        
        print(f"Returning {len(products)} products")
        return products
        
    except requests.RequestException as e:
        print(f"Error making request: {str(e)}")
        return []

# Example usage
#if __name__ == "__main__":
 #   products = scrape_amazon_india("smartphone", 10000, 20000, 5)
#    print(json.dumps(products, indent=2))