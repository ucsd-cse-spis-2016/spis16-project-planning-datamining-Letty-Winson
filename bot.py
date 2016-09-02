'''Search subreddits for product keywords and suggest related items from Amazon'''

import math, random, time, re, sys, praw, ConfigParser, urllib2, itertools, numpy, pandas, sqlite3
from amazon.api import AmazonAPI
from bs4 import BeautifulSoup

def main():
    #Read setup, Reddit, and Amazon configurations from config.ini
    config = ConfigParser.ConfigParser()
    config.read("config.ini")
    NUM_RETRIEVE = int(config.get("setup", "NUM_RETRIEVE")) #Number of submissions to retrieve from "New" in each subreddit
    MIN_CONFIDENCE = int(config.get("setup", "MIN_CONFIDENCE")) #Minimum confidence to reply to keyword call
    SENTENCES_IN_REPLY = int(config.get("setup", "SENTENCES_IN_REPLY")) #Maximum number of sentences in reply
    SLEEP_TIME = int(config.get("setup", "SLEEP_TIME")) #Time between pulls, in seconds
    USERNAME = config.get("praw", "USERNAME")
    PASSWORD = config.get("praw", "PASSWORD")
    USER_AGENT = config.get("praw", "USER_AGENT")
    AMAZON_KEY = config.get("amazon", "AMAZON_KEY")
    AMAZON_SECRET = config.get("amazon", "AMAZON_SECRET")
    AMAZON_ASSOCIATE = config.get("amazon", "AMAZON_ASSOCIATE")

    #Initialize variables
    global keywords, c
    alreadyReplied = [] #Users and submissions that have already been replied to
    keywords = pandas.read_csv('data.csv') #Items, suggestives, blacklist, subreddits
    conn = sqlite3.connect('templates.db') #Sentence templates (brand, category, price, link)
    c = conn.cursor()
    subreddits = "+".join([line.strip() for line in keywords['subreddits'].dropna()])

    #Connect to Reddit and Amazon
    r = praw.Reddit(USER_AGENT)
    r.login(USERNAME, PASSWORD, disable_warning=True)
    amazon = AmazonAPI(AMAZON_KEY, AMAZON_SECRET, AMAZON_ASSOCIATE)

    while True:
        submissions = r.get_subreddit(subreddits)
        #Get 'NUM_RETRIEVE' newest submissions from subreddits
        for i in submissions.get_new(limit=NUM_RETRIEVE):
            try:
                if str(i.author) in alreadyReplied:
                    raise ValueError('SKIPPING: ALREADY REPLIED TO AUTHOR')
                if 'reddit.com' not in i.url:
                    raise ValueError('SKIPPING: LINK SUBMISSION')

                #Amazon link in submission (self) text
                str_self = i.selftext.encode('utf-8').lower()
                if  ('/dp/' in str_self) or ('/gp/' in str_self):
                    productData = find_in_amazon(amazon, AMAZON_ASSOCIATE, amazon.similarity_lookup(ItemId=get_ASIN(str_self))[0])
                    if type(productData) is dict:
                        print "FOUND", productData['link'], "IN SELF:", i.id
                        alreadyReplied.append(str(i.author)) #Add username to cache
                        print ""
                        print generate_Comment(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews'])
                        i.add_comment(generate_Comment(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews']))
                        print ""
                        raise ValueError('SKIPPING: DONE REPLYING')
                    elif type(productData) is str:
                        print productData #Error

                #Amazon link in comment
                for comment in i.comments:
                    str_comment = str(comment).lower()
                    if  (str(comment.author) not in alreadyReplied) and (('/dp/' in str_comment) or ('/gp/' in str_comment)):
                        productData = find_in_amazon(amazon, AMAZON_ASSOCIATE, amazon.similarity_lookup(ItemId=str(get_ASIN(str_comment)))[0])
                        if type(productData) is dict:
                            print "FOUND", productData['link'], "IN COMMENT", comment.id
                            alreadyReplied.append(str(i.author)) #Add username to cache
                            alreadyReplied.append(str(comment.author)) #Add username to cache
                            print ""
                            print generate_amazonCommentReply(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews'])
                            comment.reply(generate_amazonCommentReply(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews']))
                            print ""
                            raise ValueError('SKIPPING: DONE REPLYING')
                        elif type(productData) is str:
                            print productData #Error

                #Item keyword in title
                for word in keywords['items'].dropna(): #Scan matches between 'items' and title
                    if word.lower() in i.title.encode('utf-8').lower(): #Only reply if match found and confidence is high that a suggestion is advised
                        if calculate_confidence(i) >= MIN_CONFIDENCE:
                            productData = find_in_amazon(amazon, AMAZON_ASSOCIATE, amazon.search_n(1, Keywords=word, SearchIndex='All')[0])
                            if type(productData) is dict:
                                print "FOUND", word, "IN TITLE", i.id
                                alreadyReplied.append(str(i.author)) #Add username to cache
                                productData['category'] = word #'word' is more relevant than the default category
                                print ""
                                print generate_Comment(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews'])
                                i.add_comment(generate_Comment(SENTENCES_IN_REPLY, productData['link'], productData['brand'], str(productData['category']).lower(), productData['price'], productData['features'], productData['reviews']))
                                print ""
                                raise ValueError('SKIPPING: DONE REPLYING')
                            elif type(productData) is str:
                                print productData #Error
                #Let sprinkle some crack on'em and get outta here
                raise ValueError('SKIPPING: NOTHING FOUND')

            except KeyboardInterrupt:
                raise
            except ValueError as err:
                print err
            except:
                print sys.exc_info()[0]
        print 'SLEEPING FOR', SLEEP_TIME, 'SECONDS...'
        time.sleep(SLEEP_TIME)

def find_in_amazon(amazon, associate, product):
    #Find product in Amazon and return product data
    opener = urllib2.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.117 Safari/537.36')] #Can't stop me
    reviews = []
    features = []
    try:
        reviews.extend((BeautifulSoup(product.editorial_review, "lxml").get_text().encode('ascii','ignore')).split('.')) #Scrape editorial reviews
        customer = BeautifulSoup(opener.open(product.reviews[1]).read(), "lxml").findAll('div', {'class':'reviewText'}) #Scrape customer reviews
        for i in range(len(customer)):
            reviews.extend(customer[i].get_text().encode('ascii','ignore').split('.')) #Add customer reviews

    except:
        print 'ERROR: PROBLEM FETCHING REVIEW'

    try:
        productData = {}

        #Create Amazon link with shortened title
        if ',' in product.title:
            link = "[" + product.title[:product.title.index(',')] + "](https://amzn.com/dp/" + product.asin + "/?tag=" + associate + ")"
        else:
            link = "[" + product.title + "](https://amzn.com/dp/" + product.asin + "/?tag=" + associate + ")"

        #Remove review sentences that contain blacklisted keywords
        for word in keywords['blacklist'].dropna():
            reviews = [x for x in reviews if not word in x]
            features = [x for x in features if not word in x]

        productData['brand'] = product.brand
        productData['category'] = product.browse_nodes[len(product.browse_nodes)-1].name
        productData['features'] = features
        productData['price'] = '$' + str(int(math.ceil(max(product.price_and_currency[0],product.list_price[0]) / 10.0) * 10.0)) #Round up to the nearest $10 (so that we can say the product is "less than $x0")
        productData['reviews'] = reviews
        productData['link'] = link
        return productData
    except:
        return 'PRODUCT NOT FOUND'

def get_ASIN(str_comment):
    #Find ASIN and return it
    if '/dp/' in str_comment:
        start_index = str_comment.find('/dp/') + 4
    elif '/gp/product/' in str_comment:
        start_index = str_comment.find('/gp/') + 12
    else:
        start_index = str_comment.find('/gp/') + 9
    asin = str_comment[start_index:start_index+10]
    return asin

def calculate_confidence(submission):
    #Calculate confidence in the fact that an Amazon suggestion is advised by considering the number of matches with keywords in 'suggestives'
    confidence = 0
    for word in keywords['suggestives'].dropna():
        if word.lower() in submission.title.encode('utf-8').lower():
            confidence += 3
        if word.lower() in submission.selftext.encode('utf-8').lower():
            confidence += 2
        for comment in submission.comments:
            if word.lower() in str(comment).lower():
                confidence += 1
    return confidence

def random_String(tableName, columnName):
    #Select a random template string from a specific column (brand, category, price, link)
    numColumns = c.execute('SELECT COUNT(*) FROM {tn}'.\
                format(tn=tableName)).fetchone()[0]
    c.execute('SELECT {cn} FROM {tn} WHERE id={sentenceId}'.\
            format(cn=columnName, tn=tableName, sentenceId=random.randint(1,numColumns)))
    return c.fetchone()[0]

def generate_amazonCommentReply(length, link, brand, category, price, features, reviews):
    #Generate a comment with the first sentence as a reply
    return random_String('amazonCommentReply', 'badProduct') + generate_Comment(length, link, brand, category, price, features, reviews)

def generate_Comment(length, link, brand, category, price, features, reviews):
    #Generate a random comment between the length of 3 and SENTENCES_IN_REPLY sentences, with mentions of link, brand, category, price, reviews, and features
    commentList = []
    for i in itertools.chain([(random_String('topLevelReply', 'link')).format(link),
    (random_String('topLevelReply', 'brand')).format(brand),
    (random_String('topLevelReply', 'category')).format(category),
    (random_String('topLevelReply', 'price')).format(price)],
    (j for j in random.sample(reviews, min(3,len(reviews)))), #Add 0-3 reviews
    (('This ' + k.lower() + '. ') for k in random.sample(features, min(2,len(features))))): #Add 0-2 features
        commentList.append(i)
    return commentList[0] + ' '.join(random.sample(commentList[1:], random.randint(3,length- 1))) + ' (sorry for the typos, english is my second language)' #Python is my first language.

if __name__ == '__main__':
    main()
