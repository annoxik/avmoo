#!/usr/bin/env python3

"""
Get proxies from some free proxy sites.

Cron:
    0 * * * * /home/ubuntu/proxy.py -l

"""
import gevent
from gevent import monkey

monkey.patch_all()

from gevent.pool import Pool

import os
import requests
import datetime
import re
import logging
import random
import sys

from logging.handlers import RotatingFileHandler
from time import time, sleep
from bs4 import BeautifulSoup
from peewee import MySQLDatabase, CharField, DateTimeField, Model, FloatField, BooleanField, IntegrityError
from avmoo import int2mid

# http request headers
headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'Accept': 'text / html, application / xhtml + xml, application / xml;'
              'q = 0.9, image / webp, * / *;q = 0.8',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Ubuntu Chromium/48.0.2564.116 Chrome/48.0.2564.116 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'en-US,en;q=0.8,zh-CN;q=0.6,zh;q=0.4,zh-TW;q=0.2',
    'Cookie': '__cfduid=dc8923d6d41cddd5038668885a97b61a11458400017; '
              'AD_enterTime=1458400024; AD_juic_j_L_728x90=0; AD_wav_j_L_728x90=0; AD_exoc_j_POPUNDER=1;'
              ' AD_clic_j_POPUNDER=2; AD_adst_j_POPUNDER=1; AD_traf_j_POPUNDER=1; AD_exoc_j_L_728x90=4; '
              'AD_exoc_j_M_728x90=4; AD_javu_j_L_728x90=2; AD_juic_j_M_728x90=1; '
              'AD_bts_j_P_728x90=5; _gat=1; _ga=GA1.2.2125902479.1458400018'
}

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:45.0) Gecko/20100101 Firefox/45.0',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36 OPR/36.0.2130.32',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 UBrowser/5.6.10551.6 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 4.4.4; HTC D820mt Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.91 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 5.0; Google Nexus 5 - 5.0.0 - API 21 - 1080x1920 Build/LRX21M) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/37.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/48.0.2564.116 Chrome/48.0.2564.116 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:45.0) Gecko/20100101 Firefox/45.0'
]

# # logging config
logging.getLogger("requests").setLevel(logging.WARNING)

log_file = os.path.join(os.path.expanduser("~"), 'proxy.log')
handler = RotatingFileHandler(log_file, mode='a', maxBytes=50 * 1024 * 1024, backupCount=2)
handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
handler.setLevel(logging.INFO)

logger = logging.getLogger('root')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# database
db = MySQLDatabase(database='proxies', user='root', password='19961020')

using_logger = False


class Proxy(Model):
    proxy = CharField(primary_key=True)
    check_time = DateTimeField(null=True)
    response_time = FloatField(null=True)
    available = BooleanField(null=True)

    class Meta:
        database = db


def store_in_db(proxy, escaped=None, status_code=403, is_failed=False):
    try:
        available = True if (not is_failed)  else False
        try:
            Proxy.create(proxy=proxy, check_time=datetime.datetime.now(), response_time=escaped, available=available)
        except IntegrityError:
            Proxy.update(check_time=datetime.datetime.now(), response_time=escaped,
                         available=available).where(Proxy.proxy == proxy).execute()
    except Exception as e:
        log(e.args)


def log(msg):
    if using_logger:
        logger.info(msg)
    else:
        print(msg)


def http(url, data=None, session=None, proxies=None):
    try:
        headers['User-Agent'] = random.choice(user_agents)
        if data is None:
            res = requests.get(url, headers=headers, proxies=proxies) if session is None \
                else session.get(url, headers=headers, proxies=proxies)
        else:
            res = requests.post(url, headers=headers, data=data, proxies=proxies) if session is None \
                else session.post(url, headers=headers, data=data, proxies=proxies)

        code = res.status_code
        log('[{:d}] {:s} {:s}'.format(code, 'POST' if data is not None else 'GET', url))
        return res.text if code == 200 else ''
    except Exception as e:
        # log(e.args)
        # log('[{:s}] {:s} {:s}'.format('HTTP Error', 'POST' if data is not None else 'GET', url))
        return ''


def from_pachong_org():
    """
    From "http://pachong.org/"
    :return:
    """
    proxies = []

    urls = ['http://pachong.org/transparent.html',
            'http://pachong.org/high.html',
            'http://pachong.org/anonymous.html'
            ]
    for url in urls:
        sleep(0.5)
        res = http(url)

        # var duck=1159+2359
        m = re.search('var ([a-zA-Z]+)=(.*?);', res)
        if not m:
            return []

        var = {m.group(1): eval(m.group(2))}

        # var bee=6474+1151^duck;
        exprs = re.findall('var ([a-zA-Z]+)=(\d+)\+(\d+)\^([a-zA-Z]+);', res)

        for expr in exprs:
            var[expr[0]] = int(expr[1]) + int(expr[2]) ^ var[expr[3]]

        try:
            soup = BeautifulSoup(res, 'lxml')
        except:
            continue
        table = soup.find('table', class_='tb')

        for tr in table.find_all('tr'):
            data = tr.find_all('td')
            ip = data[1].text

            if not re.match('\d+\.\d+\.\d+\.\d+', ip):
                continue

            # port=(15824^seal)+1327
            script = data[2].script.text
            expr = re.search('\((\d+)\^([a-zA-Z]+)\)\+(\d+)', script)

            port = (int(expr.group(1)) ^ var[expr.group(2)]) + int(expr.group(3))
            proxies.append('%s:%s' % (ip, port))
    proxies = list(set(proxies))
    return proxies


def from_cn_proxy():
    """
    From "http://cn-proxy.com/"
    :return:
    """
    urls = [
        'http://cn-proxy.com/archives/218',
        'http://cn-proxy.com/'
    ]
    proxies = []

    for url in urls:
        sleep(0.5)
        res = http(url)
        data = re.findall('<td>(\d+\.\d+\.\d+\.\d+)</td>.*?<td>(\d+)</td>', res, re.DOTALL)

        for item in data:
            proxies.append('%s:%s' % (item[0], item[1]))
    return proxies


def from_proxy_spy():
    """
    From "http://txt.proxyspy.net/proxy.txt"
    :return:
    """
    url = 'http://txt.proxyspy.net/proxy.txt'
    res = http(url)
    proxies = re.findall('(\d+\.\d+\.\d+\.\d+:\d+) .*', res)
    return proxies


def from_xici_daili():
    """
    From "http://www.xicidaili.com/"
    :return:
    """
    urls = [
        'http://www.xicidaili.com/nt/1',
        'http://www.xicidaili.com/nt/2',
        'http://www.xicidaili.com/nn/1',
        'http://www.xicidaili.com/nn/2',
        'http://www.xicidaili.com/wn/1',
        'http://www.xicidaili.com/wn/2',
        'http://www.xicidaili.com/wt/1',
        'http://www.xicidaili.com/wt/2'
    ]

    proxies = []
    for url in urls:
        sleep(4)
        res = http(url)
        data = re.findall('<td>(\d+\.\d+\.\d+\.\d+)</td>.*?<td>(\d+)</td>', res, re.DOTALL)
        proxies += ['{:s}:{:s}'.format(host, port) for (host, port) in data]
    return proxies


def from_hide_my_ip():
    """
    From "https://www.hide-my-ip.com/proxylist.shtml"
    :return:
    """
    url = 'https://www.hide-my-ip.com/proxylist.shtml'
    res = http(url)

    data = re.findall('"i":"(\d+\.\d+\.\d+\.\d+)","p":"(\d+)"', res)
    proxies = ['{:s}:{:s}'.format(host, port) for (host, port) in data]
    return proxies


def from_cyber_syndrome():
    """
    From "http://www.cybersyndrome.net/"
    :return:
    """
    urls = [
        'http://www.cybersyndrome.net/pld.html',
        'http://www.cybersyndrome.net/pla.html'
    ]

    proxies = []
    for url in urls:
        sleep(0.5)
        res = http(url)
        proxies += re.findall('(\d+\.\d+\.\d+\.\d+:\d+)', res)
    return proxies


def from_free_proxy_list():
    """
    From "http://free-proxy-list.net/"
    :return:
    """
    urls = [
        'http://www.us-proxy.org/',
        'http://free-proxy-list.net/uk-proxy.html'
    ]
    proxies = []

    for url in urls:
        sleep(0.5)
        res = http(url)
        data = re.findall('<tr><td>(\d+\.\d+\.\d+\.\d+)</td><td>(\d+)</td>', res)
        proxies += ['{:s}:{:s}'.format(host, port) for (host, port) in data]
    return proxies


def from_gather_proxy():
    """
    From "http://www.gatherproxy.com"
    :return:
    """
    url_login = 'http://www.gatherproxy.com/subscribe/login'
    url_info = 'http://www.gatherproxy.com/subscribe/infos'
    url_download = 'http://www.gatherproxy.com/proxylist/downloadproxylist/?sid={:s}'

    session = requests.session()  # enable cookie

    # captcha like "Eight - 5"=?
    operand_map = {
        'Zero': 0, '0': 0,
        'One': 1, '1': 1,
        'Two': 2, '2': 2,
        'Three': 3, '3': 3,
        'Four': 4, '4': 4,
        'Five': 5, '5': 5,
        'Six': 6, '6': 6,
        'Seven': 7, '7': 7,
        'Eight': 8, '8': 8,
        'Nine': 9, '9': 9
    }
    operator_map = {
        'plus': '+', '+': '+',
        'multiplied': '*', 'X': '*',
        'minus': '-', '-': '-'
    }

    # get captcha
    res = http(url_login, session=session)
    m = re.search('Enter verify code: <span class="blue">(.*?) = </span>', res)
    if not m:
        return []

    calcu = m.group(1).strip()
    opers = calcu.split()
    if len(opers) != 3:
        return []

    operand1 = operand_map.get(opers[0])
    operator = operator_map.get(opers[1])
    operand2 = operand_map.get(opers[2])

    try:
        result = eval('{} {} {}'.format(operand1, operator, operand2))
    except:
        return []

    data = {
        'Username': 'jun-kai-xin@163.com',
        'Password': 'N}rS^>&3',
        'Captcha': result
    }

    # post to login and redirect to info page to get download `id`
    http(url_login, data=data, session=session)
    res = http(url_info, session=session)

    m = re.search('<p><a href="/proxylist/downloadproxylist/\?sid=(\d+)">Download', res)
    if m is None:
        return []

    data = {
        'ID': m.group(1),
        'C': '',
        'P': '',
        'T': '',
        'U': 90  # uptime
    }

    # post id to get proxy list
    res = http(url_download.format(m.group(1)), data=data, session=session)
    session.close()

    proxies = res.split('\n')  # split the txt file
    return proxies


def from_get_proxy():
    """
    From "http://www.getproxy.jp"
    :return:
    """
    base = 'http://www.getproxy.jp/proxyapi?' \
           'ApiKey=659eb61dd7a5fc509bef01f2e8b15669dfdb0f54' \
           '&area={:s}&sort=requesttime&orderby=asc&page={:d}'

    urls = [base.format('CN', i) for i in range(1, 25)]
    urls += [base.format('US', i) for i in range(1, 25)]
    urls += [base.format('CN', i) for i in range(25, 100)]
    urls += [base.format('US', i) for i in range(25, 100)]

    proxies = []

    i = 0
    retry = 0
    length = len(urls)
    while i < length:
        res = http(urls[i])
        try:
            soup = BeautifulSoup(res, 'lxml')
        except:
            i += 1
            continue

        data = soup.find_all('ip')
        if len(data) == 0:
            retry += 1
            if retry == 4:
                break
            else:
                sleep(62)
        else:
            retry = 0
            proxies += [pro.text for pro in data]
            i += 1
    return proxies


def test_proxies(proxies, timeout, single_url=None, many_urls=None):
    """
    测试代理。剔除响应时间大于timeout的代理
    :param proxies:  代理列表
    :param url:  测试链接
    :param timeout: 响应时间(s)
    :return:
    """

    proxies = set(proxies)
    errors = set()
    pool = Pool(100)

    def test(proxy):
        failed = False
        code = 403
        url = random.choice(many_urls) if many_urls is not None else single_url

        try:
            with gevent.Timeout(seconds=timeout, exception=Exception('[Connection Timeout]')):
                res = requests.get(url, proxies={'http': 'http://{}'.format(proxy.strip()),
                                                 'https': 'https://{}'.format(proxy.strip())})
                code = res.status_code
            log('[Proxy: {:d} {:s}]'.format(code, proxy))
        except Exception as e:
            # log(e.args)
            failed = True
            errors.add(proxy)

        store_in_db(proxy, status_code=code, is_failed=failed)

    for proxy in proxies:
        pool.spawn(test, proxy)
    pool.join()

    proxies = proxies - errors
    log('[HTTP Proxies] Available:{:d} Deprecated:{:d}'.format(len(proxies), len(errors)))

    return list(proxies)


def update():
    """
    从上面的网站爬取最新的代理ip
    """
    db.create_table(Proxy, safe=True)
    functions = [
        from_cn_proxy,
        from_proxy_spy, from_xici_daili,
        from_hide_my_ip, from_cyber_syndrome,
        from_free_proxy_list, from_gather_proxy,
        from_get_proxy,
        # from_pachong_org,
    ]

    proxies = []
    for func in functions:
        pro = func()
        log('[{:s}] {:d} proxies'.format(func.__name__, len(pro)))
        proxies += pro

    proxies = test_proxies(proxies, 10, single_url='https://www.baidu.com')
    log('Proxies amount: {:d}'.format(len(proxies)))


def check():
    """
    测试以及爬取的ip的可用性
    """
    proxies = [proxy.proxy for proxy in Proxy.select()]
    urls = ['https://www.avmoo.com/cn/movie/{}'.format(int2mid(i)) for i in range(1, 252604)]
    test_proxies(proxies, 10, many_urls=urls)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        using_logger = True
    update()
    # check()
