import requests

url = "http://127.0.0.1:5000/v5/get_data"

# JSON payload jo server ko bhejna hai
payload = {
    "product_url": "https://images-wp.stockx.com/news/wp-content/uploads/2022/08/blog-hero-twitter-square-1-1200x1200.jpg"
}

# Request bhejo
response = requests.post(url, json=payload)

# Response print karo
print("Status Code:", response.status_code)
print("Response JSON:", response.json())  # Assuming server JSON return karega
