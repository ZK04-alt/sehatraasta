"""Run with: python -m sehatraasta.web --database instance/sehatraasta.sqlite"""
import argparse
from werkzeug.serving import WSGIRequestHandler, run_simple
from . import create_app


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass  # No record IDs, query strings or user text in access logs.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SehatRaasta local website')
    parser.add_argument('--database', default='instance/sehatraasta.sqlite')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    app = create_app({'DATABASE': args.database})
    run_simple('127.0.0.1', args.port, app, use_debugger=False, use_reloader=False,
               threaded=False, request_handler=QuietHandler)
