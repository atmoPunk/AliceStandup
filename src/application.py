import logging
import os
import ssl

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from dialog import DialogHandler, AuthorizationRequest
from request import Request
from storage import StorageConnectionFactory

application = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)


@application.route('/', methods=['POST'])
def webhook():
    logging.info('Request: %r', request.json)
    handler = DialogHandler(StorageConnectionFactory())
    response = {'version': request.json['version'],
                'session': request.json['session']}
    try:
        handler.handle_dialog(Request(request.json))
        response['response'] = handler.response
    except AuthorizationRequest:
        response['start_account_linking'] = {}
    logging.info('Response: %r', response)
    return jsonify(response)


if __name__ == '__main__':
    load_dotenv()
    context = ssl.SSLContext()
    context.load_cert_chain(os.getenv('SSL_CERT'), os.getenv('SSL_KEY'))
    application.run(host='0.0.0.0', ssl_context=context)
