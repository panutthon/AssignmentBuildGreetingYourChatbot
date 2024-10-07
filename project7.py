from flask import Flask, request
from linebot import LineBotApi
from linebot.models import FlexSendMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from neo4j import GraphDatabase

app = Flask(__name__)

# Initialize LineBotApi with your channel access token
line_bot_api = LineBotApi('rvVY90zi7+UL80fU6aQbDj+itnTfPGf+UXv5JyOLAgjxX6xpTzwGNkRAU8b901gGXLop3vOBCfXotyEvhxyYCqAOcuMWOh1x1gCuMDQSHJhiQDpZB1lp4CYIDVN/3hJLuBGMBgkMw7s+qDbONAqySAdB04t89/1O/w1cDnyilFU=')

# Connect to Neo4j
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Function to run Neo4j queries
def run_query(query, parameters):
    with driver.session() as session:
        result = session.run(query, parameters)
        return [record for record in result]

# Function to store chat history and keyword
def store_chat_history_and_keyword(user_id, user_message, bot_response, last_keyword, scraped_text=None):
    timestamp = datetime.now().isoformat()  # Create timestamp
    query = '''
    MERGE (u:User {user_id: $user_id})
    SET u.last_keyword = $last_keyword
    CREATE (m:Chat {user_message: $user_message, timestamp: $timestamp})
    CREATE (c:bot_response {bot_response: $bot_response, scraped_text: $scraped_text, timestamp: $timestamp})
    MERGE (u)-[:question]->(m)-[:answer]->(c)
    '''
    parameters = {
        'user_id': user_id,
        'user_message': user_message,
        'bot_response': bot_response,
        'scraped_text': scraped_text,
        'last_keyword': last_keyword,
        'timestamp': timestamp
    }
    run_query(query, parameters)

# Function to get the last keyword
def get_last_keyword(user_id):
    query = '''
    MATCH (u:User {user_id: $user_id})
    RETURN u.last_keyword AS last_keyword
    '''
    parameters = {'user_id': user_id}
    result = run_query(query, parameters)
    
    if result and result[0]['last_keyword']:
        return result[0]['last_keyword']
    return None

# Function to compute bot response
def compute_response(user_message):
    # This is a simple placeholder. You can modify this to make the response smarter.
    if "hello" in user_message.lower():
        return "Hi! How can I assist you today?"
    return "I'm here to help. What do you need?"

# Function to handle scraping from converse website
def scrape_converse(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    products_details = []
    products = soup.find_all("li", {"class": "item product product-item"})
    for product in products:
        name = product.find("strong", class_="product name product-item-name")
        price = product.find("span", class_="price")
        image_tag = product.find("img", class_="product-image-photo")
        image_url = image_tag['src'] if image_tag else 'No image found'

        link_tag = product.find("a", class_="product-item-link")
        product_url = link_tag['href'] if link_tag else 'No link found'

        products_details.append({
            'name': name.text.strip() if name else 'No title found',
            'price': price.text.strip() if price else 'No price found',
            'image_url': image_url,
            'product_url': product_url
        })
    return products_details

# Function to send Flex Message with product details
def send_flex_message(reply_token, products):
    if not products:
        text_message = TextSendMessage(text="No products found.")
        line_bot_api.reply_message(reply_token, text_message)
        return

    bubbles = [{
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": prod['image_url'],
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {
                "type": "uri",
                "uri": prod['product_url']
            }
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": prod['name'], "weight": "bold", "size": "md", "wrap": True},
                {"type": "text", "text": f"Price: {prod['price']}", "size": "sm", "color": "#999999"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#00C853",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "View Product",
                        "uri": prod['product_url']
                    }
                }
            ]
        }
    } for prod in products]

    contents = {"type": "carousel", "contents": bubbles}

    flex_message = FlexSendMessage(
        alt_text="Product List",
        contents=contents
    )

    line_bot_api.reply_message(
        reply_token,
        messages=[flex_message]
    )

# Function to handle Quick Reply for gender selection (for All Style)
def ask_gender_all_style(reply_token):
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="Men", text="Men for all style")),
        QuickReplyButton(action=MessageAction(label="Women", text="Women for all style")),
        QuickReplyButton(action=MessageAction(label="Unisex", text="Unisex for all style")),
    ])

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text="Please choose gender:", quick_reply=quick_reply)
    )

# Function to handle Quick Reply for gender selection (for Best Sellers, New Arrival, Exclusives)
def ask_gender(reply_token, category):
    if category == "new arrival":
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="Women", text="Women")),
            QuickReplyButton(action=MessageAction(label="Unisex", text="Unisex")),
        ])
    else:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="Men", text="Men")),
            QuickReplyButton(action=MessageAction(label="Women", text="Women")),
            QuickReplyButton(action=MessageAction(label="Unisex", text="Unisex")),
        ])

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text="Please choose gender:", quick_reply=quick_reply)
    )

# Function to handle style selection under ALL Style
def ask_style(reply_token):
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="Chuck 70", text="chuck 70")),
        QuickReplyButton(action=MessageAction(label="Classic Chuck", text="classic chuck")),
        QuickReplyButton(action=MessageAction(label="Sport", text="sport")),
        QuickReplyButton(action=MessageAction(label="Elevation", text="elevation")),
    ])

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text="Please choose a style:", quick_reply=quick_reply)
    )

# Function to handle the first Quick Reply for categories
def ask_category(reply_token):
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ALL Style", text="all style")),
        QuickReplyButton(action=MessageAction(label="Best Sellers", text="best sellers")),
        QuickReplyButton(action=MessageAction(label="New Arrival", text="new arrival")),
        QuickReplyButton(action=MessageAction(label="Exclusives", text="exclusives")),
    ])

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text="Please choose a category:", quick_reply=quick_reply)
    )

@app.route("/", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)
    try:
        json_data = json.loads(body)
        reply_token = json_data['events'][0]['replyToken']
        user_id = json_data['events'][0]['source']['userId']
        user_message = json_data['events'][0]['message']['text'].lower()

        # Compute bot response based on user message
        bot_response = compute_response(user_message)
        
        # Get the last keyword the user used
        last_keyword = get_last_keyword(user_id)
        
        # Global variable to store the final URL for scraping
        global final_url

        # URL map for styles in ALL Style
        style_url_map = {
            "chuck 70": "https://www.converse.co.th/chuck-70.html",
            "classic chuck": "https://www.converse.co.th/classic-chuck.html",
            "sport": "https://www.converse.co.th/sport.html",
            "elevation": "https://www.converse.co.th/women/shoes/platform.html"
        }

        # Handle first category selection
        if user_message == "all style":
            ask_style(reply_token)  # Ask user to select style under ALL Style

        # Handle style selection in ALL Style
        elif user_message in style_url_map:
            final_url = style_url_map[user_message]
            ask_gender_all_style(reply_token)  # Ask user to select gender for All Style

        # Handle gender selection for ALL Style
        elif user_message in ["men for all style", "women for all style", "unisex for all style"]:
            gender_map = {
                "men for all style": "?gender=62",
                "women for all style": "?gender=61",
                "unisex for all style": "?gender=63"
            }

            final_url = f"{final_url}{gender_map[user_message]}"
            products = scrape_converse(final_url)
            send_flex_message(reply_token, products)

        # Handle Best Sellers, New Arrival, Exclusives
        elif user_message == "best sellers":
            final_url = "https://www.converse.co.th/men/trending.html?cat=13"
            ask_gender(reply_token, "best sellers")
        elif user_message == "new arrival":
            final_url = "https://www.converse.co.th/men/trending.html?cat=14"
            ask_gender(reply_token, "new arrival")
        elif user_message == "exclusives":
            final_url = "https://www.converse.co.th/men/trending.html?cat=15"
            ask_gender(reply_token, "exclusives")

        # Handle gender selection for Best Sellers, New Arrival, Exclusives
        elif user_message in ["men", "women", "unisex"]:
            gender_map = {
                "men": "&gender=62",
                "women": "&gender=61",
                "unisex": "&gender=63"
            }

            final_url = f"{final_url}{gender_map[user_message]}"
            products = scrape_converse(final_url)
            send_flex_message(reply_token, products)

        # Store chat history and last keyword
        store_chat_history_and_keyword(user_id, user_message, bot_response, last_keyword)

    except Exception as e:
        print(f"Error processing the LINE event: {e}")

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000, debug=True)
