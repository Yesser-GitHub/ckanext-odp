import ckan.logic as logic
import json

def get_ksa_helpers():
    return {
        'ksa_group_list': ksa_group_list,
        'get_ksa_group_img': get_ksa_group_img,
    }

def ksa_group_list():
    response = logic.get_action('group_list')({}, {})
    return response

def get_ksa_group_img(group):
    response = logic.get_action('group_show')({}, {'id': group})
    img = response.get('image_url', '')
    return img
