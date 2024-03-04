from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import sql
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)


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
            if 'ebay' in link:
                ebay_links.append(link)


        return ebay_links
    except:
        print("Error:")
        return []


@app.route('/get_product_data', methods=['POST'])
def get_product_data():
  try:
    # Get the product URL from the request
    data = request.get_json()
    p_url = data.get('product_url')
    category_aspects=data.get('aspects')
    category_value={}
    urls=GetLinksFromSerpAPI(p_url)
      
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
        'category_value': category_value
    }  # taxanomy dictionary

    return jsonify(api_response), 200

  except Exception as e:
    print(str(e))
    return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
  app.run()
