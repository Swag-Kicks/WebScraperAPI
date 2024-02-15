from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import sql

app = Flask(__name__)


@app.route('/keep_alive', methods=['GET'])
def keep_alive():
  return 'Server is alive!'


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

    def checkAll():
      if any(value == '' for value in
             [brand, color, country, type, upc, material, model, price]):
        print("0")
        return False
      else:
        return True

    for url in urls:
      response = requests.get(url)
      soup = BeautifulSoup(response.text, 'html.parser')
      evo_rows = soup.find_all('div', class_='ux-layout-section-evo__row')
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

    # Construct the API response
    api_response = {
        'brand': brand,
        'color': color,
        'country': country,
        'type': type,
        'upc': upc,
        'material': material,
        'price': price,
        'model': model
    }  # taxanomy dictionary

    return jsonify(api_response), 200

  except Exception as e:
    return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
