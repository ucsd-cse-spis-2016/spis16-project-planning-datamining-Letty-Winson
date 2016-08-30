from lxml import html
import requests

page = requests.get('http://www.amazon.com/reviews/iframe?akid=AKIAIIKM6BZG5RNDPK3A&alinkCode=xm2&asin=B000HBGGQ4&atag=collegeloan0f-20&exp=2016-08-31T16%3A19%3A41Z&v=2&sig=RIDysStjBjf1u3I8HHczyCyM3rAz435gTxWIozvxF1c%3D')
tree = html.fromstring(page.content)

#reviews = tree.xpath('/html/body/div[1]/div[3]/table/tr/td/div[1]/text()[7]')
reviews = tree.xpath('/html/body/div[1]/div[3]/table/tr/td/div[1]/div[6]/text()')

if __name__ == '__main__':
    print reviews
    '''
    children = reviews[0].getchildren()
    for child in children:
        print child.tag
'''
