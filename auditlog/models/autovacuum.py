# Copyright 2016 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
from datetime import datetime, timedelta

from odoo import models, fields, api, registry
from odoo.tools.misc import split_every

_logger = logging.getLogger(__name__)


class AuditlogAutovacuum(models.TransientModel):
    _name = 'auditlog.autovacuum'
    _description = "Auditlog - Delete old logs"

    @api.model
    def autovacuum(self, days):
        """Delete all logs older than ``days``. This includes:
            - CRUD logs (create, read, write, unlink)
            - HTTP requests
            - HTTP user sessions

        Called from a cron.
        """
        days = (days > 0) and int(days) or 0
        deadline = datetime.now() - timedelta(days=days)
        data_models = (
            'auditlog.log',
            'auditlog.http.request',
            'auditlog.http.session',
        )
        # Create a new cursor to run this action
        cr = registry(self._cr.dbname).cursor()
        # Assign this cursor to self and all arguments to ensure consistent
        # data in all method
        self = self.with_env(self.env(cr=cr))

        SPLIT = 10000
        for data_model in data_models:
            records = self.env[data_model].search(
                [('create_date', '<=', fields.Datetime.to_string(deadline))]
            )
            idx = 0
            for ids in list(split_every(SPLIT, records.ids)):
                _logger.info(
                    '%s AUTOVACUUM (%d -> %d)/%d', data_model, idx,
                    min(idx + SPLIT, len(records.ids)), len(records.ids)
                )
                idx += SPLIT
                self.env[data_model].browse(ids).unlink()
                # Commit this deletion to keep it even after a worker timeout
                self.env.cr.commit()

        self.env.cr.close()
        return True
