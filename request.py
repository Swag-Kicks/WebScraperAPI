import requests

url = "http://127.0.0.1:5000/v5/get_data"

# JSON payload jo server ko bhejna hai
payload = {
    "product_url": "https://www.swag-kicks.com/cdn/shop/products/IMG_3298_20copy_dfa41d5c-336b-4866-99bd-ca7c1a7355e7.jpg?v=1694583064&width=713"
}

# Request bhejo
response = requests.post(url, json=payload)

# Response print karo
print("Status Code:", response.status_code)
print("Response JSON:", response.json())  # Assuming server JSON return karega
