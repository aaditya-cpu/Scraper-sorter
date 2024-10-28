from flask import Flask, request, render_template_string, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import sqlite3
import requests
from PIL import Image
from io import BytesIO

# Initialize the Flask application
app = Flask(__name__)

# Initialize SQLite database
conn = sqlite3.connect('extracted_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS extraction_results (id INTEGER PRIMARY KEY, url TEXT, json_content TEXT)''')
conn.commit()

# HTML template for the Flask dashboard with Bootstrap, the provided color theme, and a copy button
TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text Extractor</title>
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* Color Theme Swatches in Hex */
        .baseblood-of-Sun-1-hex { color: #540B0E; }
        .baseblood-of-Sun-2-hex { color: #A62E38; }
        .baseblood-of-Sun-3-hex { color: #335C67; }
        .baseblood-of-Sun-4-hex { color: #FFF3B0; }
        .baseblood-of-Sun-5-hex { color: #E09F3E; }

        body {
            background-color: #FFF3B0;
            color: #335C67;
        }
        .header {
            background-color: #540B0E;
            color: #FFF;
            padding: 20px;
            text-align: center;
        }
        .form-container {
            margin: 50px auto;
            padding: 30px;
            background-color: #E09F3E;
            border-radius: 50px;
            background: linear-gradient(145deg, #A62E38, #E09F3E);
            box-shadow:  20px 20px 60px #A62E38, -20px -20px 60px #FFF3B0;
            max-width: 600px;
            color: #FFF;
        }
        .btn-custom {
            background-color: #A62E38;
            color: #FFF;
        }
        .btn-custom:hover {
            background-color: #540B0E;
            color: #FFF;
        }
        .result-container {
            margin: 20px auto;
            padding: 20px;
            background-color: #E09F3E;
            border: 2px solid #335C67;
            border-radius: 50px;
            background: linear-gradient(145deg, #A62E38, #E09F3E);
            box-shadow:  20px 20px 60px #A62E38, -20px -20px 60px #FFF3B0;
            max-width: 800px;
            color: #FFF;
            position: relative;
        }
        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: #A62E38;
            color: #FFF;
            border: none;
            padding: 5px 10px;
            cursor: pointer;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Extract Text from URL</h1>
    </div>
    <div class="container">
        <div class="form-container">
            <form method="POST" action="/extract">
                <div class="form-group">
                    <label for="url">Enter URL:</label>
                    <input type="text" class="form-control" id="url" name="url" required>
                </div>
                <button type="submit" class="btn btn-custom">Extract Text</button>
            </form>
        </div>
        
        {% if extracted_data %}
        <div class="result-container">
            <h2>Extracted Data</h2>
            <button class="copy-btn" onclick="copyToClipboard()">Copy JSON</button>
            <pre id="jsonData">{{ extracted_data }}</pre>
        </div>
        {% endif %}
    </div>
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@1.16.1/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
    <script>
        function copyToClipboard() {
            var copyText = document.getElementById("jsonData").innerText;
            navigator.clipboard.writeText(copyText).then(function() {
                alert("Copied to clipboard");
            }, function(err) {
                console.error("Async: Could not copy text: ", err);
            });
        }
    </script>
</body>
</html>
"""

# Function to extract text and images using Selenium and BeautifulSoup
def extract_text_from_url(url):
    # Setting up Chrome options for Selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        # Fetch the URL
        driver.get(url)
        time.sleep(2)  # Allow time for JavaScript to execute

        # Scroll down to the bottom of the page to ensure all content is loaded
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Expand all dropdowns or hidden elements
        retry_count = 3
        while retry_count > 0:
            try:
                elements = driver.find_elements(By.XPATH, "//*[contains(@onclick, 'toggle') or contains(@class, 'dropdown') or contains(@aria-expanded, 'false')] | //button | //a[@role='button']")
                for element in elements:
                    try:
                        ActionChains(driver).move_to_element(element).click(element).perform()
                        time.sleep(0.5)
                    except Exception as e:
                        continue
                retry_count = 0
            except Exception as e:
                retry_count -= 1
                time.sleep(1)

        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract and label all sections of interest
        extracted_data = {
            "title": soup.title.string if soup.title else "",
            "meta_description": soup.find('meta', attrs={'name': 'description'})['content'] if soup.find('meta', attrs={'name': 'description'}) else "",
            "sections": [],
            "images": []
        }

        # Extract content based on headings, and group corresponding content
        current_section = None
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div']):
            if tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Start a new section with the heading
                if current_section:
                    extracted_data['sections'].append(current_section)
                current_section = {
                    "heading": f"{tag.name.upper()}: {tag.get_text(strip=True)}",
                    "content": ""
                }
            else:
                # Add content to the current section, including content type
                if current_section and tag.get_text(strip=True):
                    current_section['content'] += f"[{tag.name}] {tag.get_text(strip=True)}\n"

        # Append the last section if it exists
        if current_section:
            extracted_data['sections'].append(current_section)

        # Extract image URLs and their sizes
        img_tags = soup.find_all('img')
        for img in img_tags:
            img_url = img.get('src')
            if img_url:
                # Ensure the URL is absolute
                if not img_url.startswith(('http://', 'https://')):
                    img_url = requests.compat.urljoin(url, img_url)
                try:
                    # Fetch the image to get its size
                    response = requests.get(img_url)
                    img_obj = Image.open(BytesIO(response.content))
                    width, height = img_obj.size
                    extracted_data['images'].append({
                        "url": img_url,
                        "width": width,
                        "height": height
                    })
                except Exception as e:
                    continue

        # Convert the data to JSON format
        json_data = json.dumps(extracted_data, indent=4)

        # Save the extraction result to the SQLite database
        cursor.execute("INSERT INTO extraction_results (url, json_content) VALUES (?, ?)", (url, json_data))
        conn.commit()

        # Return the JSON data
        return json_data
    finally:
        # Close the WebDriver
        driver.quit()

# Flask routes
@app.route('/', methods=['GET'])
def index():
    return render_template_string(TEMPLATE)

@app.route('/extract', methods=['POST'])
def extract():
    url = request.form.get('url')
    extracted_data = extract_text_from_url(url)
    return render_template_string(TEMPLATE, extracted_data=extracted_data)
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
