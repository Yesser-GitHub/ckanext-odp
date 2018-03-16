import json
import logging
import requests
import functools
import tempfile
import datetime
import collections

import pathlib2
import paste.script

from ckan.lib.cli import CkanCommand
import ckan.logic as logic
import ckan.model as model

logger = logging.getLogger(__name__)


class KSACommand(CkanCommand):
    """
    ckanext-ksa management commands.

    Usage::
        paster ksa [command]
    Commands::
        pull-data - get all datasets from data.gov.sa and store
                    them in temporary dir
        inject-pulled-data - ...

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

    parser.add_option(
        '-d', '--dir-with-data', help='Dir where is stored pulled data'
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

    def inject_pulled_data(self):
        dir_with_data = self.options.dir_with_data
        if not dir_with_data:
            logger.info('Data dir is not provided. Pulling data...')
            dir_with_data = self.pull_data()
        site_user = logic.get_action('get_site_user')()
        logger.debug(
            'Using <User name={name} api_key={apikey}>'.format(**site_user)
        )
        path = pathlib2.Path(dir_with_data)
        pkg_counter = collections.Counter()
        res_counter = collections.Counter()
        entity_counter = collections.Counter()
        group_set = set()
        for doc in path.iterdir():
            with doc.open() as fd:
                data = json.load(fd)
                datasets = data['result']
                logger.debug(
                    '{:3} datasets inside file://{}'.format(
                        len(datasets), doc
                    )
                )
                entity_counter.update(dataset=len(datasets))
                for dataset in datasets:
                    try:
                        pkg_counter.update(dataset.keys())
                        resources = dataset.get('resources', [])
                        entity_counter.update(resource=len(resources))
                        for group in dataset.get('groups', []):
                            group['name'] = group['id']
                            group['image_url'] = group['image_display_url']
                            if group['id'] not in group_set:
                                logic.get_action('group_create')(
                                    dict(model=model, user=site_user['name']),
                                    group
                                )
                        for res in resources[:]:
                            res_counter.update(res.keys())
                            if not res['name']:
                                logger.warn(
                                    'Incorrect resource inside {}({})\n\t{}'.
                                    format(dataset['id'], doc, res)
                                )
                                resources.remove(res)
                                continue
                            if res['size']:
                                res['size'] = int(
                                    float(res['size'].split()[0]) * 1024
                                )
                            res['last_modified'] = _reformat_date(
                                res['last_modified']
                            )
                            res['created'] = _reformat_date(res['created'])
                        dataset['name'] = dataset['id']
                        dataset['state'] = dataset['state'].lower()
                        dataset['type'] = dataset['type'].lower()
                        dataset['license_id'] = dataset['license_title']
                        pkg_dict = logic.get_action('package_create')(
                            dict(user=site_user['name'], model=model), dataset
                        )
                        logger.debug(
                            'Created dataset with id: {}'.format(
                                pkg_dict['id']
                            )
                        )
                    except Exception as e:
                        logger.error(
                            '{}:<{}> {}, {}'.format(
                                type(e), dataset['id'], e, vars(e)
                            )
                        )

        log_stats(entity_counter, pkg_counter, res_counter)

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
        logger.debug('API site_read response: {}'.format(res.json()))

        tmp_prefix = '{}-data.gov.sa-'.format(datetime.datetime.now().date())
        tmp_dir = pathlib2.Path(tempfile.mkdtemp(prefix=tmp_prefix))
        for offset, data in request_pack_of_datasets(get, url, limit):
            file_path = tmp_dir / '{:0>4}-{:0>4}.json'.format(
                offset, offset + limit
            )
            logger.info('Writing [file://{}]'.format(file_path))
            file_path.write_bytes(data)
        logger.info(
            'Completed. Data stored inside [file://{}] folder'.format(tmp_dir)
        )
        return tmp_dir


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


def log_stats(entity, pkg, res):
    logger.info('Dataset stats:')
    logger.info('\tTotal: {0}'.format(entity['dataset']))
    logger.info('\tFields:')
    for field, count in pkg.items():
        logger.info('\t\t{:20}: {:6} times'.format(field, count))
    logger.info('Resource stats:')
    logger.info('\tTotal: {0}'.format(entity['resource']))
    logger.info('\tFields:')
    for field, count in res.items():
        logger.info('\t\t{:20}: {:6} times'.format(field, count))


def _reformat_date(date):
    dt = date.split(',')[-1].strip()
    return datetime.datetime.strptime(dt, '%d/%m/%Y - %H:%M')
