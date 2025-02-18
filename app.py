from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

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

        # 返回所有商品（不只四個）
        return jsonify({'products': products})
    else:
        return jsonify({'error': '請提供搜尋關鍵字'})

# 設定 Chrome 瀏覽器選項
def configure_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 如果不需要顯示瀏覽器，可以啟用這行
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('User-Agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36"')
    return chrome_options

# 初始化 WebDriver
def initialize_driver():
    chrome_options = configure_chrome_options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# 訪問網頁並抓取評論資料
def fetch_comments(driver, url):
    driver.get(url)
    
    # 點擊商品評價按鈕
    review_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'goodsCommendLi')]//span"))
    )
    driver.execute_script("arguments[0].click();", review_button)  # 使用 JavaScript 點擊

    time.sleep(3)
    # 獲取總頁數
    page_number_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.pageArea span:nth-child(2)'))
    )
    # 使用正則表達式提取總頁數
    total_pages_match = re.search(r'(\d+)/(\d+)', page_number_element.text)
    
    total_pages = int(total_pages_match.group(2))
    
    # 初始化評論和評分資料
    comments_data = []

    # 抓取評論和評分
    def grab_comments_from_page():
        # 等待評論加載
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.reviewCard'))
        )

        # 抓取評論
        comments = driver.find_elements(By.CSS_SELECTOR, 'div.reviewCardInner div.CommentContainer:not(.ReplyContainer .CommentContainer) p.Comment')
        for comment in comments:
            comments_data.append(comment.text)     

    # 抓取第一頁評論
    grab_comments_from_page()

    # 抓取剩餘頁面評論
    for page in range(2, total_pages + 1):
        # **修正 XPath 來選擇分頁按鈕**
        next_page_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//dd[@pageidx='{page}']/a"))
        )
    
        # **確保按鈕可以被點擊**
        driver.execute_script("arguments[0].click();", next_page_button)


        # 等待評論加載並抓取評論與評分
        grab_comments_from_page()

    # 格式化資料
    comments_data = [[comment] for comment in comments_data]

    return comments_data

@app.route('/get_comments', methods=['POST'])
def get_comments():
    data = request.json
    product_url = data.get("url")

    if not product_url:
         return jsonify({"error": "缺少商品網址"}), 400

    driver = initialize_driver()
    comments = fetch_comments(driver, product_url)
    driver.quit()
    
    return jsonify({"comments": comments[:5]})

if __name__ == '__main__':
    app.run(debug=True)
