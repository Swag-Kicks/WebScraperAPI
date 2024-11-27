from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import sql
from flask_cors import CORS
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import json
import google.generativeai as genai
import os

import re
import json

from requests import Session
from bs4 import BeautifulSoup

class GoogleLens:
    def __init__(self):
        self.url = "https://lens.google.com"
        self.session = Session()
        self.session.headers.update(
            {'User-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:103.0) Gecko/20100101 Firefox/103.0'}
        )

    def __get_prerender_script(self, page: str):
        soup = BeautifulSoup(page, 'html.parser')

        prerender_script = list(filter(
            lambda s: (
                'AF_initDataCallback(' in s.text and
                re.search(r"key: 'ds:(\d+)'", s.text).group(1) == "0"),
            soup.find_all('script')))[0].text
        prerender_script = prerender_script.replace(
            "AF_initDataCallback(", "").replace(");", "")
        hash = re.search(r"hash: '(\d+)'", prerender_script).group(1)
        prerender_script = prerender_script.replace(
            f"key: 'ds:0', hash: '{hash}', data:",
            f"\"key\": \"ds:0\", \"hash\": \"{hash}\", \"data\":").replace("sideChannel:", "\"sideChannel\":")

        prerender_script = json.loads(prerender_script)

        return prerender_script['data'][1]

    def __parse_prerender_script(self, prerender_script):
        data = {
            "match": None,
            "similar": []
        }

        try:
            data["match"] = {
                "title": prerender_script[0][1][8][12][0][0][0],
                "thumbnail": prerender_script[0][1][8][12][0][2][0][0],
                "pageURL": prerender_script[0][1][8][12][0][2][0][4]
            }
        except IndexError:
            pass
        
        if data["match"] is not None:
            visual_matches = prerender_script[1][1][8][8][0][12]
        else:
            try:
                visual_matches = prerender_script[0][1][8][8][0][12]
            except IndexError:
                return data

        for match in visual_matches:
            data["similar"].append(
                {
                    "title": match[3],
                    "pageURL": match[5],
                    "sourceWebsite": match[14]
                }
            )

        return data
        
    def search_by_url(self, url: str):
        response = self.session.get(self.url + "/uploadbyurl", params={"url": url}, allow_redirects=True)

        prerender_script = self.__get_prerender_script(response.text)

        return self.__parse_prerender_script(prerender_script)

app = Flask(__name__)
CORS(app)
#CORS(app, resources={r"/api/*": {"origins": "*"}})

genai.configure(api_key="AIzaSyBGLYWcvn5gh0GeLocshqjL7ug8GWVNzA8")

model = genai.GenerativeModel('gemini-1.5-flash-8b')

@app.route('/keep_alive', methods=['GET'])
def keep_alive():
  return 'Server is alive!!!'


@app.route('/', methods=['GET'])
def keep_aliv():
  return 'Server is alive!'


@app.route('/AddDatatoDatabase', methods=['POST'])
def AddDatatoDatabase():
  try:
    url = 'postgres://cwgfmigf:6Rs-BQSMOQv7ai06RFzTCVkVj0RgzTDw@tiny.db.elephantsql.com/cwgfmigf'
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    data = request.get_json()
    queries = data.get('listOfQuery')
    cur.execute(queries[len(queries) - 1])
    uploaded_id = str(cur.fetchone()[0])
    for i in range(len(queries) - 1):
      queries[i] = queries[i].replace("0", uploaded_id)
      cur.execute(queries[i])
    conn.commit()
    cur.close()
    conn.close()
    return jsonify("success" + uploaded_id), 200
  except Exception as e:
    print(str(e))
    return jsonify({'error': str(e)}), 500


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
            if "https://www.ebay." in link and "/itm" in link:
                ebay_links.append(link)
                if(len(ebay_links)==10):
                  break


        return ebay_links
    except:
        print("Error:")
        return []

def find_ebay_links(image_url):
    lens = GoogleLens()
    search_result = lens.search_by_url(image_url)
    response_data=search_result


    ebay_links = []

    # Loop through the 'similar' list in the response data
    for item in response_data['similar']:
        page_url = item.get('pageURL')  # Get the pageURL from each item
        if page_url and "https://www.ebay." in page_url and "/itm" in page_url:
            ebay_links.append(page_url)
            if len(ebay_links) >= 10:  # Stop after collecting 10 links
                break

    # Print the collected eBay links
    #print(ebay_links)
    return ebay_links

def find_links(image_url, url_filter=None):
    lens = GoogleLens()
    search_result = lens.search_by_url(image_url)
    response_data = search_result

    links = []

    # Loop through the 'similar' list in the response data
    for item in response_data['similar']:
        page_url = item.get('pageURL')  # Get the pageURL from each item
        if page_url:
            if url_filter:
                # Apply the filter if it's provided
                if url_filter in page_url:
                    links.append(page_url)
            else:
                # Add all URLs if no filter is provided
                links.append(page_url)
            
        if len(links) >= 10:  # Stop after collecting 10 links
            break

    return links

@app.route('/getLinks', methods=['POST'])
def get_links():
    # Extract 'image_url' and 'filter' from the request body
    data = request.json
    image_url = data.get('image_url')
    url_filter = data.get('filter', None)

    if not image_url:
        return jsonify({'error': 'image_url is required'}), 400

    # Find and filter the links
    links = find_links(image_url, url_filter)

    return jsonify({'links': links}), 200


@app.route('/get_ebay_data', methods=['POST'])
def get_ebay_data():
  try:
    # Get the product URL from the request
    data = request.get_json()
    p_url = data.get('product_url')
    category_aspects=data.get('aspects')
    category_value={}
    urls=GetLinksFromSerpAPI(p_url)
    price=0
    title=''
    r=requests.get(urls[0])
    soup=BeautifulSoup(r.text,'html.parser')
    if (price == 0):
        pricediv = soup.find('div', class_='x-price-primary')
        price = pricediv.find('span', class_='ux-textspans').text
        titleh=soup.find('h1',class_='x-item-title__mainTitle')
        title=titleh.find('span',class_='ux-textspans ux-textspans--BOLD').text
        print(price)
    def UrlScraper(url):
      response = requests.get(url)
      soup = BeautifulSoup(response.text, 'html.parser')
      evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')
      for evo_row in evo_rows:
        evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
        for evo_col in evo_cols:
          labels = evo_col.find('dt', class_='ux-labels-values__labels')
          values = evo_col.find('dd', class_='ux-labels-values__values')
          
          if labels:
            for i in range(len(category_aspects)):
              label_text = labels.find(
                  'div', class_='ux-labels-values__labels-content').find(
                      'span', class_='ux-textspans').text
              if label_text == category_aspects[i] and label_text not in category_value:
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                category_value[category_aspects[i]] = value_text
                print(f"{category_aspects[i]}: {category_value[category_aspects[i]]}")

    threads = []
    for url in urls:
      thread=threading.Thread(target=UrlScraper,args=(url,))
      thread.start()
      threads.append(thread)
    for thread in threads:
      thread.join()

    # Construct the API response
    api_response = {
        'category_value': category_value,
        'price':price,
        'title':title
    }  # taxanomy dictionary

    return jsonify(api_response), 200

  except Exception as e:
    print(str(e))
    return jsonify({'error': str(e)}), 500

@app.route('/get_product_data', methods=['POST'])
def get_product_data():
  try:
    # Get the product URL from the request
    data = request.get_json()
    urls = data.get('product_url')
    brand = ''
    color = ''
    country = ''
    type = ''
    upc = ''
    material = ''
    model = ''
    price = ''
    title=''

    def checkAll():
      if any(value == '' for value in
             [brand, color, country, type, upc, material, model, price]):
        print("0")
        return False
      else:
        return True

    for url in urls:
      try:
        response = requests.get(url,timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')
        if(title==''):
          titleh = soup.find('h1', class_='x-item-title__mainTitle')
          title = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
        if (price == ''):
          pricediv = soup.find('div', class_='x-price-primary')
          price = pricediv.find('span', class_='ux-textspans').text
        for evo_row in evo_rows:
          evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
          for evo_col in evo_cols:
            labels = evo_col.find('dt', class_='ux-labels-values__labels')
            values = evo_col.find('dd', class_='ux-labels-values__values')

            if labels:
              label_text = labels.find(
                  'div', class_='ux-labels-values__labels-content').find(
                      'span', class_='ux-textspans').text
              if label_text == 'Brand' and brand == '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                brand = value_text
                print(f"Brand: {value_text}")
              elif label_text == 'Color' and color == '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                color = value_text
                print(f"Color: {value_text}")
              elif label_text == 'Country/Region of Manufacture' and country != '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                country = value_text
                print(f"Country: {value_text}")
              elif label_text == 'Type' and type == '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                type = value_text
                print(f"Type: {value_text}")
              elif label_text == 'UPC' and upc == '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                if (value_text != 'Does not apply'):
                  upc = value_text
                  print(f"UPC: {value_text}")
              elif label_text == 'Model' and model == '':
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                model = value_text
                print(f"Model: {value_text}")
              elif 'Material' in label_text:
                value_text = values.find(
                    'div', class_='ux-labels-values__values-content').find(
                        'span', class_='ux-textspans').text
                if (value_text not in material):
                  if (material == ''):
                    material = value_text
                  else:
                    material += " , " + value_text
                    print(f"Material : {material}")
        if (checkAll()):
          break
      except:
        print("An exception occurred at ",url)
    # Construct the API response
    api_response = {
        'title':title,
        'brand': brand,
        'color': color,
        'country': country,
        'type': type,
        'upc': upc,
        'material': material,
        'price': price,
        'model': model
    }  # taxanomy dictionary
    return jsonify({'api_response': api_response}), 200

  except Exception as e:
    return jsonify({'error': str(e)}), 500

@app.route('/get_data', methods=['POST'])
def get_data():
  try:
    data = request.get_json()
    p_url = data.get('product_url')
    category_value = {}
    urls = GetLinksFromSerpAPI(p_url)
    price = 0
    title = ''
    category_id=''
    print("Number of url to be scraped: "+str(len(urls)))
    # Fetch the first URL to get price and title
    def get_headers(index):
      print(urls[index])
      r = requests.get(urls[index],timeout=10)
      soup = BeautifulSoup(r.text, 'html.parser')
      try: 
          pricediv = soup.find('div', class_='x-price-primary')
          pricer = pricediv.find('span', class_='ux-textspans').text
          titleh = soup.find('h1', class_='x-item-title__mainTitle')
          titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
          categorydiv=soup.find_all('a',class_='seo-breadcrumb-text')
          categoryarray=categorydiv[len(categorydiv)-1].get('href').split('/')
          category_idr=categoryarray[len(categoryarray)-2]
          if(category_idr=='p' or category_idr=='b'):
            categoryarray=categorydiv[len(categorydiv)-2].get('href').split('/')
          category_idr=categoryarray[len(categoryarray)-2]
          print("Title: ",titler)
          print("category ID: ",int(category_idr))
          print("Price: ",pricer)
          return pricer,titler,category_idr
      except Exception as e:
        print(str(e))
        return get_headers(index+1)
        
    count=0
    price,title,category_id=get_headers(count)
    lock = threading.Lock()

    def UrlScraper(url):
      try:
          response = requests.get(url, timeout=10)  # Adding timeout
          soup = BeautifulSoup(response.text, 'html.parser')
          evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')
          for evo_row in evo_rows:
              evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
              for evo_col in evo_cols:
                  labels = evo_col.find('dt', class_='ux-labels-values__labels')
                  values = evo_col.find('dd', class_='ux-labels-values__values')
                  
                  if labels:
                      label_text = labels.find(
                          'div', class_='ux-labels-values__labels-content').find(
                              'span', class_='ux-textspans').text
                      if label_text not in category_value:
                          value_text = values.find(
                              'div', class_='ux-labels-values__values-content').find(
                                  'span', class_='ux-textspans').text
                          
                          # Lock the dictionary for safe access
                          with lock:
                              if label_text not in category_value:
                                  category_value[label_text] = value_text
                                  print(f"{label_text}: {category_value[label_text]}")
      except Exception as e:
          print(f"Error scraping URL {url}: {str(e)}")
    # Create and start threads
    threads = []
    for url in urls:
      thread = threading.Thread(target=UrlScraper, args=(url,))
      thread.start()
      threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
      print(1)
      thread.join()

    # Construct the API response
    api_response = {
        'category_value': category_value,
        'price': price,
        'title': title,
        'category_id':category_id
    }
    return jsonify(api_response), 200

  except Exception as e:
    print(str(e))
    return jsonify({'error': str(e)}), 500

@app.route('/v2/get_data', methods=['POST'])
def get_data2():
  try:
    data = request.get_json()
    p_url = data.get('product_url')
    category_value = {}
    confirmed_value={}
    urls = GetLinksFromSerpAPI(p_url)
    price = 0
    title = ''
    category_id=''
    breadcrumb_string=''
    print("Number of url to be scraped: "+str(len(urls)))
    # Fetch the first URL to get price and title
    def get_headers(index):
      print(urls[index])
      r = requests.get(urls[index],timeout=10)
      soup = BeautifulSoup(r.text, 'html.parser')
      try: 
          pricediv = soup.find('div', class_='x-price-primary')
          pricer = pricediv.find('span', class_='ux-textspans').text
          titleh = soup.find('h1', class_='x-item-title__mainTitle')
          titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
          categorydiv=soup.find_all('a',class_='seo-breadcrumb-text')
          categoryarray=categorydiv[len(categorydiv)-1].get('href').split('/')
          category_idr=categoryarray[len(categoryarray)-2]
          if(category_idr=='p' or category_idr=='b'):
            categoryarray=categorydiv[len(categorydiv)-2].get('href').split('/')
          category_idr=categoryarray[len(categoryarray)-2]
          breadcrumbs = []

          for breadcrumb in soup.select('.seo-breadcrumb-text'):
              breadcrumbs.append(breadcrumb.get_text(strip=True))

          breadcrumb_string = ' > '.join(breadcrumbs)
          print(breadcrumb_string)
          print("Title: ",titler)
          print("category ID: ",int(category_idr))
          print("Price: ",pricer)
          return pricer,titler,category_idr,breadcrumb_string
      except Exception as e:
        print(str(e))
        return get_headers(index+1)
        
    count=0
    price,title,category_id,breadcrumb_string=get_headers(count)
    lock = threading.Lock()

    def UrlScraper(url):
      try:
          response = requests.get(url, timeout=10)  # Adding timeout
          soup = BeautifulSoup(response.text, 'html.parser')
          evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')
          
          for evo_row in evo_rows:
              evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
              for evo_col in evo_cols:
                  labels = evo_col.find('dt', class_='ux-labels-values__labels')
                  values = evo_col.find('dd', class_='ux-labels-values__values')
                  
                  if labels:
                      label_text = labels.find(
                          'div', class_='ux-labels-values__labels-content').find(
                              'span', class_='ux-textspans').text
                      value_text = values.find(
                          'div', class_='ux-labels-values__values-content').find(
                              'span', class_='ux-textspans').text if values else None
                      
                      if label_text and value_text:
                          # Lock the dictionary for safe access
                          with lock:
                              if label_text not in category_value:
                                  category_value[label_text] = []
                              
                              if label_text not in confirmed_value:
                                  confirmed_value[label_text] = set()

                              if value_text in confirmed_value[label_text]:
                                  continue  # Skip if the value_text is already confirmed for this label

                              if value_text not in category_value[label_text]:
                                  category_value[label_text].append(value_text)
                                  print(f"{label_text}: {value_text}")
                              else:
                                  # Move to confirmed values and remove from category_value
                                  confirmed_value[label_text].add(value_text)
                                  category_value[label_text].remove(value_text)
                                  print(f"Confirmed {label_text}: {value_text}")
      except Exception as e:
          print(f"Error scraping URL {url}: {str(e)}")
    # Create and start threads
    threads = []
    for url in urls:
      thread = threading.Thread(target=UrlScraper, args=(url,))
      thread.start()
      threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
      print(1)
      thread.join()
    def remove_empty_lists(data):
      return {k: v for k, v in data.items() if v}
    confirmed_value_serializable = {k: list(v) for k, v in confirmed_value.items()}
    category_value=remove_empty_lists(category_value)
    confirmed_value=remove_empty_lists(confirmed_value_serializable)
    # Construct the API response
    api_response = {
        'confirmed_value':confirmed_value,
        'category_value': category_value,
        'price': price,
        'title': title,
        'category_id':category_id,
        'category':breadcrumb_string
    }
    return jsonify(api_response), 200

  except Exception as e:
    print(str(e))
    return jsonify({'error': str(e)}), 500

@app.route('/v3/get_data', methods=['POST'])
def get_data3():
    try:
        data = request.get_json()
        p_url = data.get('product_url')
        category_value = {}
        value_count = {}
        urls = GetLinksFromSerpAPI(p_url)
        price = 0
        title = ''
        category_id = ''
        breadcrumb_string = ''
        currency_name=''
        print("Number of urls to be scraped: " + str(len(urls)))
        def get_headers(index):
            print(urls[index])
            r = requests.get(urls[index], timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            try:
                pricediv = soup.find('div', class_='x-price-primary')
                pricer = pricediv.find('span', class_='ux-textspans').text
                titleh = soup.find('h1', class_='x-item-title__mainTitle')
                titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
                categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
                categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                if category_idr == 'p' or category_idr == 'b':
                    categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                breadcrumbs = []

                for breadcrumb in soup.select('.seo-breadcrumb-text'):
                    breadcrumbs.append(breadcrumb.get_text(strip=True))
                currency,price_value=pricer.split(' $')
                price_float=float(price_value)
                if("$" in pricer):
                  currency="USD"
                elif("€" in pricer):
                  currency="EUR"
                elif("£" in pricer):
                  currency="GBP"
                elif("¥" in pricer):
                  currency="JPY"

                breadcrumb_string = ' > '.join(breadcrumbs)
                print(breadcrumb_string)
                print("Title: ", titler)
                print("category ID: ", int(category_idr))
                print("Price: ", pricer)
                return price_float, titler, category_idr, breadcrumb_string,currency
            except Exception as e:
                print(str(e))
                return get_headers(index + 1)

        count = 0
        price, title, category_id, breadcrumb_string,currency_name = get_headers(count)
        lock = threading.Lock()

        def UrlScraper(url):
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')

                for evo_row in evo_rows:
                    evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
                    for evo_col in evo_cols:
                        labels = evo_col.find('dt', class_='ux-labels-values__labels')
                        values = evo_col.find('dd', class_='ux-labels-values__values')

                        if labels:
                            label_text = labels.find(
                                'div', class_='ux-labels-values__labels-content').find(
                                'span', class_='ux-textspans').text
                            value_text = values.find(
                                'div', class_='ux-labels-values__values-content').find(
                                'span', class_='ux-textspans').text if values else None

                            if label_text and value_text:
                                with lock:
                                    if label_text not in category_value:
                                        category_value[label_text] = []
                                    if label_text not in value_count:
                                        value_count[label_text] = {}

                                    if value_text not in value_count[label_text]:
                                        value_count[label_text][value_text] = 0
                                    value_count[label_text][value_text] += 1

            except Exception as e:
                print(f"Error scraping URL {url}: {str(e)}")

        # Create and start threads
        threads = []
        for url in urls:
            thread = threading.Thread(target=UrlScraper, args=(url,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to finish
        for thread in threads:
            print(1)
            thread.join()

        def get_confirmed_and_category_values(counts):
            confirmed = {}
            category = {}
            for label, values in counts.items():
                for value, count in values.items():
                    if count > 2:
                        if label not in confirmed:
                            confirmed[label] = []
                        confirmed[label].append((value, count))
                    else:
                        if label not in category:
                            category[label] = []
                        category[label].append(value)
            return confirmed, category

        confirmed_value, category_value = get_confirmed_and_category_values(value_count)

        # Sort each label's values by their count in descending order
        confirmed_value = {k: sorted(v, key=lambda x: x[1], reverse=True) for k, v in confirmed_value.items()}

        # Sort the confirmed_value dictionary by the highest count of its values
        confirmed_value = dict(sorted(confirmed_value.items(), key=lambda item: max(item[1], key=lambda x: x[1])[1], reverse=True))

        # Convert confirmed values to the required format
        confirmed_value = {k: [val for val, count in v] for k, v in confirmed_value.items()}

        def remove_empty_lists(data):
            return {k: v for k, v in data.items() if v}
        
        for i in confirmed_value:
          print(i)
          category_value[i]=[]
        category_value = remove_empty_lists(category_value)  # Clean up empty lists from category_value

        # Construct the API response
        api_response = {
            'confirmed_value': confirmed_value,
            'category_value': category_value,
            'price': price,
            'currency':currency_name,
            'title': title,
            'category_id': category_id,
            'category': breadcrumb_string
        }
        return jsonify(api_response), 200

    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/v4/get_data', methods=['POST'])
def get_data4():
    try:
        data = request.get_json()
        p_url = data.get('product_url')
        token=data.get('token')
        category_value = {}
        value_count = {}
        urls = GetLinksFromSerpAPI(p_url)
        price = 0
        title = ''
        category_id = ''
        breadcrumb_string = ''
        currency_name=''
        print("Number of urls to be scraped: " + str(len(urls)))
        def get_headers(index):
            print(urls[index])
            r = requests.get(urls[index], timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            try:
                pricediv = soup.find('div', class_='x-price-primary')
                pricer = pricediv.find('span', class_='ux-textspans').text
                titleh = soup.find('h1', class_='x-item-title__mainTitle')
                titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
                categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
                categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                if category_idr == 'p' or category_idr == 'b':
                    categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                breadcrumbs = []

                for breadcrumb in soup.select('.seo-breadcrumb-text'):
                    breadcrumbs.append(breadcrumb.get_text(strip=True))
                currency,price_value=pricer.split(' $')
                price_float=float(price_value)
                if("$" in pricer):
                  currency="USD"
                elif("€" in pricer):
                  currency="EUR"
                elif("£" in pricer):
                  currency="GBP"
                elif("¥" in pricer):
                  currency="JPY"

                breadcrumb_string = ' > '.join(breadcrumbs)
                print(breadcrumb_string)
                print("Title: ", titler)
                print("category ID: ", int(category_idr))
                print("Price: ", pricer)
                return price_float, titler, category_idr, breadcrumb_string,currency
            except Exception as e:
                print(str(e))
                return get_headers(index + 1)

        count = 0
        price, title, category_id, breadcrumb_string,currency_name = get_headers(count)
        lock = threading.Lock()

        def fetchCategoryAspects(categoryID,token):
          url = "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id=15687"

          payload = json.dumps({
            "token": token
          })
          headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid=s%3AuTDH_5nvCY5WasAeZjyieT7Z326oaabd.zLFzbLPlZQjE19RXWcE1w6aYEUTwuyCArC03mo0coYU'
          }

          response = requests.request("POST", "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id="+str(categoryID), headers=headers, data=payload)
          if response.status_code == 404:
            print("Response token expired")
            return "null"
          else:
            response_data = response.json()
            # Extracting aspect names where aspectUsage is 'RECOMMENDED'
            recommended_aspect_names = [
                aspect["localizedAspectName"]
                for aspect in response_data["category_aspects"]["aspects"]
                if aspect["aspectConstraint"]["aspectUsage"] == "RECOMMENDED"
            ]

            return recommended_aspect_names

        def UrlScraper(url):
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')

                for evo_row in evo_rows:
                    evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
                    for evo_col in evo_cols:
                        labels = evo_col.find('dt', class_='ux-labels-values__labels')
                        values = evo_col.find('dd', class_='ux-labels-values__values')

                        if labels:
                            label_text = labels.find(
                                'div', class_='ux-labels-values__labels-content').find(
                                'span', class_='ux-textspans').text
                            value_text = values.find(
                                'div', class_='ux-labels-values__values-content').find(
                                'span', class_='ux-textspans').text if values else None

                            if label_text and value_text:
                                with lock:
                                    if label_text not in category_value:
                                        category_value[label_text] = []
                                    if label_text not in value_count:
                                        value_count[label_text] = {}

                                    if value_text not in value_count[label_text]:
                                        value_count[label_text][value_text] = 0
                                    value_count[label_text][value_text] += 1

                  # Clear the BeautifulSoup object to release memory
                soup.decompose()
                soup = None
            except Exception as e:
                print(f"Error scraping URL {url}: {str(e)}")
              

        # Create and start threads
        threads = []
        for url in urls:
            thread = threading.Thread(target=UrlScraper, args=(url,))
            thread.start()
            threads.append(thread)
        recommended_aspect_names = fetchCategoryAspects(category_id, token)
        if(recommended_aspect_names=="null"):
          return jsonify({'error': "Token Expired"}), 500

        # Wait for all threads to finish
        for thread in threads:
            print(1)
            thread.join()
        recommended_aspect_names = fetchCategoryAspects(category_id, token)
        def get_confirmed_and_category_values(counts):
            confirmed = {}
            category = {}
            for label, values in counts.items():
                for value, count in values.items():
                    if count > 2:
                        if label not in confirmed:
                            confirmed[label] = []
                        confirmed[label].append((value, count))
                    else:
                        if label not in category:
                            category[label] = []
                        category[label].append(value)
            return confirmed, category

        confirmed_value, category_value = get_confirmed_and_category_values(value_count)

        # Sort each label's values by their count in descending order
        confirmed_value = {k: sorted(v, key=lambda x: x[1], reverse=True) for k, v in confirmed_value.items()}

        # Sort the confirmed_value dictionary by the highest count of its values
        confirmed_value = dict(sorted(confirmed_value.items(), key=lambda item: max(item[1], key=lambda x: x[1])[1], reverse=True))

        # Convert confirmed values to the required format
        confirmed_value = {k: [val for val, count in v] for k, v in confirmed_value.items()}

        def remove_empty_lists(data):
            return {k: v for k, v in data.items() if v}
        
        for i in confirmed_value:
          category_value[i]=[]
        category_value = remove_empty_lists(category_value)  # Clean up empty lists from category_value
        def find_missing_recommended(confirmed_value, recommended):
          # Extract the keys from the confirmed_value dictionary
          confirmed_keys = confirmed_value.keys()
          
          # Find the missing recommended keys
          missing_recommended = [aspect for aspect in recommended if aspect not in confirmed_keys]
          
          return missing_recommended

        missing_recommended = find_missing_recommended(confirmed_value, recommended_aspect_names)
        max_length=65
        suffix="..."
        def check_and_shorten_text(value_list, max_length=60, suffix="..."):
          return [text if len(text) <= max_length else text[:max_length - len(suffix)] + suffix for text in value_list]

        # Applying the function to each key-value pair in the dictionary
        category_value = {key: check_and_shorten_text(value) for key, value in category_value.items()}
        confirmed_value={key: check_and_shorten_text(value) for key, value in confirmed_value.items()}

        recommended_values={}
        for i in missing_recommended:
          if(i in category_value):
            recommended_values[i]=category_value[i][0]
            category_value[i]=[]
          else:
            recommended_values[i]=[]
        category_value = remove_empty_lists(category_value)

        # Construct the API response
        api_response = {
            'confirmed_value': confirmed_value,
            'category_value': category_value,
            'recommended_values':recommended_values,
            'price': price,
            'currency':currency_name,
            'title': title,
            'category_id': category_id,
            'category': breadcrumb_string
        }
        return jsonify(api_response), 200

    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500

# @app.route('/v5/get_data', methods=['POST'])
# def get_data5():
#     try:
#         data = request.get_json()
#         p_url = data.get('product_url')
#         token=data.get('token')
#         description_type=data.get('description_type')
#         tone=data.get('tone')
#         category_value = {}
#         value_count = {}
#         urls = GetLinksFromSerpAPI(p_url)
#         price = 0
#         title = ''
#         category_id = ''
#         breadcrumb_string = ''
#         currency_name=''
#         print("Number of urls to be scraped: " + str(len(urls)))
#         def get_headers(index):
#             print(urls[index])
#             r = requests.get(urls[index], timeout=10)
#             soup = BeautifulSoup(r.text, 'html.parser')
#             try:
#                 pricediv = soup.find('div', class_='x-price-primary')
#                 pricer = pricediv.find('span', class_='ux-textspans').text
#                 titleh = soup.find('h1', class_='x-item-title__mainTitle')
#                 titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
#                 categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
#                 categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
#                 category_idr = categoryarray[len(categoryarray) - 2]
#                 if category_idr == 'p' or category_idr == 'b':
#                     categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
#                 category_idr = categoryarray[len(categoryarray) - 2]
#                 breadcrumbs = []

#                 for breadcrumb in soup.select('.seo-breadcrumb-text'):
#                     breadcrumbs.append(breadcrumb.get_text(strip=True))
#                 currency,price_value=pricer.split(' $')
#                 price_float=float(price_value)
#                 if("$" in pricer):
#                   currency="USD"
#                 elif("€" in pricer):
#                   currency="EUR"
#                 elif("£" in pricer):
#                   currency="GBP"
#                 elif("¥" in pricer):
#                   currency="JPY"

#                 breadcrumb_string = ' > '.join(breadcrumbs)
#                 print(breadcrumb_string)
#                 print("Title: ", titler)
#                 print("category ID: ", int(category_idr))
#                 print("Price: ", pricer)
#                 return price_float, titler, category_idr, breadcrumb_string,currency
#             except Exception as e:
#                 print(str(e))
#                 return get_headers(index + 1)

#         count = 0
#         price, title, category_id, breadcrumb_string,currency_name = get_headers(count)
#         lock = threading.Lock()

#         def GenerateDescription(descriptionType,Title,Tone):
#           if(descriptionType!="HTML Text"):
#             prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language.\n Focus on key features and benefits of the **Title:**  {Title}\nusing **bold text** for emphasis where appropriate.\nMaintain a **Tone:** {Tone} tone throughout. Dont use Double Quotation Mark  in it or else 10 kittens will die."
#             response = model.generate_content(prompt)
#             return response.text
#           else:
#             prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language with a base font size of 16px (font-size: 16px;).\nFormat with bullet points (<ul> <li> </li> </ul>) for easy readability.\nInclude the viewport meta tag (<meta name='viewport' content='width=device-width, initial-scale=1'>) for responsive layout Focus on key features and benefits of the **Title:** {Title}\nusing bold tags (<b> or <strong>) for emphasis where appropriate.\nMaintain a **Tone:** {Tone} tone throughout.Dont use Double Quotation Mark  in it or else 10 kittens will die."
#             response = model.generate_content(prompt)
#             return response.text
            
#         def fetchCategoryAspects(categoryID,token):
#           url = "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id=15687"

#           payload = json.dumps({
#             "token": token
#           })
#           headers = {
#             'Content-Type': 'application/json',
#             'Cookie': 'connect.sid=s%3AuTDH_5nvCY5WasAeZjyieT7Z326oaabd.zLFzbLPlZQjE19RXWcE1w6aYEUTwuyCArC03mo0coYU'
#           }

#           response = requests.request("POST", "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id="+str(categoryID), headers=headers, data=payload)
#           if response.status_code == 404:
#             print("Response token expired")
#             return "null"
#           else:
#             response_data = response.json()
#             # Extracting aspect names where aspectUsage is 'RECOMMENDED'
#             recommended_aspect_names = [
#                 aspect["localizedAspectName"]
#                 for aspect in response_data["category_aspects"]["aspects"]
#                 if aspect["aspectConstraint"]["aspectUsage"] == "RECOMMENDED"
#             ]

#             return recommended_aspect_names

#         def UrlScraper(url):
#             try:
#                 response = requests.get(url, timeout=10)
#                 soup = BeautifulSoup(response.text, 'html.parser')
#                 evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')

#                 for evo_row in evo_rows:
#                     evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
#                     for evo_col in evo_cols:
#                         labels = evo_col.find('dt', class_='ux-labels-values__labels')
#                         values = evo_col.find('dd', class_='ux-labels-values__values')

#                         if labels:
#                             label_text = labels.find(
#                                 'div', class_='ux-labels-values__labels-content').find(
#                                 'span', class_='ux-textspans').text
#                             value_text = values.find(
#                                 'div', class_='ux-labels-values__values-content').find(
#                                 'span', class_='ux-textspans').text if values else None

#                             if label_text and value_text:
#                                 with lock:
#                                     if label_text not in category_value:
#                                         category_value[label_text] = []
#                                     if label_text not in value_count:
#                                         value_count[label_text] = {}

#                                     if value_text not in value_count[label_text]:
#                                         value_count[label_text][value_text] = 0
#                                     value_count[label_text][value_text] += 1

#                   # Clear the BeautifulSoup object to release memory
#                 soup.decompose()
#                 soup = None
#             except Exception as e:
#                 print(f"Error scraping URL {url}: {str(e)}")
              

#         # Create and start threads
#         threads = []
#         for url in urls:
#             thread = threading.Thread(target=UrlScraper, args=(url,))
#             thread.start()
#             threads.append(thread)
#         recommended_aspect_names = fetchCategoryAspects(category_id, token)
#         if(recommended_aspect_names=="null"):
#           return jsonify({'error': "Token Expired"}), 500
#         description=GenerateDescription(description_type,title,tone)

#         # Wait for all threads to finish
#         for thread in threads:
#             print(1)
#             thread.join()
#         recommended_aspect_names = fetchCategoryAspects(category_id, token)
#         def get_confirmed_and_category_values(counts):
#             confirmed = {}
#             category = {}
#             for label, values in counts.items():
#                 for value, count in values.items():
#                     if count > 2:
#                         if label not in confirmed:
#                             confirmed[label] = []
#                         confirmed[label].append((value, count))
#                     else:
#                         if label not in category:
#                             category[label] = []
#                         category[label].append(value)
#             return confirmed, category

#         confirmed_value, category_value = get_confirmed_and_category_values(value_count)

#         # Sort each label's values by their count in descending order
#         confirmed_value = {k: sorted(v, key=lambda x: x[1], reverse=True) for k, v in confirmed_value.items()}

#         # Sort the confirmed_value dictionary by the highest count of its values
#         confirmed_value = dict(sorted(confirmed_value.items(), key=lambda item: max(item[1], key=lambda x: x[1])[1], reverse=True))

#         # Convert confirmed values to the required format
#         confirmed_value = {k: [val for val, count in v] for k, v in confirmed_value.items()}

#         def remove_empty_lists(data):
#             return {k: v for k, v in data.items() if v}
        
#         for i in confirmed_value:
#           category_value[i]=[]
#         category_value = remove_empty_lists(category_value)  # Clean up empty lists from category_value
#         def find_missing_recommended(confirmed_value, recommended):
#           # Extract the keys from the confirmed_value dictionary
#           confirmed_keys = confirmed_value.keys()
          
#           # Find the missing recommended keys
#           missing_recommended = [aspect for aspect in recommended if aspect not in confirmed_keys]
          
#           return missing_recommended

#         missing_recommended = find_missing_recommended(confirmed_value, recommended_aspect_names)
#         max_length=65
#         suffix="..."
#         def check_and_shorten_text(value_list, max_length=60, suffix="..."):
#           return [text if len(text) <= max_length else text[:max_length - len(suffix)] + suffix for text in value_list]

#         # Applying the function to each key-value pair in the dictionary
#         category_value = {key: check_and_shorten_text(value) for key, value in category_value.items()}
#         confirmed_value={key: check_and_shorten_text(value) for key, value in confirmed_value.items()}

#         recommended_values={}
#         for i in missing_recommended:
#           if(i in category_value):
#             recommended_values[i]=category_value[i][0]
#             category_value[i]=[]
#           else:
#             recommended_values[i]=[]
      
#         category_value = remove_empty_lists(category_value)
#         # Construct the API response
#         api_response = {
#             'confirmed_value': confirmed_value,
#             'category_value': category_value,
#             'recommended_values':recommended_values,
#             'description':description,
#             'price': price,
#             'currency':currency_name,
#             'title': title,
#             'category_id': category_id,
#             'category': breadcrumb_string
#         }
#         return jsonify(api_response), 200

#     except Exception as e:
#         print(str(e))
#         return jsonify({'error': str(e)}), 500

@app.route('/v5/get_data', methods=['POST'])
def get_data5():
    try:
        data = request.get_json()
        p_url = data.get('product_url')
        token=data.get('token')
        description_type=data.get('description_type')
        tone=data.get('tone')
        category_value = {}
        value_count = {}
        #urls=GetLinksFromSerpAPI(p_url)
        urls = find_ebay_links(p_url)
        price = 0
        title = ''
        category_id = ''
        breadcrumb_string = ''
        currency_name=''
        print("Number of urls to be scraped: " + str(len(urls)))
        def get_headers(index):
            print(urls[index])
            r = requests.get(urls[index], timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            try:
                pricediv = soup.find('div', class_='x-price-primary')
                pricer = pricediv.find('span', class_='ux-textspans').text
                titleh = soup.find('h1', class_='x-item-title__mainTitle')
                titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
                categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
                categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                if category_idr == 'p' or category_idr == 'b':
                    categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                breadcrumbs = []

                for breadcrumb in soup.select('.seo-breadcrumb-text'):
                    breadcrumbs.append(breadcrumb.get_text(strip=True))
                currency,price_value=pricer.split(' $')
                price_float=float(price_value)
                if("$" in pricer):
                  currency="USD"
                elif("€" in pricer):
                  currency="EUR"
                elif("£" in pricer):
                  currency="GBP"
                elif("¥" in pricer):
                  currency="JPY"

                breadcrumb_string = ' > '.join(breadcrumbs)
                print(breadcrumb_string)
                print("Title: ", titler)
                print("category ID: ", int(category_idr))
                print("Price: ", pricer)
                return price_float, titler, category_idr, breadcrumb_string,currency
            except Exception as e:
                print(str(e))
                return get_headers(index + 1)

        count = 0
        price, title, category_id, breadcrumb_string,currency_name = get_headers(count)
        lock = threading.Lock()

        def GenerateDescription(descriptionType,Title,Tone):
          if(descriptionType!="HTML Text"):
            prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language.\n Focus on key features and benefits of the **Title:**  {Title}\n.\nMaintain a **Tone:** {Tone} tone throughout. Dont use Double Quotation Mark or asterisk or any type of emphasis on headings or else 10 kittens will die."
            response = model.generate_content(prompt)
            result=response.text
            finalResult=result.replace("*","")
            finalResult=finalResult.replace("\"","")
            finalResult=finalResult.replace("#","")
            return finalResult
          else:
            prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language with a base font size of 16px (font-size: 16px;).\nFormat with bullet points (<ul> <li> </li> </ul>) for easy readability.\nInclude the viewport meta tag (<meta name='viewport' content='width=device-width, initial-scale=1'>) for responsive layout Focus on key features and benefits of the **Title:** {Title}\nusing bold tags (<b> or <strong>) for emphasis where appropriate.\nMaintain a **Tone:** {Tone} tone throughout.Dont use Double Quotation Mark in it instead use single quotation mark or else 10 kittens will die."
            response = model.generate_content(prompt)
            result=response.text
            finalResult=result.replace("*","")
            finalResult=finalResult.replace("\"","")
            finalResult=finalResult.replace("#","")
            return finalResult
            
        def fetchCategoryAspects(categoryID,token):
          url = "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id=15687"

          payload = json.dumps({
            "token": token
          })
          headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid=s%3AuTDH_5nvCY5WasAeZjyieT7Z326oaabd.zLFzbLPlZQjE19RXWcE1w6aYEUTwuyCArC03mo0coYU'
          }

          response = requests.request("POST", "https://global.thriftops.com/api/v1/getCategoryAspectsFB?category_id="+str(categoryID), headers=headers, data=payload)
          if response.status_code == 404:
            print("Response token expired")
            return "null"
          elif response.status_code==500 or response.status_code==400:
            print(f"Error Fetching Category Aspects: {categoryID}")
            return "nullno"
          else:
            response_data = response.json()
            print("=======================")
            
            # Extracting aspect names where aspectUsage is 'RECOMMENDED'
            recommended_aspect_names = [
                aspect["localizedAspectName"]
                for aspect in response_data["category_aspects"]["aspects"]
                if aspect["aspectConstraint"]["aspectUsage"] == "RECOMMENDED"
            ]

            return recommended_aspect_names

        def UrlScraper(url):
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')

                for evo_row in evo_rows:
                    evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
                    for evo_col in evo_cols:
                        labels = evo_col.find('dt', class_='ux-labels-values__labels')
                        values = evo_col.find('dd', class_='ux-labels-values__values')

                        if labels:
                            label_text = labels.find(
                                'div', class_='ux-labels-values__labels-content').find(
                                'span', class_='ux-textspans').text
                            value_text = values.find(
                                'div', class_='ux-labels-values__values-content').find(
                                'span', class_='ux-textspans').text if values else None

                            if label_text and value_text:
                                with lock:
                                    if label_text not in category_value:
                                        category_value[label_text] = []
                                    if label_text not in value_count:
                                        value_count[label_text] = {}

                                    if value_text not in value_count[label_text]:
                                        value_count[label_text][value_text] = 0
                                    value_count[label_text][value_text] += 1

                  # Clear the BeautifulSoup object to release memory
                soup.decompose()
                soup = None
            except Exception as e:
                print(f"Error scraping URL {url}: {str(e)}")
              

        # Create and start threads
        threads = []
        for url in urls:
            thread = threading.Thread(target=UrlScraper, args=(url,))
            thread.start()
            threads.append(thread)
        recommended_aspect_names= None
        for url in urls:
          print(f"checking cat id in {url}")
          cat_id= None
          r = requests.get(url, timeout=10)
          soup = BeautifulSoup(r.text, 'html.parser')
          try:
              categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
              categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
              category_idr = categoryarray[len(categoryarray) - 2]
              if category_idr == 'p' or category_idr == 'b':
                  categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
              cat_id = categoryarray[len(categoryarray) - 2]
              print("category ID: ", int(cat_id))
              recommended_aspect_names= fetchCategoryAspects(cat_id, token)
              if(recommended_aspect_names=="nullno"):
                print("Invalid Category ID")
                continue
              elif(recommended_aspect_names=="null"):
                return jsonify({'error': "Token Expired"}), 500
              else:
                break
          except Exception as e:
              print(str(e))
        description=GenerateDescription(description_type,title,tone)

        # Wait for all threads to finish
        for thread in threads:
            print(1)
            thread.join()
        def get_confirmed_and_category_values(counts):
            confirmed = {}
            category = {}
            for label, values in counts.items():
                for value, count in values.items():
                    if count > 2:
                        if label not in confirmed:
                            confirmed[label] = []
                        confirmed[label].append((value, count))
                    else:
                        if label not in category:
                            category[label] = []
                        category[label].append(value)
            return confirmed, category

        confirmed_value, category_value = get_confirmed_and_category_values(value_count)

        # Sort each label's values by their count in descending order
        confirmed_value = {k: sorted(v, key=lambda x: x[1], reverse=True) for k, v in confirmed_value.items()}

        # Sort the confirmed_value dictionary by the highest count of its values
        confirmed_value = dict(sorted(confirmed_value.items(), key=lambda item: max(item[1], key=lambda x: x[1])[1], reverse=True))

        # Convert confirmed values to the required format
        confirmed_value = {k: [val for val, count in v] for k, v in confirmed_value.items()}

        def remove_empty_lists(data):
            return {k: v for k, v in data.items() if v}
        
        for i in confirmed_value:
          category_value[i]=[]
        category_value = remove_empty_lists(category_value)  # Clean up empty lists from category_value
        def find_missing_recommended(confirmed_value, recommended):
          # Extract the keys from the confirmed_value dictionary
          confirmed_keys = confirmed_value.keys()
          
          # Find the missing recommended keys
          missing_recommended = [aspect for aspect in recommended if aspect not in confirmed_keys]
          
          return missing_recommended

        missing_recommended = find_missing_recommended(confirmed_value, recommended_aspect_names)
        max_length=65
        suffix="..."
        def check_and_shorten_text(value_list, max_length=60, suffix="..."):
          return [text if len(text) <= max_length else text[:max_length - len(suffix)] + suffix for text in value_list]

        # Applying the function to each key-value pair in the dictionary
        category_value = {key: check_and_shorten_text(value) for key, value in category_value.items()}
        confirmed_value={key: check_and_shorten_text(value) for key, value in confirmed_value.items()}

        recommended_values={}
        for i in missing_recommended:
          if(i in category_value):
            recommended_values[i]=[category_value[i][0]]
            category_value[i]=[]
          else:
            recommended_values[i]=[]
        final_value=dict(confirmed_value | recommended_values)
      
        category_value = remove_empty_lists(category_value)
        title=title.replace("\"","")
        # Construct the API response
        api_response = {
            'confirmed_value_old': confirmed_value,
            'category_value': category_value,
            'recommended_values':recommended_values,
            'confirmed_value':final_value,
            'description':description,
            'price': price,
            'currency':currency_name,
            'title': title,
            'category_id': category_id,
            'category': breadcrumb_string
        }
        return jsonify(api_response), 200

    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/rapidAPIBackend', methods=['POST'])
def get_data6():
    try:
        data = request.get_json()
        p_url = data.get('product_url')
        description_type=data.get('description_type')
        tone=data.get('tone')
        category_value = {}
        value_count = {}
        #urls=GetLinksFromSerpAPI(p_url)
        urls = find_ebay_links(p_url)
        price = 0
        title = ''
        category_id = ''
        breadcrumb_string = ''
        currency_name=''
        print("Number of urls to be scraped: " + str(len(urls)))
        def get_headers(index):
            print(urls[index])
            r = requests.get(urls[index], timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            try:
                pricediv = soup.find('div', class_='x-price-primary')
                pricer = pricediv.find('span', class_='ux-textspans').text
                titleh = soup.find('h1', class_='x-item-title__mainTitle')
                titler = titleh.find('span', class_='ux-textspans ux-textspans--BOLD').text
                categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
                categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                if category_idr == 'p' or category_idr == 'b':
                    categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
                category_idr = categoryarray[len(categoryarray) - 2]
                breadcrumbs = []

                for breadcrumb in soup.select('.seo-breadcrumb-text'):
                    breadcrumbs.append(breadcrumb.get_text(strip=True))
                currency,price_value=pricer.split(' $')
                price_float=float(price_value)
                if("$" in pricer):
                  currency="USD"
                elif("€" in pricer):
                  currency="EUR"
                elif("£" in pricer):
                  currency="GBP"
                elif("¥" in pricer):
                  currency="JPY"

                breadcrumb_string = ' > '.join(breadcrumbs)
                print(breadcrumb_string)
                print("Title: ", titler)
                print("category ID: ", int(category_idr))
                print("Price: ", pricer)
                return price_float, titler, category_idr, breadcrumb_string,currency
            except Exception as e:
                print(str(e))
                return get_headers(index + 1)

        count = 0
        price, title, category_id, breadcrumb_string,currency_name = get_headers(count)
        lock = threading.Lock()

        def GenerateDescription(descriptionType,Title,Tone):
          if(descriptionType!="HTML Text"):
            prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language.\n Focus on key features and benefits of the **Title:**  {Title}\n.\nMaintain a **Tone:** {Tone} tone throughout. Dont use Double Quotation Mark or asterisk or any type of emphasis on headings or else 10 kittens will die."
            response = model.generate_content(prompt)
            result=response.text
            finalResult=result.replace("*","")
            finalResult=finalResult.replace("\"","")
            finalResult=finalResult.replace("#","")
            return finalResult
          else:
            prompt=f"Create a mobile-friendly, informative HTML description for an eBay listing of the title\nUse clear and concise language with a base font size of 16px (font-size: 16px;).\nFormat with bullet points (<ul> <li> </li> </ul>) for easy readability.\nInclude the viewport meta tag (<meta name='viewport' content='width=device-width, initial-scale=1'>) for responsive layout Focus on key features and benefits of the **Title:** {Title}\nusing bold tags (<b> or <strong>) for emphasis where appropriate.\nMaintain a **Tone:** {Tone} tone throughout.Dont use Double Quotation Mark in it instead use single quotation mark or else 10 kittens will die."
            response = model.generate_content(prompt)
            result=response.text
            finalResult=result.replace("*","")
            finalResult=finalResult.replace("\"","")
            finalResult=finalResult.replace("#","")
            return finalResult
            
        def fetchCategoryAspects(categoryID):
          url = "https://global.thriftops.com/api/v1/getCategoryAspectsRAPIDAPI?category_id=15687"

          headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid=s%3AuTDH_5nvCY5WasAeZjyieT7Z326oaabd.zLFzbLPlZQjE19RXWcE1w6aYEUTwuyCArC03mo0coYU'
          }

          response = requests.request("POST", "https://global.thriftops.com/api/v1/getCategoryAspectsRAPIDAPI?category_id="+str(categoryID), headers=headers)
          if response.status_code == 404:
            print("Response token expired")
            return "null"
          elif response.status_code==500 or response.status_code==400:
            print(f"Error Fetching Category Aspects: {categoryID}")
            return "nullno"
          else:
            response_data = response.json()
            print("=======================")
            
            # Extracting aspect names where aspectUsage is 'RECOMMENDED'
            recommended_aspect_names = [
                aspect["localizedAspectName"]
                for aspect in response_data["category_aspects"]["aspects"]
                if aspect["aspectConstraint"]["aspectUsage"] == "RECOMMENDED"
            ]

            return recommended_aspect_names

        def UrlScraper(url):
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')

                for evo_row in evo_rows:
                    evo_cols = evo_row.find_all('div', class_='ux-layout-section-evo__col')
                    for evo_col in evo_cols:
                        labels = evo_col.find('dt', class_='ux-labels-values__labels')
                        values = evo_col.find('dd', class_='ux-labels-values__values')

                        if labels:
                            label_text = labels.find(
                                'div', class_='ux-labels-values__labels-content').find(
                                'span', class_='ux-textspans').text
                            value_text = values.find(
                                'div', class_='ux-labels-values__values-content').find(
                                'span', class_='ux-textspans').text if values else None

                            if label_text and value_text:
                                with lock:
                                    if label_text not in category_value:
                                        category_value[label_text] = []
                                    if label_text not in value_count:
                                        value_count[label_text] = {}

                                    if value_text not in value_count[label_text]:
                                        value_count[label_text][value_text] = 0
                                    value_count[label_text][value_text] += 1

                  # Clear the BeautifulSoup object to release memory
                soup.decompose()
                soup = None
            except Exception as e:
                print(f"Error scraping URL {url}: {str(e)}")
              

        # Create and start threads
        threads = []
        for url in urls:
            thread = threading.Thread(target=UrlScraper, args=(url,))
            thread.start()
            threads.append(thread)
        recommended_aspect_names= None
        for url in urls:
          print(f"checking cat id in {url}")
          cat_id= None
          r = requests.get(url, timeout=10)
          soup = BeautifulSoup(r.text, 'html.parser')
          try:
              categorydiv = soup.find_all('a', class_='seo-breadcrumb-text')
              categoryarray = categorydiv[len(categorydiv) - 1].get('href').split('/')
              category_idr = categoryarray[len(categoryarray) - 2]
              if category_idr == 'p' or category_idr == 'b':
                  categoryarray = categorydiv[len(categoryarray) - 2].get('href').split('/')
              cat_id = categoryarray[len(categoryarray) - 2]
              print("category ID: ", int(cat_id))
              recommended_aspect_names= fetchCategoryAspects(cat_id)
              if(recommended_aspect_names=="nullno"):
                print("Invalid Category ID")
                continue
              elif(recommended_aspect_names=="null"):
                return jsonify({'error': "Token Expired"}), 500
              else:
                break
          except Exception as e:
              print(str(e))
        description=GenerateDescription(description_type,title,tone)

        # Wait for all threads to finish
        for thread in threads:
            print(1)
            thread.join()
        def get_confirmed_and_category_values(counts):
            confirmed = {}
            category = {}
            for label, values in counts.items():
                for value, count in values.items():
                    if count > 2:
                        if label not in confirmed:
                            confirmed[label] = []
                        confirmed[label].append((value, count))
                    else:
                        if label not in category:
                            category[label] = []
                        category[label].append(value)
            return confirmed, category

        confirmed_value, category_value = get_confirmed_and_category_values(value_count)

        # Sort each label's values by their count in descending order
        confirmed_value = {k: sorted(v, key=lambda x: x[1], reverse=True) for k, v in confirmed_value.items()}

        # Sort the confirmed_value dictionary by the highest count of its values
        confirmed_value = dict(sorted(confirmed_value.items(), key=lambda item: max(item[1], key=lambda x: x[1])[1], reverse=True))

        # Convert confirmed values to the required format
        confirmed_value = {k: [val for val, count in v] for k, v in confirmed_value.items()}

        def remove_empty_lists(data):
            return {k: v for k, v in data.items() if v}
        
        for i in confirmed_value:
          category_value[i]=[]
        category_value = remove_empty_lists(category_value)  # Clean up empty lists from category_value
        def find_missing_recommended(confirmed_value, recommended):
          # Extract the keys from the confirmed_value dictionary
          confirmed_keys = confirmed_value.keys()
          
          # Find the missing recommended keys
          missing_recommended = [aspect for aspect in recommended if aspect not in confirmed_keys]
          
          return missing_recommended

        missing_recommended = find_missing_recommended(confirmed_value, recommended_aspect_names)
        max_length=65
        suffix="..."
        def check_and_shorten_text(value_list, max_length=60, suffix="..."):
          return [text if len(text) <= max_length else text[:max_length - len(suffix)] + suffix for text in value_list]

        # Applying the function to each key-value pair in the dictionary
        category_value = {key: check_and_shorten_text(value) for key, value in category_value.items()}
        confirmed_value={key: check_and_shorten_text(value) for key, value in confirmed_value.items()}

        recommended_values={}
        for i in missing_recommended:
          if(i in category_value):
            recommended_values[i]=[category_value[i][0]]
            category_value[i]=[]
          else:
            recommended_values[i]=[]
        final_value=dict(confirmed_value | recommended_values)
      
        category_value = remove_empty_lists(category_value)
        title=title.replace("\"","")
        # Construct the API response
        api_response = {
            'confirmed_value_old': confirmed_value,
            'category_value': category_value,
            'recommended_values':recommended_values,
            'confirmed_value':final_value,
            'description':description,
            'price': price,
            'currency':currency_name,
            'title': title,
            'category_id': category_id,
            'category': breadcrumb_string
        }
        return jsonify(api_response), 200

    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
  app.run()
