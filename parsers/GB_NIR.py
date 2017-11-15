#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime
from dateutil import parser, tz
from operator import itemgetter
import pandas as pd
import requests
from StringIO import StringIO

thermal_url = 'http://www.soni.ltd.uk/DownloadCentre/aspx/FuelMix.aspx'
wind_url = 'http://www.soni.ltd.uk/DownloadCentre/aspx/SystemOutput.aspx'
exchange_url = 'http://www.soni.ltd.uk/DownloadCentre/aspx/MoyleTie.aspx'
#Positive values represent imports to Northern Ireland.
#Negative value represent exports from Northern Ireland.


def get_data(url, session = None):
    """
    Requests data from a specified url in CSV format.
    Returns a response.text object.
    """

    s = session or requests.Session()

    headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
              }

    pagereq = requests.get(url, headers = headers)
    soup = BeautifulSoup(pagereq.text, 'html.parser')

    #Find and define parameters needed to send a POST request for the actual data.
    viewstategenerator = soup.find("input", attrs = {'id': '__VIEWSTATEGENERATOR'})['value']
    viewstate = soup.find("input", attrs = {'id': '__VIEWSTATE'})['value']
    eventvalidation = soup.find("input", attrs = {'id': '__EVENTVALIDATION'})['value']

    #Set date for post request.
    current_date = datetime.now().date()
    month = current_date.month
    day = current_date.day
    year = current_date.year

    FromDatePicker_clientState = '|0|01%s-%s-%s-0-0-0-0||[[[[]],[],[]],[{%s},[]],"01%s-%s-%s-0-0-0-0"]' % (year, month, day, '', year, month, day)
    ToDatePicker_clientState = '|0|01%s-%s-%s-0-0-0-0||[[[[]],[],[]],[{%s},[]],"01%s-%s-%s-0-0-0-0"]' % (year, month, day, '', year, month, day)
    btnDownloadCSV = 'Download+CSV'
    ig_def_dp_cal_clientState = '|0|15,2017,09,2017,%s,%s||[[null,[],null],[{%s},[]],"11,2017,09,2017,%s,%s"]' % (month, day, '', month, day)
    IG_CSS_LINKS_ = 'ig_res/default/ig_monthcalendar.css|ig_res/default/ig_texteditor.css|ig_res/default/ig_shared.css'

    postdata = {'__VIEWSTATE': viewstate,
                '__VIEWSTATEGENERATOR': viewstategenerator,
                '__EVENTVALIDATION': eventvalidation,
                'FromDatePicker_clientState': FromDatePicker_clientState,
                'ToDatePicker_clientState': ToDatePicker_clientState,
                'btnDownloadCSV': btnDownloadCSV,
                '_ig_def_dp_cal_clientState': ig_def_dp_cal_clientState,
                '_IG_CSS_LINKS_': IG_CSS_LINKS_
               }

    postheaders = {
                   'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0',
                   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                   'Content-Type': 'application/x-www-form-urlencoded'
                  }

    datareq = s.post(url, headers = postheaders, data = postdata)

    return datareq.text


def add_default_tz(timestamp):
    """
    Adds Northern Ireland timezone to datetime object if tz = None.
    """

    NIR = tz.gettz('Europe/Belfast')
    modified_timestamp = timestamp.replace(tzinfo = timestamp.tzinfo or NIR)

    return modified_timestamp


def create_thermal_df(text_data):
    """
    Turns thermal csv data into a usable dataframe.
    """

    cols_to_use = [0,1,2,3,4,5]
    df_thermal = pd.read_csv(StringIO(text_data.decode('utf-8')), usecols = cols_to_use)
    df_thermal.fillna(0.0, inplace = True)

    return df_thermal


def create_wind_df(text_data):
    """
    Turns wind csv data into a usable dataframe.
    """

    cols_to_use = [0,1]
    df_wind = pd.read_csv(StringIO(text_data.decode('utf-8')), usecols = cols_to_use)
    df_wind.fillna(0.0, inplace = True)

    return df_wind


def create_exchange_df(text_data):
    """
    Turns exchange csv data into a usable dataframe.
    """

    df_exchange = pd.read_csv(StringIO(text_data.decode('utf-8')))
    df_exchange.fillna(0.0, inplace = True)

    return df_exchange


def thermal_processor(df):
    """
    Creates quarter hour datapoints for thermal production.
    Returns a list.
    """

    datapoints = []
    for index, row in df.iterrows():
        snapshot = {}
        snapshot['datetime'] = row['TimeStamp']
        snapshot['gas'] = row['Gas_MW']
        snapshot['coal'] = row['Coal_MW']
        snapshot['oil'] = row['Distillate_MW'] + row['Diesel_MW']
        datapoints.append(snapshot)

    return datapoints


def wind_processor(df):
    """
    Creates quarter hour datapoints for wind production.
    Returns a list.
    """

    datapoints = []
    for index, row in df.iterrows():
        snapshot = {}
        snapshot['datetime'] = row['TimeStamp']
        snapshot['wind'] = row['Total_Wind_Generated_MW']
        if snapshot['wind'] > -20: snapshot['wind'] = max(snapshot['wind'], 0)
        datapoints.append(snapshot)

    return datapoints


def moyle_processor(df):
    """
    Creates quarter hour datapoints for GB exchange.
    Returns a list.
    """

    datapoints =[]
    for index, row in df.iterrows():
        snapshot = {}
        snapshot['datetime'] = add_default_tz(parser.parse(row['TimeStamp'], dayfirst=True))
        snapshot['netFlow'] = row['Total_Moyle_Load_MW']
        snapshot['source'] = 'soni.ltd.uk'
        snapshot['sortedCountryCodes'] = 'GB->GB-NIR'
        datapoints.append(snapshot)

    return datapoints


def IE_processor(df):
    """
    Creates quarter hour datapoints for IE exchange.
    Returns a list.
    """

    datapoints =[]
    for index, row in df.iterrows():
        snapshot = {}
        snapshot['datetime'] = add_default_tz(parser.parse(row['TimeStamp'], dayfirst=True))
        netFlow = row['Total_Str_Let_Load_MW'] + row['Total_Enn_Cor_Load_MW'] + \
                  row['Total_Tan_Lou_Load_MW']
        snapshot['netFlow'] = -1*(netFlow)
        snapshot['source'] = 'soni.ltd.uk'
        snapshot['sortedCountryCodes'] = 'GB-NIR->IE'
        datapoints.append(snapshot)

    return datapoints


def merge_production(thermal_data, wind_data):
    """
    Joins thermal and wind production data on shared datetime key.
    Returns a list.
    """

    total_production = thermal_data + wind_data

    #Join thermal and wind dicts on 'datetime' key.
    d = defaultdict(dict)
    for elem in total_production:
        d[elem['datetime']].update(elem)

    joined_data = sorted(d.values(), key=itemgetter("datetime"))

    for datapoint in joined_data:
        datapoint['datetime'] = add_default_tz(parser.parse(datapoint['datetime'], dayfirst=True))

    return joined_data


def fetch_production(country_code = 'GB-NIR', session = None):
    """
    Requests the last known production mix (in MW) of a given country
        Arguments:
        country_code (optional) -- used in case a parser is able to fetch multiple countries
        session (optional)      -- request session passed in order to re-use an existing session
        Return:
        A dictionary in the form:
        {
          'countryCode': 'FR',
          'datetime': '2017-01-01T00:00:00Z',
          'production': {
              'biomass': 0.0,
              'coal': 0.0,
              'gas': 0.0,
              'hydro': 0.0,
              'nuclear': null,
              'oil': 0.0,
              'solar': 0.0,
              'wind': 0.0,
              'geothermal': 0.0,
              'unknown': 0.0
          },
          'storage': {
              'hydro': -10.0,
          },
          'source': 'mysource.com'
        }
    """

    thermal_data = get_data(thermal_url)
    wind_data = get_data(wind_url)
    thermal_df = create_thermal_df(thermal_data)
    wind_df = create_wind_df(wind_data)
    thermal = thermal_processor(thermal_df)
    wind = wind_processor(wind_df)
    merge = merge_production(thermal, wind)

    production_mix_by_quarter_hour = []

    for datapoint in merge:
        production_mix = {
          'countryCode': country_code,
          'datetime': datapoint.get('datetime', 0.0),
          'production': {
              'coal': datapoint.get('coal', 0.0),
              'gas': datapoint.get('gas', 0.0),
              'oil': datapoint.get('oil', 0.0),
              'solar': None,
              'wind': datapoint.get('wind', 0.0)
          },
          'source': 'soni.ltd.uk'
        }
        production_mix_by_quarter_hour.append(production_mix)

    return production_mix_by_quarter_hour


def fetch_exchange(country_code1, country_code2, session = None):
    """Requests the last known power exchange (in MW) between two countries
    Arguments:
    country_code (optional) -- used in case a parser is able to fetch multiple countries
    session (optional)      -- request session passed in order to re-use an existing session
    Return:
    A dictionary in the form:
    {
      'sortedCountryCodes': 'DK->NO',
      'datetime': '2017-01-01T00:00:00Z',
      'netFlow': 0.0,
      'source': 'mysource.com'
    }
    """

    exchange_data = get_data(exchange_url)
    exchange_dataframe = create_exchange_df(exchange_data)
    if '->'.join(sorted([country_code1, country_code2])) == 'GB->GB-NIR':
        moyle = moyle_processor(exchange_dataframe)
        return moyle
    elif '->'.join(sorted([country_code1, country_code2])) == 'GB-NIR->IE':
        IE = IE_processor(exchange_dataframe)
        return IE
    else:
        raise NotImplementedError('This exchange pair is not implemented')


if __name__ == '__main__':
    """Main method, never used by the Electricity Map backend, but handy for testing."""

    print('fetch_production() ->')
    print(fetch_production())
    print('fetch_exchange(GB-NIR, GB) ->')
    print(fetch_exchange('GB-NIR', 'GB'))
    print('fetch_exchange(GB-NIR, IE) ->')
    print(fetch_exchange('GB-NIR', 'IE'))
