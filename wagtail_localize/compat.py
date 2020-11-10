import os

if os.name == 'nt':
    # Windows has a different strftime format for dates without leading 0
    # https://stackoverflow.com/questions/904928/python-strftime-date-without-leading-0
    DATE_FORMAT = '%#d %B %Y'
else:
    DATE_FORMAT = '%-d %B %Y'
