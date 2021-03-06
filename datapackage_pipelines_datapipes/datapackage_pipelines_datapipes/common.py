import logging
import os

from datapackage_pipelines.utilities.extended_json import LazyJsonLine, json

only_last = os.environ.get('DATAPIPES_DOWNLOAD') is not None


class LoggerImpl:

    def __init__(self, parameters):
        self.bad_values = 0
        self.uuid = parameters['uuid']

    def _send(self, msg):
        msg['uuid'] = self.uuid
        if only_last and self.uuid == 'last':
            logging.info(json.dumps(msg))
        elif not only_last and self.uuid != 'last':
            logging.info(json.dumps(msg))

    def _event(self, ev, **kwargs):
        kwargs['e'] = ev
        self._send(kwargs)

    def start(self):
        self._event('start')

    def error(self, msg):
        self._event('err', msg=msg)

    def bad_value(self, res, idx, data, field, value):
        if self.bad_values < 100:
            self._event('ve', res=res, idx=idx, data=data, field=field, value=value)
        self.bad_values += 1

    def done(self):
        self._event('done', bad_values=self.bad_values)

    def line_filter(self, i, scale):
        for _ in range(10):
            new_scale = scale * 10
            if i <= new_scale:
                return scale, i % scale == 0
            scale = new_scale

    def log_rows(self, dp, res_iter):
        def res_logger(spec_, res_):
            last = []
            scale = 1
            self._event('rs', data=spec_['schema']['fields'])
            for i, row in enumerate(res_):
                scale, show = self.line_filter(i, scale)
                if show or only_last:
                    if isinstance(row, LazyJsonLine):
                        row = dict(row)
                    self._event('r', res=spec_['name'], idx=i, data=row)
                    last = []
                else:
                    last.append((i, row))
                    if len(last) > 5:
                        last.pop(0)
                yield row
            for i, row in last:
                if isinstance(row, LazyJsonLine):
                    row = dict(row)
                self._event('r', res=spec_['name'], idx=i, data=row)

        for spec, res in zip(dp['resources'], res_iter):
            yield res_logger(spec, res)


class Logger:

    def __init__(self, parameters):
        self.parameters = parameters

    def __enter__(self):
        self.logger = LoggerImpl(self.parameters)
        self.logger.start()
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            logging.exception('Processor failed')
            self.logger.error(str(exc_val))
        self.logger.done()
        return True
