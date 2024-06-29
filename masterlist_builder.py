# masterlist_builder.py
#
# By Oliver Barnes/Flurpbot
# constructs masterlist.csv from Backpack.tf data

from BackpackTF import Currency
import json
import requests
import urllib.parse
from statistics import mean
import time
import numpy as np
import pandas as pd
import datetime


# ========== SEARCH ==========
# values for search are inclusive - if you want specifics or exclusive ones, please edit the block where the search is processed
priceSearchCurrency = "keys"
priceSearchMin = 1
priceSearchMax = 2


# read in BPTF api key and token

f = open("keys.txt", "r")
keys = f.read().splitlines()
apikey = keys[0]
token = keys[1]
f.close()

api = Currency(apikey)
price = api.get_all_prices()
jprice = json.dumps(price["items"])

# read in price schema
f = open("prices.txt", "w")
f.write(jprice)
f.close()

# convert schema to json object
f = open("prices.txt", "r")
jprice = json.loads(f.read())

# item entry in json
print(jprice["Mann Co. Supply Crate Key"]["prices"])

qual = {}

g = open("quals.json", "r")
filters = json.load(g)

# build qual dict
for q in filters:
    qual[q["id"]] = q["name"]

# check that quals dict is correctly read
print(qual)

# function to convert quality id to string
# just used for ease of viz.
def id_to_qual(id):
    return qual[id]

# certain qual IDs have different attribs, causes schema problems
# 14, 15, 1, 13, 0, 9, 11, 6, 5, 3
exempt = ["14", "1", "13", "0", "9", "11", "6", "5", "3"]

# craft and uncraft are grouped in same sub-item entry

# list for item entries for new schema
pricedata = []

# for item name in pricelist
for item in jprice:

    # extract price info and subitems
    defIndex = jprice[item]["defindex"]
    itemInfo = jprice[item]["prices"]

    # for subitem (qualities and unu. effects)
    #
    # subitem format:
    # '6': {'Tradable': {'Craftable': [{'value': 1, 'currency': 'hat', 'difference': -0.33499999999999996, 'last_update': 1706136040, 'value_raw': 1.495}], 
    #       'Non-Craftable': [{'value': 4, 'currency': 'metal', 'difference': 1.4500000000000002, 'last_update': 1631802538, 'value_raw': 4}]}}, 
    for subitem in itemInfo:

        # check quality list before attempt to apply schema
        if (subitem in exempt):
            try:
                # extract price info from subitem
                subitemInfo = itemInfo[subitem]["Tradable"]

                # for subitem (qualities and unu. effects)
                #
                # subtype format:
                # 'Craftable': [{'value': 1, 'currency': 'hat', 'difference': -0.33499999999999996, 'last_update': 1706136040, 'value_raw': 1.495}]
                for subtype in subitemInfo:
                    subtypeInfo = subitemInfo[subtype]

                    # dat is a single data object defining a subtype of a subitem
                    # this is how a price for "Unique Non-Craftable Frontier Justice" is extracted 
                    dat = []

                    # defindex added to schema for classified processing and SKU use
                    #dat.append(defIndex)
                    # qual id added to schema for classified processing and SKU use
                    dat.append(subitem)
                    # plaintext quality stored for viz
                    dat.append(id_to_qual(subitem))
                    # subtype (craft/uncraft label)
                    dat.append(subtype)
                    # item name
                    dat.append(item)
                    # item value
                    dat.append(subtypeInfo[0]["value"])
                    # currency
                    dat.append(subtypeInfo[0]["currency"])                    
                    # last price update (epoch timestamp)
                    dat.append(subtypeInfo[0]["last_update"])

                    # print statement for debug
                    #print(dat)
                    pricedata.append(dat)
                    
            except:
                print("DEBUG: Unusual effect recognized as item type... skipping.")

pricelist = pd.DataFrame(pricedata, columns=["qualityID", "quality", "craft", "name", "value", "currency", "lastUpdate"])

pricesearch = pricelist.loc[(pricelist["currency"] == priceSearchCurrency) & (pricelist["value"] >= priceSearchMin) & (pricelist["value"] <= priceSearchMax)]

appid = 440

# function for retrieving classifieds data
# loosely based on the BackpackTF Account module: pypi.org/project/BackpackTF/
# uses new "/classifieds/listings/snapshot" request

# returns a json of classifieds listings

# args:
# apikey - client api key
# token - client token
# sku - Backpack.tf item SKU - the title for the item page
# appid - steam app id - TF2 = 440

# returns:
# jsondata - JSON response containing classified listing data
def classifieds_snapshot(
    apikey,
    token,
    sku,
    appid
):
        payload = {
            "key": apikey,
            "token": token,
            "sku": sku,
            "appid": appid
        }

        encoded = urllib.parse.urlencode(payload)

        r = requests.get("https://backpack.tf/api/classifieds/listings/snapshot?" + encoded)
        jsondata = json.loads(r.text)

        return jsondata

# function for creating searchable SKU to pass to classifieds_snapshot

# args:
# item - df object containing needed item data

# returns:
# df - df with sku column
def get_sku(
    df
):
    df.loc[(df["qualityID"] == "6") & (df["craft"] == "Craftable"), 'sku'] = df["name"]
    df.loc[(df["qualityID"] == "6") & (df["craft"] != "Craftable"), 'sku'] = df["craft"] + " " + df["name"]
    df.loc[(df["qualityID"] != "6") & (df["craft"] == "Craftable"), 'sku'] = df["quality"] + " " + df["name"]
    df.loc[(df["qualityID"] != "6") & (df["craft"] != "Craftable"), 'sku'] = df["craft"] + " " + df["quality"] + " " + df["name"]
    
    return df

keyprice = jprice["Mann Co. Supply Crate Key"]["prices"]["6"]["Tradable"]["Craftable"][0]["value"]
refprice = 0.018

# return the set of classified listings for a given item
#
# params:
# sku - item sku
#
# returns:
# 
def getClassifiedListings(sku):
    appid = 440
    listings = classifieds_snapshot(apikey, token, sku, appid)["listings"]
    
    sells = []
    buys = []
    sellAge = []
    
    for listing in listings:
        totalval = 0
            
        # currencies must be iterated as multiple currency types can me attached to one price
        # TODO: cast currencies to metal using actual prices - pull from api
        priceInfo = listing["currencies"]
        for currency in priceInfo:
            if currency == "keys":
                totalval += priceInfo[currency] * keyprice
            elif currency == "usd":
                totalval += priceInfo[currency] / refprice
            elif currency == "hat":
                totalval += 1.22
            else:
                totalval += priceInfo[currency]
        
        if listing["intent"] == "sell":
            sells.append(totalval)

            age = listing["bump"] - listing["timestamp"]

            if (age > 30000):
                sellAge.append(age)
            else:
                sellAge.append(3600000)
        else:
            buys.append(totalval)

    
    sellsByPrice = sorted(sells,key=lambda x: x)
    sellLowest = sellsByPrice[0]

    # volume calculation is len(sells) * 1000/ avg(listing age)
    
    sellVol = round((10000000 / ((1 + abs(len(sells) - len(buys)))  * mean(sellAge))), 3)
    
    # buy listings with over 110% value of lowest sell need eliminating from the set

    realBuys = [i for i in buys if i <= (1.1 * sellLowest)]
    
    buysByPrice = sorted(realBuys,key=lambda x: x, reverse=True)
    buyHighest = buysByPrice[0]
    
    priceGap = sellLowest - buyHighest
    priceGap = round(priceGap, 2)
    
    return ([sku, priceGap, sellVol])

data = []

for index, row in get_sku(pricesearch).iterrows():
    time.sleep(1)
    try:
        classifieds = getClassifiedListings(row['sku'])
        data.append(classifieds)
    except:
        try:
            classifieds = getClassifiedListings("The " + row['sku'])
            data.append(classifieds)
        except:
            print("price data unavailable for " + row['sku'])

df = pd.DataFrame(data, columns =['sku', 'pricegap', 'vol']) 
df['fitness'] = (np.log2(df['pricegap'])) * df['vol']
outFileName = "masterlist.csv"
df.to_csv(outFileName, index=False)

x = datetime.datetime.now()

currentdate = x.strftime("%y%m%d%H%M") 

outFileName = "./history/" + str(priceSearchMin) + "-" + str(priceSearchMax) + priceSearchCurrency + currentdate + ".csv"
df.to_csv(outFileName, index=False)