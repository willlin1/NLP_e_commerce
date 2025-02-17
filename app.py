from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# 定義搜尋商品的函數
def search_momo(keyword):
    # 初始化 Selenium 驅動
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('User-Agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36"')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 設定搜尋網址
    url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={keyword}&cateLevel=0&_isFuzzy=0&searchType=1"
    
    # 打開 Momo 搜尋結果頁面
    driver.get(url)
    
    time.sleep(3)
    # 等待商品資料加載
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "goodsUrl")]'))
    )
    
    # 抓取商品資料
    products = driver.find_elements(By.XPATH, '//div[contains(@class, "goodsUrl")]')
    
    product_data = []
    for product in products:
            # 商品名稱
            name = product.find_element(By.XPATH, './/h3[@class="prdName"]').text
            # 商品價格
            price = product.find_element(By.XPATH, './/span[@class="price"]/b').text
            # 商品連結
            url = product.find_element(By.XPATH, './/a[@class="goods-img-url"]').get_attribute('href')
            # 商品圖片 URL
            image_url = product.find_element(By.XPATH, './/img[@class="prdImg"]').get_attribute('src')

            # 添加商品資料
            product_data.append({
                'name': name,
                'price': price,
                'url': url,
                'image': image_url
            })
    
    driver.quit()  # 關閉瀏覽器
    return product_data



# 處理搜尋請求
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    if keyword:
        # 抓取momo的搜尋結果
        products = search_momo(keyword)

        # 只取前三個商品
        top_four_products = products[:4]

        # 返回前三個商品
        return jsonify({'products': top_four_products})
    else:
        return jsonify({'error': '請提供搜尋關鍵字'})

if __name__ == '__main__':
    app.run(debug=True)
