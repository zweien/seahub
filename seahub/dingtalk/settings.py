import seahub.settings as settings
ENABLE_DINGTALK_QR_CONNECT = getattr(settings, 'ENABLE_DINGTALK_QR_CONNECT', False)
APP_ID = getattr(settings, 'DINGTALK_QR_CONNECT_APP_ID', '')
APP_SECRET = getattr(settings, 'DINGTALK_QR_CONNECT_APP_SECRET', '')
REDIRECT_URL = getattr(settings, 'DINGTALK_QR_CONNECT_REDIRECT_URL', '')

AUTHORIZATION_URL = getattr(settings, 'DINGTALK_QR_CONNECT_AUTHORIZATION_URL', 'https://oapi.dingtalk.com/connect/qrconnect')
USER_INFO_URL = getattr(settings, 'DINGTALK_QR_CONNECT_USER_INFO_URL', 'https://oapi.dingtalk.com/sns/getuserinfo_bycode')
RESPONSE_TYPE = getattr(settings, 'DINGTALK_QR_CONNECT_RESPONSE_TYPE', 'code')
SCOPE = getattr(settings, 'DINGTALK_QR_CONNECT_SCOPE', 'snsapi_login')
PROVIDER_DOMAIN = getattr(settings, 'DINGTALK_QR_CONNECT_PROVIDER_DOMAIN', 'dingtalk.com')
