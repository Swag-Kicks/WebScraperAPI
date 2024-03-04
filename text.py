import requests
def GetLinksFromSerpAPI(p_url):
    parameters = {
        "engine": "google_lens",
        "api_key": "5c4236693f1f420e308826d7f36e001950df15529036bf510c578fffe244598f",
        "url": p_url,
        "no_cache": False
    }

    # Construct the request URL
    request_url = "https://serpapi.com/search"

  # Make the GET request
    try:
        response = requests.get(request_url, params=parameters)
        data = response.json()
        visual_matches=data.get('visual_matches',[])

        ebay_links = []
        for match in visual_matches:
            link = match.get('link', '')
            if 'ebay' in link:
                ebay_links.append(link)


        return ebay_links
    except:
        print("Error:")
        return []
  
print(GetLinksFromSerpAPI("https://www.swag-kicks.com/cdn/shop/products/20240227_072012_IMG_9700_20copy.jpg?v=1709018439&width=600"))