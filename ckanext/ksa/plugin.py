import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import ckanext.ksa.helpers as ksa_helpers

class KsaPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IRoutes, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'ksa')

    # ITemplateHelpers

    def get_helpers(self):
        return ksa_helpers.get_ksa_helpers()

    def before_map(self, routeMap):
        """ Use our custom controller, and disable some unwanted URLs
        """
        controller = 'ckanext.ksa.controller:KsaController'

        return routeMap
