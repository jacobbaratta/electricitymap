# The arrow library is used to handle datetimes
import arrow
import urllib
# The request library is used to fetch content through HTTP
import requests
from os import environ
from parsers.lib.exceptions import ParserException


def fetch_exchange(country_code1='ES', country_code2='MA', session=None, token=None):

    ## Get ESIOS token
    token = environ.get('ESIOS_TOKEN', token)
    if not token:
        raise ParserException("ESIOS", "Require access token")

    ses = session or requests.Session()

    ## Request headers
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json; application/vnd.esios-api-v2+json',
               'Authorization': 'Token token="{0}"'.format(token)}

    ## Request query url
    utc = arrow.utcnow()
    start_date = utc.shift(hours=-24).floor('hour').isoformat()
    end_date = utc.ceil('hour').isoformat()
    dates = {'start_date': start_date, 'end_date': end_date}
    query = urllib.urlencode(dates)
    url = 'https://api.esios.ree.es/indicators/10209?{0}'.format(query)

    response = ses.get(url, headers=headers)
    if response.status_code != 200 or not response.text:
        raise ParserException('ESIOS', 'Response code: {0}'.format(response.status_code))

    json = response.json()
    values = json['indicator']['values']
    if not values:
        raise ParserException('ESIOS', 'No values received')
    else:
        data = []
        sorted_country_codes = sorted([country_code1, country_code2])

        for value in values:
            # Get last value in datasource
            datetime = arrow.get(value['datetime_utc']).datetime
            # Datasource negative value is exporting, positive value is importing
            net_flow = -value['value']

            value_data = {
                'sortedCountryCodes': '->'.join(sorted_country_codes),
                'datetime': datetime,
                'netFlow': net_flow if country_code1 == sorted_country_codes[0] else -1 * net_flow,
                'source': 'api.esios.ree.es',
            }

            data.append(value_data)

        return data


if __name__ == '__main__':
    session = requests.Session()
    print fetch_exchange('ES', 'MA', session)