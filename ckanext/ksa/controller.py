import ckan.lib.base as base
from ckan.lib.base import BaseController, render
from ckan.common import request, c
import ckan.logic as logic

class KsaController(BaseController):

    def translations(self):
        if request.method == 'POST':
            en = request.params.get('en')
            ar = request.params.get('ar')
            context = {
                'user': c.user
            }
            data_dict = {
                'term': en,
                'term_translation': ar,
                'lang_code': 'ar'
            }
            res = logic.get_action('term_translation_update')(context, data_dict)

        return base.render('translations.html')
