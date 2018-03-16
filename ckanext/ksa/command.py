import logging
import requests
import functools
import tempfile
import datetime

import pathlib2
import paste.script

from ckan.lib.cli import CkanCommand

logger = logging.getLogger(__name__)


class KSACommand(CkanCommand):
    """
    ckanext-ksa management commands.

    Usage::
        paster ksa [command]
    Commands::
        pull-data - get all datasets from data.gov.sa and store
                    them in temporary dir

    """

    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option(
        '-c',
        '--config',
        dest='config',
        default='../development.ini',
        help='Config file to use.'
    )
    parser.add_option(
        '-u', '--use-proxy', action='store_true', help='Enable proxy'
    )
    parser.add_option('-s', '--socks', default='localhost:2001')

    def command(self):
        self._load_config()
        logger.disabled = False

        action = self.args[0] if self.args else ''
        action = action.replace('-', '_')

        if getattr(self, action, None) is None:
            return self.usage

        return getattr(self, action)()

    def pull_data(self):
        limit = 20
        proxies = {}
        if self.options.use_proxy:
            addr = 'socks5://{}'.format(self.options.socks)
            logger.debug('Using proxy: {}'.format(addr))
            proxies.update(http=addr, https=addr)
        get = functools.partial(requests.get, proxies=proxies)

        url = 'http://data.gov.sa/api/3/action/'
        logger.debug('Using <{}> as API base'.format(url))

        try:
            res = get(url + 'site_read', proxies=proxies, timeout=10)
        except requests.exceptions.ReadTimeout:
            logger.error(
                'Remote portal is not available. Try to use proxy(-u flag)'
            )
            exit(1)
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error('HTTPError: {}'.format(e.message))
            exit(1)
        logger.debug(res.json())

        tmp_prefix = '{}-data.gov.sa-'.format(datetime.datetime.now().date())
        tmp_dir = pathlib2.Path(tempfile.mkdtemp(prefix=tmp_prefix))

        for offset, data in request_pack_of_datasets(get, url, limit):
            file_path = tmp_dir / '{}-{}.json'.format(offset, offset + limit)
            logger.info('Writing <{}>'.format(file_path))
            file_path.write_bytes(data)
        logger.info(
            'Completed. Data stored inside <{}> folder'.format(tmp_dir)
        )


def request_pack_of_datasets(get, url, limit):
    params = dict(limit=limit, offset=0)
    endpoint = url + 'current_package_list_with_resources'
    while True:
        logger.debug('Request to <{}> with params {}'.format(endpoint, params))
        resp = get(endpoint, params=params)

        if resp.ok:
            logger.debug(
                'Success({}, {})'.format(
                    params['offset'], params['offset'] + params['limit']
                )
            )
            if not resp.json()['result']:
                break
            yield params['offset'], resp.content
        else:
            logger.warn(
                'Fail({}, {}). {}'.format(
                    params['offset'], params['offset'] + params['limit'],
                    resp.text
                )
            )

        params['offset'] += limit
