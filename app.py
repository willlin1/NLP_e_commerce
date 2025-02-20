from flask import Flask, request, jsonify, render_template, send_file
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import torch
from transformers import BertForSequenceClassification, BertTokenizer
import joblib
import matplotlib.pyplot as plt
import io
import base64

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

model_path = './results'
model = BertForSequenceClassification.from_pretrained(model_path)
tokenizer = BertTokenizer.from_pretrained(model_path)
# 加載儲存的 LabelEncoder
label_encoder = joblib.load('label_encoder.pkl')

def analyze_sentiment(text, model, tokenizer, label_encoder):
    # 設定裝置為 CPU
    device = torch.device("cpu")  # 設定裝置為 CPU

    # 移動模型到指定的裝置（這裡是 CPU）
    model = model.to(device)

    # 使用 tokenizer 對文本進行編碼
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128)

    # 將輸入張量移動到相同的裝置
    inputs = {key: value.to(device) for key, value in inputs.items()}

    # 禁用梯度計算，進行推理
    with torch.no_grad():
        outputs = model(**inputs)

    # 預測的類別
    predicted_class = torch.argmax(outputs.logits, dim=1)

    # 從 CPU 移動 predicted_class 並轉換為 NumPy 陣列
    predicted_class_cpu = predicted_class.numpy()

    # 使用 label_encoder 解碼為原始標籤
    predicted_label = label_encoder.inverse_transform(predicted_class_cpu)

    sentiment_map = {0: 'bad', 1: 'good', 2: 'neutral'}
    sentiment = sentiment_map[predicted_class_cpu[0]]  # 使用映射將數字轉換為對應的情感標籤

    return sentiment


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
    try:
        page_number_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.pageArea span:nth-child(2)'))
        )
        # 使用正則表達式提取總頁數
        total_pages_match = re.search(r'(\d+)/(\d+)', page_number_element.text)
        
        total_pages = int(total_pages_match.group(2))
    except Exception as e:
        return []
    
    # 初始化評論資料
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

    # 使用情感分析模型處理評論
    analyze_comments = []
    sentiment_count = {"good": 0, "bad": 0, "neutral": 0}
    
    for comment in comments_data:
        sentiment = analyze_sentiment(comment[0],  model, tokenizer, label_encoder)
        analyze_comments.append({"comment": comment[0], "sentiment": sentiment})

    for comment in analyze_comments:
        sentiment = comment['sentiment']
        sentiment_count[sentiment] += 1

    # 產生圓餅圖
    fig, ax = plt.subplots()
    ax.pie(sentiment_count.values(), labels=sentiment_count.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # 使圓餅圖為圓形

     # 保存圓餅圖為圖片，然後轉換為 base64 編碼
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)  # 重設指標到圖片的起始位置
    img_base64 = base64.b64encode(img_stream.getvalue()).decode('utf-8')

    return analyze_comments, img_base64

@app.route('/get_comments', methods=['POST'])
def get_comments():
    data = request.json
    product_url = data.get("url")

    if not product_url:
         return jsonify({"error": "缺少商品網址"}), 400

    driver = initialize_driver()
    analyzed_comments, pie_chart_base64 = fetch_comments(driver, product_url)
    driver.quit()

    return jsonify({
        "comments": analyzed_comments[:5],
        "pie_chart": pie_chart_base64
    })



if __name__ == '__main__':
    app.run(debug=True)
