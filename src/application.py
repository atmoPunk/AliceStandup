import ssl
import logging
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from dialog import DialogHandler

application = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)


@application.route('/', methods=['POST'])
def webhook():
    logging.info('Request: %r', request.json)
    handler = DialogHandler()
    handler.handle_dialog(request.json)
    response = {'version': request.json['version'],
                'session': request.json['session'],
                'response': handler.response}
    logging.info('Response: %r', response)
    return jsonify(response)


if __name__ == '__main__':
    load_dotenv()
    context = ssl.SSLContext()
    context.load_cert_chain(os.getenv('SSL_CERT'), os.getenv('SSL_KEY'))
    application.run(host='0.0.0.0', ssl_context=context)
