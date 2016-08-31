import urllib
from bs4 import BeautifulSoup

url = urllib.urlopen('http://www.amazon.com/reviews/iframe?akid=AKIAIIKM6BZG5RNDPK3A&alinkCode=xm2&asin=B000HBGGQ4&atag=collegeloan0f-20&exp=2016-08-31T16%3A19%3A41Z&v=2&sig=RIDysStjBjf1u3I8HHczyCyM3rAz435gTxWIozvxF1c%3D').read()
soup = BeautifulSoup(url)
reviews = soup.findAll('div', {'class':'reviewText'})
print reviews
